from langchain.docstore.document import Document
from langchain_community.graphs import Neo4jGraph
import logging
import os
import re

logging.basicConfig(format="%(asctime)s - %(message)s", level="INFO")


class CreateChunksofDocument:
    def __init__(self, chunk_docs: list[Document], graph: Neo4jGraph):
        self.chunk_docs = chunk_docs
        self.graph = graph

    def split_file_into_chunks(self):
        # 仅仅返回传递进来的已经划分好的Document(page_content=chunk_text,meta_data={})
        return self.chunk_docs
    
