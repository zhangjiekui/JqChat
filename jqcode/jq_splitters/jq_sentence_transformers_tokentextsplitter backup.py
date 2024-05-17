import math
from langchain.text_splitter import TextSplitter,Tokenizer,split_text_on_tokens
from langchain_community.embeddings import HuggingFaceEmbeddings,HuggingFaceBgeEmbeddings
from jqcode.jq_agent.c0_init_env_models import get_emb_8k_rerank_model
from jqcode.jq_splitters.jq_chinese_recursive_text_splitter import ChineseRecursiveTextSplitter

from typing import (
    AbstractSet,
    Any,
    Callable,
    Collection,
    Dict,
    Iterable,
    List,
    Literal,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypedDict,
    TypeVar,
    Union,
    cast,
)

embed_model,embedding_model_8k,reranker = get_emb_8k_rerank_model()
class SentenceTransformersTokenTextSplitter(TextSplitter):
    """
    复制修改了源码，可以与HuggingFaceEmbeddings/HuggingFaceBgeEmbeddings共享model和tokenizer，避免了各自独立加载
    Splitting text to tokens using sentence model tokenizer.
    并且tokenizer\split_text\count_tokens等替换为ChineseRecursiveTextSplitter
    """

    def __init__(
        self,
        chunk_overlap: Union[int,float] = 50,
        model_name: Union[HuggingFaceEmbeddings, HuggingFaceBgeEmbeddings,str] = embed_model,
        tokens_per_chunk: Optional[int] = 500,
        **kwargs: Any,
    ) -> None:
        """Create a new TextSplitter."""
        if isinstance(chunk_overlap, float):
            if not 0.0 < chunk_overlap < 1.0:
                raise ValueError(f"Chunk overlap ratio/percent must between (0.0, 1.0), but got a value of {chunk_overlap}")                
            chunk_overlap = math.floor(tokens_per_chunk * chunk_overlap)
        
        if chunk_overlap >= tokens_per_chunk:
            raise ValueError(
                f"Got a larger chunk overlap ({chunk_overlap}) than or equal to chunk size "
                f"({tokens_per_chunk}), should be smaller."
            )        

        super().__init__(**kwargs, chunk_overlap=chunk_overlap)

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "Could not import sentence_transformer python package. "
                "This is needed in order to for SentenceTransformersTokenTextSplitter. "
                "Please install it with `pip install sentence-transformers`."
            )

        if isinstance(model_name,str):
            self.model_name = model_name
            self._model = SentenceTransformer(self.model_name)
        if isinstance(model_name,HuggingFaceEmbeddings) or isinstance(model_name,HuggingFaceBgeEmbeddings):
            self._model = model_name.client
            self.model_name = model_name.model_name

        self.tokenizer = self._model.tokenizer
        self._initialize_chunk_configuration(tokens_per_chunk=tokens_per_chunk)

    def _initialize_chunk_configuration(
        self, *, tokens_per_chunk: Optional[int]
    ) -> None:
        self.maximum_tokens_per_chunk = cast(int, self._model.max_seq_length)

        if tokens_per_chunk is None:
            self.tokens_per_chunk = self.maximum_tokens_per_chunk - 12
        else:
            self.tokens_per_chunk = tokens_per_chunk

        self._chunk_size = self.tokens_per_chunk

        if self.tokens_per_chunk > self.maximum_tokens_per_chunk - 12:
            raise ValueError(
                f"The token limit of the models '{self.model_name}'"
                f" is: {self.maximum_tokens_per_chunk}."
                f" Argument tokens_per_chunk={self.tokens_per_chunk}"
                f" > maximum token limit - 12."
            )

    def split_text(self, text: str) -> List[str]:
        def encode_strip_start_and_stop_token_ids(text: str) -> List[int]:
            return self._encode(text)[1:-1]

        tokenizer = Tokenizer(
            chunk_overlap=self._chunk_overlap,
            tokens_per_chunk=self.tokens_per_chunk,
            decode=self.tokenizer.decode,
            encode=encode_strip_start_and_stop_token_ids,
        )

        return split_text_on_tokens(text=text, tokenizer=tokenizer)

    def count_tokens(self, *, text: str) -> int:
        return len(self._encode(text))

    _max_length_equal_32_bit_integer: int = 2**32

    def _encode(self, text: str) -> List[int]:
        token_ids_with_start_and_end_token_ids = self.tokenizer.encode(
            text,
            max_length=self._max_length_equal_32_bit_integer,
            truncation="do_not_truncate",
        )
        return token_ids_with_start_and_end_token_ids
    
if __name__ == "__main__":
    from jqcode.jq_agent.c0_init_env_models import get_emb_8k_rerank_model
    embed_model,embedding_model_8k,reranker = get_emb_8k_rerank_model()

    text='区块链功能实现层实现了区块链网络中各种具体的区块链功能逻辑。平台采用实体挂载组件的方式。一个节点可以装配若干功能组件实现节点的实际功能。账本组件负责记录发生在网络中的交易信息，包括状态数据库、历史数据库和索引数据库等信息。区块组件将排序后的交易填充为区块。节点支持客户端对指定事件进行监听，并由监听者对事件进行处理。共识组件主要提供对交易的全局排序。交易指的是通过调用链码实现对账本状态的一次改变。客户端可以通过发送交易请求来让分布式账本记录信息。背书组件对收到的来自客户端的请求（交易提案）按照自身的逻辑进行检查，以决策是否予以支持。验证组件对排序后的一批交易进行提交到账本之前最终的检查。PKI组件主要负责对数字证书进行管理，包括生成、撤销等。智能合约组件提供对智能合约的功能支撑，由合约框架、应用合约和系统合约组成。智能合约是作为交易的一部分保存在总账上的应用级的代码。合约框架提供支持特定编程语言（JAVA、GO）的智能合约运行环境。应用合约支持提供编写用户智能合约的支持接口。系统合约负责节点自身的处理逻辑，包括系统配置、背书、检验等系统级智能合约。'
    
    stTokenTextSplitter=SentenceTransformersTokenTextSplitter(model_name=embed_model,tokens_per_chunk=100,chunk_overlap=0.2)
    # stTokenTextSplitter=SentenceTransformersTokenTextSplitter(model_name=embed_model,tokens_per_chunk=501,chunk_overlap=0.2)
    splits = stTokenTextSplitter.split_text(text)
    print(len(splits))
    for s in splits:
        tokens = stTokenTextSplitter.count_tokens(text=s)
        print(tokens)

    code = """
        class ChineseRecursiveTextSplitter(RecursiveCharacterTextSplitter):
            _tokenizer = _JqkjTokenizerWrapper()
            _len_func = _tokenizer.tokens_len

            def __init__(
                    self,
                    chunk_size: int = 1000,
                    chunk_overlap: Union[int,float] = 0.2,
                    separators: Optional[List[str]] = None,
                    keep_separator: bool = True,
                    is_separator_regex: bool = True,
                    add_start_index: bool = True,
                    strip_whitespace: bool = True,
                    length_function: Callable[[str], int] = _len_func,            
                    **kwargs: Any,
            ) -> None:
                'Create a new TextSplitter.'
                if isinstance(chunk_overlap, float):
                    if not 0.0 < chunk_overlap < 1.0:
                        raise ValueError(f"Chunk overlap ratio/percent must between (0.0, 1.0), but got a value of {chunk_overlap}")                
                    chunk_overlap = math.floor(chunk_size * chunk_overlap)

                if chunk_overlap >= chunk_size:
                    raise ValueError(
                        f"Got a larger chunk overlap ({chunk_overlap}) than or equal to chunk size "
                        f"({chunk_size}), should be smaller."
                    )
                super().__init__(chunk_size=chunk_size,chunk_overlap=chunk_overlap,add_start_index=add_start_index,keep_separator=keep_separator, strip_whitespace=strip_whitespace, length_function = length_function,**kwargs)
                self._separators = separators or [
                    "\n\n",
                    "\n",
                    "。|！|？",
                    "\.\s|\!\s|\?\s",
                    "；|;\s",
                    "”|》\s",
                    "，|,|、\s" #还不能删除逗号作为分隔符，否则有些句子无法分割
                    " " # 有些可能没有符号分割的，如方法名列表，考虑用空格分
                ]
                self._is_separator_regex = is_separator_regex
"""

    splits = stTokenTextSplitter.split_text(code)
    print(len(splits))
    for s in splits:
        tokens = stTokenTextSplitter.count_tokens(text=s)
        print(tokens)

