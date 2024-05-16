
import os
import pathlib
import openai
from openai import OpenAI
from langchain_openai import ChatOpenAI
from BCEmbedding.tools.langchain import BCERerank
from sentence_transformers import SentenceTransformer

from elasticsearch import Elasticsearch
from langchain_elasticsearch import ElasticsearchStore
from langchain.indexes import SQLRecordManager, index
from langchain_elasticsearch.chat_history import ElasticsearchChatMessageHistory
from langchain_community.chat_models import ChatOllama
from langchain_experimental.llms.ollama_functions import OllamaFunctions

from dotenv import load_dotenv

def load_project_env(): 
    print('\n\n')
    print('=*'*20)
    root_dir = pathlib.Path(__file__).resolve().parent.parent
    env_dir = root_dir/'.env'
    dotenv_loaded = load_dotenv(env_dir)
    if dotenv_loaded:
        print("=*=* load_dotenv('.env')成功！")
    else:
        print("=*=* load_dotenv('.env')失败，请检查！")
    print('=*'*20)
    print('\n\n')

load_project_env()

base_url=os.getenv("OPENAI_API_BASE",'http://10.1.150.105:4000/v1')
api_key =os.getenv("OPENAI_API_KEY",'NotNeeded')
api_type =os.getenv("OPENAI_API_TYPE",'open_ai')
llm_model_name = os.getenv("LLM_MODEL_NAME",'gpt-4')
# https://python.langchain.com/v0.1/docs/integrations/chat/ollama_functions/
USING_OLLAMA_FUNCTIONS = os.getenv("USING_OLLAMA_FUNCTIONS",'false')
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

def get_langchain_chat_model():
    chat_model = ChatOpenAI(
        model_name=llm_model_name,
        openai_api_base=base_url,    
        openai_api_key= api_key,
        streaming=True,
        temperature=0.0,
        max_tokens=5000
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

# litellm_model = get_langchain_litellm_model()
# pass

# todo: embedding_model_8k with langchain
def get_emb_8k_rerank_model(model_name=embedding_model_name):
    if 'bge' in embedding_model_name: 
        # 有query_instruction https://github.com/langchain-ai/langchain/blob/ee94ef55ee6ab064da08340817955f821dfa6261/libs/langchain/langchain/embeddings/huggingface.py#L187
        from langchain_community.embeddings import HuggingFaceBgeEmbeddings as HuggingFaceEmbeddings
    else:
        from langchain_community.embeddings import HuggingFaceEmbeddings
    embedding_model_kwargs = {'device': 'cpu'}
    embedding_encode_kwargs = {'batch_size': 32, 'normalize_embeddings': True}
    embed_model = HuggingFaceEmbeddings(
        model_name=embedding_model_name,
        model_kwargs=embedding_model_kwargs,
        encode_kwargs=embedding_encode_kwargs,
    )
    print(f'{embedding_model_name=}初始化成功！')

    reranker_args = {'model': rerank_model_name, 'top_n': 5, 'device': 'cpu'}
    reranker = BCERerank(**reranker_args)
    print(f'{rerank_model_name=}初始化成功！')

    embedding_model_8k = SentenceTransformer(embedding_model_name_8k, trust_remote_code=True, device='cpu')
    embedding_model_8k.max_seq_length = 8192
    print(f'{embedding_model_name_8k=}初始化成功！{embedding_model_8k.max_seq_length=}，可根据实际需要进行修改。')
    return embed_model,embedding_model_8k,reranker


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

if __name__ == '__main__':
    # qwen:110b-chat-v1.5-q4_K_M
    # litellm --model ollama_chat/llama3:70b-instruct
    # litellm --model ollama_chat/yi:34b-chat-v1.5-q8_0
    es_connection = get_es_connection()
    es_searchstore = get_es_searchstore()

    knowledge_base_list = get_all_knowledge_base(es_connection)    

    open_ai = get_openai()
    openai_client = get_openai_client()
    langchain_chat_model = get_langchain_chat_model()
    embed_model,reranker,embedding_model_8k = get_emb_8k_rerank_model()
    

    from langchain_core.messages import HumanMessage,SystemMessage
    res = langchain_chat_model.invoke([SystemMessage('请使用中文回答我！'), HumanMessage('你好')])
    print(res)
    

    '''
docker run --shm-size=64g --name xinference103 -d -p 9997:9997 -e XINFERENCE_MODEL_SRC=modelscope -v /home/jqsoft/.xinference:/root/.xinference -v /home/jqsoft/.cache/huggingface:/root/.cache/huggingface -v /home/jqsoft/.cache/modelscope:/root/.cache/modelscope --gpus all xprobe/xinference:latest xinference-local -H 0.0.0.0 --log-level debug

docker run --shm-size=64g --name xinferencenightly -d -p 9997:9997 -e XINFERENCE_MODEL_SRC=modelscope -v /home/jqsoft/.xinference:/root/.xinference -v /home/jqsoft/.cache/huggingface:/root/.cache/huggingface -v /home/jqsoft/.cache/modelscope:/root/.cache/modelscope --gpus all xprobe/xinference:nightly-main xinference-local -H 0.0.0.0 --log-level debug


    '''

