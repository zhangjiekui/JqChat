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

def convert_tool_calls_list_into_dict(tool_calls_list: List[dict]) -> dict:
    next=None
    if tool_calls_list:
        tool_call_dict = tool_calls_list[0]
        tool_call_dict_args = tool_call_dict['args']
        next = tool_call_dict_args.get('next',None)
        if not next:
            next = tool_call_dict.get('type',None)
    if next:
        print(next)
    else:
        print(f"空NEXT={next}，转向FINISH")
        next = 'FINISH'        
    return {"next":next}
    

def create_team_supervisor(llm: ChatOpenAI, system_prompt, members) -> str:
    """An LLM-based router."""
    options = ["FINISH"] + members
    function_def = {
        "name": "route",
        "description": "Select the next role.",
        "parameters": {
            "title": "routeSchema",
            "type": "object",
            "properties": {
                "next": {
                    "title": "Next",
                    "anyOf": [
                        {"enum": options},
                    ],
                },
            },
            "required": ["next"],
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
        | llm.bind_tools(tools=[function_def], tool_choice="route")
        | JsonOutputToolsParser()
        | convert_tool_calls_list_into_dict
        # | llm.bind_functions(functions=[function_def], function_call="route")
        # | convert_message_into_dict
    )
