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
    Literal
)
import aiohttp
from aiohttp import request
from aiomultiprocess import Pool
import requests
from requests.compat import _resolve_char_detection #()chardat
from bs4 import BeautifulSoup
import html2text
from langchain_core.documents import Document
from langchain_community.document_loaders import AsyncHtmlLoader
from langchain_community.document_loaders.async_html import _build_metadata
from langchain_community.tools.tavily_search import TavilySearchResults

from func_timeout import func_set_timeout, FunctionTimedOut
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from chromedriver_py import binary_path # this will get you the path variable

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
#这些网站的网页内容，基本无法成功访问、获取,要么没有实质性性的文本内容
filter_out_host = ("image.baidu.com","haokan.baidu.com","map.baidu.com","www.bilibili.com","tv.sohu.com",'github.com','google.com','huggingface.co','web.archive.org') 
html2text_handler = html2text.HTML2Text()
html2text_handler.ignore_images=True
html2text_handler.ignore_links=True
html2text_handler.ignore_mailto_links=True
chardet = _resolve_char_detection()

def get_user_agents():
    try:
        from fake_useragent import UserAgent
        ua = UserAgent()
        user_agents = ua.random
    except:
        print('使用fake_useragent获取user_agents失败，请检查!只好使用预定义的user_agents，但反爬虫机制的存在，成功获取搜索结果的概率会降低！')
        user_agents = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36 Edg/108.0.1462.76'
    return user_agents

def is_query_chinese(query):
    pattern = re.compile(r'[\u4e00-\u9fa5]')
    return bool(re.search(pattern, query))

def convert_search_query(query,join_character='+'):
    '''
    join_character:
        取值：‘+’ （默认），其他情况下传入None
        使用Baidu、Bing搜索引擎时，需要用 ‘+’ 连接搜索关键词 （代替空格）
        但使用TavilySearch时，不需要 ‘+’ 
    '''
    query = query.strip()
    query = re.sub(r' +', ' ', query)
    if is_query_chinese(query):        
        if join_character:
            query_terms = query.strip().split(' ')
            query = join_character.join(query_terms)
    return query

def get_random_elements(my_list, N):
    random_elements = random.sample(my_list, N)
    return random_elements

class JqSeleniumSearchBaiduAndSearXNG:
    """将百度搜索和SearXNG结合起来，一步获取搜索结果Urls列表`.

    This is useful for loading pages that require javascript to render.

    Attributes:
        se_searxng_host:str,要使用的SearXNG，可从https://searx.space/查看获取
        filter_out_host:tuple,要过滤掉的网站或域名，要么是基本无法成功访问、获取（如Google）,要么是没有实质性性的文本内容（如视频、地图）
        browser (str): The browser to use, either 'chrome' or 'firefox'.
        binary_location (Optional[str]): The location of the browser binary.
        executable_path (Optional[str]): The path to the browser executable.
        headless (bool): If True, the browser will run in headless mode.
        arguments [List[str]]: List of arguments to pass to the browser.
    """
    def __init__(
        self, 
        filter_out_host:tuple = filter_out_host,       
        se_searxng_host:str ="https://search.inetol.net",        
        browser:Literal["chrome", "firefox"] = "chrome",
        binary_location: Optional[str] = None,
        executable_path: Optional[str] = binary_path,
        headless: bool = True,
        arguments: List[str] = ['--disable-gpu','--disable-gpu','--disable-dev-shm-usage','--remote-debugging-pipe'],
    ):
        try:
            import selenium  # noqa:F401
        except ImportError:
            raise ImportError(
                "selenium package not found, please install it with "
                "`pip install selenium`"
            )

        self.browser = browser
        self.binary_location = binary_location
        self.executable_path = executable_path
        self.headless = headless
        self.arguments = arguments
        self.driver = self._get_driver()
        
        self.se_baidu_host:str="https://www.baidu.com"
        self.se_baidu_url = f"{self.se_baidu_host}/s?ie=utf-8&tn=baidu&wd="
        self.se_baidu_params:str=""
        self.se_baidu_valid_prefix:tuple=('http://www.baidu.com/link?url=',)
        self.se_baidu_invalid_prefixes:tuple = ("https://image.baidu.com","https://haokan.baidu.com","https://map.baidu.com")
        self.se_baidu_invalid_fields_or_suffixes:str = ("?anchor=","?fr=",)
        
        self.se_searxng_host:str=se_searxng_host
        self.se_searxng_url = f"{self.se_searxng_host}/search?q="
        self.se_searxng_params:str='&category_general=1&language=all&time_range=&safesearch=2&theme=simple'
        self.se_searxng_valid_prefix:tuple=('http',)
        self.se_searxng_invalid_prefixes:tuple = (self.se_searxng_host,'https://github.com/searxng',)
        self.se_searxng_fields_or_suffixes:tuple = ()
        self.session = requests.Session()
        
        self.invalid_domains:tuple =filter_out_host

    def _get_driver(self) -> Literal["Chrome", "Firefox"]:
        """Create and return a WebDriver instance based on the specified browser.

        Raises:
            ValueError: If an invalid browser is specified.

        Returns:
            Union[Chrome, Firefox]: A WebDriver instance for the specified browser.
        """
        if self.browser.lower() == "chrome":
            from selenium.webdriver import Chrome
            from selenium.webdriver.chrome.options import Options as ChromeOptions
            from selenium.webdriver.chrome.service import Service

            chrome_options = ChromeOptions()

            for arg in self.arguments:
                chrome_options.add_argument(arg)

            if self.headless:
                chrome_options.add_argument("--headless")
                chrome_options.add_argument("--no-sandbox")
            if self.binary_location is not None:
                chrome_options.binary_location = self.binary_location
            if self.executable_path is None:
                return Chrome(options=chrome_options)
            return Chrome(
                options=chrome_options,
                service=Service(executable_path=self.executable_path),
            )
        elif self.browser.lower() == "firefox":
            from selenium.webdriver import Firefox
            from selenium.webdriver.firefox.options import Options as FirefoxOptions
            from selenium.webdriver.firefox.service import Service

            firefox_options = FirefoxOptions()

            for arg in self.arguments:
                firefox_options.add_argument(arg)

            if self.headless:
                firefox_options.add_argument("--headless")
            if self.binary_location is not None:
                firefox_options.binary_location = self.binary_location
            if self.executable_path is None:
                return Firefox(options=firefox_options)
            return Firefox(
                options=firefox_options,
                service=Service(executable_path=self.executable_path),
            )
        else:
            raise ValueError("Invalid browser specified. Use 'chrome' or 'firefox'.")

    def search(self,query:str):
        query = convert_search_query(query)
        search_baidu_url = self.se_baidu_url + query + self.se_baidu_params
        logger.warning(f"Baidu搜索:{search_baidu_url}") 
        self.driver.get(search_baidu_url)
        page_content = self.driver.page_source
        soup = BeautifulSoup(page_content, "lxml")
        baidu_result_links = [urljoin(self.se_baidu_url, a["href"]) for a in soup.find_all("a", href=True) if a["href"]]
        for valid_prefix in self.se_baidu_valid_prefix:
            baidu_result_links = [link for link in baidu_result_links if link.startswith(valid_prefix)]            
        baidu_result_links_without_repeated = sorted(set(baidu_result_links),key=baidu_result_links.index)
        baidu_result_links_real = []
        # 获取百度搜索结果列表的真实地址
        # 如'http://www.baidu.com/link?url=h6vPEeCUjt5yEvYIVRcHupL3R0fiHI7Fw-402uHI2LUZMFMZTDysUjwbOq1XUqbC' ==> 'https://www.hfss.gov.cn/'
        for url in baidu_result_links_without_repeated:
            response = self.session.get(url,allow_redirects=False)
            url = response.headers.get("Location",None)
            if url:
                if not url.startswith(self.se_baidu_invalid_prefixes):
                    if url not in baidu_result_links_real:
                        baidu_result_links_real.append(url)
            else:
                logger.warning(f"无法获取的百度搜索结果的真实URL，所以跳过{url}")
        
        search_searxng_url = self.se_searxng_url + query + self.se_searxng_params
        logger.warning(f"SearXNG搜索:{search_searxng_url}")
        self.driver.get(search_searxng_url)
        page_content = self.driver.page_source
        soup = BeautifulSoup(page_content, "lxml")
        searxng_result_links = [urljoin(self.se_searxng_url, a["href"]) for a in soup.find_all("a", href=True) if a["href"]]
            
        for valid_prefix in self.se_searxng_valid_prefix:
            searxng_result_links = [link for link in searxng_result_links if link.startswith(valid_prefix)]
            
        searxng_result_links_without_repeated = sorted(set(searxng_result_links),key=searxng_result_links.index)
        searxng_result_links_real = []
        for url in searxng_result_links_without_repeated:     
            if not url.startswith(self.se_searxng_invalid_prefixes): 
                if not url in searxng_result_links_real:
                     searxng_result_links_real.append(url)  
            
        _all_urls = baidu_result_links_real + searxng_result_links_real
        _all_urls = sorted(set(_all_urls),key=_all_urls.index)
        all_urls = []
        # all_urls = ['https://baike.baidu.com/item/%E5%90%88%E8%82%A5%E5%A4%A7%E8%9C%80%E5%B1%B1%E5%9B%BD%E5%AE%B6%E6%A3%AE%E6%9E%97%E5%85%AC%E5%9B%AD/22176384?anchor=1#1'] 
        # all_urls +=['https://baike.baidu.com/item/%E5%90%88%E8%82%A5%E5%A4%A7%E8%9C%80%E5%B1%B1%E5%9B%BD%E5%AE%B6%E6%A3%AE%E6%9E%97%E5%85%AC%E5%9B%AD/22176384?anchor=3#3']
        # all_urls +=['https://baike.baidu.com/item/%E5%90%88%E8%82%A5%E5%A4%A7%E8%9C%80%E5%B1%B1%E5%9B%BD%E5%AE%B6%E6%A3%AE%E6%9E%97%E5%85%AC%E5%9B%AD/22176384']
        for url in _all_urls:
            if "baidu.com" in url:
                for invalid_field_or_suffix in self.se_baidu_invalid_fields_or_suffixes:
                    if invalid_field_or_suffix in url:
                        new_url = url.split(invalid_field_or_suffix)[0]
                        if new_url not in all_urls:
                            all_urls.append(new_url)
            else:
                if url not in all_urls:
                    all_urls.append(url)       

        for invalid_domain in self.invalid_domains:
            for url in all_urls:
                if invalid_domain in url:
                     all_urls.remove(url)

        logger.warning(f"Baidu和SearXNG共获取到{len(all_urls)=}个搜索结果")
                
        return all_urls

class BaiduSearch:
    def __init__(self):
        # 请求头信息
        self.HEADERS = {"Accept": "text/html",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": get_user_agents(),
            "Referer": "https://www.baidu.com/",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "zh-CN,zh;q=0.9"
        }
        self.url = "https://www.baidu.com/s?ie=utf-8&tn=baidu&wd=" 
        self.valid_prefix = 'http://www.baidu.com/link?url='
        self.invalid_prefixes = ("https://image.baidu.com")
        self.invalid_fields = "?anchor="


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
        
        filtered_real_and_valid_urls = []
        for url in valid_links_without_repeated:
            with session.get(url,headers=session.headers,allow_redirects=False) as response:
                real_url = response.headers.get("Location",None)
                if real_url:
                    if not real_url.startswith(self.invalid_prefixes):
                        if self.invalid_fields in real_url:
                            real_url = real_url.split(self.invalid_fields)[0]
                        if real_url not in filtered_real_and_valid_urls:
                            filtered_real_and_valid_urls.append(real_url)
                else:
                    logger.debug(f"无法获取的百度搜索结果的真实URL，所以跳过{url}")        
        return filtered_real_and_valid_urls

class BingSearch:
    def __init__(self,):
        self.HEADERS = {"User-Agent": get_user_agents()}
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
    baidu_searxng =JqSeleniumSearchBaiduAndSearXNG() 
    urls = baidu_searxng.search(query)
    return urls

@func_set_timeout(timeout_value)
def _get_search_result_links(query):
    baidu_searxng =JqSeleniumSearchBaiduAndSearXNG() 
    baidu = BaiduSearch()
    bing =  BingSearch()
    jina =  JinaSearch()
    urls = []  
    query = convert_search_query(query)    
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
        preserve_order: bool = False,
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
        self, url: str, retries: int = 1, cooldown: int = 1, backoff: float = 1
    ) -> str:
        
        text = ""
        real_url = ""
        try:
            async with aiohttp.ClientSession(trust_env=self.trust_env) as session:
                for i in range(retries):
                    # print(f"retries:{i} for {url}")
                    try:
                        async with session.get(
                            url,
                            headers=self.session.headers,
                            ssl=None if self.session.verify else False,
                            allow_redirects=False,
                            **self.requests_kwargs,
                        ) as response:
                            try:                                
                                text = await response.text()
                            except UnicodeDecodeError:
                                try:
                                    encoding = chardet.detect(response._body)["encoding"]                                
                                    text = await response.text(encoding=encoding)
                                except UnicodeDecodeError as e:
                                    logger.error(f"Failed to decode content from {url} using detected {encoding=}:{e}")
                                
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
        async for url, real_url, text in self._lazy_fetch_all(
            self.web_paths, self.preserve_order
        ):
            if text:
                yield self._to_document(url, real_url, text)        
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
async def get_webpages_texts_by_langchain_document_loader_from_urls(urls,question,query,max_doc_nums=4,header_template=None,timeout_seconds:int=10):
    """
    Args:
        question:str 用户的问题
        query：搜索引擎query
        两者可能一致
    """    
    from jqcode.langgraph_in_class import retrieval_document_relevance_grader 
    requests_per_second = min(len(urls),max_doc_nums*2)   
    loader = AsyncHtmlLoaderBypassException(urls,requests_per_second=requests_per_second,header_template=header_template, autoset_encoding=True,verify_ssl=False,raise_for_status=False,ignore_load_errors=True,preserve_order=False,requests_kwargs={"timeout":timeout_seconds})
    # async with async
    docs_async_generator = loader.alazy_load()        
    docs_transformed_completed = []
    try:
        async for doc in docs_async_generator:                                         
            page_content = html2text_handler.handle(doc.page_content).strip()
            length = len(page_content)
            if 20000>length>500: # 只保留page_content长度>500的，太短了意味着可能没有实质性的文本内容；或者<20000的，太长了会导致无法获取retrieval_document_relevance_grader相关性评分
                transformed_document = Document(page_content=page_content, metadata={**doc.metadata})
                try:
                    if question!=query:
                        q_str = f"用户问题：'{question}'及'搜索语句: {query}'"
                    else:
                        q_str = question
                    # grade = retrieval_document_relevance_grader.invoke({"document":page_content,"question":q_str})
                    grade = await retrieval_document_relevance_grader.ainvoke({"document":page_content,"question":q_str})
                    relavant = grade.k
                    if relavant == "yes":                         
                        docs_transformed_completed.append(transformed_document)
                except Exception as e:
                    logger.warning(f"无法获取网页内容与问题的相关性评分：{e}，但仍然加入")
                    docs_transformed_completed.append(transformed_document) 
            if len(docs_transformed_completed) == max_doc_nums:
                break
    except Exception as e:
            logger.warning(f"出现错误：{e}")             
    
    return docs_transformed_completed

@func_set_timeout(timeout_value)
async def get_webpages_texts_by_jina_ai_reader_from_urls(urls,docs=[],max_doc_nums=4):
        headers = {"x-respond-with": "html"}
        jina_urls = [jina_reader_prefix + url for url in urls]
        # max_doc_nums = len(jina_urls)
        jina_docs = await get_webpages_texts_by_langchain_document_loader_from_urls(jina_urls,max_doc_nums=max_doc_nums,header_template=headers)
        docs += jina_docs
        return docs

@func_set_timeout(timeout_value)
async def get_search_result_documents(urls,question,query,document_loader_class=AsyncHtmlLoader,max_doc_nums=4,filter_out_host = filter_out_host):
    """
    Args:
        question:str 用户的问题
        query：搜索引擎query
        两者可能一致
    """
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
    # if max_doc_nums<url_nums:
    #     # urls = urls[:max_doc_nums]
    #     urls = get_random_elements(urls,max_doc_nums)
    #     print(f'拟随机获取{max_doc_nums}条Urls的搜索结果')
    # else:
    #     print(f'拟获取全部{url_nums}条Urls的搜索结果')

    docs = [] 
    try:
        docs =await get_webpages_texts_by_langchain_document_loader_from_urls(urls,question,query,max_doc_nums=max_doc_nums)
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
                    url_getted = d.metadata.get('source',False)
                    if url_getted:
                        urls_getted.append(url_getted)
                _urls = list(set(urls) - set(urls_getted)) 
                print('================================================')
                print(f'       -------urls:{len(urls)}')
                print(f'       -------urls_getted:{len(urls_getted)}')
                print(f'       -------_urls:{len(_urls)}')
                print('================================================')
                jina_num = max_doc_nums - len(docs)
                jina_num = min(jina_num,len(_urls))
                print(f"继续尝试使用jina_reader再从{len(_urls)=}个urls中获取{jina_num}网页内容")
            try:
                docs = await get_webpages_texts_by_jina_ai_reader_from_urls(_urls,docs=docs,max_doc_nums=jina_num)
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
    documents = []
    tavily_search = TavilySearchResults(max_results=max_doc_nums)
    docs = tavily_search.invoke({"query": query})
    if isinstance(docs,list):
        documents = [Document(page_content=doc['content'], metadata={"source": doc['url'],"search_engine":"tavily_search"}) for doc in docs]
        return documents
    else:
        logger.warning(docs)
        raise Exception(docs)
    
    

# 最终的方法调用，建议用户只调用该方法
# 根据query，返回最多max_doc_nums个结果文档，返回结果类型为:list[langchain_core.documents.base.Document]
@func_set_timeout(timeout_value)
async def get_web_search_documents(question,query='',max_doc_nums=6):
    """
    Args:
        question:str 用户的问题
        query：搜索引擎query
        两者可能一致
    """
    print(question)
    print(query)
    try:
        docs = await _get_web_search_documents(question,query,max_doc_nums=max_doc_nums)
        for doc in docs:        
            page_content = doc.page_content

            _webpage_title = ""
            _webpage_description = ""
            metadata = doc.metadata
            if metadata:
                webpage_title = metadata.get("title","")
                if webpage_title:
                    if webpage_title not in page_content:
                        _webpage_title = "【标题】" + webpage_title + " " 
                webpage_description = metadata.get("description","")
                if webpage_description:
                    if webpage_description not in page_content:
                        _webpage_description = " " + "【描述】" + webpage_description  
            if page_content:
                if (_webpage_title or _webpage_description):
                        page_content = "【内容】" + page_content                               
                        doc.page_content = _webpage_title + page_content + _webpage_description
        return docs

    except Exception as e:
        logger.error(f"获取网络搜索文档结果失败:{e}")
        return []

@func_set_timeout(timeout_value)
async def _get_web_search_documents(question,query='',max_doc_nums=4):
    """
    Args:
        question:str 用户的问题
        query：搜索引擎query
        两者可能一致
    """
    docs = []
    if not query:
        print(f"提交到Web_Search的query为空！直接返回空列表。")
        return docs
    try:
        tavily_search_query = convert_search_query(query,join_character=None)
        # raise Exception("测试：不使用tavily_search_query")
                  
        print(f'{tavily_search_query=}')
        docs = get_tavily_search_result_documents(tavily_search_query,max_doc_nums=max_doc_nums)
        print(f'使用tavily_search,获取到{len(docs)}个文档。')
        return docs
    except FunctionTimedOut as e:
        logger.warning(f"get_tavily_search_result_documents执行超时:{e}")
    except Exception as e:
        logger.warning(f'直接调用TavilySearchResults获得搜索结果失败:{e}')


    # 如果上面的代码执行正常（没有异常抛出），就会正常return docs，不会执行下面的代码   
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
            from jq_agent.tools.jq_crawl4ai_batch_crawler import crawl4ai_get_search_result_documents
            docs =  await crawl4ai_get_search_result_documents(urls=urls,question=question,query=query,max_doc_nums=max_doc_nums)
            if not docs:
                raise Exception
        except:
            try:
                docs = await get_search_result_documents(urls,question=question,query=query,max_doc_nums=max_doc_nums)
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
    if docs:
        return docs 
    else:
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
    queries = ['how python install langchain langgraph package','合肥大蜀山和科学岛','合肥大蜀山 科学岛','合肥八中 校区数量','   合肥八中   校区数量   ']
    
    for query in queries:
        print('~~'*20)
        print('~~'*20)
        print(f'原始query={query}')    
       
        
        docs = asyncio.run(get_web_search_documents(query,query,max_doc_nums=4))
        print(f"获取到{len(docs)}个网页文档")
        for doc in docs:
            print(f"文档的类型为{type(doc).__name__}")
            print(f"......文档的source为{doc.metadata.get('source',None)}")
