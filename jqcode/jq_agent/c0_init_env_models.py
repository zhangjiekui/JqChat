
import os
import re
import pathlib

from typing import Annotated, List, TypedDict

import openai
import langchain
langchain.verbose = True
from openai import OpenAI
from langchain_openai import ChatOpenAI
from BCEmbedding.tools.langchain import BCERerank
from sentence_transformers import SentenceTransformer
from itertools import groupby
from elasticsearch import Elasticsearch
from langchain_core.documents import Document
from langchain_elasticsearch import ElasticsearchStore
from langchain.indexes import SQLRecordManager, index
from langchain_elasticsearch.chat_history import ElasticsearchChatMessageHistory
from langchain_community.chat_models import ChatOllama
from langchain_experimental.llms.ollama_functions import OllamaFunctions
from langchain_community.document_loaders import WebBaseLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.messages import BaseMessage
from langchain_community.vectorstores import FAISS
from langchain_community.vectorstores.utils import DistanceStrategy
from langchain.retrievers import ContextualCompressionRetriever
from langchain_core.messages import BaseMessage, HumanMessage,SystemMessage,ToolMessage,AIMessage
from langchain.callbacks.base import BaseCallbackHandler
from jqcode.jq_splitters.jq_chinese_recursive_text_splitter import ChineseRecursiveTextSplitter
from langchain_core.callbacks import StdOutCallbackHandler
from dotenv import load_dotenv
os.environ['LANGCHAIN_TRACING_V2'] = 'true'
os.environ['LANGCHAIN_ENDPOINT'] = 'https://api.smith.langchain.com'
os.environ['LANGCHAIN_API_KEY'] = "ls__fe150087fa0643f28b3eae3a07d57529"
os.environ['TAVILY_API_KEY'] = "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"

def load_project_env(): 
    print('\n\n')
    print('=*'*20)
    root_dir = pathlib.Path(__file__).resolve().parent.parent.parent
    env_dir = root_dir/'.env'
    dotenv_loaded = load_dotenv(env_dir)
    if dotenv_loaded:
        print(f"=*=* load_dotenv('{env_dir}')成功！")
    else:
        print(f"=*=* load_dotenv('{env_dir}')失败，请检查！")
    print('=*'*20)
    print('\n\n')

load_project_env()

base_url=os.getenv("OPENAI_API_BASE",'http://10.1.150.105:4000/v1')
api_key =os.getenv("OPENAI_API_KEY",'NotNeeded')
api_type =os.getenv("OPENAI_API_TYPE",'open_ai')
llm_model_name = os.getenv("LLM_MODEL_NAME",'gpt-4')

LANGCHAIN_TRACING_V2 = os.environ['LANGCHAIN_TRACING_V2']
print(f'{LANGCHAIN_TRACING_V2=}')
# https://python.langchain.com/v0.1/docs/integrations/chat/ollama_functions/
USING_OLLAMA_FUNCTIONS = os.getenv("USING_OLLAMA_FUNCTIONS",'false')
if USING_OLLAMA_FUNCTIONS.lower() == 'false' :
    USING_OLLAMA_FUNCTIONS = False
else:
    USING_OLLAMA_FUNCTIONS = True

USING_OLLAMA_LITELLM = False
prefix = 'ollama_chat/'

if prefix in llm_model_name:
    USING_OLLAMA_LITELLM =True

embedding_model_name = os.getenv("EMBEDDING_MODEL_NAME",'maidalun1020/bce-embedding-base_v1')
embedding_model_name_8k = os.getenv("EMBEDDING_MODEL_8k",'jinaai/jina-embeddings-v2-base-zh') # max_tokes =8192
rerank_model_name = os.getenv("RERANK_MODEL_NAME",'maidalun1020/bce-reranker-base_v1') #supports long passages (more than 512 tokens, less than 32k tokens) reranking

ELASTIC_PASSWORD = os.getenv("ELASTIC_PASSWORD")
CERT_FINGERPRINT = os.getenv("CERT_FINGERPRINT")
ES_URL = os.getenv("ES_URL","https://localhost:9200")

def get_openai():
    openai.api_type = api_type
    openai.default_headers = {"x-foo": "true"}  #新增的，来自官方 https://github.com/openai/openai-python/tree/e9724398d2bdd87ba41f199c3577303f1b80f2c7
    openai.api_version = os.environ.get("OPENAI_API_VERSION")
    openai.log = os.getenv("OPENAI_API_LOGLEVEL")
    return openai

# 直接使用OpenAI
def get_openai_client():
    openai_client = OpenAI(base_url=base_url,api_key=api_key)
    print(f'当前使用的模型base_url为:OpenAI, {openai_client.base_url}')
    return openai_client

def get_langchain_chat_model(temperature=0.0, max_tokens=10000, streaming=True):
    chat_model = ChatOpenAI(
        model_name=llm_model_name,
        openai_api_base=base_url,    
        openai_api_key= api_key,
        streaming=True,
        verbose=True,
        temperature=temperature,
        max_tokens=max_tokens
    )#.bind(response_format={"type": "json_object"})

    print(f'当前使用的模型为:Langchain ChatOpenAI, {chat_model.model_name}, API_URL为{chat_model.openai_api_base}')
    return chat_model

def get_langchain_chat_ollama_functions():
    _llm_model_name = llm_model_name
    if prefix in _llm_model_name:
        _llm_model_name = _llm_model_name.replace(prefix,'')
    litellm_model = OllamaFunctions(
        model = _llm_model_name,
        streaming=True,
        temperature=0.0,
        max_tokens=5000, 
        format="json"
    )
    print(f'当前使用的模型为:Langchain OllamaFunctions, {litellm_model.model}, API_URL为{litellm_model.base_url}')
    return litellm_model

# todo: embedding_model_8k with langchain
def _get_emb_8k_rerank_model(model_name=embedding_model_name, device = ['cpu','cpu','cpu'],final_docs_num_reranked=4): #device = ['cuda:1','cuda:2''cuda:3']
    if 'bge' in embedding_model_name: 
        # 有query_instruction https://github.com/langchain-ai/langchain/blob/ee94ef55ee6ab064da08340817955f821dfa6261/libs/langchain/langchain/embeddings/huggingface.py#L187
        from langchain_community.embeddings import HuggingFaceBgeEmbeddings as HuggingFaceEmbeddings
    else:
        from langchain_community.embeddings import HuggingFaceEmbeddings
    embedding_model_kwargs = {'device': device[0]}
    embedding_encode_kwargs = {'batch_size': 32, 'normalize_embeddings': True}
    embed_model = HuggingFaceEmbeddings(
        model_name=embedding_model_name,
        model_kwargs=embedding_model_kwargs,
        encode_kwargs=embedding_encode_kwargs,
    )
    emb = embed_model.embed_query("初始化成功！")
    print(emb)
    print(f'{embedding_model_name=}初始化成功！')

    reranker_args = {'model': rerank_model_name, 'top_n': final_docs_num_reranked, 'device': device[1]}
    reranker = BCERerank(**reranker_args)
    print(f'{rerank_model_name=}初始化成功！')

    embedding_model_8k = SentenceTransformer(embedding_model_name_8k, trust_remote_code=True, device=device[2])
    embedding_model_8k.max_seq_length = 8192
    print(f'{embedding_model_name_8k=}初始化成功！{embedding_model_8k.max_seq_length=}，可根据实际需要进行修改。')
    return embed_model,embedding_model_8k,reranker

embed_model,embedding_model_8k,reranker = _get_emb_8k_rerank_model()

def get_emb_8k_rerank_model(model_name=embedding_model_name, device = ['cpu','cpu','cpu'],final_docs_num_reranked=4):
    global embed_model
    global embedding_model_8k
    global reranker
    if not (embed_model and  embedding_model_8k and  reranker):
        embed_model,embedding_model_8k,reranker = _get_emb_8k_rerank_model(model_name=model_name, device = device,final_docs_num_reranked=final_docs_num_reranked)
    return embed_model,embedding_model_8k,reranker


chinese_text_splitter = ChineseRecursiveTextSplitter(chunk_size=500,chunk_overlap=0.2,model_name=embed_model)
# Clean
def replace_multiple_newlines(text):
    return re.sub(r'\n+', '\n', text)

def split_and_get_chunks_relevant_from_documents(query:str, docs_list:List[Document]=None,text_splitter=chinese_text_splitter,reranker=reranker,
                                                 if_reranking:bool=True,retriever_docs_num=10,final_docs_num=4,score_threshold=0.3):
    docs_list_cleaned = []
    for doc in docs_list:
        doc.page_content = replace_multiple_newlines(doc.page_content)
        docs_list_cleaned.append(doc)
    text_chunks = text_splitter.split_documents(docs_list_cleaned)
    
    if if_reranking:
        retriever = FAISS.from_documents(text_chunks, embed_model, distance_strategy=DistanceStrategy.MAX_INNER_PRODUCT).as_retriever(search_type="similarity", search_kwargs={"score_threshold": score_threshold, "k": retriever_docs_num})
        compression_retriever = ContextualCompressionRetriever(base_compressor=reranker, base_retriever=retriever)
        chunks_relevant = compression_retriever.invoke(query)
    else:
        retriever_docs_num = final_docs_num
        retriever = FAISS.from_documents(text_chunks, embed_model, distance_strategy=DistanceStrategy.MAX_INNER_PRODUCT).as_retriever(search_type="similarity", search_kwargs={"score_threshold": score_threshold, "k": retriever_docs_num})
        chunks_relevant = retriever.invoke(query)
    return chunks_relevant

# https://github.com/langchain-ai/langgraph/blob/main/examples/managing-conversation-history.ipynb
def filter_and_get_messages_relevant_to_query(query:str,messages_list:List[BaseMessage],text_splitter=chinese_text_splitter,reranker=reranker,
                                                 if_reranking:bool=True,retriever_docs_num=10,final_docs_num=4,score_threshold=0.3):
    unique_messages_list = []
    messages_content_set = set()
    messages_list.reverse()
    for message in messages_list:
        if message.content not in  messages_content_set:
            unique_messages_list.append(message)
            messages_content_set.add(message.content)
    unique_messages_list.reverse()    
    docs_from_messages = [Document(page_content=message.content,metadata={"message_index":message_index}) for message_index, message in enumerate(unique_messages_list)]
    
    chunks_relevant = split_and_get_chunks_relevant_from_documents(query, docs_from_messages,text_splitter=text_splitter,reranker=reranker,
                                                                   if_reranking=if_reranking,retriever_docs_num=retriever_docs_num, final_docs_num=final_docs_num,score_threshold=score_threshold)
    
    
    text_chunks = text_splitter.split_documents(docs_from_messages)
    retriever = FAISS.from_documents(text_chunks, embed_model, distance_strategy=DistanceStrategy.MAX_INNER_PRODUCT).as_retriever(search_type="similarity", search_kwargs={"score_threshold": score_threshold, "k": retriever_docs_num})
    chunks_relevant2 = retriever.invoke(query)

    sorted_chunks_relevant = sorted(chunks_relevant, key=lambda x: (x.metadata['message_index'], x.metadata['start_index']))
    messages_relevant = []

    print("+++++++++++过滤后保留的消息++++++++++++++++++++++过滤后保留的消息++++++++++++++++++++++过滤后保留的消息+++++++++++")   
    for chunk_relevant in sorted_chunks_relevant:
        index = chunk_relevant.metadata['message_index']
        # unique_messages_list[index].content = chunk_relevant.page_content #不能改变内容（即不能使用分块后的内容，否则可能无法获取完整的答案）
        message_relevant = unique_messages_list[index]
        if message_relevant not in messages_relevant:
            relevance_score = chunk_relevant.metadata.get('relevance_score',None)
            print("--------------------------------")            
            # if isinstance(message_relevant,ToolMessage):
            #     if message_relevant.name == 'web_search':
            #         pass
            messages_relevant.append(message_relevant)
            message_relevant.pretty_print()
            print(f"^^^^^^^^^上条Message的{relevance_score=}^^^^^^^^^")
    print("+++++++++++过滤后保留的消息++++++++++++++++++++++过滤后保留的消息++++++++++++++++++++++过滤后保留的消息+++++++++++")
    messages_list.reverse() # 前面messages_list顺序翻转了，所以这里还要翻转回来
    last_message = messages_list[-1]
    if messages_relevant[-1]!=last_message: 
        messages_relevant.append(last_message)
    return messages_relevant


def get_es_connection(): 
    es_connection= Elasticsearch(
        ES_URL,
        # ca_certs=f"d:\JqkjKB\http_ca.crt",
        ssl_assert_fingerprint=CERT_FINGERPRINT,
        basic_auth=("elastic", ELASTIC_PASSWORD),
        request_timeout=600 #这个设置很重要  elastic_transport.ConnectionTimeout: Connection timed out
    )

    print(f'当前使用的Elasticsearch URL为| { ES_URL } |,详细信息如下:')
    print('-------Elasticsearch Connection详细信息-------')
    print(es_connection.info())
    print('-------Elasticsearch Connection详细信息-------')
    print('-------可以通过Kibana URL查看:| http://127.0.0.1:5601 | -------')
    return es_connection

def get_all_knowledge_base(es_connection=None,exclude_system_indices=True):
    if not es_connection:
        es_connection=get_es_connection()
    all_indices = es_connection.indices.get_alias(index="*")
    if exclude_system_indices:
        all_indices = [index_name for index_name in all_indices if not index_name.startswith('.')]
    return all_indices


hybrid=False
strategy=ElasticsearchStore.ApproxRetrievalStrategy(hybrid=hybrid)
def get_es_searchstore(embedding=None,es_connection=None,index_name='test',strategy=strategy):
    embedding = embedding if embedding else get_emb_8k_rerank_model()[0]
    es_connection = es_connection if es_connection else get_es_connection()
    index_name = index_name if index_name else 'test'    
    es_searchstore = ElasticsearchStore(es_connection=es_connection, index_name=index_name, embedding=embedding,strategy=strategy)
    return es_searchstore


# 方式一，使用LangChain indexing API，防止重复插入
# https://python.langchain.com/docs/modules/data_connection/indexing 

def get_es_searchstore_index_documents(documents,embedding,es_connection,index_name,cleanup="incremental",clear_before_add_index=True,strategy=strategy):
    es_searchstore = ElasticsearchStore(es_connection=es_connection, index_name=index_name, embedding=embedding,strategy=strategy)
    namespace = f"elasticsearch/{index_name}"
    record_manager = SQLRecordManager(namespace, db_url="sqlite:///record_manager_cache.sql")
    record_manager.create_schema()
    
    def _clear():
        """Hacky helper method to clear content. See the `full` mode section to to understand why it works."""
    clear_result_report = index([], record_manager, es_searchstore, cleanup="full", source_id_key="source")
    print(f'Clear_Result report of "index_documents_to_es_searchstore":{clear_result_report}')

    if clear_before_add_index:
        _clear()
    es_searchstore.index_name=index_name
    index_result_report=index(documents, record_manager, es_searchstore, cleanup=cleanup, source_id_key="source")
    print(f'Index_Result report of "index_documents_to_es_searchstore":{index_result_report}')

    es_searchstore.client.indices.refresh(index=index_name)
    return es_searchstore

# 方式二：常见的在教程中见到的
def get_es_searchstore_from_documents(documents,embedding,es_connection,index_name,strategy=strategy):
    es_searchstore = ElasticsearchStore.from_documents(documents=documents,embedding=embedding,es_connection=es_connection,index_name=index_name,strategy=strategy)
    es_searchstore.client.indices.refresh(index=index_name)
    es_searchstore.index_name=index_name
    return es_searchstore


class MyCustomHandler(BaseCallbackHandler):
    def on_chat_model_start(self,serialized, messages: List[List[BaseMessage]], *args, **kwargs):
        print("<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<")
        print(f"Input Messages:")
        for ms in messages:
            for m in ms:
                m.pretty_print()
        print("<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<\n")

    def on_llm_end(self, response,*args, **kwargs):
        print("\n>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
        print(f"Output Generations:")
        for g in response.generations:
            print(g[0].text)
        print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")

custom_handler = MyCustomHandler()
std_out_handler = StdOutCallbackHandler()
def get_custom_handler():
    global custom_handler
    global std_out_handler
    if not custom_handler:
        custom_handler = MyCustomHandler()
    if not std_out_handler:
        std_out_handler = StdOutCallbackHandler()
    return [custom_handler,std_out_handler]



if __name__ == '__main__':
    # qwen:110b-chat-v1.5-q4_K_M
    # litellm --model ollama_chat/llama3:70b-instruct
    # litellm --model ollama_chat/yi:34b-chat-v1.5-q8_0


    sentense= ["张结魁是谁？","张结魁是安徽晶奇公司的",
               "create a compression retriever, we need a base retriever first",
               "As shown in the summary table above, the number of lexical units has increased by 16% to more than 11,800, while the numbers of frames and FEs have increased by 25% to 1,019 and 8,884 respectively. Some frames are marked as “non-lexical”, meaning that we have created them because they are logically necessary in the frame hierarchy,"]
    docs = [Document(page_content=s) for s in sentense]
    chunks = split_and_get_chunks_relevant_from_documents(docs_list=docs,query='张结魁')
    print(chunks)

    from langchain_core.messages import HumanMessage,SystemMessage
    es_connection = get_es_connection()
    es_searchstore = get_es_searchstore()

    knowledge_base_list = get_all_knowledge_base(es_connection)    

    open_ai = get_openai()
    openai_client = get_openai_client()
    langchain_chat_model = get_langchain_chat_model()
    embed_model,embedding_model_8k,reranker = get_emb_8k_rerank_model()
    res = langchain_chat_model.invoke([SystemMessage('请使用中文回答我！'), HumanMessage('你好')])
    print(res)

    ### Build An Index
    index_name='health'
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

    knowledge_base_list = get_all_knowledge_base(es_connection) 
    print(f"插入{index_name}前的{knowledge_base_list=}")
    if es_connection.indices.exists(index=index_name):
        print(f"已存在index='{index_name}'！跳过插入索引的环节。")
    else:
        docs = [WebBaseLoader(url).load() for url in urls]
        docs_list = [item for sublist in docs for item in sublist]
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
        print(f"插入{index_name}后的{knowledge_base_list=}")


    '''
docker run --shm-size=64g --name xinference103 -d -p 9997:9997 -e XINFERENCE_MODEL_SRC=modelscope -v /home/jqsoft/.xinference:/root/.xinference -v /home/jqsoft/.cache/huggingface:/root/.cache/huggingface -v /home/jqsoft/.cache/modelscope:/root/.cache/modelscope --gpus all xprobe/xinference:latest xinference-local -H 0.0.0.0 --log-level debug

docker run --shm-size=64g --name xinferencenightly -d -p 9997:9997 -e XINFERENCE_MODEL_SRC=modelscope -v /home/jqsoft/.xinference:/root/.xinference -v /home/jqsoft/.cache/huggingface:/root/.cache/huggingface -v /home/jqsoft/.cache/modelscope:/root/.cache/modelscope --gpus all xprobe/xinference:nightly-main xinference-local -H 0.0.0.0 --log-level debug


    '''

