import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    EMBEDDING_MODEL_NAME = os.getenv("Qwen3_EMBEDDING_MODEL_NAME", "Qwen/Qwen3-Embedding-0.6B")
    RERANK_MODEL_NAME = os.getenv("Qwen3_RERANK_MODEL_NAME", "Qwen/Qwen3-Reranker-0.6B")
    API_VERSION = os.getenv("API_VERSION", "v1")
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8090))