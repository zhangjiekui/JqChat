import sys,os,logging
# project_root = '/media/yqli/JqChat'
# sys.path.insert(0, project_root)
import time 
import shutil
import asyncio
from langchain.schema import Document as LcDocument
from jqcode.jq_agent.c0_init_env_models import env_models_instance
from jqcode.jq_docstores.backend_docstore_utils.jq_es_metastores import JqElasticsearchUniMetaStore, md5_id_from_text
from jqcode.jq_docstores.backend_docstore_utils.jq_es_docstores import JqElasticsearchDocumentStore
from jqcode.jq_docstores.backend_docstore_utils.jq_es_indexstores import JqElasticsearchIndexStore
from jqcode.jq_readers.jqkj_readers import JqkjSimpleDirectoryReader, filetype_reader_dict
from jqcode.graph_rag_networkx import JqGraphRag    
from jqcode.jq_utils.logger import jqkj_logger

logger = jqkj_logger(__file__).get_logger()
required_exts_in_reader = list(filetype_reader_dict.keys())
doc_tree_spiltter = env_models_instance.doc_tree_spiltter
embed_model = env_models_instance.get_emb_8k_rerank_model()[0]

class JqEsClient():
    """
        JqEsClient封装对ES的操作,以维护metastores,docstores和doc_index之间的一致性
        
    """
    def __init__(self,) -> None:
        self.metastores = JqElasticsearchUniMetaStore()
        self.docstores = JqElasticsearchDocumentStore()
        self.client = env_models_instance.get_es_connection()
        self.default_index_settings = env_models_instance.ES_DEFAULT_CHINESE_SETTINGS
    
    def get_all_kb(self, current_user=None):
        """
        获取所有相关的知识库名字（索引），可根据当前用户限制，或者返回所有
        :param current_user: 当前用户的标识，默认为 None，表示不限制用户
        :return: 知识库名字的列表
        """
        private_system_indices = ["temp_memory_or_web_results","temp_index_for_upload_files","unimetastore","docstore"]
        try:
            # 如果没有指定用户，则查询所有索引
            if current_user:
                index_pattern = f"{current_user}_*"
                logger.info(f"Fetching indices with prefix: {index_pattern}")
            else:
                index_pattern = "*"
                logger.info("Fetching all indices")

            # 使用Elasticsearch的cat.indices API来获取索引
            response = self.client.cat.indices(index=index_pattern, h='index', format='json')

            # 将响应转换为索引名列表，并排除系统索引（以 '.' 开头的）
            kb_names = [index_info['index'] for index_info in response if not index_info['index'].startswith('.')]
            kb_names = [kb_name for kb_name in kb_names if kb_name not in private_system_indices]
            logger.info(f"Found {len(kb_names)} knowledge bases")
            return kb_names

        except Exception as e:
            logger.error(f"Error fetching knowledge base names: {e}")
            return []
   

    def get_index_info(self, index_name=''):
        try:
            # 首先，检查索引是否存在
            if not self.client.indices.exists(index=index_name):
                logger.warning(f"Index {index_name} does not exist.")
                return None

            # 使用 index_name 生成 index_id
            index_id = md5_id_from_text(index_name)

            # 从 metastores 获取索引元数据
            docs = self.metastores.get_docs_by_ids(index_id)
            
            if not docs:
                logger.warning(f"Failed to retrieve metadata for index {index_name}")
                return None

            # 从元数据中获取 description
            metadata = docs[0]['_source']
            description = metadata.get('description')
            logger.info(f"index_name:{index_name}; index_description: {description}")
            
            return description
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            return None

        
    def create_doc_index(self,index_name:str="",description:str="",index_creator:str = ""):
        """
            创建一个doc_index(存储doc chunks的文本内容及向量,就是通常意义上的知识库)
            (1) 验证创建的或已存在的doc_index,在metastores是否存在
            (2) 如果不存在,就新增一条doc_index的记录
            (3) 创建doc_index,分存在与不存在 
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
            (1) 如果是一个空的doc_index,实际上还没有chunks/embeddings记录,则删除该doc_index
            (2) 如果不是空的doc_index
                (2.1)获取全部的doc_ids
                 (2.2) 删除doc_index
                 (2.3) 找到docstores中对应的doc_ids记录的file_used_in_indexes,删除该doc_index
            (3) 睡眠1秒(ES的刷新间隔默认为1秒),检查doc_index是否存在
            (4) 不存在:
                (4.1) 在docstores中, 从该doc_ids对应的file_used_in_indexes中,删除该doc_indexstatus
                (4.2) 在metastores中,将该doc_index对应的status标识为false
                
        #    todo:什么时候,将docstores中的记录标识设为false呢?
            
            
        """
        if index_name in [self.docstores.index_name,self.metastores.index_name]:
            logger.warning(f"{index_name}是系统必须的，无法自动删除，如确有必要，请手动删除！")
            return False
        
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
                    logger.warning(f"意外：{index_name=}依然存在!请在Kibana中查看核实,手动删除。") 
                    
                
            else:
                logger.warning(f"{index_name=}本不存在，无需删除")

            return True
        

    def delete_file_from_es_kb(self, kb_name: str, filename: str) -> bool:
        """
        删除知识库中的文件及其所有块。

        :param kb_name: 知识库的名称
        :param filename: 要删除的文件名
        :return: 如果所有块删除成功返回True,否则返回False
        """
        try:
            # 根据文件名查找所有匹配的文档ID（假设文件名存储在"metadata.file_name"字段中）
            search_result = self.client.search(index=kb_name, body={
                "query": {
                    "match": {
                        "metadata.file_name.keyword": filename
                    }
                },
                "size":10000,# 注意设置size，默认返回10个。
            })

            # 如果找到文档，删除所有匹配的文档
            if search_result['hits']['total']['value'] > 0:
                for hit in search_result['hits']['hits']:
                    document_id = hit['_id']
                    delete_result = self.client.delete(index=kb_name, id=document_id)
                    if delete_result['result'] == 'deleted':
                        logging.info(f"Document block '{filename}' with ID '{document_id}' deleted successfully from index '{kb_name}'.")
                    else:
                        logging.warning(f"Document block '{filename}' with ID '{document_id}' found but could not be deleted.")
                        return False
                logging.info(f"All document blocks for '{filename}' deleted successfully from index '{kb_name}'.")
                return True
            else:
                logging.warning(f"File '{filename}' not found in index '{kb_name}'.")
                return False
        except Exception as e:
            logging.error(f"Error deleting document blocks: {e}")
            return False
        

    def chunks_indexing_from_input_dir_or_files(self,
            # 当前用户，将在create_doc_index和add_or_update_index_metadata_if_id_exists方法中使用
            current_user:str,
            #create_doc_index方法相关参数：创建知识库，并在metastores中增加所建知识库的相关元数据描述信息
            index_name:str="",
            description:str=None,
            #JqkjSimpleDirectoryReader实例化相关参数，读取文件 
            input_dir:str=None,
            input_files:list=None, 
            overwrite_existing_converted_files=False,
            required_exts=required_exts_in_reader,
            if_uploade_src_file = False,
            exclude_hidden=False
        ):
        """
            将文档chunks文本和向量存储到doc_index
            (1) 调用执行create_doc_index方法
            (2) 将文档所属的原始文件及doc_tree存储到docstores中,并在对应记录的file_used_in_indexes中增加该doc_index，并获取文件记录ID
            (3) 将文件记录ID更新到chunks元数据中
            (4) 将文档chunks文本和向量存储到doc_index
        """
    # 1、可选。创建知识库，并在metastore中写入该知识库的元数据（如名称、描述、创建者)
        if index_name not in self.metastores.index_names or not self.client.indices.exists(index=index_name):
            logger.info(f"创建知识库{index_name},并在metastore中写入该知识库的元数据(如名称、描述、创建者)")       
            index_store = self.create_doc_index(index_name=index_name,description=description,index_creator=current_user)
            logger.info(f"应已创建知识库{index_name}，并在{self.metastores.index_name}中有该知识库({index_name})的描述等元信息")
        else:
            logger.info(f"知识库{index_name}已存在,并在metastore中存在{self.metastores.index_names}") 
            index_store = JqElasticsearchIndexStore(index_name=index_name)
    # 2、读取文件
        simple_reader = JqkjSimpleDirectoryReader(input_dir=input_dir,input_files=input_files, 
                                                  overwrite_existing_converted_files=overwrite_existing_converted_files,
                                                  required_exts=required_exts,
                                                  exclude_hidden=exclude_hidden)
        lm_documents = asyncio.run(simple_reader.aload_data())
        logger.warning(f"读取到的文件数量:{len(lm_documents)=}")
    # 3.1、上传到文件库(docstore)，并在lm_documents元数据中加入存储库(docstore)及文件对应ID等信息
        status,lm_documents_with_added_index_info_metadata,es_index_doc_id_list = self.docstores.add_or_update_index_metadata_if_id_exists(lm_documents=lm_documents,file_upload_user=current_user,if_uploade_src_file=if_uploade_src_file)
        if if_uploade_src_file:
            logger.warning(f"上传到ES的文件数量：{len(lm_documents_with_added_index_info_metadata)=}")
            logger.info(f"上传的文件查看：{self.docstores.index_name}中存在{es_index_doc_id_list}等{len(es_index_doc_id_list)}文件记录！")
            logger.info(f"lm_documents_with_added_index_info_metadata中应以包含:存储库(docstore)及文件存储ID({es_index_doc_id_list})的信息,请核实！")
        else:
            logger.warning(f"选择不上传文件到ES：{if_uploade_src_file=}")
    # 3.2、如果是上传到/temp目录下的文件，复制到知识库目录下，并更新元数据
        tmp_dir = env_models_instance.abs_workspace + f"/temp"
        for doc in lm_documents:
            metadata = doc.metadata            
            src_filepath = metadata.get('source', metadata.get('original_source_jq',None))
            file_name = os.path.basename(src_filepath)
            kb_dir = env_models_instance.abs_workspace + f"/knowledge_base/{index_name}/content"
            if not os.path.exists(kb_dir):
                os.makedirs(kb_dir,exist_ok=True)
                
            kb_filepath = f"{kb_dir}/{file_name}"
            if not os.path.isfile(kb_filepath):
                shutil.copy2(src_filepath, kb_filepath)
                logger.warning(f"  ==已将文件拷贝到知识库：{src_filepath}=>{kb_filepath}")
                
            # if src_filepath.startswith(tmp_dir):
            #     doc.metadata.update({"source_kb":kb_filepath})
            doc.metadata.update({"source_kb":kb_filepath})
            
    # 4、切分文件
        lm_splitted_documents = doc_tree_spiltter.get_nodes_from_documents(lm_documents) #llamaindex格式
        lc_splitted_documents = [LcDocument(page_content=doc.text,metadata=doc.metadata) for doc in lm_splitted_documents] #转换为langchain格式
        logger.warning(f"从{len(lm_documents)}个文件中，生成的切片数为:{len(lc_splitted_documents)}")
    # 5、将文件切片写入知识库
        if len(lm_documents)>0:    
            vectorstore = env_models_instance.get_es_searchstore_index_documents(documents=lc_splitted_documents, embedding=embed_model,index_name=index_name,source_id_key='source',clear_before_add_index=False)        
            logger.warning(f"已将{len(lc_splitted_documents)=}个文件切片写入ES知识库，并返回vectorstore对象")
            # graph_rag = JqGraphRag(documents=lc_splitted_documents,index_name=index_name)
            # gml_path = graph_rag.graph_indexing()
            # logger.warning(f"已写入图索引：{gml_path}")
        else:
            logger.warning(f"{len(lm_documents)=}，无需写入ES知识库，直接返回vectorstore对象")
            vectorstore = env_models_instance.get_es_searchstore(es_connection=self.client,embedding=embed_model,index_name=index_name)
        # es_index_doc_ids,es_index_doc_filepaths = index_store.get_all_unique_fileids_filepaths()
        # if es_index_doc_ids:
        #     for i in range(len(es_index_doc_ids)):
        #         logger.debug(f"序号：{i+1},Id:{es_index_doc_ids[i]},Path:{es_index_doc_filepaths[i]}")
        #     logger.debug(f"知识库{index_store.index_name}中的记录数为:{index_store.count}")
        return vectorstore
    
    
if __name__ == "__main__":
    
    # index_name='tempuse'
    # current_user='elastic'

    jq_es_client = JqEsClient()
    # status = jq_es_client.delete_file_from_es_kb('liyuanqin', 'OCR接口性能报告.docx')
    # status = jq_es_client.delete_file_from_es_kb('liyuanqin', '测试文本.txt')
    # # status = jq_es_client.create_doc_index(index_name='tempuse',
    # #                                        description="创建一个测试知识库知识库,该知识库主要用测试获取基本信息功能")
    
    # kbs = jq_es_client.get_all_kb()

    # index_info = jq_es_client.get_index_info(index_name='tempuse')


    # pass
    
    # index_store = JqElasticsearchIndexStore(index_name=index_name)
    # print(f"知识库{index_store.index_name}中的记录数为:{index_store.count}")

    # status = jq_es_client.drop_doc_index(index_name=index_name)
    
    # input_dir = "/media/program/UPLOAD_DOCS/knowledge_base/liyuanqin/content"
    # input_dir = fr'/data/projects/JqChatV2/JqChat/jqcode/jq_readers/.test_files/.testinputdocs'
    # input_files =["/data/projects/JqChatV2/JqChat/jqcode/jq_readers/.test_files/.testinputdocs/AAMIS_项目总体计划_120925.doc"]
    # input_files = "/media/program/UPLOAD_DOCS/knowledge_base/liyuanqin/content/Agent调试跟踪1.txt"
    input_files = ['/media/program/workspace/knowledge_base/create2/content/“主动健康和老龄化科技应对”重点专项2.docx']
    # vectorstore = jq_es_client.chunks_indexing_from_input_dir_or_files(current_user='',index_name='graphrag_test',
    #                                                                 description="graphrag_test: 转换/data/projects/JqChatV2/JqChat/jqcode/jq_readers/.test_files/.testinputdocs目录下的文件，测试速度",
    #                                                                 input_dir = input_dir,
    #                                                                 input_files=None)
    vectorstore = jq_es_client.chunks_indexing_from_input_dir_or_files(current_user='',index_name='create2',
                                                                description="JqConverter跳过文件转换: /data/projects/JqChatV2/JqChat/jqcode/jq_readers/.test_files/.testinputdocs/A方案.txt",
                                                                input_dir = None,
                                                                input_files=input_files)
    pass
    
