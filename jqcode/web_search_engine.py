import os
import re
import sys
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from fake_useragent import UserAgent

from langchain_community.document_loaders import WebBaseLoader
from langchain_community.document_loaders import SeleniumURLLoader
from langchain_community.document_loaders import AsyncHtmlLoader
from langchain_community.document_loaders import NewsURLLoader #需导入结巴分词的词典，严重拖慢速度
from langchain_community.document_loaders import PlaywrightURLLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_transformers import Html2TextTransformer
from jqcode.c0_init_env_models import get_es_connection, get_es_searchstore, get_es_searchstore_index_documents

USING_JINA_AI_READER = os.getenv("USING_JINA_AI_READER",True)
es_vectorstore = get_es_searchstore()

html2text = Html2TextTransformer()



from functools import partial
from typing import Optional
from langchain_core.callbacks.manager import Callbacks
from langchain_core.prompts import BasePromptTemplate, PromptTemplate, format_document
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.retrievers import BaseRetriever
from langchain_elasticsearch import ElasticsearchStore
from langchain.tools import Tool

jina_reader_prefix = 'https://r.jina.ai/'
index_name='temp_web_search_index'
try:
    ua = UserAgent(browsers=['edge', 'chrome'])
    user_agents = ua.random
except:
    user_agents = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36 Edg/108.0.1462.76'


def convert_search_query_backup(query):
    query_terms = query.strip().split(' ')
    query_terms = [query_term for query_term in query_terms if query_term]
    converted_query = '+'.join(query_terms)
    return converted_query

def convert_search_query(query):
    query = query.strip()
    # query = re.sub(r' +', ' ', query)
    # query_terms = query.strip().split(' ')
    # converted_query = '+'.join(query_terms)
    converted_query = re.sub(r' +', ' ', query)
    return converted_query




def is_query_chinese(query):
    pattern = re.compile(r'[\u4e00-\u9fa5]')
    return bool(re.search(pattern, query))

class RetrieverInput(BaseModel):
    """Input to the retriever."""
    query: str = Field(description="query to look up in retriever")

class BaiduSearch:
    def __init__(self):
        # 请求头信息
        self.HEADERS = {"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": user_agents,
            "Referer": "https://www.baidu.com/",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "zh-CN,zh;q=0.9"
        }


    def search(self,query):
        # 百度高级搜索https://www.baidu.com/gaoji/advanced.html

        if query:
            session = requests.Session()
            session.headers = self.HEADERS

            query = convert_search_query(query)
            url = "https://www.baidu.com/s?ie=utf-8&tn=baidu&wd=" + query

            response = session.get(url=url)
            if response.status_code == 200:
                print("百度搜索：",url)
            else:
                print(f"百度搜索失败（response.status_code != 200）: {url}")
                jina_url = jina_reader_prefix+url
                print(f"尝试使用jina_reader: {jina_url}")
                session.headers = {"x-respond-with": "html"}
                response = session.get(url=jina_url)
                if response.status_code!= 200:
                    print(f"尝试jina_reader也失败（response.status_code != 200）: {jina_url}")
                    return []
                                          
            response.encoding = "utf-8"
            soup = BeautifulSoup(response.text, "lxml")
            # Finding all 'a' tags which typically contain href attribute for links
            links = [urljoin(url, a["href"]) for a in soup.find_all("a", href=True) if a["href"]]
            valid_prefix='http://www.baidu.com/link?url='
            valid_links = [link for link in links if link.startswith(valid_prefix)]
            valid_links_without_repeated = sorted(set(valid_links),key=valid_links.index)
            
            if len(valid_links_without_repeated)==0:
            # if len(valid_links_without_repeated):
                print(f"百度搜索未能获得有效URL结果。")
                jina_url = jina_reader_prefix+url
                print(f"尝试使用jina_reader: {jina_url}")
                session.headers = {"x-respond-with": "html"}
                response = session.get(url=jina_url)
                response.encoding = "utf-8"
                soup = BeautifulSoup(response.text, "lxml")
                # Finding all 'a' tags which typically contain href attribute for links
                links = [urljoin(url, a["href"]) for a in soup.find_all("a", href=True) if a["href"]]
                valid_prefix='http://www.baidu.com/link?url='
                valid_links = [link for link in links if link.startswith(valid_prefix)]
                valid_links_without_repeated = sorted(set(valid_links),key=valid_links.index)
            return valid_links_without_repeated

        else:
            print("搜索查询(query)为空！请检查")
            return []

class BingSearch:
    def __init__(self,):
        self.HEADERS = {"User-Agent": user_agents}

    def search(self,query):
        if query:
            query = convert_search_query(query)
            url = f'https://www.bing.com/search?q={query}'
            
            session = requests.Session()
            session.headers = self.HEADERS
            response = session.get(url=url)
            if response.status_code == 200:
                print("必应搜索：",url)
            else:
                print(f"必应搜索失败（response.status_code != 200）: {url}")
                jina_url = jina_reader_prefix+url
                print(f"尝试使用jina_reader: {jina_url}")
                session.headers = {"x-respond-with": "html"}
                response = session.get(url=jina_url)
                if response.status_code!= 200:
                    print(f"尝试jina_reader也失败（response.status_code != 200）: {jina_url}")
                    return []
            
            links = []    
            soup = BeautifulSoup(response.text,'lxml') #"html5lib" 'html.parser'            
            lis = soup.find_all('li',class_ = 'b_algo')            
            if lis:
                for i in lis:
                    url=i.find('a',class_ = 'tilk')['href']
                    links.append(url)
            else:
                no_result = soup.find_all('li',class_ = 'b_no')
                if no_result:
                    texts = no_result[0].find('h1').contents[0]
                    print(f"必应搜索未能获得有效结果，返回文本为：'{texts}{query}'")
                jina_url = jina_reader_prefix+url
                print(f"由于必应搜索未能获得有效URL结果，尝试使用jina_reader: {jina_url}")
                session.headers = {"x-respond-with": "html"}
                response = session.get(url=jina_url)
                soup = BeautifulSoup(response.text,'lxml') #"html5lib" 'html.parser'
                lis = soup.find_all('li',class_ = 'b_algo')
                if lis:
                    for i in lis:
                        url=i.find('a',class_ = 'tilk')['href']
                        links.append(url)
            return links
        
        else:
            print("搜索查询(query)为空！请检查")
            return []
        
def get_search_result_links(query): # todo优化逻辑
    if query:
        if is_query_chinese(query):
            baidu = BaiduSearch()
            urls = baidu.search(query)
            url_num = len(urls)
            print(f'Baidu搜索到 {url_num} 条相关内容！')
            if url_num == 0:
                bing =BingSearch()
                urls=bing.search(query)
                url_num = len(urls)
                print(f'Bing搜索到 {url_num} 条相关内容！')
        else:
            bing =BingSearch()
            urls=bing.search(query)
            url_num = len(urls)
            print(f'Bing搜索到 {url_num} 条相关内容！')
            if url_num == 0:
                baidu = BaiduSearch()
                urls = baidu.search(query)
                url_num = len(urls)
                print(f'Baidu搜索到 {url_num} 条相关内容！')



        if urls:
            print(urls)
            return urls
        else:
            print('没有搜索到任何相关内容！')
            return []
    else:
        print("搜索查询(query)为空！请检查")
        return []



def get_search_result_documents(urls,query,es_vectorstore,document_loader_class=WebBaseLoader,max_search_nums=10,max_doc_nums=5):

    # https://www.comet.com/site/blog/langchain-document-loaders-for-web-data/
            # 内容应该是NewsURLLoader比较适合RAG
            # 但SeleniumURLLoader似乎可以防屏蔽
    # 警告：这里不能使用loader.aload()方法，否则后面langchain agent里会报错！
    if max_search_nums:
        urls = urls[:max_search_nums]
        print(f'只获取前{max_search_nums}条搜索结果！')


    if document_loader_class==NewsURLLoader:
        loader = document_loader_class(urls,text_mode=True,nlp=True,continue_on_failure=True)
        docs = loader.load()
    elif document_loader_class==WebBaseLoader:
        loader = document_loader_class(urls,autoset_encoding=True,requests_kwargs ={'verify':False},verify_ssl=False,requests_per_second=1,continue_on_failure=True)
        docs = loader.load()
    elif document_loader_class==AsyncHtmlLoader:
        loader = document_loader_class(urls,autoset_encoding=True,requests_kwargs ={'verify':False},verify_ssl=False,requests_per_second=1,ignore_load_errors=False)
        docs = loader.load()
    elif document_loader_class==SeleniumURLLoader:
        loader = document_loader_class(urls)
        docs = loader.load()
    elif document_loader_class==PlaywrightURLLoader:
        # with sync_playwright() as p:
        loader = document_loader_class(urls,remove_selectors=["header", "footer"])
        docs = loader.load()
    else:
        print('暂时只支持Web Document Loaders：WebBaseLoader,NewsURLLoader, SeleniumURLLoader,AsyncHtmlLoader,PlaywrightURLLoader')
        print(f'但现要求使用的为{document_loader_class},请检查！')
        return []

    docs = loader.load()
    
    if docs and es_vectorstore:
        docs_transformed = html2text.transform_documents(docs)
        # 只保留page_content长度>50的
        docs_transformed = [doc for doc in docs_transformed if len(doc.page_content.strip())>50]

        if len(docs_transformed)>0:            
            text_splitter = RecursiveCharacterTextSplitter(chunk_size = 500,chunk_overlap = 100)
            documents = text_splitter.split_documents(docs_transformed)
            results = index_documents_to_es_vectorstore(documents,index_name=index_name,es_vectorstore=es_vectorstore,clear_before_add_index=True)
            print(f"Add indices['{index_name}'] result:",results)
            
            docs_mmr = es_vectorstore.max_marginal_relevance_search(query,k=max_doc_nums)
            return docs_mmr
        else:
            return []
    else:
        return docs

    
def get_web_search_documents(query,es_vectorstore,max_doc_nums=5):
    urls = get_search_result_links(query)
    docs = []
    if urls:
        docs = get_search_result_documents(urls,query,es_vectorstore,max_doc_nums=max_doc_nums)
    return docs

class RetrieverInput(BaseModel):
    """Input to the retriever."""

    query: str = Field(description="query to look up in retriever")


def _get_relevant_documents(
    query: str,
    es_vectorstore: ElasticsearchStore,
    document_prompt: BasePromptTemplate,
    document_separator: str,
    callbacks: Callbacks = None,

) -> str:
    docs = get_web_search_documents(query,es_vectorstore)
    return document_separator.join(
        format_document(doc, document_prompt) for doc in docs
    )

async def _aget_relevant_documents(
    query: str,
    retriever: BaseRetriever,
    document_prompt: BasePromptTemplate,
    document_separator: str,
    callbacks: Callbacks = None,
) -> str:
    print('警告：afunc是假设es_vectorstore已经建立了索引!因为我不会暂时不会async呀')
    docs = await retriever.aget_relevant_documents(query, callbacks=callbacks)
    return document_separator.join(
        format_document(doc, document_prompt) for doc in docs
    )

def create_web_retriever_tool(
    es_vectorstore: ElasticsearchStore,
    name: str,
    description: str,
    *,
    document_prompt: Optional[BasePromptTemplate] = None,
    document_separator: str = "\n\n",
) -> Tool:
    """Create a tool to do retrieval of documents.

    Args:
        retriever: The retriever to use for the retrieval
        name: The name for the tool. This will be passed to the language model,
            so should be unique and somewhat descriptive.
        description: The description for the tool. This will be passed to the language
            model, so should be descriptive.

    Returns:
        Tool class to pass to an agent
    """
    document_prompt = document_prompt or PromptTemplate.from_template("{page_content}")
    es_vectorstore.index_name = index_name
    func = partial(
        _get_relevant_documents,
        es_vectorstore=es_vectorstore,
        document_prompt=document_prompt,
        document_separator=document_separator,
    )

    afunc = partial(
        _aget_relevant_documents,
        retriever= es_vectorstore.as_retriever(),
        document_prompt=document_prompt,
        document_separator=document_separator,
    )

    return Tool(
        name=name,
        description=description,
        func=func,
        coroutine=afunc, # 注意，afunc是假设es_vectorstore已经建立了索引
        args_schema=RetrieverInput,
    )



if __name__ == "__main__":

    # urls = get_search_result_links("langchain")
    # print(urls)
    # docs = get_search_result_documents(urls)

    # query = '中国科学技术大学'
    query = 'how python install langchain langgraph package'
    d2 = get_web_search_documents(query,es_vectorstore=es_vectorstore)

    query = '合肥八中       校区数量'
    d2 = get_web_search_documents(query,es_vectorstore=es_vectorstore)

    for doc in d2:
        print(doc.page_content)

# http://www.quanso.com.cn/ 全网搜
# https://www.baidu.com/gaoji/advanced.html 百度高级搜索

# https://www.baidu.com/s?q1=%E5%90%88%E8%82%A5%E5%85%AB%E4%B8%AD+%E6%A0%A1%E5%8C%BA%E6%95%B0%E9%87%8F++&q2=&q3=&q4=&rn=20&lm=0&ct=0&ft=&q5=&q6=&tn=baiduadv
    # 调用方法
    '''
        from c62_create_websearch_agenttool create_web_retriever_tool
        web_search= create_web_retriever_tool(es_vectorstore = es_vectorstore,
                                            name='web_search', 
                                            description='根据输入的搜索关键词(query)，使用搜索引擎进行搜索，返回搜索结果。重要:当你自身的知识无法回答用户问题时，可以尝试进行网络搜索'
                                            )
    
    '''