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
from graph_create_utils import create_team_supervisor, create_agent, agent_node, get_graph_nodes,get_custom_supervisor_node,get_last_state,llm
from hierarchical_teams_supervisor_examples.sub_graphs.research_sub_graph import research_chain
from hierarchical_teams_supervisor_examples.sub_graphs.writing_sub_graph import authoring_chain

# 一、创建总图

members = ["Research team", "Paper writing team"]
supervisor_node = create_team_supervisor(
    llm,
    "记住，我为你提供了可以可靠上网、执行python代码和绘制图表的工具和环境！You are a supervisor tasked with managing a conversation between the"
    " following teams: {team_members}. Given the following user request,"
    " respond with the worker to act next. Each worker will perform a"
    " task and respond with their results and status. When finished,"
    " respond with FINISH.",
    members,
)

# Top-level graph state
class SuperState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    response_message:str ="FIRST"
    next: str
    retry_n_times:int = 0

def join_graph(response: dict):
    return {"messages": [response["messages"][-1]],"response_message":None}


# Define the super graph.
super_graph = StateGraph(SuperState)
# First add the nodes, which will do the work

custom_supervisor_node = get_custom_supervisor_node(supervisor_node, members)
super_graph.add_node("supervisor", custom_supervisor_node)

super_graph.add_node("Research team", get_last_state | research_chain | join_graph)
super_graph.add_node("Paper writing team", get_last_state | authoring_chain | join_graph)


# Define the graph connections, which controls how the logic
# propagates through the program
super_graph.add_edge("Research team", "supervisor")
super_graph.add_edge("Paper writing team", "supervisor")
super_graph.add_conditional_edges(
    "supervisor",
    lambda x: x["next"],
    {
        "Paper writing team": "Paper writing team",
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
