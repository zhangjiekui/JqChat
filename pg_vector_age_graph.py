from langchain_core.documents import Document
from langchain_postgres import PGVector
# from langchain_postgres.vectorstores import PGVector
from jqcode.jq_agent.c0_init_env_models import env_models_instance
from langchain_community.graphs.age_graph import AGEGraph
# from langchain_neo4j import GraphCypherQAChain
from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain
from langchain_experimental.graph_transformers import LLMGraphTransformer

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
# See docker command above to launch a postgres instance with pgvector enabled.
# connection = "postgresql+psycopg://postgresUser:postgresPW@localhost:5455/postgresDB"  # Uses psycopg3!
connection = "postgresql+psycopg://langchain:langchain@localhost:6024/langchain"  # Uses psycopg3!


from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.sql import text


engine = create_engine(connection)
llm = env_models_instance.chat_model
llm_transformer = LLMGraphTransformer(llm=llm)


with Session(engine) as session:
    with session.begin():
        session.execute(text("create extension if not exists vector;"))
        session.execute(text("create extension if not exists age;"))
        # session.execute(text("create extension if not exists zhparser;"))  #zhparser中文分词的PostgreSQL插件
        # session.execute(text("CREATE TEXT SEARCH CONFIGURATION testzhcfg (PARSER = zhparser);"))
        # session.execute(text("ALTER TEXT SEARCH CONFIGURATION testzhcfg ADD MAPPING FOR n,v,a,i,e,l WITH simple;"))


        # 在PostgreSQL数据库中，默认的search_path设置为"$user", public, pg_catalog，其中每个部分的含义如下：
        # 1. $user
            # $user表示PostgreSQL首先会查找与当前用户同名的模式（schema）。例如，如果以用户postgres登录，系统会优先在名为postgres的schema中查找对象。如果该schema不存在，则会被忽略。
        # 2. public
            # public是一个公共模式，PostgreSQL在创建数据库时自动生成。所有用户都可以访问这个schema，因此它通常用于存放公共数据表和视图。若没有指定schema，PostgreSQL将默认在public中创建新对象。
        # 3. pg_catalog
            # pg_catalog是PostgreSQL的系统schema，包含了系统自带的函数、表、视图以及数据类型等元数据。无论是否在search_path中明确列出，系统总是会首先搜索这个schema，以确保内置对象能够被找到。
        # 总结
            # $user：优先查找与当前用户同名的schema。
            # public：所有用户可访问的公共schema。
            # pg_catalog：系统级别的schema，包含内置函数和元数据。
            # 这种设计使得PostgreSQL能够灵活地处理对象查找，同时保持了良好的安全性和可管理性。
        
        session.execute(text('ALTER DATABASE postgres SET search_path = ag_catalog, "$user", public;'))   
            #  
        
index_name = "my_docs"

embeddings = env_models_instance.embed_model
vector_store = PGVector(
    embeddings=embeddings,
    collection_name=index_name,
    connection=connection,
    use_jsonb=True,
)

docs = [
    Document(
        page_content="there are cats in the pond",
        metadata={"id": 1, "location": "pond", "topic": "animals"},
    ),
    Document(
        page_content="ducks are also found in the pond",
        metadata={"id": 2, "location": "pond", "topic": "animals"},
    ),
    Document(
        page_content="fresh apples are available at the market",
        metadata={"id": 3, "location": "market", "topic": "food"},
    ),
    Document(
        page_content="the market also sells fresh oranges",
        metadata={"id": 4, "location": "market", "topic": "food"},
    ),
    Document(
        page_content="the new art exhibit is fascinating",
        metadata={"id": 5, "location": "museum", "topic": "art"},
    ),
    Document(
        page_content="a sculpture exhibit is also at the museum",
        metadata={"id": 6, "location": "museum", "topic": "art"},
    ),
    Document(
        page_content="a new coffee shop opened on Main Street",
        metadata={"id": 7, "location": "Main Street", "topic": "food"},
    ),
    Document(
        page_content="the book club meets at the library",
        metadata={"id": 8, "location": "library", "topic": "reading"},
    ),
    Document(
        page_content="the library hosts a weekly story time for kids",
        metadata={"id": 9, "location": "library", "topic": "reading"},
    ),
    Document(
        page_content="a cooking class for beginners is offered at the community center",
        metadata={"id": 10, "location": "community center", "topic": "classes"},
    ),
]




vector_store.add_documents(docs, ids=[doc.metadata["id"] for doc in docs])
results = vector_store.similarity_search_with_relevance_scores(
    "kitty", k=10, filter={"id": {"$in": [1, 5, 2, 9]}}
)
for doc,sim in results:
    print(f"==doc==")
    print(f"* relevance_scores:{sim};\ncontent:{doc.page_content};\nmetadata: [{doc.metadata}]")


conf = {
    "database": "langchain",
    "user": "langchain",
    "password": "langchain",
    "host": "localhost",
    "port": 6024,
}

graph = AGEGraph(graph_name=index_name, conf=conf)
# Assuming your database is empty, you can populate it using Cypher query language. 
graph.query(
    """
MERGE (m:Movie {name:"Top Gun"})
WITH m
UNWIND ["Tom Cruise", "Val Kilmer", "Anthony Edwards", "Meg Ryan"] AS actor
MERGE (a:Actor {name:actor})
MERGE (a)-[:ACTED_IN]->(m)
"""
)

graph_documents = llm_transformer.convert_to_graph_documents(docs)
graph.add_graph_documents(graph_documents)

graph.refresh_schema()
print(graph.schema)


from langchain_core.prompts.prompt import PromptTemplate
CYPHER_GENERATION_TEMPLATE = """Task:Generate Cypher statement to query a graph database.
Instructions:
Use only the provided relationship types and properties in the schema.
Do not use any other relationship types or properties that are not provided.
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
    llm, graph=graph, verbose=True, cypher_prompt=CYPHER_GENERATION_PROMPT, validate_cypher=True,allow_dangerous_requests=True
)

# result = chain.invoke("Who played in Top Gun?")
# print(result)


# results = vector_store.similarity_search_with_relevance_scores(
#     "where to find ducks?", k=3
# )
# for doc,sim in results:
#     print(f"==doc==")
#     print(f"* relevance_scores:{sim};\ncontent:{doc.page_content};\nmetadata: [{doc.metadata}]")
# result2 = chain.invoke(f"With Added Context:{results},Try to Answer The Question:'where to find ducks?'")
# print(result2)


q="where are the cats?"
results = vector_store.similarity_search_with_relevance_scores(q, k=3)
for doc,sim in results:
    print(f"==doc==")
    print(f"* relevance_scores:{sim};\ncontent:{doc.page_content};\nmetadata: [{doc.metadata}]")
result2 = chain.invoke(f"With Added Context:{results},Try to Answer The Question:'{q}'")
print(result2)







