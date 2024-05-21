from typing import List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import BaseMessage, HumanMessage,SystemMessage,ToolMessage,AIMessage
from langchain.output_parsers.openai_tools import JsonOutputToolsParser

# create_tool_calling_agent是Langchain(v0.1.16)最新推出的统一的ToolAgent接口！
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.output_parsers.openai_functions import JsonOutputFunctionsParser

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
    return {"messages": [HumanMessage(content=result["output"], name=name)]}

def supervisor_post_process(tool_calls_list: List[dict]) -> dict:
    next=None
    print(f"{len(tool_calls_list)=}")
    if tool_calls_list:
        tool_call_dict = tool_calls_list[0]
        called_tool_name = tool_call_dict.get('type',None)
        if called_tool_name == 'route': #调用的是supervisor_rout
            tool_call_dict_args = tool_call_dict['args']
            next = tool_call_dict_args.get('next',None)

        else: #调用的是实际的工具
            next = called_tool_name #调用的是子图中的工具
            if not next:
                next = 'FINISH' 
                print(f"【NEXT】为空，人为转向‘FINISH’")
    if not next:
        next = "DEFAULT"
        print(f"ToolCall返回的【NEXT】为空，人为设为‘DEFAULT’，可在总图和各子图中增加‘DEFAULT’的节点路由设置")

    print(f"【NEXT】转向图或图节点：{next}")
    return {"next":next}
    

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
        | supervisor_post_process
    )


def sub_graph_enter_chain(message_and_next:dict, members: List[str]):
    results = {}
    try:
        message = message_and_next['content']
        next = message_and_next['next']
        results = {
            "messages": [HumanMessage(content=message)],
            "next":next,
            "team_members": ", ".join(members)
        }
    except:
        print(type(message))
        print(message)
    return results