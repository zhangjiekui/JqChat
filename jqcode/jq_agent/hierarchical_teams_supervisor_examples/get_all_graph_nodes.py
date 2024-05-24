from typing import List,Union
from langgraph.graph import StateGraph
from super_graph_builder import super_graph
from sub_graphs.research_sub_graph import research_graph
from sub_graphs.writing_sub_graph import writing_graph
from graph_create_utils import get_graph_nodes

graphs = [super_graph, research_graph, writing_graph]
all_members = get_graph_nodes(graphs)
print(all_members)