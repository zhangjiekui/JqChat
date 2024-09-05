from abc import ABC, abstractmethod
from typing import List, Optional, Union, Callable

from langchain.schema import Document as LcDocument
from llama_index.core import Document as LmDocument
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
from jqcode.jq_docstores.base_docstores import JqBaseDocumentStore
from jqcode.jq_agent.c0_init_env_models import env_models_instance
import hashlib
from datetime import datetime
import yaml
import copy 
from anytree.exporter import DictExporter
from anytree.importer import DictImporter
from anytree import RenderTree
from pathlib import Path

from jqcode.jq_agent.c0_init_env_models import env_models_instance
from jqcode.jq_readers.jqkj_readers import JqkjSimpleDirectoryReader
from jqcode.jq_agent.tools.jq_retriever import get_retriever

from langchain.schema import Document as LcDocument
from base64 import b64encode,b64decode

from jqcode.jq_utils.logger import jqkj_logger
logger = jqkj_logger(__file__).get_logger()

MAX_DOCS_TO_GET = 10**4
anytree_dict_exporter = DictExporter()
anytree_dict_importer = DictImporter()

def md5_text_value(text:str):
    md5_hash = hashlib.md5()
    md5_hash.update(text.encode())
    return md5_hash.hexdigest()

# 参考源码：https://github.com/Cinnamon/kotaemon/blob/4f0785773df718a6dc7a3928482bd5b8b12c0bfc/libs/kotaemon/kotaemon/storages/docstores/elasticsearch.py
# 如何搜索的示例代码：https://github.com/elastic/elasticsearch-labs
# /data/projects/JqChatV2/JqChat/jqcode/es_code_example.py

# todo:增加Filters
class JqElasticsearchUniMetaStore(JqBaseDocumentStore):
    """Elasticsearch document store that store file/document in a ES database"""

    def __init__(
        self,        
        elasticsearch_connection: Elasticsearch = env_models_instance.get_es_connection(),
        k1: float = 2.0,
        b: float = 0.75,        
        **kwargs,
    ):
        self.index_name = "unimetastore"
        self.k1 = k1
        self.b = b
        # Create an Elasticsearch client instance
        self.client = elasticsearch_connection
        self.es_bulk = bulk     


        
        # Define the index settings and mappings
        settings = {"similarity": {"custom_bm25": {"type": "BM25", "k1": k1, "b": b}}}
        settings.update(env_models_instance.ES_DEFAULT_CHINESE_SETTINGS)
   
        mappings = {"properties": {
            "index_name": {"type": "keyword"},
            "description": {
                "type": "text",
                "similarity": "custom_bm25",  # Use the custom BM25 similarity
            },

            # 创建的用户
            "index_creator": {"type": "keyword"},
            # 创建的日期
            "index_create_date": {"type": "date", "format": "yyyy-MM-dd HH:mm:ss||strict_date_optional_time ||epoch_millis"},

            # 是否启用：启用（True）、弃用(False)
            # 由于index是独立创建的，有可能某个index已经删除了，如果监测到，可以将该状态设为False
            "status": {"type": "boolean"},
        }
        }

        # Create the index with the specified settings and mappings
        if not self.client.indices.exists(index=self.index_name):
            self.client.indices.create(
                index=self.index_name, settings=settings, mappings=mappings
            )
        self.count = 0
        self.ids = []
        try: 
            self.count = self._count()
            self.ids = self._ids()
        except:
            pass

    def add_or_update_index_metadata_if_id_exists(
        self,
        index_id:str="",
        index_name:str="",
        description:str="",
        index_creator:str = "manager",
        status:bool=True, 
        allow_create_new = False,   
        refresh_indices: bool = True,
        **kwargs,
    ):
        """Add metadata into meta store.

        Args:
            description:str,index的描述
            index_creator:str, 创建index的用户 
            refresh_indices: request Elasticsearch to update its index (default to True)
        """
        dt = datetime.now()
        fmt = "%Y-%m-%d %H:%M:%S"
        dt_string = dt.strftime(fmt)
        rs = []
        request = []
        
        
        if index_id and index_name:
            if index_id != md5_text_value(index_name):
                logger.warning("index_id和index_name都提供了，但彼此不一致！忽略此次操作。")
                return False,''        
        
        elif index_name or index_id:
            if index_id:
                logger.debug(f"根据提供的{index_id=}进行查询......")
                # 检查index_id是否存在且只有一个        
                rs = self.get_docs_by_ids(index_id)
                if len(rs)!=1:
                    logger.warning(f"根据提供的{index_id=}得到的查询结果不唯一！忽略此次操作。")
                    return False,''
                
            else:
                logger.debug(f"根据提供的{index_name=}进行校验......")
                if not isinstance(index_name,str) or len(index_name)<=3:
                    logger.warning(f"{index_name=}必须是有效的字符串,且长度必须大于3！忽略此次操作。")
                    return False,''
        else:
            logger.warning(f"{index_id=}、{index_name=}不能都为空！忽略此次操作。")
            return False,''        
                
        index_id = index_id if index_id else md5_text_value(index_name)
        # 检查index_id是否存在且只有一个        
        rs = self.get_docs_by_ids(index_id)
        if len(rs)>1:
            logger.warning(f"根据提供的{index_id=}得到的查询结果不唯一！忽略此次操作。")
            return False,''                
        else:
            if len(rs)==0:
                if not allow_create_new:
                    logger.warning(f"根据提供的{index_id=}、{index_name=}没有查询到记录！但又不允许创建新纪录{allow_create_new=}，忽略此次操作。")
                    return False,''
            try:                     
                r=rs[0]["_source"]
                index_name = index_name if index_name else r['index_name']
                description = description if description else r['description']
                index_creator = index_creator if index_creator else r['index_creator']
                status = status if status else r['status']

                request = {                
                    "index_name":index_name,
                    "description":description,
                    "index_creator": index_creator,
                    "index_create_date": dt_string,
                    "status":status,
                    }           

                action = {"_op_type": "index","_index":self.index_name, "_id":index_id, "_source":request}
                    
                success, failed = self.es_bulk(self.client, [action])
                logger.info(f"Added/Updated {index_name}(id:{index_id}) to Metastore '{self.index_name}'")
                status = True
                if refresh_indices:
                    self.client.indices.refresh(index=self.index_name)
                return status,index_id
            except Exception as e:
                logger.error(e)
                try:
                    error = e.errors[0]
                    logger.error(error["index"]["error"])
                except:
                    pass
                status = False
                return status,index_id


    def update_doc_fields_values(self, index_id:str="", index_name:str="",update_field_value_pair_dict:Union[dict,List[dict]]=None,refresh_indices:bool=True):
        """Update documents【由list doc_ids指定】 fields with new values 【由update_field_value_pair_dict指定】

            Args:
                index_id：要更新的index的id
                index_name:要更新的index的name,
                    1）如果index_id已经提供，则忽略该值
                    2）试图以此index_name去检索匹配记录，如果匹配结果是唯一的，则执行更新，否则返回匹配到的多个ids
                update_field_value_pair_dict: Union[dict,List[dict]]，指定要更新的Filed_name和对应的New_value
                    形如: update_field_value_pair_dict = {"status":"false","description":"new description in string length>10", "index_creator":"new_name"}
                refresh_indices: bool. request Elasticsearch to update its index (default to True)

            Returns:status,bool. 代表更新成功或失败！
        """
        status,index_id = self.add_or_update_index_metadata_if_id_exists(index_id=index_id,index_name=index_name,allow_create_new=False,**update_field_value_pair_dict)
        return status,index_id
      
    
    def query_raw(self, query: dict) -> List[LmDocument]:
        """Query Elasticsearch store using query format of ES client

        Args:
            query (dict): Elasticsearch query format

        Returns:
            List[LmDocument]: List of result documents
        """
        res = self.client.search(index=self.index_name, body=query)
        rs = []
        for r in res["hits"]["hits"]:
            rs.append(r)           
        return rs
        
    def _get_query(self,user_query_text: str=None,size=MAX_DOCS_TO_GET,query_on_fileds:list = ["index_name","description"], filter_by_index_creators:list=None,filter_by_status:list=["true","false"]):
        # 即使用户没有提供status或status为空，因爲status状态少，好构造全集，所以放在第一个，总是存在
        _status = filter_by_status if filter_by_status else ["true","false"]
        filer_terms = [{"terms": {"status": _status}}]
        if filter_by_index_creators:
            filer_terms.append({"terms": {"index_creator": filter_by_index_creators}})     
        
        query = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "multi_match": {
                                "query": user_query_text,
                                "fields": query_on_fileds,
                                "type": "cross_fields"
                            }
                        }
                    ],
                    "filter": filer_terms,
                }
            },
            "size": size,  # 注意设置size，默认返回10个。
        }
        return query
    
    # 如何搜索的示例代码：https://github.com/elastic/elasticsearch-labs
    def search_docs_by_text(self, user_query_text: str=None,top_k: int = 10, query_on_fileds:list =["index_name","description"], filter_by_index_creators:list=None,filter_by_status:list=["true","false"]) -> List[LmDocument]:
        """Query Elasticsearch store using query format of ES client

        Args:
            user_query_text (str): 用户要搜索的文本            


        Returns:
            List[Document]: List of result documents
        """
        query = self._get_query(user_query_text=user_query_text,size=top_k,query_on_fileds=query_on_fileds,filter_by_index_creators=filter_by_index_creators,filter_by_status=filter_by_status)      
        rs = self.query_raw(query)
        return rs

    def get_docs_by_ids(self, ids: Union[List[str], str]) -> List[LmDocument]:
        """Get document by id"""
        if not isinstance(ids, list):
            ids = [ids]
        query_dict = {"query": {"terms": {"_id": ids}}, "size": MAX_DOCS_TO_GET}
        return self.query_raw(query_dict)
    
    def get_all_docs(self) -> List[LmDocument]:
        """Get all documents"""
        query = {"query": {"match_all": {}}, "size": MAX_DOCS_TO_GET}
        return self.query_raw(query)

    def _count(self) -> int:
        """Count number of documents"""
        count = int(
            self.client.cat.count(index=self.index_name, format="json")[0]["count"]
        )
        return count
    
    def _ids(self) -> set[str]:
        rs = self.get_all_docs()
        ids = [r["_id"] for r in rs]
        return set(ids)

    def delete(self, ids: Union[List[str], str]):
        """Delete document by id"""
        if not isinstance(ids, list):
            ids = [ids]

        query = {"query": {"terms": {"_id": ids}}}
        self.client.delete_by_query(index=self.index_name, body=query)
        self.client.indices.refresh(index=self.index_name)

    def drop(self):
        """Drop the document store"""
        self.client.indices.delete(index=self.index_name)
        self.client.indices.refresh(index=self.index_name)

    def get_settings_and_mappings(self):
        settings = self.client.indices.get_settings(index=self.index_name) 
        mappings = self.client.indices.get_mapping(index=self.index_name)
        return settings,mappings
    
if __name__ == "__main__":
    metastore = JqElasticsearchUniMetaStore()
    index_id="myindex"
    status,id=metastore.add_or_update_index_metadata_if_id_exists(index_id=index_id,description="修改了myindex，index的详细描述，不少于10个字")
    status,id=metastore.add_or_update_index_metadata_if_id_exists(index_name="myindex",description="index的详细描述，不少于10个字")
    print(id)
    status,id=metastore.add_or_update_index_metadata_if_id_exists(index_name="notallow_myindex",description="index的详细描述，不少于10个字")
    print(id)
    status,id=metastore.add_or_update_index_metadata_if_id_exists(index_name="notallow_myindex",description="index的详细描述，不少于10个字",allow_create_new=True)
    print(id)
    update_field_value_pair_dict = {"status":"false","description":"new description in string length>10", "index_creator":"new_name"}
    status,id = metastore.update_doc_fields_values(index_name="notallow_myindex",update_field_value_pair_dict=update_field_value_pair_dict)
    print(id)
    print(f"{metastore.count=}")
    ids = metastore.ids
    print(f"{metastore.ids=}")

