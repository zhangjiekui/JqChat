# to be added
import time
from jqcode.jq_agent.c0_init_env_models import env_models_instance
from jqcode.jq_docstores.backend_docstore_utils.jq_es_metastores import JqElasticsearchUniMetaStore
from jqcode.jq_docstores.backend_docstore_utils.jq_es_docstores import JqElasticsearchDocumentStore
from jqcode.jq_docstores.backend_docstore_utils.jq_es_indexstores import JqElasticsearchIndexStore
from jqcode.jq_utils.logger import jqkj_logger
logger = jqkj_logger(__file__).get_logger()

class JqEsClient():
    """
        JqEsClient封装对ES的操作，以维护metastores,docstores和doc_index之间的一致性
        
    """
    def __init__(self,) -> None:
        self.metastores = JqElasticsearchUniMetaStore()
        self.docstores = JqElasticsearchDocumentStore()
        self.client = env_models_instance.get_es_connection()
        self.default_index_settings = env_models_instance.ES_DEFAULT_CHINESE_SETTINGS
        
    def create_doc_index(self,index_name:str="",description:str="",index_creator:str = "",):
        """
            创建一个doc_index（存储doc chunks的文本内容及向量，就是通常意义上的知识库）
            (1) 验证创建的或已存在的doc_index，在metastores是否存在
            (2) 如果不存在，就新增一条doc_index的记录
            (3) 创建doc_index，分存在与不存在 
        """
        index_store = None
        status,index_id = self.metastores.add_or_update_index_metadata_if_id_exists(index_name=index_name,description=description,index_creator=index_creator,allow_create_new=True)
        if status:
            if not self.client.indices.exists(index=index_name): 
                # self.client.indices.create(index=index_name, settings=self.default_index_settings)
                logger.info(f"{index_name=}不存在，将创建......")
                index_store = JqElasticsearchIndexStore(index_name=index_name,create_if_not_exists=True)
            else:
                index_store = JqElasticsearchIndexStore(index_name=index_name,create_if_not_exists=False)
                logger.info(f"{index_name=}已存在，将跳过......")
        
        if not self.client.indices.exists(index=index_name):
                logger.warning(f"创建{index_name=}失败")
                index_store = None
                
        return index_store
  
    def drop_doc_index(self,index_name):
        """
            删除一个doc_index(即通常意义上的删除一个知识库)
            (1) 如果是一个空的doc_index，实际上还没有chunks/embeddings记录，则删除该doc_index
            (2) 如果不是空的doc_index
                （2.1）获取全部的doc_ids
                 (2.2) 删除doc_index
                 (2.3) 找到docstores中对应的doc_ids记录的file_used_in_indexes，删除该doc_index
            (3) 睡眠1秒(ES的刷新间隔默认为1秒)，检查doc_index是否存在
            (4) 不存在:
                (4.1) 在docstores中, 从该doc_ids对应的file_used_in_indexes中，删除该doc_indexstatus
                (4.2) 在metastores中,将该doc_index对应的status标识为false
                
        #    todo:什么时候，将docstores中的记录标识设为false呢？
            
            
        """
        if index_name in [self.docstores.index_name,self.metastores.index_name]:
            logger.warning(f"{index_name}是系统必须的，无法自动删除，如确有必要，请手动删除！")
        else:
            if self.client.indices.exists(index=index_name):
                index_store = JqElasticsearchIndexStore(index_name=index_name,create_if_not_exists=False)
                es_index_doc_ids,es_index_doc_filepaths = index_store.get_all_unique_fileids_filepaths()
                print(f"{len(es_index_doc_ids)}")
                print(f"{len(es_index_doc_filepaths)}")
                
                index_store.drop()
                time.sleep(1)
                
                if not self.client.indices.exists(index=index_name):
                    logger.info(f"{index_name}已删除！")
                    if es_index_doc_ids:
                        self.docstores.update_doc_fields_values(doc_ids=es_index_doc_ids,update_field_value_pair_dict=[{"file_used_in_indexes":f"---{index_name}"}]*len(es_index_doc_ids))
                        logger.info(f"{self.docstores.index_name}中的file_used_in_indexes也删除了{index_name},共涉及{len(es_index_doc_ids)=}个文档文件")
                    self.metastores.update_doc_fields_values(index_name=index_name,update_field_value_pair_dict = {"status":False})
                    
                else:
                    logger.warning(f"意外：{index_name=}依然存在！请在Kibana中查看核实，手动删除。") 
                
            else:
                logger.warning(f"{index_name=}本不存在，无需删除")
    
    def chunks_indexing():
        """
            将文档chunks文本和向量存储到doc_index
            (1) 调用执行create_doc_index方法
            (2) 将文档所属的原始文件及doc_tree存储到docstores中,并在对应记录的file_used_in_indexes中增加该doc_index，并获取文件记录ID
            (3) 将文件记录ID更新到chunks元数据中
            (4) 将文档chunks文本和向量存储到doc_index
        """
        pass
    
if __name__ == "__main__":
    jq_es_client = JqEsClient()
    # "health" "2024-09-05 04:27:12"
    status = jq_es_client.create_doc_index(index_name="health",description="Test:创建一个doc_index（存储doc chunks的文本内容及向量，就是通常意义上的知识库）")
    # "health_new" "2024-09-05 04:28:02"
    status = jq_es_client.create_doc_index(index_name="health_new",description="Test:创建一个doc_index（存储doc chunks的文本内容及向量，就是通常意义上的知识库）")
    status = jq_es_client.drop_doc_index(index_name="health_new")
    print(status)
    