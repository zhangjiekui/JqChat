import warnings
warnings.filterwarnings("ignore")
warnings.filterwarnings('ignore',message='unstructured',append=True) 
warnings.filterwarnings('ignore',message='profiles',append=True) 
warnings.filterwarnings('ignore',message='datasets',module='datasets',append=True) 
warnings.filterwarnings('ignore',message='PyTorch',module='datasets',append=True) 

import os,sys,pathlib
import requests
import base64
import json
import random
os.environ['USER_AGENT'] = 'myagent'
import re
import threading
from pathlib import Path
from functools import lru_cache
from typing import Annotated, List, Iterable, TypedDict, Optional, Sequence,Literal, Any,Union,Tuple,Dict
from langchain.callbacks.manager import Callbacks
import langchain

langchain.verbose = False

from openai import OpenAI
from langchain_openai import ChatOpenAI

from sentence_transformers import SentenceTransformer
from elasticsearch import Elasticsearch
from langchain_core.documents import Document
from langchain_elasticsearch import ElasticsearchStore
# 以下4个Strategy均继承自RetrievalStrategy
    # """BM25Strategy： classic full-text search"""
    # """SparseVectorStrategy：using the `text_expansion` processor."""
    # """DenseVectorStrategy： using K-nearest-neighbors retrieval."""
    # """DenseVectorScriptScoreStrategy：Exact nearest neighbors retrieval using the `script_score` query."""
from elasticsearch.helpers.vectorstore import BM25Strategy,SparseVectorStrategy,DenseVectorStrategy,DenseVectorScriptScoreStrategy
from elasticsearch.helpers.vectorstore._utils import DistanceMetric
from langchain.indexes import SQLRecordManager, index
from langchain.retrievers.document_compressors.base import BaseDocumentCompressor
from langchain_core.messages import BaseMessage
from langchain_core.vectorstores import VectorStoreRetriever
from langchain.callbacks.manager import AsyncCallbackManagerForRetrieverRun,CallbackManagerForRetrieverRun
from langchain_community.vectorstores import FAISS
from langchain_community.vectorstores.utils import DistanceStrategy
from langchain.retrievers import ContextualCompressionRetriever
from langchain_core.messages import BaseMessage, HumanMessage,SystemMessage,ToolMessage,AIMessage
from langchain.callbacks.base import BaseCallbackHandler
from langchain_core.callbacks import StdOutCallbackHandler,FileCallbackHandler
from jqcode.jq_splitters.backend_splitter_utils.jq_chinese_recursive_text_splitter import JqChineseRecursiveTextSplitter
from jqcode.jq_readers.jqkj_readers import JqkjDocxReader
from jqcode.jq_splitters.jq_docx_tree_text_splitter import JqkjDocTreeTokenTextSplitter,load_project_env,JQ_TOKENIZER,JQ_TEXT_SPLITTER,JQ_DocTreeTokenTextSplitter
from transformers import AutoTokenizer
from pydantic import PrivateAttr
import json_repair
from langchain_core.utils.input import print_text
import multiprocessing
from concurrent.futures import ProcessPoolExecutor,ThreadPoolExecutor
from jqcode.jq_config.general_config import llm_handler_file_path,if_log_verbose,logfile_path
from jqcode.jq_utils.logger import jqkj_logger,set_multiprocessing_context,is_main_process
from langchain.globals import set_llm_cache
logger = jqkj_logger(__file__).get_logger()

set_multiprocessing_context(multiprocessing,context="spawn",logger=logger)

VERBOSE = if_log_verbose()
os.environ["NEO4J_URI"] = "bolt://10.1.150.105:7687"
os.environ["NEO4J_USERNAME"] = "neo4j"
os.environ["NEO4J_PASSWORD"] = "neo4jneo4j"
os.environ['LANGCHAIN_TRACING_V2'] = 'true'
os.environ['LANGCHAIN_ENDPOINT'] = 'https://api.smith.langchain.com'
os.environ['LANGCHAIN_API_KEY'] = "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"
os.environ['TAVILY_API_KEY'] = "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"
os.environ['LANGCHAIN_PROJECT']= 'JqChat'

def _add_scores_before_page_content(d:Document):
    d.page_content = f'[relevance_score_retriever={d.metadata.get("relevance_score_retriever",0)},relevance_score_reranker={d.metadata.get("relevance_score_reranker",0)}]{d.page_content}'

class Vlm_API:
    '''
    https://github.com/QwenLM/Qwen2.5-VL
    "Qwen/Qwen2.5-VL-7B-Instruct"
    '''
    def __init__(self,api_base:str = "http://10.1.150.105:8000/v1",api_key:str='abc123',model:str="qwenvl"):
        self.api_base = api_base
        self.api_key = api_key
        self.model=model
        self.client = OpenAI(api_key=api_key,base_url=api_base)
        self.default_prompt = "首先识别出有意义的区块，然后逐个区块完整识别并仅输出图中的文字（相当于ocr，去掉不必要的换行符，但保留必要的空格，使用‘||’分割文本块）。最后仅输出完整的文本，不要有任何额外的内容和解释。"
        # 请识别出发票中的购买方 名称（keyname:gmf）、销售方 名称（keyname:xsf）、销售项目名称 （keyname:item）、发票类型（keyname:type，取值为普通发票或专用发票）。以Json形式返回，使用括号中的keyname代替中文名称，不要有多余内容
    def __call__(self,image_path_or_base64:str,is_decoded_image_text:bool=False,query:str=None,only_return_text=True):
        ## 如果是图片地址，读取图片并转换为base64
        if not query:
            query = self.default_prompt
        if is_decoded_image_text:
            encoded_image_text = image_path_or_base64
        else:
            if isinstance(image_path_or_base64,str): 
                if os.path.isfile(image_path_or_base64):
                    with open(image_path_or_base64, 'rb') as f:
                        image_path_or_base64 = f.read()
                else:
                    raise Exception(f"{image_path_or_base64}文件不存在！")
            elif isinstance(image_path_or_base64, bytes):
                pass
            else:
                raise Exception(f"目前只接受str或bytes类型的参数，不支持：{type(image_path_or_base64)=}")               
            encoded_data = base64.b64encode(image_path_or_base64)
            encoded_image_text = encoded_data.decode('utf-8')
        base64_qwen = f"data:image;base64,{encoded_image_text}"

        try:
            chat_response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                            {"role": "system", "content": "You are a helpful assistant."},
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": base64_qwen
                                        },
                                    },
                                    {"type": "text", "text": query},
                                ],
                            },
                            ],
                        )  
            logger.info(f"Chat response:\n{chat_response}")
            if only_return_text:
                text = chat_response.choices[0].message.content
                text = text.replace('\n', ' ')
                return text
            else:
                return chat_response
             
        except Exception as e:
            logger.error(f"请求错误: {str(e)}")
            return ''

# vlm= Vlm_API()
# r1=vlm(image_path_or_base64="/data/projects/JqChatV2/JqChat/graph.jpg",
#        query='首先识别出有意义的区块，然后逐个区块完整识别并仅输出图中的文字（相当于ocr，但去掉不必要的换行符），不能遗漏，同一区块的文字内容放在一起。最后仅输出完整的纯文本内容，不要有任何额外的解释、格式等。',
#        only_return_text=False)     
# print(r1)
# print(r1.choices[0].message.content)


# r2 = vlm(image_path_or_base64='/data/projects/JqChatV2/JqChat/ocr.png')
# print(r2)




class Ocr_API:
    def __init__(self,server_url:str = "http://10.1.150.106:5566/api/ocr"):
        self.server_url = server_url
        self.vlm = Vlm_API()       
    
    def __call__(self,image_path_or_base64):
        ## 如果是图片地址，读取图片并转换为base64
        try:
            if isinstance(image_path_or_base64,Path):
                image_path_or_base64 = str(image_path_or_base64)
            if isinstance(image_path_or_base64,str): 
                if os.path.isfile(image_path_or_base64):
                    with open(image_path_or_base64, 'rb') as f:
                        image_path_or_base64 = f.read()
                else:
                    raise Exception(f"{image_path_or_base64}文件不存在！")
            elif isinstance(image_path_or_base64, bytes):
                pass
            else:
                raise Exception(f"目前只接受str、path或bytes类型的参数，不支持：{type(image_path_or_base64)=}")               
            encoded_data = base64.b64encode(image_path_or_base64)
            encoded_data_str = encoded_data.decode('utf-8')
        except Exception as e:
            logger.warning(f"{e}")
            return ""
        try:
            logger.warning(f"优先调用VLM模型来做图片OCR识别...")
            result = self.vlm(encoded_data_str,is_decoded_image_text=True)
            logger.warning("VLM识别结果:"+result)
            # raise Exception("故意抛出错误，以跳转测试OCR接口......")

        except Exception as e:
            logger.error(f"VLM接口请求错误: {str(e)}。下面尝试请求OCR接口......")            
            payload = {
                "imgString": encoded_data_str,
                "bStore": False
            }            
            # 发送POST请求
            headers = {'Content-Type': 'application/json'}
            response = requests.post(
                self.server_url,
                data=json.dumps(payload),
                headers=headers,
                timeout=60  # 设置超时时间
            )            
            # 检查响应状态
            response.raise_for_status()            
            result_json = response.json()
            result = result_json.get('data')[0].get('text','')        
            # 返回结果
            # logger.warning("OCR识别结果:"+result)            
        return result


# ocr_api= Ocr_API()
# image_path_or_base64="/data/projects/JqChatV2/JqChat/graph.jpg"
# r1=ocr_api(image_path_or_base64=image_path_or_base64) 
# print(r1)  

class Ocr_GOT_API:    
    def __init__(self,model_uid='GOT-OCR2_0',base_url:str = "http://10.1.150.106:9997",auth_headers={}):
        from xinference.client.restful.restful_client import RESTfulImageModelHandle
        self.ocr_got = RESTfulImageModelHandle(model_uid=model_uid,base_url=base_url,auth_headers=auth_headers)      
    
    def __call__(self,image_path_or_base64):
        ## 如果是图片地址，读取图片并转换为base64
        from diffusers.utils import load_image
        import io
        image = load_image(image_path_or_base64)
        bio = io.BytesIO()
        image.save(bio, format="JPEG")

        try:    
            result = self.ocr_got.ocr(bio.getvalue())       
            # 返回结果
            logger.debug("识别结果:"+result)
            return result
        except requests.exceptions.RequestException as e:
            logger.error(f"请求错误: {str(e)}")
            return ''
        except Exception as e:
            logger.error(f"其他错误: {str(e)}")
            return ''
def test_orc_got(Ocr_GOT_API):
    ocr_got = Ocr_GOT_API()
    img1='/data/projects/JqChatV2/JqChat/image.png'  
    img2="/data/projects/JqChatV2/JqChat/jqcode/jq_knowledge_manegement/data/knowledge_base/samples/content/llm/img/大模型推理优化策略-幕布图片-923924-83386.jpg"
    img3="/data/projects/JqChatV2/JqChat/ocr.png"
    img4='/data/projects/JqChatV2/JqChat/ocr2.jpg'
    results = []
    for img in [img1,img2,img3,img4]:
        res = ocr_got(img)
        results.append(res)
    print(results)

# test_orc_got(Ocr_GOT_API)
# pass

class JqVectorStoreRetrieverWithScore(VectorStoreRetriever):
    # See https://github.com/langchain-ai/langchain/blob/61dd92f8215daef3d9cf1734b0d1f8c70c1571c3/libs/langchain/langchain/vectorstores/base.py#L500
    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        instruction = 'Given the user query, retrieve the relevant passages that answer the query'
        embedding_model = "None"
        if self.name=="embedding":
            embedding_model = self.vectorstore.embedding.model
            # if "Qwen" in embedding_model:
            #     query = f'Instruct: {instruction}\nQuery:{query}'
        print(f"JqVectorStoreRetrieverWithScore:{self.name=},{embedding_model=},{query=}，下面执行文档检索......")
        docs_and_similarities = (
            self.vectorstore.similarity_search_with_relevance_scores(
                query, **self.search_kwargs
            )
        ) 
        # Make the score part of the document metadata        
        for doc, similarity in docs_and_similarities:
            doc.metadata[f"relevance_score_retriever_{self.name}"] = similarity
            # doc.page_content = f'[relevance_score_retriever={similarity:.2f}]{doc.page_content}'

        docs = [doc for doc, _ in docs_and_similarities]
        return docs
    
class JqXinferenceReranker(BaseDocumentCompressor):
    client: str = 'Xinference'
    top_n: int = 6
    """Number of documents to return."""
    model: Any=None
    """Xinference Rerank Model Instance to use for reranking."""
    _model: Any = PrivateAttr()
    class Config:
        """Configuration for this pydantic object."""
        extra = 'allow'
        arbitrary_types_allowed = True

    def __init__(
        self,
        top_n: int = 6,
        model:Any =None,
        threshold:float =0.2, #"""相关性阈值，低于此值的文档不返回."""
        **kwargs
    ):
        
        super().__init__(top_n=top_n, model=model,**kwargs)
        self._model = model
        self.threshold = threshold
    
    # https://github.com/xorbitsai/inference/blob/7d83300a7694a0262b634007ea4164ea753e466f/xinference/model/rerank/core.py
    def rerank(
        self,
        documents: List[str],
        query: str,
        top_n: Optional[int]= 6,        
        max_chunks_per_doc: Optional[int]=None,
        return_documents: Optional[bool]=True,
        return_len: Optional[bool]=True,
        normalize: Optional[bool]=True,
        **kwargs,
    ):
        top_n = top_n or self.top_n
        if not kwargs:
            kwargs = {"normalize":normalize}
        else:
            kwargs.update({"normalize":normalize})
        # return self._model.rerank(documents,query,top_n,max_chunks_per_doc,return_documents,return_len,**kwargs)
        if isinstance(query, list):
            logger.warning("query is not a string, only customed Qwen Reranker support List(query:str).please check your input")
            if "Qwen" not in self._model._model_uid:
                logger.warning("Not Qwen Reranker, only use the first query in the list:query = query[0]")
                query = query[0]
                assert isinstance(query, str), f"Not Qwen Reranker, assert query should be a string, but got {type(query)}"
        return self._model.rerank(documents,query,top_n,max_chunks_per_doc,return_documents,return_len)
    
    def compress_documents(
        self,
        documents: Union[Sequence[Document],Sequence[str]],
        query: str,        
        callbacks: Optional[Callbacks] = None,
        normalize: Optional[bool]=True,
        **kwargs
        
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
        
        if isinstance(query, list):            
            if "Qwen" not in self._model._model_uid:
                if len(query)>1:
                    logger.warning("query is not a string, only customed Qwen Reranker support List(query:str).please check your input")
                    logger.warning(f"Not Qwen Reranker, only use the first query in the list:query = query[0]，But got {len(query)=} queries")
                query = query[0]
                assert isinstance(query, str), f"Not Qwen Reranker, assert query should be a string, but got {type(query)}"        
        
        rerank_result = self._model.rerank(passages,query,top_n=self.top_n,return_documents=True,return_len=False,**kwargs)
        rerank_result_list = rerank_result["results"]
        final_results = []
        num_passages = len(passages)
        for result in rerank_result_list:
            score =  result.get('relevance_score',0) or result.get('score',0)
            if score>=self.threshold:
                doc_id = result['index']
                doc_id = doc_id % num_passages 
                text = None
                if result.get('query_document_pairs'):
                    text = result.get('query_document_pairs')[1]
                try:
                    doc = valid_doc_list[doc_id]
                except IndexError as e:
                    logger.warning(f"{doc_id}对应的文档不存在，请检查！")
                if  text:
                    if text not in doc.page_content:
                        pass
                    # assert text in doc.page_content, f"query={result.get('query_document_pairs')[0]},doc.page_content={doc.page_content}, text={text}, doc_id={doc_id}, num_passages={num_passages}, num_queries={num_queries}"
                doc.metadata.update({"relevance_score_reranker":score})
                # get retriever_score
                retriever_score_string=''
                retriever_score_keys=['relevance_score_retriever_embedding','relevance_score_retriever_bm25']
                for key in retriever_score_keys:
                    if  key in doc.metadata.keys():
                        retriever_score = doc.metadata.get(key,0)
                        retriever_score_string += f"{key}={retriever_score:.2f};"
                        # break                
                doc.page_content = f'[{retriever_score_string}relevance_score_reranker={score:.2f}]{doc.page_content}'
                final_results.append(doc)
       
        final_results = final_results[:self.top_n]
        return final_results

class JqCustomLlmHandler(BaseCallbackHandler):
    # print = logger.debug
    def on_chat_model_start(self,serialized, messages: List[List[BaseMessage]], *args, **kwargs):
        print(f"<<<<<<<<<<<<<<<<<<<<<<<<<模型输入：开始<<<<<<<<<<<<<<<<<<<<<<<<<")
        # print(f"Input Messages:")
        for ms in messages:
            for m in ms:
                m.pretty_print()
        print("<<<<<<<<<<<<<<<<<<<<<<<<<模型输入：结束<<<<<<<<<<<<<<<<<<<<<<<<<")
        print("\n    '↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓等待模型的输出↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓'    \n")

    def on_llm_end(self, response,*args, **kwargs):
        print(">>>>>>>>>>>>>>>>>>>>>>>>>模型输出：开始>>>>>>>>>>>>>>>>>>>>>>>>>")
        # print(f"Output Generations:")
        for g in response.generations:
            _g = g[0]
            content = f"content={_g.text}\ntool_calls={_g.message.tool_calls}"
            print(content)
        print(">>>>>>>>>>>>>>>>>>>>>>>>>模型输出：结束>>>>>>>>>>>>>>>>>>>>>>>>>")
        
class JqCustomLlmFileHandler(FileCallbackHandler):    
    
    def __init__(
        self, filename: str=llm_handler_file_path, mode: str = "w", color: Optional[str] = None
    ):
        super().__init__(filename=filename,mode=mode,color=color)
        
    def on_chat_model_start(self,serialized, messages: List[List[BaseMessage]], *args, **kwargs):
        print_text(f"<<<<<<<<<<<<<<<<<<<<<<<<<模型输入：开始<<<<<<<<<<<<<<<<<<<<<<<<<",end="\n",file=self.file,)
        # print_text(f"Input Messages:",end="\n",file=self.file,)
        for ms in messages:
            for m in ms:
                print_text(m.pretty_repr(),end="\n",file=self.file,)                
        print_text(f"<<<<<<<<<<<<<<<<<<<<<<<<<模型输入：结束<<<<<<<<<<<<<<<<<<<<<<<<<",end="\n",file=self.file,)
        print_text("\n    '↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓等待模型的输出↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓'    \n",end="\n",file=self.file)

    def on_llm_end(self, response,*args, **kwargs):
        print_text(">>>>>>>>>>>>>>>>>>>>>>>>>模型输出：开始>>>>>>>>>>>>>>>>>>>>>>>>>",end="\n",file=self.file,)
        # print_text(f"Output Generations:",end="\n",file=self.file,)
        for g in response.generations:
            _g = g[0]
            content = f"content={_g.text}\ntool_calls={_g.message.tool_calls}" 
            print_text(content,end="\n",file=self.file,)
        print_text(">>>>>>>>>>>>>>>>>>>>>>>>>模型输出：结束>>>>>>>>>>>>>>>>>>>>>>>>>",end="\n",file=self.file,)
        

def get_custom_handlers(vebose=VERBOSE):
    custom_handler = JqCustomLlmHandler()    
    file_handler = JqCustomLlmFileHandler(llm_handler_file_path)
    handlers = [custom_handler,file_handler] if vebose else [file_handler]
    return handlers
    # std_out_handler = StdOutCallbackHandler()
    # return [custom_handler,std_out_handler,file_handler]


def replace_multiple_newlines(text):
    return re.sub(r'\n+', '\n', text)

def clean_up_list_when_encounter_null_element(messages_a: list, messages_b: list | None) -> list:
    # todo 可以考虑在messages_b中加入一个控制消息：如ControlMassage(content="replace")，取出来后，直接返回 messages_b[0:-1]
    if messages_b:
        if not isinstance(messages_b,list):
            messages_b = [messages_b]        
       
        if not messages_a or messages_a == messages_b:
            return messages_b
        if messages_a in messages_b or messages_a[1:] in messages_b:
            return messages_b
        if messages_b in messages_a:
            return messages_a
        else:
            # messages_a = [el for el in messages_a if el not in messages_b]
            return messages_a + messages_b
    else:
        return []

class JqOnlineEmbeddingTokenizer():
    def __init__(self, embedding_model_name: str = "bce-embedding-base_v1", base_url:str="http://10.1.150.106:9997/v1", **kwargs):
        self.tokenizer_name = embedding_model_name
        self.base_url = base_url

    def convert_ids_to_tokens(
        self, input: Union[List, List[List]], **kwargs
    ) -> List[str]:
        """
        Convert token IDs to human readable tokens via RESTful APIs.

        Parameters
        ----------
        input: Union[List, List[List]]
            Input token IDs to convert, can be a single list of token IDs or a list of token ID lists.
            To convert multiple sequences in a single request, pass a list of token ID lists.

        Returns
        -------
        list
            A list of decoded tokens in human readable format.

        Raises
        ------
        RuntimeError
            Report the failure of token conversion and provide the error message.

        """
        url = f"{self._base_url}/v1/convert_ids_to_tokens"
        request_body = {
            "model": self._model_uid,
            "input": input,
        }
        request_body.update(kwargs)
        response = requests.post(url, json=request_body, headers=self.auth_headers)
        if response.status_code != 200:
            raise RuntimeError(
                f"Failed to decode token ids, detail: "
            )
        response_data = response.json()
        return response_data


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

        _default_api_key =os.getenv("OPENAI_API_KEY",'abc123')
        self.llm_model_api_key = self.llm_model_card.get('api_key',_default_api_key)
        self.llm_model_base_url= self.llm_model_card['base_url']
        self.llm_model_name = self.llm_model_card['name']
        self.llm_model_name = self.llm_model_card['name']
        self.llm_model_max_tokens = self.llm_model_card['max_tokens']
        self.llm_model_max_tokens = self.llm_model_card['max_tokens']
        self.llm_tokenize_url = self.llm_model_card.get('tokenize_url',"http://10.1.150.105:9998/tokenize")
        self.llm_detokenize_url = self.llm_model_card.get('detokenize_url',"http://10.1.150.105:9998/detokenize")
        self.llm_tokenize_api_key = self.llm_model_card.get('tokenize_api_key',_default_api_key)
        self.need_custom_tool_call_parse = self.llm_model_card.get('need_custom_tool_call_parse',True)
        self.need_json_mode = self.llm_model_card.get('need_json_mode',False)
        
        handlers = get_custom_handlers()
        invoke_llm_config = {'callbacks' : handlers}
        self.invoke_llm_config = invoke_llm_config

        self.base_url = self.llm_model_base_url # 如果是同一服务器上部署的大语言和Emb模型，可能会省略配置其他模型，直接用这个
        self.api_key = self.llm_model_api_key

        self.embedding_model_name = self.embedding_model_card['name']
        self.embedding_model_dimentions = self.embedding_model_card['dimensions']
        self.embedding_model_max_tokens = self.embedding_model_card['max_tokens']
        self.embedding_model_local = self.embedding_model_card['local']
        self.embedding_model_online = self.embedding_model_card['online']
        self.embedding_model_base_url = self.embedding_model_card.get('base_url',None) or self.base_url
        self.embedding_tokenize_url = self.embedding_model_card.get('tokenize_url',"http://10.1.150.106:9998/tokenize")
        self.embedding_detokenize_url = self.embedding_model_card.get('detokenize_url',"http://10.1.150.106:9998/detokenize")
        self.embedding_tokenize_api_key = self.embedding_model_card.get('tokenize_api_key',_default_api_key)
        self.reduce_emb_dimensions = self.embedding_model_card.get('reduce_emb_dimensions',False)
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
        
        
        self._tokenizer = JQ_TOKENIZER        
        self.jq_text_splitter = JQ_TEXT_SPLITTER
        self.jq_doctree_spiltter = JQ_DocTreeTokenTextSplitter
        self.jq_docx_reader = JqkjDocxReader()
        self.jq_logger = logger
        # code_splitter = self.text_splitter.from_language(language=Language.PYTHON,tokenizer=self._tokenizer)
        try:
            text = "中华人民共和国抗日胜利80周年93大阅兵"
            r1 = self._tokenizer.encode(text)
            r2 = self._tokenizer.decode(r1)
            r3 = self.jq_text_splitter.split_text(text)
            r4 = self.jq_doctree_spiltter.split_text(text)            
        except Exception as e:
            logger.error(f"加载tokenizer/spiltter失败：{str(e)}")
        # r = self._tokenizer.encode("中华人民共和国")
        
        self.ELASTIC_PASSWORD = os.getenv("ELASTIC_PASSWORD")
        self.CERT_FINGERPRINT = os.getenv("CERT_FINGERPRINT")
        self.ES_URL = os.getenv("ES_URL","https://localhost:9200")
        
        
        self.POSTGRES_USER = os.getenv("POSTGRES_USER")
        self.POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
        self.POSTGRES_HOST = os.getenv("POSTGRES_HOST")
        self.POSTGRES_PORT = os.getenv("POSTGRES_PORT")
        self.POSTGRES_DBNAME = os.getenv("POSTGRES_DBNAME")
        # postgres_conn2 = "postgresql+psycopg2://scott:tiger@localhost/test"
        # postgres_conn3 = "postgresql://langchain:langchain@10.1.150.105:7000/postgres?sslmode=disable"
        self.postgres_conn_psycopg1 = f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DBNAME}"
        self.postgres_conn_psycopg2 = f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DBNAME}"
        self.postgres_conn_psycopg3 = f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DBNAME}"
        self.postgres_conn_conf_dict={"database": self.POSTGRES_DBNAME,"user":self.POSTGRES_USER,"password": self.POSTGRES_PASSWORD,"host": self.POSTGRES_HOST,"port":self.POSTGRES_PORT}
         
        try:
            # https://python.langchain.com/docs/integrations/llm_caching/
            from langchain_community.cache import SQLAlchemyCache
            from jqcode.jq_agent.c0_zh_fulltext_sql_alchemy_cache import ZhFulltextLLMCache
            from sqlalchemy import create_engine
            engine = create_engine(self.postgres_conn_psycopg3)
            # engine2 = create_engine(self.postgres_conn_psycopg2)
            set_llm_cache(SQLAlchemyCache(engine,ZhFulltextLLMCache))
            # Cache位置：Schemas - public - Tables - llm_cache_fulltext
            if is_main_process():
                logger.warning(f"设置全局的Postgresql lm_cache成功！")
        except Exception as e:
            logger.error(f"设置全局的Postgresql lm_cache失败:{e}")
            try:
                from langchain.cache import SQLiteCache
                set_llm_cache(SQLiteCache(database_path=".langchain_llm_cache.db"))
                if is_main_process():
                    logger.warning(f"设置全局的SQLiteCache lm_cache成功！")
            except Exception as e:
                logger.error(f"设置全局的lm_cache（Postgresql及SQLiteCache）都失败:{e}")

        

        self.NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD","neo4jneo4j")
        self.NEO4J_USERNAME = os.getenv("NEO4J_USERNAME","neo4j")
        self.NEO4J_URI = os.getenv("NEO4J_URI","bolt://10.1.150.105:7687")
        USING_GRAPH_RAG_STR= os.getenv("USING_GRAPH_RAG","false")
        if USING_GRAPH_RAG_STR.lower()=='true':
            self.USING_GRAPH_RAG = True
        else:
            self.USING_GRAPH_RAG = False


        ES_DEFAULT_CHINESE_SETTINGS = os.getenv("ES_DEFAULT_CHINESE_SETTINGS",'') 
        ES_DEFAULT_CHINESE_SETTINGS = json_repair.loads(ES_DEFAULT_CHINESE_SETTINGS)
        self.ES_DEFAULT_CHINESE_SETTINGS = ES_DEFAULT_CHINESE_SETTINGS if len(ES_DEFAULT_CHINESE_SETTINGS)>0 else {"index": {"analysis.analyzer.default.type": "ik_max_word","analysis.search_analyzer.default.type": "ik_smart"}}
        assert self.ES_DEFAULT_CHINESE_SETTINGS, f"ES_DEFAULT_CHINESE_SETTINGS不能为空：{self.ES_DEFAULT_CHINESE_SETTINGS=}"

        KERNEL_API_BASE = os.getenv("KERNEL_API_BASE",'http://localhost')
        API_PORT = os.getenv("API_PORT",5011)
        self.kernel_api_url = f"{KERNEL_API_BASE}:{API_PORT}/api"
        
        root_dir = pathlib.Path().resolve().parent        
        workspace = os.getenv("workspace","/data/projects/JqChatV2/workspace")
        if workspace.startswith('/'):
            rel_workspace = os.path.basename(workspace)           
            abs_workspace = workspace
        else:
            rel_workspace = workspace
            abs_workspace = f"{root_dir}/{workspace}"         
        workspace_url = os.getenv("workspace_url",f'http://10.1.150.105:7861/{rel_workspace}')
        
        self.rel_workspace = rel_workspace
        self.abs_workspace = abs_workspace
        self.workspace_url = workspace_url
        self.deployment_url = self.get_deployment_url()
        self.api_deployment_url = self.get_api_deployment_url()

        self.ocr_mode = 'API'
        _pool_size = 32 if  self.ocr_mode == 'API' else 8
        _Executor = ThreadPoolExecutor if  self.ocr_mode == 'API' else ProcessPoolExecutor     
        self.ocr_pool = _Executor(_pool_size)
        self.gpu_idxs = [0,1,2,3]

        self.vlm = Vlm_API()  

        self.chat_model = None
        self.openai_chat_model=None
        self.get_langchain_chat_model()

        self.embed_model,self.embedding_model_8k,self.reranker = None, None, None
        self.embed_model,self.embedding_model_8k,self.reranker = self.get_emb_8k_rerank_model() 

        # load ES 
        self.es_connection = None
        self.get_es_connection() 

        self.all_indices = None
        self.all_indices = self.get_all_knowledge_base()
        self.strategy = DenseVectorStrategy(hybrid=False,rrf=False,distance=DistanceMetric.COSINE)
        self.default_chinese_analyzer_settings =self.ES_DEFAULT_CHINESE_SETTINGS

        ContentProducer = "JQWL001"
        ProduceID =  "7dab1ae2ac724f4e9370f81229a55de6"
        # “内容由AI生成-JQWL001-7dab1ae2ac724f4e9370f81229a55de6”
        self.aigc_visible_text = "内容由AI生成"
        self.aigc_invisible_watermark = f"{self.aigc_visible_text}-{ContentProducer}-{ProduceID}"
        self.aigc_metadata = {    
            "AIGC": 
            {        
                "ContentProducer": ContentProducer,        
                "ProduceID": ProduceID
            }
}
    
    def get_deployment_url(self):
        deployment_url = os.getenv("deployment_url",self.workspace_url)
        return deployment_url
    def get_api_deployment_url(self):
        api_deployment_url = os.getenv("api_deployment_url",self.workspace_url)
        return api_deployment_url
    # https://www.modelscope.cn/models/Qwen/Qwen3-30B-A3B-Instruct-2507  temperature=0.7,top_p =0.8, top_k=20, min_p=0等参数设置依据
    def get_langchain_chat_model(self, temperature=0.1,top_p =0.8, top_k=20, min_p=0, presence_penalty=0.6,frequency_penalty=0.2, repetition_penalty=1.05, max_tokens=None, streaming=False,use_deepseek=True):
        if max_tokens:
            if max_tokens!=self.llm_model_max_tokens:
                logger.warning(f"您现在请求的llm {max_tokens=}，与环境配置中的{self.llm_model_max_tokens=}不同，请确认！")
        else:
            max_tokens = self.llm_model_max_tokens

        if use_deepseek:
            try:
                from langchain_deepseek import ChatDeepSeek
                self.chat_model = ChatDeepSeek(
                        cache=True,
                        model_name=self.llm_model_name,
                        api_base=self.llm_model_base_url,    
                        api_key= self.api_key,
                        streaming=streaming,
                        verbose=True,
                        temperature=temperature,
                        top_p=top_p,
                        presence_penalty = presence_penalty,
                        frequency_penalty=frequency_penalty,
                        max_tokens=max_tokens, 
                        # 设置vllm+qwen2.5的repetition_penalty: https://qwen.readthedocs.io/zh-cn/latest/framework/function_call.html#vllm
                        # https://huggingface.co/Qwen/QwQ-32B#usage-guidelines              
                        extra_body={"repetition_penalty": repetition_penalty,"min_p": min_p,"top_k": top_k},        
                    )
                if is_main_process():
                    logger.warning(f'当前使用ChatDeepSeek接口,LLM模型为:model_name = {self.chat_model.model_name}, api_base = {self.chat_model.api_base}')
            except ImportError as e:
                logger.error(f"ChatDeepSeek模块未安装，请安装'from langchain_deepseek import ChatDeepSeek'：{str(e)}")
            except Exception as e:
                logger.error(f"加载ChatDeepSeek失败：{str(e)}")

        openai_chat_model = ChatOpenAI(
                    cache=True,
                    model_name=self.llm_model_name,
                    openai_api_base=self.llm_model_base_url,    
                    openai_api_key= self.api_key,
                    streaming=streaming,
                    verbose=True,
                    temperature=temperature,
                    top_p=top_p,
                    frequency_penalty=frequency_penalty,
                    max_tokens=max_tokens, 
                    # 设置vllm+qwen2.5的repetition_penalty: https://qwen.readthedocs.io/zh-cn/latest/framework/function_call.html#vllm
                    # https://huggingface.co/Qwen/QwQ-32B#usage-guidelines              
                    extra_body={"repetition_penalty": repetition_penalty,"min_p": min_p,"top_k": top_k},        
                )       
        self.openai_chat_model = openai_chat_model

        if not self.chat_model:
            self.chat_model = openai_chat_model            
            if is_main_process():
                logger.warning(f'当前使用ChatOpenAI接口,LLM模型为:model_name = {self.chat_model.model_name}, api_base = {self.chat_model.openai_api_base}')
        return self.chat_model
    
    def _get_emb_8k_rerank_model(self,embedding_model_name=None, embedding_model_name_8k=None, rerank_model_name=None, device = ['cpu','cpu','cpu'],final_docs_num_reranked=4): #device = ['cuda:1','cuda:2''cuda:3']
        from BCEmbedding.tools.langchain import BCERerank
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
        from jqcode.jq_kb_manegement.server.localai_embeddings import LocalAIEmbeddings
       
        try:
            # embed_model = LocalAIEmbeddings(model=self.embedding_model_name,deployment=self.embedding_model_name,api_key="abc123",headers={'Authorization': 'Bearer abc123'},openai_api_base=self.embedding_model_base_url,base_url=self.embedding_model_base_url,embedding_ctx_length=self.embedding_model_max_tokens*8,chunk_size=self.embedding_model_max_tokens)
            import openai

            # Assume that the model is already launched.
            # The api_key can't be empty, any string is OK.
            # client = openai.Client(api_key="not empty", base_url="http://10.1.150.106:9997/v1")
            # client.embeddings.create(model=self.embedding_model_name, input=["What is the capital of China?"])

            # embeddings_api = LocalAIEmbeddings(
            #     model= 'Qwen3-Embedding-0.6B',#Qwen3-Embedding-0.6B
            #     openai_api_key="abc123",
            #     openai_api_base="http://10.1.150.106:9997/v1")
            # emb_test = embeddings_api.embed_query("test query text")
            
            os.environ["VLLM_API_KEY"] = "abc123"
            if self.reduce_emb_dimensions:
                embed_model = LocalAIEmbeddings(model=self.embedding_model_name,openai_api_base=self.embedding_model_base_url,openai_api_key="abc123",model_kwargs={'dimensions': self.embedding_model_dimentions})
            else:
                embed_model = LocalAIEmbeddings(model=self.embedding_model_name,openai_api_base=self.embedding_model_base_url,openai_api_key="abc123")
            emb_test = embed_model.embed_query("test query text")
            embedding_model_8k = LocalAIEmbeddings(model=self.embedding_model_8k_name,deployment=self.embedding_model_name,api_key="abc123",openai_api_base=self.embedding_model_base_url,base_url=self.embedding_model_8k_base_url,embedding_ctx_length=self.embedding_model_8k_max_tokens*4,chunk_size=self.embedding_model_8k_max_tokens)
            # r2 = embed_model.embed_documents(["执行embed_documents测试......test documents text1","test documents text2"])
            # print(r2)
            if is_main_process(): 
                logger.warning(f"{self.embedding_model_name} 嵌入模型接口{self.embedding_model_base_url}获取成功，返回的嵌入维度为{len(emb_test)}")
        except Exception as e:
            embed_model = None
            embedding_model_8k = None            
            if is_main_process(): 
                logger.error(f"{embed_model=} 嵌入模型接口{self.embedding_model_base_url}工作不正常，请检查:{e}")
        try:
            # BCERerank: compress_documents(documents: Sequence[Document],query: str)
            # xinference.client: model.rerank(corpus, query) https://inference.readthedocs.io/zh-cn/latest/index.html
            # https://github.com/xorbitsai/inference/blob/7d83300a7694a0262b634007ea4164ea753e466f/xinference/model/rerank/core.py
            
            try:
                # client = Client(self.rerank_model_base_url,api_key='abc123') #url要去掉"/v1"
                client = Client(self.rerank_model_base_url)
                xinfer_reranker = client.get_model(self.rerank_model_name)
                reranker = JqXinferenceReranker(top_n=6,model=xinfer_reranker)
            except:
                from xinference.client.restful.restful_client import RESTfulRerankModelHandle
                model = RESTfulRerankModelHandle(self.rerank_model_name,self.rerank_model_base_url, auth_headers={'Authorization': 'Bearer abc123'})
                reranker = JqXinferenceReranker(top_n=6,model=model)

            query = "A man is eating pasta."
            corpus = ["A man is eating food.","A woman is playing violin.","一个人在踢球","一个人在吃饭"]
            rerank_test1 = reranker.rerank(corpus, query,top_n=3)
            logger.debug(rerank_test1)
            rerank_test2 = reranker.compress_documents(corpus, query)
            logger.debug(rerank_test2)
            if is_main_process(): 
                logger.warning(f"{self.rerank_model_name}  重排模型接口{self.rerank_model_base_url}获取成功")
        except Exception as e:
            reranker = None
            logger.warning(f"{self.rerank_model_name}  重排模型接口{self.rerank_model_base_url}工作不正常，请检查:{e}")
            # "Failed to rerank documents, detail: [{'type': 'missing', 'loc': ['body', 'queries'], 'msg': 'Field required', 'input': {'model': 'Qwen/Qwen3-Reranker-0.6B', 'documents': ['A man is eating food.', 'A woman is playing violin.'], 'query': 'A man is eating pasta.', 'top_n': 6, 'max_chunks_per_doc': None, 'return_documents': True, 'return_len': True, 'kwargs': '{}'}}]"
            # "Failed to rerank documents, detail: [{'type': 'list_type', 'loc': ['body', 'query'], 'msg': 'Input should be a valid list', 'input': 'A man is eating pasta.'}]"
        return embed_model,embedding_model_8k,reranker

    def get_lightrag(self,index_name,example_number=2,language="Simplified Chinese",keyword_extraction=False, working_dir = "Neo4jWorkDir",log_level="DEBUG"):
        from lightrag import LightRAG
        from lightrag.llm import openai_complete_if_cache, openai_embedding
        from lightrag.utils import EmbeddingFunc
        from lightrag.utils import ENCODER
        ENCODER = self._tokenizer
        abs_working_dir = f"{self.abs_workspace}/knowledge_base/{index_name}/{working_dir}" 
        if not os.path.exists(abs_working_dir):
            os.makedirs(abs_working_dir,exist_ok=True)
        
        async def embedding_func(texts: list[str]):
            return await openai_embedding(
                texts,
                model=self.embedding_model_name,
                api_key=self.api_key,
                base_url=self.embedding_model_base_url,
            )
        async def llm_model_func(
                prompt, system_prompt=None, history_messages=[], keyword_extraction=keyword_extraction, **kwargs
            ) -> str:
                return await openai_complete_if_cache(
                    "qwen25b14",
                    prompt,
                    system_prompt=system_prompt,
                    history_messages=history_messages,
                    api_key=self.llm_model_api_key,
                    base_url="http://10.1.150.105:9999/v1",
                    **kwargs,
                )
        
        addon_params = {"example_number": example_number, "language": language}
        lightrag = LightRAG(
                working_dir=abs_working_dir,
                llm_model_func=llm_model_func,
                embedding_func=EmbeddingFunc(embedding_dim=self.embedding_model_dimentions, max_token_size=self.embedding_model_max_tokens, func=embedding_func),
                chunk_token_size = self.embedding_model_max_tokens,
                addon_params = addon_params,
                # vector_storage = "Neo4JStorage", 未实现
                graph_storage="Neo4JStorage", #<-----------override KG default
                log_level=log_level  #<-----------override log_level default
            )
        
        return lightrag

    @lru_cache
    def get_emb_8k_rerank_model(self,embedding_model_name=None, embedding_model_name_8k=None, rerank_model_name=None, device = ['cpu','cpu','cpu'],final_docs_num_reranked=6,api_mode:bool=True):
        if not (self.embed_model and self.embedding_model_8k and self.reranker):
            if api_mode:
                self.embed_model,self.embedding_model_8k,self.reranker = self._get_emb_8k_rerank_model_api()
            else:
                self.embed_model,self.embedding_model_8k,self.reranker = self._get_emb_8k_rerank_model(embedding_model_name=embedding_model_name, embedding_model_name_8k=embedding_model_name_8k, rerank_model_name=rerank_model_name,device = device,final_docs_num_reranked=final_docs_num_reranked)
        # try:
        #     r1 = self.embed_model.embed_query("执行embed_query测试......test query text")
        #     r2 = self.embed_model.embed_documents(["执行embed_documents测试......test documents text1","test documents text2"])
        #     # print(r2)
        # except Exception as e:
        #     logger.error(f"{self.embed_model=}工作不正常，请检查:{e}")
        # # try:
        # #     r2 = self.embedding_model_8k.embed_query("test query text")
        # # except Exception as e:
        # #     logger.error(f"{self.embed_model=}工作不正常，请检查:{e}")        
        # try:
        #     r3 = self.reranker.rerank(documents=["张结魁是谁？","张结魁是安徽晶奇公司的","create a compression retriever, we need a base retriever first"],
        #                              query="张结魁")
        # except Exception as e:
        #     logger.error(f"{self.reranker=}工作不正常，请检查:{e}")

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
            if is_main_process():                    
                print(f'当前使用的Elasticsearch URL为:| { self.ES_URL } |')
                # print('-------Elasticsearch Connection详细信息-------')
                # print(self.es_connection.info())
                # print('-------Elasticsearch Connection详细信息-------')
                print('-------可以通过Kibana URL查看:| http://127.0.0.1:5601 | http://10.1.150.105:5601 |-------\n')
        return self.es_connection
    
    @lru_cache
    def get_pg_connection(self,index_name:str='default',
                          connection_str:str =None,
                          connection_conf:dict =None):
        from langchain_postgres import PGVector
        from langchain_community.graphs.age_graph import AGEGraph
        from langchain_opengauss import openGaussAGEGraph
        from langchain_opengauss.config import OpenGaussSettings
        from langchain_experimental.graph_transformers import LLMGraphTransformer

        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        from sqlalchemy.sql import text
        if not connection_str:
            connection_str = self.postgres_conn_psycopg3
        if not connection_conf:
            connection_conf = {"database": "langchain","user": "langchain","password": "langchain","host": "localhost","port": 7000,}
            connection_conf = self.postgres_conn_conf_dict

        engine = create_engine(connection_str)
        with Session(engine) as session:
            with session.begin():
                session.execute(text("create extension if not exists age;"))
                session.execute(text('ALTER DATABASE postgres SET search_path = ag_catalog, "$user", public;'))   


        pg_vector_store = PGVector(async_mode=True,embeddings=self.embed_model,collection_name=index_name,connection=connection_str,use_jsonb=True,)
# self.postgres_conn_conf_dict={"database": self.POSTGRES_DBNAME,"user":self.POSTGRES_USER,"password": self.POSTGRES_PASSWORD,"host": self.POSTGRES_HOST,"port":self.POSTGRES_PORT}

        pg_graph_store = AGEGraph(graph_name=index_name, conf=connection_conf,create=True)
        pg_graph_store._enhanced_schema = False
        pg_graph_store.enhanced_schema = False

        try:
            gauss_conf = OpenGaussSettings(database = self.POSTGRES_DBNAME,
                                            user = self.POSTGRES_USER,
                                            password = self.POSTGRES_PASSWORD,
                                            host = self.POSTGRES_HOST,
                                            port = self.POSTGRES_PORT
                                        )
            gauss_graph_store = openGaussAGEGraph(graph_name=index_name,conf=gauss_conf,create=True)
        except:
            gauss_graph_store = None
        kg_llm_transformer = LLMGraphTransformer(llm=self.chat_model)
        return pg_vector_store,pg_graph_store,gauss_graph_store,kg_llm_transformer
    
    

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
        
    def _init_ocr_instances(self,mode="API"):
        ocr = None
        mode = mode or self.ocr_mode
        if mode == "API":
            ocr = Ocr_API()
            logger.debug(f"将使用多线程GPU Paddle Ocr_API")
        
        elif mode == "rapidocr":
            try:
                # raise Exception("调试，不使用多线程GPU RapidOCR的情况")
                from rapidocr_paddle import RapidOCR # For GPU 
                gpu_id = random.choice(self.gpu_idxs)
                # 为使用gpu_id参数
                # 需修改/root/.virtualenvs/test/lib/python3.10/site-packages/rapidocr_paddle/main.py
                # updater = UpdateParameters()
                # if 'gpu_id' in kwargs:
                #     gpu_id = kwargs.pop('gpu_id')
                #     config = updater(config, **kwargs)
                #     config["Det"].update({"gpu_id":gpu_id})
                #     config["Cls"].update({"gpu_id":gpu_id})
                #     config["Rec"].update({"gpu_id":gpu_id})          
                ocr = RapidOCR(det_use_cuda=True, cls_use_cuda=True, rec_use_cuda=True,gpu_id=gpu_id)
                logger.debug(f"将使用多进程GPU RapidOCR (rapidocr_paddle)")
            except Exception as e:            
                logger.debug(f"初始化GPU RapidOCR (rapidocr_paddle)失败:{e}")
                logger.debug(f"将使用多进程CPU RapidOCR (rapidocr_onnxruntime)")
                from rapidocr_onnxruntime import RapidOCR
                ocr = RapidOCR()
        return ocr
    
    def get_ocr(self):
        ocr = self._init_ocr_instances(mode=self.ocr_mode)
        return ocr

    #################################################################################
    def get_ocr_pool(self):
        return self.ocr_pool
    
    # 方式一，使用LangChain indexing API，防止重复插入
    # https://python.langchain.com/docs/modules/data_connection/indexing 

    def get_es_searchstore(self,embedding=None,es_connection=None,index_name='',strategy=None):
        assert index_name, "参数index_name（ES的索引名称）不得为空！"
        es_connection = es_connection if es_connection else self.get_es_connection()
        self.create_es_index_if_not_existes_with_default_chinese_analyzer(es_connection=es_connection,index_name=index_name)

        embedding = embedding if embedding else self.get_emb_8k_rerank_model()[0]        
        strategy = strategy if strategy else self.strategy           
        es_searchstore = ElasticsearchStore(es_connection=es_connection, index_name=index_name, embedding=embedding,strategy=strategy)
        return es_searchstore

    def get_es_searchstore_index_documents(self,documents,embedding,index_name,es_connection=None,cleanup=None,clear_before_add_index=False,strategy=None,source_id_key="source",force_update=True):
        assert index_name, "参数index_name（ES的索引名称）不得为空！"
        if not es_connection:
            es_connection=self.get_es_connection()
        embedding = embedding if embedding else self.get_emb_8k_rerank_model()[0]
        self.create_es_index_if_not_existes_with_default_chinese_analyzer(es_connection=es_connection,index_name=index_name)
        strategy = strategy if strategy else self.strategy
        es_searchstore = ElasticsearchStore(es_connection=es_connection, index_name=index_name, embedding=embedding,strategy=strategy)
        if len(documents)==0:
            return es_searchstore
                    

        
        # 检查source_id_key是否存在，如果不存在就使用'page_content'
        for document in documents:
            if source_id_key not in document.metadata.keys():
                document.metadata.update({'source':document.page_content})
        

        
        namespace = f"elasticsearch/{index_name}"
        # 
        # todo 将record_manager更改为postgres，计划是在将vectorstore由ElasticsearchStore 改为 PGVectorStore 时一起做
        # Be able to combine the transactions between the use of SQLRecordManager and PGVectorStore.
        # 参考：https://github.com/langchain-ai/langchain-postgres/pull/64
        record_manager = SQLRecordManager(namespace, db_url="sqlite:///record_manager_cache.sqlite")
        record_manager.create_schema()
        
        def _clear():
            """Hacky helper method to clear content. See the `full` mode section to to understand why it works."""        
            clear_result_report = index([], record_manager, es_searchstore, cleanup="full", source_id_key=source_id_key)
            logger.info(f'Clear_Result report of "index_documents_to_es_searchstore":{clear_result_report}')

        if clear_before_add_index:
            _clear()
        
        index_result_report=index(documents, record_manager, es_searchstore, cleanup=cleanup, source_id_key=source_id_key,force_update=force_update)
        logger.info(f'Index_Result report of "index_documents_to_es_searchstore":{index_result_report}')

        es_searchstore.client.indices.refresh(index=index_name)
        return es_searchstore

    # 方式二：常见的在教程中见到的
    def get_es_searchstore_from_documents(self, documents,embedding,index_name,es_connection=None,strategy=None):
        assert index_name, "参数index_name（ES的索引名称）不得为空！"
        assert documents,  "参数documents（待索引的文档）不得为空！"
        if not es_connection:
            es_connection=self.get_es_connection()
        embedding = embedding if embedding else self.get_emb_8k_rerank_model()[0] 
        self.create_es_index_if_not_existes_with_default_chinese_analyzer(es_connection=es_connection,index_name=index_name)       
        strategy = strategy if strategy else self.strategy
        es_searchstore = ElasticsearchStore.from_documents(documents=documents,embedding=embedding,es_connection=es_connection,index_name=index_name,strategy=strategy)
        es_searchstore.client.indices.refresh(index=index_name)
        es_searchstore.index_name=index_name
        return es_searchstore

    # 方式三：embedding vectores已经存在的情况
    def get_es_searchstore_from_document_embedding_pairs(self,index_name:str,text_embedding_pairs: Iterable[Tuple[str, List[float]]],ids:Optional[List[str]] ,
                                                         metadatas: Optional[List[dict]]=None ,es_connection=None,strategy=None,embedding=None,refresh_indices: bool = True,bulk_kwargs: Optional[Dict] = None):
        assert index_name, "参数index_name（ES的索引名称）不得为空！"
        assert text_embedding_pairs,  "参数documents（待索引的文档）不得为空！"
        assert len(text_embedding_pairs[0])==len(text_embedding_pairs[1]),  "参数text_embedding_pairs里的texts列表和embeddings列表的长度必须一致！"
        if ids:
            assert len(text_embedding_pairs[0])==len(ids),  "参数text_embedding_pairs里的texts列表和ids列表的长度必须一致！"
        if not es_connection:
            es_connection=self.get_es_connection()
        embedding = embedding if embedding else self.get_emb_8k_rerank_model()[0]
        self.create_es_index_if_not_existes_with_default_chinese_analyzer(es_connection=es_connection,index_name=index_name)       
        strategy = strategy if strategy else self.strategy
        es_searchstore = ElasticsearchStore(es_connection=es_connection, index_name=index_name, embedding=embedding,strategy=strategy)
        document_ids = es_searchstore.add_embeddings(text_embedding_pairs,metadatas=metadatas,ids=ids,bulk_kwargs=bulk_kwargs,refresh_indices=refresh_indices)

        es_searchstore.index_name=index_name
        return es_searchstore
    
    
    def split_and_get_chunks_relevant_from_documents(self,query:str, docs_list:List[Document]=None,text_splitter=None,embed_model=None,reranker=None,
                                                    if_reranking:bool=True,retriever_docs_num=10,final_docs_num=6,score_threshold=0.2,only_use_reranker:bool=True):
        
        docs_list_cleaned = []
        for doc in docs_list:
            doc.page_content = replace_multiple_newlines(doc.page_content)
            docs_list_cleaned.append(doc)
        if not text_splitter:
            text_splitter = self.jq_text_splitter
        text_chunks = text_splitter.split_documents(docs_list_cleaned)
                
        reranker = reranker if reranker else self.reranker
        original_reranker_top_n = reranker.top_n

        if only_use_reranker:
            # reduce memory usage.
            micro_bs = 6
            num_chunks = len(text_chunks)            
            if num_chunks > micro_bs:
                reranker.top_n = micro_bs
                _chunks_relevant = []
                for i in range(0, num_chunks, micro_bs):
                    sub_docs = text_chunks[i : i + micro_bs]
                    sub_chunks_relevant = reranker.compress_documents(sub_docs,query)
                    _chunks_relevant.extend(sub_chunks_relevant)            
                # s = _chunks_relevant[0].metadata.get('relevance_score_reranker', 0)
                chunks_relevant = sorted(_chunks_relevant, key=lambda x: x.metadata.get('relevance_score_reranker', 0), reverse=True)
                chunks_relevant = chunks_relevant[:final_docs_num]
            else:
                reranker.top_n = final_docs_num
                chunks_relevant = reranker.compress_documents(text_chunks,query)
            reranker.top_n = original_reranker_top_n
        
        else:
            from jqcode.jq_agent.tools.jq_retriever import get_retriever
            es_vectorstore = self.get_es_searchstore_index_documents(text_chunks, embed_model,index_name="temp_memory_or_web_results",clear_before_add_index=True) 
            retriever = get_retriever(vectorstore=es_vectorstore,top_k=retriever_docs_num,score_threshold=score_threshold) 
            chunks_relevant = retriever.invoke(query,config=self.invoke_llm_config) 
            
            # region 使用Faiss
            # embed_model  = embed_model if embed_model else self.embed_model
            # # vs=FAISS.from_documents(text_chunks, embed_model, distance_strategy=DistanceStrategy.COSINE)
            # # retriever = JqVectorStoreRetrieverWithScore(vectorstore=vs,search_type="similarity_score_threshold", search_kwargs={"score_threshold": score_threshold, "k": retriever_docs_num})
     
            # if if_reranking:                
            #     compression_retriever = ContextualCompressionRetriever(base_compressor=reranker, base_retriever=retriever)
            #     chunks_relevant = compression_retriever.invoke(query,config=self.invoke_llm_config)
            # else:
            #     retriever.search_kwargs['k'] = final_docs_num
            #     chunks_relevant = retriever.invoke(query,config=self.invoke_llm_config)
            # endregion 使用Faiss
      
        return chunks_relevant

    def is_toolcall_aimessage(self, message):
        if isinstance(message,AIMessage) and len(message.tool_calls):
            return True
        else:
            return False
            
    # https://github.com/langchain-ai/langgraph/blob/main/examples/managing-conversation-history.ipynb
    # 历史相关信息首先获得相关的字符串内容，然后组装成一条HumanMessage，再生成一条AIMessage
    # makeup_aimesaage = AIMessage(content="I know, I have got the converstion history.")    
    # 避免历史消息类型的拼装（符合HumanMessage、AIMessage、[ToolMessage if AIMessage is a ToolCall AIMessage]），引入不相关、不必要的消息
    # 返回最近的n条消息列表，并且保证是以HumanMessage开头的，符合HumanMessage、AIMessage、[ToolMessage if AIMessage is a ToolCall AIMessage]
    def filter_and_get_messages_relevant_to_query(self,query:str,messages_list:List[BaseMessage],reserve_last_n_messages_num=0,reserve_message_types:tuple=(HumanMessage,AIMessage),text_splitter=None,embed_model=None,reranker=None,
                                                    if_reranking:bool=True,retriever_docs_num=10,final_docs_num=6 ,score_threshold=0.3, only_use_reranker=True):
    
        if not messages_list:
           return []        
        if reserve_last_n_messages_num>0 and reserve_last_n_messages_num>=len(messages_list):
            return messages_list
                        
        else:            
            history_context = ''
            last_n_messages = []
            history_messages = []
            if reserve_last_n_messages_num == 0:
                last_n_messages = []
                history_messages = messages_list
            # 首先得到最近的n条消息列表，并且保证是以HumanMessage开头的
            else:
                last_n_messages = messages_list[-reserve_last_n_messages_num:]
                history_messages = messages_list[:-reserve_last_n_messages_num]
                if last_n_messages:
                    last_n_messages0 = last_n_messages[0]
                    # 补齐，直到消息列表是以HumanMessage开头的
                    if not isinstance(last_n_messages0,HumanMessage):
                        for m in history_messages[::-1]:
                            last_n_messages.insert(0,m)
                            if isinstance(m,HumanMessage):
                                break
                    last_n_messages0 = last_n_messages[0]
                    assert isinstance(last_n_messages0,HumanMessage), f"保留的消息列表必须是以HumanMessage开始的,但当前的第一条消息是:{last_n_messages0}"
                
                    # 根据补齐后的消息列表，重新得到历史消息列表
                    reserve_last_n_messages_num = len(last_n_messages)
                    history_messages = messages_list[:-reserve_last_n_messages_num] 
            # 上面已经得到了最终的last_n_messages结果
            
            # 上面也已经得到了history_messages（不包括last_n_messages）的内容
            #  现在只需要筛选出独立、相关的，并组装成history_context字符串
            existed_messages_content_set = set([m.content for m in last_n_messages])
            unique_history_messages_list = []
            # 得到非空的，unique的HumanMessage,AIMessage列表
            # 且是最近的
            for message in history_messages[::-1]: #倒序添加
                if isinstance(message,reserve_message_types):                     # 只保留HumanMessage,AIMessage
                    # if self.is_toolcall_aimessage(message):
                    #     continue
                    if message.content:                                              # 确保message.content不为空
                        if not self.is_toolcall_aimessage(message):
                            if message.content not in  existed_messages_content_set:
                                unique_history_messages_list.append(message.content)
                                existed_messages_content_set.add(message.content)
            # 因为是倒序添加的，所以要翻转回来，
            # 注意：这里只是 消息内容列表
            unique_history_messages_list.reverse()
        
            if len(unique_history_messages_list) > 0:
                embed_model  = embed_model if embed_model else self.embed_model
                reranker  = reranker if reranker else self.reranker
                text_splitter  = text_splitter if text_splitter else self.jq_text_splitter 

                docs_from_messages = [Document(page_content=message_content,metadata={"message_index":message_index,"source":message_content}) for message_index, message_content in enumerate(unique_history_messages_list)]
                chunks_relevant = self.split_and_get_chunks_relevant_from_documents(query, docs_from_messages,text_splitter=text_splitter,reranker=reranker,
                                                                            if_reranking=if_reranking,retriever_docs_num=retriever_docs_num, final_docs_num=final_docs_num,score_threshold=score_threshold,only_use_reranker=only_use_reranker)
                if chunks_relevant:
                    content_list = [document.page_content for document in chunks_relevant]
                    history_context = "\n".join(content_list)
                    history_context = "\nHere is the conversation history.\n[BEGINOFHISTORY]:\n" + history_context + "\n[ENDOFHISTORY].\n"
        
                    makeup_human_message = HumanMessage(content=history_context,name="history_context")
                    makeup_ai_mesaage = AIMessage(content="I know, I have got the converstion history.",name='history_ai')
                    all_messages = [makeup_human_message,makeup_ai_mesaage] + last_n_messages
                    return all_messages
                else:
                    return last_n_messages
            
            else:
                return []

@lru_cache
def get_env_models_instance():
    _env_models_instance = InitEnvModels()
    return _env_models_instance

env_models_instance = get_env_models_instance()

# region 留着备用
# embedding_model_fn = env_models_instance.get_emb_8k_rerank_model()[0]
# texts = ["张结魁是谁？","张结魁是安徽晶奇公司的"]
# embeddings = embedding_model_fn.embed_documents(texts)
# text_embedding_pairs = list(zip(texts,embeddings))
# vs = env_models_instance.get_es_searchstore_from_document_embedding_pairs(index_name="temp_emb_dense",text_embedding_pairs=text_embedding_pairs,ids=["1","2"],metadatas=[{"source":"张结魁是谁？"},{"source":"张结魁是安徽晶奇公司的"}])
# # vs = env_models_instance.get_es_searchstore_from_document_embedding_pairs(index_name="temp_emb_dense",text_embedding_pairs=[(texts[0], embeddings[0]),(texts[1], embeddings[1])],ids=["1","2"],metadatas=[{"source":"张结魁是谁？"},{"source":"张结魁是安徽晶奇公司的"}])
# print(vs)
# r1=vs.similarity_search("张结魁是谁？")
# r2=vs.similarity_search_with_score("张结魁是谁？")
# pass




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




if __name__ == '__main__':
    # qwen:110b-chat-v1.5-q4_K_M
    # litellm --model ollama_chat/llama3:70b-instruct
    # litellm --model ollama_chat/yi:34b-chat-v1.5-q8_0
    # ocr = env_models_instance.get_ocr()
    # pg_vector_store,pg_graph_store,kg_llm_transformer = env_models_instance.get_pg_connection()

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
    llm = env_models_instance.chat_model.bind_tools(tools)
    print("==========="*10)
    system_prompt = f"""You are an assistant that has access to functions.
        ONLY Use them:

        {rendered_tools}


        Given the user input, return the name and input of the tool to use.
        Return your response as a JSON blob with 'name' and 'arguments' keys.
        The value associated with the 'arguments' key should be a dictionary of parameters."""
    print("==========="*10)

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
    prompt = '使用python无法计算出3*10的正确结果，请思考这句话正确吗？你是接受还是拒绝这个陈述,并请给出理由'
    # prompt = "Statement:Using Python can calculate out 3*10's correct result. Should you accept or reject the statement? and give me your reason"
    # prompt = "Using Python can calculate out 3*10's correct result.你是接受还是拒绝这个陈述"

    res = LLM(prompt,system_prompt)
    print(res)
    
    llm = env_models_instance.chat_model
    res = llm.invoke("你好")
    print(res)


    sentense= ["张结魁是谁？","张结魁是安徽晶奇公司的",
               "create a compression retriever, we need a base retriever first",
               "As shown in the summary table above, the number of lexical units has increased by 16% to more than 11,800, while the numbers of frames and FEs have increased by 25% to 1,019 and 8,884 respectively. Some frames are marked as “non-lexical”, meaning that we have created them because they are logically necessary in the frame hierarchy,"]
    docs = [Document(page_content=s) for s in sentense]
    chunks = env_models_instance.split_and_get_chunks_relevant_from_documents(docs_list=docs,query='张结魁',only_use_reranker=True)
    print(chunks)

    from langchain_core.messages import HumanMessage,SystemMessage
    es_connection = env_models_instance.get_es_connection()
    es_searchstore = env_models_instance.get_es_searchstore(index_name = "default")

    knowledge_base_list = env_models_instance.get_all_knowledge_base(es_connection) 
    print(knowledge_base_list)   

    # open_ai = env_models_instance.get_openai()
    # openai_client = env_models_instance.get_openai_client()
    langchain_chat_model = env_models_instance.chat_model
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

