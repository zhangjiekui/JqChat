from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel

from R2RV350.py.core.providers import (
    AnthropicCompletionProvider,
    AsyncSMTPEmailProvider,
    ConsoleMockEmailProvider,
    HatchetOrchestrationProvider,
    JwtAuthProvider,
    LiteLLMCompletionProvider,
    LiteLLMEmbeddingProvider,
    MailerSendEmailProvider,
    OllamaEmbeddingProvider,
    OpenAICompletionProvider,
    OpenAIEmbeddingProvider,
    PostgresDatabaseProvider,
    R2RAuthProvider,
    R2RCompletionProvider,
    R2RIngestionProvider,
    SendGridEmailProvider,
    SimpleOrchestrationProvider,
    SupabaseAuthProvider,
    UnstructuredIngestionProvider,
)

if TYPE_CHECKING:
    from R2RV350.py.core.main.services.auth_service import AuthService
    from R2RV350.py.core.main.services.graph_service import GraphService
    from R2RV350.py.core.main.services.ingestion_service import IngestionService
    from R2RV350.py.core.main.services.management_service import ManagementService
    from R2RV350.py.core.main.services.retrieval_service import (  # type: ignore
        RetrievalService,  # type: ignore
    )


class R2RProviders(BaseModel):
    auth: R2RAuthProvider | SupabaseAuthProvider | JwtAuthProvider
    database: PostgresDatabaseProvider
    ingestion: R2RIngestionProvider | UnstructuredIngestionProvider
    embedding: (
        LiteLLMEmbeddingProvider
        | OpenAIEmbeddingProvider
        | OllamaEmbeddingProvider
    )
    completion_embedding: (
        LiteLLMEmbeddingProvider
        | OpenAIEmbeddingProvider
        | OllamaEmbeddingProvider
    )
    llm: (
        AnthropicCompletionProvider
        | LiteLLMCompletionProvider
        | OpenAICompletionProvider
        | R2RCompletionProvider
    )
    orchestration: HatchetOrchestrationProvider | SimpleOrchestrationProvider
    email: (
        AsyncSMTPEmailProvider
        | ConsoleMockEmailProvider
        | SendGridEmailProvider
        | MailerSendEmailProvider
    )

    class Config:
        arbitrary_types_allowed = True


@dataclass
class R2RServices:
    auth: "AuthService"
    ingestion: "IngestionService"
    management: "ManagementService"
    retrieval: "RetrievalService"
    graph: "GraphService"
