from langchain_core.documents import Document
from langchain_postgres import PGVector
from jqcode.jq_agent.c0_init_env_models import env_models_instance
from langchain_community.graphs.age_graph import AGEGraph
from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain
from langchain_experimental.graph_transformers import LLMGraphTransformer

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.sql import text
from langchain.chains import LLMChain
from langchain.chains import RetrievalQA
from langchain_core.retrievers import BaseRetriever
import psycopg
index_name = "my_collection"
database_name = 'rag'
connection = f"postgresql+psycopg://langchain:langchain@localhost:6022/{database_name}"  # Uses psycopg3!
engine = create_engine(connection)


with Session(engine) as session:
    with session.begin():
        session.execute(text("create extension if not exists vector;"))
        session.execute(text("create extension if not exists age;"))
        session.execute(text("create extension if not exists pg_jieba;")) 
        # /var/polardb/primary_datadir/postgresql.conf
        # shared_preload_libraries = 'pg_jieba'

        # session.execute(text("CREATE TEXT SEARCH CONFIGURATION chinese (PARSER = pg_jieba);"))
        # # # 将指定的词汇类别（n，v，a，i，e，l）与已存在的 simple 配置进行映射。这意味着对于这些词汇类别，将使用 simple 配置的规则来进行文本分析和处理。
        # session.execute(text("ALTER TEXT SEARCH CONFIGURATION chinese ADD MAPPING FOR n,v,a,i,e,l WITH simple;"))


        # # session.execute(text("create extension if not exists pg_jieba;")) 
        # # session.execute(text("create extension if not exists pg_jieba;")) 
        
        r=session.execute(text("SELECT * FROM to_tsvector('jiebacfg', '小明硕士毕业于中国科学院计算所，后在日本京都大学深造')"))
        print(r)
        rec = r.fetchone()
        print(rec)
        session.execute(text('ALTER DATABASE postgres SET search_path = ag_catalog,polar_feature_utils,"$user", public;'))   
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
    Document(
        page_content="在PostgreSQL数据库中，默认的search_path设置为'$user', public, pg_catalog",
        metadata={"id": 11, "domain": "技术", "topic": "数据库"},
    ),
]     

vector_store.add_documents(docs, ids=[doc.metadata["id"] for doc in docs])
results_vector = vector_store.similarity_search_with_relevance_scores(
    "cats", k=10, filter={"id": {"$in": [1, 5, 2, 9]}}
)
results_vector = vector_store.similarity_search_with_relevance_scores("cats", k=2)
for doc,sim in results_vector:
    print(f"==doc==")
    print(f"* relevance_scores:{sim};\ncontent:{doc.page_content};\nmetadata: [{doc.metadata}]")


conf = {
    "database": database_name,
    "user": "langchain",
    "password": "langchain",
    "host": "localhost",
    "port": 6022,
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

llm = env_models_instance.chat_model
graphchain = GraphCypherQAChain.from_llm(
    llm, graph=graph, verbose=True, cypher_prompt=CYPHER_GENERATION_PROMPT, validate_cypher=True,allow_dangerous_requests=True,
    return_direct=True, #此处直接返回查询结果，不需要llm来组织回答
)

result = graphchain.invoke("Who played in Top Gun?")
print(result)


llm_transformer = LLMGraphTransformer(llm=llm)
graph_documents = llm_transformer.convert_to_graph_documents(docs)
graph.add_graph_documents(graph_documents)
graph.refresh_schema()
print(graph.schema)

q="where are the cats?"
results_vector = vector_store.similarity_search_with_relevance_scores(q, k=3)
for doc,sim in results_vector:
    print(f"==doc==")
    print(f"* relevance_scores:{sim};\ncontent:{doc.page_content};\nmetadata: [{doc.metadata}]")

g_query = """
SELECT * from cypher('my_docs2', $$ 
MATCH (V:Entity {id:'Cats'})-[R]-(V2) RETURN V,R,V2 
$$) as (V agtype, R agtype, V2 agtype);
"""
g_query = """
SELECT * from cypher('my_docs2', $$
        MATCH (V:Entity {id:"Cats"})-[R]-(V2)
        RETURN V,R,V2
$$) as (V agtype, R agtype, V2 agtype);
"""

g_query = """
        MATCH (V:Animal {id:"Cats"})-[R]-(V2)
        RETURN V,R,V2
"""

g_query = """
        MATCH (V {id:"Cats"})-[R]-(V2)
        RETURN V,R,V2
"""

results_graph = graph.query(g_query)

results = results_vector + results_graph
result2 = graphchain.invoke(f"With Added Context:{results},Try to Answer The Question:'{q}'")
print(result2)

psycopg_connection_str = f"dbname={database_name} user=langchain host=localhost port=6022 password=langchain"  
conn = psycopg.connect(psycopg_connection_str)
class CustomRetriever(BaseRetriever):
    def __init__(self):
        super().__init__()
    def _get_relevant_documents(self, query: str,topn=5) -> list[Document]:
        relevant_docs = []
        cur = conn.cursor()
        # Get the top 5 most similar documents using the KNN <=> operator
        # cur.execute("SELECT document FROM docs ORDER BY embedding <=> '{}' LIMIT 5".format(embeddings.embed_query(query)))
        cur.execute(f"SELECT document FROM public.langchain_pg_embedding ORDER BY embedding <=> '{embeddings.embed_query(query)}' LIMIT {topn}")
        topn_docs = cur.fetchall()
        cur.close()
        
        for doc in topn_docs:
            relevant_docs.append(Document(page_content=doc[0]))
        return relevant_docs
custom_retriever = CustomRetriever()
qa_chain = RetrievalQA.from_chain_type(
    llm=llm,
    retriever=custom_retriever,
    verbose=True
)  

template = """Task:Generate more detailed information about the raw answer.
The question is:
{question}
the raw answer from knowledge graph in format:
{answer}
please give more detailed answer about raw answer
"""
prompt = PromptTemplate(
    input_variables=["question", "answer"],
    template=template
)
llm_chain = LLMChain(llm=llm, prompt=prompt)
def dynamic_query(question):
    # first round use graph cypher qa
    answer = graphchain.invoke(question)
    
    if answer['result']:
        graph_answer=answer['result'][0]
    else:
        graph_answer = ''
    # 格式化输入提示
    formatted_prompt = prompt.format(question=question,answer=graph_answer)
    
    answer = qa_chain.invoke(formatted_prompt)
    return answer
response = dynamic_query(q)
print(response['result'])

response = dynamic_query("数据库")
print(response['result'])








