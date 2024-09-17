from jqcode.jq_knowledge_manegement.chatchat.server.file_rag.retrievers import (
    BaseRetrieverService,
    EnsembleRetrieverService,
    VectorstoreRetrieverService,
)

Retrivals = {
    "vectorstore": VectorstoreRetrieverService,
    "ensemble": EnsembleRetrieverService,
}


def get_Retriever(type: str = "vectorstore") -> BaseRetrieverService:
    return Retrivals[type]
