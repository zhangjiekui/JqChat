# https://ai.plainenglish.io/crewai-integrating-3rd-party-tools-from-langchain-and-even-those-that-not-officially-supported-9a6b41e477db

from langchain.agents import Tool
from langchain.agents.agent_types import AgentType
from langchain_experimental.agents.agent_toolkits import create_pandas_dataframe_agent
from langchain_openai import ChatOpenAI
import pandas as pd
from crewai import Agent,Task,Crew
from crewai_tools import CodeInterpreterTool

llm=ChatOpenAI(temperature=0, model='openai/qwen25b70',base_url='http://10.1.150.105:9997/v1',api_key='abc123')

# Creating Agents
coding_agent  = Agent(
    role="Programmer",
    goal="Write and execute code and share the output::{query}",
    backstory="""You are an experienced programmer with strong Python skills.""",
	verbose=True,
    llm=llm,
    allow_code_execution=True,
    code_execution_mode='safe',
)

code_task = Task(
    description="""\
    1. Understand the user request on the requirements: {query}.并尽量使用中文回答用户的问题。
    2. Write the code to meet the requirements. Proceed to next step only if the code is correct.
    3. Run the code and share the output.
    4. Stop iterating once the output is correct.""",

    expected_output="""\
    1. The output of the code execution.
    2. The code used to generate the output.
    3. The Explanation of the code and the output, for non-technical users.
    4. the output file or image full path if existed.
    5. End of the conversation""",
    agent=coding_agent
)

# Create a crew and add the task
analysis_crew = Crew(
    agents=[coding_agent],
    tasks=[code_task]
)

# Execute the crew
# result = analysis_crew.kickoff(inputs={"query": "请计算1到100的和,并使用中文回答"})
result = analysis_crew.kickoff(inputs={"query": "请绘制sin(x)曲线,并保存绘制的图形/图像为my_png"})

print(result)

# df = pd.read_csv("/data/projects/JqChatV2/JqChat/titanic.csv")

# pandas_tool_agent = create_pandas_dataframe_agent(
#     llm=llm,
#     df=df, 
#     agent_type=AgentType.OPENAI_FUNCTIONS,
#     allow_dangerous_code=True # <-- This is an "acknowledgement" that this can run potentially dangerous code
# )

# # Create the tool
# pandas_tool = Tool(
#     name="Manipulate and Analyze tabular data with Code",
#     func=pandas_tool_agent.invoke, # <-- This is the function that will be called when the tool is run. Note that there is no `()` at the end
#     description="Useful for search-based queries",
# )

# # Creating Agents
# agent_data_analyst = Agent(
#     role="Content Planner",
#     goal="Analyze the data based on user query: {topic}",
#     backstory="""You're the best data analyst.""",
#     allow_delegation=False,
# 	verbose=True,
#     tools=[pandas_tool],
#     llm=llm,
#     allow_code_execution=True,
#     code_execution_mode='safe',
# )

# task_analyze = Task(
#     description="""\
#     1. Understand the user query: {topic}.
#     2. Use the tool to analyze the data based on the user query.
#     3. Develop a comprehensive report based on the analysis.""",

#     expected_output="""\
#     A comprehensive analysis report that present the results using McKinsey's Pyramid Principle.""",

#     agent=agent_data_analyst,
# )

# # Creating the Crew
# crew = Crew(
#     agents=[agent_data_analyst],
#     tasks=[task_analyze],
#     verbose=True
# )

# # Running the Crew
# result = crew.kickoff(inputs={"topic": "What is the average age of passengers in the Titanic dataset?"})
# print(result)