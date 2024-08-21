from typing import List
from pathlib import Path
from llama_index.core import ServiceContext
from langchain import schema
from elasticsearch import Elasticsearch
from langchain.retrievers import EnsembleRetriever,ContextualCompressionRetriever
from langchain_community.retrievers import ElasticSearchBM25Retriever
from llama_index.core.readers.file.base import default_file_metadata_func
from jqcode.jq_readers.jqkj_readers import JqkjSimpleDirectoryReader,JqkjDocxReader
from jqcode.jq_readers.backend_reader_utils.jqkj_doc_tree_utils import jieba_pre_process
from jqcode.jq_agent.c0_init_env_models import env_models_instance
from jqcode.jq_utils.logger import jqkj_logger
logger = jqkj_logger(__file__).get_logger()

class JqElasticSearchBM25Retriever(ElasticSearchBM25Retriever):
    @classmethod
    def create(
        cls, elasticsearch_connection: Elasticsearch, index_name: str, k1: float = 2.0, b: float = 0.75
    ) -> ElasticSearchBM25Retriever:
        es = elasticsearch_connection
                # Define the index settings and mappings
        settings = {
            "analysis": {"analyzer": {"default": {"type": "standard"}}},
            "similarity": {
                "custom_bm25": {
                    "type": "BM25",
                    "k1": k1,
                    "b": b,
                }
            },
        }
        mappings = {
            "properties": {
                "content": {
                    "type": "text",
                    "similarity": "custom_bm25",  # Use the custom BM25 similarity
                }
            }
        }

        # Create the index with the specified settings and mappings
        es.indices.index(index=index_name, mappings=mappings, settings=settings)
        return cls(client=es, index_name=index_name)


def get_retriever(index_name:str=None,chat_on_docs_list:List[str]=None,add_docs_list_to_kb=True,default_temp_index_name:str="temp_index_for_upload_files",
                  top_n:int=6,source_id_key='source',required_exts=['.doc','.docx','.pdf','.md']):
    llm = env_models_instance.chat_model
    embed_model = env_models_instance.embed_model
    reranker = env_models_instance.reranker
    es_connection = env_models_instance.get_es_connection()
    
    vectorstore = None
    if index_name:
        vectorstore = env_models_instance.get_es_searchstore(es_connection=es_connection,embedding=embed_model,index_name=index_name)
    lc_documents = None
    doc_paths_exists = []
    compression_retriever = None
    index_destination = index_name or default_temp_index_name
    if chat_on_docs_list:
        chat_on_docs_list = [Path(item) for item in chat_on_docs_list]
        doc_paths_exists = [item for item in chat_on_docs_list if Path.exists(item)]
        doc_paths_not_exists = [item for item in chat_on_docs_list if not Path.exists(item)]
        if len(doc_paths_exists)==0:
            logger.warning(f"'{chat_on_docs_list=}'中不存在的任何有效文件路径，请检查确认！")
        else:
            if doc_paths_not_exists:
                logger.warning(f"以下文件路径并不存在，请检查确认！'{doc_paths_not_exists=}'")
            
            filter_by_files = [str(file) for file in doc_paths_exists]
            # !!!下面的代码不要删除，以后要用!!!
            #region 测试插入整个文档，为父子文档做技术准备,顺便测试JqkjDocxReader
            # from jqcode.jq_readers.jqkj_readers import JqkjDocxReader
            # for file in filter_by_files:
            #     jq_file_reader = JqkjDocxReader(file_path=file)
            #     doc = jq_file_reader.load()[0]
            #     _metadata = doc.metadata
            #     del _metadata['file_doc_object_jq']
            #     del _metadata['file_doc_tree_jq']
            #     del _metadata['df_table_list_jq']
            #     doc_index_dict = {"text":doc.text,"id":"my_id",
            #                       "metadata":_metadata
            #                     }
            #     result = es_connection.index(index=index_destination,body=doc_index_dict)
            #endregion 测试插入整个文档，为父子文档做技术准备,顺便测试JqkjDocxReader
            # !!!上面的代码不要删除，以后要用!!!

            files_to_be_add_to_index = []            
            # 在给定的index_name中（如果没给定，就放到'temp_index_for_upload_files'知识库中）查询
            # 是否全部或部分文件已经存在索引了，如果已经存在，就不要做文件的读取、切分等操作，节省时间
            # 得到真正的files_to_be_add_to_index
            if es_connection.indices.exists(index=index_destination): 
            # region 保留用做测试   
                # query0= {
                #             "query": {"terms":{"metadata.source.keyword":[filter_by_files[0]]}},
                #             "size":10000,# 注意设置size，默认返回10个。
                #         }
                # all_results_in_the_index = es_connection.search(index=default_temp_index_name, body=query0)
                # all_hits0 = all_results_in_the_index['hits']['hits']
                # print(len(all_hits0))

                # query1= {
                #             "query": {"terms":{"metadata.source.keyword":[filter_by_files[1]]}},
                #             "size":10000,# 注意设置size，默认返回10个。
                #         }
                # all_results_in_the_index = es_connection.search(index=default_temp_index_name, body=query1)
                # all_hits1 = all_results_in_the_index['hits']['hits']
                # print(len(all_hits1))
            # endregion 保留用做测试
                query = {
                            "query": {"terms":{"metadata.source.keyword":filter_by_files}},
                            "size":10000,# 注意设置size，默认返回10个。
                        }
                all_results_in_the_index = es_connection.search(index=default_temp_index_name, body=query)
                all_hits = all_results_in_the_index['hits']['hits']
                print(len(all_hits))

                file_stem_set_without_extention = set()
                has_processed_file_path = set()
                for hit in all_hits:
                    _source = hit["_source"]
                    if 'vector' in _source.keys():
                        metadata = _source["metadata"]
                        file_key = ''
                        if "source" in metadata.keys():
                            file_key = "source"
                        elif "original_source_jq" in metadata.keys():
                            file_key = "original_source_jq"
                        else:
                            raise Exception('Langchain Document的metadata不存在key:"source"或"original_source_jq"')
                        file_path = metadata[file_key]
                        if file_path not in has_processed_file_path:
                            has_processed_file_path.add(file_path)

                            # 调用/root/.virtualenvs/test/lib/python3.10/site-packages/llama_index/legacy/readers/file/base.py
                            # default_file_metadata_func方法，来获取文件default_file_metadata
                            default_file_metadata = default_file_metadata_func(file_path)
                            file_size_current = default_file_metadata['file_size']
                            last_modified_current = default_file_metadata['last_modified_date']
                            file_size_in_es_index = metadata['file_size']
                            last_modified_date_in_es_index = metadata['last_modified_date']
                            if file_size_current==file_size_in_es_index and last_modified_current == last_modified_date_in_es_index:
                                file_stem = Path(file_path).stem
                                file_stem_set_without_extention.add(file_stem)
                            else:
                                if Path(file_path).suffix!='.docx':
                                    if "original_source_converted_jq" in metadata.keys():
                                        converted_file_key = "original_source_converted_jq"
                                    elif "file_path" in metadata.keys():
                                        converted_file_key = "file_path"
                                    else:
                                        raise Exception('Langchain Document的metadata不存在key:"file_path"或"original_source_converted_jq"')                                

                                    # 调用/root/.virtualenvs/test/lib/python3.10/site-packages/llama_index/legacy/readers/file/base.py
                                    # default_file_metadata_func方法，来获取文件default_file_metadata
                                    converted_file_path = metadata[converted_file_key]
                                    if converted_file_path!=file_path:
                                        default_converted_file_metadata = default_file_metadata_func(converted_file_path)
                                        file_size_converted = default_converted_file_metadata['file_size']
                                        last_modified_converted = default_converted_file_metadata['last_modified_date']
                                        if file_size_converted==file_size_in_es_index and last_modified_converted == last_modified_date_in_es_index:
                                            file_stem = Path(file_path).stem
                                            file_stem_set_without_extention.add(file_stem)                                

                filter_by_file_stem_without_extention = [Path(file_path).stem for file_path in filter_by_files]
                for i, file in enumerate(filter_by_file_stem_without_extention):                        
                    if file not in file_stem_set_without_extention:
                        files_to_be_add_to_index.append(filter_by_files[i])

                filter_by_files = files_to_be_add_to_index
            
            if filter_by_files:
                doc_tree_spiltter = env_models_instance.doc_tree_spiltter
                simple_reader = JqkjSimpleDirectoryReader(input_files=filter_by_files,overwrite_existing_converted_files=False,required_exts=required_exts)
                documents = simple_reader.load_data()
                service_context = ServiceContext.from_defaults(llm=llm, embed_model=embed_model,node_parser=doc_tree_spiltter)
                nodes = service_context.node_parser.get_nodes_from_documents(documents)
                lc_documents = [schema.Document(page_content=node.text,metadata=node.metadata) for node in nodes]

  
    if add_docs_list_to_kb:
        if lc_documents and index_name:
            vectorstore = env_models_instance.get_es_searchstore_index_documents(documents=lc_documents, embedding=embed_model,index_name=index_name,
                                                                                 es_connection=es_connection,clear_before_add_index=True,source_id_key=source_id_key)
        elif not lc_documents:
            if doc_paths_exists:
                vectorstore = env_models_instance.get_es_searchstore(es_connection=es_connection,embedding=embed_model,index_name=index_name)
            else:
                logger.warning(f"您的选择是将文件加入知识库('{add_docs_list_to_kb=}')，但实际上并未获取到可入库的文件('{lc_documents=}')，请检查确认！")

        elif not index_name:    
            logger.warning(f"您还没有选择知识库'{index_name=}'，将使用默认的临时知识库{default_temp_index_name}来处理。")
            vectorstore = env_models_instance.get_es_searchstore_index_documents(documents=lc_documents, embedding=embed_model,index_name=default_temp_index_name,
                                                                        es_connection=es_connection,clear_before_add_index=False,source_id_key=source_id_key)

        else:
            raise Exception("还有未考虑到的情形吗？")
    else:         
        if lc_documents:
            logger.warning(f"您没有要将文件加入到'{index_name=}'，将使用默认的临时知识库{default_temp_index_name}来处理。")            
            vectorstore = env_models_instance.get_es_searchstore_index_documents(documents=lc_documents, embedding=embed_model,index_name=default_temp_index_name,
                                                                            es_connection=es_connection,clear_before_add_index=False,source_id_key=source_id_key)
        elif doc_paths_exists:
             vectorstore = env_models_instance.get_es_searchstore(es_connection=es_connection,embedding=embed_model,index_name=index_name)

    
    
    
    if vectorstore:
        if doc_paths_exists:
            filter_by_files = [str(file) for file in doc_paths_exists]
            filters = {"terms":{f"metadata.{source_id_key}": filter_by_files}} 
            retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k":top_n,"filter":filters})
            # bm25_retriever = JqElasticSearchBM25Retriever.create(es_connection, index_name=index_name)
            # bm25_retriever = LC_BM25Retriever.from_documents(lc_documents,preprocess_func=jieba_pre_process,search_kwargs={"k":top_n,"filter":filters})  
        else:
            retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k":top_n})
            # bm25_retriever = LC_BM25Retriever.from_documents(lc_documents,preprocess_func=jieba_pre_process, search_kwargs={"k":top_n})  
            # bm25_retriever = JqElasticSearchBM25Retriever.create(es_connection, index_name=index_name)
  

        # 初始化集成检索器  
        ensemble_retriever = EnsembleRetriever(retrievers=[retriever], weights=[0.3, 0.7])
        compression_retriever = ContextualCompressionRetriever(base_compressor=reranker, base_retriever=ensemble_retriever)

    filters = {"terms":{f"metadata.{source_id_key}.keyword": [filter_by_files[0]]}}
    retriever = vectorstore.as_retriever(search_type="similarity_score_threshold", search_kwargs={'k':20,'score_threshold': 0.8,'filter':filters})
    result08 =retriever.invoke("晶奇公司的应急技术服务电话？")

    retriever = vectorstore.as_retriever(search_type="similarity_score_threshold", search_kwargs={'k':20,'score_threshold': 0.73,'filter':filters})
    result06 =retriever.invoke("晶奇公司的应急技术服务电话？")

    filters = {"terms":{f"metadata.{source_id_key}.keyword": [filter_by_files[1]]}}
    retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={'k':20,'score_threshold': 0.8,'filter':filters})
    result1 =retriever.invoke("晶奇公司的应急技术服务电话？")

    filters = {"terms":{f"metadata.{source_id_key}.keyword": filter_by_files}}
    retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={'k':20,'score_threshold': 0.8,'filter':filters})
    result =retriever.invoke("晶奇公司的应急技术服务电话？")
###################
    filters = {"terms":{f"metadata.{source_id_key}.keyword": [filter_by_files[0]]}}
    retriever = vectorstore.as_retriever(search_kwargs={'filter':filters})
    result08 =retriever.invoke("晶奇公司的应急技术服务电话？")

    retriever = vectorstore.as_retriever(search_type="similarity_score_threshold", search_kwargs={'k':20,'score_threshold': 0.73,'filter':filters})
    result06 =retriever.invoke("晶奇公司的应急技术服务电话？")

    filters = {"terms":{f"metadata.{source_id_key}.keyword": [filter_by_files[1]]}}
    retriever = vectorstore.as_retriever(search_kwargs={'filter':filters})
    result1 =retriever.invoke("晶奇公司的应急技术服务电话？")

    filters = {"terms":{f"metadata.{source_id_key}.keyword": filter_by_files}}
    retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={'k':7,'filter':filters})
    result =retriever.invoke("晶奇公司的应急技术服务电话？")





    # result2 = vectorstore.similarity_search("晶奇公司的应急技术服务电话？")
    # result3 = vectorstore.max_marginal_relevance_search("晶奇公司的应急技术服务电话？")
    compression_retriever = ContextualCompressionRetriever(base_compressor=reranker, base_retriever=retriever)
    if not compression_retriever:
        logger.warning(f"未能获取到有效的Retriever：'{compression_retriever=}")
    return compression_retriever

if __name__ == "__main__":
    input_files = [fr'/data/projects/JqChatV2/JqChat/jqcode/jq_readers/.test_files/.testinputdocs/A方案.docx'] 
    input_files += [fr'/data/projects/JqChatV2/JqChat/jqcode/jq_readers/.test_files/.testinputdocs/PPQA000_质量保证过程.doc']   
    index_name='temp_index_for_upload_files'
    compression_retriever = get_retriever(index_name=index_name,chat_on_docs_list=input_files,add_docs_list_to_kb=True)     
    print(type(compression_retriever))        
