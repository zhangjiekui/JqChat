from pydantic import BaseModel
from typing import List, Optional, Union

class EmbeddingRequest(BaseModel):
    input: List[str]
    model: Optional[str] = None

class EmbeddingResponse(BaseModel):
    object: str = "list"
    data: List[dict]
    model: str

class TokenizeRequest(BaseModel):
    model: Optional[str] = None
    input: Union[str, List[str]]

class TokenizeResponse(BaseModel):
    model: str
    tokens: List[int]
    token_count: int

class RerankRequest(BaseModel):
    model: Optional[str] = None
    query: str
    documents: List[str]
    top_n: Optional[int] = None
    return_documents: Optional[bool] = False
    return_len: Optional[bool] = False
    max_chunks_per_doc: Optional[int] = None
    instruction: Optional[str] = None
    kwargs: Optional[str] = None

class RerankResponse(BaseModel):
    model: str
    results: List[dict]  # 包含scores的字典列表

# 定义模型信息的响应结构
class ModelInfo(BaseModel):
    id: str
    object: str = "model"
    owned_by: str = "organization-owner"
    permission: list = []

# 定义/v1/models接口的响应结构
class ModelsResponse(BaseModel):
    object: str = "list"
    data: list[ModelInfo]