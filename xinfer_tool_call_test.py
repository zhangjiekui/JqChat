from langchain_core.prompts import PromptTemplate
from langchain_core.messages import AnyMessage, SystemMessage, HumanMessage, ToolMessage,AIMessage
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
from langchain_openai import ChatOpenAI
import logging
import json_repair
logger = logging.getLogger(__name__)


print('===工具函数定义==='*3)
# 自定义工具函数1
@tool(parse_docstring=True)
def get_flight_number(origin:Optional[str],destination:Optional[str],date:Optional[str]) -> str:
    """
    根据输入的出发地(origin),目的地(destination),日期(date),返回航班号。重要:当前日期是{current_date}，日期(date)只接受python datetime.date类型输入。如果日期是不确定的描述，如明天、后天等，请先使用工具'python_repl_tool'进行计算，并且返回python datetime.date类型结果，具体格式示例如下：2024-04-03。
    
    Args:
        origin:(str), 出发地/城市，例如合肥
        destination:(str), 目的地/城市，例如北京
        date:(date) 飞行日期， 例如2024-08-03.如果日期是不确定的描述，如明天、后天等，请先调用工具'python_repl_tool'或者'CODE_GENERATION'进行计算，并且返回python datetime.date类型结果
    """
    result = f"晶奇网络科技航空测试航班号：{origin}=>{destination} JQ6666-{date}"
    print(f"-----'get_flight_number'执行结果: {result}")
    return result

current_date = str(datetime.now().date())
try:
    get_flight_number.description= get_flight_number.description.replace("{current_date}",current_date)
except:
    get_flight_number.__doc__= get_flight_number.__doc__.replace("{current_date}",current_date)
args_schema = get_flight_number.args_schema.schema()
print(f"get_flight_number:{args_schema=}")

# 自定义工具函数2
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
                    print(f"-----'python_repl_tool'执行结果:{result}")           
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
            print(f"-----'python_repl_tool'执行结果:{result}")            
            return result
        else:
            raise ToolException(f"No observation was found. Maybe you should add `print($value)` in you python code?")
args_schema = python_repl_tool.args_schema.schema()
print(f"python_repl_tool:{args_schema=}")

print('===工具校验完成==='*3)


def get_langchain_chat_model(llm_model_name="qwen2-instruct",llm_model_base_url="http://localhost:9997/v1",api_key="your_key",temperature=0.01, max_tokens=None, streaming=False):
    chat_model = ChatOpenAI(
            model_name=llm_model_name,
            openai_api_base=llm_model_base_url,    
            openai_api_key= api_key,
            streaming=streaming,
            verbose=True,
            temperature=temperature,
            max_tokens=max_tokens,           
        )
    logger.info(f'当前使用的LLM模型为:Langchain ChatOpenAI, {chat_model.model_name}, API_URL为{chat_model.openai_api_base}')
    return chat_model

def call_llm(messages,chat_model_with_tools,tool_names,executable_tools_dict):
    try:
        result = chat_model_with_tools.invoke(messages)
    except Exception as e:
        messages.append(AIMessage("大语言模型执行失败"),f'！！！大语言模型执行失败，！！！错误消息为:{e}')
        raise e
    
    tool_calls = result.tool_calls
    returned_tool_calling_nums = len(tool_calls)
    if returned_tool_calling_nums>0:
        for tool_call in tool_calls:
            tool_call_result = executable_tools_dict[tool_call["name"]].invoke(tool_call["args"])
            tool_message = ToolMessage(content=tool_call_result,tool_call_id=tool_call["id"],name=tool_call["name"])
            messages.append(tool_message)
            # return messages,None
    else:
        try:                
            tool_calls_json_list = json_repair.loads(result.content)
            if isinstance(tool_calls_json_list,dict):
                tool_calls_json_list = [tool_calls_json_list]
            if len(tool_calls_json_list)>0:
                for tool_call in tool_calls_json_list:
                    tool_name = tool_call['name']
                    if tool_name in tool_names:
                        parameters = tool_call['arguments']
                        if not isinstance(parameters,dict):
                            parameters = json_repair.loads(parameters)
                        if isinstance(parameters,dict):
                            tool_call_result = executable_tools_dict[tool_name].invoke(parameters)
                            tool_message = ToolMessage(content=tool_call_result,tool_call_id=result.id,name=tool_name)
                            messages.append(tool_message)
            else:
                messages.append(result)
        except Exception as e:
            logger.debug(f"解析函数调用过程中出现错误:{e}")
            messages.append(result)
            
    return messages
        


def run_conversation(user_question,chat_model_with_tools,system_message,tool_names,executable_tools_dict):    
    messages = [("system", system_message),("human", user_question)]
    messages = [SystemMessage(system_message),HumanMessage(user_question)]
    while not isinstance(messages[-1],AIMessage):
        try:
            messages= call_llm(messages,chat_model_with_tools,tool_names,executable_tools_dict)
        except Exception as e:
            logger.error(e)
    return messages[-1].content

if __name__ == "__main__":
    chat_model = get_langchain_chat_model()
    executable_tools = [get_flight_number,python_repl_tool]
    chat_model_with_tools = chat_model.bind_tools(executable_tools)
    
    executable_tools_dict = {t.name: t for t in executable_tools}
    tool_names = [tool.name for tool in executable_tools]
    tool_names_str = ','.join(tool_names)
    system_message = f"Solve/Answer user's questions as best as you can in the language the user asked, preferred/default to Simplified Chinese. You have access to the following tools:{tool_names_str}.You are allowed to make multiple calls (either together or in sequence)."
       
    
    
    
    user_questions = [
        '请查询明天从合肥到上海的航班',
        '请查询明天从合肥到上海的航班,以及南昌到北京的航班',
        '请使用python_repl_tool来计算1到100的和',
        '请调用python_repl_tool工具，一个计算1到100的和,另一个计算10的阶乘，并实际执行工具获取计算结果',
    ]

    for user_question in user_questions:
        print('======'*5)
        print('======'*5)
        print(user_question)
        result = run_conversation(user_question,chat_model_with_tools,system_message,tool_names=tool_names,executable_tools_dict=executable_tools_dict)

        print(result)
    
    
