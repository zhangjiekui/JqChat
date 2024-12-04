import os
from langchain.schema import Document
from langchain_neo4j import Neo4jVector
from langchain_openai import ChatOpenAI
from jqcode.jq_knowledge_manegement.chatchat.server.localai_embeddings import LocalAIEmbeddings



# llm = ChatOpenAI(temperature=0, model_name="gpt-4o")
llm = ChatOpenAI(
        model_name='qwen25b70',
        openai_api_base="http://10.1.150.105:9997/v1",    
        openai_api_key= 'abc123',              
    )
embed_model = LocalAIEmbeddings(model='bce-embedding-base_v1',deployment='bce-embedding-base_v1',api_key="NotNeed",openai_api_base='http://10.1.150.106:9997/v1',base_url='http://10.1.150.106:9997/v1',embedding_ctx_length=512*8,chunk_size=512)

os.environ["NEO4J_URI"] = url =  "bolt://10.1.150.105:7687"
os.environ["NEO4J_USERNAME"] = username = "neo4j"
os.environ["NEO4J_PASSWORD"] = password = "neo4jneo4j"
os.environ['LANGCHAIN_TRACING_V2'] = 'true'
os.environ['LANGCHAIN_ENDPOINT'] = 'https://api.smith.langchain.com'
os.environ['LANGCHAIN_API_KEY'] = "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"


text = '''
        安徽晶奇网络科技股份有限公司：
        根据【上级单位名称】于【印发日期】正式印发的《【文件名称】》文件精神，明确要求我单位需在【完成期限】前实施【上级单位要求实施的项目内容】。
        鉴于该项目实施存在客观紧迫性，加之相关系统长期由贵公司承建开发并维护至今，为确保系统的稳定性和连续性，因此，从项目实施的效率和安全性角度考量，我单位认为不宜改由其他供应商处承担相关工作。
        请贵公司在收到本函之日起【具体完成时限，体现项目紧迫性】日内，按照我单位工作方案要求完成【具体实施的内容】相关工作。
        上述服务产生的费用由我单位与贵公司根据市场公允水平另行商榷，我单位将根据相关规定通过【单一来源】采购方式尽快完成项目采购及合同签署。
        '''
docs = [Document(page_content=text)]

hybrid_db = Neo4jVector.from_documents(
    docs,
    embed_model,
    url=url,
    username=username,
    password=password,
    search_type="hybrid",
)


print(hybrid_db)


index_name = "neo4j"  # default index name
keyword_index_name = "keyword"
existing_graph = Neo4jVector.from_existing_index(
    embed_model,
    url=url,
    username=username,
    password=password,
    index_name=index_name,
    keyword_index_name = keyword_index_name ,
    search_type="hybrid",
)

result = existing_graph.similarity_search("李友涛", k=1)
print(result)

result = existing_graph.similarity_search("安徽晶奇网络科技股份有限公司", k=3)
print(result)

retriever = existing_graph.as_retriever()
result = retriever.invoke("安徽晶奇网络科技股份有限公司")