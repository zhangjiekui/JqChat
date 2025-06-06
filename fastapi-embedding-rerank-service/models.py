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
    input: List[dict] # 包含 query和document的字典列表
    model: Optional[str] = None
    instruction: Optional[str] = None

class RerankResponse(BaseModel):
    model: str
    data: List[dict]  # 包含scores的字典列表