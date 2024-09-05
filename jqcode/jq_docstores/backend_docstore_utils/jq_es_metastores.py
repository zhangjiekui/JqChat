
import hashlib
from datetime import datetime
from typing import List, Optional, Union, Callable

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
from jqcode.jq_docstores.backend_docstore_utils.jq_base_docstores import JqBaseDocumentStore
from jqcode.jq_agent.c0_init_env_models import env_models_instance



from jqcode.jq_agent.c0_init_env_models import env_models_instance



from jqcode.jq_utils.logger import jqkj_logger
logger = jqkj_logger(__file__).get_logger()

MAX_DOCS_TO_GET = 10**4
min_length_of_index_name = 3
min_length_of_index_description = 20

def md5_id_from_text(text:str):
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

        # Create the index with the specified settings and mappings if not exists
        if not self.client.indices.exists(index=self.index_name):        
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
            self.client.indices.create(
                index=self.index_name, settings=settings, mappings=mappings
            )
            
        self.count = self._count()
        self.ids = self._ids()
        
    def add_or_update_index_metadata_if_id_exists(
        self,
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
            index_name:str="", 新增或更新的index名称
            description:str,index的描述
            index_creator:str, 创建index的用户 
            refresh_indices: request Elasticsearch to update its index (default to True)
        """
        if not isinstance(index_name,str) or len(index_name) < min_length_of_index_name:
            logger.warning(f"{index_name=}必须是有效的字符串,且长度必须至少为{min_length_of_index_name}！忽略此次操作。")
            return False,''               
        
        # index_name ==> index_id，然后检查是否存在且只有一个
        index_id = md5_id_from_text(index_name)        
        rs = self.get_docs_by_ids(index_id)
        if len(rs)>1:
            logger.warning(f"根据提供的{index_id=}得到的查询结果不唯一！忽略此次操作。")
            return False,''                
        else:
            if len(rs)==0:
                if not allow_create_new:
                    logger.warning(f"根据提供的{index_name=}没有查询到记录！但又不允许创建新纪录{allow_create_new=}，忽略此次操作。")
                    return False,''
                else:
                    logger.warning(f"根据提供的{index_name=}没有查询到记录！您允许创建新纪录{allow_create_new=}，将执行新增操作。")
            try:
                index_create_date = ''
                if len(rs)==1: #如果有记录，则需取出原来的值来填补用户没有提供的字段                    
                    r=rs[0]["_source"]
                    index_name = index_name if index_name else r['index_name']
                    description = description if description else r['description']
                    index_creator = index_creator if index_creator else r['index_creator']
                    status = status if status is not None else r['status'] #注意status可能是bool类型,所以不能直接用 if status判断，因status=False会出问题
                    index_create_date = r['index_create_date']
                    
                if not isinstance(description,str) or len(description) < min_length_of_index_description:
                    logger.warning(f"{description=}必须是有效的字符串,且长度必须至少为{min_length_of_index_description}！忽略此次操作。")
                    return False,''                
                
                if not index_create_date:
                    dt = datetime.now()
                    fmt = "%Y-%m-%d %H:%M:%S"
                    index_create_date = dt.strftime(fmt)

                request = {                
                    "index_name":index_name,
                    "description":description,
                    "index_creator": index_creator or "manager",
                    "index_create_date": index_create_date,
                    "status":status,
                    }           

                action = {"_op_type": "index","_index":self.index_name, "_id":index_id, "_source":request}
                    
                success, failed = self.es_bulk(self.client, [action])
                logger.info(f"Added/Updated {index_name}(id:{index_id}) to Metastore '{self.index_name}'")
                if refresh_indices:
                    self.client.indices.refresh(index=self.index_name)
                return True,index_id
            except Exception as e:
                logger.error(e)
                try:
                    error = e.errors[0]
                    logger.error(error["index"]["error"])
                except:
                    pass
                return False,index_id


    def update_doc_fields_values(self, index_name:str="",update_field_value_pair_dict:Union[dict,List[dict]]=None,refresh_indices:bool=True):
        """Update documents【由list doc_ids指定】 fields with new values 【由update_field_value_pair_dict指定】

            Args:

                index_name:要更新的index的name,
                    1）如果index_id已经提供，则忽略该值
                    2）试图以此index_name去检索匹配记录，如果匹配结果是唯一的，则执行更新，否则返回匹配到的多个ids
                update_field_value_pair_dict: Union[dict,List[dict]]，指定要更新的Filed_name和对应的New_value
                    形如: update_field_value_pair_dict = {"status":"false","description":"new description in string length>10", "index_creator":"new_name"}
                refresh_indices: bool. request Elasticsearch to update its index (default to True)

            Returns:status,bool. 代表更新成功或失败！
        """
        status,index_id = self.add_or_update_index_metadata_if_id_exists(index_name=index_name,allow_create_new=False,**update_field_value_pair_dict)
        return status,index_id
      
    
    def query_raw(self, query: dict) -> list:
        """Query Elasticsearch store using query format of ES client

        Args:
            query (dict): Elasticsearch query format

        Returns:
            list[result]: List of result documents
        """
        res = self.client.search(index=self.index_name, body=query)
        # rs = []
        # for r in res["hits"]["hits"]:
        #     rs.append(r) 
        rs = res["hits"]["hits"]          
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
    def search_docs_by_text(self, user_query_text: str=None,top_k: int = MAX_DOCS_TO_GET, query_on_fileds:list =["index_name","description"], filter_by_index_creators:list=None,filter_by_status:list=["true","false"]) -> list:
        """Query Elasticsearch store using query format of ES client

        Args:
            user_query_text (str): 用户要搜索的文本

        Returns:
            list[result]: List of results
        """
        query = self._get_query(user_query_text=user_query_text,size=top_k,query_on_fileds=query_on_fileds,filter_by_index_creators=filter_by_index_creators,filter_by_status=filter_by_status)      
        rs = self.query_raw(query)
        return rs

    def get_docs_by_ids(self, ids: Union[List[str], str]) -> list:
        """Get document by id"""
        if not isinstance(ids, list):
            ids = [ids]
        query_dict = {"query": {"terms": {"_id": ids}}, "size": MAX_DOCS_TO_GET}
        return self.query_raw(query_dict)
    
    def get_all_docs(self) -> list:
        """Get all documents"""
        query = {"query": {"match_all": {}}, "size": MAX_DOCS_TO_GET}
        return self.query_raw(query)
    
    def get_all_docs_by_users_and_status(self,users_list=["manager"],status_list=[True,"true"]) -> list: #[True,"true",False,"false"])
        """Get all documents"""
        rs = []
        query = {"query": {"match_all": {}}, "size": MAX_DOCS_TO_GET}
        all_rs = self.query_raw(query)
        for r in all_rs:
            source = r["_source"]
            if users_list:
                if source["index_creator"] not in users_list:
                    continue
            if status_list:
                status = source["status"]
                if isinstance(status,str):
                    status = status.lower()
                if status not in status_list:
                    continue
            rs.append(source)
        return rs

    def _count(self) -> int:
        """Count number of documents"""
        try:
            count = int(
                self.client.cat.count(index=self.index_name, format="json")[0]["count"]
            )
        except Exception as e:
            logger.warning(f"无法获取到记录数:{e}")
            count = 0
        return count
    
    def _ids(self) -> list:
        try:
            rs = self.get_all_docs()
            ids = [r["_id"] for r in rs]
            return list(set(ids))
        except Exception as e:
            logger.warning(f"无法获取到ids:{e}")            
            return []

    def delete(self, ids: Union[List[str], str]):
        """Delete a record/docs by id"""
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
    rs = metastore.get_all_docs_by_users_and_status()
    print(rs)
    rs = metastore.get_all_docs_by_users_and_status(status_list=[False,'false'])
    print(rs)
    rs = metastore.get_all_docs_by_users_and_status(users_list='manager',status_list=[])
    print(rs)
    rs = metastore.get_all_docs_by_users_and_status(users_list='new_name',status_list=[False,'false'])
    print(rs)
    rs = metastore.get_all_docs_by_users_and_status(users_list='new_name')
    print(rs)    
    
    status,id=metastore.add_or_update_index_metadata_if_id_exists(index_name="myindex",description="index的详细描述，不少于20个字")
    print(id)
    status,id=metastore.add_or_update_index_metadata_if_id_exists(index_name="notallow_myindex",description="index的详细描述，不少于20个字")
    print(id)
    status,id=metastore.add_or_update_index_metadata_if_id_exists(index_name="new_notallow_myindex",description="index的详细描述，不少于20个字",allow_create_new=False)
    print(id)
    status,id=metastore.add_or_update_index_metadata_if_id_exists(index_name="new_allowed_myindex",description="index的详细描述，不少于20个字",allow_create_new=True)
    print(id)
    status,id=metastore.add_or_update_index_metadata_if_id_exists(index_name="new_allowed_myindex",description="index的详细描述，不少于20个字.new description in string length>=20",allow_create_new=True)
    print(id)
    update_field_value_pair_dict = {"status":"false","description":"new description in string length>=20", "index_creator":"new_name"}
    status,id = metastore.update_doc_fields_values(index_name="notallow_myindex",update_field_value_pair_dict=update_field_value_pair_dict)
    print(id)
    print(f"{metastore.count=}")
    ids = metastore.ids
    print(f"{metastore.ids=}")
    metastore.delete("208d63861d535a96e47260281e53e816")
    print(f"{metastore.count=}")
    ids = metastore.ids
    print(f"{metastore.ids=}")

