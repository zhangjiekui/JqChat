import os
import re
import math
from functools import partial
from typing import List, Optional, Any, Callable,Union
from transformers import AutoTokenizer
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from langchain_huggingface import HuggingFaceEmbeddings
from jqcode.jq_utils.logger import jqkj_logger
from jqcode.jq_config import general_config



logger = jqkj_logger(__file__).get_logger()
general_config.VERBOSE = True

def _split_text_with_regex_from_end(
        text: str, separator: str, keep_separator: bool
) -> List[str]:
    # Now that we have the separator, split the text
    if separator:
        if keep_separator:
            # The parentheses in the pattern keep the delimiters in the result.
            _splits = re.split(f"({separator})", text)
            splits = ["".join(i) for i in zip(_splits[0::2], _splits[1::2])]
            if len(_splits) % 2 == 1:
                splits += _splits[-1:]
            # splits = [_splits[0]] + splits
        else:
            splits = re.split(separator, text)
    else:
        splits = list(text)
    return [s for s in splits if s != ""]

class _JqkjTokenizerWrapper():
    def __init__(self, embeding_model: Union[HuggingFaceEmbeddings, HuggingFaceBgeEmbeddings,str] = None):
        if embeding_model is None:
            from jqcode.jq_agent.c0_init_env_models import env_models_instance
            embeding_model,embedding_model_8k,reranker = env_models_instance.get_emb_8k_rerank_model()
        assert embeding_model, 'embeding_model_instance不能为空'

        if isinstance(embeding_model,(HuggingFaceEmbeddings,HuggingFaceBgeEmbeddings)):
            self.model_name_or_path = embeding_model.model_name
            self.tokenizer = embeding_model.client.tokenizer
        elif isinstance(embeding_model,str):
            assert os.path.exists(embeding_model)
            self.model_name_or_path = embeding_model
            self.tokenizer = AutoTokenizer.from_pretrained(embeding_model)
        else:
            raise Exception('_JqkjTokenizerWrapper初始化失败，参数必须是Union[HuggingFaceEmbeddings, HuggingFaceBgeEmbeddings,str]')
        # self.partial_tokenize_func = partial(self.tokenizer.encode,**kwargs)

    _max_length_equal_32_bit_integer: int = 2**32
    def tokenize(self, text: str) -> List[int]: 
        token_ids_with_start_and_end_token_ids = self.tokenizer.encode(text,max_length=self._max_length_equal_32_bit_integer,truncation="do_not_truncate")
        return token_ids_with_start_and_end_token_ids
    
    def de_tokenize(self,ids: List[int]) -> str:
        return self.tokenizer.decode(ids)
    
    def tokens_len(self, text: str)-> int:
        if len(text)==0:
            return 0
        return len(self.tokenize(text))

    
    def __call__(self, text: str) -> List[int]:
        return self.tokenize(text)


class ChineseRecursiveTextSplitter(RecursiveCharacterTextSplitter):
    def __init__(
            self,
            model_name: Union[HuggingFaceEmbeddings, HuggingFaceBgeEmbeddings,str] = None,
            chunk_size: int = 500,
            chunk_overlap: float = 0.2,
            separators: Optional[List[str]] = None,
            keep_separator: bool = True,
            is_separator_regex: bool = True,
            add_start_index: bool = True,
            strip_whitespace: bool = True,
            length_function: Callable[[str], int] = None,            
            **kwargs: Any,
    ) -> None:
        """Create a new TextSplitter."""
        if isinstance(chunk_overlap, float):
            if not 0.0 < chunk_overlap < 1.0:
                raise ValueError(f"Chunk overlap ratio/percent must between (0.0, 1.0), but got a value of {chunk_overlap}")                
            chunk_overlap = math.floor(chunk_size * chunk_overlap)

        if chunk_overlap >= chunk_size:
            raise ValueError(
                f"Got a larger chunk overlap ({chunk_overlap}) than or equal to chunk size "
                f"({chunk_size}), should be smaller."
            )
        self.tokenizer_wrapper = _JqkjTokenizerWrapper(embeding_model=model_name)        
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

        super().__init__(chunk_size=chunk_size,chunk_overlap=chunk_overlap,add_start_index=add_start_index,keep_separator=keep_separator, strip_whitespace=strip_whitespace, length_function = self.tokenizer_wrapper.tokens_len,**kwargs)

    def _split_text(self, text: str, separators: List[str]) -> List[str]:
        """Split incoming text and return chunks."""
        final_chunks = []
        # Get appropriate separator to use
        separator = separators[-1]
        new_separators = []
        for i, _s in enumerate(separators):
            _separator = _s if self._is_separator_regex else re.escape(_s)
            if _s == "":
                separator = _s
                break
            if re.search(_separator, text):
                separator = _s
                new_separators = separators[i + 1:]
                break

        _separator = separator if self._is_separator_regex else re.escape(separator)
        splits = _split_text_with_regex_from_end(text, _separator, self._keep_separator)

        # Now go merging things, recursively splitting longer texts.
        _good_splits = []
        _separator = "" if self._keep_separator else separator
        for s in splits:
            if self._length_function(s) < self._chunk_size:
                _good_splits.append(s)
            else:
                if _good_splits:
                    merged_text = self._merge_splits(_good_splits, _separator)
                    final_chunks.extend(merged_text)
                    _good_splits = []
                if not new_separators:
                    final_chunks.append(s)
                else:
                    other_info = self._split_text(s, new_separators)
                    final_chunks.extend(other_info)
        if _good_splits:
            merged_text = self._merge_splits(_good_splits, _separator)
            final_chunks.extend(merged_text)
        return [re.sub(r"\n{2,}", "\n", chunk.strip()) for chunk in final_chunks if chunk.strip()!=""]

def _test__JqkjTokenizerWrapper():
    import tiktoken

    text = "你好，世界！"
    tokenizer_wrapper = _JqkjTokenizerWrapper()
    tokens = tokenizer_wrapper(text)
    print(tokens)
    print(tokenizer_wrapper.de_tokenize(tokens))
    print(tokenizer_wrapper.tokenizer.convert_ids_to_tokens(tokens))
    print(tokenizer_wrapper.tokenizer.decode(tokens))
    

    # de_tokenize

    tiktoken_enc = tiktoken.get_encoding("cl100k_base")
    tokens2 = tiktoken_enc.encode(text)
    print(tokens2)
    print(tiktoken_enc.decode(tokens2))    

def _test_JqkjChineseRecursiveTextSplitter():
    text_splitter = ChineseRecursiveTextSplitter(
        chunk_size=200,
        chunk_overlap=0
    )
    ls = [
        """中国对外贸易形势报告（75页）。前 10 个月，一般贸易进出口 19.5 万亿元，增长 25.1%， 比整体进出口增速高出 2.9 个百分点，占进出口总额的 61.7%，较去年同期提升 1.6 个百分点。其中，一般贸易出口 10.6 万亿元，增长 25.3%，占出口总额的 60.9%，提升 1.5 个百分点；进口8.9万亿元，增长24.9%，占进口总额的62.7%， 提升 1.8 个百分点。加工贸易进出口 6.8 万亿元，增长 11.8%， 占进出口总额的 21.5%，减少 2.0 个百分点。其中，出口增 长 10.4%，占出口总额的 24.3%，减少 2.6 个百分点；进口增 长 14.2%，占进口总额的 18.0%，减少 1.2 个百分点。此外， 以保税物流方式进出口 3.96 万亿元，增长 27.9%。其中，出 口 1.47 万亿元，增长 38.9%；进口 2.49 万亿元，增长 22.2%。前三季度，中国服务贸易继续保持快速增长态势。服务 进出口总额 37834.3 亿元，增长 11.6%；其中服务出口 17820.9 亿元，增长 27.3%；进口 20013.4 亿元，增长 0.5%，进口增 速实现了疫情以来的首次转正。服务出口增幅大于进口 26.8 个百分点，带动服务贸易逆差下降 62.9%至 2192.5 亿元。服 务贸易结构持续优化，知识密集型服务进出口 16917.7 亿元， 增长 13.3%，占服务进出口总额的比重达到 44.7%，提升 0.7 个百分点。 二、中国对外贸易发展环境分析和展望 全球疫情起伏反复，经济复苏分化加剧，大宗商品价格 上涨、能源紧缺、运力紧张及发达经济体政策调整外溢等风 险交织叠加。同时也要看到，我国经济长期向好的趋势没有 改变，外贸企业韧性和活力不断增强，新业态新模式加快发 展，创新转型步伐提速。产业链供应链面临挑战。美欧等加快出台制造业回迁计 划，加速产业链供应链本土布局，跨国公司调整产业链供应 链，全球双链面临新一轮重构，区域化、近岸化、本土化、 短链化趋势凸显。疫苗供应不足，制造业“缺芯”、物流受限、 运价高企，全球产业链供应链面临压力。 全球通胀持续高位运行。能源价格上涨加大主要经济体 的通胀压力，增加全球经济复苏的不确定性。世界银行今年 10 月发布《大宗商品市场展望》指出，能源价格在 2021 年 大涨逾 80%，并且仍将在 2022 年小幅上涨。IMF 指出，全 球通胀上行风险加剧，通胀前景存在巨大不确定性。""",
        """在深化医改的大背景下，国家高度重视医疗卫生行业信息化建设，经过多年的努力，从国家层面上基本完成了全国医院信息化建设的总体规划设计，初步解决了医院信息化缺乏标准和规范的问题，为医院信息化建设指明了方向。2016年6月-2018年8月，为促进和规范全国医院信息化建设，国家卫生健康委员会规划与信息司组织国内相关单位专家和技术人员，在总结了近20年来全国医院信息化应用发展的基础上，全面、科学地明确界定了医院信息化建设的基本功能、技术和建设要求，先后印发《医院信息平台应用功能指引》、《医院信息化建设应用指引》、《委属管医院数据上报管理方案》和《全国医院信息化建设标准与规范（试行）》等规范性文件。""",
        ]
    

    for inum, text in enumerate(ls):
        chunks = text_splitter.split_text(text)
        for i_num_chunk, chunk in enumerate(chunks):
            print(f'    ====#{inum+1}.{i_num_chunk+1},字符长度{len(chunk)}，tokens长度{text_splitter.tokenizer_wrapper.tokens_len(chunk)}\n',chunk)
        print('=============================================================')

    # documents = text_splitter.create_documents(ls)
    # for i, doc in enumerate(documents):
    #     print(doc)
            
    text = '中国对外贸易形势报告（75页）'
    ids = text_splitter.tokenizer_wrapper(text)
    id = text_splitter.tokenizer_wrapper("") #检查空字符串，正确返回[]
    print(ids)
    print(len(ids))
    l = text_splitter.tokenizer_wrapper.tokens_len(text)
    print(l)
    print(text_splitter.tokenizer_wrapper.de_tokenize(ids))
    for i,id in enumerate(ids):
        print(i,id,text_splitter.tokenizer_wrapper.de_tokenize(id))

if __name__ == "__main__":
    _test__JqkjTokenizerWrapper()
    _test_JqkjChineseRecursiveTextSplitter()

    text='区块链功能实现层实现了区块链网络中各种具体的区块链功能逻辑。平台采用实体挂载组件的方式。一个节点可以装配若干功能组件实现节点的实际功能。账本组件负责记录发生在网络中的交易信息，包括状态数据库、历史数据库和索引数据库等信息。区块组件将排序后的交易填充为区块。节点支持客户端对指定事件进行监听，并由监听者对事件进行处理。共识组件主要提供对交易的全局排序。交易指的是通过调用链码实现对账本状态的一次改变。客户端可以通过发送交易请求来让分布式账本记录信息。背书组件对收到的来自客户端的请求（交易提案）按照自身的逻辑进行检查，以决策是否予以支持。验证组件对排序后的一批交易进行提交到账本之前最终的检查。PKI组件主要负责对数字证书进行管理，包括生成、撤销等。智能合约组件提供对智能合约的功能支撑，由合约框架、应用合约和系统合约组成。智能合约是作为交易的一部分保存在总账上的应用级的代码。合约框架提供支持特定编程语言（JAVA、GO）的智能合约运行环境。应用合约支持提供编写用户智能合约的支持接口。系统合约负责节点自身的处理逻辑，包括系统配置、背书、检验等系统级智能合约。'
    text_splitter = ChineseRecursiveTextSplitter(
        chunk_size=100,
        chunk_overlap=0.2
    )


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

    chunks = text_splitter.split_text(code)
    inum =0
    print('=============================================================')
    for chunk in chunks:
        # inum+=1
        # print(f'    ====#{inum},字符长度{len(chunk)}，tokens长度{text_splitter._tokenizer.tokens_len(chunk)}\n',chunk)
        print(text_splitter.tokenizer_wrapper.tokens_len(chunk))
    print('=============================================================')