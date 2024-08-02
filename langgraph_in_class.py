# source: https://learn.deeplearning.ai/courses/ai-agents-in-langgraph/lesson/3/langgraph-components
print('参考：https://learn.deeplearning.ai/courses/ai-agents-in-langgraph/lesson/3/langgraph-components')
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated, Literal
from langchain_core.pydantic_v1 import BaseModel, Field

from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage, SystemMessage, HumanMessage, ToolMessage, AIMessage
from langchain_openai import ChatOpenAI
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_openai import ChatOpenAI
from langchain import hub
from langchain_core.tools import tool
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.aiosqlite import AsyncSqliteSaver

from jqcode.jq_agent.c0_init_env_models import env_models_instance
from jqcode.jq_agent.tools.jq_functions_and_tools import get_flight_number,python_repl_tool
from jqcode.jq_agent.jq_rag_agent_sub_graph import rag_sub_graph
# from jqcode.jq_agent.jq_rag_agent_sub_graph import WEB_SEARCH,VECTORSTORE,CODE_GENERATION,CODE_EXECUTION
import os
import shortuuid
from dotenv import load_dotenv
_ = load_dotenv()

### Router Data model
class DIRECT_RESPONCE(BaseModel):
    """
    Direct response. Answer user directly if you do know how to response.
    """
    query: str = Field(description="The question user want you to answer.")

class WEB_SEARCH(BaseModel):
    """
    The internet. Use web_search for questions that are related to anything else than agent memory , prompt engineering, and adversarial attacks, 特别是2024年及以后相关的问题及发生的事情.
    """
    query: str = Field(description="The query to use when searching the internet.")

class VECTORSTORE(BaseModel):
    """
    A vectorstore containing documents related to 晶奇公司、安徽晶奇网络科技股份有限公司、医疗卫生、医疗健康、医疗服务、医疗政策、medical treatment & health. 凡是与晶奇公司、安徽晶奇网络科技股份有限公司及医疗健康相关的问题，都必须使用vectorstore工具。MUST use the vectorstore for questions on these topics.
    """
    query: str = Field(description="The query to use when searching the vectorstore.")

class CODE_GENERATION(BaseModel):
    """
    Code Assistant/Code generation . Use programming code (preferred Python language) to slove a user question, if the question related to [code generating, file processing/analyzing, data exploring/analyzing/visualizing].
    """
    query: str = Field(description="The query to use when generating code.")

class CODE_EXECUTION(BaseModel):
    """
    Code execution/Code intepreter. When user providing a code snippet and asking for running/executing, w or w/o returning the result.
    """
    query: str = Field(description="The query to use when asking for running/executing a code snippet.")

class GraphAgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    question : str
    rag_graph_next:str = Literal["WEB_SEARCH", "VECTORSTORE", "CODE_GENERATION", "CODE_EXECUTION", "DIRECT_RESPONCE"]


class GraphAgent:
    def __init__(self,executable_tools:list, routing_tools_wrapped_in_class:list, llm_model:ChatOpenAI=None, recursion_limit:int=25, memory_thread_id:str=shortuuid.uuid()) -> None:
        
        _executable_tool_names = [tool.name for tool in executable_tools]
        _routing_tool_names = [tool.__name__ for tool in routing_tools_wrapped_in_class]
        _tool_names = _executable_tool_names + _routing_tool_names
        _tool_names_str = ','.join(_tool_names)
        _system_message_content = f"Solve/Answer user's questions as best as you can. You have access to the following tools:{_tool_names_str}.You are allowed to make multiple calls (either together or in sequence)."

        if llm_model is None:
            llm_model = env_models_instance.get_langchain_chat_model()

        
        self.all_tools = executable_tools + routing_tools_wrapped_in_class
        self.all_tools_names = _tool_names
        self.routing_tool_names = _routing_tool_names
        self.executable_tool_names = _executable_tool_names
        self.executable_tool_dict = {t.name: t for t in executable_tools} 

        self.model = llm_model.bind_tools(self.all_tools)
               
        self.system_message = [SystemMessage(content=_system_message_content)]
        self.config =  {"recursion_limit":recursion_limit,"configurable": {"thread_id":memory_thread_id }}
        self.memory = SqliteSaver.from_conn_string("checkpoints.sqlite")
        self.graph = self.graph_definition()
        self.state = self.graph.get_state(config=self.config).values
        
    
    def graph_definition(self,):
        graph = StateGraph(GraphAgentState)
        graph.add_node("llm",self.call_llm)
        graph.add_node("action", self.take_action)
        graph.add_node("Rag", rag_sub_graph.compile())
        graph.add_conditional_edges(
            "llm",
            self.exists_action,
            {True: "action", False: END , "Rag":"Rag"}
        )
        graph.add_edge("action", "llm")        
        graph.add_edge("Rag", END)
        graph.set_entry_point("llm")
        return graph.compile(checkpointer=self.memory)
    
    def take_action(self, state:GraphAgentState):
        tool_calls = state['messages'][-1].tool_calls
        results = []
        for t in tool_calls:
            print(f"LLM Returned tool_calling: ")
            print(f"    Tool_name:{ t['name']}")
            print(f"    Tool_args: {t['args']}")
            if not t['name'] in self.executable_tool_dict:      # check for bad tool name from LLM
                print("\n ....bad tool name....")
                result = "bad tool name, retry"  # instruct LLM to retry if bad
            else:
                try:
                    result = self.executable_tool_dict[t['name']].invoke(t['args'])
                    print(f"{t['name']}({t['args']})的执行结果为:'{result}'")
                except Exception as e:
                    print(e)
                
            results.append(ToolMessage(tool_call_id=t['id'], name=t['name'], content=str(result)))
        print("Back to the model!")
        return {'messages': results}
    
    def exists_action(self,state:GraphAgentState):
        result = state['messages'][-1]
        print('*************** finish_reason ***************') 
        print(f'finish_reason: {result.response_metadata["finish_reason"]}')
        print('*************** finish_reason ***************') 
        returned_tool_calling_nums = len(result.tool_calls)
        os.environ["rag_graph_next"] = ''

        if returned_tool_calling_nums>0:
            print(f'Returned {returned_tool_calling_nums} tool_calls')
            if returned_tool_calling_nums>1:
                print(f'!!! Multitple  tool_calls !!!')
            tool_call_1 = result.tool_calls[0]
            tool_call_1_name = tool_call_1['name']

            if tool_call_1_name in self.routing_tool_names:
                print(f"Returned first ToolName is '{tool_call_1_name}', So routing to sub_graph 'Rag:{tool_call_1_name}' Node......")
                os.environ["rag_graph_next"] = tool_call_1_name
                os.environ['web_search_query'] = tool_call_1["args"]['query']
                return "Rag"
        else:
            print('No returned tool_calling')
            print(f'{type(result)}: {result.content}')
            
        return returned_tool_calling_nums
    
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
executable_tools = [get_flight_number,python_repl_tool]
route_tools = [WEB_SEARCH,VECTORSTORE,CODE_GENERATION,CODE_EXECUTION]
abot = GraphAgent(executable_tools=executable_tools,routing_tools_wrapped_in_class=route_tools)

def run(abot):
    user_questions = [
    '你好',
    '合肥大蜀山',   
    '请查询明天从合肥到上海的航班',
    '请使用python_repl_tool来计算1到100的和',
    "请使用tavily_search_tool工具搜索信息，回答问题：What is the weather in SF and LA? ",
    "Who won the super bowl in 2024? In what state is the winning team headquarters located?What is the GDP of that state? ",
    ]
    for user_question in user_questions:
        print('================='*5) 
        print(f"USER：{user_question}")
        messages = [HumanMessage(content=user_question)]
        result = abot.graph.invoke({"messages": messages,"question":user_question},config=abot.config)
        print('====问题和答案====') 
        print(f"USER：{user_question}")
        print(f"AI：{result['messages'][-1].content}")
        print('================='*5)


if __name__ == "__main__":
    run(abot)


# source: https://learn.deeplearning.ai/courses/ai-agents-in-langgraph/lesson/3/langgraph-components    