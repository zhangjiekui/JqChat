# source: https://learn.deeplearning.ai/courses/ai-agents-in-langgraph/lesson/3/langgraph-components
print('参考：https://learn.deeplearning.ai/courses/ai-agents-in-langgraph/lesson/3/langgraph-components')
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
import operator
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage, SystemMessage, HumanMessage, ToolMessage
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
        _system_message_content = f'Solve/Answer user questions as best you can. You have access to the following tools:{_tool_names_str}.\nnYou are allowed to make multiple calls (either together or in sequence).'

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
        returned_tool_calling = len(result.tool_calls) > 0
        if not returned_tool_calling:
            print('No returned tool_calling')
        return returned_tool_calling
    
    def call_llm(self,state: GraphAgentState):
        messages = state['messages']

        # todo add message filter
        if self.system_message:
            messages = self.system_message + messages
        message = self.model.invoke(messages,config=self.config)
        return {'messages': message}
    



tavily_search_tool = TavilySearchResults(max_results=4) #increased number of results
tools = [tavily_search_tool,get_flight_number,python_repl_tool]
abot = GraphAgent(tools=tools)

user_questions = [
    # '请查询明天从合肥到上海的航班',
    # '请计算1到100的和',
    # "What is the weather in SF and LA?",
    "Who won the super bowl in 2024? In what state is the winning team headquarters located?What is the GDP of that state? Answer each question.",
    ]
for user_question in user_questions:
    messages = [HumanMessage(content=user_question)]
    result = abot.graph.invoke({"messages": messages},config=abot.config)
    print('================='*5)
    print(f"USER：{user_question}")
    print(f"AI：{result['messages'][-1].content}")
    print('================='*5)

# source: https://learn.deeplearning.ai/courses/ai-agents-in-langgraph/lesson/3/langgraph-components    