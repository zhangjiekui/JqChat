import ray
import time
import torch
import itertools
from ray import serve
from typing import List, Dict
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from ray.serve.config import HTTPOptions
from qwen3_embedding_transformers import Qwen3Embedding
from qwen3_reranker_transformers import Qwen3Reranker

from config import Config
from modelscope import snapshot_download
from models import TokenizeRequest, TokenizeResponse, EmbeddingRequest,EmbeddingResponse,RerankRequest, RerankResponse, ModelInfo,ModelsResponse
import logging
logger = logging.getLogger(__name__)
config =Config()
print(f"准备下载{config.EMBEDDING_MODEL_NAME=}和{config.RERANK_MODEL_NAME=}模型")
embedding_model_name  = config.EMBEDDING_MODEL_NAME
embedding_model_dir = snapshot_download(embedding_model_name,cache_dir='/data/models/')
print(f"成功下载模型'{embedding_model_name}'到{embedding_model_dir=}")
rerank_model_dir = snapshot_download(config.RERANK_MODEL_NAME,cache_dir='/data/models/')
print(f"成功下载模型'{config.RERANK_MODEL_NAME}'到{rerank_model_dir=}")


NUM_REPLICAS = 1  # 这个表示你需要这个进程启动几份。
NUM_GPUS = 0.2  # 这个表示，每一份占用多少个gpu （这种小模型，不需要设置超过1）

# 当前参数表示，会启动2份，第1，2，3会在显卡1上。第4，5，6会在显卡2上。


## example 2
# NUM_REPLICAS = 6
# NUM_GPUS = 0.5
# 当前参数表示，会启动6份，第1，2会在显卡1上。第3，4会在显卡2上。5，6会在显卡3上。

## example 3
# NUM_REPLICAS = 2
# NUM_GPUS = 0.6
# 当前参数表示，会启动2份，第1会在显卡1上。第2会在显卡2上

ray.init(dashboard_host="0.0.0.0", dashboard_port=8266, include_dashboard=True, log_to_driver=True)
app = FastAPI()
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@serve.deployment(num_replicas=NUM_REPLICAS, ray_actor_options={"num_gpus": NUM_GPUS})
@serve.ingress(app)
class BatchCombineInferModel:
    def __init__(
        self, model_name_or_path_embedding: str=embedding_model_dir , model_name_or_path_reranker: str=rerank_model_dir
    ):
        self.emodel_embedding = Qwen3Embedding(
            model_name_or_path=model_name_or_path_embedding,
        )
        self.model_reranker = Qwen3Reranker(
            model_name_or_path=model_name_or_path_reranker,
            instruction="Retrieval document that can answer user's query",
            max_length=8192,
            use_cuda=False,  # 设置为False以避免使用GPU
        )

    @app.post("/v1/embeddings", response_model=EmbeddingResponse)
    def create_embedding(self, request: EmbeddingRequest):
        logger.warning(f"EmbeddingRequest:{request}")
        print(f"EmbeddingRequest:{request}",flush=True)

        with torch.inference_mode():
            output = self.emodel_embedding.encode(request.input, is_query= False,dim=request.dim)
            embeddings = output.cpu().detach().numpy().tolist()
                # 组织返回格式
        data = [
            {
                "object": "embedding",
                "embedding": emb,
                "index": idx
            }
            for idx, emb in enumerate(embeddings)
        ]

        return EmbeddingResponse(
            data=data,
            model=embedding_model_name
        )


    @app.post("/v1/rerank", response_model=RerankResponse)    
    def create_rerank(self,request: RerankRequest):
        # logger.warning(f"RerankRequest:{request}")
        with torch.inference_mode():
            if isinstance(request.query, str):
                pairs = [(request.query, doc) for doc in request.documents]
            else:
                pairs = list(itertools.product(request.query, request.documents))
                # pairs = list(zip(request.query, request.documents))
            # logger.warning(f"pairs:{pairs}")

            instruction = "Given the user query, retrieval the relevant passages"
            scores = self.model_reranker.compute_scores(pairs, instruction)
            # logger.warning(f"scores:{scores}")
            # 组织返回数据

            if request.return_documents:
                data = [
                    {
                        "score": score,
                        "index": idx,
                        "query_document_pairs": pairs[idx],
                    }
                    for idx, score in enumerate(scores)
                ]
            else:
                data = [
                    {
                        "score": score,
                        "index": idx,
                    }
                    for idx, score in enumerate(scores)
                ]
            # logger.warning(f"排序前的data:{data}")
            # 将返回列表结果转换为按score降序排序结果
            sorted_data = sorted(data,key=lambda x: x["score"], reverse=True)
            # logger.warning(f"排序后的data:{sorted_data}")
  
            if request.top_n is not None:
                sorted_data = sorted_data[:request.top_n]
                # logger.warning(f"排序后的data {request.top_n=}:{sorted_data}")

            return RerankResponse(
                model=config.RERANK_MODEL_NAME,
                results=sorted_data,           
            )
    @app.get("/v1/models", response_model=ModelsResponse)
    def get_models(self):
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
    def get_model_description(self):
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
    def get_model_description(self):
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
    def get_cluster_auth(self):
        # 返回集群认证信息
        auth_info = {
            "auth": True,
        }
        return auth_info

serve.start(http_options=HTTPOptions(host="0.0.0.0", port=8090))


serve.run(
    BatchCombineInferModel.bind(
        embedding_model_dir, rerank_model_dir
    ),
    route_prefix="/",
)


while True:
    time.sleep(1000)

# ray stop --force