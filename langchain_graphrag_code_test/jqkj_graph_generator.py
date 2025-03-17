from copy import deepcopy
from typing import Callable

import networkx as nx
import pandas as pd

from langchain_graphrag_code_test.jqkj_er_extractor import EntityRelationshipExtractor
from langchain_graphrag.indexing.graph_generation import EntityRelationshipDescriptionSummarizer
from langchain_graphrag.indexing.graph_generation import GraphsMerger




class GraphGenerator:
    def __init__(
        self,
        er_extractor: EntityRelationshipExtractor,
        graphs_merger: GraphsMerger,
        er_description_summarizer: EntityRelationshipDescriptionSummarizer,
        graph_sanitizer: Callable[[nx.Graph], nx.Graph] | None = None,
    ):
        self._er_extractor = er_extractor
        self._graphs_merger = graphs_merger
        self._graph_sanitizer = graph_sanitizer
        self._er_description_summarizer = er_description_summarizer

    def run(self, text_units: pd.DataFrame) -> tuple[nx.Graph, nx.Graph]:
        er_graphs = self._er_extractor.batch(text_units, batch_size=14)
        er_merged_graph = self._graphs_merger(er_graphs)
        er_sanitized_graph = (
            self._graph_sanitizer(er_merged_graph)
            if self._graph_sanitizer
            else er_merged_graph
        )
        er_summarized_graph = self._er_description_summarizer.invoke(
            deepcopy(er_sanitized_graph)
        )
        return er_sanitized_graph, er_summarized_graph
