import sys
import functools
from typing import List,Union, TypedDict
# from typing import Any, Callable, List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import BaseMessage, HumanMessage,SystemMessage,ToolMessage,AIMessage

from langchain_core.runnables import Runnable,RunnablePassthrough,RunnableLambda

# create_tool_calling_agent是Langchain(v0.1.16)最新推出的统一的ToolAgent接口！
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.output_parsers.openai_tools import JsonOutputToolsParser
from langchain.agents.output_parsers.tools import ToolsAgentOutputParser

from langgraph.graph import StateGraph
from jq_agent.c0_init_env_models import get_langchain_chat_model

def create_agent(
    llm: ChatOpenAI,
    tools: list,
    system_prompt: str,
) -> str:
    """Create a function-calling agent and add it to the graph."""
    system_prompt += "\nWork autonomously according to your specialty, using the tools available to you."
    " Do not ask for clarification."
    " Your other team members (and other teams) will collaborate with you with their own specialties."
    " You are chosen for a reason! You are one of the following team members: {team_members}."
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                system_prompt,
            ),
            MessagesPlaceholder(variable_name="messages"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )
    agent = create_tool_calling_agent(llm, tools, prompt)
    executor = AgentExecutor(agent=agent, tools=tools, verbose=True, handle_parsing_errors=True,return_intermediate_steps=True)
    return executor


def agent_node(state, agent, name):
    result = agent.invoke(state)
    print(f"~~~~~~~~~~~~~~~~~~~~~~~agent tool[{name}]执行结果~~~~~~~~~~~~~~~~~~~~~~")
    print(result["output"])
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
    return {"messages": [HumanMessage(content=result["output"], name=name)]}

def create_team_supervisor(llm: ChatOpenAI, system_prompt, members) -> str:
    """An LLM-based router."""
    options = ["FINISH"] + members
    supervisor_rout_tool = {
        "type": "function",
        "function":{
        "name": "route",
        "description": "Select the next role.",
        "parameters": {
            "title": "routeSchema",
            "type": "object",
            "properties": {
                "next": {
                    "title": "Next",
                    "anyOf": [{"enum": options}]
                },
            },
            "required": ["next"],
        }
        },
    }
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="messages"),
            (
                "system",
                "Given the conversation above, who should act next?"
                " Or should we FINISH? Select one of: {options}",
            ),
        ]
    ).partial(options=str(options), team_members=", ".join(members))
    
    return (
        prompt
        | llm.bind_tools(tools=[supervisor_rout_tool], tool_choice="route")
        | JsonOutputToolsParser()
        # | supervisor_post_process
    )


def sub_graph_enter_chain(message_and_next:dict, members: List[str]):
    results = {}
    members = members + ["FINISH"]
    try:
        messages = message_and_next['messages']
        next = message_and_next['next']
        results = {
            "messages": messages,
            "next":next,
            "team_members": ", ".join(members)
        }
    except:
        print(type(messages))
        print(messages)
    return results

# 因存在import免循环依赖的问题，只好：
    # 手动调用 /home/jqsoft/AgentRagChatCI/AgentRagChatCI-0.0.1/jqcode/jq_agent/hierarchical_teams_supervisor_examples/get_all_graph_nodes.py
    # 获得all_members = ['Research team', 'Paper writing team', 'Search', 'Web Scraper', 'DocWriter', 'NoteTaker', 'ChartGenerator']
# 但可以使用延迟导入（lazy import）来避免循环依赖。可以将导入语句放在需要使用的时候再进行，而不是在模块的顶部导入。这样可以在遇到循环依赖时，绕过导入问题。
def get_last_state(state) -> dict:
    return state

def get_custom_supervisor_node(supervisor_node, members):

    supervisor_template_with_toolcalls_and_state_runnable = {
        "state": RunnablePassthrough(),
        "toolcalls":supervisor_node
    } | RunnablePassthrough()

    patial_supervisor_post_process_node =functools.partial(supervisor_post_process_node,supervisor_node=supervisor_node, members=members)
    custom_supervisor_node = get_last_state | supervisor_template_with_toolcalls_and_state_runnable | patial_supervisor_post_process_node
    return custom_supervisor_node



def supervisor_post_process_node(toolcalls_and_state:dict,supervisor_node, members) -> dict:
    next = None
    tool_call_parsed_message =  None

    if 'FINISH' not in members:
        members = members + ['FINISH']
 
    state = toolcalls_and_state["state"]
    messages = state["messages"]
    message = state["messages"][-1]
    question = message.content
    tools_response = '||'.join([m.content for m in messages[1:]])
    str_messages_with_history = f"""用户原始问题为:{question}\n中间工具返回信息为:{tools_response}\n"""
    tool_calls_list = toolcalls_and_state['toolcalls']
    print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')
    print("导航输出的原始工具列表")
    print(tool_calls_list)
    print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')
    next, tool_call_parsed_message = _parse_next(tool_calls_list,members)
    
    if next:
        return {"messages":state["messages"],'next':next}
    else:
        retry_n_times = 4
        for i in range(retry_n_times):
            _message = f'“{str_messages_with_history}” 错误信息为:{tool_call_parsed_message}'
            print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')
            print(f"导航[第{i+1}次重试]")
            print("问题及附加反馈信息：")
            print(_message)
            retry_result = supervisor_node.invoke([_message])            
            print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')
            print(f"输出的工具列表：")
            print(retry_result)
            print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')
            next, tool_call_parsed_message = _parse_next(retry_result,members)
            if next:
                return {"messages":state["messages"],'next':next}
    
    print(f"无法正常导航到下一节点，已重试{retry_n_times}次，被迫导向‘FINISH’！")
    if len(messages)>=3:
        next = "Paper writing team"
    else:
        next = "FINISH"
    return {"messages":state["messages"],'next': "FINISH"}

def _parse_next(tool_calls_list, members):
    tool_call_parsed_message = ''
    if tool_calls_list:
        tool_call_dict = tool_calls_list[0]       
        tool_call_type = tool_call_dict['type']
        tool_call_args = tool_call_dict['args']

        if 'next' in tool_call_args:
            next = tool_call_args['next']
            if tool_call_type=='route':
                if not next:                    
                        tool_call_parsed_message = f"""工具调用返回的Json格式正确，但next参数值{next}为空"""
                        print(tool_call_parsed_message)
                elif next not in members: 
                    next = None            
                    tool_call_parsed_message = f"""工具调用返回的Json格式正确，但next参数值{next}不正确，必须是以下列表取值之一[{",".join(members)}]"""
                    print(tool_call_parsed_message)
        else:
            next = tool_call_type if tool_call_type in members else None
            
    else:        
        next = None            
        tool_call_parsed_message = f"未返回有效的工具调用列表。请重试，务必返回有效的工具调用Json格式数据"
        print(tool_call_parsed_message)
    return next,tool_call_parsed_message

def get_graph_nodes(graphs:Union[StateGraph,List[StateGraph]]) -> list:
    def _get_graph_nodes(graph):
        members = list(graph.nodes.keys())
        if 'supervisor' in members:
            members.remove('supervisor')
        return members
      
    members = []
    if isinstance(graphs,list):
        for graph in graphs:
            _members = _get_graph_nodes(graph)
            members += _members
    else:
        members = _get_graph_nodes(graphs)
    return members

llm = get_langchain_chat_model(
        temperature=0.7,
        max_tokens=5000)


