import re
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import WebBaseLoader
from jqcode.jq_agent.c0_init_env_models import get_es_connection, get_es_searchstore, get_es_searchstore_index_documents,get_all_knowledge_base
from jqcode.jq_agent.c0_init_env_models import get_emb_8k_rerank_model


embed_model,embedding_model_8k,reranker = get_emb_8k_rerank_model()
### Build Index
index_name='health'
es_connection = get_es_connection()
knowledge_base_list = get_all_knowledge_base(es_connection) 
print(f"当前已存在的知识库列表：{knowledge_base_list=}")
if es_connection.indices.exists(index=index_name):
    print(f"已存在index='{index_name}'！跳过插入索引的环节。")
    vectorstore = get_es_searchstore(embedding=embed_model,es_connection=es_connection,index_name=index_name)

else:
# Docs to index
    urls = [
        "https://www.gov.cn/zhengce/content/202406/content_6955904.htm",
        "https://www.gov.cn/zhengce/2023-03/23/content_5748063.htm",
        "https://www.gov.cn/zhengce/zhengceku/202305/content_6883704.htm",
        "https://new.qq.com/rain/a/20220916A0213800",
        "https://www.gov.cn/zhengce/content/2022-05/20/content_5691424.htm",
        "https://www.cn-healthcare.com/articlewm/20220211/content-1313937.html",
        "https://www3.weforum.org/docs/WEF_Global_Health_and_Healthcare_Strategic_Outlook_2023_CN.pdf",
        "https://www2.deloitte.com/content/dam/Deloitte/cn/Documents/life-sciences-health-care/deloitte-cn-lshc-2023-global-health-care-outlook-zh-230316.pdf",
        "https://www2.deloitte.com/content/dam/Deloitte/cn/Documents/life-sciences-health-care/cn-lshc-china-lshc-industry-survey-2024-zh-240314.pdf",
        "https://www.gov.cn/zhengce/2012-12/26/content_2618554.htm"
    ]

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
    text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        chunk_size=512, chunk_overlap=100
    )
    doc_splits = text_splitter.split_documents(docs_list_cleaned)

    # Add to vectorstore
    vectorstore = get_es_searchstore_index_documents(documents=doc_splits, es_connection=es_connection,embedding=embed_model,index_name=index_name)

knowledge_base_list = get_all_knowledge_base(es_connection) 
print(f"(可能新建并刷新后)存在的知识库列表：{knowledge_base_list=}")
retriever = vectorstore.as_retriever()