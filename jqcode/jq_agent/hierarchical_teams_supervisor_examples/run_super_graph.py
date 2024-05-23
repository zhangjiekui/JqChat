import sys
project_root_path = '/home/jqsoft/AgentRagChatCI/AgentRagChatCI-0.0.1'
p1 = '/home/jqsoft/AgentRagChatCI/AgentRagChatCI-0.0.1/jqcode'
p2 = '/home/jqsoft/AgentRagChatCI/AgentRagChatCI-0.0.1/jqcode/jq_agent'
for p in [project_root_path, p1, p2]:
    sys.path.append(p)

from langchain_core.messages import HumanMessage
# from jqcode.jq_agent.hierarchical_teams_supervisor_examples.super_graph import super_graph_compiled
from super_graph_builder import super_graph_compiled

question = "Write a brief research report on the North American sturgeon. Include a chart."
# question ="写一份安徽晶奇公司的研究报告，包括图表。记住，你拥有可以上网、执行python代码和绘制图表的工具能力"
# # question ="请首先搜索安徽晶奇公司的相关信息，并根据这些信息写一份安徽晶奇公司的简要介绍。"
question ="请搜索中国科学技术大学的信息，并写一份中国科学技术大学的简要介绍材料。"
for s in super_graph_compiled.stream(
    {"messages": [HumanMessage(content=question)]},
    {"recursion_limit": 150},
):
    if "__end__" not in s:
        print(s)
        print("---")