import requests
from config import Config
config =Config()
def test_embedding_service(config=config):
    url = f"http://{config.HOST}:{config.PORT}/v1/embeddings"
    payload = {
        "input": ["Hello, world!", "FastAPI is great!"],
        "model": config.EMBEDDING_MODEL_NAME
    }
    
    response = requests.post(url, json=payload)
    
    if response.status_code == 200:
        print("Response from embedding service:")
        print(response.json())
    else:
        print(f"Error: {response.status_code} - {response.text}")

def test_tokenize_service(config=config):
    url = f"http://{config.HOST}:{config.PORT}/v1/tokenize"
    payload = {
        "input": "Hello, world!",
        "model": config.EMBEDDING_MODEL_NAME
    }
    
    response = requests.post(url, json=payload)
    
    if response.status_code == 200:
        print("Response from tokenize service:")
        print(response.json())
    else:
        print(f"Error: {response.status_code} - {response.text}")

def test_rerank_service(config=config):
    url = f"http://{config.HOST}:{config.PORT}/v1/rerank"
    payload = {
        "input": [
            {
                "query": "What is the capital of China?",
                "document": "The capital of China is Beijing."
            },
            {
                "query": "What is the capital of China?",
                "document": "Gravity is a force that attracts two bodies towards each other."
            }
        ],
        "model": config.RERANK_MODEL_NAME
    }
    
    response = requests.post(url, json=payload)
    
    if response.status_code == 200:
        print("Response from rerank service:")
        print(response.json())
    else:
        print(f"Error: {response.status_code} - {response.text}")

if __name__ == "__main__":
    print("\ntest_embedding_service:")
    test_embedding_service()
    print("\nTesting tokenize service:")
    test_tokenize_service()
    print("\nTesting rerank service:")
    test_rerank_service()