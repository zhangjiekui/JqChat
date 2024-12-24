import os
import asyncio
from dbgpt.model.proxy import OpenAILLMClient,OllamaLLMClient
from dbgpt.rag.embedding import OpenAPIEmbeddings
from dbgpt.rag.embedding import DefaultEmbeddingFactory
from dbgpt.core import Chunk, HumanPromptTemplate, ModelMessage, ModelRequest
from dbgpt.storage.knowledge_graph.community_summary import (
    CommunitySummaryKnowledgeGraph,
    CommunitySummaryKnowledgeGraphConfig,
)

from dbgpt.configs.model_config import ROOT_PATH
from dbgpt.core import Chunk, HumanPromptTemplate, ModelMessage, ModelRequest
from dbgpt.rag import ChunkParameters
from dbgpt.rag.assembler import EmbeddingAssembler
from dbgpt.rag.knowledge import KnowledgeFactory
from dbgpt.rag.retriever import RetrieverStrategy
from jqcode.jq_agent.c0_init_env_models import env_models_instance
llm_model_name = graph_model_name = 'qwen25b70'
# llm_model_name = graph_model_name = "vanilj/Phi-4:Q8_0"
# llm_model_name = graph_model_name = "vanilj/Phi-4:Q4_K_M"
emb_model_name = "bce-embedding-base_v1"

embedding_fn = OpenAPIEmbeddings(api_key=None,api_url='http://10.1.150.106:9997/v1/embeddings',model_name=emb_model_name)
texts = ["Hello, world!", "How are you?"]
emd = embedding_fn.embed_documents(texts)
print("embedding_fn ok")


llm_client = OpenAILLMClient(api_key='abc123',api_base='http://10.1.150.105:9997/v1',model=graph_model_name)
# llm_client = OllamaLLMClient(host='http://localhost:11434',model=graph_model_name)
# llm_client = OllamaLLMClient(host='http://10.1.42.212:11434',model="vanilj/Phi-4:Q4_K_M")

rag_template = (
    "Based on the following [Context] {context}, "
    "answer [Question] {question}."
)
template = HumanPromptTemplate.from_template(rag_template)
messages = template.format_messages(context="我叫张结魁？", question="你知道我叫什么吗？")
model_messages = ModelMessage.from_base_messages(messages)
request = ModelRequest(model=llm_model_name, messages=model_messages)
response = asyncio.run(llm_client.generate(request=request))
print(response.text)

# asyncio.run(llm_client.generate)
def __create_community_kg_connector():
    """Create community knowledge graph connector."""
    return CommunitySummaryKnowledgeGraph(
        config=CommunitySummaryKnowledgeGraphConfig(
            name="Operation_Dulce",
            embedding_fn=embedding_fn,
            llm_client=llm_client,
            model_name=graph_model_name,
            graph_store_type="TuGraphGraph",
            vector_store_type='ElasticSearch'
        ),
    )



async def test_community_graph_rag(question):
    await __run_graph_rag(
        knowledge_file='/data/projects/JqChatV2/JqChat/Operation Dulce.md',
        chunk_strategy="CHUNK_BY_MARKDOWN_HEADER",
        # chunk_strategy="Automatic",
        knowledge_graph=__create_community_kg_connector(),
        question=question,
    )

async def __run_graph_rag(knowledge_file, chunk_strategy, knowledge_graph, question):
    file_path = os.path.join(ROOT_PATH, knowledge_file).format()
    knowledge = KnowledgeFactory.from_file_path(file_path)
    try:
        if chunk_strategy:
            chunk_parameters = ChunkParameters(chunk_strategy=chunk_strategy)
        else:
            chunk_parameters = ChunkParameters()

        # get embedding assembler
        assembler = await EmbeddingAssembler.aload_from_knowledge(
            knowledge=knowledge,
            chunk_parameters=chunk_parameters,
            index_store=knowledge_graph,
            # retrieve_strategy=RetrieverStrategy.GRAPH,s
            retrieve_strategy=RetrieverStrategy.HYBRID,
        )
        await assembler.apersist()

        # get embeddings retriever
        retriever = assembler.as_retriever(10)
        chunks = await retriever.aretrieve_with_scores(question, score_threshold=0.3)

        # chat
        if chunks:
            print(f"检索到{len(chunks)=}相关文本")
            print(f"{await ask_chunk(chunks[0], question)}")
        else:
            print(f"没有检索到相关文本")

    finally:
        pass
        # print("finally ")
        # knowledge_graph.delete_vector_name(knowledge_graph.get_config().name)

async def ask_chunk(chunk: Chunk, question) -> str:
    rag_template = (
        "Based on the following [Context] {context}, "
        "answer [Question] {question}."
    )
    template = HumanPromptTemplate.from_template(rag_template)
    messages = template.format_messages(context=chunk.content, question=question)
    model_messages = ModelMessage.from_base_messages(messages)
    request = ModelRequest(model=llm_model_name, messages=model_messages)
    response = await llm_client.generate(request=request)

    if not response.success:
        code = str(response.error_code)
        reason = response.text
        raise Exception(f"request llm failed ({code}) {reason}")

    return response.text

if __name__ == "__main__":

    rag_template = ("Based on the following [Context] {context}, " "answer [Question] {question}.")
    template = HumanPromptTemplate.from_template(rag_template)
    messages = template.format_messages(context="张结魁是晶奇公司的董事", question="张结魁是谁？")
    model_messages = ModelMessage.from_base_messages(messages)
    request = ModelRequest(model=llm_model_name, messages=model_messages)
    result = asyncio.run(llm_client.generate(request))
    print(result)

    result = asyncio.run(test_community_graph_rag("亚历克斯·梅尔策"))
    print(result)
