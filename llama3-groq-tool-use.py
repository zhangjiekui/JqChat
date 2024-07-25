# from langchain_ollama import ChatOllama
# from langchain.tools.render import render_text_description # to describe tools as a string 
# from langchain_core.tools import tool # tools for our llm

# import logging
# logging.basicConfig(level=logging.INFO)
# tools_logger = logging.getLogger("tools")
# @tool
# def accept(reason) -> int:
#     "Accept a reason and return 1."
#     tools_logger.info(f"Accepting reason: {reason}")
#     return 1


# @tool
# def reject(reason) -> int:
#     "Reject a reason and return 0."
#     tools_logger.info(f"Rejecting reason: {reason}")
#     return 0

# tools = [accept,reject]
# toos_dict = {tool.name:tool for tool in tools}
# rendered_tools = render_text_description(tools)
# print(rendered_tools)

# model_name = "llama3-groq-tool-use"
model_name = "llama3-groq-tool-use:8b-q8_0"
# # model_name = 'llama3-groq-tool-use:70b'
# llm = ChatOllama(model=model_name,format='json',temperature=0.5,top_p=0.65).bind_tools(tools)
# # llm = ChatOllama(model=model_name).bind_tools(tools)

# system_prompt = f"""You are an assistant that has access to functions.
# ONLY Use them:

# {rendered_tools}


# Given the user input, return the name and input of the tool to use.
# Return your response as a JSON blob with 'name' and 'arguments' keys.
# The value associated with the 'arguments' key should be a dictionary of parameters."""
# print("==========="*10)
# print(system_prompt)

# from datetime import datetime
# from openai import OpenAI

# def LLM(prompt, system_message, model=llm):
#     try:
#         messages=[{"role": "system", "content": system_message}, {"role": "user", "content": prompt}]
#         response = llm.invoke(messages)
#         print('Success:\n', response)
#         return response
#     except Exception as error:
#         print('Error:', error)
#         raise
# prompt = '使用python可以计算出3*10的正确结果，请思考这句话正确吗？并请给出理由'
# prompt = "Statement:Using Python can calculate out 3*10's correct result. Should you accept or reject the statement? and give me your reason"
# prompt = "Using Python can calculate out 3*10's correct result."
# prompt = "1+1=2"
# response = LLM(prompt,system_prompt)

# print("==========="*10)
# # print(response)
# if response.tool_calls:
#     for tool in response.tool_calls:
#          tool_name = tool['name']
#          tool_args = tool['args']['reason']
#          res = toos_dict[tool_name](tool_args)
#          print(f"Result:调用了工具:{tool_name}，调用参数为:{tool_args},运行结果为:{res}")


# print("###########"*10)
# prompt = '使用python无法计算出3*10的正确结果，请思考判断这句话正确吗？并请给出理由'
# prompt = "Statement:Using Python can not calculate out 3*10's correct result. Should you accept or reject the statement? and give me your reason"
# prompt = "1+1=3"
# response = LLM(prompt,system_prompt)


# # print(response)
# if response.tool_calls:
#     for tool in response.tool_calls:
#          tool_name = tool['name']
#          tool_args = tool['args']['reason']
#          res = toos_dict[tool_name](tool_args)
#          print(f"Result:调用了工具:{tool_name}，调用参数为:{tool_args},运行结果为:{res}")


print('======= OllamaFunctions ======='*3)
from langchain_experimental.llms.ollama_functions import OllamaFunctions
from langchain_core.messages import HumanMessage

model = OllamaFunctions(
    model=model_name, 
    keep_alive=-1,
    format="json"
    )

model = model.bind_tools(
    tools=[
        {
            "name": "get_current_weather",
            "description": "Get the current weather in a given location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city and state, " "e.g. San Francisco, CA",
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                    },
                },
                "required": ["location"],
            },
        }
    ],
    function_call={"name": "get_current_weather"},
)

response = model.invoke("what is the weather in Singapore?")

print(response.tool_calls)

