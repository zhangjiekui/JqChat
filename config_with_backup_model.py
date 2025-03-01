# pip install langchain langchain-openai langchain-anthropic
from langchain.chat_models import init_chat_model
from pydantic import BaseModel, Field

class GetWeather(BaseModel):
    '''Get the current weather in a given location'''

    location: str = Field(..., description="The city and state, e.g. San Francisco, CA")

class GetPopulation(BaseModel):
    '''Get the current population in a given location'''
    location: str = Field(..., description="The city and state, e.g. San Francisco, CA")


configurable_model_with_default = init_chat_model(
    model="qwen25b70",
    model_provider="openai",
    configurable_fields="any",  # this allows us to configure other params like temperature, max_tokens, etc at runtime.
    base_url = "http://10.1.150.105:9997/v1",
    api_key = 'abc123',
    config_prefix="backup",
    temperature=0
)

print("=======================================Result1=======================================")
q="""<think>\n好的，我现在需要解决用户的问题：“Which city is hotter today and which is bigger: LA or NY?”。首先，我需要确定用户需要哪些信息。用户想知道两个城市中哪个更热，哪个更大。\n\n首先，用户的问题涉及到两个不同的数据：天气和人口。因此，我需要确定需要调用哪些工具。用户的问题涉及到两个不同的方面：温度和人口。所以需要分别处理。\n\n首先，关于天气，用户问哪个城市更热，所以需要获取LA和NY的当前天气情况。因此需要使用GetWeather工具来获取这两个城市的天气数据，比较温度。然后，关于哪个城市更大，可能需要比较人口或面积，用户可能是指人口多少，所以需要获取两个城市的人口数据，使用GetPopulation工具。\n\n接下来，确定需要调用的工具。用户的问题涉及到两个不同的数据点：天气和人口。所以需要分别调用GetWeather和GetPopulation工具。对于天气，需要分别查询LA和NY的天气数据，然后比较温度。对于人口，需要获取两个城市的人口数据进行比较。\n\n接下来，确定参数。每个工具需要location参数，即城市名称。对于GetWeather，每个城市调用一次，或者是否支持多城市查询？根据工具定义，每个GetWeather调用可能需要单独的城市参数。所以可能需要为每个城市分别调用GetWeather。同样，GetPopulation也需要location参数，分别获取两个城市的人口数据。\n\n因此，需要调用GetWeather两次（分别针对LA和NY），以及GetPopulation两次（分别获取LA和NY的人口）。或者，是否工具支持多个地点一次查询？根据工具定义，每个工具的参数是location字符串，每个请求一个location。因此，每个城市需要单独调用。\n\n所以，对于天气，需要调用GetWeather两次：location分别为"Los Angeles, CA"和"New York, NY"。对于人口，同样需要两次GetPopulation调用，参数分别为"Los Angeles, CA"和"New York, NY"。\n\n所以，最终需要调用GetWeather两次，每次一个城市，以及GetPopulation两次。或者，是否可以将location参数设置为数组？但根据工具定义，location参数是字符串，所以需要分别调用。\n\n因此，需要生成四个工具调用：两次GetWeather（分别针对LA和NY）和两次GetPopulation（同样分别处理）。或者，是否可以将两个城市合并到一个调用中？例如，可以一次获取多个城市的数据？但根据工具定义，每个工具的参数是location字符串，所以每次只能查询一个地点。因此，需要为每个城市分别调用。\n\n所以，正确的调用应该是：\n\n调用GetWeather两次，分别传递location为"Los Angeles, CA"和"New York, NY"。同样，调用GetPopulation两次，同样分别处理LA和NY。\n\n因此，最终需要生成四个工具调用：两次GetWeather和两次GetPopulation，每个调用对应一个城市。\n\n所以，生成的JSON结构应包含四个action，每个对应一个工具调用。例如：\n\n[\n  {\n    "tool": "GetWeather",\n    "parameters": {\n      "location": "Los Angeles, CA"\n    }\n  },\n  {\n    "tool": "GetWeather",\n    "parameters": {\n      "location": "New York, NY"\n    }\n  },\n  {\n    "tool": "GetPopulation",\n    "parameters": {\n      "location": "Los Angeles, CA"\n    }\n  },\n  {\n    "tool": "GetPopulation",\n    "parameters": {\n      "location": "New York, NY"\n    }\n  }\n]\n\n这样，通过四次调用获取所有必要的数据，然后比较结果，确定哪个城市更热（温度更高），以及哪个城市更大（人口更多）。\n\n所以，正确的JSON结构应该包含这四个调用。\n</think>\n\n```json\n[\n  {\n    "tool": "GetWeather",\n    "parameters": {\n      "location": "Los Angeles, CA"\n    }\n  },\n  {\n    "tool": "GetWeather",\n    "parameters": {\n      "location": "New York, NY"\n    }\n  },\n  {\n    "tool": "GetPopulation",\n    "parameters": {\n      "location": "Los Angeles, CA"\n    }\n  },\n  {\n    "tool": "GetPopulation",\n    "parameters": {\n      "location": "New York, NY"\n    }\n  }\n]\n```' additional_kwargs={'refusal': None} response_metadata={'token_usage': {'completion_tokens': 1, 'prompt_tokens': 1, 'total_tokens': 2, 'completion_tokens_details': None, 'prompt_tokens_details': None}, 'model_name': 'not implmented', 'system_fingerprint': 'not implmented', 'finish_reason': None, 'logprobs': None} id='run-46c81c3f-26a1-4dde-8793-04eba7698978-0' usage_metadata={'input_tokens': 1, 'output_tokens': 1, 'total_tokens': 2, 'input_token_details': {}, 'output_token_details': {}}"""
r1 = configurable_model_with_default.invoke(q)
print(r1)


# print("=======================================Result2=======================================")
# r2 = configurable_model_with_default.invoke(
#     "单词strawberry中有多少个字母“r”？",
#     config={
#         "configurable": {
#             "backup_model": "DeepSeekR1",
#             "backup_base_url":"http://10.1.150.105:8080/v1",
#             "backup_temperature": 0.6
#         }
#     }
# )
# print(r2)


configurable_model_with_tools = configurable_model_with_default.bind_tools([GetWeather, GetPopulation])
# print(configurable_model_with_tools.__annotations__)
# print(configurable_model_with_tools._queued_declarative_operations)
print("=======================================ResultTool1=======================================")
r1_tool = configurable_model_with_tools.invoke(
    q
)
print(r1_tool)


print("=======================================ResultTool2=======================================")
prompt =     """现在定义了两个工具：
    class GetWeather(BaseModel):
        '''Get the current weather in a given location'''

        location: str = Field(..., description="The city and state, e.g. San Francisco, CA")

    class GetPopulation(BaseModel):
        '''Get the current population in a given location'''
        location: str = Field(..., description="The city and state, e.g. San Francisco, CA")
    用户的问题是：
    Which city is hotter today and which is bigger: LA or NY?",
    请返回要调用的工具及参数，要满足openai的规范（Json格式）
    """
r2_tool = configurable_model_with_tools.invoke(prompt,
        config={
        "configurable": {
                "backup_model": "DeepSeekR1",
                "backup_base_url":"http://10.1.150.105:8080/v1",
                "backup_temperature": 0.6
            }
        }
)
print(r2_tool)
