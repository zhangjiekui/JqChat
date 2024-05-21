from langchain_core.messages import HumanMessage
from jqcode.jq_agent.hierarchical_teams_supervisor_examples.super_graph import super_graph_compiled

question = "Write a brief research report on the North American sturgeon. Include a chart."
question ="写一份安徽晶奇公司的研究报告，包括图表。记住，你拥有可以上网、执行python代码和绘制图表的工具能力"
question ="请首先搜索安徽晶奇公司的相关信息，并根据这些信息写一份安徽晶奇公司的简要介绍。"
question ="请写一份安徽晶奇公司张结魁的简要介绍。"
for s in super_graph_compiled.stream(
    {"messages": [HumanMessage(content=question)]},
    {"recursion_limit": 150},
):
    if "__end__" not in s:
        print(s)
        print("---")