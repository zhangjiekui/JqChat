from datetime import date, datetime
from langchain.agents import Tool,tool,load_tools,get_all_tool_names
from langchain_experimental.tools import PythonREPLTool

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig


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
    description ="""牢记：请生成Python代码,代码内容必须是全英文字符，代码行之间必须用换行号符'\n'分割,千万不要使用';'来分割！
                You are an agent designed to write and execute python code to answer questions.
                You have access to a python REPL, which you can use to execute python code.Input should be a valid python command.
  
                If you get an error, debug your code and try again.
                Only use the output of your code to answer the question.
                You might know the answer without running any code, but you should still run the code to get the answer.
                If it does not seem like you can write code to answer the question, just return "I don't know" as the answer.
                """,
    # https://python.langchain.com/docs/integrations/tools/python
    # description="A Python shell. Use this to execute python commands. Input should be a valid python command. If you want to see the output of a value, you should print it out with `print(...)`.",
    func=python_repl_run_with_print
)

tools = [get_flight_number,python_repl_tool]
tool_names = ','.join([tool.name for tool in tools])
print(f'\n本次程序中提供的所有可用的工具列表:\n {tool_names}')

primary_assistant_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a helpful customer support assistant for Swiss Airlines. "
            " Use the provided tools to search for flights, company policies, and other information to assist the user's queries. "
            " When searching, be persistent. Expand your query bounds if the first search returns no results. "
            " If a search comes up empty, expand your search before giving up."
            "\n\nCurrent user:\n<User>\n{user_info}\n</User>"
            "\nCurrent time: {time}.",
        ),
        ("placeholder", "{messages}"),
    ]
).partial(time=datetime.now()