from datetime import date, datetime
from langchain.agents import Tool,tool,load_tools,get_all_tool_names
from langchain_experimental.tools import PythonREPLTool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig, RunnableLambda
from langchain_core.messages import SystemMessage
from langchain_core.messages import ToolMessage
from langgraph.prebuilt import ToolNode

from jqcode.jq_agent.c0_init_env_models import get_langchain_chat_model


# 自定义工具函数
@tool
def get_flight_number(dep:str,des:str,date:date) -> str:
    """根据输入的出发地(dep),目的地(des),日期(date),返回航班号。重要:当前日期是{current_date}，日期(date)只接受python datetime.date类型输入。如果日期是不确定的描述，如明天、后天等，可以先使用工具'python_repl_tool'进行计算，并且返回python datetime.date类型结果，具体格式示例如下：2024-04-03。"""
    return f"晶奇航空666[{date}]"
current_date = str(datetime.now().date())
get_flight_number.description= get_flight_number.description.replace("{current_date}",current_date)

# 使用python_repl并包装成Agent工具 【代码执行层面】
print('---------------------------------------------------------')
python_repl = PythonREPLTool()
print(python_repl.run("print('---------------------------------------------------------')")) #先运行一遍，后面似乎就不再会输出警告信息: Python REPL can execute arbitrary code. Use with caution.
def python_repl_run_with_print(query:str,python_repl=python_repl) -> str:
    print('...调用执行Python_REPL......结果如下：')
    return python_repl.run(query)

python_repl_tool = Tool(
    name="python_repl_tool",
    # from https://python.langchain.com/docs/integrations/toolkits/python
    description ="""牢记：请生成Python代码,代码内容必须是全英文字符，代码行之间必须用换行号符'\\n'分割,千万不要使用';'来分割！You are an agent designed to write and execute python code to answer questions.You have access to a python REPL, which you can use to execute python code.Input should be a valid python command.If you get an error, debug your code and try again.Only use the output of your code to answer the question. You might know the answer without running any code, but you should still run the code to get the answer. If it does not seem like you can write code to answer the question, just return "I don't know" as the answer.""",
    # https://python.langchain.com/docs/integrations/tools/python
    # description="A Python shell. Use this to execute python commands. Input should be a valid python command. If you want to see the output of a value, you should print it out with `print(...)`.",
    func=python_repl_run_with_print
)

excutable_tools = [get_flight_number,python_repl_tool]
excutable_tool_names = [tool.name for tool in excutable_tools]

excutable_tools_descriptions_str = '\n\n'.join([f"[ToolName]:{t.name}; [ToolDescription]:{t.description}" for t in excutable_tools])
excutable_tool_names_str = ','.join([tool.name for tool in excutable_tools])

print(excutable_tools_descriptions_str)
print(f'\n本次程序中提供的所有可用的工具列表:\n {excutable_tool_names_str}')
print("=================== system_prompt ===================")
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
            )
            for tc in tool_calls
        ]
    }


def create_tool_node_with_fallback(tools: list) -> dict:
    return ToolNode(tools).with_fallbacks(
        [RunnableLambda(handle_tool_error)], exception_key="error"
    )

excutable_tool_node = create_tool_node_with_fallback(excutable_tools)


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