import os
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from fake_useragent import UserAgent

from langchain_core.documents import Document
from langchain_community.document_loaders import WebBaseLoader
from langchain_community.document_loaders import SeleniumURLLoader
from langchain_community.document_loaders import AsyncHtmlLoader
from langchain_community.document_loaders import NewsURLLoader #需导入结巴分词的词典，严重拖慢速度
from langchain_community.document_loaders import PlaywrightURLLoader
from langchain_community.document_transformers import Html2TextTransformer

from langchain_community.tools.tavily_search import TavilySearchResults

from jqcode.c0_init_env_models import get_es_connection, get_es_searchstore, get_es_searchstore_index_documents

from func_timeout import func_set_timeout, FunctionTimedOut

import urllib3
urllib3.disable_warnings()

timeout_value = 60
USING_JINA_AI_READER = os.getenv("USING_JINA_AI_READER",True)
jina_reader_prefix = 'https://r.jina.ai/'
valid_prefix='http://www.baidu.com/link?url='

filter_out_host = ['github.com','google.com','huggingface.co'] #这些网站的网页内容，基本无法成功访问、获取
html2text = Html2TextTransformer()

try:
    ua = UserAgent(browsers=['edge', 'chrome'])
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
# print(convert_search_query('   合肥大蜀山     科学岛   '))
# print(convert_search_query('   合肥大蜀山     科学岛   ',join_character=None))



def is_query_chinese(query):
    pattern = re.compile(r'[\u4e00-\u9fa5]')
    return bool(re.search(pattern, query))
# print(is_query_chinese('   合肥大蜀山     科学岛   '))
# print(is_query_chinese('   text/html,application/xhtml+xml   '))
# print(is_query_chinese('   text/html,application/xhtml+xml 详细信息  '))


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

@func_set_timeout(timeout_value)
def get_webpages_texts_by_langchain_document_loader_from_urls(urls,document_loader_class=AsyncHtmlLoader, max_doc_nums=4):
    if document_loader_class==NewsURLLoader:
        loader = document_loader_class(urls,text_mode=True,nlp=True,continue_on_failure=True)
        docs = loader.load()
    elif document_loader_class==WebBaseLoader:
        loader = document_loader_class(urls,autoset_encoding=True,requests_kwargs ={'verify':False},verify_ssl=False,requests_per_second=max_doc_nums,raise_for_status=False,continue_on_failure=True)
        docs = loader.load()
    elif document_loader_class==AsyncHtmlLoader:
        loader = document_loader_class(urls,autoset_encoding=True,requests_kwargs ={'verify':False},verify_ssl=False,requests_per_second=max_doc_nums,raise_for_status=False,ignore_load_errors=True)
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
        raise NotImplementedError(f'{document_loader_class}暂不支持，当前支持的Web Document Loaders为：WebBaseLoader,NewsURLLoader, SeleniumURLLoader,AsyncHtmlLoader,PlaywrightURLLoader')
    if docs:
        docs = html2text.transform_documents(docs)
        # 只保留page_content长度>50的
        docs = [doc for doc in docs if len(doc.page_content.strip())>50]
        return docs
    else:
        return []
    

@func_set_timeout(timeout_value)
def get_webpages_texts_by_jina_ai_reader_from_urls(urls,docs=[]):
        session = requests.Session()
        session.headers = {"x-respond-with": "html"}
        for url in urls:
            jina_url = jina_reader_prefix + url
            # print(f"尝试使用jina_reader: {jina_url}")
            response = session.get(url=jina_url)            
            if response.status_code!= 200:
                print(f"jina_reader获取{jina_url}失败: （response.status_code != 200）")
            else:
                text = re.sub(r'\n\n+', '\n\n', response.text)
                soup = BeautifulSoup(text, "lxml")
                title = soup.title.string
                doc = Document(page_content=text, metadata={"source": jina_url,'title':title})
                docs.append(doc)
        docs = html2text.transform_documents(docs)
        # 只保留page_content长度>50的
        docs = [doc for doc in docs if len(doc.page_content.strip())>50]
        return docs
# docs = get_webpages_texts_by_jina_ai_reader_from_urls(['http://www.jqsoft.net/','https://github.com/jina-ai/reader'])

def get_search_result_documents(urls,query,document_loader_class=AsyncHtmlLoader,max_doc_nums=4,filter_out_host = filter_out_host):
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
        urls = urls[:max_doc_nums]
        print(f'拟获取前{max_doc_nums}条Urls的搜索结果：')
    else:
        print(f'拟获取全部{url_nums}条Urls的搜索结果：')

    # for i,url in enumerate(urls):
    #     print('-'*2 + f"[{i}] {url}")

    docs = []
    try:
        docs = get_webpages_texts_by_langchain_document_loader_from_urls(urls,document_loader_class=document_loader_class, max_doc_nums=max_doc_nums)
    except FunctionTimedOut as e:
        print(f'直接获取URLs网页超时！只获取到{len(docs)}个文档。')

    except Exception as e:
        print(f'直接获取URLs网页内容失败！只获取到{len(docs)}个文档。')

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


                print(f"继续尝试使用jina_reader获取{len(_urls)=}个网页内容")
            try:
                docs = get_webpages_texts_by_jina_ai_reader_from_urls(_urls,docs=docs)
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

def get_tavily_search_result_documents(query,max_doc_nums=4):
    
    tavily_search = TavilySearchResults(max_results=max_doc_nums)
    docs = tavily_search.invoke({"query": query})
    documents = [Document(page_content=doc['content'], metadata={"source": doc['url']}) for doc in docs]
    return documents
# query = 'who is playing in the super bowl'
# _query = convert_search_query(query)
# docs1 = get_tavily_search_result_documents(query)
# docs2 = get_tavily_search_result_documents(_query)
# docs = get_tavily_search_result_documents('合肥大蜀山和科学岛')
# for doc in docs:
#     print('\n\n')
#     print(doc)

# 最终的方法调用，建议用户只调用该方法
# 根据query，返回最多max_doc_nums个结果文档，返回结果类型为:list[langchain_core.documents.base.Document]
def get_web_search_documents(query,max_doc_nums=4):
    docs = []
    if not query:
        print(f"提交到Web_Search的query为空！直接返回空列表。")
        return docs   
    
    tavily_search_query = convert_search_query(query,join_character=None) 

    if not is_query_chinese(query):#直接调用TavilySearchResults获得搜索结果，List[Document]
        try:           
           print(f'{tavily_search_query=}')
           docs = get_tavily_search_result_documents(tavily_search_query,max_doc_nums=max_doc_nums)
           print(f'非中文，使用tavily_search,获取到{len(docs)}个文档。')
           return docs
        except Exception as e:
            print('直接调用TavilySearchResults获得搜索结果失败！')
            print(f"失败的原因为：{e}")  

    query = convert_search_query(query)
    
    # 获取搜索引擎结果列表URLs
    urls = None
    try:
        urls = get_search_result_links(query)
    except Exception as e:
        print('搜索引擎获取URLs结果失败！')
        print(f"失败的原因为：{e}")  

    # 根据获取到的搜索引擎结果列表URLs，提取网页文档结果
    docs = None
    if urls:
        try:
            docs = get_search_result_documents(urls,query,max_doc_nums=max_doc_nums)
            return docs
        except Exception as e:
            print('搜索网页文档结果失败！')
            print(f"失败的原因为：{e}")  
    
    #如果前面未能获取到实际的结果文档（即使是中文搜索），最后也转向使用TavilySearchResults
    if not docs:
        try:           
           print(f'{tavily_search_query=}')
           docs = get_tavily_search_result_documents(tavily_search_query,max_doc_nums=max_doc_nums)
           print(f'中文query，但由于使用Baidu、Bing、Jina未能获得最终网页文档结果。转向使用tavily_search,获取到{len(docs)}个文档。')
           return docs
        except Exception as e:
            print('直接调用TavilySearchResults获得搜索结果失败！')
            print(f"失败的原因为：{e}")  
    

if __name__ == "__main__":
    queries = ['who is playing in the super bowl','中国科学技术大学','how python install langchain langgraph package','合肥大蜀山和科学岛','合肥大蜀山 科学岛','合肥八中 校区数量','   合肥八中   校区数量   ']
    for query in queries:
        print('~~'*20)
        print('~~'*20)
        print(f'原始query={query}')
        docs = get_web_search_documents(query)
        print(f"获取到{len(docs)=}个网页文档")
        for doc in docs:
            print(f"文档的类型为{type(docs[0])}")
