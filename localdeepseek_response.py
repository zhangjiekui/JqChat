import os
from langchain.chat_models import init_chat_model
# model = init_chat_model(model="DeepSeekR1", model_provider="openai",base_url='http://10.1.150.105:8080/v1')
# result=model.invoke("我有一个搜索工具,Web_Search(str:query),你需要首先判断用户问题是否需要搜索，如果需要搜索，还需要判断该问题是否要分解成多个子搜索，如安徽省会2024年的GDP是多少？则需要生成搜索，首先搜索安徽的省会是哪个城市？（搜索到的结果是合肥），然后再搜索2024年合肥的GPD是多少。现在的用户问题为：Who won the super bowl in 2024? In what state is the winning team headquarters located?What is the GDP of that state?。请帮我规划如何通过Web_Search(str:query)工具调用得到问题答案")
# print(result)


import os
from langchain.chat_models import init_chat_model
from langchain_community.tools import TavilySearchResults
from langchain_core.tools import Tool
from langgraph.prebuilt import create_react_agent
from jqcode.jq_agent.tools.jq_web_search_engine_async import get_web_search_documents as async_search
from jqcode.jq_agent.tools.jq_web_search_engine import get_web_search_documents as search

tool1 = Tool(
    name="JqSearchEngineTool",
    description="Comprehensive Jq Search Engine for recent results from web.",
    func=async_search,
)

tool2 = TavilySearchResults(
    max_results=5,
    search_depth="advanced",
    include_answer=True,
    include_raw_content=True,
    include_images=True,
    # include_domains=[...],
    # exclude_domains=[...],
    # name="...",            # overwrite default tool name
    # description="...",     # overwrite default tool description
    # args_schema=...,       # overwrite default args_schema: BaseModel
)
llm = init_chat_model(model="qwen25b70", model_provider="openai",base_url='http://10.1.150.105:9997/v1',api_key='abc123')
tools = [tool1,tool2]
system_message = "你是一个搜索专家，请根据用户问题进行必要的分解，并持续搜索直到获得满意的答案，使用的语言与用户提问的语言保持一致，默认使用中文"
agent = create_react_agent(model=llm,tools=tools, state_modifier=system_message, debug=True)
# agent.invoke("Who won the super bowl in 2024? In what state is the winning team headquarters located?What is the GDP of that state? ")
query = "Who won the super bowl in 2024? In what state is the winning team headquarters located?What is the GDP of that state? "
query = "2024年安徽省会城市的GDP是多少? "
messages_dict = await agent.ainvoke({"messages": [("user", query)]})
messages=messages_dict.get('messages',[])
print(f"{len(messages)=}")
print(f"{messages[-1].content}")

# messages_dict = agent.ainvoke({"messages": [("user", query)]})
# import asyncio
# messages_dict = asyncio.run(messages_dict)
# messages=messages_dict.get('messages',[])
# print(f"{len(messages)=}")

