import warnings
warnings.filterwarnings("ignore")

import os,sys,pathlib
os.environ['USER_AGENT'] = 'myagent'
import re
import threading
from pathlib import Path
from functools import lru_cache
from typing import Annotated, List, TypedDict, Optional, Sequence,Literal, Any,Union
from langchain.callbacks.manager import Callbacks
import openai
import langchain
langchain.verbose = False
from langchain.pydantic_v1 import Extra
from openai import OpenAI
from langchain_openai import ChatOpenAI
from BCEmbedding.tools.langchain import BCERerank
from sentence_transformers import SentenceTransformer
from itertools import groupby
from elasticsearch import Elasticsearch
from langchain_core.documents import Document
from langchain_elasticsearch import ElasticsearchStore
from elasticsearch.helpers.vectorstore import DenseVectorStrategy,BM25Strategy
from langchain.indexes import SQLRecordManager, index
from langchain_elasticsearch.chat_history import ElasticsearchChatMessageHistory

# from langchain_community.chat_models import ChatOllama
from langchain_ollama import ChatOllama

from langchain.retrievers.document_compressors.base import BaseDocumentCompressor
from sentence_transformers import SentenceTransformer,CrossEncoder

from langchain_community.document_loaders import WebBaseLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.messages import BaseMessage
from langchain_community.vectorstores import FAISS
from langchain_community.vectorstores.utils import DistanceStrategy

from langchain.retrievers import ContextualCompressionRetriever
from langchain_core.messages import BaseMessage, HumanMessage,SystemMessage,ToolMessage,AIMessage
from langchain.callbacks.base import BaseCallbackHandler
from langchain_core.callbacks import StdOutCallbackHandler
from jqcode.jq_splitters.backend_splitter_utils.jq_chinese_recursive_text_splitter import JqChineseRecursiveTextSplitter
from jqcode.jq_splitters.jq_docx_tree_text_splitter import JqkjDocTreeTokenTextSplitter,load_project_env
from langchain_text_splitters import Language


from transformers import AutoTokenizer
from pydantic.v1 import PrivateAttr
from dotenv import load_dotenv, find_dotenv
import json_repair
from jqcode.jq_utils.logger import jqkj_logger
logger = jqkj_logger(__file__).get_logger()


# os.environ['LANGCHAIN_TRACING_V2'] = 'true'
# os.environ['LANGCHAIN_ENDPOINT'] = 'https://api.smith.langchain.com'
# os.environ['LANGCHAIN_API_KEY'] = "ls__fe150087fa0643f28b3eae3a07d57529"
# os.environ['TAVILY_API_KEY'] = "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"

class XinferenceReranker(BaseDocumentCompressor):
    client: str = 'Xinference'
    top_n: int = 6
    """Number of documents to return."""
    model: Any=None
    """Xinference Rerank Model Instance to use for reranking."""
    _model: Any = PrivateAttr()
    class Config:
        """Configuration for this pydantic object."""
        # extra = Extra.forbid 
        extra = Extra.allow
        arbitrary_types_allowed = True

    def __init__(
        self,
        top_n: int = 6,
        model:Any =None,
        **kwargs
    ):
        self._model = model
        super().__init__(top_n=top_n, model=model)
    
    # https://github.com/xorbitsai/inference/blob/7d83300a7694a0262b634007ea4164ea753e466f/xinference/model/rerank/core.py
    def rerank(
        self,
        documents: List[str],
        query: str,
        top_n: Optional[int]= 6,        
        max_chunks_per_doc: Optional[int]=None,
        return_documents: Optional[bool]=True,
        return_len: Optional[bool]=True,
        **kwargs,
    ):
        top_n = top_n or self.top_n
        return self._model.rerank(documents,query,top_n,max_chunks_per_doc,return_documents,return_len,**kwargs)
    
    def compress_documents(
        self,
        documents: Union[Sequence[Document],Sequence[str]],
        query: str,
        threshold:float = 0.2, #"""相关性阈值，低于此值的文档不返回."""
        callbacks: Optional[Callbacks] = None,
    ) -> Sequence[Document]:
        """
        Compress documents using `Xinference Rerank Model API`.

        Args:
            documents: A sequence of documents to compress.
            query: The query to use for compressing the documents.
            callbacks: Callbacks to run during the compression process.

        Returns:
            A sequence of compressed documents.
        """
        if len(documents) == 0:  # to avoid empty api call
            return []
        doc_list = list(documents)
        passages = []
        valid_doc_list = []

        doc_list = [Document(page_content=d) if isinstance(d,str) else d for d in doc_list]
        for d in doc_list:
            passage = d.page_content if isinstance(d,Document) else d
            if isinstance(passage, str) and len(passage) > 0:
                passages.append(passage.replace('\n', ' '))
                valid_doc_list.append(d)
       
        rerank_result = self._model.rerank(passages,query,top_n=self.top_n,return_documents=False,return_len=True)
        rerank_result_list = rerank_result["results"]
        final_results = []
        for result in rerank_result_list:
            score =  result['relevance_score']
            if score>=threshold:
                doc_id = result['index']
                doc = valid_doc_list[doc_id]
                doc.metadata.update({"relevance_score":score})
                final_results.append(doc)
       
        final_results = final_results[:self.top_n]
        return final_results


def replace_multiple_newlines(text):
    return re.sub(r'\n+', '\n', text)

def clean_up_list_when_encounter_null_element(messages_a: list, messages_b: list | None) -> list:
    # todo 可以考虑在messages_b中加入一个控制消息：如ControlMassage(content="replace")，取出来后，直接返回 messages_b[0:-1]
    if messages_b:
        if not isinstance(messages_b,list):
            messages_b = [messages_b]        
       
        if not messages_a or messages_a == messages_b:
            return messages_b
        else:
            messages_a = [el for el in messages_a if el not in messages_b]
            return messages_a + messages_b
    else:
        return []

class SingletonDecorator:
    def __init__(self, cls):
        self._cls = cls
        self._instances = {}
        self._lock = threading.Lock()

    def __call__(self, *args, **kwargs):
        if self._cls not in self._instances:
            with self._lock:
                if self._cls not in self._instances:
                    instance = self._cls(*args, **kwargs)
                    self._instances[self._cls] = instance
        return self._instances[self._cls]

@SingletonDecorator
class InitEnvModels:
    def __init__(self):
        self.env_loaded = load_project_env()
        assert self.env_loaded, "环境变量没有正确载入！"
        
        self.ollama_host = os.getenv("OLLAMA_HOST",'http://localhost:11434')
        self.api_key =os.getenv("OPENAI_API_KEY",'abc123')
        self.api_type =os.getenv("OPENAI_API_TYPE",'open_ai')
        

        _LLM_MODEL_CARD = {"name":"qwen2-instruct","online":"http://10.1.150.105:9997/v1","local":"","dimensions":0,"max_tokens":32000,"base_url":"http://10.1.150.105:9997/v1"}
        _EMBEDDING_MODEL_CARD = {"name":"bce-embedding-base_v1","online":"maidalun1020/bce-embedding-base_v1","local":"/data/models/bce-embedding-base_v1","dimensions":768,"max_tokens":512,"base_url":"http://10.1.150.105:9997/v1"}
        _EMBEDDING_MODEL_8k_CARD = {"name":"jina-embeddings-v2-base-zh","online":"jinaai/jina-embeddings-v2-base-zh","local":"/data/models/jina-embeddings-v2-base-zh","dimensions":768,"max_tokens":8192,"base_url":"http://10.1.150.105:9997/v1"}
        # https://github.com/xorbitsai/inference/issues/1695 bce-reranker-base_v1的是514  经过测试，使用bce-rerank模型时，只要corpus里的文本总tensor长度超过514就会报错
        _RERANK_MODEL_CARD = {"name":"jina-reranker-v2","online":"jinaai/jina-reranker-v2-base-multilingual","local":"maidalun1020/bce-reranker-base_v1","dimensions":768,"max_tokens":1026,"base_url":"http://10.1.150.105:9997"} ##Rerank: url要去掉"/v1"
        # _RERANK_MODEL_CARD = {"name":"bce-reranker-base_v1","online":"maidalun1020/bce-reranker-base_v1","local":"/data/models/bce-reranker-base_v1","dimensions":512,"max_tokens":32000,"base_url":"http://10.1.150.105:9997"} ##Rerank: url要去掉"/v1"

        
        LLM_MODEL_CARD = os.getenv("LLM_MODEL_CARD",'')
        LLM_MODEL_CARD = json_repair.loads(LLM_MODEL_CARD)
        LLM_MODEL_CARD = LLM_MODEL_CARD if LLM_MODEL_CARD else _LLM_MODEL_CARD
        
        EMBEDDING_MODEL_CARD = os.getenv("EMBEDDING_MODEL_CARD",'')
        EMBEDDING_MODEL_CARD = json_repair.loads(EMBEDDING_MODEL_CARD)
        EMBEDDING_MODEL_CARD = EMBEDDING_MODEL_CARD if EMBEDDING_MODEL_CARD else _EMBEDDING_MODEL_CARD

        EMBEDDING_MODEL_8k_CARD = os.getenv("EMBEDDING_MODEL_8k_CARD",'')
        EMBEDDING_MODEL_8k_CARD = json_repair.loads(EMBEDDING_MODEL_8k_CARD)
        EMBEDDING_MODEL_8k_CARD = EMBEDDING_MODEL_8k_CARD if EMBEDDING_MODEL_8k_CARD else _EMBEDDING_MODEL_8k_CARD

        RERANK_MODEL_CARD = os.getenv("RERANK_MODEL_CARD",'')
        RERANK_MODEL_CARD = json_repair.loads(RERANK_MODEL_CARD)
        RERANK_MODEL_CARD = RERANK_MODEL_CARD if RERANK_MODEL_CARD else _RERANK_MODEL_CARD

        self.llm_model_card = LLM_MODEL_CARD
        self.embedding_model_card = EMBEDDING_MODEL_CARD
        self.embedding_model_8k_card = EMBEDDING_MODEL_8k_CARD
        self.rerank_model_card = RERANK_MODEL_CARD

        self.llm_model_base_url= self.llm_model_card['base_url']
        self.llm_model_name = self.llm_model_card['name']
        self.llm_model_max_tokens = self.llm_model_card['max_tokens']


        self.base_url = self.llm_model_base_url # 如果是同一服务器上部署的大语言和Emb模型，可能会省略配置其他模型，直接用这个

        self.embedding_model_name = self.embedding_model_card['name']
        self.embedding_model_dimentions = self.embedding_model_card['dimensions']
        self.embedding_model_max_tokens = self.embedding_model_card['max_tokens']
        self.embedding_model_local = self.embedding_model_card['local']
        self.embedding_model_online = self.embedding_model_card['online']
        self.embedding_model_base_url = self.embedding_model_card.get('base_url',None) or self.base_url
        self.embedding_model_name_or_path = self.embedding_model_local if self.embedding_model_local and Path(self.embedding_model_local).exists() else self.embedding_model_online


        self.embedding_model_8k_name =self.embedding_model_8k_card['name']
        self.embedding_model_8k_dimentions = self.embedding_model_8k_card['dimensions']
        self.embedding_model_8k_max_tokens = self.embedding_model_8k_card['max_tokens']
        self.embedding_model_8k_local = self.embedding_model_8k_card['local']
        self.embedding_model_8k_online = self.embedding_model_8k_card['online']
        self.embedding_model_8k_base_url = self.embedding_model_8k_card.get('base_url',None) or self.base_url
        self.embedding_model_8k_name_or_path = self.embedding_model_8k_local if self.embedding_model_8k_local and Path(self.embedding_model_8k_local).exists() else self.embedding_model_8k_online



        self.rerank_model_name = self.rerank_model_card['name']        
        self.rerank_model_dimentions = self.rerank_model_card['dimensions']
        self.rerank_model_max_tokens = self.rerank_model_card['max_tokens']
        self.rerank_model_local = self.rerank_model_card['local']
        self.rerank_model_online = self.rerank_model_card['online']
        self.rerank_model_base_url = self.rerank_model_card.get('base_url',None) or self.base_url[0:-3] ####Rerank: url要去掉"/v1"
        self.rerank_model_name_or_path = self.rerank_model_local if self.rerank_model_local and Path(self.rerank_model_local).exists() else self.rerank_model_online
        
        self.embed_model,self.embedding_model_8k,self.reranker = None,None,None
        self.embed_model,self.embedding_model_8k,self.reranker = self.get_emb_8k_rerank_model()
        
        self._tokenizer = AutoTokenizer.from_pretrained(self.embedding_model_name_or_path)
        self.text_splitter = JqChineseRecursiveTextSplitter(self._tokenizer,chunk_size=self.embedding_model_max_tokens,chunk_overlap=0.2)
        self.doc_tree_spiltter = JqkjDocTreeTokenTextSplitter.from_defaults(cr_text_splitter=self.text_splitter)

        # code_splitter = self.text_splitter.from_language(language=Language.PYTHON,tokenizer=self._tokenizer)

  
        
        self.ELASTIC_PASSWORD = os.getenv("ELASTIC_PASSWORD")
        self.CERT_FINGERPRINT = os.getenv("CERT_FINGERPRINT")
        self.ES_URL = os.getenv("ES_URL","https://localhost:9200")

        KERNEL_API_BASE = os.getenv("KERNEL_API_BASE",'http://localhost')
        API_PORT = os.getenv("API_PORT",5011)
        self.kernel_api_url = f"{KERNEL_API_BASE}:{API_PORT}/api"
        root_dir = pathlib.Path().resolve()
        self.workspace = str(root_dir/'JqChat/workspace/')

        # loade models:
        self.openai = None
        self.get_openai()

        self.openai_client = None
        self.get_openai_client()

        self.chat_model = None
        self.get_langchain_chat_model()

        self.embed_model,self.embedding_model_8k,self.reranker = None, None, None
        self.embed_model,self.embedding_model_8k,self.reranker = self.get_emb_8k_rerank_model() 

        # load ES 
        self.es_connection = None
        self.get_es_connection() 

        self.all_indices = None
        self.all_indices = self.get_all_knowledge_base()
        self.strategy = DenseVectorStrategy(hybrid=False)

        self.default_chinese_analyzer_settings = {"index": {"analysis.analyzer.default.type": "ik_max_word","analysis.search_analyzer.default.type": "ik_smart"}}

    def load_project_env(self):
        if not self.env_loaded: 
            print('\n\n')
            print('=*'*20)
            env_dir = find_dotenv()
            if not env_dir:
                root_dir = pathlib.Path().resolve()
                env_dir = root_dir/'JqChat/.env'
            print(f"项目.env文件路径：{env_dir}")
            dotenv_loaded = load_dotenv(env_dir)
            if dotenv_loaded:
                print(f"=*=* load_dotenv('{env_dir}')成功！")
            else:
                print(f"=*=* load_dotenv('{env_dir}')失败，请检查！")
            print('=*'*20)
            print('\n\n')
        self.env_loaded = True

    def get_openai(self):
        if not self.openai:
            openai.api_type = self.api_type
            openai.default_headers = {"x-foo": "true"}  #新增的，来自官方 https://github.com/openai/openai-python/tree/e9724398d2bdd87ba41f199c3577303f1b80f2c7
            openai.api_version = os.environ.get("OPENAI_API_VERSION")
            openai.log = os.getenv("OPENAI_API_LOGLEVEL")
            self.openai = openai
        return self.openai

    # 直接使用OpenAI
    def get_openai_client(self):
        if not self.openai_client:
            self.openai_client = OpenAI(base_url=self.llm_model_base_url,api_key=self.api_key)
            print(f'当前使用的LLM模型base_url为:OpenAI, {self.openai_client.base_url}')
        return self.openai_client


    def get_langchain_chat_model(self, temperature=0.01, max_tokens=None, streaming=True):
        if max_tokens:
            if max_tokens!=self.llm_model_max_tokens:
                logger.warning(f"您现在请求的llm {max_tokens=}，与环境配置中的{self.llm_model_max_tokens=}不同，请确认！")
        else:
            max_tokens = self.llm_model_max_tokens

        self.chat_model = ChatOpenAI(
                model_name=self.llm_model_name,
                openai_api_base=self.llm_model_base_url,    
                openai_api_key= self.api_key,
                streaming=streaming,
                verbose=True,
                temperature=temperature,
                max_tokens=max_tokens,
                
            )
        logger.info(f'当前使用的LLM模型为:Langchain ChatOpenAI, {self.chat_model.model_name}, API_URL为{self.chat_model.openai_api_base}')
        return self.chat_model
    
    def _get_emb_8k_rerank_model(self,embedding_model_name=None, embedding_model_name_8k=None, rerank_model_name=None, device = ['cpu','cpu','cpu'],final_docs_num_reranked=4): #device = ['cuda:1','cuda:2''cuda:3']
        name_or_path = embedding_model_name if embedding_model_name else self.embedding_model_name_or_path       
        if 'bge' in name_or_path: 
            # 有query_instruction https://github.com/langchain-ai/langchain/blob/ee94ef55ee6ab064da08340817955f821dfa6261/libs/langchain/langchain/embeddings/huggingface.py#L187
            from langchain_community.embeddings import HuggingFaceBgeEmbeddings as HuggingFaceEmbeddings
        else:
            from langchain_huggingface import HuggingFaceEmbeddings
        embedding_model_kwargs = {'device': device[0]}
        embedding_encode_kwargs = {'batch_size': 32, 'normalize_embeddings': True}
        embed_model = HuggingFaceEmbeddings(
            model_name=name_or_path,
            model_kwargs=embedding_model_kwargs,
            encode_kwargs=embedding_encode_kwargs,
        )
        # emb = embed_model.embed_query("初始化成功！")
        # print(emb)
        if name_or_path == self.embedding_model_name_or_path:
            logger.info(f'embedding_model: {self.embedding_model_name}初始化成功！维度为{self.embedding_model_dimentions}，最大Tokens数为:{self.embedding_model_max_tokens}')
        else:
            logger.info(f'embedding_model: {name_or_path}初始化成功！')
        
        
        name_or_path = embedding_model_name_8k if embedding_model_name_8k else self.embedding_model_8k_name_or_path
        embedding_model_8k = SentenceTransformer(name_or_path, trust_remote_code=True, device=device[2])

        if name_or_path == self.embedding_model_8k_name_or_path:
            embedding_model_8k.max_seq_length = self.embedding_model_8k_max_tokens
            logger.info(f'embedding_model_8k: {self.embedding_model_8k_name}初始化成功！维度为{self.embedding_model_8k_dimentions}，最大Tokens数为:{self.embedding_model_8k_max_tokens}')
            logger.info(f'{embedding_model_8k.max_seq_length=}，可根据实际需要进行修改。')
        else:
            logger.info(f'embedding_model_8k: {name_or_path}初始化成功！')
        

        name_or_path = rerank_model_name if rerank_model_name else self.rerank_model_name_or_path
        reranker_args = {'model': name_or_path, 'top_n': final_docs_num_reranked, 'device': device[1]}
        reranker = BCERerank(**reranker_args)
        if name_or_path == self.rerank_model_name_or_path:
            logger.info(f'rerank_model: {self.rerank_model_name}初始化成功！维度为{self.rerank_model_dimentions}，最大Tokens数为:{self.rerank_model_max_tokens}')
        else:
            logger.info(f'rerank_model: {name_or_path}初始化成功！')

        return embed_model,embedding_model_8k,reranker

    def _get_emb_8k_rerank_model_api(self):
        from xinference.client import Client
        from jqcode.jq_knowledge_manegement.chatchat.server.localai_embeddings import LocalAIEmbeddings
        embed_model = LocalAIEmbeddings(model=self.embedding_model_name,api_key="NotNeed",base_url=self.embedding_model_base_url,embedding_ctx_length=self.embedding_model_max_tokens*8,chunk_size=self.embedding_model_max_tokens)
        embedding_model_8k = LocalAIEmbeddings(model=self.embedding_model_8k_name,api_key="NotNeed",base_url=self.embedding_model_8k_base_url,embedding_ctx_length=self.embedding_model_8k_max_tokens*4,chunk_size=self.embedding_model_8k_max_tokens)
        try:
            client = Client(self.rerank_model_base_url) #url要去掉"/v1"
            xinfer_reranker = client.get_model(self.rerank_model_name)

            # BCERerank: compress_documents(documents: Sequence[Document],query: str)
            # xinference.client: model.rerank(corpus, query) https://inference.readthedocs.io/zh-cn/latest/index.html
            # https://github.com/xorbitsai/inference/blob/7d83300a7694a0262b634007ea4164ea753e466f/xinference/model/rerank/core.py
            reranker = XinferenceReranker(top_n=6,model=xinfer_reranker)
            # reranker.compress_documents = reranker.rerank
            # query = "A man is eating pasta."
            # corpus = ["A man is eating food.","A woman is playing violin."]
            # r = reranker.rerank(corpus, query)
            # logger.debug(r)
            # c = reranker.compress_documents(corpus, query)
            # logger.debug(c)

        except Exception as e:
            reranker = None
            logger.warning(f"{self.rerank_model_name}在线模型无法获取: {e}")
        return embed_model,embedding_model_8k,reranker



    @lru_cache
    def get_emb_8k_rerank_model(self,embedding_model_name=None, embedding_model_name_8k=None, rerank_model_name=None, device = ['cpu','cpu','cpu'],final_docs_num_reranked=4,api_mode:bool=True):
        if not (self.embed_model and self.embedding_model_8k and self.reranker):
            if api_mode:
                self.embed_model,self.embedding_model_8k,self.reranker = self._get_emb_8k_rerank_model_api()
            else:
                self.embed_model,self.embedding_model_8k,self.reranker = self._get_emb_8k_rerank_model(embedding_model_name=embedding_model_name, embedding_model_name_8k=embedding_model_name_8k, rerank_model_name=rerank_model_name,device = device,final_docs_num_reranked=final_docs_num_reranked)
        return self.embed_model,self.embedding_model_8k,self.reranker

    def get_es_connection(self):
        if not self.es_connection: 
            self.es_connection= Elasticsearch(
                self.ES_URL,
                # ca_certs=f"d:\JqkjKB\http_ca.crt",
                ssl_assert_fingerprint=self.CERT_FINGERPRINT,
                basic_auth=("elastic", self.ELASTIC_PASSWORD),
                request_timeout=600 #这个设置很重要  elastic_transport.ConnectionTimeout: Connection timed out
            )

            print(f'当前使用的Elasticsearch URL为:| { self.ES_URL } |')
            # print('-------Elasticsearch Connection详细信息-------')
            # print(self.es_connection.info())
            # print('-------Elasticsearch Connection详细信息-------')
            print('-------可以通过Kibana URL查看:| http://127.0.0.1:5601 | http://10.1.150.105:5601 |-------')
        return self.es_connection

    def create_es_index_if_not_existes_with_default_chinese_analyzer(self, es_connection=None,index_name:str=None):
        assert index_name, "参数index_name（ES的索引名称）不得为空！"
        if not es_connection:
            es_connection=self.get_es_connection()
        if not es_connection.indices.exists(index=index_name):
            try:
                es_connection.indices.create(index=index_name,settings=self.default_chinese_analyzer_settings)
            except Exception as e:
                logger.error(f'创建ES Index={index_name}失败，错误信息为:{e}')
        else:
            logger.info(f'ES Index={index_name}已经存在！') 
    
    
    def get_all_knowledge_base(self, es_connection=None,exclude_system_indices=True):
        if not es_connection:
            es_connection=self.get_es_connection()
        self.all_indices = es_connection.indices.get_alias(index="_all")
        if exclude_system_indices:
            self.all_indices = [index_name for index_name in self.all_indices if not index_name.startswith('.')]
        return self.all_indices
        
    def get_es_searchstore(self,embedding=None,es_connection=None,index_name='',strategy=None):
        assert index_name, "参数index_name（ES的索引名称）不得为空！"
        es_connection = es_connection if es_connection else self.get_es_connection()
        self.create_es_index_if_not_existes_with_default_chinese_analyzer(es_connection=es_connection,index_name=index_name)

        embedding = embedding if embedding else self.get_emb_8k_rerank_model()[0]        
        strategy = strategy if strategy else self.strategy           
        es_searchstore = ElasticsearchStore(es_connection=es_connection, index_name=index_name, embedding=embedding,strategy=strategy)
        return es_searchstore
    
  

    # 方式一，使用LangChain indexing API，防止重复插入
    # https://python.langchain.com/docs/modules/data_connection/indexing 

    def get_es_searchstore_index_documents(self,documents,embedding,index_name,es_connection=None,cleanup="incremental",clear_before_add_index=True,strategy=None,source_id_key="source"):
        assert index_name, "参数index_name（ES的索引名称）不得为空！"
        assert documents,  "参数documents（待索引的文档）不得为空！"
        if not es_connection:
            es_connection=self.get_es_connection()
        self.create_es_index_if_not_existes_with_default_chinese_analyzer(es_connection=es_connection,index_name=index_name)
        strategy = strategy if strategy else self.strategy
        es_searchstore = ElasticsearchStore(es_connection=es_connection, index_name=index_name, embedding=embedding,strategy=strategy)
        
        namespace = f"elasticsearch/{index_name}"
        record_manager = SQLRecordManager(namespace, db_url="sqlite:///record_manager_cache.sql")
        record_manager.create_schema()
        
        def _clear():
            """Hacky helper method to clear content. See the `full` mode section to to understand why it works."""        
            clear_result_report = index([], record_manager, es_searchstore, cleanup="full", source_id_key=source_id_key)
            logger.info(f'Clear_Result report of "index_documents_to_es_searchstore":{clear_result_report}')

        if clear_before_add_index:
            _clear()
        
        index_result_report=index(documents, record_manager, es_searchstore, cleanup=cleanup, source_id_key=source_id_key)
        logger.info(f'Index_Result report of "index_documents_to_es_searchstore":{index_result_report}')

        es_searchstore.client.indices.refresh(index=index_name)
        return es_searchstore

    # 方式二：常见的在教程中见到的
    def get_es_searchstore_from_documents(self,documents,embedding,index_name,es_connection=None,strategy=None):
        assert index_name, "参数index_name（ES的索引名称）不得为空！"
        assert documents,  "参数documents（待索引的文档）不得为空！"
        if not es_connection:
            es_connection=self.get_es_connection()
        self.create_es_index_if_not_existes_with_default_chinese_analyzer(es_connection=es_connection,index_name=index_name)       
        strategy = strategy if strategy else self.strategy
        es_searchstore = ElasticsearchStore.from_documents(documents=documents,embedding=embedding,es_connection=es_connection,index_name=index_name,strategy=strategy)
        es_searchstore.client.indices.refresh(index=index_name)
        es_searchstore.index_name=index_name
        return es_searchstore

    def split_and_get_chunks_relevant_from_documents(self,query:str, docs_list:List[Document]=None,text_splitter=None,embed_model=None,reranker=None,
                                                    if_reranking:bool=True,retriever_docs_num=10,final_docs_num=4,score_threshold=0.3,only_use_reranker:bool=True):
        
        docs_list_cleaned = []
        for doc in docs_list:
            doc.page_content = replace_multiple_newlines(doc.page_content)
            docs_list_cleaned.append(doc)
        if not text_splitter:
            text_splitter = self.text_splitter
        text_chunks = text_splitter.split_documents(docs_list_cleaned)
        
        reranker = reranker if reranker else self.reranker
        reranker.top_n = final_docs_num

        if only_use_reranker:            
            _chunks_relevant = reranker.compress_documents(text_chunks,query)
            # 只返回relevance_score>=score_threshold的
            chunks_relevant = [d for d in _chunks_relevant if d.metadata.get("relevance_score",0)>=score_threshold]
        
        else:
            embed_model  = embed_model if embed_model else self.embed_model        
            if if_reranking:
                retriever = FAISS.from_documents(text_chunks, embed_model, distance_strategy=DistanceStrategy.MAX_INNER_PRODUCT).as_retriever(search_type="mmr", search_kwargs={"score_threshold": score_threshold, "k": retriever_docs_num})
                compression_retriever = ContextualCompressionRetriever(base_compressor=reranker, base_retriever=retriever)
                chunks_relevant = compression_retriever.invoke(query)
            else:
                retriever_docs_num = final_docs_num
                retriever = FAISS.from_documents(text_chunks, embed_model, distance_strategy=DistanceStrategy.MAX_INNER_PRODUCT).as_retriever(search_type="mmr", search_kwargs={"score_threshold": score_threshold, "k": retriever_docs_num})
                chunks_relevant = retriever.invoke(query)
        return chunks_relevant

    # https://github.com/langchain-ai/langgraph/blob/main/examples/managing-conversation-history.ipynb
    def filter_and_get_messages_relevant_to_query(self,query:str,messages_list:List[BaseMessage],reserve_last_n_unique_messages = 6,reserve_message_types:tuple=(HumanMessage,AIMessage),text_splitter=None,embed_model=None,reranker=None,
                                                    if_reranking:bool=True,retriever_docs_num=10,final_docs_num=6 ,score_threshold=0.5, only_use_reranker=True):
        if not messages_list:
            return []
        
        unique_messages_list = []
        messages_content_set = set()
        messages_list.reverse()
        for message in messages_list:
            if isinstance(message,reserve_message_types):                     # 只保留HumanMessage,AIMessage
                if message.content:                                              # 确保message.content不为空
                    if message.content not in  messages_content_set:
                        unique_messages_list.append(message)
                        messages_content_set.add(message.content)        
        unique_messages_list.reverse() 
        messages_list.reverse() # 前面messages_list顺序翻转了，所以这里还要翻转回来
        
        if len(unique_messages_list) > reserve_last_n_unique_messages:

            embed_model  = embed_model if embed_model else self.embed_model
            reranker  = reranker if reranker else self.reranker
            text_splitter  = text_splitter if text_splitter else self.text_splitter 

            docs_from_messages = [Document(page_content=message.content,metadata={"message_index":message_index}) for message_index, message in enumerate(unique_messages_list)]
            chunks_relevant = self.split_and_get_chunks_relevant_from_documents(query, docs_from_messages,text_splitter=text_splitter,reranker=reranker,
                                                                        if_reranking=if_reranking,retriever_docs_num=retriever_docs_num, final_docs_num=final_docs_num,score_threshold=score_threshold,only_use_reranker=only_use_reranker)

            if not chunks_relevant:
                if reserve_last_n_unique_messages>0:
                    last_n_unique_messages = unique_messages_list[-reserve_last_n_unique_messages:]
                    return last_n_unique_messages

            sorted_chunks_relevant = sorted(chunks_relevant, key=lambda x: (x.metadata['message_index'], x.metadata['start_index']))
            
            messages_relevant = []            
            for chunk_relevant in sorted_chunks_relevant:
                index = chunk_relevant.metadata['message_index']
                # unique_messages_list[index].content = chunk_relevant.page_content #不能改变内容（即不能使用分块后的内容，否则可能无法获取完整的答案）
                message_relevant = unique_messages_list[index]
                if message_relevant not in messages_relevant:                               
                    messages_relevant.append(message_relevant)
                    # logger.info("--------------------------------") 
                    # relevance_score = chunk_relevant.metadata.get('relevance_score',None)
                    # message_relevant.pretty_print()
                    # logger.info(f"^^^^^^^^^上条Message的{relevance_score=}^^^^^^^^^")                
                
                logger.info(f"++++++++++++++++【根据相关性过滤后保留的[{len(messages_relevant)}]条 + 最近的last_n_unique_messages[{reserve_last_n_unique_messages}]条】消息++++++++++++++++")
                if reserve_last_n_unique_messages>0:
                    last_n_unique_messages = unique_messages_list[-reserve_last_n_unique_messages:]
                    for last_message in last_n_unique_messages:
                        last_message_content = last_message.content
                        # 防止之前的消息内容与当前消息内容一致,且要保证先后顺序，留下的确实是最近的
                        messages_relevant = [m for m in messages_relevant if m.content!=last_message_content]
                        messages_relevant.append(last_message)                        
                logger.info(f"++++++++++++++++【根据相关性过滤后保留的[{len(messages_relevant)}]条 + 最近的last_n_unique_messages[{reserve_last_n_unique_messages}]条合并后，保留了[{len(messages_relevant)}]条】消息++++++++++++++++")
                
                logger.info(f"================【为保留后的HumanMassage查询增加对应的AIMessage消息】：当前消息数[{len(messages_relevant)}]条================")
                final_messages_relevant = []                                
                for message in messages_relevant:
                    if message not in final_messages_relevant:
                        final_messages_relevant.append(message)
                    if isinstance(message,HumanMessage):
                        try:
                            question_id = message.additional_kwargs.get("question_id","")
                        except:            
                            question_id = ""
                        
                        if question_id:
                            m0_index = messages_list.index(message)
                            _messages_list  = messages_list[m0_index:]
                            for m in _messages_list:
                                if isinstance(m,AIMessage):
                                    try:
                                        ai_message_id = m.additional_kwargs.get("question_id","")
                                        if ai_message_id == question_id:
                                            final_messages_relevant.append(m)
                                            break
                                    except:
                                        continue
                logger.info(f"================【为保留后的HumanMassage查询增加对应的AIMessage消息】，增加后消息数[{len(final_messages_relevant)}]条================")
                
                logger.info(f"****************【无论如何，增加保留最后1条消息】，当前消息数[{len(final_messages_relevant)}]条****************")
                last_message_of_messages_list = messages_list[-1]
                if last_message_of_messages_list not in final_messages_relevant:
                    final_messages_relevant.append(last_message_of_messages_list)
                else:
                    logger.info(f"****************【最后1条消息已经存在】****************")
                logger.info(f"****************【无论如何，增加保留最后1条消息】，增加后消息数[{len(final_messages_relevant)}]条****************")
                return final_messages_relevant

        else:
            return unique_messages_list

@lru_cache
def get_env_models_instance():
    _env_models_instance = InitEnvModels()
    return _env_models_instance

env_models_instance = get_env_models_instance()

# region 留着备用
# Visualized-BGE： https://github.com/FlagOpen/FlagEmbedding/tree/master/FlagEmbedding/visual 

# class BgeRerank(BaseDocumentCompressor):
#     """Document compressor that uses `BAAI/bge-reranker`."""

#     model_name:str = "BAAI/bge-reranker-large"
#     """Model name to use for reranking."""
#     top_n: int = 10
#     """Number of documents to return."""
#     model:CrossEncoder = CrossEncoder(model_name)
#     """CrossEncoder instance to use for reranking."""

#     def bge_rerank(self,query,docs):

#         model_inputs =  [[query, doc] for doc in docs]
#         scores = self.model.predict(model_inputs)
#         results = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)

#         return results[:self.top_n]


#     class Config:
#         """Configuration for this pydantic object."""

#         extra = Extra.forbid
#         arbitrary_types_allowed = True

#     def compress_documents(
#         self,
#         documents: Sequence[Document],
#         query: str,
#         callbacks: Optional[Callbacks] = None,
#     ) -> Sequence[Document]:
#         """
#         Compress documents using `BAAI/bge-reranker`.

#         Args:
#             documents: A sequence of documents to compress.
#             query: The query to use for compressing the documents.
#             callbacks: Callbacks to run during the compression process.

#         Returns:
#             A sequence of compressed documents.
#         """
#         if len(documents) == 0:  # to avoid empty api call
#             return []
#         doc_list = list(documents)
#         _docs = [d.page_content for d in doc_list]
#         results = self.bge_rerank(query, _docs)
#         final_results = []
#         for r in results:
#             doc = doc_list[r[0]]
#             doc.metadata["relevance_score"] = r[1]
#             final_results.append(doc)
#         return final_results
# endregion 留着备用
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

    from langchain_core.tools import tool
    from langchain.tools.render import render_text_description # to describe tools as a string 
    @tool
    def accept(reason) -> int:
        "Accept a reason and return 1."
        logger.info(f"Accepting reason: {reason}")
        return 1


    @tool
    def reject(reason) -> int:
        "Reject a reason and return 0."
        logger.info(f"Rejecting reason: {reason}")
        return 0

    tools = [accept,reject]
    toos_dict = {tool.name:tool for tool in tools}
    rendered_tools = render_text_description(tools)
    # llm = env_models_instance.get_ollama_chat_model(tools=tools)
    llm = env_models_instance.get_langchain_chat_model().bind_tools(tools)
    print("==========="*10)
    system_prompt = f"""You are an assistant that has access to functions.
        ONLY Use them:

        {rendered_tools}


        Given the user input, return the name and input of the tool to use.
        Return your response as a JSON blob with 'name' and 'arguments' keys.
        The value associated with the 'arguments' key should be a dictionary of parameters."""
    print("==========="*10)

    prompt = "1+1=2"

    import json
    import json_repair

    def LLM(prompt, system_message, model=llm):
        try:
            messages=[{"role": "system", "content": system_message}, {"role": "user", "content": prompt}]
            response = model.invoke(messages)
            print('Success:\n', response)
            
            if not response.tool_calls:
                try:
                    parsed_tool_calls=[json_repair.loads(response.content)]
                    for tool in parsed_tool_calls:
                        tool_name = tool['name']
                        tool_args = tool['arguments']['reason']
                        res = toos_dict[tool_name](tool_args)
                        print(f"Result:调用了工具:{tool_name}，调用参数为:{tool_args},运行结果为:{res}")
                        return res
                except:
                    return "no valid tool call"


            if response.tool_calls:
                for tool in response.tool_calls:
                    tool_name = tool['name']
                    tool_args = tool['args']['reason']
                    res = toos_dict[tool_name](tool_args)
                    print(f"Result:调用了工具:{tool_name}，调用参数为:{tool_args},运行结果为:{res}")
                    return res
        except Exception as error:
            print('Error:', error)
            raise
    prompt = '使用python可以计算出3*10的正确结果，请思考这句话正确吗？并请给出理由'
    prompt = "Statement:Using Python can calculate out 3*10's correct result. Should you accept or reject the statement? and give me your reason"
    prompt = "Using Python can calculate out 3*10's correct result."
    prompt = "1+1=2"
    res = LLM(prompt,system_prompt)
    print(res)


    sentense= ["张结魁是谁？","张结魁是安徽晶奇公司的",
               "create a compression retriever, we need a base retriever first",
               "As shown in the summary table above, the number of lexical units has increased by 16% to more than 11,800, while the numbers of frames and FEs have increased by 25% to 1,019 and 8,884 respectively. Some frames are marked as “non-lexical”, meaning that we have created them because they are logically necessary in the frame hierarchy,"]
    docs = [Document(page_content=s) for s in sentense]
    chunks = env_models_instance.split_and_get_chunks_relevant_from_documents(docs_list=docs,query='张结魁')
    print(chunks)

    from langchain_core.messages import HumanMessage,SystemMessage
    es_connection = env_models_instance.get_es_connection()
    es_searchstore = env_models_instance.get_es_searchstore()

    knowledge_base_list = env_models_instance.get_all_knowledge_base(es_connection) 
    print(knowledge_base_list)   

    open_ai = env_models_instance.get_openai()
    openai_client = env_models_instance.get_openai_client()
    langchain_chat_model = env_models_instance.get_langchain_chat_model()
    embed_model,embedding_model_8k,reranker = env_models_instance.get_emb_8k_rerank_model()
    res = langchain_chat_model.invoke([SystemMessage('请使用中文回答我！'), HumanMessage('你好')])
    # print(res)

    ### Build An Index
    # index_name='test_doc_tree_reader'
    # urls = [
    #     "https://www.gov.cn/zhengce/content/202406/content_6955904.htm",
    #     # "https://www.gov.cn/zhengce/2023-03/23/content_5748063.htm",
    #     # "https://www.gov.cn/zhengce/zhengceku/202305/content_6883704.htm",
    #     # "https://new.qq.com/rain/a/20220916A0213800",
    #     # "https://www.gov.cn/zhengce/content/2022-05/20/content_5691424.htm",
    #     # "https://www.cn-healthcare.com/articlewm/20220211/content-1313937.html",
    #     # "https://www3.weforum.org/docs/WEF_Global_Health_and_Healthcare_Strategic_Outlook_2023_CN.pdf",
    #     # "https://www2.deloitte.com/content/dam/Deloitte/cn/Documents/life-sciences-health-care/deloitte-cn-lshc-2023-global-health-care-outlook-zh-230316.pdf",
    #     # "https://www2.deloitte.com/content/dam/Deloitte/cn/Documents/life-sciences-health-care/cn-lshc-china-lshc-industry-survey-2024-zh-240314.pdf",
    #     # "https://www.gov.cn/zhengce/2012-12/26/content_2618554.htm"
    # ]

    # knowledge_base_list = env_models_instance.get_all_knowledge_base(es_connection) 
    # print(f"插入{index_name}前的{knowledge_base_list=}")
    # if es_connection.indices.exists(index=index_name):
    #     print(f"已存在index='{index_name}'！跳过插入索引的环节。")
    # else:
    #     docs = [WebBaseLoader(url).load() for url in urls]
    #     docs_list = [item for sublist in docs for item in sublist]
    #     docs_list_cleaned = []
    #     for doc in docs_list:
    #         doc.page_content = replace_multiple_newlines(doc.page_content)
    #         docs_list_cleaned.append(doc)

    #     # Split
    #     text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    #         chunk_size=512, chunk_overlap=0
    #     )
    #     doc_splits = text_splitter.split_documents(docs_list_cleaned)

    #     # Add to vectorstore
    #     vectorstore = env_models_instance.get_es_searchstore_index_documents(documents=doc_splits, es_connection=es_connection,embedding=embed_model,index_name=index_name)
    #     print(f"插入{index_name}后的{knowledge_base_list=}")


    '''
docker run --shm-size=64g --name xinference103 -d -p 9997:9997 -e XINFERENCE_MODEL_SRC=modelscope -v /home/jqsoft/.xinference:/root/.xinference -v /home/jqsoft/.cache/huggingface:/root/.cache/huggingface -v /home/jqsoft/.cache/modelscope:/root/.cache/modelscope --gpus all xprobe/xinference:latest xinference-local -H 0.0.0.0 --log-level debug

docker run --shm-size=64g --name xinferencenightly -d -p 9997:9997 -e XINFERENCE_MODEL_SRC=modelscope -v /home/jqsoft/.xinference:/root/.xinference -v /home/jqsoft/.cache/huggingface:/root/.cache/huggingface -v /home/jqsoft/.cache/modelscope:/root/.cache/modelscope --gpus all xprobe/xinference:nightly-main xinference-local -H 0.0.0.0 --log-level debug


    '''

