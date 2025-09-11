# type: ignore
import logging
import time
from typing import Any, AsyncGenerator, Optional
from docx.document import Document as DocxDocumentObject
from core import parsers
from core.base import (
    AsyncParser,
    ChunkingStrategy,
    Document,
    DocumentChunk,
    DocumentType,
    IngestionConfig,
    IngestionProvider,
    R2RDocumentProcessingError,
    RecursiveCharacterTextSplitter,
    TextSplitter,
)

try:
    from core.base import JqChineseRecursiveTextSplitter
except:
    from r2r import JqChineseRecursiveTextSplitter

from core.utils import generate_extraction_id

from ...database import PostgresDatabaseProvider
from ...llm import (
    LiteLLMCompletionProvider,
    OpenAICompletionProvider,
    R2RCompletionProvider,
)

logger = logging.getLogger()

file_type_processed_by_jqreader = ["pdf","doc","docx","md","html","htm"]

DEFAULT_PARSERS_BACKED = {
    "doc": parsers.DOCParser,
    "html": parsers.HTMLParser,
    "htm": parsers.HTMLParser,
    "md": parsers.MDParser,
    "pdf": parsers.BasicPDFParser,
}

class JqIngestionConfig(IngestionConfig):
    chunk_size: int = 512
    chunk_overlap: int = 100
    chunking_strategy: ChunkingStrategy = ChunkingStrategy.JQ
    extra_fields: dict[str, Any] = {}
    separator: Optional[str] = None


class JqIngestionProvider(IngestionProvider):


    DEFAULT_PARSERS = {
        DocumentType.BMP: parsers.BMPParser,
        DocumentType.CSV: parsers.CSVParser,
        DocumentType.DOC: parsers.JqDOCXParser, # JqDOCXParser
        DocumentType.DOCX: parsers.JqDOCXParser,# JqDOCXParser
        DocumentType.EML: parsers.EMLParser,
        DocumentType.EPUB: parsers.EPUBParser,
        DocumentType.HTML: parsers.JqDOCXParser,# JqDOCXParser
        DocumentType.HTM: parsers.JqDOCXParser, # JqDOCXParser
        DocumentType.ODT: parsers.ODTParser,
        DocumentType.JSON: parsers.JSONParser,
        DocumentType.MSG: parsers.MSGParser,
        DocumentType.ORG: parsers.ORGParser,
        DocumentType.MD: parsers.JqDOCXParser,  # JqDOCXParser
        DocumentType.PDF: parsers.JqDOCXParser, # JqDOCXParser
        DocumentType.PPT: parsers.PPTParser,
        DocumentType.PPTX: parsers.PPTXParser,
        DocumentType.TXT: parsers.TextParser,
        DocumentType.XLSX: parsers.XLSXParser,
        DocumentType.GIF: parsers.ImageParser,
        DocumentType.JPEG: parsers.ImageParser,
        DocumentType.JPG: parsers.ImageParser,
        DocumentType.TSV: parsers.TSVParser,
        DocumentType.PNG: parsers.ImageParser,
        DocumentType.HEIC: parsers.ImageParser,
        DocumentType.SVG: parsers.ImageParser,
        DocumentType.MP3: parsers.AudioParser,
        DocumentType.P7S: parsers.P7SParser,
        DocumentType.RST: parsers.RSTParser,
        DocumentType.RTF: parsers.RTFParser,
        DocumentType.TIFF: parsers.TIFFParser,
        DocumentType.XLS: parsers.XLSParser,
    }


    EXTRA_PARSERS = {
        DocumentType.CSV: {"advanced": parsers.CSVParserAdvanced},
        DocumentType.PDF: {
            "unstructured": parsers.PDFParserUnstructured,
            "zerox": parsers.VLMPDFParser,
        },
        DocumentType.XLSX: {"advanced": parsers.XLSXParserAdvanced},
    }

    IMAGE_TYPES = {
        DocumentType.GIF,
        DocumentType.HEIC,
        DocumentType.JPG,
        DocumentType.JPEG,
        DocumentType.PNG,
        DocumentType.SVG,
    }

    def __init__(
        self,
        config: JqIngestionConfig,
        database_provider: PostgresDatabaseProvider,
        llm_provider: (
            LiteLLMCompletionProvider
            | OpenAICompletionProvider
            | R2RCompletionProvider
        ),
    ):
        super().__init__(config, database_provider, llm_provider)
        self.config: JqIngestionConfig = config
        self.database_provider: PostgresDatabaseProvider = database_provider
        self.llm_provider: (
            LiteLLMCompletionProvider
            | OpenAICompletionProvider
            | R2RCompletionProvider
        ) = llm_provider
        self.parsers: dict[DocumentType, AsyncParser] = {}
        self.text_splitter = self._build_text_splitter()
        self._initialize_parsers()

        logger.info(
            f"JqIngestionProvider initialized with config: {self.config}"
        )

    def _initialize_parsers(self):
        for doc_type, parser in self.DEFAULT_PARSERS.items():
            # will choose the first parser in the list
            if doc_type not in self.config.excluded_parsers:
                self.parsers[doc_type] = parser(
                    config=self.config,
                    database_provider=self.database_provider,
                    llm_provider=self.llm_provider,
                )
        for doc_type, doc_parser_name in self.config.extra_parsers.items():
            logger.info(f"JqIngestionProvider extra parser: {doc_parser_name}")
            logger.info(f"JqIngestionProvider extra parser doc_type: {doc_type}")
            logger.info(f"JqIngestionProvider EXTRA_PARSERS: {JqIngestionProvider.EXTRA_PARSERS[doc_type]}")

            if isinstance(doc_parser_name, list):
                doc_parser_name = doc_parser_name[0]
            self.parsers[f"{doc_parser_name}_{str(doc_type)}"] = (
                JqIngestionProvider.EXTRA_PARSERS[doc_type][doc_parser_name](
                    config=self.config,
                    database_provider=self.database_provider,
                    llm_provider=self.llm_provider,
                )
            )

    def _build_text_splitter(
        self, ingestion_config_override: Optional[dict] = None
    ) -> TextSplitter:
        logger.info(
            f"Initializing text splitter with method: {self.config.chunking_strategy}"
        )

        if not ingestion_config_override:
            ingestion_config_override = {}

        chunking_strategy = (
            ingestion_config_override.get("chunking_strategy")
            or self.config.chunking_strategy
        )

        chunk_size = (
            ingestion_config_override.get("chunk_size")
            or self.config.chunk_size
        )
        chunk_overlap = (
            ingestion_config_override.get("chunk_overlap")
            or self.config.chunk_overlap
        )
        if chunking_strategy == ChunkingStrategy.JQ:
            return JqChineseRecursiveTextSplitter(
                tokenizer=None,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )  


        if chunking_strategy == ChunkingStrategy.RECURSIVE:
            return RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
        elif chunking_strategy == ChunkingStrategy.CHARACTER:
            from core.base.utils.splitter.text import CharacterTextSplitter

            separator = (
                ingestion_config_override.get("separator")
                or self.config.separator
                or CharacterTextSplitter.DEFAULT_SEPARATOR
            )

            return CharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                separator=separator,
                keep_separator=False,
                strip_whitespace=True,
            )
        elif chunking_strategy == ChunkingStrategy.BASIC:
            raise NotImplementedError(
                "Basic chunking method not implemented. Please use Recursive."
            )
        elif chunking_strategy == ChunkingStrategy.BY_TITLE:
            raise NotImplementedError("By title method not implemented")
        else:
            raise ValueError(f"Unsupported method type: {chunking_strategy}")

    def validate_config(self) -> bool:
        return self.config.chunk_size > 0 and self.config.chunk_overlap >= 0

    def chunk(
        self,
        parsed_document: str | DocumentChunk | DocxDocumentObject,
        ingestion_config_override: dict,
    ) -> AsyncGenerator[Any, None]:
        splitter = self.text_splitter
        if ingestion_config_override:
            splitter = self._build_text_splitter(
                ingestion_config_override
            )
        if isinstance(parsed_document, DocumentChunk):
            parsed_document = parsed_document.data

        if isinstance(parsed_document, str):
            # text = '<标题目录toc：doc1.docx/>[表格]：项目名称,,,省工信厅“中国声谷”奖补项目申报核查,,,,,,\r\n被审计（调查）单位或个人,,,安徽晶奇网络科技股份有限公司,,,,,,\r\n审计（调查）事项,,,对技术创新产品产业化项目、企业研发产品产业化项目申报,,,,,,\r\n审计（调查）事项摘要,"安徽晶奇网络科技股份有限公司（以下简称“晶奇网络公司”）以民政和卫生领域的信息化为基础，围绕“防、治、养”为大健康产业链中的服务对象提供智慧医疗、智慧医保、智慧民政、智慧健康养老的整体解方案、数据挖掘以及数据安全服务,在健康医疗大数据领域从大数据采集、大数据治理、大数据挖掘分析和大数据应用四个环节提供技术解决方案和产品服务，系软件信息化整体解决方案提供商。根据《支持中国声谷创新发展若干政策》及应用指南等有关政策文件中关于企业研发产品产业化项目、企业研发产品产业化项目的相关规定，分别于2019年至2023年每年度向省工信厅（原省经信厅）提交有关项目申请奖补材料。1.企业日常按“晶奇退役军人智能信息管理系统”“处方流转平台”等项目进行内部研发立项（为便于区别，以下简称“小项目”），在向省工信厅申报研发产品产业化补助时，将若干研发“小项目”组成一个“大项目”进行奖补申报，如2020年申报的“基层民生服务大数据应用示范项目”共涉及11个“小项目”。“大项目”与“小项目”对应关系如下表所示：2.检查晶奇网络公司产品产业化项目相关申报材料，发现以下事实，详见下表（单位：万元）：",,,,,,,,\r\n审计人员,,,,,,编制日期,,,\r\n证据提供单位或个人意见,,,,,,,,,\r\n证据提供单位或个人意见,,证据提供单位盖章、负责人或者其确定的人员签名,,,,,日期,,\r\n附件：     页'
            # chunks = text_spliiter.create_documents([text])
            chunks = splitter.create_documents([parsed_document])

        elif isinstance(parsed_document, DocxDocumentObject):
            from r2r import JqkjDocxReader,JqkjDocTreeTokenTextSplitter,JqChineseRecursiveTextSplitter
            from llama_index.core.schema import TextNode

            reader = JqkjDocxReader()
            makeup_file_path="/app/docs/doc1.docx"

            doc_tree,_ = reader.parse_docx_into_tree(parsed_document,file_path=makeup_file_path)             
            text_splitter = JqChineseRecursiveTextSplitter(tokenizer=None)
            doc_tree_spiltter = JqkjDocTreeTokenTextSplitter.from_defaults(cr_text_splitter=text_splitter)
            lm_base_node = TextNode(text='',metadata={"source":makeup_file_path})
            split_results = doc_tree_spiltter._parse_node_on_tree(lm_base_node,doc_tree)
            chunks = [node.text for node in split_results]

        else:
            # Assuming parsed_document is already a list of text chunks
            chunks = parsed_document

        for chunk in chunks:
            yield (
                chunk.page_content if hasattr(chunk, "page_content") else chunk
            )

    async def parse(  # type: ignore
        self,
        file_content: bytes,
        document: Document,
        ingestion_config_override: dict,
    ) -> AsyncGenerator[DocumentChunk, None]:
        if document.document_type not in self.parsers:
            raise R2RDocumentProcessingError(
                document_id=document.id,
                error_message=f"Parser for {document.document_type} not found in `R2RIngestionProvider`.",
            )
        else:
            t0 = time.time()
            contents = []
            parser_overrides = ingestion_config_override.get(
                "parser_overrides", {}
            )
            if document.document_type.value in parser_overrides:
                logger.info(
                    f"Using parser_override for {document.document_type} with input value {parser_overrides[document.document_type.value]}"
                )
                # TODO - Cleanup this approach to be less hardcoded
                if (
                    document.document_type != DocumentType.PDF
                    or parser_overrides[DocumentType.PDF.value] != "zerox"
                ):
                    raise ValueError(
                        "Only Zerox PDF parser override is available."
                    )
                async for chunk in self.parsers[
                    f"zerox_{DocumentType.PDF.value}"
                ].ingest(file_content, **ingestion_config_override):
                    if isinstance(chunk, dict) and chunk.get("content"):
                        contents.append(chunk)
                    elif (
                        chunk
                    ):  # Handle string output for backward compatibility
                        contents.append({"content": chunk})
            else:
                ingestion_config_override.update({"document":document})
                async for text in self.parsers[document.document_type].ingest(
                    file_content, **ingestion_config_override
                ):
                    if text is not None:
                        contents.append({"content": text})

            if not contents:
                logging.warning(
                    "No valid text content was extracted during parsing"
                )
                return

            iteration = 0
            for content_item in contents:
                chunk_text = content_item["content"]
                chunks = self.chunk(chunk_text, ingestion_config_override)

                for chunk in chunks:
                    metadata = {**document.metadata, "chunk_order": iteration}
                    if "page_number" in content_item:
                        metadata["page_number"] = content_item["page_number"]

                    extraction = DocumentChunk(
                        id=generate_extraction_id(document.id, iteration),
                        document_id=document.id,
                        owner_id=document.owner_id,
                        collection_ids=document.collection_ids,
                        data=chunk,
                        metadata=metadata,
                    )
                    iteration += 1
                    yield extraction

            logger.debug(
                f"Parsed document with id={document.id}, title={document.metadata.get('title', None)}, "
                f"user_id={document.metadata.get('user_id', None)}, metadata={document.metadata} "
                f"into {iteration} extractions in t={time.time() - t0:.2f} seconds."
            )

    def get_parser_for_document_type(self, doc_type: DocumentType) -> Any:
        return self.parsers.get(doc_type)
