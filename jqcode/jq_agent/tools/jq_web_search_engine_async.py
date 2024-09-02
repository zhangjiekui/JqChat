import os
import re
import random
import asyncio
from typing import (
    Any,
    AsyncIterator,
    Dict,
    Iterator,
    List,
    Optional,
    Tuple,
    Union,
    cast,
)
import aiohttp
from aiohttp import request
from aiomultiprocess import Pool
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import html2text
from langchain_core.documents import Document
from langchain_community.document_loaders import AsyncHtmlLoader
from langchain_community.document_loaders.async_html import _build_metadata
from langchain_community.tools.tavily_search import TavilySearchResults

from func_timeout import func_set_timeout, FunctionTimedOut

import urllib3
from urllib.parse import urljoin
urllib3.disable_warnings()
from langchain_core.tools import tool

from jqcode.jq_utils.logger import jqkj_logger
logger = jqkj_logger(__file__).get_logger()

timeout_value = 60
USING_JINA_AI_READER = os.getenv("USING_JINA_AI_READER",True)
jina_reader_prefix = 'https://r.jina.ai/'
valid_prefix='http://www.baidu.com/link?url='

filter_out_host = ['github.com','google.com','huggingface.co'] #这些网站的网页内容，基本无法成功访问、获取
html2text_handler = html2text.HTML2Text()


try:
    ua = UserAgent()
    user_agents = ua.random
except:
    print('使用fake_useragent获取user_agents失败，请检查!只好使用预定义的user_agents，但反爬虫机制的存在，成功获取搜索结果的概率会降低！')
    user_agents = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36 Edg/108.0.1462.76'

def convert_search_query(query,join_character='+'):
    '''
    join_character:
        取值：‘+’ （默认），其他情况下传入None
        使用Baidu、Bing搜索引擎时，需要用 ‘+’ 连接搜索关键词 （代替空格）
        但使用TavilySearch时，不需要 ‘+’ 
    '''
    query = query.strip()
    query = re.sub(r' +', ' ', query)
    if join_character:
        query_terms = query.strip().split(' ')
        query = join_character.join(query_terms)
    return query

def is_query_chinese(query):
    pattern = re.compile(r'[\u4e00-\u9fa5]')
    return bool(re.search(pattern, query))

def get_random_elements(my_list, N):
    random_elements = random.sample(my_list, N)
    return random_elements

class BaiduSearch:
    def __init__(self):
        # 请求头信息
        self.HEADERS = {"Accept": "text/html",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": user_agents,
            "Referer": "https://www.baidu.com/",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "zh-CN,zh;q=0.9"
        }
        self.url = "https://www.baidu.com/s?ie=utf-8&tn=baidu&wd=" 


    def search(self,query):
        session = requests.Session()
        session.headers = self.HEADERS
        url = self.url + query
        response = session.get(url=url)
        if response.status_code == 200:
            print("百度搜索：",url)
        else:
            print(f"百度搜索失败（response.status_code != 200）: {url}")
            return []
                                        
        response.encoding = "utf-8"
        soup = BeautifulSoup(response.text, "lxml")
        # Finding all 'a' tags which typically contain href attribute for links
        links = [urljoin(url, a["href"]) for a in soup.find_all("a", href=True) if a["href"]]
        
        valid_links = [link for link in links if link.startswith(valid_prefix)]
        valid_links_without_repeated = sorted(set(valid_links),key=valid_links.index)
        
        return valid_links_without_repeated

class BingSearch:
    def __init__(self,):
        self.HEADERS = {"User-Agent": user_agents}
        self.url = 'https://www.bing.com/search?q='

    def search(self,query):
        url = self.url + query        
        session = requests.Session()
        session.headers = self.HEADERS
        response = session.get(url=url)
        if response.status_code == 200:
            print("必应搜索：",url)
        else:
            print(f"必应搜索失败（response.status_code != 200）: {url}")
            return []
        
        bing_links = []    
        soup = BeautifulSoup(response.text,'lxml') #"html5lib" 'html.parser'            
        lis = soup.find_all('li',class_ = 'b_algo')            
        if lis:
            for i in lis:
                url=i.find('a',class_ = 'tilk')['href']
                bing_links.append(url)
            else:
                no_result = soup.find_all('li',class_ = 'b_no')
                if no_result:
                    texts = no_result[0].find('h1').contents[0]
                    print(f"必应搜索未能获得有效结果，返回文本为：'{texts}{query}'")
        
        # Bing搜索故意不保持顺序排序，因为访问速度慢，后面获取网页内容时容易超时，
        # 不保持排序，才可能有机会获取到部分URLs的网页内容
        # valid_links_without_repeated = sorted(set(bing_links),key=bing_links.index)
        valid_links_without_repeated = list(set(bing_links))
        return valid_links_without_repeated

class JinaSearch:
    def __init__(self,):
        self.HEADERS =  {"x-respond-with": "html"}
        self.url = 'https://r.jina.ai/'

    def search(self,query,search_engine_url):
        valid_links_without_repeated = []
        session = requests.Session()
        session.headers = self.HEADERS
        jina_url = self.url + search_engine_url + query
        print(f"尝试使用jina_reader: {jina_url}")   
        response = session.get(url=jina_url)
        if response.status_code!= 200:
            print(f"尝试JinaSearch失败（response.status_code != 200）: {jina_url}")
            return []
        response.encoding = "utf-8"
        soup = BeautifulSoup(response.text, "lxml")
        if "baidu" in search_engine_url:
            links = [urljoin(search_engine_url, a["href"]) for a in soup.find_all("a", href=True) if a["href"]]
            valid_links = [link for link in links if link.startswith(valid_prefix)]
            valid_links_without_repeated = sorted(set(valid_links),key=valid_links.index)
        if "bing" in search_engine_url:
            bing_links = []
            lis = soup.find_all('li',class_ = 'b_algo')            
            if lis:
                for i in lis:
                    url=i.find('a',class_ = 'tilk')['href']
                    bing_links.append(url)
            valid_links_without_repeated = sorted(set(bing_links),key=bing_links.index)
            return valid_links_without_repeated


@func_set_timeout(timeout_value)
def get_search_result_links(query): 
    baidu = BaiduSearch()
    bing =  BingSearch()
    jina =  JinaSearch()
    urls = []
    if is_query_chinese(query):        
        urls = baidu.search(query)
        url_num = len(urls) if urls else 0
        print(f'Baidu搜索到 {url_num} 条相关内容！')
        if url_num == 0:           
            urls=bing.search(query)
            url_num = len(urls) if urls else 0
            print(f'Bing搜索到 {url_num} 条相关内容！')
        if url_num == 0: 
            urls=jina.search(query,baidu.url)
            url_num = len(urls) if urls else 0
            print(f'Jina+Baidu搜索到 {url_num} 条相关内容！')
    else:
        urls=bing.search(query)
        url_num = len(urls) if urls else 0
        print(f'Bing搜索到 {url_num} 条相关内容！')
        if url_num == 0:
            urls = baidu.search(query)
            url_num = len(urls) if urls else 0
            print(f'Baidu搜索到 {url_num} 条相关内容！')
        if url_num == 0: 
            urls=jina.search(query,bing.url)
            url_num = len(urls) if urls else 0
            print(f'Jina+Bing搜索到 {url_num} 条相关内容！')
    if urls:
        # print(urls)
        return urls
    else:
        print('没有搜索到任何相关内容！')
        return []

class AsyncHtmlLoaderBypassException(AsyncHtmlLoader):
    def __init__(
        self,
        web_path: Union[str, List[str]],
        header_template: Optional[dict] = None,
        verify_ssl: Optional[bool] = True,
        proxies: Optional[dict] = None,
        autoset_encoding: bool = True,
        encoding: Optional[str] = None,
        default_parser: str = "html.parser",
        requests_per_second: int = 2,
        requests_kwargs: Optional[Dict[str, Any]] = None,
        raise_for_status: bool = False,
        ignore_load_errors: bool = False,
        *,
        preserve_order: bool = True,
        trust_env: bool = False,
    ):
        super().__init__(
            web_path,
            header_template,
            verify_ssl,
            proxies,
            autoset_encoding,
            encoding,
            default_parser,
            requests_per_second,
            requests_kwargs,
            raise_for_status,
            ignore_load_errors,
            preserve_order=preserve_order,
            trust_env=trust_env
        )
    async def _fetch(
        self, url: str, retries: int = 3, cooldown: int = 2, backoff: float = 1.5
    ) -> str:
        
        text = ""
        real_url = ""
        try:
            async with aiohttp.ClientSession(trust_env=self.trust_env) as session:
                for i in range(retries):
                    try:
                        async with session.get(
                            url,
                            headers=self.session.headers,
                            ssl=None if self.session.verify else False,
                            allow_redirects=False,
                            **self.requests_kwargs,
                        ) as response:
                            try:
                                if url.startswith('http://www.baidu.com/link?'):
                                    real_url = response.headers.get("Location",None)
                                    if real_url:
                                        url = real_url
                                text = await response.text()
                            except UnicodeDecodeError:
                                logger.error(f"Failed to decode content from {url}")
                                
                            # return url,text
                    except (aiohttp.ClientConnectionError, TimeoutError) as e:
                        if i == retries - 1 and self.ignore_load_errors:
                            logger.warning(f"Error fetching {url} after {retries} retries.")
                            
                        elif i == retries - 1:
                            print(f'尝试了{i=}次')
                            i == retries - 1
                            continue
                        else:
                            logger.warning(
                                f"Error fetching {url} with attempt "
                                f"{i + 1}/{retries}: {e}. Retrying..."
                            )
                            await asyncio.sleep(cooldown * backoff**i)
            # raise ValueError(".....retry count exceeded.....")
        except Exception as e:
            if self.ignore_load_errors:
                logger.error(f"无法获得到{url},错误信息为:{str(e) or type(e).__name__}")
                
            else:
                raise e
        finally:
            return real_url,text
    async def _fetch_with_rate_limit(
        self, url: str, semaphore: asyncio.Semaphore
    ) -> Tuple[str, str]:
        async with semaphore:
            real_url, text = await self._fetch(url)
            return url, real_url,  text
    async def alazy_load(self) -> AsyncIterator[Document]:
        """Lazy load text from the url(s) in web_path."""
        async for url, real_url,  text in self._lazy_fetch_all(
            self.web_paths, self.preserve_order
        ):
            yield self._to_document(url, real_url,  text)        
    def _to_document(self, url: str, real_url:str,text: str) -> Document:
        from bs4 import BeautifulSoup

        if url.endswith(".xml"):
            parser = "xml"
        else:
            parser = self.default_parser
        self._check_parser(parser)
        soup = BeautifulSoup(text, parser)
        source_url = real_url if real_url else url
        metadata = _build_metadata(soup, source_url)
        metadata.update({"baidu_url":url})
        return Document(page_content=text, metadata=metadata)

@func_set_timeout(timeout_value)
async def get_webpages_texts_by_langchain_document_loader_from_urls(urls,max_doc_nums=4,header_template=None,timeout_seconds:int=10):    
    loader = AsyncHtmlLoaderBypassException(urls,requests_per_second=max_doc_nums,header_template=header_template, autoset_encoding=True,verify_ssl=False,raise_for_status=False,ignore_load_errors=True,preserve_order=False,requests_kwargs={"timeout":timeout_seconds})
    # async with async
    docs_async_generator = loader.alazy_load()        
    docs_transformed_completed = []
    try:
        async for doc in docs_async_generator:                
            page_content = html2text_handler.handle(doc.page_content)
            transformed_document = Document(page_content=page_content, metadata={**doc.metadata})
            docs_transformed_completed.append(transformed_document)
            if len(docs_transformed_completed) == max_doc_nums:
                break 
    except Exception as e:
        logger.error(f'get_webpages_texts_by_langchain_document_loader_from_urls失败:{e}')                     
    
    # 只保留page_content长度>50的
    if docs_transformed_completed:
        docs = [doc for doc in docs_transformed_completed if len(doc.page_content.strip())>50]
    else:
        docs = []
    return docs

@func_set_timeout(timeout_value)
async def get_webpages_texts_by_jina_ai_reader_from_urls(urls,docs=[]):
        headers = {"x-respond-with": "html"}
        jina_urls = [jina_reader_prefix + url for url in urls]
        max_doc_nums = len(jina_urls)
        jina_docs = await get_webpages_texts_by_langchain_document_loader_from_urls(jina_urls,max_doc_nums=max_doc_nums,header_template=headers)
        docs += jina_docs
        return docs

@func_set_timeout(timeout_value)
async def get_search_result_documents(urls,query,document_loader_class=AsyncHtmlLoader,max_doc_nums=4,filter_out_host = filter_out_host):
    # https://www.comet.com/site/blog/langchain-document-loaders-for-web-data/
            # 内容应该是NewsURLLoader比较适合RAG
            # 但SeleniumURLLoader似乎可以防屏蔽
    # 警告：这里不能使用loader.aload()方法，否则后面langchain agent里会报错！
    
    if len(urls) == 0:
        print("待获取的URLs列表为空！请检查")
        return []
    
    if filter_out_host:
        for host in filter_out_host:
            for url in urls:
                if host in url:
                    urls.remove(url)
                    print(f"过滤/删除的{url=}")

    url_nums = len(urls) 
    print(f'共有{url_nums}条Urls')
    if max_doc_nums<url_nums:
        # urls = urls[:max_doc_nums]
        urls = get_random_elements(urls,max_doc_nums)
        print(f'拟随机获取{max_doc_nums}条Urls的搜索结果')
    else:
        print(f'拟获取全部{url_nums}条Urls的搜索结果')

    docs = []
    try:
        docs =await get_webpages_texts_by_langchain_document_loader_from_urls(urls, max_doc_nums=max_doc_nums)
    except FunctionTimedOut as e:
        print(f'直接获取URLs网页超时！只获取到{len(docs)}个文档。{e}')
    except Exception as e:
        print(f'直接获取URLs网页内容失败！只获取到{len(docs)}个文档。{e}')

    finally:
        print(f"已获取到{len(docs)}个文档。")    
        if USING_JINA_AI_READER and len(docs) < min(max_doc_nums,url_nums):
            if docs:
                urls_getted = []
                for d in docs:
                    url_getted = d.metadata.get('baidu_url',False)
                    if url_getted:
                        urls_getted.append(url_getted)
                _urls = list(set(urls) - set(urls_getted)) 
                print('================================================')
                print(f'       -------urls:{len(urls)}')
                print(f'       -------urls_getted:{len(urls_getted)}')
                print(f'       -------_urls:{len(_urls)}')
                print('================================================')


                print(f"继续尝试使用jina_reader获取{len(_urls)=}个网页内容")
            try:
                docs = await get_webpages_texts_by_jina_ai_reader_from_urls(_urls,docs=docs)
            except FunctionTimedOut as e:
                print(f'尝试使用jina_reader获取网页内容超时！只获取到{len(docs)}个文档。')
            except Exception as e:
                print(f"尝试使用jina_reader获取网页内容失败！只获取到{len(docs)}个文档。")
            finally:
                return docs

    # if docs:
    #     # 只保留page_content长度>50的
    #     docs = [doc for doc in docs if len(doc.page_content.strip())>50]
    return docs

@func_set_timeout(timeout_value)
def get_tavily_search_result_documents(query,max_doc_nums=4):
    
    tavily_search = TavilySearchResults(max_results=max_doc_nums)
    docs = tavily_search.invoke({"query": query})
    documents = [Document(page_content=doc['content'], metadata={"source": doc['url'],"search_engine":"tavily_search"}) for doc in docs]
    return documents

# 最终的方法调用，建议用户只调用该方法
# 根据query，返回最多max_doc_nums个结果文档，返回结果类型为:list[langchain_core.documents.base.Document]
@func_set_timeout(timeout_value)
async def get_web_search_documents(query,max_doc_nums=4):
    try:
        docs = await _get_web_search_documents(query,max_doc_nums=max_doc_nums)
        for doc in docs:        
            page_content = doc.page_content

            webpage_title = ""
            webpage_description = ""
            metadata = doc.metadata
            if metadata:
                webpage_title = metadata.get("title","")
                if webpage_title:
                    webpage_title = "【标题】" + webpage_title + " " 
                webpage_description = metadata.get("description","")
                if webpage_description:
                    webpage_description = " " + "【描述】" + webpage_description  
            if page_content:
                if (webpage_title or webpage_description):
                        page_content = "【内容】" + page_content       
                        doc.page_content = webpage_title + page_content + webpage_description
        return docs

    except Exception as e:
        logger.error(f"获取网络搜索文档结果失败:{e}")
        return []

@func_set_timeout(timeout_value)
async def _get_web_search_documents(query,max_doc_nums=4):
    docs = []
    if not query:
        print(f"提交到Web_Search的query为空！直接返回空列表。")
        return docs
    try:
        tavily_search_query = convert_search_query(query,join_character=None)          
        print(f'{tavily_search_query=}')
        docs = get_tavily_search_result_documents(tavily_search_query,max_doc_nums=max_doc_nums)
        print(f'使用tavily_search,获取到{len(docs)}个文档。')
        return docs
    except FunctionTimedOut as e:
        logger.warning(f"get_tavily_search_result_documents执行超时:{e}")
    except Exception as e:
        logger.warning(f'直接调用TavilySearchResults获得搜索结果失败:{e}')


    # 如果上面的代码执行正常（没有异常抛出），就会正常return docs，不会执行下面的代码
    query = convert_search_query(query)
    
    # 获取搜索引擎结果列表URLs
    urls = []
    try:
        urls = get_search_result_links(query)    
    except FunctionTimedOut as e:
        print(f'获取搜索引擎URLs列表超时！')
        print(f"失败的原因为：{e}") 
    except Exception as e:
        print('搜索引擎获取URLs结果失败！')
        print(f"失败的原因为：{e}")  
    finally:
        print(f'获取到{len(urls)}个urls')
        print(f"Finally:继续向下执行！") 
       
    # 根据获取到的搜索引擎结果列表URLs，提取网页文档结果
    docs = None
    if urls:
        try:
            docs = await get_search_result_documents(urls,query,max_doc_nums=max_doc_nums)
            if docs:
                return docs        
        except FunctionTimedOut as e:
            print(f'搜索网页文档结果超时！')
            print(f"失败的原因为：{e}") 
        except Exception as e:
            print('搜索网页文档结果失败！')
            print(f"失败的原因为：{e}") 
        finally:
            print(f'获取到{len(docs)}个docs')
            print(f"Finally:继续向下执行！")             
    
    #如果前面未能获取到实际的结果文档，（即使是中文搜索）最后也转向使用TavilySearchResults
    if not docs:
        try:           
           print(f'{tavily_search_query=}')
           docs = get_tavily_search_result_documents(tavily_search_query,max_doc_nums=max_doc_nums)
           print(f'中文query，但由于使用Baidu、Bing、Jina未能获得最终网页文档结果。转向使用tavily_search,获取到{len(docs)}个文档。')
           return docs
        except Exception as e:
            print('直接调用TavilySearchResults获得搜索结果失败！')
            print(f"失败的原因为：{e}")
        finally:
            return docs if docs else []     
        
# Clean
def replace_multiple_newlines(text):
    return re.sub(r'\n+', '\n', text)        

if __name__ == "__main__":
    queries = ['中国科学技术大学','how python install langchain langgraph package','合肥大蜀山和科学岛','合肥大蜀山 科学岛','合肥八中 校区数量','   合肥八中   校区数量   ']
    queries = ['中国科学技术大学','how python install langchain langgraph package','合肥大蜀山和科学岛','合肥大蜀山 科学岛','合肥八中 校区数量','   合肥八中   校区数量   ']
    for query in queries:
        print('~~'*20)
        print('~~'*20)
        print(f'原始query={query}')
        docs = asyncio.run(get_web_search_documents(query,max_doc_nums=10))
        print(f"获取到{len(docs)}个网页文档")
        for doc in docs:
            print(f"文档的类型为{type(doc).__name__}")
            print(f"......文档的source为{doc.metadata.get('source',None)}")
