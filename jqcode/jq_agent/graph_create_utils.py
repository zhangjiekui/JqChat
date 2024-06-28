import sys
import functools
from typing import List,Union, TypedDict
# from typing import Any, Callable, List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import BaseMessage, HumanMessage,SystemMessage,ToolMessage,AIMessage
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.runnables import Runnable,RunnablePassthrough,RunnableLambda

# create_tool_calling_agent是Langchain(v0.1.16)最新推出的统一的ToolAgent接口！
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.output_parsers.openai_tools import JsonOutputToolsParser
from langchain.agents.output_parsers.tools import ToolsAgentOutputParser

from langgraph.graph import StateGraph
from jqcode.jq_agent.c0_init_env_models import get_langchain_chat_model
from jqcode.jq_agent.c0_init_env_models import filter_and_get_messages_relevant_to_query

def create_agent(
    llm: ChatOpenAI,
    tools: list,
    system_prompt: str,
) -> str:
    """Create a function-calling agent and add it to the graph."""
    system_prompt += "\nWork autonomously according to your specialty, using the tools available to you."
    " Do not ask for clarification."
    # " You are chosen for a reason! You are one of the following graph members: {graph_members}."
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
    executor = AgentExecutor(agent=agent, tools=tools, handle_parsing_errors=True)
    # executor = AgentExecutor(agent=agent, tools=tools, verbose=True, handle_parsing_errors=True,return_intermediate_steps=True)
    return executor


def agent_node(state, agent, name):
    result = agent.invoke(state)
    print(f"~~~~~~~~~~~~~~~~~~~~~~~agent tool[{name}]执行结果~~~~~~~~~~~~~~~~~~~~~~")
    print(result["output"])
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
    from jq_excutable_tool_agent_subgraph import members
    if name in members:
        return {"messages": [ToolMessage(content=result["output"], name=name,tool_call_id='-1')],"next":"FINISH"}
    return {"messages": [ToolMessage(content=result["output"], name=name,tool_call_id='-1')]}

def create_graph_supervisor(llm: ChatOpenAI, system_prompt, members) -> str:
    """An LLM-based router."""
    options = ["FINISH"] + members
    supervisor_rout_tool = {
        "type": "function",
        "function":{
        "name": "route",
        "description": "Select the next role.",
        "parameters": {
            # "title": "routeSchema",
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
    ).partial(options=str(options), graph_members=", ".join(members))
    
    return (
        prompt
        | llm.bind_tools(tools=[supervisor_rout_tool], tool_choice="route")
        # | JsonOutputToolsParser()
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
            "graph_members": ", ".join(members)
        }
    except:
        # print(type(messages))
        # print(messages)
        results = message_and_next
    return results

def get_last_state(state) -> dict:
    navigated_sub_nodes = state.get("navigated_sub_nodes",[])
    print(f"get_last_state中获取到的navigated_sub_nodes:{navigated_sub_nodes}")
    navigated_question_and_tool = state.get("navigated_question_and_tool", None) # {question:tool_name}
    print(f"get_last_state中获取到的navigated_question_and_tool:{navigated_question_and_tool}")
    messages = state.get("messages",[])
    if (messages_num:=len(messages))>1:
        print(f'原始的消息数量={messages_num}')
        original_question = state['question']
        filtered_messages = filter_and_get_messages_relevant_to_query(original_question,messages)
        # print("-----------过滤掉的消息-----------")
        # for m in messages:
        #     if m not in filtered_messages:
        #          m.pretty_print()
        # print("-----------过滤掉的消息-----------")
        # print(f'过滤后的消息数量={len(filtered_messages)}')
        state["messages"] = filtered_messages

    return state

def get_custom_supervisor_node(supervisor_node, members, graph_name):

    supervisor_template_with_toolcalls_and_state_runnable = {
        "state": RunnablePassthrough(),
        "toolcalls":supervisor_node
    } | RunnablePassthrough()

    patial_supervisor_post_process_node =functools.partial(supervisor_post_process_node,supervisor_node=supervisor_node, members=members, graph_name=graph_name)
    custom_supervisor_node = get_last_state | supervisor_template_with_toolcalls_and_state_runnable | patial_supervisor_post_process_node
    return custom_supervisor_node

def supervisor_post_process_node(toolcalls_and_state:dict,supervisor_node, members, graph_name) -> dict:
    retry_n_times = 1
    tool_call_parsed_message =  None
    if 'FINISH' not in members:
        members_with_finish = members + ['FINISH']
    state = toolcalls_and_state["state"]
    navigated_sub_nodes = state.get("navigated_sub_nodes",[])
    print(f"supervisor_post_process_node中获取到的navigated_sub_nodes:{navigated_sub_nodes}")
    navigated_question_and_tool = state.get("navigated_question_and_tool", None) # {question:tool_name}
    print(f"supervisor_post_process_node中获取到的navigated_question_and_tool:{navigated_question_and_tool}")
    if not navigated_sub_nodes:
        navigated_sub_nodes = []
    messages = state["messages"]
    message = messages[-1]
    toolcalls_message = toolcalls_and_state["toolcalls"]
    print('*****************'*5)
    print(f"Enter in {graph_name},{len(messages)=}")
    print('*****************'*2)

    question = state.get("question",None)
    if question is None:
        print('state["question"]不存在！')
        question = message.content
    if question is None:
        print('question为空！')
        raise Exception('question为空！')    
   
    is_coding_related = user_question_is_related_to_coding_or_data_analyzing(question=question)
    tool_calls_list = toolcalls_message.tool_calls


    print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')
    print(f"导航输出的原始工具列表:{tool_calls_list}")
    print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')
    next, tool_call_parsed_message = _parse_next(tool_calls_list,members_with_finish)  
    # todo: 需增加最后消息不是HumanMessage并且content真正存在才能在总图中让NEXT = "FINISH" 
    if next:
        print('*****************'*5)
        print(f"Current in {graph_name}, {graph_name} outputed next: {next}")
        print('*****************'*5)
        if graph_name=='super_graph':                
            if next=='FINISH' and len(navigated_sub_nodes)==0:
                print(f"The output next '{next}', next=='FINISH', but 'len(navigated_sub_nodes)==0',we have not answer the question"  )
                print(f"So let next='Rag'")
                next="Rag"
                print(f"Current in {graph_name}, Next to: {next}")
                navigated_sub_nodes.append(next)
                return {"messages":messages,'next':next,"question":question,"navigated_sub_nodes":navigated_sub_nodes}  
            if next in navigated_sub_nodes:
                print(f"The output next '{next}' is in navigated_sub_nodes '{navigated_sub_nodes}'")
                if isinstance(message,(ToolMessage,AIMessage)) and message.content:                    
                    print(f"The last_message is '{type(message)}'属于(ToolMessage,AIMessage)")
                    print(f"并且message.content已存在，如下: '{message.content}' ")
                    print(f"So let next='FINISH'")
                    next="FINISH"
                else:
                    print(f"但是，以下条件没有同时满足:")
                    print(f"The last_message is '{type(message)}'属于(ToolMessage,AIMessage)")
                    print(f"并且message.content已存在，如下: '{message.content}' ")
                    print(f"So let next='Rag'")
                    next="Rag"

                print(f"Current in {graph_name}, Next to: {next}")
                return {"messages":messages,'next':next,"question":question,"navigated_sub_nodes":[]}
            else:
                navigated_sub_nodes.append(next)
                print(f"Current in {graph_name}, Next to: {next}")
                return {"messages":messages,'next':next,"question":question,"navigated_sub_nodes":navigated_sub_nodes}
        elif graph_name=='tool_sub_graph':
            if is_coding_related:
                if next not in ['get_flight_number']:
                    raise Exception('该问题与Python代码、数据分析相关，此处抛出异常，好跳转到相关模块执行！')
            print(f"IN tool_sub_graph: '{question}' Next to: {next}")
            if navigated_question_and_tool:
                navigated_tool_name = navigated_question_and_tool.get(question, None)
                print(f"'{question}' already navigated_tool_name:{navigated_tool_name}")
                if next==navigated_tool_name:
                    print(f"Current in {graph_name}, Next to: {next}")
                    print(f"But question '{question}' has already handled by '{navigated_tool_name}',now should not Next to '{next}' again")
                    print(f"So let next='FINISH'")
                    next="FINISH"
                    print(f"Current in {graph_name}, Next to: {next}")
                    return {"messages":messages,'next':next,"question":question,"navigated_question_and_tool":{}}

            # 不满足上面的条件
            return {"messages":messages,'next':next,"question":question,"navigated_question_and_tool":{question:next}}
        else:
            return {"messages":messages,'next':next,"question":question,"navigated_question_and_tool":{}}

    else:
        if graph_name=='super_graph':
            print(f"Current in {graph_name}, {graph_name} outputed next: {next}")
            navigated_sub_node=set(members).intersection(set(navigated_sub_nodes))
            # print(f"navigated_sub_node:{navigated_sub_node}")
            if is_coding_related:
                print(f'该问题与Python代码、数据分析相关，但NEXT= “{next}”，所以此处抛出异常，好跳转到相关模块执行！')
                raise Exception('该问题与Python代码、数据分析相关，此处抛出异常，好跳转到相关模块执行！') 
            if navigated_sub_node:
                print(f"But navigated_sub_node:{navigated_sub_node} 已经存在")
                if isinstance(message,(ToolMessage,AIMessage)) and message.content:
                    print(f"The last_message is '{type(message)}'属于(ToolMessage,AIMessage)")
                    print(f"并且message.content已存在，如下: '{message.content}' ")
                    print(f"So let next='FINISH'")
                    next="FINISH"
                else:
                    print(f"但是，以下条件没有同时满足:")
                    print(f"The last_message is '{type(message)}'属于(ToolMessage,AIMessage)")
                    print(f"并且message.content已存在，如下: '{message.content}' ")                
                    print(f"So let next='Rag'")
                    next="Rag"
                print(f"Current in {graph_name}, Next to: {next}")
                return {"messages":messages,'next':next,"question":question,"navigated_sub_nodes":[]}
            else:
               print(f"But navigated_sub_node:{navigated_sub_node} 为空")
               print(f"So let next='Rag'")
               next="Rag"
               print(f"Current in {graph_name}, Next to: {next}")
               navigated_sub_nodes.append(next)
               return {"messages":messages,'next':next,"question":question,"navigated_sub_nodes":navigated_sub_nodes}
        else:
            print(f"Current in {graph_name}, {graph_name} outputed next: {next} is None")
            print(f"But we are already in {graph_name}")                
            print(f"So let next='FINISH'")
            next="FINISH"
            return {"messages":messages,'next':next,"question":question}    

        print(f"Current in {graph_name}, {graph_name} outputed next: {next} is None, and Not in 'super_graph', we have to retry......")
        if question == message.content:
            tools_response_messages = messages[1:]
        else:
            tools_response_messages = messages
        str_messages_with_history = f"""用户原始问题为:{question}"""
        if tools_response_messages:
            if isinstance(tools_response_messages,list):
                tools_response = '||'.join([m.content for m in tools_response_messages])   
            else:
                tools_response = tools_response_messages
            tools_response = tools_response.replace(question,'') # 移除原始问题    

            str_messages_with_history += f"""\n中间工具返回信息为:{tools_response}"""
        
        for i in range(retry_n_times):
            _message = f'{str_messages_with_history} \n错误信息为:{tool_call_parsed_message}'
            print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')
            print(f"导航[第{i+1}次重试]的问题及附加反馈信息为：")
            print(_message)
            retry_result = supervisor_node.invoke({"messages":[HumanMessage(content=_message)],"team_members":members_with_finish}) .tool_calls
            # retry_result = supervisor_node.invoke([_message]) .tool_calls           
            print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')
            print(f"输出的工具列表：")
            print(retry_result)
            print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')
            next, tool_call_parsed_message = _parse_next(retry_result,members_with_finish)
            if next:
                print('*****************')
                print(f"Current in {graph_name}, Next to {next}")
                print('*****************'*5)                
                return {"messages":messages,'next':next,"question":question}
    
    print(f"无法正常导航到下一节点，已重试{retry_n_times}次！启用自定义规则")


    if graph_name=='super_graph':
        ms_num = len(messages)
        last_message = messages[-1]
        if ms_num<3 or isinstance(last_message,HumanMessage):
            next = "Rag"
        else:
            next = "FINISH"
    else:
        next = "FINISH"
    print('*****************')
    print(f"Current in {graph_name}, Next to {next}")
    print('*****************'*5)
    return {"messages":messages,'next': next,"question":question}

def _parse_next(tool_calls_list, members):
    tool_call_parsed_message = ''
    next = None
    _next = None
    tool_call_name = None

    if tool_calls_list:
        tool_call_dict = tool_calls_list[0]       
        tool_call_name = tool_call_dict['name']
        tool_call_args = tool_call_dict['args']

        if 'next' in tool_call_args:
            next = tool_call_args['next']
            _next = tool_call_args['next']
            if next in members:
                return next,tool_call_parsed_message
            else:
                if tool_call_name=='route':
                    if not next:                    
                            tool_call_parsed_message = f"""工具调用返回的Json格式正确，但next参数值{next}为空"""
                            print(tool_call_parsed_message)
                    else:
                        next = None            
                        tool_call_parsed_message = f"""工具调用返回的Json格式正确，但next参数值{next}不正确，必须是以下列表取值之一[{",".join(members)}]"""
                        print(tool_call_parsed_message)

        next = tool_call_name if tool_call_name else None
        if next in members:
            return next,tool_call_parsed_message
        else:
            next = None
            tool_call_parsed_message = f"""工具调用返回的Json格式正确，但返回的工具名称(name)不对，必须是以下列表取值之一[{",".join(members)}]"""

        print(f'供调试观察的信息：Next={_next},tool_call_name={tool_call_name}')    
    else:        
        next = None            
        tool_call_parsed_message = f"未返回有效的工具调用列表。请重试，务必返回一个有效的工具（Tool）/函数（Function）调用"
        # print(tool_call_parsed_message)
        
    return next,tool_call_parsed_message
"""
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
"""


llm = get_langchain_chat_model(
        temperature=0.0,
        max_tokens=10000,
        streaming=True)


### Coding Grader
# Coding Grader Data model
class GradeCodingRelavance(BaseModel):
    """Binary classification for a user question is relevant to code generating/executing,data file processing or data exploring/analyzing."""
    k: str = Field(description="Whether a user question is relevant to [code generating/executing,data file processing and data exploring/analyzing], k must be 'yes' or 'no'")
# Code Generating/Code Executing Relavance Grader Prompt
preamble_coding_relevant_grader = """You are a grader assessing relevance of a user question to [code generating/executing,data file processing or data exploring/analyzing]. Response me with a simple JSON string can be directly consumed by  ‘json.loads’ method, must be ‘{{"k":"yes"}}’ or  ‘{{"k":"no"}}’,'yes' means a user question is related to code generating/executing,data file processing or data exploring/analyzing.No preamble or explaination."""
structured_llm_coding_relevant_grader = llm.with_structured_output(GradeCodingRelavance,method='json_mode')
coding_relevance_prompt = ChatPromptTemplate.from_messages(
    [
        ("system",preamble_coding_relevant_grader),
        ("human", "User question: {question}")
    ]
)
# Coding Relavance Grader
coding_relevance_grader = coding_relevance_prompt | structured_llm_coding_relevant_grader

def user_question_is_related_to_coding_or_data_analyzing(question:str):
    response =  coding_relevance_grader.invoke({"question": question})
    print(f"判断：Whether question '{question}' is related to [Codeing/Data File/Analyzing]? 判断结果：{response=}")
    try:
        result_str = response.k
        if result_str.lower() == 'yes':
            return True
        else:
            return False
    except:
        print('“coding_relevance_grader”无法正常返回判断结果，所以人为返回False')
        return False

if __name__ == "__main__":
    qustion = "请使用Python生成代码，计算1到100的和，并返回计算结果"
    result = user_question_is_related_to_coding_or_data_analyzing(qustion)
    print(result)