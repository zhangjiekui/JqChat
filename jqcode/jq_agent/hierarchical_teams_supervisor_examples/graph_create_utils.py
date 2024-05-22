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
    executor = AgentExecutor(agent=agent, tools=tools)
    return executor


def agent_node(state, agent, name):
    result = agent.invoke(state)
    print(f"~~~~~~~~~~~~~~~~~~~~~~~~~~~~~agent[{name}]执行结果~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
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

def get_custom_supervisor_node(supervisor_node):

    supervisor_template_with_toolcalls_and_state_runnable = {
        "state": RunnablePassthrough(),
        "toolcalls":supervisor_node
    } | RunnablePassthrough()

    patial_supervisor_post_process_node =functools.partial(supervisor_post_process_node,supervisor_node=supervisor_node)
    custom_supervisor_node = get_last_state | supervisor_template_with_toolcalls_and_state_runnable | patial_supervisor_post_process_node
    return custom_supervisor_node



def supervisor_post_process_node(toolcalls_and_state:dict,supervisor_node) -> dict:
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

def _supervisor_post_process(tool_calls_list: List[dict]) -> dict:
    try:
        from jqcode.jq_agent.hierarchical_teams_supervisor_examples.get_all_graph_nodes import all_members, graphs,super_graph_compiled
    except:
        all_members = ['Research team', 'Paper writing team', 'Search', 'Web Scraper', 'DocWriter', 'NoteTaker', 'ChartGenerator']

    all_members = ['FINISH',"SELF"] + all_members
    next=None
    response_message = 'SUCCESS'
    print(f"{len(tool_calls_list)=}")
    if tool_calls_list:
        tool_call_dict = tool_calls_list[0]
        tool_call_dict_args = tool_call_dict['args']
        next = tool_call_dict_args.get('next',None)        
        if next not in all_members: # 优先获取的next值不正确
            # called_tool_name = tool_call_dict.get('type',None)
            # print(f"ToolCalls返回的【NEXT】值{next}不正确，尝试工具名{called_tool_name}")            
            # next = called_tool_name # 尝试工具名
            if next:
                response_message = f'工具调用返回形式正确，但请返回正确的“next”值,现在的“next={next}”不在工具列表中'
            else:
                response_message = '工具调用返回形式正确，但请返回正确的“next”值,现在的“next”为空'
            next = "SELF"
    else:
        next = "SELF"
        response_message = f"必须返回一个Json形式的工具调用!"
    print(f"【NEXT】转向图或图节点：{next}")
    return {"response_message":response_message, "next":next}
        

    # if tool_calls_list:
    #     if not next:
    #         print(f"ToolCalls返回形式正确：\n{tool_call_dict}\n")
    #         print(f"但未能从ToolCall获取到的【NEXT】值")
    #         pass

    # if not next:
    #     next = "SELF"
    #     print(f"ToolCalls返回的【NEXT】为空，人为设为‘DEFAULT’，可在总图和各子图中增加‘DEFAULT’的节点路由设置")

    
    # if next not in all_members:
    #     print(f"【NEXT】因返回的{next}不在图节点{all_members}中，人为设为‘DEFAULT’")
    #     next = "SELF"
    # return {"added_content":added_content, "next":next}

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


