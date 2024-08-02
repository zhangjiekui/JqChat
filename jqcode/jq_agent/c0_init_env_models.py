
import os
import re
import threading
import pathlib
from functools import lru_cache
from typing import Annotated, List, TypedDict, Optional, Sequence
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
from dotenv import load_dotenv, find_dotenv

from jqcode.jq_utils.logger import jqkj_logger
logger = jqkj_logger(__file__).get_logger()


os.environ['LANGCHAIN_TRACING_V2'] = 'true'
os.environ['LANGCHAIN_ENDPOINT'] = 'https://api.smith.langchain.com'
os.environ['LANGCHAIN_API_KEY'] = "ls__fe150087fa0643f28b3eae3a07d57529"
os.environ['TAVILY_API_KEY'] = "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"

def replace_multiple_newlines(text):
    return re.sub(r'\n+', '\n', text)

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
        self.env_loaded = False
        # loade envs:
        self.load_project_env()
        self.base_url=os.getenv("OPENAI_API_BASE",'http://10.1.150.105:4000/v1')
        self.ollama_host = os.getenv("OLLAMA_HOST",'http://localhost:11434')
        self.api_key =os.getenv("OPENAI_API_KEY",'NotNeeded')
        self.api_type =os.getenv("OPENAI_API_TYPE",'open_ai')
        self.llm_model_name = os.getenv("LLM_MODEL_NAME",'qwen2-instruct')
        self.embedding_model_name = os.getenv("EMBEDDING_MODEL_NAME",'maidalun1020/bce-embedding-base_v1')
        self.embedding_model_name_8k = os.getenv("EMBEDDING_MODEL_8k",'jinaai/jina-embeddings-v2-base-zh') # max_tokes =8192
        self.rerank_model_name = os.getenv("RERANK_MODEL_NAME",'maidalun1020/bce-reranker-base_v1') #supports long passages (more than 512 tokens, less than 32k tokens) reranking
        self.ELASTIC_PASSWORD = os.getenv("ELASTIC_PASSWORD")
        self.CERT_FINGERPRINT = os.getenv("CERT_FINGERPRINT")
        self.ES_URL = os.getenv("ES_URL","https://localhost:9200")

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
        self.strategy = ElasticsearchStore.ApproxRetrievalStrategy(hybrid=False) 


    def load_project_env(self):
        if not self.env_loaded: 
            print('\n\n')
            print('=*'*20)
            env_dir = find_dotenv()
            print(f"项目.env文件路径：{env_dir}")
            # root_dir = pathlib.Path(__file__).resolve().parent.parent.parent
            # env_dir = root_dir/'.env'
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
            self.openai_client = OpenAI(base_url=self.base_url,api_key=self.api_key)
            print(f'当前使用的模型base_url为:OpenAI, {self.openai_client.base_url}')
        return self.openai_client


    def get_langchain_chat_model(self, temperature=0.0, max_tokens=2000, streaming=True):
        if not self.chat_model or temperature!=self.chat_model.temperature or max_tokens!=self.chat_model.max_tokens or streaming!=self.chat_model.streaming:
            self.chat_model = ChatOpenAI(
                model_name=self.llm_model_name,
                openai_api_base=self.base_url,    
                openai_api_key= self.api_key,
                streaming=True,
                verbose=True,
                temperature=temperature,
                max_tokens=max_tokens
            )
        print(f'当前使用的模型为:Langchain ChatOpenAI, {self.chat_model.model_name}, API_URL为{self.chat_model.openai_api_base}')
        return self.chat_model
    # model_name = "llama3-groq-tool-use:8b-q8_0"
    # model_name = "adrienbrault/gorilla-openfunctions-v2:Q6_K"
    # model_name = "allenporter/xlam:7b"
    model_name = "mistral-large:latest"
    
    def get_ollama_chat_model(self,model_name = model_name,temperature=0.5,top_p=0.65, tools:list = None,verbose=True):
        ollama_chat_model = ChatOllama(model=model_name,temperature=temperature,top_p=top_p,verbose=verbose)
        print("-------ollama_chat_model详细信息-------")
        print(f'       ==Get ollama_chat_model successfully. model_name={model_name}, ollama_host = {self.ollama_host}')
        print("-------ollama_chat_model详细信息-------")
        if tools:
            return ollama_chat_model.bind_tools(tools)        
        return ollama_chat_model
    
   
    # todo: embedding_model_8k with langchain

    def _get_emb_8k_rerank_model(self,embedding_model_name=None, embedding_model_name_8k=None, rerank_model_name=None, device = ['cpu','cpu','cpu'],final_docs_num_reranked=4): #device = ['cuda:1','cuda:2''cuda:3']
        if embedding_model_name:
            self.embedding_model_name = embedding_model_name            
        if 'bge' in self.embedding_model_name: 
            # 有query_instruction https://github.com/langchain-ai/langchain/blob/ee94ef55ee6ab064da08340817955f821dfa6261/libs/langchain/langchain/embeddings/huggingface.py#L187
            from langchain_community.embeddings import HuggingFaceBgeEmbeddings as HuggingFaceEmbeddings
        else:
            # from langchain_community.embeddings import HuggingFaceEmbeddings
            from langchain_huggingface import HuggingFaceEmbeddings
        embedding_model_kwargs = {'device': device[0]}
        embedding_encode_kwargs = {'batch_size': 32, 'normalize_embeddings': True}
        embed_model = HuggingFaceEmbeddings(
            model_name=self.embedding_model_name,
            model_kwargs=embedding_model_kwargs,
            encode_kwargs=embedding_encode_kwargs,
        )
        # emb = embed_model.embed_query("初始化成功！")
        # print(emb)
        print(f'{self.embedding_model_name=}初始化成功！维度为768')

        if embedding_model_name_8k:
            self.embedding_model_name_8k = embedding_model_name_8k
        embedding_model_8k = SentenceTransformer(self.embedding_model_name_8k, trust_remote_code=True, device=device[2])
        embedding_model_8k.max_seq_length = 8192
        print(f'{embedding_model_name_8k=}初始化成功！{embedding_model_8k.max_seq_length=}，可根据实际需要进行修改。')

        if rerank_model_name:
            self.rerank_model_name = rerank_model_name
        reranker_args = {'model': self.rerank_model_name, 'top_n': final_docs_num_reranked, 'device': device[1]}
        reranker = BCERerank(**reranker_args)
        print(f'{rerank_model_name=}初始化成功！')
        return embed_model,embedding_model_8k,reranker

    @lru_cache
    def get_emb_8k_rerank_model(self,embedding_model_name=None, embedding_model_name_8k=None, rerank_model_name=None, device = ['cpu','cpu','cpu'],final_docs_num_reranked=4):
        if not (self.embed_model and self.embedding_model_8k and self.reranker):
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

            print(f'当前使用的Elasticsearch URL为| { self.ES_URL } |,详细信息如下:')
            print('-------Elasticsearch Connection详细信息-------')
            print(self.es_connection.info())
            print('-------Elasticsearch Connection详细信息-------')
            print('-------可以通过Kibana URL查看:| http://127.0.0.1:5601 | http://10.1.150.105:5601 |-------')
        return self.es_connection

    def get_all_knowledge_base(self, es_connection=None,exclude_system_indices=True):
        if not es_connection:
            es_connection=self.get_es_connection()
        self.all_indices = es_connection.indices.get_alias(index="*")
        if exclude_system_indices:
            self.all_indices = [index_name for index_name in self.all_indices if not index_name.startswith('.')]
        return self.all_indices
        
    def get_es_searchstore(self,embedding=None,es_connection=None,index_name='',strategy=None):
        embedding = embedding if embedding else self.get_emb_8k_rerank_model()[0]
        es_connection = es_connection if es_connection else self.get_es_connection()
        strategy = strategy if strategy else ElasticsearchStore.ApproxRetrievalStrategy(hybrid=False)
        index_name = index_name if index_name else 'test_doc_tree_reader'    
        es_searchstore = ElasticsearchStore(es_connection=es_connection, index_name=index_name, embedding=embedding,strategy=strategy)
        return es_searchstore


    # 方式一，使用LangChain indexing API，防止重复插入
    # https://python.langchain.com/docs/modules/data_connection/indexing 

    def get_es_searchstore_index_documents(self,documents,embedding,index_name,es_connection=None,cleanup="incremental",clear_before_add_index=True,strategy=None,source_id_key="source"):
        if not es_connection:
            es_connection=self.get_es_connection()

        strategy = strategy if strategy else self.strategy
        es_searchstore = ElasticsearchStore(es_connection=es_connection, index_name=index_name, embedding=embedding,strategy=strategy)
        namespace = f"elasticsearch/{index_name}"
        record_manager = SQLRecordManager(namespace, db_url="sqlite:///record_manager_cache.sql")
        record_manager.create_schema()
        
        def _clear():
            """Hacky helper method to clear content. See the `full` mode section to to understand why it works."""
        clear_result_report = index([], record_manager, es_searchstore, cleanup="full", source_id_key=source_id_key)
        print(f'Clear_Result report of "index_documents_to_es_searchstore":{clear_result_report}')

        if clear_before_add_index:
            _clear()
        es_searchstore.index_name=index_name
        index_result_report=index(documents, record_manager, es_searchstore, cleanup=cleanup, source_id_key=source_id_key)
        print(f'Index_Result report of "index_documents_to_es_searchstore":{index_result_report}')

        es_searchstore.client.indices.refresh(index=index_name)
        return es_searchstore

    # 方式二：常见的在教程中见到的
    def get_es_searchstore_from_documents(self,documents,embedding,index_name,es_connection=None,strategy=None):
        if not es_connection:
            es_connection=self.get_es_connection()
        
        strategy = strategy if strategy else self.strategy
        es_searchstore = ElasticsearchStore.from_documents(documents=documents,embedding=embedding,es_connection=es_connection,index_name=index_name,strategy=strategy)
        es_searchstore.client.indices.refresh(index=index_name)
        es_searchstore.index_name=index_name
        return es_searchstore

    def split_and_get_chunks_relevant_from_documents(self,query:str, docs_list:List[Document]=None,text_splitter=None,embed_model=None,reranker=None,
                                                    if_reranking:bool=True,retriever_docs_num=10,final_docs_num=4,score_threshold=0.3):
        
        
        embed_model  = embed_model if embed_model else self.embed_model
        reranker  = reranker if reranker else self.reranker
        docs_list_cleaned = []
        for doc in docs_list:
            doc.page_content = replace_multiple_newlines(doc.page_content)
            docs_list_cleaned.append(doc)
        if not text_splitter:
            from jqcode.jq_splitters.backend_splitter_utils.jq_chinese_recursive_text_splitter import JqChineseRecursiveTextSplitter
            text_splitter = JqChineseRecursiveTextSplitter(chunk_size=500,chunk_overlap=0.2,model_name=embed_model)
        
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
    def filter_and_get_messages_relevant_to_query(self,query:str,messages_list:List[BaseMessage],text_splitter=None,embed_model=None,reranker=None,
                                                    if_reranking:bool=True,retriever_docs_num=10,final_docs_num=6 ,score_threshold=0.3,reserve_last_n_messages = 6):
        if len(messages_list) > reserve_last_n_messages:
            embed_model  = embed_model if embed_model else self.embed_model
            reranker  = reranker if reranker else self.reranker
            unique_messages_list = []
            messages_content_set = set()
            messages_list.reverse()
            for message in messages_list[reserve_last_n_messages:]:
                if message.content not in  messages_content_set:
                    unique_messages_list.append(message)
                    messages_content_set.add(message.content)
            unique_messages_list.reverse()    
            docs_from_messages = [Document(page_content=message.content,metadata={"message_index":message_index}) for message_index, message in enumerate(unique_messages_list)]
            if not text_splitter:
                from jqcode.jq_splitters.backend_splitter_utils.jq_chinese_recursive_text_splitter import JqChineseRecursiveTextSplitter
                text_splitter = JqChineseRecursiveTextSplitter(chunk_size=500,chunk_overlap=0.2,model_name=embed_model)

            chunks_relevant = self.split_and_get_chunks_relevant_from_documents(query, docs_from_messages,text_splitter=text_splitter,reranker=reranker,
                                                                        if_reranking=if_reranking,retriever_docs_num=retriever_docs_num, final_docs_num=final_docs_num,score_threshold=score_threshold)

            sorted_chunks_relevant = sorted(chunks_relevant, key=lambda x: (x.metadata['message_index'], x.metadata['start_index']))
            messages_relevant = []

            print(f"++++++++++++++++++++++++++++++++++++++++++++【过滤后保留的+最近的条{reserve_last_n_messages}】消息++++++++++++++++++++++++++++++++++++++++++++")   
            for chunk_relevant in sorted_chunks_relevant:
                index = chunk_relevant.metadata['message_index']
                # unique_messages_list[index].content = chunk_relevant.page_content #不能改变内容（即不能使用分块后的内容，否则可能无法获取完整的答案）
                message_relevant = unique_messages_list[index]
                if message_relevant not in messages_relevant:
                    relevance_score = chunk_relevant.metadata.get('relevance_score',None)
                    # print("--------------------------------")            
                    messages_relevant.append(message_relevant)
                    # message_relevant.pretty_print()
                    # print(f"^^^^^^^^^上条Message的{relevance_score=}^^^^^^^^^")
            print(f"++++++++++++++++++++++++++++++++++++++++++++【过滤后保留的+最近的条{reserve_last_n_messages}】消息++++++++++++++++++++++++++++++++++++++++++++")   
            messages_list.reverse() # 前面messages_list顺序翻转了，所以这里还要翻转回来
            last_n_messages = messages_list[-reserve_last_n_messages:]
            for last_message in last_n_messages:
                if  last_message not in messages_relevant:
                    messages_relevant.append(last_message)
            return messages_relevant
        else:
            return messages_list
        
env_models_instance = InitEnvModels()


# 留着备用
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
                parsed_tool_calls=[json_repair.loads(response.content)]
                for tool in parsed_tool_calls:
                    tool_name = tool['name']
                    tool_args = tool['arguments']['reason']
                    res = toos_dict[tool_name](tool_args)
                    print(f"Result:调用了工具:{tool_name}，调用参数为:{tool_args},运行结果为:{res}")
                    return res

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
    print(res)

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

