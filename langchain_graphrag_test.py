from langchain_community.graphs.age_graph import AGEGraph
from langchain_graphrag.indexing.graph_clustering.leiden_community_detector import HierarchicalLeidenCommunityDetector
from langchain_neo4j import GraphCypherQAChain
from jqcode.jq_agent.c0_init_env_models import env_models_instance

pg_vector_store,pg_graph_store,gauss_graph_store,kg_llm_transformer = env_models_instance.get_pg_connection(index_name = 'test6_ok')
llm = env_models_instance.chat_model

# Error:实际上无法创建Actor的姓名
# https://python.langchain.com/docs/integrations/graphs/apache_age/
# result1 = pg_graph_store.query(
#     """
#     MERGE (m:Movie {name:"Top Gun"})
#     WITH m
#     UNWIND ["Tom Cruise", "Val Kilmer", "Anthony Edwards", "Meg Ryan"] AS actor
#     MERGE (a:Actor {name:actor})
#     MERGE (a)-[:ACTED_IN]->(m)
#     """
# )
# print(result1)

# 替代方法: 为每个 Actor 创建节点和关系
actors = ["Tom Cruise", "Val Kilmer", "Anthony Edwards", "Meg Ryan"]
for actor_name in actors:
    try:
        result_actor = pg_graph_store.query(f"""
            MERGE (m:Movie {{name:"Top Gun"}})
            MERGE (a:Actor {{name: "{actor_name}"}}) // 使用 MERGE 确保 Actor 节点存在
            MERGE (a)-[r:ACTED_IN]->(m) // 使用 MERGE 确保关系存在 (可选)
            RETURN m, r, a
        """)
        print(result_actor)
    except Exception as e:
        print(f"Error creating actor {actor_name}: {e}")

pg_graph_store.refresh_schema()

print(pg_graph_store.schema)

from langchain_core.prompts.prompt import PromptTemplate

CYPHER_GENERATION_TEMPLATE = """Task:Generate Cypher statement to query a graph database.
Instructions:
Use only the provided relationship types and properties in the schema.
Do not use any other relationship types or properties that are not provided.
if has RETURN a.name, must be RETURN a.name As a_name
Schema:
{schema}
Note: Do not include any explanations or apologies in your responses.
Do not respond to any questions that might ask anything else than for you to construct a Cypher statement.
Do not include any text except the generated Cypher statement.
Examples: Here are a few examples of generated Cypher statements for particular questions:
# How many people played in Top Gun?
MATCH (m:Movie {{title:"Top Gun"}})<-[:ACTED_IN]-()
RETURN count(*) AS numberOfActors

The question is:
{question}"""

CYPHER_GENERATION_PROMPT = PromptTemplate(
    input_variables=["schema", "question"], template=CYPHER_GENERATION_TEMPLATE
)

chain = GraphCypherQAChain.from_llm(
    llm, graph=pg_graph_store, verbose=True, allow_dangerous_requests=True,return_intermediate_steps=True,cypher_prompt=CYPHER_GENERATION_PROMPT,
)

answer = chain.invoke("Who played in Top Gun?")
print(answer)


answer = chain.invoke("图中一共有多少个节点？")
print(answer)


