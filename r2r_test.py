import asyncio
from r2r import R2RClient
client = R2RClient("http://10.1.150.105:7272")

chunks = ["Pre-chunked content with metadata", "other pre-chunked content with metadata"]
r_chunks = client.documents.create(chunks=chunks,metadata={"title":"test title"})

# Setup collection and extract knowledge
collection_id = "122fdf6a-e116-546b-a8f6-e4cb2e2c0a09"

r = client.collections.extract(collection_id)
print(r)
r2 = client.graphs.pull(collection_id)
print(r2)



# Synthetically generate a description for the collection
client.collections.update(
    collection_id,
    generate_description=True
)

# Build communities for your collection's graph
build_response = client.graphs.build(collection_id)
print(build_response)


# Search across all levels
search_response = client.retrieval.search(
    "全民健康信息平台的详细信息",
    search_settings={
        "graph_settings": {
            "enabled": True,
        }
    }
)
print(search_response)

# RAG with community context
rag_response = client.retrieval.rag(
    "全民健康信息平台的详细信息",
    search_settings={
        "enabled": True
    }
)

print(rag_response)



