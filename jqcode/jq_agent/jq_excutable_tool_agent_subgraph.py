from jq_agent.tools.jq_functions_and_tools import excutable_tool_node, excutable_tool_names, excutable_tool_names_str,get_flight_number,python_repl_tool
from jq_agent.graph_create_utils import create_graph_supervisor, create_agent, agent_node, sub_graph_enter_chain
from jq_agent.graph_create_utils import supervisor_post_process_node,get_last_state, get_custom_supervisor_node,llm
from langchain_core.runnables import Runnable,RunnablePassthrough,RunnableLambda
from typing import Annotated, List, TypedDict
from langgraph.graph import END, StateGraph
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.graph.message import add_messages
import functools

class ToolSubgraphState(TypedDict):
    # A message is added after each team member finishes
    messages: Annotated[List[BaseMessage], add_messages]
    team_members: List[str]
    # Used to route work. The supervisor calls a function
    # that will update this every time it makes a decision
    next: str
    navigated_sub_nodes: List[str]
    question:str
    navigated_question_and_tool:dict ## {question:tool_name}



supervisor_agent = create_graph_supervisor(
    llm,
    " You are a supervisor tasked with managing a conversation between the"
    " following tools:  get_flight_number,python_repl_tool.  Given the following user request,"
    " respond with the tool to act next. Each tool will perform a specific task and respond with their results and status. When finished, respond with FINISH.",
    excutable_tool_names,
)

flight_agent = create_agent(
    llm,
    [get_flight_number],
    "You are a research flight assistant, 根据输入的出发地(dep),目的地(des),日期(date),查询返回航班号",
)
flight_node = functools.partial(agent_node, agent=flight_agent, name="get_flight_number")

python_repl_agent = create_agent(
    llm,
    [python_repl_tool],
    "You are a Python assistant. Use this to execute Input(query:str) python commands."
)
python_repl_node = functools.partial(agent_node, agent=python_repl_agent, name="python_repl_tool")

# members = ["Flight", "PythonRepl"]
members = ["get_flight_number", "python_repl_tool"]
tool_subgraph = StateGraph(ToolSubgraphState)
tool_subgraph.add_node("get_flight_number", flight_node)
tool_subgraph.add_node("python_repl_tool", python_repl_node)

custom_supervisor_node = get_custom_supervisor_node(supervisor_agent, members, graph_name = 'tool_sub_graph')
tool_subgraph.add_node("supervisor", custom_supervisor_node)

# Define the control flow
tool_subgraph.add_edge("get_flight_number", "supervisor")
tool_subgraph.add_edge("python_repl_tool", "supervisor")
tool_subgraph.add_conditional_edges(
    "supervisor",
    lambda x: x["next"],
    {"get_flight_number": "get_flight_number", "python_repl_tool": "python_repl_tool", "FINISH": END }
)

tool_subgraph.set_entry_point("supervisor")
tool_subgraph_compiled = tool_subgraph.compile()


# The following functions interoperate between the top level graph state
# and the state of the research sub-graph
# this makes it so that the states of each graph don't get intermixed
tool_chain = functools.partial(sub_graph_enter_chain, members=members) | tool_subgraph_compiled