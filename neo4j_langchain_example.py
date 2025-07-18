import os
from langchain.schema import Document
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_neo4j import Neo4jVector, Neo4jGraph, GraphCypherQAChain
from langchain_openai import ChatOpenAI
from jqcode.jq_kb_manegement.server.localai_embeddings import LocalAIEmbeddings

# Initialize the language model with specific parameters
llm = ChatOpenAI(
    model_name='vanilj/Phi-4:Q8_0',
    openai_api_base="http://localhost:11434/v1",    
    openai_api_key= 'abc123',              
)

# Initialize the LLMGraphTransformer with the language model
llm_transformer = LLMGraphTransformer(llm=llm)

# Initialize the embedding model with specific parameters
embed_model = LocalAIEmbeddings(
    model='bce-embedding-base_v1',
    deployment='bce-embedding-base_v1',
    api_key="NotNeed",
    openai_api_base='http://10.1.150.106:9997/v1',
    base_url='http://10.1.150.106:9997/v1',
    embedding_ctx_length=512*8,
    chunk_size=512
)

# Set environment variables for Neo4j connection
os.environ["NEO4J_URI"] = url = "bolt://10.1.150.105:7687"
os.environ["NEO4J_USERNAME"] = username = "neo4j"
os.environ["NEO4J_PASSWORD"] = password = "neo4jneo4j"
os.environ['LANGCHAIN_TRACING_V2'] = 'true'
os.environ['LANGCHAIN_ENDPOINT'] = 'https://api.smith.langchain.com'
os.environ['LANGCHAIN_API_KEY'] = "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"

# Initialize the Neo4j graph with the connection parameters
graph = Neo4jGraph(
    url=url,
    username=username,
    password=password,
    enhanced_schema=True
)

# Sample text documents to be processed
text1 = '''
    安徽晶奇网络科技股份有限公司：
    根据【上级单位名称】于【印发日期】正式印发的《【文件名称】》文件精神，明确要求我单位需在【完成期限】前实施【上级单位要求实施的项目内容】。
    鉴于该项目实施存在客观紧迫性，加之相关系统长期由贵公司承建开发并维护至今，为确保系统的稳定性和连续性，因此，从项目实施的效率和安全性角度考量，我单位认为不宜改由其他供应商处承担相关工作。
    请贵公司在收到本函之日起【具体完成时限，体现项目紧迫性】日内，按照我单位工作方案要求完成【具体实施的内容】相关工作。
    上述服务产生的费用由我单位与贵公司根据市场公允水平另行商榷，我单位将根据相关规定通过【单一来源】采购方式尽快完成项目采购及合同签署。
'''

text2 = """
Marie Curie, born in 1867, was a Polish and naturalised-French physicist and chemist who conducted pioneering research on radioactivity.
She was the first woman to win a Nobel Prize, the first person to win a Nobel Prize twice, and the only person to win a Nobel Prize in two scientific fields.
Her husband, Pierre Curie, was a co-winner of her first Nobel Prize, making them the first-ever married couple to win the Nobel Prize and launching the Curie family legacy of five Nobel Prizes.
She was, in 1906, the first woman to become a professor at the University of Paris.
"""

# Create Document objects from the sample texts
documents = [Document(page_content=text1), Document(page_content=text2)]

# Create a hybrid database from the documents using the embedding model and Neo4j connection parameters
hybrid_db = Neo4jVector.from_documents(
    documents,
    embed_model,
    url=url,
    username=username,
    password=password,
    search_type="hybrid",
)

# Print the schema of the hybrid database
print(hybrid_db.schema)

# Convert the documents to graph documents using the LLMGraphTransformer
graph_documents = llm_transformer.convert_to_graph_documents(documents)

# Print the nodes and relationships of the graph documents
print(f"Nodes:{graph_documents[0].nodes}")
print(f"Relationships:{graph_documents[0].relationships}")
print(f"Nodes:{graph_documents[1].nodes}")
print(f"Relationships:{graph_documents[1].relationships}")

# Add the graph documents to the Neo4j graph
graph.add_graph_documents(graph_documents)

# Print the schema of the Neo4j graph
print(graph.schema)

# Define index names for the Neo4j vector
index_name = "neo4j"  # default index name
keyword_index_name = "keyword"

# Create a Neo4j vector from an existing index
existing_neo4j_vector = Neo4jVector.from_existing_index(
    embed_model,
    url=url,
    username=username,
    password=password,
    index_name=index_name,
    keyword_index_name=keyword_index_name,
    search_type="hybrid",
)

# Perform similarity search for the term "李友涛" and print the result
result = existing_neo4j_vector.similarity_search("李友涛", k=1)
print(result)

# Perform similarity search for the term "安徽晶奇网络科技股份有限公司" and print the result
result = existing_neo4j_vector.similarity_search("安徽晶奇网络科技股份有限公司", k=3)
print(result)

# Create a retriever from the existing Neo4j vector with a similarity score threshold
retriever = existing_neo4j_vector.as_retriever(search_type="similarity_score_threshold", search_kwargs={'score_threshold': 0.8})

# Invoke the retriever with the query "安徽晶奇网络科技股份有限公司" and print the result
result = retriever.invoke("安徽晶奇网络科技股份有限公司")
print(result)

# Refresh the schema of the Neo4j graph
graph.refresh_schema()

# Initialize the GraphCypherQAChain with the language model and Neo4j graph
chain = GraphCypherQAChain.from_llm(
    llm,
    graph=graph,
    allow_dangerous_requests=True,
    return_intermediate_steps=True,
    verbose=True
)

# Define a function to perform QA with hybrid context
def neo4j_qa_with_hybrid_context(query):
    # Invoke the retriever with the query to get vector documents
    vector_docs = retriever.invoke(query)
    # Extract the page content from the vector documents
    texts = [doc.page_content for doc in vector_docs]
    # Join the texts with newline characters
    context = '\n\n'.join(texts)
    # Run the chain with the context and query to get the result
    result = chain.run(f"上下文为：<context>{context}</context>。\n用户问题为：<query>{query}</query>。请检索问题相关的信息并回答该问题")
    # Print the result
    print(result)

# Perform QA with the query "Marie_Curie"
neo4j_qa_with_hybrid_context("Marie_Curie")

# Perform QA with the query "晶奇网络公司"
neo4j_qa_with_hybrid_context("晶奇网络公司")
