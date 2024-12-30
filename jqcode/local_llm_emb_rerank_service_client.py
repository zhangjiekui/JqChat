from openai import OpenAI,AsyncOpenAI
import requests
import logging
logger = logging.getLogger()
logger.warning(f"OpenAICompletionProvider initialized by")

# client_llm = OpenAI(api_key='abc123',base_url='http://10.1.150.105:9997/v1')
# response = client_llm.chat.completions.create(messages=[{'role':'system','content':'start conversation'},{'role':'user','content':'你好'}],model='qwen25b70',max_tokens=100)
# print(response)

# client_embedding = OpenAI(api_key='abc123',base_url='http://10.1.150.106:9997/v1')
# response_embedding = client_embedding.embeddings.create(input="测试文本",model='bce-embedding-base_v1',dimensions=512)
# print(response_embedding)


from litellm import embedding,completion
response_lite_embdding = embedding(input="测试文本",model='bce-embedding-base_v1',dimensions=768,api_base="http://10.1.150.106:9997/v1",custom_llm_provider="xinference")
# response_lite_completion = completion(messages=[{'role':'system','content':'start conversation'},{'role':'user','content':'你好'}],model='qwen25b70',max_tokens=100,base_url='http://10.1.150.105:9997/v1',custom_llm_provider="xinference")
# print(response_lite_completion)

response_lite_completion2 = completion(messages=[{'role':'system','content':'start conversation'},{'role':'user','content':'你好'}],model='qwen25b70',max_tokens=100,api_base='http://10.1.150.105:9997/v1',custom_llm_provider="xinference")
print(response_lite_completion2)


rerank_model="jina-reranker-v2"
rerank_url='http://10.1.150.106:9997/v1/rerank'
def rerank(
    query: str,
    texts,
    limit: int = 2,
):

        payload = {
            "model": rerank_model,
            "query": query,
            "documents": texts,
            "top_n": limit,
        }

        headers = {"Content-Type": "application/json"}

        try:
            response = requests.post(
                rerank_url, json=payload, headers=headers
            )
            response.raise_for_status()
            reranked_results = response.json()
            print(reranked_results)

            # Copy reranked results into new array
            scored_results = []
            # {'index': 2, 'relevance_score': 0.96875, 'document': None}
            for rank_info in reranked_results.get("results", []):
                score = rank_info["relevance_score"]
                scored_results.append(score)

            # Return only the ChunkSearchResult objects, limited to specified count
            return scored_results[:limit]

        except requests.RequestException as e:
            print(f"Error during reranking: {e}")
            return None
        
r = rerank("测试文本",["测试文本","测试文本","测试文本"])
