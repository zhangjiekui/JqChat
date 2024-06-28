from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
import operator
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage, SystemMessage, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_openai import ChatOpenAI

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.aiosqlite import AsyncSqliteSaver

from jqcode.jq_agent.c0_init_env_models import get_langchain_chat_model

from dotenv import load_dotenv
_ = load_dotenv()
tool = TavilySearchResults(max_results=4) #increased number of results
print(type(tool))
print(tool.name)

class GraphAgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    #  Annotated[list, add_messages]
    added_messages: Annotated[list[AnyMessage], add_messages]

class GraphAgent:
    def __init__(self,llm_model:ChatOpenAI, tools:list, system_prompt:str,config= {"recursion_limit":25,"configurable": {"thread_id": "UserName_SessionID"}}) -> None:
        if llm_model is None:
            llm_model = get_langchain_chat_model()
        
        self.model = llm_model.bind_tools(tools)
        self.tools = {t.name: t for t in tools}        
        self.system_message_content = system_prompt
        self.config = config
        self.memory = SqliteSaver.from_conn_string("checkpoints.sqlite")
        self.graph = self.graph_definition()
        self.state = self.graph.get_state(config=self.config)
        
    
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
            print(f"Tool_Calling: {t}")
            if not t['name'] in self.tools:      # check for bad tool name from LLM
                print("\n ....bad tool name....")
                result = "bad tool name, retry"  # instruct LLM to retry if bad
            else:
                result = self.tools[t['name']].invoke(t['args'])
            results.append(ToolMessage(tool_call_id=t['id'], name=t['name'], content=str(result)))
        print("Back to the model!")
        return {'messages': results, 'added_messages':results}
    
    def exists_action(self,state:GraphAgentState):
        result = state['messages'][-1]
        return len(result.tool_calls) > 0
    
    def call_llm(self,state: GraphAgentState):
        messages = state['messages']
        if self.system_message_content:
            messages = [SystemMessage(content=self.system_message_content)] + messages
        message = self.model.invoke(messages,config=self.config)
        return {'messages': message, 'added_messages':message}
    
prompt = """You are a smart research assistant. Use the search engine to look up information. \
You are allowed to make multiple calls (either together or in sequence). \
Only look up information when you are sure of what you want. \
If you need to look up some information before asking a follow up question, you are allowed to do that!
"""


abot = GraphAgent(llm_model=None, tools=[tool], system_prompt=prompt)
user_questions = [
    "What is the weather in SF and LA?",
    "Who won the super bowl in 2024? In what state is the winning team headquarters located?What is the GDP of that state? Answer each question.",
    ]
for user_question in user_questions:
    messages = [HumanMessage(content=user_question)]
    result = abot.graph.invoke({"messages": messages, 'added_messages':messages},config=abot.config)
    print('================='*10)
    print(f"USER：{user_question}")
    print(f"AI：{result['messages'][-1].content}")
    print('================='*10)

    