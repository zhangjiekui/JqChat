# source: https://learn.deeplearning.ai/courses/ai-agents-in-langgraph/lesson/3/langgraph-components
print('参考：https://learn.deeplearning.ai/courses/ai-agents-in-langgraph/lesson/3/langgraph-components')
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
import operator
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage, SystemMessage, HumanMessage, ToolMessage, AIMessage
from langchain_openai import ChatOpenAI
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_openai import ChatOpenAI
from langchain import hub

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.aiosqlite import AsyncSqliteSaver

from jqcode.jq_agent.c0_init_env_models import get_langchain_chat_model
from jqcode.jq_agent.tools.jq_functions_and_tools import get_flight_number,python_repl_tool
import shortuuid
from dotenv import load_dotenv
_ = load_dotenv()




class GraphAgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]

class GraphAgent:
    def __init__(self,tools:list, llm_model:ChatOpenAI=None, recursion_limit:int=25, memory_thread_id:str=shortuuid.uuid()) -> None:
        
        _tool_names = [tool.name for tool in tools]
        _tool_names_str = ','.join(_tool_names)
        _system_message_content = f"Solve/Answer user's questions as best as you can. You have access to the following tools:{_tool_names_str}.You are allowed to make multiple calls (either together or in sequence)."

        if llm_model is None:
            llm_model = get_langchain_chat_model()

        self.tools = {t.name: t for t in tools} 
        self.model = llm_model.bind_tools(tools)
               
        self.system_message = [SystemMessage(content=_system_message_content)]
        self.config =  {"recursion_limit":recursion_limit,"configurable": {"thread_id":memory_thread_id }}
        self.memory = SqliteSaver.from_conn_string("checkpoints.sqlite")
        self.graph = self.graph_definition()
        self.state = self.graph.get_state(config=self.config).values
        
    
    def graph_definition(self,):
        graph = StateGraph(GraphAgentState)
        graph.add_node("llm",self.call_llm)
        graph.add_node("action", self.take_action)
        graph.add_conditional_edges(
            "llm",
            self.exists_action,
            {True: "action", False: END}
        )
        graph.add_edge("action", "llm")
        graph.set_entry_point("llm")
        return graph.compile(checkpointer=self.memory)
    
    def take_action(self, state:GraphAgentState):
        tool_calls = state['messages'][-1].tool_calls
        results = []
        for t in tool_calls:
            print(f"LLM Returned tool_calling: ")
            print(f"    Tool_name:{ t['name']}")
            print(f"    Tool_args: {t['args']}")
            if not t['name'] in self.tools:      # check for bad tool name from LLM
                print("\n ....bad tool name....")
                result = "bad tool name, retry"  # instruct LLM to retry if bad
            else:
                result = self.tools[t['name']].invoke(t['args'])
            results.append(ToolMessage(tool_call_id=t['id'], name=t['name'], content=str(result)))
        print("Back to the model!")
        return {'messages': results}
    
    def exists_action(self,state:GraphAgentState):
        result = state['messages'][-1]
        returned_tool_calling = len(result.tool_calls)
        if returned_tool_calling>0:
            print(f'{returned_tool_calling} tool_calls')            
        else:
            print('No returned tool_calling')
            print(f'{type(result)}: {result.content}')
            print(f'finish_reason: {result.response_metadata["finish_reason"]}')
        return returned_tool_calling
    
    def call_llm(self,state: GraphAgentState):
        messages = state['messages']
        # for m in messages:
        #     m.pretty_print()

        # todo add message filter
        # messages = [m for m in messages if isinstance(m,(HumanMessage, AIMessage))] 

        if self.system_message:
            messages = self.system_message + messages
            print(f"{len(messages)=}")
        message = self.model.invoke(messages,config=self.config)
        return {'messages': message}
    



tavily_search_tool = TavilySearchResults(max_results=4) #increased number of results
tools = [tavily_search_tool,get_flight_number,python_repl_tool]
abot = GraphAgent(tools=tools)

def run(abot):
    user_questions = [
    # '请查询明天从合肥到上海的航班',
    # '请计算1到100的和',
    "What is the weather in SF and LA? ",
    "Who won the super bowl in 2024? In what state is the winning team headquarters located?What is the GDP of that state? ",
    ]
    for user_question in user_questions:
        print('================='*5) 
        print(f"USER：{user_question}")
        messages = [HumanMessage(content=user_question)]
        result = abot.graph.invoke({"messages": messages},config=abot.config)
    
        print(f"AI：{result['messages'][-1].content}")
        print('================='*5)

def run_tavily_search():
    import os
    from tavily import TavilyClient
    api_key=os.environ.get("TAVILY_API_KEY")
    client = TavilyClient(api_key=api_key)
    # run search
    result = client.search("What is in Nvidia's new Blackwell GPU?",
                        include_answer=True)

    # print the answer
    print(result["answer"])
def run_regula_search(query):
    import requests
    from bs4 import BeautifulSoup
    from duckduckgo_search import DDGS
    import re

    ddg = DDGS()
    def search(query=query, max_results=6):
        try:
            results = ddg.text(query, max_results=max_results)
            return [i["href"] for i in results]
        except Exception as e:
            print(f"returning previous results due to exception reaching ddg:{e}")
            results = [ # cover case where DDG rate limits due to high deeplearning.ai volume
                "https://weather.com/weather/today/l/USCA0987:1:US",
                "https://weather.com/weather/hourbyhour/l/54f9d8baac32496f6b5497b4bf7a277c3e2e6cc5625de69680e6169e7e38e9a8",
            ]
            return results  


    for i in search(query):
        print(i)


if __name__ == "__main__":
    run(abot)
    # run_tavily_search()
    # run_regula_search("What is the weather in SF and LA? ")

# source: https://learn.deeplearning.ai/courses/ai-agents-in-langgraph/lesson/3/langgraph-components    