import os
import asyncio
from langchain.schema import Document
from langchain_neo4j import Neo4jVector
from langchain_openai import ChatOpenAI
from jqcode.jq_knowledge_manegement.chatchat.server.localai_embeddings import LocalAIEmbeddings
from graphiti_core import Graphiti
from graphiti_core.llm_client import OpenAIClient,LLMConfig,LLMClient
from graphiti_core.cross_encoder.client import CrossEncoderClient

# OpenAIRerankerClient
from graphiti_core.cross_encoder.bge_reranker_client import BGERerankerClient
from graphiti_core.embedder import EmbedderClient, OpenAIEmbedder,OpenAIEmbedderConfig
from graphiti_core.nodes import EpisodeType
from graphiti_core.utils.maintenance.graph_data_operations import clear_data
from datetime import datetime, timezone
# from jqcode.jq_agent.c0_init_env_models import env_models_instance
from jqcode.jq_splitters.jq_docx_tree_text_splitter import load_project_env

load_project_env()

class JqGraphiti(Graphiti):
    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        database:str = 'neo4j',
        llm_client: LLMClient | None = None,
        embedder: EmbedderClient | None = None,
        cross_encoder: CrossEncoderClient | None = None,
        store_raw_episode_content: bool = True,
    ):
        super().__init__(uri=uri,user=user,password=password,llm_client=llm_client,embedder=embedder,cross_encoder=cross_encoder,store_raw_episode_content=store_raw_episode_content)
        os.environ['DEFAULT_DATABASE']=database
        self.database = database
       

embed_model_config = OpenAIEmbedderConfig(embedding_model='bce-embedding-base_v1',api_key="NotNeed",base_url='http://10.1.150.106:9997/v1',embedding_dim=768)
embed_model = OpenAIEmbedder(config=embed_model_config)
reranker =None
# embed_model,embedding_model_8k,reranker = env_models_instance.get_emb_8k_rerank_model()
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

llm_config = LLMConfig(
    api_key='abc123',
    model='qwen25b70',
    base_url="http://10.1.150.105:9997/v1",
    max_tokens = 8000,
    temperature= 0.1
    ) 
# llm_config = LLMConfig(
#     api_key='sk-9051c1a25842405aa650623c510889ad',
#     model='qwen-turbo',
#     base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
#     max_tokens = 2000,
#     temperature= 0.1
#     ) 
llm_client = OpenAIClient(config=llm_config)
# Initialize Graphiti
graphiti = Graphiti(url, username, password,llm_client=llm_client,embedder=embed_model,cross_encoder=reranker)


async def setup_graphiti():
    # CAREFUL: empty's the graph
    await clear_data(graphiti.driver)
    # Initialize the graph database with graphiti's indices. This only needs to be done once
    await graphiti.build_indices_and_constraints()

# Add episodes
episodes = [
    "Kamala Harris is the Attorney General of California. She was previously "
    "the district attorney for San Francisco.",
    "As AG, Harris was in office from January 3, 2011 – January 3, 2017",
]



async def add_episode(episodes=episodes):
    # CAREFUL: empty's the graph
    await setup_graphiti()
    for i, episode in enumerate(episodes):
        await graphiti.add_episode(
            group_id='group1',
            name=f"Freakonomics Radio {i}",
            episode_body=episode,
            source=EpisodeType.text,
            source_description="podcast",
            reference_time=datetime.now(timezone.utc)
        )
    print("add_episode completed!")


# Search the graph
# Execute a hybrid search combining semantic similarity and BM25 retrieval
# Results are combined and reranked using Reciprocal Rank Fusion
async def search(query='Who was the California Attorney General?',center_node_uuid=None, group_ids=['group1']):
    results = await graphiti.search(query='Who was the California Attorney General?',center_node_uuid=center_node_uuid, group_ids=group_ids)
    return results


if __name__ == "__main__":
     text = '''
        安徽晶奇网络科技股份有限公司：
        根据【上级单位名称】于【印发日期】正式印发的《【文件名称】》文件精神，明确要求我单位需在【完成期限】前实施【上级单位要求实施的项目内容】。
        鉴于该项目实施存在客观紧迫性，加之相关系统长期由贵公司承建开发并维护至今，为确保系统的稳定性和连续性，因此，从项目实施的效率和安全性角度考量，我单位认为不宜改由其他供应商处承担相关工作。
        请贵公司在收到本函之日起【具体完成时限，体现项目紧迫性】日内，按照我单位工作方案要求完成【具体实施的内容】相关工作。
        上述服务
        '''
     text = '安徽晶奇网络科技股份有限公司'
     asyncio.run(add_episode(text))
    #  results = asyncio.run(search('晶奇网络科技'))
    #  print(results)
    #  results = asyncio.run(search('李友涛'))
     results = asyncio.run(search())
     print(results)

