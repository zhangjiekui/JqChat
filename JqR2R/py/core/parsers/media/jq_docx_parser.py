# type: ignore
from io import BytesIO
from typing import AsyncGenerator

from docx import Document
from llama_index.core.schema import TextNode
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
            raise ValueError("DOCX/PDF etc. file data must be in bytes format.")
        document = kwargs.get("document",None)
        document_type = ''
        filename = ''
        if document:
            document_type = document.document_type.value
            filename = document.metadata.get("title",'')
            if filename:
                if not filename.endswith(document_type):
                    filename = filename + '.' + document_type
                
        from core.providers.ingestion.jq.base import file_type_processed_by_jqreader,DEFAULT_PARSERS_BACKED
        if document_type != 'docx' and document_type in file_type_processed_by_jqreader:
            default_parser_class = DEFAULT_PARSERS_BACKED.get(document_type,None)
            print(f"转成docx文件出现错误，使用默认的Parser:{default_parser_class}")
            chunks = ""
            async for chunk in default_parser_class(self.config,self.database_provider,self.llm_provider).ingest(data, **kwargs):
                chunks += chunk + "\n"
                yield chunks        
            
        else:
            print(f"本是或已转成docx文件，使用JqDOCXParser")
            doc = self.Document(BytesIO(data))            
            yield TextNode(text='',metadata={"doc":doc,"source":filename})


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
