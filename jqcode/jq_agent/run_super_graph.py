import sys
project_root_path = '/data/projects/JqChat'
p1 = '/data/projects/JqChat/jqcode'
p2 = '/data/projects/JqChat/jqcode/jq_agent'
for p in [project_root_path, p1, p2]:
    sys.path.append(p)

from langchain_core.messages import HumanMessage
# from jqcode.jq_agent.hierarchical_teams_supervisor_examples.super_graph import super_graph_compiled
from super_graph_builder import super_graph_compiled

question = "Write a brief research report on the North American sturgeon. Include a chart."
# question ="写一份安徽晶奇公司的研究报告，包括图表。记住，你拥有可以上网、执行python代码和绘制图表的工具能力"
# # question ="请首先搜索安徽晶奇公司的相关信息，并根据这些信息写一份安徽晶奇公司的简要介绍。"
question ="请搜索中国科学技术大学的信息，并写一份中国科学技术大学的简要介绍材料。"
question ="请查询明天从合肥到上海的航班。"
question ="请使用python工具计算1到100的和。"
question ="合肥八中有多少个校区？"


for s in super_graph_compiled.stream(
    {"messages": [HumanMessage(content=question)],"question":question},
    {"recursion_limit": 150},
    debug = False
):
    if "__end__" not in s:
        # print(s)
        print("---")