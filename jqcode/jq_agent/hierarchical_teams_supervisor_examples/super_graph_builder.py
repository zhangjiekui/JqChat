# source: https://langchain-ai.github.io/langgraph/tutorials/multi_agent/hierarchical_agent_teams/?h=hierarchical+teams

import sys
from typing import Any, Callable, List, Optional, TypedDict, Union, Annotated
import functools

# create_tool_calling_agent是Langchain(v0.1.16)最新推出的统一的ToolAgent接口！
from langchain.agents import AgentExecutor, create_tool_calling_agent

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import BaseMessage, HumanMessage,SystemMessage,ToolMessage,AIMessage

from langchain_core.runnables import Runnable,RunnablePassthrough,RunnableLambda
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from langgraph.graph.message import add_messages

from langgraph.graph import END, StateGraph


# from jqcode.jq_agent.hierarchical_teams_supervisor_examples.graph_create_utils import create_team_supervisor,supervisor_post_process, create_agent, agent_node, get_graph_nodes,llm
# from jqcode.jq_agent.hierarchical_teams_supervisor_examples.sub_graphs.research_sub_graph import research_chain
# from jqcode.jq_agent.hierarchical_teams_supervisor_examples.sub_graphs.writing_sub_graph import authoring_chain
from graph_create_utils import create_team_supervisor, create_agent, agent_node, get_graph_nodes,llm
from hierarchical_teams_supervisor_examples.sub_graphs.research_sub_graph import research_chain
from hierarchical_teams_supervisor_examples.sub_graphs.writing_sub_graph import authoring_chain

# 一、创建总图
# llm = get_langchain_chat_model()
supervisor_node = create_team_supervisor(
    llm,
    "记住，我为你提供了可以可靠上网、执行python代码和绘制图表的工具和环境！You are a supervisor tasked with managing a conversation between the"
    " following teams: {team_members}. Given the following user request,"
    " respond with the worker to act next. Each worker will perform a"
    " task and respond with their results and status. When finished,"
    " respond with FINISH.",
    ["Research team", "Paper writing team"],
)

# Top-level graph state
class SuperState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    response_message:str ="FIRST"
    next: str
    retry_n_times:int = 0
def get_last_state(state: SuperState) -> dict:
    return state

def get_last_message(state: SuperState) -> dict:
    return state
    # response_message = state["response_message"]
    
    # if response_message is None or response_message=="FIRST":#刚进入super_graph的首次执行
    #     return {"messages": state["messages"], "retry_n_times":0}
    
    # message = state["messages"][-1]
    # if response_message == 'SUCCESS':
    #     return {"content":message.content,'next':state["next"], "retry_n_times":0}
    # else:
    #     _content = f'上次用户问题为:“{message.content}”\n但你未能正确回应用户问题，错误信息为:{response_message}请重新回应'
    #     message.content = _content
    #     retry_n_times =  state.get("retry_n_times",0)
    #     retry_n_times = retry_n_times+1 if retry_n_times else 1
    #     if retry_n_times>1:
    #         pass
    #     state["retry_n_times"] = retry_n_times
    #     print(f"{retry_n_times=}")
    #     if retry_n_times>3:
    #         print(f"无法正常导航到下一节点，已重试{retry_n_times}次，只好退出！")
            # sys.exit()

        # return {"messages": [message],"retry_n_times":retry_n_times}

def supervisor_post_process_node(toolcalls_and_state:dict) -> dict:
    from get_all_graph_nodes import all_members
    next = None
    tool_call_parsed_message =  None


    state = toolcalls_and_state["state"]
    message = state["messages"][-1]
    tool_calls_list = toolcalls_and_state['toolcalls']
    if tool_calls_list:
        tool_call_dict = tool_calls_list[0]       

        tool_call_dict_args = tool_call_dict['args']
        next = tool_call_dict_args.get('next',None)
        if next not in all_members: 
            next = None            
            tool_call_parsed_message = f"""工具调用返回的Json格式正确，但next参数值{next}不正确，必须是以下列表取值之一[{",".join(all_members)}]"""
            print(tool_call_parsed_message)
    else:
        next = None            
        tool_call_parsed_message = f"未返回有效的工具调用Json格式数据，请重试，务必返回有效的工具调用Json格式数据"
        print(tool_call_parsed_message)
    
    if next:
        return {"messages":state["messages"],'next':next}
    else:
        retry_n_times = 4
        for i in range(retry_n_times):
            _message = f'用户问题为:“{message.content}”\n 错误信息为:{tool_call_parsed_message}'
            retry_result = supervisor_node.invoke([_message])
            tool_calls_list = retry_result[0]
            if tool_calls_list:
                tool_call_dict_args = tool_calls_list['args']
                next = tool_call_dict_args.get('next',None)
                if next not in all_members: 
                    next = None            
                    tool_call_parsed_message = f"""工具调用返回的Json格式正确，但next参数值{next}不正确，必须是以下列表取值之一[{",".join(all_members)}]"""
                    print(tool_call_parsed_message)
                else:
                    return {"messages":state["messages"],'next':next}
    
    print(f"无法正常导航到下一节点，已重试{retry_n_times}次，只好退出！")
    sys.exit()

    
    

def join_graph(response: dict):
    return {"messages": [response["messages"][-1]],"response_message":None}


# supervisor_template_with_toolcalls_and_state = f"""
# state: {get_last_message}
# toolcalls:f{supervisor_node};
# """
# prompt = ChatPromptTemplate.from_template(supervisor_template_with_toolcalls_and_state)


# supervisor_chain = "toolcalls": | {"toolcalls": RunnablePassthrough(), "state": get_last_message} | supervisor_post_process

# supervisor_chain_RunnableLambda = RunnableLambda(get_last_message) | {

# }

supervisor_template_with_toolcalls_and_state_runnable = {
    "state": RunnablePassthrough(),
    "toolcalls":supervisor_node
} | RunnablePassthrough()

# supervisor_template_with_toolcalls_and_state_runnable.invoke({"messages": [HumanMessage(content="Hello")]})

# Define the super graph.
super_graph = StateGraph(SuperState)
# First add the nodes, which will do the work
super_graph.add_node("supervisor", get_last_state | supervisor_template_with_toolcalls_and_state_runnable | supervisor_post_process_node)
super_graph.add_node("Research team", get_last_message | research_chain | join_graph)
super_graph.add_node(
    "Paper writing team", get_last_message | authoring_chain | join_graph
)


# Define the graph connections, which controls how the logic
# propagates through the program
super_graph.add_edge("Research team", "supervisor")
super_graph.add_edge("Paper writing team", "supervisor")
super_graph.add_conditional_edges(
    "supervisor",
    lambda x: x["next"],
    {
        "Paper writing team": "Paper writing team",
        "SELF":"supervisor", # "SELF"设置
        "Research team": "Research team",
        "FINISH": END,
    },
)
super_graph.set_entry_point("supervisor")
# members = get_graph_nodes(super_graph)
# print(members)
# ['Research team', 'Paper writing team']
super_graph_compiled = super_graph.compile()
# 
