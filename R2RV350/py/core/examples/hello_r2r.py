from r2r import R2RClient

client = R2RClient()

with open("test.txt", "w") as file:
    file.write("John is a person that works at Google.")
from core.main.config import R2RConfig
from core.main.assembly.factory import R2RProviderFactory
from core.main.orchestration.simple.ingestion_workflow import simple_ingestion_factory
from core.main.services.ingestion_service import IngestionService
import asyncio

r2rconfig = R2RConfig.from_toml(config_path="/data/projects/JqChatV2/JqChat/R2RV350/py/core/configs/full_jq.toml")
ingestion_factory = simple_ingestion_factory(IngestionService(config=r2rconfig.ingestion,providers=R2RProviderFactory(config=r2rconfig)))
client.documents.create(file_path="test.txt")
ingest_files = ingestion_factory["ingest-files"]
text = asyncio.run(ingest_files("test.txt"))

client.ingest_files("test.txt")

# Call RAG directly on an R2R object
rag_response = client.rag(
    query="Who is john",
    rag_generation_config={"model": "gpt-4o-mini", "temperature": 0.0},
)
results = rag_response["results"]
print(f"Search Results:\n{results['search_results']}")
print(f"Completion:\n{results['completion']}")

# RAG Results:
# Search Results:
# AggregateSearchResult(chunk_search_results=[ChunkSearchResult(id=2d71e689-0a0e-5491-a50b-4ecb9494c832, score=0.6848798582029441, metadata={'text': 'John is a person that works at Google.', 'version': 'v0', 'chunk_order': 0, 'document_id': 'ed76b6ee-dd80-5172-9263-919d493b439a', 'id': '1ba494d7-cb2f-5f0e-9f64-76c31da11381', 'associatedQuery': 'Who is john'})], graph_search_results=None)
# Completion:
# ChatCompletion(id='chatcmpl-9g0HnjGjyWDLADe7E2EvLWa35cMkB', choices=[Choice(finish_reason='stop', index=0, logprobs=None, message=ChatCompletionMessage(content='John is a person that works at Google [1].', role='assistant', function_call=None, tool_calls=None))], created=1719797903, model='gpt-4o-mini', object='chat.completion', service_tier=None, system_fingerprint=None, usage=CompletionUsage(completion_tokens=11, prompt_tokens=145, total_tokens=156))
