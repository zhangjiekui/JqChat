
import os
import pathlib
import openai
from openai import OpenAI
from langchain_openai import ChatOpenAI

from langchain_community.embeddings import HuggingFaceEmbeddings
from BCEmbedding.tools.langchain import BCERerank
from sentence_transformers import SentenceTransformer

from elasticsearch import Elasticsearch
from langchain_elasticsearch import ElasticsearchStore
from langchain.indexes import SQLRecordManager, index
from langchain_elasticsearch.chat_history import ElasticsearchChatMessageHistory

from dotenv import load_dotenv
 
root_dir = pathlib.Path(__file__).resolve().parent.parent
env_dir = root_dir/'.env'
dotenv_loaded = load_dotenv(env_dir)
if dotenv_loaded:
    print("load_dotenv('.env')成功！")
else:
    print("load_dotenv('.env')失败，请检查！")

base_url=os.getenv("OPENAI_API_BASE",'http://10.1.150.105:4000/v1')
api_key =os.getenv("OPENAI_API_KEY",'NotNeeded')
api_type =os.getenv("OPENAI_API_TYPE",'open_ai')
llm_model_name = os.getenv("LLM_MODEL_NAME",'gpt-4')

embedding_model_name = os.getenv("EMBEDDING_MODEL_NAME",'maidalun1020/bce-embedding-base_v1')
rerank_model_name = os.getenv("RERANK_MODEL_NAME",'maidalun1020/bce-reranker-base_v1') #supports long passages (more than 512 tokens, less than 32k tokens) reranking
embedding_model_name_8k = os.getenv("EMBEDDING_MODEL_8k",'jinaai/jina-embeddings-v2-base-zh') # max_tokes =8192

ELASTIC_PASSWORD = os.getenv("ELASTIC_PASSWORD")
CERT_FINGERPRINT = os.getenv("CERT_FINGERPRINT")
ES_URL = os.getenv("ELASTIC_PASSWORD","https://localhost:9200")

def get_openai():
    openai.api_type = api_type
    openai.default_headers = {"x-foo": "true"}  #新增的，来自官方 https://github.com/openai/openai-python/tree/e9724398d2bdd87ba41f199c3577303f1b80f2c7
    openai.api_version = os.environ.get("OPENAI_API_VERSION")
    openai.log = os.getenv("OPENAI_API_LOGLEVEL")
    return openai

# 直接使用OpenAI
def get_openai_client():
    openai_client = OpenAI(base_url=base_url,api_key=api_key)
    print(f'当前使用的OpenAI模型base_url为:{openai_client.base_url}')
    return openai_client

def get_langchain_chat_model():
    chat_model = ChatOpenAI(
        model_name=llm_model_name,
        openai_api_base=base_url,    
        openai_api_key= api_key,
        streaming=True,
        temperature=0
    )
    print(f'当前使用的Langchain ChatOpenAI模型为:{chat_model.model_name},API_URL为{chat_model.openai_api_base}')
    return chat_model

# todo: embedding_model_8k with langchain
def get_emb_rerank_8k_model():
    embedding_model_kwargs = {'device': 'cuda:1'}
    embedding_encode_kwargs = {'batch_size': 32, 'normalize_embeddings': True, 'show_progress_bar': False}
    embed_model = HuggingFaceEmbeddings(
        model_name=embedding_model_name,
        model_kwargs=embedding_model_kwargs,
        encode_kwargs=embedding_encode_kwargs,
    )

    reranker_args = {'model': rerank_model_name, 'top_n': 5, 'device': 'cuda:2'}
    reranker = BCERerank(**reranker_args)

    embedding_model_8k = SentenceTransformer(embedding_model_name_8k, trust_remote_code=True, device='cuda:3')
    embedding_model_8k.max_seq_length = 8192
    return embed_model,reranker,embedding_model_8k


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
    return es_connection

if __name__ == '__main__':
    open_ai = get_openai()
    openai_client = get_openai_client()
    langchain_chat_model = get_langchain_chat_model()
    embed_model,reranker,embedding_model_8k = get_emb_rerank_8k_model()
    es_connection = get_es_connection()
    

