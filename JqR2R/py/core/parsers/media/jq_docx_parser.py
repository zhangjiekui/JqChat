# type: ignore
from io import BytesIO
from typing import AsyncGenerator

from docx import Document

from core.base.parsers.base_parser import AsyncParser
from core.base.providers import (
    CompletionProvider,
    DatabaseProvider,
    IngestionConfig,
)


class JqDOCXParser(AsyncParser[str | bytes]):
    """A parser for DOCX data."""

    def __init__(
        self,
        config: IngestionConfig,
        database_provider: DatabaseProvider,
        llm_provider: CompletionProvider,
    ):
        self.database_provider = database_provider
        self.llm_provider = llm_provider
        self.config = config
        self.Document = Document

    async def ingest(
        self, data: str | bytes, *args, **kwargs
    ) -> AsyncGenerator[str, None]:  # type: ignore
        """Ingest DOCX data and yield text from each paragraph."""
        if isinstance(data, str):
            raise ValueError("DOCX data must be in bytes format.")

        doc = self.Document(BytesIO(data))
        yield doc

        # from jqcode.jq_readers.jqkj_readers import JqkjDocxReader
        # reader = JqkjDocxReader()
        # doc_tree,df_table_list = reader.parse_docx_into_tree(doc,file_path="/data/projects/JqChatV2/JqChat/JqR2R/py/doc1.docx")
        # from jqcode.jq_agent.c0_init_env_models import env_models_instance
        # doc_tree_spiltter = env_models_instance.doc_tree_spiltter
        # from llama_index.core.schema import TextNode
        # lm_base_node = TextNode(text='',metadata={"source":"/data/projects/JqChatV2/JqChat/JqR2R/py/doc1.docx"})
        # split_results = doc_tree_spiltter._parse_node_on_tree(lm_base_node,doc_tree)


        # for paragraph in doc.paragraphs:
        #     yield paragraph.text
