from typing import List
from pathlib import Path
from llama_index.core import ServiceContext
from langchain import schema
from langchain.retrievers import EnsembleRetriever,ContextualCompressionRetriever
from langchain_community.retrievers import BM25Retriever as LC_BM25Retriever
from jqcode.jq_readers.jqkj_readers import JqkjSimpleDirectoryReader,JqkjDocxReader
from jqcode.jq_readers.backend_reader_utils.jqkj_doc_tree_utils import jieba_pre_process
from jqcode.jq_agent.c0_init_env_models import env_models_instance
from jqcode.jq_utils.logger import jqkj_logger
logger = jqkj_logger(__file__).get_logger()

def get_retriever(index_name:str=None,chat_on_docs_list:List[str]=None,add_docs_list_to_kb=True,top_n:int=6,source_id_key='source',required_exts=['.doc','.docx','.pdf','.md']):
    llm = env_models_instance.chat_model
    embed_model = env_models_instance.embed_model
    reranker = env_models_instance.reranker
    es_connection = env_models_instance.get_es_connection()
    
    vectorstore = None
    lc_documents = None
    doc_paths_exists = []
    compression_retriever = None
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
            files_to_be_add_to_index = []
            
            # 在给定的index_name中（如果没给定，就放到'temp_index_for_upload_files'知识库中）查询
            # 是否全部或部分文件已经存在索引了，如果已经存在，就不要做文件的读取、切分等操作，节省时间
            # 得到真正的files_to_be_add_to_index
            index_destination = index_name or 'temp_index_for_upload_files' 
            if es_connection.indices.exists(index=index_destination): 
                query = {
                        "query": {
                            # "term": {"metadata.source.keyword": filter_by_files},
                            "term": {"metadata.source": filter_by_files}, #使用metadata中的source键
                            "term": {"_index": index_destination},
                        },
                        "size":10000,# 注意设置size，默认返回10个。

                    }
                all_results_in_the_index = es_connection.search(index=index_destination, body=query)
                all_hits = all_results_in_the_index['hits']['hits']
                all_metadatas = [hit["_source"]["metadata"]  for hit in all_hits]
                file_path_set_without_extention = set()
                for metadata in all_metadatas:
                    file_key = ''
                    if "source" in metadata.keys():
                        file_key = "source"
                    elif "original_source_jq" in metadata.keys():
                        file_key = "original_source_jq"
                    # elif "file_path_jq" in metadata.keys():
                    #     file_key = "file_path_jq"
                    else:
                        raise Exception('Langchain Document的metadata不存在key:"source"或"original_source_jq"')
                    file_path = metadata[file_key]
                    file_path_set_without_extention.add(file_path[0:-len(Path(file_path).suffix)]) 
                    filter_by_files_without_extention = [file_path[0:-len(Path(file_path).suffix)] for file_path in filter_by_files]

                for i, file in enumerate(filter_by_files_without_extention):                        
                    if file not in file_path_set_without_extention:
                        files_to_be_add_to_index.append(filter_by_files[i])

                filter_by_files = files_to_be_add_to_index

            doc_tree_spiltter = env_models_instance.doc_tree_spiltter
            simple_reader = JqkjSimpleDirectoryReader(input_files=filter_by_files,overwrite_existing_converted_files=False,required_exts=required_exts)
            documents = simple_reader.load_data()
            service_context = ServiceContext.from_defaults(llm=llm, embed_model=embed_model,node_parser=doc_tree_spiltter)
            nodes = service_context.node_parser.get_nodes_from_documents(documents)
            lc_documents = [schema.Document(page_content=node.text,metadata=node.metadata) for node in nodes]

            # #region 测试插入整个文档，为父子文档做技术准备,顺便测试JqkjDocxReader
            # from jqcode.jq_readers.jqkj_readers import JqkjDocxReader
            # for file in filter_by_files:
            #     jq_file_reader = JqkjDocxReader(file_path=file)
            #     doc = jq_file_reader.load()[0]
            #     doc_index_dict = {"text":doc.text,"id":"my_id",'original_source_jq':str(doc.metadata['original_source_jq']),'source':str(doc.metadata['source']),'original_source_converted_jq':str(doc.metadata['original_source_converted_jq'])}
            #     result = es_connection.index(index=index_destination,body=doc_index_dict)
            # #endregion 测试插入整个文档，为父子文档做技术准备

    
    if index_name:
        if add_docs_list_to_kb:
            if lc_documents:
                vectorstore = env_models_instance.get_es_searchstore_index_documents(documents=lc_documents, embedding=embed_model,index_name=index_name,source_id_key=source_id_key)
            else:
                logger.warning(f"您的选择是将文件加入知识库('{add_docs_list_to_kb=}')，但实际上并未获取到可入库的文件('{lc_documents=}')，请检查确认！")
                # 与下面的代码内容是一致的
                
                if not es_connection.indices.exists(index=index_name):
                    logger.warning(f"'{index_name}'不存在,请确认您的选择！")
                else:
                    vectorstore = env_models_instance.get_es_searchstore(es_connection=es_connection,embedding=embed_model,index_name=index_name)
        else:
            if lc_documents:
                vectorstore = env_models_instance.get_es_searchstore_index_documents(documents=lc_documents, embedding=embed_model,index_name="temp_index_for_upload_files",source_id_key=source_id_key)
            else:
                if not es_connection.indices.exists(index=index_name):
                    logger.warning(f"'{index_name}'不存在,请确认您的选择！")
                else:
                    vectorstore = env_models_instance.get_es_searchstore(es_connection=es_connection,index_name=index_name)
    if vectorstore:
        if doc_paths_exists:
            filter_by_files = [str(file) for file in doc_paths_exists]
            # filters = [{f"metadata.{source_id_key}": {'$in': filter_by_files}}]
            # filters = [{"terms":{f"metadata.{source_id_key}": {'$in': filter_by_files}}}] 
            filters = [{"terms":{f"metadata.{source_id_key}": filter_by_files}}] 
            retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k":top_n,"filter":filters})
            bm25_retriever = LC_BM25Retriever.from_documents(lc_documents,preprocess_func=jieba_pre_process,search_kwargs={"k":top_n,"filter":filters})  
        else:
            retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k":top_n})
            bm25_retriever = LC_BM25Retriever.from_documents(lc_documents,preprocess_func=jieba_pre_process, search_kwargs={"k":top_n})  
  

        # 初始化集成检索器  
        ensemble_retriever = EnsembleRetriever(retrievers=[bm25_retriever, retriever], weights=[0.3, 0.7])
        compressor = reranker   
        compression_retriever = ContextualCompressionRetriever(base_compressor=compressor, base_retriever=ensemble_retriever)

    
    if not compression_retriever:
        logger.warning(f"未能获取到有效的Retriever：'{compression_retriever=}")
    return compression_retriever               
