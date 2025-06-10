import logging
from fastapi import FastAPI,HTTPException, status
from sentence_transformers import SentenceTransformer
from typing import List, Union, Optional
from pydantic import BaseModel
from config import Config
from models import TokenizeRequest, TokenizeResponse, RerankRequest, RerankResponse, ModelInfo,ModelsResponse
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch



logger = logging.getLogger(__name__)
from modelscope import snapshot_download
config =Config()
print(f"准备下载/加载{config.EMBEDDING_MODEL_NAME=}和{config.RERANK_MODEL_NAME=}模型")
embedding_model_name  = config.EMBEDDING_MODEL_NAME
embedding_model_dir = snapshot_download(embedding_model_name,cache_dir='/data/models/')
print(f"成功下载模型'{embedding_model_name}'到{embedding_model_dir=}")
model = SentenceTransformer(embedding_model_dir)
print(f"成功从{embedding_model_dir=}加载模型'{embedding_model_name}'")

rerank_model_dir = snapshot_download(config.RERANK_MODEL_NAME,cache_dir='/data/models/')
print(f"成功下载模型'{config.RERANK_MODEL_NAME}'到{rerank_model_dir=}")

# 初始化tokenizer
tokenizer = AutoTokenizer.from_pretrained(embedding_model_dir)
print(f"成功从{embedding_model_dir=}加载模型'{embedding_model_name}'的tokenizer")
# 初始化rerank模型
rerank_model = AutoModelForCausalLM.from_pretrained(rerank_model_dir).eval()
print(f"成功从{rerank_model_dir=}加载模型'{config.RERANK_MODEL_NAME}'")
token_false_id = tokenizer.convert_tokens_to_ids("no")
token_true_id = tokenizer.convert_tokens_to_ids("yes")
max_length = 8192

prefix = "<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the Instruct provided. Note that the answer can only be \"yes\" or \"no\".<|im_end|>\n<|im_start|>user\n"
suffix = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
prefix_tokens = tokenizer.encode(prefix, add_special_tokens=False)
suffix_tokens = tokenizer.encode(suffix, add_special_tokens=False)

def format_instruction(instruction, query, doc):
    if instruction is None:
        instruction = 'Given a web search query, retrieve relevant passages that answer the query'
    return f"<Instruct>: {instruction}\n<Query>: {query}\n<Document>: {doc}"

def process_inputs(pairs):
    inputs = tokenizer(
        pairs, padding=False, truncation='longest_first',
        return_attention_mask=False, max_length=max_length - len(prefix_tokens) - len(suffix_tokens)
    )
    for i, ele in enumerate(inputs['input_ids']):
        inputs['input_ids'][i] = prefix_tokens + ele + suffix_tokens
    inputs = tokenizer.pad(inputs, padding=True, return_tensors="pt", max_length=max_length)
    for key in inputs:
        inputs[key] = inputs[key].to(rerank_model.device)
    return inputs

@torch.no_grad()
def compute_logits(inputs):
    batch_scores = rerank_model(**inputs).logits[:, -1, :]
    true_vector = batch_scores[:, token_true_id]
    false_vector = batch_scores[:, token_false_id]
    batch_scores = torch.stack([false_vector, true_vector], dim=1)
    batch_scores = torch.nn.functional.log_softmax(batch_scores, dim=1)
    scores = batch_scores[:, 1].exp().tolist()
    return scores

app = FastAPI()
class EmbeddingRequest(BaseModel):
    input: List[str]
    model: Optional[str] = None

class EmbeddingResponse(BaseModel):
    object: str = "list"
    data: List[dict]
    model: str
@app.post("/v1/embeddings", response_model=EmbeddingResponse)
def create_embedding(request: EmbeddingRequest):
    print(f"EmbeddingRequest:{request}")
    try:
        # 输入校验（示例）
        if not request.input:
            raise ValueError("Input cannot be empty")
        # else:
        #     print(f"EmbeddingRequest:{request.input=}")
        
        if isinstance(request.input, list) and len(request.input) > 100:
            raise ValueError("Input list length exceeds maximum allowed (100)")

        # 生成 embedding
        embeddings = model.encode(request.input, show_progress_bar=False)

        # 组织返回格式
        data = [
            {
                "object": "embedding",
                "embedding": emb.tolist(),
                "index": idx
            }
            for idx, emb in enumerate(embeddings)
        ]

        return EmbeddingResponse(
            data=data,
            model=embedding_model_name
        )

    except (ValueError, RuntimeError) as e:
        logger.error(f"Model inference error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")
@app.post("/v1/tokenize", response_model=TokenizeResponse)
def create_tokenize(request: TokenizeRequest):
    try:
        # 处理输入
        input_text = request.input
        if isinstance(input_text, str):
            input_text = [input_text]
            
        # 进行tokenize
        all_tokens = []
        for text in input_text:
            # tokens = tokenizer.encode(text)
            tokens = tokenizer(text)
            all_tokens.extend(tokens)
            
        return TokenizeResponse(
            model=embedding_model_name,
            tokens=all_tokens,
            token_count=len(all_tokens)
        )
    
    except Exception as e:
        logger.error(f"Tokenize error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
@app.post("/v1/rerank", response_model=RerankResponse)
def create_rerank(request: RerankRequest):
    print(f"RerankRequest:{request}")
    try:
        if not request.query:
            raise ValueError("Query cannot be empty")
        if not request.documents:
            raise ValueError("Documents cannot be empty")
        try:
            print(f"User Provided Instruction: {request.instruction}")
        except:
            request.instruction=None

        # 格式化输入
        pairs = [
            format_instruction(
                request.instruction, 
                request.query, 
                doc
            )  for doc in request.documents
        ]
        print(f"RerankPairs:{pairs}")

        # 处理输入并计算分数
        inputs = process_inputs(pairs)
        scores = compute_logits(inputs)

        # 组织返回数据
        data = [
            {
                "score": score,
                "index": idx,
            }
            for idx, score in enumerate(scores)
        ]

        return RerankResponse(
            model=config.RERANK_MODEL_NAME,
            results=data,           
        )

    except Exception as e:
        logger.error(f"Rerank error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# 添加 /v1/models 接口
@app.get("/v1/models", response_model=ModelsResponse)
def get_models():
    # 返回当前服务支持的模型列表及其相关信息
    models = ModelsResponse(
        data=[
            ModelInfo(id=embedding_model_name, object="model", owned_by="jq-embed", permission=[]),
            ModelInfo(id=config.RERANK_MODEL_NAME, object="model", owned_by="jq-rerank", permission=[])
        ]
    )
    return models

# 添加 /v1/models/{model_id} 接口
@app.get(f"/v1/models/{config.RERANK_MODEL_NAME}")
def get_model_description():
    # 返回当前服务支持的模型列表及其相关信息
    model={
        "id": config.RERANK_MODEL_NAME,
        "model_name": config.RERANK_MODEL_NAME,
        "model_type":"rerank",
        "model_description": "This is a qwen3 rerank model for evaluating the relevance of documents to a given query.",
        "context_length":32768
    }
    return model
# 添加 /v1/models/{model_id} 接口
@app.get(f"/v1/models/{config.EMBEDDING_MODEL_NAME}")
def get_model_description():
    # 返回当前服务支持的模型列表及其相关信息
    model={
        "id": config.EMBEDDING_MODEL_NAME,
        "model_name": config.EMBEDDING_MODEL_NAME,
        "model_type":"embedding",
        "model_description": "This is a qwen3 embedding model for generating embeddings from text.",
        "context_length":32768
    }
    return model

@app.get(f"/v1/cluster/auth")
def get_cluster_auth():
    # 返回集群认证信息
    auth_info = {
        "auth": True,
    }
    return auth_info

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.HOST, port=config.PORT, log_level="info")


    # 需要增加/v1/models接口，返回模型信息