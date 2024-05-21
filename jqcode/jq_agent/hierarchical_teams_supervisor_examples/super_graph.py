# source: https://langchain-ai.github.io/langgraph/tutorials/multi_agent/hierarchical_agent_teams/?h=hierarchical+teams

from typing import Any, Callable, List, Optional, TypedDict, Union, Annotated
import functools

# create_tool_calling_agent是Langchain(v0.1.16)最新推出的统一的ToolAgent接口！
from langchain.agents import AgentExecutor, create_tool_calling_agent

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import BaseMessage, HumanMessage,SystemMessage,ToolMessage,AIMessage

from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from langgraph.graph.message import add_messages

from langgraph.graph import END, StateGraph

from jqcode.jq_agent.c0_init_env_models import get_langchain_chat_model
from jqcode.jq_agent.hierarchical_teams_supervisor_examples.graph_create_utils import create_team_supervisor, create_agent, agent_node
from jqcode.jq_agent.hierarchical_teams_supervisor_examples.sub_graphs.research_sub_graph import research_chain
from jqcode.jq_agent.hierarchical_teams_supervisor_examples.sub_graphs.writing_sub_graph import authoring_chain

# 一、创建总图
llm = get_langchain_chat_model()
supervisor_node = create_team_supervisor(
    llm,
    "You are a supervisor tasked with managing a conversation between the"
    " following teams: {team_members}. Given the following user request,"
    " respond with the worker to act next. Each worker will perform a"
    " task and respond with their results and status. When finished,"
    " respond with FINISH.",
    ["Research team", "Paper writing team"],
)

# Top-level graph state
class SuperState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    next: str

def get_last_message(state: SuperState) -> str:
    return {"content":state["messages"][-1].content,'next':state["next"]}

def join_graph(response: dict):
    return {"messages": [response["messages"][-1]]}


# Define the super graph.
super_graph = StateGraph(SuperState)
# First add the nodes, which will do the work
super_graph.add_node("Research team", get_last_message | research_chain | join_graph)
super_graph.add_node(
    "Paper writing team", get_last_message | authoring_chain | join_graph
)
super_graph.add_node("supervisor", supervisor_node)

# Define the graph connections, which controls how the logic
# propagates through the program
super_graph.add_edge("Research team", "supervisor")
super_graph.add_edge("Paper writing team", "supervisor")
super_graph.add_conditional_edges(
    "supervisor",
    lambda x: x["next"],
    {
        "Paper writing team": "Paper writing team",
        "DEFAULT":"Paper writing team", # "DEFAULT"设置
        "Research team": "Research team",
        "FINISH": END,
    },
)
super_graph.set_entry_point("supervisor")
super_graph = super_graph.compile()
