import openai
from openai import OpenAI

model_name='coder'
endpoint = f"http://192.168.44.200:8000/v1"
model_name='kimi'
endpoint = f"http://192.168.44.200:9000/v1"
temperature = 1.0
top_p = 1.0
max_tokens = 12800
client = OpenAI(base_url=f"{endpoint}",api_key='xxx')
messages = [
        {"role": "system", "content": "You are Kimi, an AI assistant created by Moonshot AI."},
    ]

def simple_chat(query: str,client: openai.OpenAI=client, model_name: str=model_name ):
    global messages
    print("=====simple_chat result======")
    print(f"query: {query}")
    
    messages += [
        {"role": "user", "content": query},
    ]
    response = client.chat.completions.create(
        model=model_name,
        messages=messages,
        stream=False,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
        # frequency_penalty=0.5,
        # presence_penalty=0.1,
        # # extra_body={"repetition_penalty": 1.05,"min_p": 0.01,"top_k": 20},
        # extra_body={"min_p": 0.01},
    )
    print("========================================================")
    print("-----------------------------")
    answer = response.choices[0].message.content
    reasoning_content = response.choices[0].message.reasoning_content
    assistant_message = {"role": "assistant", "content":answer, "reasoning_content":reasoning_content }
    messages.append(assistant_message)
    print(f"answer: {answer}")    
    print("-----------------------------")
    print(f"reasoning content: {reasoning_content}")
    print("========================================================")


if __name__ == "__main__":
    # questions =  ["which one is bigger, 9.11 or 9.9? think carefully.","请写一篇5000字的黄山旅游论文","数值9.11与9.9，哪个更大？","合肥工业大学介绍","中国科学技术大学介绍","对上面的对话进行总结"]
    questions =  ["which one is bigger, 9.11 or 9.9? think carefully.","数值9.11与9.9，哪个更大？","合肥工业大学介绍","中国科学技术大学介绍","对上面的对话进行总结"]
    for question in questions:
        simple_chat(question)


