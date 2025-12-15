import openai
from openai import OpenAI

# model_name='coder'
# endpoint = f"http://192.168.44.200:8000/v1"
model_name='kimi'
endpoint = f"http://192.168.44.200:9000/v1"
temperature = 0.7
max_tokens = 12800
client = OpenAI(base_url=f"{endpoint}",api_key='xxx')
def simple_chat(query: str,client: openai.OpenAI=client, model_name: str=model_name ):
    print("=====simple_chat result======")
    print(f"query: {query}")
    
    messages = [
        {"role": "system", "content": "You are Kimi, an AI assistant created by Moonshot AI."},
        {"role": "user", "content": [{"type": "text", "text": query}]},
    ]
    response = client.chat.completions.create(
        model=model_name,
        messages=messages,
        stream=False,
        temperature=temperature,
        max_tokens=max_tokens,
        frequency_penalty=0.5,
        presence_penalty=0.1,
        # top_p=0.8,
        # extra_body={"repetition_penalty": 1.05,"min_p": 0.01,"top_k": 20},
        extra_body={"min_p": 0.01},
    )
    print("-----------------------------")
    print(f"answer: {response.choices[0].message.content}")
    print(f"reasoning content: {response.choices[0].message.reasoning_content}")
    print("========================================================")


if __name__ == "__main__":
    questions =  ["数字9.11与9.9，哪个更大？","合肥工业大学介绍","中国科学技术大学介绍","请写一篇5000字的黄山旅游论文"]
    for question in questions:
        simple_chat(question)


