from datetime import date, datetime
from langchain.agents import Tool,tool
from typing import Optional
from langchain_community.agent_toolkits.load_tools import load_tools,get_all_tool_names
from langchain_experimental.tools import PythonREPLTool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig, RunnableLambda
from langchain_core.messages import SystemMessage
from langchain_core.messages import ToolMessage
from langgraph.prebuilt import ToolNode
from langchain_core.tools import ToolException
from typing import List
from jqcode.jq_utils.logger import jqkj_logger
import requests
import json
logger = jqkj_logger(__file__).get_logger()
# from jqcode.jq_agent.c0_init_env_models import env_models_instance


# 自定义工具函数

@tool(parse_docstring=True)
def get_elderly_organization_list(location:str="安徽晶奇网络科技股份有限公司",radius:int=10,num:int=10) -> str:
    """
    根据用户的当前地址位置(location),附近距离(radius),查询返回指定数量(num)的养老机构列表信息。

    Args:
        location:(str), 用户当前地址位置
        radius:(int), 距离用户当前地址位置的距离（附近多少公里范围内）
        num:int,返回的养老机构个数

    """
    url = f"http://192.168.44.140:9000/pub_external/orgList?page_num=1&page_size={num}&address={location}&distance={radius}"
    print(url)
    headers = {"referer":"http://192.168.44.140:9000"}

    try:
        result_str = "接口调用成功，但未找到符合条件的养老机构。"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            output = response.json()
            data = output.get("data",[])
            if data:
                num = data.get('total',0)
                organizations = data.get('list',[])                     
                organization_names = [d.get('org_name','') for d in organizations]
                organization_names = [o for o in organization_names if o]
                if organization_names:
                    out_str = f"共找到{len(organization_names)}家养老机构："
                    organization_names_str = ','.join(organization_names)
                    result_str = f"{out_str}{organization_names_str}"              
            return result_str
        
        else:
            raise Exception(response.text)
    except Exception as e:
        msg = f'无法获取到养老机构列表信息:{e}'
        logger.error(msg)
        return msg
## 注释掉# @tool(parse_docstring=True) 后，可运行函数测试
# r = get_elderly_organization_list(num="10",user_location="安徽晶奇网络科技股份有限公司",distance=3)
# print(r)


@tool(parse_docstring=True)
def get_flight_number(origin:Optional[str],destination:Optional[str],date:Optional[str]) -> str:
    """
    根据输入的出发地(origin),目的地(destination),日期(date),返回航班号。重要:当前日期是{current_date}，日期(date)只接受python datetime.date类型输入。如果日期是不确定的描述，如明天、后天等，请先使用工具'python_repl_tool'进行计算，并且返回python datetime.date类型结果，具体格式示例如下：2024-04-03。
    
    Args:
        origin:(str), 出发地/城市，例如合肥
        destination:(str), 目的地/城市，例如北京
        date:(date) 飞行日期， 例如2024-08-03.如果日期是不确定的描述，如明天、后天等，请先调用工具'python_repl_tool'或者'CODE_GENERATION'进行计算，并且返回python datetime.date类型结果
    """
    result = f"晶奇航空测试航班号{origin}=>{destination} JQ6666-{date}"
    logger.info(f"'get_flight_number'执行结果: {result}")
    return result

current_date = str(datetime.now().date())
try:
    get_flight_number.description= get_flight_number.description.replace("{current_date}",current_date)
except:
    get_flight_number.__doc__= get_flight_number.__doc__.replace("{current_date}",current_date)
# args_schema = get_flight_number.args_schema.schema()
# print(f"get_flight_number:{args_schema=}")

# 使用python_repl并包装成Agent工具 【代码执行层面】
# print('---------------------------------------------------------')
# python_repl = PythonREPLTool()
# print(python_repl.run("print('---------------------------------------------------------')")) #先运行一遍，后面似乎就不再会输出警告信息: Python REPL can execute arbitrary code. Use with caution.

@tool(parse_docstring=True)
def python_repl_tool(query:Optional[str]) -> str: 
    """
    A Python shell. Use this to execute Input(query:str) python commands, but only suitable for simple question. 
    Waring: 'CODE_GENERATION' tool is much powerful, please use 'CODE_GENERATION' tool for drawing images, plotting graphs/charts, data file processing/analyzing/saving.
        Input: query:str. Python code. You must use '\n' to seperate each code line    
        Output: you MUST using `print($code or value$)` to print out at least one value (mostly in the last line), or multiple values as needed to better answer/solve the user's problem.For examples:
        # print out at least one value: MUST.
            import datetime
            print(datetime.datetime.today() + datetime.timedelta(days=2))
        # print out multiple values: AS NEEDED. 
            print(1+1)
            print(298*3)
            print(8-1)
    \n\nArgs:
        query:Optional[str],  Python code 
    """

    python_repl = PythonREPLTool()
    logger.debug('...调用执行Python_REPL...过程如下：')
    
    def _revise_query(query:str) -> str:
        logger.debug('......检查是否有print......：')
        query = query.replace('\\n',"\n")
        query = query.replace(';',"\n")
        lines = query.split("\n")
        for line in lines[::-1]:
            if len(line.strip())>0:
                if not line.startswith('#'): #直接跳过注释行
                    if line.startswith('print'):
                        logger.debug(f"===已经有print了，直接返回原query:\n{query}")
                        return query #已经有print了，就直接返回原query
                    else:
                        last_line_splits = line.split("#")
                        last_line = last_line_splits[0].strip()
                        last_line = f'print({last_line})'
                        lines[lines.index(line)] = last_line
                        _query = "\n".join(lines)

                        print(f"===revised_query:\n{_query}")
                        print(f"===end of revised_query")
                        return _query
    try:
        if not query:
            raise ToolException(f"query (python code) is empty")
        else:
            logger.debug(f"===尝试直接执行生成的Python程序语句:\n{query}")  
            result = python_repl.run(query) 
            if result:
                if not "error" in result.lower() and not "exception" in result.lower():
                    logger.debug(f"尝试直接执行生成的Python程序语句成功")
                    logger.debug(f"'python_repl_tool'执行结果:{result}")           
                    return result
                else:
                    logger.debug(f'直接执行生成的Python程序语句出现错误！{result}')
                    raise Exception(result)
            else:
                logger.debug(f'直接执行生成的Python程序语句执行结果为空，可能是最后一行没有使用print打印出执行结果！')
                raise Exception('直接执行生成的Python程序语句执行结果为空，可能是最后一行没有使用print打印出执行结果！')
    except Exception as e:
        logger.debug(f'直接执行生成的Python程序语句出现错误，错误信息为:{e}') 
        logger.debug(f'===尝试修改Python程序语句，并重新执行')
        revised_query = _revise_query(query)
        try:
            result = python_repl.run(revised_query)
        except Exception as e:        
            raise ToolException(f"The `python_repl_tool` failed.The python code was: \n{revised_query}. \nthe exception was: {e}")
        # result = python_repl.run(query) # 用做ToolException测试，不使用revised_query
        if result:
            logger.debug(f"'python_repl_tool'执行结果:{result}")            
            return result
        else:
            raise ToolException(f"No observation was found. Maybe you should add `print($value)` in you python code?")
# args_schema = python_repl_tool.args_schema.schema()
# print(f"python_repl_tool:{args_schema=}")

# print("\n###增加了ToolException处理函数_handle_error function")
def _handle_error(error: ToolException) -> str:
    return (
        "The following errors occurred during tool execution:"
        + error.args[0]
        + "Please regerate the input args for the current tool, or try another tool."
    )

def _bind_handle_error(tools: List[Tool]) -> None:
    for tool in tools:
        tool.handle_tool_error = _handle_error

def _print_event(event: dict, _printed: set, max_length=1500):
    current_state = event.get("dialog_state")
    if current_state:
        print(f"Currently in: ", current_state[-1])
    message = event.get("messages")
    if message:
        if isinstance(message, list):
            message = message[-1]
        if message.id not in _printed:
            msg_repr = message.pretty_repr(html=True)
            if len(msg_repr) > max_length:
                msg_repr = msg_repr[:max_length] + " ... (truncated)"
            print(msg_repr)
            _printed.add(message.id)

excutable_tools = [get_flight_number,python_repl_tool]
_bind_handle_error(excutable_tools)
excutable_tool_names = [tool.name for tool in excutable_tools]

excutable_tools_descriptions_str = '\n\n'.join([f"[ToolName]:{t.name}; [ToolDescription]:{t.description}" for t in excutable_tools])
excutable_tool_names_str = ','.join([tool.name for tool in excutable_tools])



# print(excutable_tools_descriptions_str)
# print(f'\n本次程序中提供的所有可用的工具列表:\n {excutable_tool_names_str}')
# print("=================== system_prompt ===================")
system_prompt = f"""You are a helpful tool assistant. You have access to the following tools: 
            \n\n{excutable_tools_descriptions_str}\n\nUse a json blob to specify a tool by providing an action key (tool name) and an action_input key (tool input). Use the provided tools if necessary to get flight number, write and execute python code to answer questions.Valid "action" values: "Final Answer" or {excutable_tool_names_str}\n\nProvide only ONE action per $JSON_BLOB, as shown:```\n{{\n  "action": $TOOL_NAME,\n  "action_input": $INPUT\n}}\n```\n\nFollow this format:\n\nQuestion: input question to answer\nThought: consider previous and subsequent steps\nAction:\n```\n$JSON_BLOB\n```\nObservation: action result\n... (repeat Thought/Action/Observation N times)\nThought: I know what to respond\nAction: "\n```\n{{\n"  "action": "Final Answer",\n  "action_input": "Final response to human"\n}}\n\nBegin! Reminder to ALWAYS respond with a valid json blob of a single action. Respond directly if appropriate. Format is Action:```$JSON_BLOB```then Observation
            """
# print(system_prompt)
primary_tool_assistant_prompt = ChatPromptTemplate.from_messages([SystemMessage(system_prompt),("human", "{question}")])
# primary_tool_assistant_prompt.pretty_print()


def handle_tool_error(state) -> dict:
    error = state.get("error")
    tool_calls = state["messages"][-1].tool_calls
    return {
        "messages": [
            ToolMessage(
                content=f"Error: {repr(error)}\n please fix your mistakes.",
                tool_call_id=tc["id"],
                name = tc["name"],
            )
            for tc in tool_calls
        ]
    }


def create_tool_node_with_fallback(tools: list) -> dict:
    return ToolNode(tools).with_fallbacks(
        [RunnableLambda(handle_tool_error)], exception_key="error"
    )

excutable_tool_node = create_tool_node_with_fallback(excutable_tools)


