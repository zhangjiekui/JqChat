from typing import List
from pathlib import Path
from llama_index.core import ServiceContext
from langchain import schema
from langchain.retrievers import EnsembleRetriever,ContextualCompressionRetriever
from langchain_community.retrievers import BM25Retriever as LC_BM25Retriever
from jqcode.jq_readers.jqkj_readers import JqkjSimpleDirectoryReader
from jqcode.jq_readers.backend_reader_utils.jqkj_doc_tree_utils import jieba_pre_process
from jqcode.jq_agent.c0_init_env_models import env_models_instance
from jqcode.jq_utils.logger import jqkj_logger
logger = jqkj_logger(__file__).get_logger()

def get_retriever(index_name:str=None,doc_id_or_path:List[str]=None,add_to_kb=True,top_n:int=6,source_id_key='source',required_exts=['.doc','.docx','.pdf','.md']):
    
    llm = env_models_instance.chat_model
    embed_model = env_models_instance.embed_model
    reranker = env_models_instance.reranker
    
    vectorstore = None
    lc_documents = None
    doc_id_or_path_exists = []
    compression_retriever = None
    if doc_id_or_path:
        doc_id_or_path = [Path(item) for item in doc_id_or_path]
        doc_id_or_path_exists = [item for item in doc_id_or_path if Path.exists(item)]
        doc_id_or_path_not_exists = [item for item in doc_id_or_path if not Path.exists(item)]
        if len(doc_id_or_path_exists)==0:
            logger.warning(f"'{doc_id_or_path=}'中不存在的任何有效文件路径，请检查确认！")
        else:
            if doc_id_or_path_not_exists:
                logger.warning(f"以下文件路径并不存在，请检查确认！'{doc_id_or_path_not_exists=}'")
            doc_tree_spiltter = env_models_instance.doc_tree_spiltter
            doc_id_or_path_exists = [str(file) for file in doc_id_or_path_exists]
            simple_reader = JqkjSimpleDirectoryReader(input_files=doc_id_or_path_exists,overwrite_existing_converted_files=False,required_exts=required_exts)
            documents = simple_reader.load_data()
            service_context = ServiceContext.from_defaults(llm=llm, embed_model=embed_model,node_parser=doc_tree_spiltter)
            nodes = service_context.node_parser.get_nodes_from_documents(documents)
            lc_documents = [schema.Document(page_content=node.text,metadata={**node.metadata,**{"source":node.metadata['original_source_jq']}}) for node in nodes]
    
    if index_name:
        if add_to_kb:
            if lc_documents:
                vectorstore = env_models_instance.get_es_searchstore_index_documents(documents=lc_documents, embedding=embed_model,index_name=index_name,source_id_key=source_id_key)
            else:
                logger.warning(f"您的选择是将文件加入知识库('{add_to_kb=}')，但实际上并未获取到可入库的文件('{lc_documents=}')，请检查确认！")
                # 与下面的代码内容是一致的
                es_connection = env_models_instance.get_es_connection()
                if not es_connection.indices.exists(index=index_name):
                    logger.warning(f"'{index_name}'不存在,请确认您的选择！")
                else:
                    vectorstore = env_models_instance.get_es_searchstore(es_connection=es_connection,embedding=embed_model,index_name=index_name)
        else:
            if lc_documents:
                vectorstore = env_models_instance.get_es_searchstore_index_documents(documents=lc_documents, embedding=embed_model,index_name="index_for_upload_files",source_id_key=source_id_key)
            else:
                es_connection = env_models_instance.get_es_connection()
                if not es_connection.indices.exists(index=index_name):
                    logger.warning(f"'{index_name}'不存在,请确认您的选择！")
                else:
                    vectorstore = env_models_instance.get_es_searchstore(es_connection=es_connection,index_name=index_name)
    if vectorstore:
        if doc_id_or_path_exists:
            filter_by_files = [str(file) for file in doc_id_or_path_exists]
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
