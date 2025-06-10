import logging
import math
import os
from copy import copy
from typing import Any

import litellm
import requests
from aiohttp import ClientError, ClientSession
from litellm import AuthenticationError, aembedding, embedding

from core.base import (
    ChunkSearchResult,
    EmbeddingConfig,
    EmbeddingProvider,
    EmbeddingPurpose,
    R2RException,
)

logger = logging.getLogger()


class LiteLLMEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        config: EmbeddingConfig,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(config)

        self.litellm_embedding = embedding
        self.litellm_aembedding = aembedding

        provider = config.provider
        if not provider:
            raise ValueError(
                "Must set provider in order to initialize `LiteLLMEmbeddingProvider`."
            )
        if provider != "litellm":
            raise ValueError(
                "LiteLLMEmbeddingProvider must be initialized with provider `litellm`."
            )

        self.rerank_url = config.rerank_url
        self.rerank_model=config.rerank_model

        self.api_base = config.api_base
        self.base_model = config.base_model


        if "amazon" in self.base_model:
            logger.warning("Amazon embedding model detected, dropping params")
            litellm.drop_params = True
        self.base_dimension = config.base_dimension

    def _get_embedding_kwargs(self, **kwargs):
        embedding_kwargs = {
            "api_base":self.api_base,
            "model": f"xinference/{self.base_model}",
            "dimensions": self.base_dimension,
            "custom_llm_provider":"xinference",
        }        
        embedding_kwargs.update(kwargs)
        logger.debug(f"Embedding kwargs: {embedding_kwargs}")
        return embedding_kwargs

    async def _execute_task(self, task: dict[str, Any]) -> list[list[float]]:
        texts = task["texts"]
        kwargs = self._get_embedding_kwargs(**task.get("kwargs", {}))

        if "dimensions" in kwargs and math.isnan(kwargs["dimensions"]):
            kwargs.pop("dimensions")
            logger.warning("Dropping nan dimensions from kwargs")

        try:
            response = await self.litellm_aembedding(
                input=texts,
                **kwargs,
            )
            return [data["embedding"] for data in response.data]
        except AuthenticationError:
            logger.error(
                "Authentication error: Invalid API key or credentials."
            )
            raise
        except Exception as e:
            error_msg = f"Error getting embeddings: {str(e)}"
            logger.error(error_msg)

            raise R2RException(error_msg, 400) from e

    def _execute_task_sync(self, task: dict[str, Any]) -> list[list[float]]:
        texts = task["texts"]
        kwargs = self._get_embedding_kwargs(**task.get("kwargs", {}))
        try:
            response = self.litellm_embedding(
                input=texts,
                **kwargs,
            )
            return [data["embedding"] for data in response.data]
        except AuthenticationError:
            logger.error(
                "Authentication error: Invalid API key or credentials."
            )
            raise
        except Exception as e:
            error_msg = f"Error getting embeddings: {str(e)}"
            logger.error(error_msg)
            raise R2RException(error_msg, 400) from e

    async def async_get_embedding(
        self,
        text: str,
        stage: EmbeddingProvider.Step = EmbeddingProvider.Step.BASE,
        purpose: EmbeddingPurpose = EmbeddingPurpose.INDEX,
        **kwargs,
    ) -> list[float]:
        if stage != EmbeddingProvider.Step.BASE:
            raise ValueError(
                "LiteLLMEmbeddingProvider only supports search stage."
            )

        task = {
            "texts": [text],
            "stage": stage,
            "purpose": purpose,
            "kwargs": kwargs,
        }
        logger.debug(f"Async_get_embedding ......")
        return (await self._execute_with_backoff_async(task))[0]

    def get_embedding(
        self,
        text: str,
        stage: EmbeddingProvider.Step = EmbeddingProvider.Step.BASE,
        purpose: EmbeddingPurpose = EmbeddingPurpose.INDEX,
        **kwargs,
    ) -> list[float]:
        if stage != EmbeddingProvider.Step.BASE:
            raise ValueError(
                "Error getting embeddings: LiteLLMEmbeddingProvider only supports search stage."
            )

        task = {
            "texts": [text],
            "stage": stage,
            "purpose": purpose,
            "kwargs": kwargs,
        }
        logger.debug(f"Get_embedding ......")
        return self._execute_with_backoff_sync(task)[0]

    async def async_get_embeddings(
        self,
        texts: list[str],
        stage: EmbeddingProvider.Step = EmbeddingProvider.Step.BASE,
        purpose: EmbeddingPurpose = EmbeddingPurpose.INDEX,
        **kwargs,
    ) -> list[list[float]]:
        if stage != EmbeddingProvider.Step.BASE:
            raise ValueError(
                "LiteLLMEmbeddingProvider only supports search stage."
            )

        task = {
            "texts": texts,
            "stage": stage,
            "purpose": purpose,
            "kwargs": kwargs,
        }
        return await self._execute_with_backoff_async(task)

    def get_embeddings(
        self,
        texts: list[str],
        stage: EmbeddingProvider.Step = EmbeddingProvider.Step.BASE,
        purpose: EmbeddingPurpose = EmbeddingPurpose.INDEX,
        **kwargs,
    ) -> list[list[float]]:
        if stage != EmbeddingProvider.Step.BASE:
            raise ValueError(
                "LiteLLMEmbeddingProvider only supports search stage."
            )

        task = {
            "texts": texts,
            "stage": stage,
            "purpose": purpose,
            "kwargs": kwargs,
        }
        return self._execute_with_backoff_sync(task)

    def rerank(
        self,
        query: str,
        results: list[ChunkSearchResult],
        stage: EmbeddingProvider.Step = EmbeddingProvider.Step.RERANK,
        limit: int = 10,
        min_score_threshold = 0.3
    ):
        if self.config.rerank_model is not None:
            if not self.rerank_url:
                raise ValueError(
                    "Error, `rerank_url` was expected to be set inside LiteLLMEmbeddingProvider"
                )

            texts = [result.text for result in results]
            if len(texts) == 0:
                logger.warning("由于传入的texts为空, 只好提供一段测试文本")
                texts = ["由于传入的texts为空", "只好提供一段测试文本"]

            payload = {
                "model": self.config.rerank_model,
                "query": query,
                "documents": texts,                
                "top_n": limit,
                "return_documents": True,
            }

            headers = {"Content-Type": "application/json"}
            logger.warning(f"SyncRerank kwargs: [rerank_model] {self.config.rerank_model},[rerank_url] {self.rerank_url}")

            try:
                response = requests.post(
                    self.rerank_url, json=payload, headers=headers
                )
                response.raise_for_status()
                reranked_results = response.json()

                # Copy reranked results into new array
                scored_results = []
                for rank_info in reranked_results['results']:
                    original_result = results[rank_info["index"]]
                    copied_result = copy(original_result)
                    # Inject the reranking score into the result object
                    copied_result.score = rank_info.get("score",rank_info.get("relevance_score",0))
                    if copied_result.score>min_score_threshold: 
                        scored_results.append(copied_result)

                # Return only the ChunkSearchResult objects, limited to specified count
                return scored_results[:limit]

            except requests.RequestException as e:
                logger.error(f"Error during reranking: {str(e)}")
                # Fall back to returning the original results if reranking fails
                return results[:limit]
        else:
            return results[:limit]

    async def arerank(
        self,
        query: str,
        results: list[ChunkSearchResult],
        stage: EmbeddingProvider.Step = EmbeddingProvider.Step.RERANK,
        limit: int = 10,
    ) -> list[ChunkSearchResult]:
        """Asynchronously rerank search results using the configured rerank
        model.

        Args:
            query: The search query string
            results: List of ChunkSearchResult objects to rerank
            limit: Maximum number of results to return

        Returns:
            List of reranked ChunkSearchResult objects, limited to specified count
        """
        if self.config.rerank_model is not None:
            if not self.rerank_url:
                raise ValueError(
                    "Error, `rerank_url` was expected to be set inside LiteLLMEmbeddingProvider"
                )

            texts = [result.text for result in results]
            if len(texts) == 0:
                logger.warning("由于传入的texts为空, 只好提供一段测试文本")
                texts = ["由于传入的texts为空", "只好提供一段测试文本"]

            payload = {
                "model": self.config.rerank_model,
                "query": query,
                "documents": texts,                
                "top_n": limit,
                "return_documents": True,
            }
            logger.debug(f"AsyncRerank kwargs: [rerank_model] {self.config.rerank_model},[rerank_url] {self.rerank_url}")
            headers = {"Content-Type": "application/json"}

            try:
                async with ClientSession() as session:
                    async with session.post(
                        self.rerank_url, json=payload, headers=headers
                    ) as response:
                        response.raise_for_status()
                        reranked_results = await response.json()

                        # Copy reranked results into new array
                        scored_results = []
                        for rank_info in reranked_results['results']:
                            original_result = results[rank_info["index"]]
                            copied_result = copy(original_result)
                            # Inject the reranking score into the result object
                            copied_result.score = rank_info.get("score",rank_info.get("relevance_score",0))
                            scored_results.append(copied_result)

                        # Return only the ChunkSearchResult objects, limited to specified count
                        return scored_results[:limit]

            except (ClientError, Exception) as e:
                logger.error(f"Error during async reranking: {str(e)}")
                # Fall back to returning the original results if reranking fails
                return results[:limit]
        else:
            return results[:limit]
