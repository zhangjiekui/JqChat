import json
import openai
from openai import OpenAI
import requests
from transformers import AutoTokenizer

# model_name='coder'
# endpoint = f"http://192.168.44.200:8000/v1"
model_name='kimi'
endpoint = f"http://192.168.44.200:9000/v1"
model_repo = 'moonshotai/Kimi-K2-Thinking'
temperature = 0.3
max_tokens = 4096


def extract_tool_call_info(tool_call_rsp: str):
    if '<|tool_calls_section_begin|>' not in tool_call_rsp:
        # No tool calls
        return []
    import re
    pattern = r"<\|tool_calls_section_begin\|>(.*?)<\|tool_calls_section_end\|>"
    
    tool_calls_sections = re.findall(pattern, tool_call_rsp, re.DOTALL)
    if len(tool_calls_sections) == 0:
        # No tool calls
        return []
    
    # Extract multiple tool calls
    func_call_pattern = r"<\|tool_call_begin\|>\s*(?P<tool_call_id>[\w\.]+:\d+)\s*<\|tool_call_argument_begin\|>\s*(?P<function_arguments>.*?)\s*<\|tool_call_end\|>"
    tool_calls = []
    for match in re.findall(func_call_pattern, tool_calls_sections[0], re.DOTALL):
        function_id, function_args = match
        # function_id: functions.get_weather:0
        function_name = function_id.split('.')[1].split(':')[0]
        tool_calls.append(
            {
                "id": function_id,
                "type": "function",
                "function": {
                    "name": function_name,
                    "arguments": function_args
                }
            }
        )
    print(f"extract_tool_call_info:{tool_calls}")  
    return tool_calls
# Your tool implementation
def get_weather(city: str) -> dict:
    return {"weather": "Sunny"}
# Tool schema definition
tools = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Retrieve current weather information. Call this when the user asks about the weather.",
        "parameters": {
            "type": "object",
            "required": ["city"],
            "properties": {
                "city": {
                    "type": "string",
                    "description": "Name of the city"
                }
            }
        }
    }
}]
# Map tool names to their implementations
tool_map = {
    "get_weather": get_weather
}



## requests raw api test

print("=====1. requests raw api and tool call test======")
messages = [
    {"role": "user", "content": "What's the weather like in Beijing today? Let's check using the tool."}
]
msg = ''
tokenizer = AutoTokenizer.from_pretrained(model_repo, trust_remote_code=True)
while True:
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        tools=tools,
        add_generation_prompt=True,
    )

    print("    ----- text result of tokenizer.apply_chat_template ---- ")
    print(f"text: {text}")


    payload = {
        "model": model_name,
        "prompt": text,
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    response = requests.post(
        f"{endpoint}/completions", #f"{endpoint}/chat/completions",
        headers={"Content-Type": "application/json"},
        json=payload,
        stream=False,
    )
    raw_out = response.json()

    raw_output = raw_out["choices"][0]["text"]
    print(f"raw_output: {raw_output}")
    tool_calls = extract_tool_call_info(raw_output)
    if len(tool_calls) == 0:
        # No tool calls
        msg = raw_output
        break
    else:        
        for tool_call in tool_calls:
            tool_call_name = tool_call['function']['name']
            tool_call_arguments = json.loads(tool_call['function']['arguments'])
            tool_function = tool_map[tool_call_name]
            tool_result = tool_function(tool_call_arguments)

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call['id'],
                "name": tool_call_name,
                "content": json.dumps(tool_result), 
            })
print(msg)
print('-' * 100)          

## openai api test
print("=====2.openai api and tool call test======")
client = OpenAI(base_url=f"{endpoint}",api_key='xxx')
def openai_chat(client: openai.OpenAI, model_name: str):
    messages = [
        {"role": "system", "content": "You are Kimi, an AI assistant created by Moonshot AI."},
        {"role": "user", "content": [{"type": "text", "text": "数字9.11与9.9，哪个更大？"}]},
    ]
    response = client.chat.completions.create(
        model=model_name,
        messages=messages,
        stream=False,
        temperature=temperature,
        max_tokens=max_tokens
    )
    print("=====openai_chat======")
    print(f"k2 answer: {response.choices[0].message.content}")
    print("=====below is reasoning content======")
    print(f"reasoning content: {response.choices[0].message.reasoning_content}")
def tool_call_with_client(client: OpenAI, model_name: str):
    messages = [
        {"role": "system", "content": "You are Kimi, an AI assistant created by Moonshot AI."},
        {"role": "user", "content": "What's the weather like in Beijing today? Use the tool to check."}
    ]
    finish_reason = None
    print("=====tool_call_with_client======")
    while finish_reason is None or finish_reason == "tool_calls":
        completion = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=temperature,
            tools=tools,          # tool list defined above
            tool_choice="auto",
            max_tokens=max_tokens
        )
        choice = completion.choices[0]
        print(f"k2 answer: {choice.message.content}")
        print("=====below is reasoning content======")
        print(f"reasoning content: {choice.message.reasoning_content}")
        finish_reason = choice.finish_reason
        print(f"finish_reason: {finish_reason}")
        if finish_reason == "tool_calls":
            messages.append(choice.message)
            for tool_call in choice.message.tool_calls:
                tool_call_name = tool_call.function.name
                tool_call_arguments = json.loads(tool_call.function.arguments)
                tool_function = tool_map[tool_call_name]
                tool_result = tool_function(**tool_call_arguments)
                print("tool_result:", tool_result)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_call_name,
                    "content": json.dumps(tool_result)
                })
    print(choice.message.content)
    print("-" * 100)

if __name__ == "__main__":
    
    openai_chat(client, model_name)
    tool_call_with_client(client, model_name)
