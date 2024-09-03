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

def md5_file_value(file_base64_data:bytes):#Binary value encoded as a Base64 string
    md5_hash = hashlib.md5()
    md5_hash.update(file_base64_data)
    return md5_hash.hexdigest()

# 参考源码：https://github.com/Cinnamon/kotaemon/blob/4f0785773df718a6dc7a3928482bd5b8b12c0bfc/libs/kotaemon/kotaemon/storages/docstores/elasticsearch.py
# 如何搜索的示例代码：https://github.com/elastic/elasticsearch-labs
# /data/projects/JqChatV2/JqChat/jqcode/es_code_example.py
class JqElasticsearchDocumentStore(JqBaseDocumentStore):
    """Elasticsearch document store that store file/document in a ES database"""

    def __init__(
        self,
        index_name: str = "docstore",
        elasticsearch_connection: Elasticsearch = env_models_instance.get_es_connection(),
        k1: float = 2.0,
        b: float = 0.75,        
        **kwargs,
    ):
        self.index_name = index_name
        self.k1 = k1
        self.b = b
        # Create an Elasticsearch client instance
        self.client = elasticsearch_connection
        self.es_bulk = bulk
        
        self.count = self.count()
        self.ids = self.ids()

        
        # Define the index settings and mappings
        settings = {
                        "index": {"analysis.analyzer.default.type": "ik_max_word","analysis.search_analyzer.default.type": "ik_smart"},
                        "similarity": {"custom_bm25": {"type": "BM25", "k1": k1, "b": b}},
                   }
   
        mappings = {"properties": {

                            "file_name": {
                                "type": "text",
                                "similarity": "custom_bm25",  # Use the custom BM25 similarity
                            },

                            "file_extention": {"type": "keyword"}, 

                            "file_metadata":{"type": "object"}, # https://www.elastic.co/guide/en/elasticsearch/reference/current/flattened.html

                            "file_blob":{"type": "binary"},  # Binary value encoded as a Base64 string. 

                            "file_yaml":{"type": "binary"},                              
                            
                            # 由chunks JOIN而成的
                            "file_text": {
                                "type": "text",
                                "similarity": "custom_bm25",  # Use the custom BM25 similarity
                            },
                            # 上传的用户
                            "file_upload_user": {"type": "keyword"},
                            # 上传的日期
                            "file_upload_date": {"type": "date","format":"yyyy-MM-dd HH:mm:ss||strict_date_optional_time ||epoch_millis"},
                            # "file_upload_date": {"type": "date"},

                            # 因为这里存储的是文档：
                                #该文档的切片可能出现在0-N个index中，
                                #如果监测到，可以更新该字段值，取值为逗号分隔的字符串： index_name1,index_name2,
                            "file_used_in_indexes": {"type": "keyword"},

                            # 是否：在用（True）、已弃用(False)
                            # 因为这里存储的是文档：
                                # （1）文档管理的时候，本来就可以删除，如果删除，该状态可以标识了False，相当于逻辑删除
                                # （2）由于文档的切片是在另外的index中存储的，有可能该文档对应的切片已经全部删除了，如果监测到，可以将该状态设为False
                            "status": {"type": "boolean"},
                        }
                    }

        # Create the index with the specified settings and mappings
        if not self.client.indices.exists(index=self.index_name):
            self.client.indices.create(
                index=self.index_name, settings=settings, mappings=mappings
            )

    def add_or_update_docs_if_id_exists(
        self,
        lm_documents: Union[LmDocument, List[LmDocument]],
        ids: Optional[Union[List[str], str]] = None,
        default_id_func:Callable = md5_file_value,
        file_upload_user:str = "manager",        
        refresh_indices: bool = True,
        **kwargs,
    ):
        """Add lm_documents into document store.

        Args:
            lm_documents: list of lm_documents to be added
            ids: specify the ids of lm_documents to be added or use default_id_func to generate
            default_id_func:默认的id生成函数，如果没有提供ids，则使用该id生成函数生成id，默认为md5
            file_upload_user:上传文档的用户ID
            refresh_indices: request Elasticsearch to update its index (default to True)
        """
        if not isinstance(lm_documents, list):
            lm_documents = [lm_documents]
        
        actions_list = []
        es_index_doc_id_list = []
        for document in lm_documents:
            file_name = document.metadata.get('file_name',None) or document.metadata.get('file_name_jq',None)
            file_text = document.text
            file_path = document.metadata['source']            
            file_extention = Path(file_path).suffix            

            file_blob_b64 = None
            file_data = None
            with open(file_path, 'rb') as file: 
                file_data = file.read()
                
            file_blob_b64_encoded = b64encode(file_data)
            es_index_doc_id = default_id_func(file_blob_b64_encoded)

            file_blob_b64=file_blob_b64_encoded.decode('utf-8')
           
            

            added_metadata = {"file_extension":file_extention,'es_index_name':self.index_name,"es_index_doc_id":es_index_doc_id}
            document.metadata.update(added_metadata)

            file_metadata = copy.deepcopy(document.metadata)
            _df_table_list_jq = file_metadata.pop('df_table_list_jq',None)
            _file_doc_object_jq = file_metadata.pop('file_doc_object_jq',None)
            doc_tree = file_metadata.pop('file_doc_tree_jq',None)

            file_yaml = ''
            if doc_tree:
                doc_tree_dict = anytree_dict_exporter.export(doc_tree)
                file_yaml = yaml.dump(doc_tree_dict, default_flow_style=False)
            
            dt = datetime.now()
            fmt = "%Y-%m-%d %H:%M:%S"
            dt_string = dt.strftime(fmt)

            request = {                
                "file_name":file_name,
                "file_extention":file_extention,
                "file_text":file_text,
                "file_metadata":file_metadata,
                "file_upload_user": file_upload_user,
                "file_upload_date": dt_string,
                "file_used_in_indexes": "",
                "status":False,
                "file_blob":file_blob_b64,
                "file_yaml":file_yaml,
                }
            action = {"_op_type": "index","_index":self.index_name, "_id":es_index_doc_id, "_source":request}
            actions_list.append(action)
            es_index_doc_id_list.append(es_index_doc_id)

        try:        
            success, failed = self.es_bulk(self.client, actions_list)
            logger.info(f"Added/Updated {success} documents to index '{self.index_name}'")
            failed_num = failed if failed else 0
            logger.info(f"Failed {failed_num} documents to index '{self.index_name}'" )
            status = True
            if refresh_indices:
                self.client.indices.refresh(index=self.index_name)
            logger.info("=====上传完成======"*5)
            return status,lm_documents,es_index_doc_id_list
        except Exception as e:
            logger.error(e)
            try:
                error = e.errors[0]
                logger.error(error["index"]["error"])
            except:
                pass
            status = False
            return status,[],[]

    def update_doc_fields_values(self, doc_ids:list=[],update_field_value_pair_dict:Union[dict,List[dict]]=None,apply_update_to_all_files:bool=True,refresh_indices:bool=True):
        """Update documents【由list doc_ids指定】 fields with new values 【由update_field_value_pair_dict指定】

            Args:
                doc_ids: list. specify the ids of documents to be updated
                    如果为空，但apply_update_to_all_files=True时，将会更新全部记录（但上限为MAX_DOCS_TO_GET）
                    如果不为空，将自动忽略apply_update_to_all_files
                
                update_field_value_pair_dict: Union[dict,List[dict]]，指定要更新的Filed_name和对应的New_value
                    形如: update_field_value_pair_dict = {"status":"false","file_text":"new_file_text"}

                    当apply_update_to_all_files=True时，update_field_value_pair_dict必须为dict
                    当doc_ids不为空时，update_field_value_pair_dict必须为List[dict]，且两者的长度必须一致
                    ！！警告！！：New_value必须以string的形式提供，如：status字段的类型为Mapping类型为Boolean，但必须以这样的方式来提供字段值：{"status":"false"}
                
                apply_update_to_all_files:bool. 只在doc_ids为空的情况下起作用

                refresh_indices: bool. request Elasticsearch to update its index (default to True)

            Returns:status:bool. 代表更新成功或失败！
        """
        if not doc_ids:
            if apply_update_to_all_files:
                try:
                    update_str=''
                    for field,new_value in update_field_value_pair_dict.items():
                        if not isinstance(new_value,str):
                            raise ValueError(f"更新Index时，提供的字段值必须是str类型，但现在:{type(new_value)=}")
                        new_value = f'"{new_value}"'
                        update_str += f'ctx._source.{field}={new_value};'
                        
                    resp = self.client.update_by_query(index=self.index_name,
                                                    conflicts="proceed",
                                                    script={
                                                                "source":update_str,
                                                                "lang": "painless"
                                                                }
                                                    )
                    logger.info(f"更新结果:{resp}")
                    if refresh_indices:
                        self.client.indices.refresh(index=self.index_name)
                    return True
                except Exception as e:
                    logger.error(f"更新失败:{e}")
            else:
                logger.warning(f"在{apply_update_to_all_files=}的情况下，参数doc_ids不能为空！")
                logger.warning(f"如果是想更新全部记录，请设置参数apply_update_to_all_files=True！")
                return False
        if doc_ids:
            try:
                if not isinstance(doc_ids,list):
                    raise ValueError("doc_ids的类型必须是list！")
                if not  isinstance(update_field_value_pair_dict,list):
                    raise ValueError("当doc_ids不为空时，update_field_value_pair_dict的类型必须是list！")
                len_FV = len(update_field_value_pair_dict)
                if not (len_FV==1 or len_FV==len(doc_ids)):
                    raise ValueError(f"update_field_value_pair_dict:list的长度要么为1，要么与{len(doc_ids)=}一致!")
                
                actions_list = []
                for i,doc_id in enumerate(doc_ids):
                    field_value_pair_dict = update_field_value_pair_dict[0] if len_FV ==1 else update_field_value_pair_dict[i]
                    _source = {"doc":field_value_pair_dict}
                    action = {"_op_type": "update","_index":self.index_name, "_id":doc_id, "_source":_source}
                    actions_list.append(action)

                
                success, failed = self.es_bulk(self.client, actions_list)
                if refresh_indices:
                    self.client.indices.refresh(index=self.index_name)
                logger.info(f"Added/Updated {success} documents to index '{self.index_name}'")
                failed_num = failed if failed else 0
                logger.info(f"Failed {failed_num} documents to index '{self.index_name}'" )
                return True
            except Exception as e:
                logger.error(e)
                try:
                    error = e.errors[0]
                    logger.error(error["index"]["error"])
                except:
                    pass
                return False
    
    def query_raw(self, query: dict) -> List[LmDocument]:
        """Query Elasticsearch store using query format of ES client

        Args:
            query (dict): Elasticsearch query format

        Returns:
            List[LmDocument]: List of result documents
        """
        res = self.client.search(index=self.index_name, body=query)
        lm_docs = []
        for r in res["hits"]["hits"]:
            lm_docs.append(
                LmDocument(
                    id_=r["_id"],
                    text=r["_source"]["file_text"],
                    metadata=r["_source"]["file_metadata"],
                )
            )
        return lm_docs
        
    # 如何搜索的示例代码：https://github.com/elastic/elasticsearch-labs
    def search_docs_by_text(self, user_query_text: str="AAMIS_项目总体计划", query_on_fileds:list = ["file_name","file_text"]) -> List[LmDocument]:
        """Query Elasticsearch store using query format of ES client

        Args:
            user_query_text (str): 用户要搜索的文本
            query_on_fileds (list) : 在哪些字段上搜索，共有"file_name","file_text"两个字段是可搜索的“Text”类型

        Returns:
            List[Document]: List of result documents
        """
        query = {
            "query": {"multi_match": {"query": user_query_text ,"fields":query_on_fileds}},
            "size":MAX_DOCS_TO_GET,# 注意设置size，默认返回10个。
        }
        lm_docs = self.query_raw(query)
        return lm_docs

    def search_docs_by_bm25(
        self, user_query_text: str, top_k: int = 10, doc_ids: Optional[list]= None, query_on_fileds:list = ["file_name","file_text"]
    ) -> List[LmDocument]:
        """Search Elasticsearch docstore using search query (BM25)

        Args:
            user_query_text (str): user query text
            top_k (int, optional): number of top documents to return. Defaults to 10.
            doc_ids (list, optional): only search on these ids
            query_on_fileds (list) : 在哪些字段上搜索，共有"file_name","file_text"两个字段是可搜索的“Text”类型

        Returns:
            List[Document]: List of result documents
        """
        # query_dict: dict = {"match": {"content": user_query_text}}
        query_dict = {"multi_match": {"query": user_query_text ,"fields":query_on_fileds}}
        if doc_ids is not None:
            query_dict = {"bool": {"must": [query_dict, {"terms": {"_id": doc_ids}}]}}
        
        query_dict = {"query": query_dict, "size": top_k}

        lm_docs = self.query_raw(query_dict)
        return lm_docs

    def get(self, ids: Union[List[str], str]) -> List[LmDocument]:
        """Get document by id"""
        if not isinstance(ids, list):
            ids = [ids]
        query_dict = {"query": {"terms": {"_id": ids}}, "size": MAX_DOCS_TO_GET}
        return self.query_raw(query_dict)

    def count(self) -> int:
        """Count number of documents"""
        count = int(
            self.client.cat.count(index=self.index_name, format="json")[0]["count"]
        )
        return count
    
    def ids(self) -> set[str]:
        docs = self.get_all()
        ids = [doc.doc_id for doc in docs]
        return set(ids)

    def get_all(self) -> List[LmDocument]:
        """Get all documents"""
        query_dict = {"query": {"match_all": {}}, "size": MAX_DOCS_TO_GET}
        return self.query_raw(query_dict)

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

