import re
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import WebBaseLoader
from jqcode.jq_agent.c0_init_env_models import get_es_connection, get_es_searchstore, get_es_searchstore_index_documents
from jqcode.jq_agent.c0_init_env_models import get_emb_8k_rerank_model


embed_model,embedding_model_8k,reranker = get_emb_8k_rerank_model()
### Build Index
index_name='test'
es_connection = get_es_connection()
if es_connection.indices.exists(index=index_name):
    print(f"已存在index='{index_name}'！跳过插入索引的环节。")
    vectorstore = get_es_searchstore(embedding=embed_model,es_connection=es_connection,index_name=index_name)

else:
# Docs to index
    urls = [
        "https://lilianweng.github.io/posts/2023-06-23-agent/",
        "https://lilianweng.github.io/posts/2023-03-15-prompt-engineering/",
        "https://lilianweng.github.io/posts/2023-10-25-adv-attack-llm/",
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
        chunk_size=512, chunk_overlap=0
    )
    doc_splits = text_splitter.split_documents(docs_list_cleaned)

    # Add to vectorstore
    vectorstore = get_es_searchstore_index_documents(documents=doc_splits, es_connection=es_connection,embedding=embed_model,index_name=index_name)

retriever = vectorstore.as_retriever()