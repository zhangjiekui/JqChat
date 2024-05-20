from langchain_core.messages import HumanMessage
from jqcode.jq_agent.hierarchical_teams_supervisor_examples.super_graph import super_graph

question = "Write a brief research report on the North American sturgeon. Include a chart."
for s in super_graph.stream(
    {"messages": [HumanMessage(content="写一份微软公司的研究报告，包括图表")]},
    {"recursion_limit": 150},
):
    if "__end__" not in s:
        print(s)
        print("---")