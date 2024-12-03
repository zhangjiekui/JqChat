# https://github.com/run-llama/llama_index/blob/main/docs/docs/examples/property_graph/property_graph_neo4j.ipynb
user = 'neo4j'
pwd = 'neo4jneo4j'

from llama_index.core import SimpleDirectoryReader
from llama_index.core import Settings
from llama_index.llms.localai import LocalAI
from jqcode.jq_readers.jqkj_readers import JqkjSimpleDirectoryReader
input_file_dir = fr'/data/projects/JqChatV2/JqChat/jqcode/jq_readers/.test_files/.testinputdocs'
input_files= [fr'/data/projects/JqChatV2/JqChat/jqcode/jq_readers/.test_files/.testinputdocs/PPQA000_质量保证过程.doc']
# reader = JqkjSimpleDirectoryReader(input_files=input_files,exclude_hidden = False)
reader = SimpleDirectoryReader(input_file_dir,exclude_hidden = False)

documents =reader.load_data()
documents = documents[0:2]
# _documents = [doc.metadata.pop('file_doc_tree_jq') for doc in documents]

from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore

# Note: used to be `Neo4jPGStore`
graph_store = Neo4jPropertyGraphStore(
    username=user,
    password=pwd,
    url="bolt://10.1.150.105:7687",
)

from llama_index.core import PropertyGraphIndex
from llama_index.embeddings.xinference import XinferenceEmbedding
from llama_index.llms.openai import OpenAI
from llama_index.core.indices.property_graph import SchemaLLMPathExtractor
from jqcode.jq_agent.c0_init_env_models import env_models_instance


llm = env_models_instance.chat_model
llm_model_api_key = env_models_instance.llm_model_api_key
llm_model_base_url= env_models_instance.llm_model_base_url
llm_model_name = env_models_instance.llm_model_name
embedding_model_name = env_models_instance.embedding_model_name
embedding_model_base_url = env_models_instance.embedding_model_base_url

# openai_llm_model = OpenAI(model=llm_model_name, temperature=0.0,tool_choice='auto',api_base = llm_model_base_url,api_key = llm_model_api_key) 
local_llm_model = LocalAI(model=llm_model_name, temperature=0.0,api_base = llm_model_base_url,api_key = llm_model_api_key,globally_use_chat_completions=True,pydantic_program_mode="llm",kwargs={"tool_choice":'auto'})
response = local_llm_model.complete("Hello!")
embed_model = XinferenceEmbedding(base_url='http://10.1.150.106:9997',model_uid=embedding_model_name,timeout=600000)
# embed_model = LangchainEmbedding(embed_model)
Settings.embed_model = embed_model
Settings.llm = local_llm_model

# index = PropertyGraphIndex.from_documents(
#     documents,
#     embed_model=embed_model,
#     kg_extractors=[
#         SchemaLLMPathExtractor(
#             llm=local_llm_model,
#         )
#     ],
#     property_graph_store=graph_store,
#     show_progress=True,
#     # kwargs={"tool_choice":'auto'}
#     tool_choice = 'auto'  
    
# )

index = PropertyGraphIndex.from_existing(
    embed_model=embed_model,
    kg_extractors=[
        SchemaLLMPathExtractor(
            llm=local_llm_model,
        )
    ],
    property_graph_store=graph_store,
    show_progress=True,
    # kwargs={"tool_choice":'auto'}
    tool_choice = 'auto'  
    
)

retriever = index.as_retriever(
    include_text=True,  # include source text in returned nodes, default True
)

# for sub_retriever in retriever.sub_retrievers:
#     if hasattr(sub_retriever,'_llm'):
#         sub_retriever._llm.model = llm_model_name
    

nodes1 = retriever.retrieve("质量保证过程的批准人是谁？")
nodes2 = retriever.retrieve("张结魁")
nodes3 = retriever.retrieve("质量保证过程")
nodes4 = retriever.retrieve("李友涛")

nodes = nodes1 + nodes2 + nodes3 + nodes4

context = ''
for node in nodes:
    # print(node.text)
    context += node.text

query = f"根据以下内容:{context}。回答问题:上文中涉及的全部员工（人）有哪些，对应的工作内容/职责分工是什么？谁是批准人？"    
response = local_llm_model.complete(query)
print(response.text)
