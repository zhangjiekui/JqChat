from pathlib import Path
from jqcode.jq_readers.jqkj_readers import JqkjDocxReader
from jqcode.jq_agent.c0_init_env_models import env_models_instance
from jqcode.jq_utils.logger import jqkj_logger
logger = jqkj_logger(__file__).get_logger()

def get_retriever(index_name:str=None,doc_id_or_path:str=None):
    if index_name:
        es_connection = env_models_instance.get_es_connection()
        if not es_connection.indices.exists(index=index_name):
            logger.warning(f"'{index_name}'不存在,请确认您的选择！")
        else:
            vectorstore = env_models_instance.get_es_searchstore(es_connection=es_connection,index_name=index_name)
    else:
        if not doc_id_or_path:
            logger.error(f"'{index_name=}'或'{doc_id_or_path=}'二者必须有一个不得为空,请确认您的选择！")
        else:
            if not Path.exists(doc_id_or_path):
                logger.error(f"'在{index_name=}'为空的情况下,'{doc_id_or_path=}'必须是实际存在的有效文件路径，请确认您的选择！")
            else:
                reader = JqkjDocxReader(file_path=doc_id_or_path)
                documents = reader.load()

            


        # Load
        docs = [WebBaseLoader(url).load() for url in urls]
        docs_list = [item for sublist in docs for item in sublist]

        # Clean
        def replace_multiple_newlines(text):
            return re.sub(r'\n+', '\n', text)

        docs_list_cleaned = []
        for doc in docs_list:
            doc.page_content = replace_multiple_newlines(doc.page_content)
            docs_list_cleaned.append(doc)

        # Split
        text_splitter = env_models_instance.text_splitter    
        
        doc_splits = text_splitter.split_documents(docs_list_cleaned)

        # Add to vectorstore
        vectorstore = env_models_instance.get_es_searchstore_index_documents(documents=doc_splits, es_connection=es_connection,embedding=embed_model,index_name=index_name)

    knowledge_base_list = env_models_instance.get_all_knowledge_base(es_connection) 
    print(f"(可能新建并刷新后)存在的知识库列表：{knowledge_base_list=}")
    retriever = vectorstore.as_retriever()