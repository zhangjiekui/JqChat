import logging

# Keep '*' imports for enhanced development velocity
from .agent import *
from .base import *
from .main import *
from .parsers import *
from .providers import *
from .main import *
from .utils import (
    CitationTracker,
    SearchResultsCollector,
    SSEFormatter,
    dump_collector,
    dump_obj,
    extract_citations,
    find_new_citation_spans,
    generate_id,
    num_tokens,
    num_tokens_from_messages,
    convert_nonserializable_objects
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Create a console handler and set the level to info
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)

# Create a formatter and set it for the handler
formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
ch.setFormatter(formatter)

# Add the handler to the logger
logger.addHandler(ch)

# Optional: Prevent propagation to the root logger
logger.propagate = False

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("LiteLLM").setLevel(logging.WARNING)

__all__ = [
    "R2RApp",
    "ThinkingEvent",
    "ToolCallEvent",
    "ToolResultEvent",
    "CitationEvent",
    "Citation",
    "R2RAgent",
    "SearchResultsCollector",
    "R2RRAGAgent",
    "R2RXMLToolsRAGAgent",
    "R2RStreamingRAGAgent",
    "R2RXMLToolsStreamingRAGAgent",
    "AsyncSyncMeta",
    "syncable",
    "MessageType",
    "Document",
    "DocumentChunk",
    "DocumentResponse",
    "IngestionStatus",
    "GraphExtractionStatus",
    "GraphConstructionStatus",
    "DocumentType",
    "EmbeddingPurpose",
    "default_embedding_prefixes",
    "R2RDocumentProcessingError",
    "R2RException",
    "Entity",
    "GraphExtraction",
    "Relationship",
    "GenerationConfig",
    "LLMChatCompletion",
    "LLMChatCompletionChunk",
    "RAGCompletion",
    "Prompt",
    "AggregateSearchResult",
    "WebSearchResult",
    "GraphSearchResult",
    "ChunkSearchSettings",
    "GraphSearchSettings",
    "ChunkSearchResult",
    "WebPageSearchResult",
    "SearchSettings",
    "select_search_filters",
    "SearchMode",
    "HybridSearchSettings",
    "Token",
    "TokenData",
    "Vector",
    "VectorEntry",
    "VectorType",
    "IndexConfig",
    "Agent",
    "AgentConfig",
    "Conversation",
    "Message",
    "Tool",
    "ToolResult",
    "TokenResponse",
    "User",
    "AppConfig",
    "Provider",
    "ProviderConfig",
    "AuthConfig",
    "AuthProvider",
    "CryptoConfig",
    "CryptoProvider",
    "EmailConfig",
    "EmailProvider",
    "LimitSettings",
    "DatabaseConfig",
    "DatabaseProvider",
    "EmbeddingConfig",
    "EmbeddingProvider",
    "CompletionConfig",
    "CompletionProvider",
    "RecursiveCharacterTextSplitter",
    "TextSplitter",
    "generate_id",
    "increment_version",
    "validate_uuid",
    "yield_sse_event",
    "convert_nonserializable_objects",
    "num_tokens",
    "num_tokens_from_messages",
    "SearchResultsCollector",
    "R2RProviders",
    "R2RApp",
    "R2RBuilder",
    "R2RConfig",
    "R2RProviderFactory",
    "AuthService",
    "IngestionService",
    "ManagementService",
    "RetrievalService",
    "GraphService",
    "AudioParser",
    "BMPParser",
    "DOCParser",
    "DOCXParser",
    "ImageParser",
    "ODTParser",
    "VLMPDFParser",
    "BasicPDFParser",
    "PDFParserUnstructured",
    "PPTParser",
    "PPTXParser",
    "RTFParser",
    "CSVParser",
    "CSVParserAdvanced",
    "EMLParser",
    "EPUBParser",
    "JSONParser",
    "MSGParser",
    "ORGParser",
    "P7SParser",
    "RSTParser",
    "TIFFParser",
    "TSVParser",
    "XLSParser",
    "XLSXParser",
    "XLSXParserAdvanced",
    "MDParser",
    "HTMLParser",
    "TextParser",
    "SupabaseAuthProvider",
    "R2RAuthProvider",
    "JwtAuthProvider",
    # Email
    # Crypto
    "BCryptCryptoProvider",
    "BcryptCryptoConfig",
    "NaClCryptoConfig",
    "NaClCryptoProvider",
    "PostgresDatabaseProvider",
    "LiteLLMEmbeddingProvider",
    "OpenAIEmbeddingProvider",
    "OllamaEmbeddingProvider",
    "OpenAICompletionProvider",
    "R2RCompletionProvider",
    "LiteLLMCompletionProvider",
    "UnstructuredIngestionProvider",
    "R2RIngestionProvider",
    "ChunkingStrategy",
]
logger.debug("===============/data/projects/JqChatV2/JqChat/JqR2R/py/core/__init__.py中包括的包")
logger.debug(dir())
logger.debug("===============/data/projects/JqChatV2/JqChat/JqR2R/py/core/__init__.py中包括的包")