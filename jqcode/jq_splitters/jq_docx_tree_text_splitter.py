import os,re
import copy,math
import pandas as pd
from io import StringIO
import copy
from dotenv import load_dotenv, find_dotenv
from pathlib import Path
import json_repair

from typing import Any, Callable, List, Optional, Sequence,Union
from anytree import Node as AnytreeNode
from anytree import RenderTree, AsciiStyle, PreOrderIter
from anytree import LevelOrderGroupIter, util

from llama_index.core.callbacks.base import CallbackManager
from llama_index.core.schema import BaseNode, TextNode,Document, MetadataMode
from llama_index.core.bridge.pydantic import Field
from llama_index.core.callbacks.schema import CBEventType, EventPayload
from llama_index.core.utils import get_tqdm_iterable
from llama_index.core.node_parser.node_utils import IdFuncCallable, build_nodes_from_splits
from llama_index.core.node_parser.interface import MetadataAwareTextSplitter

from jqcode.jq_readers.backend_reader_utils.jqkj_doc_tree_utils import jieba_pre_process,TreeNodeType,get_doc_tree_from_document
from jqcode.jq_splitters.backend_splitter_utils.jq_chinese_recursive_text_splitter import JqChineseRecursiveTextSplitter
from jqcode.jq_agent.tools.jq_web_search_engine import is_query_chinese
from jqcode.jq_utils.logger import jqkj_logger

logger = jqkj_logger(__file__).get_logger()

try:
    from llama_index.core.node_parser.node_utils import default_id_func    
except:
    default_id_func = None

def load_project_env(): 
    env_loaded_value_in_env = os.getenv("env_loaded",'')
    dotenv_loaded = False
    # 只载入一次
    if env_loaded_value_in_env != "True":    
        print('\n')
        print('=*'*20)
        env_dir = find_dotenv()
        if not env_dir:
            root_dir = Path().resolve()
            env_dir = root_dir/'JqChat/.env'
        print(f"项目.env文件路径：{env_dir}")       

        dotenv_loaded = load_dotenv(env_dir)
        if dotenv_loaded:
            print(f"=*=* load_dotenv('{env_dir}')成功！")
            os.environ["env_loaded"] = "True"
        else:
            print(f"=*=* load_dotenv('{env_dir}')失败，请检查！")
            os.environ["env_loaded"] = "False"
        print('=*'*20)
        print('\n')
    else:
        dotenv_loaded = True
    return dotenv_loaded
load_project_env()

# os.environ["env_loaded"] = "False"
DEFAULT_CHUNK_OVERLAP = float(os.getenv('DEFAULT_CHUNK_OVERLAP',0.2))
EMBEDDING_MODEL_CARD = os.getenv("EMBEDDING_MODEL_CARD",'')
EMBEDDING_MODEL_CARD = json_repair.loads(EMBEDDING_MODEL_CARD)
DEFAULT_CHUNK_SIZE = EMBEDDING_MODEL_CARD.get('max_tokens',512)
# NOTE: this is the number of tokens reserved for special tokens(BOS,EOS) and metadata formatting
DEFAULT_MODEL_RESERVED_TOKENS_SIZE = 10
DEFAULT_METADATA_FORMAT_LEN = 2

TOKEN_THRESHOLD = DEFAULT_CHUNK_SIZE - DEFAULT_MODEL_RESERVED_TOKENS_SIZE -2

def under_non_alpha_ratio(text: str, threshold: float = 0.5):
    """Checks if the proportion of non-alpha characters in the text snippet exceeds a given
    threshold. This helps prevent text like "-----------BREAK---------" from being tagged
    as a title or narrative text. The ratio does not count spaces.

    Parameters
    ----------
    text
        The input string to test
    threshold
        If the proportion of non-alpha characters exceeds this threshold, the function
        returns False
    """
    if len(text) == 0:
        return False
    
    if not is_query_chinese(text):
        return False
    else:
        try:
            alpha_count = len([char for char in text if char.strip() and char.isalpha()])
            total_count = len([char for char in text if char.strip()])
            ratio = alpha_count / total_count
            return ratio < threshold
        except:
            return False

# derived from jqcode.jq_knowledge_manegement.chatchat.server.file_rag.text_splitter.zh_title_enhance import is_possible_title
def is_possible_title(
    text: str,
    title_max_word_length: int = 20,
    non_alpha_threshold: float = 0.5,
) -> bool:
    """Checks to see if the text passes all of the checks for a valid title.

    Parameters
    ----------
    text
        The input text to check
    title_max_word_length
        The maximum number of words a title can contain
    non_alpha_threshold
        The minimum number of alpha characters the text needs to be considered a title
    """
    words_num = 0
    if is_query_chinese(text):
        words_num = len(text)
        if words_num<2 or words_num>title_max_word_length:
            return False
    else:
        words = text.split()
        words = [w for w in words if w.strip()]
        words_num = len(words)
        if words_num<1 or words_num>int(title_max_word_length/2):
            return False

    # 文本中数字的占比不能太高，否则不是title
    if under_non_alpha_ratio(text, threshold=non_alpha_threshold):
        return False

    # NOTE(robinson) - Prevent flagging salutations like "To My Dearest Friends," as titles
    if text.endswith(("," , "，", ";", "；" )):
        return False

    if text.isnumeric():
        return False
    
    return True

# _r = is_possible_title('2、标准规范、功能全面')
# print(_r)

def get_possible_zh_title_for_previous_sibling(cur_node,title_max_word_length=20):
    get_possible_zh_title = ''
    previous_sibling = util.leftsibling(cur_node)
    if previous_sibling:
        previous_sibling_text = previous_sibling.text.strip() + '\n'
        other_conditions = previous_sibling.is_leaf and previous_sibling.type == TreeNodeType.TEXT and 'Heading' not in previous_sibling.style
        
        previous_sibling_style = ''
        try:#
            previous_sibling_style = previous_sibling.style
            # print(f"previous_sibling.style是可能存在的，{previous_sibling.style}")    
        except:
            logger.debug(f'Tree Node previous_sibling 没有style，获取previous_sibling.style失败！')

        if 'List Paragraph' in previous_sibling_style or other_conditions:   
            if is_possible_title(text=previous_sibling_text,title_max_word_length=title_max_word_length):
                get_possible_zh_title = previous_sibling_text
 
    return get_possible_zh_title

def _get_pre_title_nodes_text(pre_title_nodes,normal_text:bool=False):
    if len(pre_title_nodes) > 0:
        pre_title_nodes_text = [pre_title_node.text for pre_title_node in pre_title_nodes]
        if normal_text:
            text_cached = '\n'.join(pre_title_nodes_text) + '\n'
        else:
            text_cached = '|'.join(pre_title_nodes_text)
            text_cached = f'\n<标题目录toc：{text_cached}/>'
            # <table column_names={col_text}/>
    else:
        text_cached = ''
    return text_cached

def get_pre_title_nodes_text(cur_node,cur_title_node,pre_title_node,cur_ancestors_text_placeholder,pre_ancestors_text_placeholder):
    if cur_node.is_leaf and cur_node.parent.type in [TreeNodeType.TEXT,TreeNodeType.DOCUMENT]:
        cur_title_node = cur_node.parent
        if cur_ancestors_text_placeholder == '': # 只有第一次会取值
            cur_ancestors_text_placeholder = _get_pre_title_nodes_text(cur_node.ancestors[1:]) #[1:] 去除文件名根节点                 
        if cur_node == cur_title_node.children[0] or cur_title_node != pre_title_node :     # 然后就只有在第一个叶子文本节点，或是父节点发生变化时再取值
            pre_title_node = cur_title_node
            cur_ancestors_text_placeholder = _get_pre_title_nodes_text(cur_node.ancestors[1:]) #[1:] 去除文件名根节点
    return cur_title_node,pre_title_node,cur_ancestors_text_placeholder,pre_ancestors_text_placeholder

class JqkjDocTreeTokenTextSplitter(MetadataAwareTextSplitter):  
    _default_normal_tokens_chunk_size = DEFAULT_CHUNK_SIZE - DEFAULT_MODEL_RESERVED_TOKENS_SIZE - DEFAULT_METADATA_FORMAT_LEN

    model_reserved_tokens_size: int = Field(default=DEFAULT_MODEL_RESERVED_TOKENS_SIZE , description="为嵌入模型预留的tokens(如BOS、EOS)数量。")    
    normal_tokens_chunk_size: int = Field(default= _default_normal_tokens_chunk_size, description="减去model_reserved_tokens_size后，能够喂入嵌入模型的正常tokens数量")
    # 注意：下面的chunk_size是已经去掉保留tokes后的，真正能够喂入模型的正常tokens数量
    chunk_size: int = Field(default=normal_tokens_chunk_size,description="每个文本块chunk的tokens数量大小", gt=0, )
    chunk_overlap: Union[int,float] = Field(default=DEFAULT_CHUNK_OVERLAP,description="两个文本块chunk可以重叠的数量大小或比例",gte=0,)
    cr_text_splitter:JqChineseRecursiveTextSplitter = Field(default=None,description="中英文文本分割器")
    tokens_len_func: Callable = Field(default=None,description="获取tokens数量")
 
    class Config:
        arbitrary_types_allowed = True
    
    def __init__(
        self,
        cr_text_splitter:JqChineseRecursiveTextSplitter,
        # chunk_size: int = DEFAULT_CHUNK_SIZE,
        # chunk_overlap: Union[int,float] = DEFAULT_CHUNK_OVERLAP,
        model_reserved_tokens_size: int = DEFAULT_MODEL_RESERVED_TOKENS_SIZE,    
        callback_manager: Optional[CallbackManager] = None,
        include_metadata: bool = True,
        include_prev_next_rel: bool = True,
        id_func: Optional[Callable[[int, Document], str]] = None,
    ):
        """Initialize with parameters."""
        chunk_size = cr_text_splitter._chunk_size
        chunk_overlap = cr_text_splitter._chunk_overlap
        _normal_tokens_chunk_size = chunk_size - model_reserved_tokens_size
        
        

        callback_manager = callback_manager or CallbackManager([])
        id_func = id_func or default_id_func

        super().__init__(
            chunk_size=_normal_tokens_chunk_size,
            chunk_overlap=chunk_overlap,
            callback_manager=callback_manager,
            include_metadata=include_metadata,
            include_prev_next_rel=include_prev_next_rel,
            id_func=id_func,
        )
        self.cr_text_splitter = cr_text_splitter
        self.tokens_len_func = self.cr_text_splitter.tokenizer_wrapper.tokens_len

            

    # 覆写了父类方法，更换了长度函数 len ->  self.cr_text_splitter._tokenizer.tokens_len
    # 增加了always_use_embed_metadata_str参数，默认为True，是因为目前embedding模型的seq_len值一般比较小，如512，1024，
    # 但大语言模型的seq_len/context已经基本不是限制了
    def _get_metadata_str(self, node: BaseNode,always_use_embed_metadata_str=True) -> str:
        """Helper function to get the proper metadata str for splitting."""
        embed_metadata_str = node.get_metadata_str(mode=MetadataMode.EMBED)
        if always_use_embed_metadata_str:
            return embed_metadata_str
        else:  # use the longest metadata str for splitting
            llm_metadata_str = node.get_metadata_str(mode=MetadataMode.LLM)            
            if self.tokens_len_func(embed_metadata_str) > self.cr_text_splitter._tokenizer.tokens_len(llm_metadata_str):
                metadata_str = embed_metadata_str
            else:
                metadata_str = llm_metadata_str
        
        logger.warning(f"{metadata_str=}")
        raise Exception("暂时不管metadata_str，目前为止都没有实际价值")
        # return metadata_str
        return ""


    @classmethod
    def from_defaults(
        cls,
        cr_text_splitter:JqChineseRecursiveTextSplitter,
        # chunk_size: int = DEFAULT_CHUNK_SIZE,
        # chunk_overlap: Union[int,float] = DEFAULT_CHUNK_OVERLAP,
        model_reserved_tokens_size: int = DEFAULT_MODEL_RESERVED_TOKENS_SIZE,
        callback_manager: Optional[CallbackManager] = None,
        include_metadata: bool = True,
        include_prev_next_rel: bool = True,
        id_func: Optional[Callable[[int, Document], str]] = None,
    ) -> "JqkjDocTreeTokenTextSplitter":
        """Initialize with default parameters."""
        callback_manager = callback_manager or CallbackManager([])
        return cls(
            cr_text_splitter,
            # chunk_size = chunk_size,
            # chunk_overlap = chunk_overlap,
            model_reserved_tokens_size = model_reserved_tokens_size, 
            callback_manager = callback_manager,
            include_metadata = include_metadata,
            include_prev_next_rel = include_prev_next_rel,
            id_func = id_func or default_id_func
            )

    @classmethod
    def class_name(cls) -> str:
        return "JqkjDocTreeTokenTextSplitter"
    
    def write_chunkes_to_preview_file(self, text_splits: List[str], save_path_txt: str):
        logger.info(f'\n==============================================================')
        logger.info(f'将切分结果保存到{save_path_txt}......')
        with open(save_path_txt,'w',encoding='utf-8') as f:            
            min_percent =1.0
            max_percent =0.0
            for i,s in enumerate(text_splits):
                tokens_num = self.tokens_len_func(text=s)
                percent = tokens_num/self.chunk_size
                if percent < min_percent:
                    min_percent = percent
                if percent > max_percent:
                    max_percent = percent
            min_percent_str = f'{min_percent*100:.1f}%'
            max_percent_str = f'{max_percent*100:.1f}%'
            f.write(f'##共切分为{len(text_splits)}个Chunks,最大tokens限制为{DEFAULT_CHUNK_SIZE}，tokens利用率最大为{max_percent_str}，最小为{min_percent_str}。##')
            # logger.info(f'共切分为{len(text_splits)}个Chunks,最大tokens限制为{DEFAULT_CHUNK_SIZE}，tokens利用率最大为{max_percent_str}，最小为{min_percent_str}。')
            
            for i,s in enumerate(text_splits):
                # if not s.startswith('<toc'):
                #     continue
                # assert s.startswith('<toc'),f'切分结果必须以"<toc"开头，当前结果为{s}'
                tokens_num = self.tokens_len_func(text=s)
                percent = tokens_num/self.chunk_size
                percent_str = f'{percent*100:.1f}%'
                error = ''

                if tokens_num/(DEFAULT_CHUNK_SIZE) > 1.0:
                    error = f'**tokens利用率{percent_str}超出100%是不对的！'
                    logger.warning(f'\n{error}本Chunk共{tokens_num}个tokens,tokens限额为{DEFAULT_CHUNK_SIZE},以下是该chunk内容:')
                    logger.warning(f'{s}')
                # logger.info(f'\n\n==S{i}：{error} 本Chunk共{tokens_num}个tokens，{len(s)}个字符，tokens利用率{percent_str}\n')
                f.write(f'\n\n==S{i+1}：{error}本Chunk共{tokens_num}个tokens,{len(s)}个字符，tokens利用率{percent_str},tokens限额为{DEFAULT_CHUNK_SIZE}\n')
                f.write(f'{s}\n\n')
        logger.info(f'......切分结果已保存到{save_path_txt}')

    def add_text(self,text_cached:str='',cur_text:str='',cur_node=None,chunks_saved:list=[]):
        merge_status = True
        text_cached_tokens = self.tokens_len_func(text_cached)
        text_tobe_added_tokens = self.tokens_len_func(cur_text)

        assert text_cached_tokens<=TOKEN_THRESHOLD, f"text_cached已有的tokens数量为{text_cached_tokens},已超过上限{TOKEN_THRESHOLD=}"
        total_tokens = text_cached_tokens + text_tobe_added_tokens
        
        if  total_tokens<= TOKEN_THRESHOLD:
            text_cached += cur_text
            text_cached_tokens = self.tokens_len_func(text_cached)
            cur_text = ''

            if text_cached_tokens >= TOKEN_THRESHOLD*0.8:
                chunks_saved.append(text_cached.strip('\n'))
                if cur_node:
                    text_cached =  get_possible_zh_title_for_previous_sibling(cur_node)
        else:
            # logger.warning(f"{total_tokens=}，超出了上限{TOKEN_THRESHOLD=}")
            # logger.warning(f"{text_cached_tokens=}，又没有达到{TOKEN_THRESHOLD*0.8=}的切分标准")
            # logger.warning(f"{text_tobe_added_tokens=}，建议先对text_tobe_added进行切分！")
            merge_status = False
        return text_cached,cur_text,chunks_saved,merge_status



    def _parse_node_on_tree(self, lm_base_node: BaseNode, doc_tree: AnytreeNode, cutoff_ratio_as_chunk=0.8,get_to_first_title_directly=False) -> List[BaseNode]:
        
        chunks_saved = [] #存储“已经处理好的Chunks”
        text_cached =''   # 累积起来的待分割的文本
        cur_text = ''     # 当前读入的文本（可能包含Ancestors节点的标题目录文本）
        node_text = ''    # 当前文本节点的文本

        tokens_cached = 0

        max_chunk_size = self.normal_tokens_chunk_size #tokes限额
        tokens_cutoff = self.normal_tokens_chunk_size  #tokes余额，会变动
        # 暂时不管metadata_str，目前为止都没有实际价值
        # lm_base_node.excluded_embed_metadata_keys.remove('file_name')
        # metadata_str = self._get_metadata_str(lm_base_node)
        # metadata_str_tokens_num = self.tokens_len_func(metadata_str) 
        metadata_str_tokens_num =0 

        pre_title_node = None
        cur_title_node = None
        pre_ancestors_text_placeholder = ''
        cur_ancestors_text_placeholder = ''

        # 特别注意：
        # 只对当前文本cur_text进行分割，
        # 前导标题节点文本ancestors_text 和 元数据字符串metadata_str 不参与分割，
        # 而是直接相加拼装上去,如：split = ancestors_text + a_cur_text_split + metadata_str
        # 但是 前导标题节点文本ancestors_text 和 元数据字符串metadata_str 的tokens_num要参与计算，避免总tokens num/len 溢出
        all_tree_nodes = list(PreOrderIter(doc_tree))
        nodes = [node for node in all_tree_nodes]
        last_nodes = nodes[-1]

        for i,cur_node in enumerate(all_tree_nodes):
            node_text = cur_node.text.strip()
            # 如果节点没有文本，跳出本次节点循环，不执行后面的代码，进入下一个节点
            if len(node_text) == 0: 
                continue

            if get_to_first_title_directly:
                try:
                    if cur_node.type == TreeNodeType.TEXT and 'Heading' in cur_node.style:
                        get_to_first_title_directly = False
                    else:
                        continue
                except :
                    continue

            cur_title_node,pre_title_node,cur_ancestors_text_placeholder,pre_ancestors_text_placeholder = get_pre_title_nodes_text(cur_node,cur_title_node=cur_title_node,pre_title_node=pre_title_node,cur_ancestors_text_placeholder=cur_ancestors_text_placeholder,pre_ancestors_text_placeholder=pre_ancestors_text_placeholder)

            #  如果是文本类型，存在过滤目录等特有处理
            if cur_node.type == TreeNodeType.TEXT:
                
                # 跳过目录(toc)的内容，因为对于RAG任务没什么作用，反而可能会在检索阶段存在干扰
                # 与上面的get_to_first_title_directly可能会重复，
                # 上面的get_to_first_title_directly处理的是即使没有明确的toc标识信息的情况（如pdf转过来的docx）
                # 这里处理的是word中生成的toc，含有 style == 'toc'信息
                # 所以仍然保留着

                if 'toc' in cur_node.style:
                    continue

                ## 跳过目录标题文本（Heading）的内容 
                if 'Heading' in cur_node.style:
                    pre_title_node = cur_node
                    continue

                if node_text.replace(' ','').lower() in ['目录','toc','tableofcontents','tableofcontent']:
                    continue

            if cur_node.type in [TreeNodeType.TEXT,TreeNodeType.IMAGE]:
                ancestors_text_placeholder = '' if pre_ancestors_text_placeholder==cur_ancestors_text_placeholder else cur_ancestors_text_placeholder

                if len(ancestors_text_placeholder) == 0 and len(text_cached) == 0: #保证每个split开头都有 标题目录 信息
                    text_cached = _get_pre_title_nodes_text(cur_node.ancestors[1:]) 

                if ancestors_text_placeholder not in text_cached:
                    cur_text = ancestors_text_placeholder + node_text + '\n'
                else:
                    cur_text = node_text + '\n'

                pre_ancestors_text_placeholder=cur_ancestors_text_placeholder                
                tokens_ancestors = self.tokens_len_func(text=ancestors_text_placeholder)
                
                text_cached,cur_text,chunks_saved,merge_status = self.add_text(text_cached=text_cached,cur_text=cur_text,cur_node=cur_node,chunks_saved=chunks_saved)
                
                if not merge_status: # 当前文本的tokens数已超出了tokens_cutoff剩余限额                    
                    #======  先处理text_cached，
                    # （1）要么直接作为chunk，这种情况在add_text方法里已经处理
                    # （2）要么对当前文本进行切分，补齐切分到text_cached，一起作为一个chunk
                            # 下面处理这种情况
                    
                    tokens_cached = self.tokens_len_func(text_cached)
                    # 【累积文本text_cached】与【当前文本node_text】拼接
                    # 正常分割，但只保留分割后的第一个chunk，用以补齐text_cached形成一个完整的Chunk
                    # 要特别注意chunk_size的控制，详见_split_text方法中对chunk_size和hunk_overlap的处理
                    chunks = self._split_text(node_text,chunk_size=max_chunk_size - tokens_cached - tokens_ancestors)
                    cur_text = ancestors_text_placeholder + chunks[0]
                    text_cached,cur_text,chunks_saved,merge_status = self.add_text(text_cached=text_cached,cur_text=cur_text,cur_node=cur_node,chunks_saved=chunks_saved)
                    # ====== text_cached已经处理完毕
                        
                    #################################################
                    
                    # 着手处理当前节点， 开始新的切片
                        # 接着将当前文本 node_text 还作为一个整体来处理，因为可能是一个很长的段落文本，本身足以构成一个或多个split(s)
                        # 所以可以取多个splits(最后一个不确定)

                    tokens_cached = self.tokens_len_func(text_cached)  # 重新计算tokens_cached
                    tokens_node_text = self.tokens_len_func(text=node_text)
      
                    # 因为是要对当前文本进行分割，所以前面必须要有cur_ancestors_text_placeholder部分
                    cur_ancestors_text_placeholder = _get_pre_title_nodes_text(cur_node.ancestors[1:])
                    # 因为要比较是否相等，所以同步加上
                    if pre_ancestors_text_placeholder == cur_ancestors_text_placeholder:
                        if pre_ancestors_text_placeholder not in text_cached:
                            pre_ancestors_text_placeholder += text_cached
                    
                    if cur_ancestors_text_placeholder not in text_cached:
                        text_cached += cur_ancestors_text_placeholder                    

                    tokens_ancestors = self.tokens_len_func(text=cur_ancestors_text_placeholder)

                    if  tokens_node_text > max_chunk_size - tokens_cached -tokens_ancestors:
                        # 只分割当前文本 node_text
                        # 把ancestors_text_placeholder 和 分割出来的部分拼接在一起， 形成一个或多个完整的split
                        chunk_tokens_size = max_chunk_size - tokens_cached - tokens_ancestors
                        chunks = self._split_text(node_text,chunk_size=chunk_tokens_size)
                        chunks = [cur_ancestors_text_placeholder + chunk for chunk in chunks]

                        _chunks = []
                        for chunk in chunks:
                            assert self.tokens_len_func(chunk) <= max_chunk_size,f"{self.tokens_len_func(text=chunk)},\n{chunk}"
                            _chunks.append(chunk.rstrip('\n'))
                        chunks_saved.extend(_chunks[:-1]) # 可以取多个splits(最后一个不确定)

                        # 处理最后一个chunk
                        text_cached = chunks[-1]


                        # 上方if:   如果当前文本段落tokens超出限制，就处理到只保留最后一个chunk，作为text_cached
                        ###########
                        # 下方else: 没有超出限制，就直接作为text_cached

                    else:
                        if cur_ancestors_text_placeholder not in node_text:
                            text_cached = cur_ancestors_text_placeholder + node_text
                        else:
                            text_cached =  node_text
                    # 可同时处理上面if-else留下来的text_cached： 是否 >=cutoff_ratio_as_chunk
                    tokens_cached = self.tokens_len_func(text=text_cached)
                    if tokens_cached >= max_chunk_size*cutoff_ratio_as_chunk:
                        assert self.tokens_len_func(text=text_cached) <= DEFAULT_CHUNK_SIZE,f"{self.tokens_len_func(text=text_cached)},\n{text_cached}"   
                        chunks_saved.append(text_cached.strip('\n'))
                        text_cached = get_possible_zh_title_for_previous_sibling(cur_node)
                
            if cur_node.type == TreeNodeType.TABLE:
                # 保险起见，先处理text_cached
                tokens_cached = self.tokens_len_func(text=text_cached)
                tokens_bound = self.normal_tokens_chunk_size
                cur_ancestors_text_placeholder = _get_pre_title_nodes_text(cur_node.ancestors[1:])
                if cur_ancestors_text_placeholder not in text_cached:
                    if self.tokens_len_func(text=text_cached) + self.tokens_len_func(text=cur_ancestors_text_placeholder) <= tokens_bound: 
                        text_cached += cur_ancestors_text_placeholder
                        assert self.tokens_len_func(text_cached)<=tokens_bound
                    else:
                        assert self.tokens_len_func(text=text_cached) <= DEFAULT_CHUNK_SIZE,f"{self.tokens_len_func(text=text_cached)},\n{text_cached}"   
                        chunks_saved.append(text_cached.strip('\n'))
                        text_cached = ''   

                if tokens_cached >= max_chunk_size*cutoff_ratio_as_chunk:
                    assert self.tokens_len_func(text=text_cached) <= DEFAULT_CHUNK_SIZE,f"{self.tokens_len_func(text=text_cached)},\n{text_cached}"   
                    chunks_saved.append(text_cached.strip('\n'))
                    text_cached = '' 

                
                vf_string = cur_node.text
                _vf_string_with_prefix = '表格：' + '\r\n' + vf_string

                table_tokens = self.tokens_len_func(text=vf_string)
                _table_tokens_prefix = self.tokens_len_func(text=_vf_string_with_prefix)
                tokens_cached = self.tokens_len_func(text=text_cached)
                if tokens_cached + table_tokens <= tokens_bound:
                    if tokens_cached + _table_tokens_prefix <= tokens_bound:
                        text_cached += _vf_string_with_prefix
                        try:
                            assert self.tokens_len_func(text_cached)<=tokens_bound, f"{self.tokens_len_func(text_cached)}<={tokens_bound}\n{text_cached=}"
                        except:
                            pass
                    elif tokens_cached + table_tokens <= tokens_bound:
                        text_cached += vf_string
                        assert self.tokens_len_func(text_cached)<=tokens_bound
                    else:
                        if self.tokens_len_func(text=text_cached) >= max_chunk_size*cutoff_ratio_as_chunk:
                            assert self.tokens_len_func(text=text_cached) <= DEFAULT_CHUNK_SIZE,f"{self.tokens_len_func(text=text_cached)},\n{text_cached}"   
                            chunks_saved.append(text_cached.strip('\n'))
                            text_cached = '' 

                else:
                    _splits_on_row = vf_string.split('\r\n')
                    splits_on_row = [row+'\r\n' for row in _splits_on_row]

                    column_names = '表格：' + '\r\n' + splits_on_row[0]
                    column_names_tokens = self.tokens_len_func(text=column_names)
                    rows = splits_on_row[1:]
                    
                    if tokens_cached + column_names_tokens > tokens_bound:
                        assert self.tokens_len_func(text=text_cached) <= DEFAULT_CHUNK_SIZE,f"{self.tokens_len_func(text=text_cached)},\n{text_cached}"   
                        chunks_saved.append(text_cached.strip('\n'))
                        text_cached = ''
                    else:
                        text_cached += column_names
                        assert self.tokens_len_func(text_cached)<=tokens_bound
                    for row in rows:
                        if self.tokens_len_func(text=text_cached)  + self.tokens_len_func(text=row) <= tokens_bound:
                             text_cached += row
                             assert self.tokens_len_func(text_cached)<=tokens_bound
                        else:
                            assert self.tokens_len_func(text=text_cached) <= DEFAULT_CHUNK_SIZE,f"{self.tokens_len_func(text=text_cached)},\n{text_cached}"   
                            chunks_saved.append(text_cached.strip('\n'))
                            # cur_title_node,pre_title_node,cur_ancestors_text_placeholder,pre_ancestors_text_placeholder = get_pre_title_nodes_text(cur_node,cur_title_node=cur_title_node,pre_title_node=pre_title_node,cur_ancestors_text_placeholder=cur_ancestors_text_placeholder,pre_ancestors_text_placeholder=pre_ancestors_text_placeholder)
                            text_cached = cur_ancestors_text_placeholder + column_names + row
                            assert self.tokens_len_func(text_cached)<=tokens_bound
            # 如果循环已经结束，需保证最后的text_cached也要读入
            if cur_node == last_nodes:
                if len(text_cached.strip('\n'))>0:
                    # 先看看text_cached能否合并到最后的一个chunks_saved中
                    if chunks_saved:#可能有些短文件，一个只有一个块
                        if self.tokens_len_func(chunks_saved[-1]) + self.tokens_len_func(text_cached)<=TOKEN_THRESHOLD:
                            chunks_saved[-1] += text_cached
                    else:
                        chunks_saved.append(text_cached.strip('\n'))
        
        file_path_docx = lm_base_node.metadata.get("source",None) or lm_base_node.metadata.get("original_source_jq",None)
        if not file_path_docx:
            logger.error(f'lm_base_node的metadata(dict)中不存在key:"source"或"original_source_jq",lm_base_node的内容如下:\n{lm_base_node}')
        
        # 分离路径和文件名（包括扩展名）
        path, full_filename = os.path.split(file_path_docx)
        # 分离文件名和扩展名
        filename, extension = os.path.splitext(full_filename)
        # 重新组合路径和文件名（不包括扩展名）
        result_path = os.path.join(path, filename)
        file_path_docx = result_path
        
        
        
        file_path_txt = file_path_docx+'.txt'
        file_path_txt_preview = file_path_docx+'_preview.txt'

        updated_text = '\n\n'.join(chunks_saved)
        # 切分后的结果保存到文本文件
        # with open(file_path_txt,'w',encoding='utf-8') as f:
        #     f.write(updated_text)
        # 保存供检查、预览的文本文件
        # self.write_chunkes_to_preview_file(chunks_saved, file_path_txt_preview)
        
        # 更新原document node的信息        
        lm_base_node.text = updated_text
        lm_base_node.metadata["file_path_chunks_to_txt_jq"] = file_path_txt
        lm_base_node.metadata["file_path_docx_jq"] = file_path_docx

        _metadata = lm_base_node.metadata
        del _metadata['file_doc_object_jq']
        del _metadata['file_doc_tree_jq']
        del _metadata['df_table_list_jq']


        llama_index_nodes = [TextNode(text=chunk,metadata = _metadata ,excluded_embed_metadata_keys=lm_base_node.excluded_embed_metadata_keys,excluded_llm_metadata_keys=lm_base_node.excluded_llm_metadata_keys) for chunk in chunks_saved]

        return llama_index_nodes


        # return chunks_saved

    def _parse_node_on_text(self, node: BaseNode, cutoff_ratio_as_chunk=0.8,get_to_first_title_directly=False) -> List[BaseNode]:
        splitter = self.cr_text_splitter
        if node.metadata.get("file_extension","") == '.py':
            from langchain_text_splitters import Language
            splitter = self.cr_text_splitter.from_language(language=Language.PYTHON,tokenizer=self.cr_text_splitter.tokenizer_wrapper.tokenizer)
        text = node.text        
        chunks = splitter.split_text(text)

        _metadata = node.metadata
        # 更新原document node的信息        
        # 因为不是doc_tree，所以不存在下列键值
        # del _metadata['file_doc_object_jq']
        # del _metadata['file_doc_tree_jq']
        # del _metadata['df_table_list_jq']

        llama_index_nodes = [TextNode(text=chunk,metadata = _metadata ,excluded_embed_metadata_keys=node.excluded_embed_metadata_keys,excluded_llm_metadata_keys=node.excluded_llm_metadata_keys) for chunk in chunks]
        return llama_index_nodes    


    def _parse_file_into_sub_nodes(self, lm_base_node: BaseNode, doc_tree: AnytreeNode, sub_nodes_chunk_size=8192, cutoff_ratio_as_chunk=0.8,get_to_first_title_directly=True)-> List[AnytreeNode]:
        # node_levels_list= [[node.name for node in children] for children in LevelOrderGroupIter(doc_tree)]
        splitted_nodes = []
        big_leaf_nodes = []
        small_nodes_can_be_composed = []
        last_node = list(doc_tree.descendants)[-1]
        min_sub_nodes_chunk_size = sub_nodes_chunk_size*cutoff_ratio_as_chunk
        # min_sub_nodes_chunk_size = 512
        while doc_tree.height>1:
            outer_loop = True 
            node_levels_list= [[node for node in children] for children in LevelOrderGroupIter(doc_tree)]
            for i in range(len(node_levels_list)):
                node_splits_composed_list_in_the_same_level = [] ## 同一级别的可组合节点列表
                continuous_nodes_list_in_the_same_level = []
                tokens_of_continuous_nodes_list_in_the_same_level = 0
                for j in range(len(node_levels_list[i])):
                    idx = (i)*10+j+1
                    node = node_levels_list[i][j]
                    if node.is_root:
                        text_list = [descendant.text for descendant in node.descendants]
                    else:
                        text_list = [node.text] + [descendant.text for descendant in node.descendants]
                    text = "\n".join(text_list)
                    text_tokens = self.tokens_len_func(text)
                    fill_in_size = min_sub_nodes_chunk_size <= text_tokens <= sub_nodes_chunk_size
                    if not hasattr(node,'idx'):
                        node.idx = idx
                    if not hasattr(node,'tokens'):    
                        node.tokens = text_tokens
                    _type = 'Leaf' if  node.is_leaf else 'No_Leaf'       
                    
                    # 单独的文本叶子节点chunk_size已经超出，所以必须分割
                    # 如果是非叶子节点，暂时不管
                    if node.is_root:
                        if text_tokens <= sub_nodes_chunk_size:
                            splitted_nodes.append(list(node.children))
                            _text = node.name + '_' + '_'.join([n.name for n in node.descendants])
                            print(f"==Root Node Added==:text_tokens={text_tokens}, {_text[:20]}")
                            return splitted_nodes
                        
                    if text_tokens > sub_nodes_chunk_size:
                        if node.is_leaf:
                            node.parent=None
                            big_leaf_nodes.append(node)
                            outer_loop = False
                            print(f"Big Leaf Node Added: {node.name}, text_tokens={text_tokens}")

                    elif fill_in_size:
                        if tokens_of_continuous_nodes_list_in_the_same_level>0:
                            assert len(continuous_nodes_list_in_the_same_level) > 0, f'continuous_nodes_list_in_the_same_level不能为空！'
                            for _node in continuous_nodes_list_in_the_same_level:
                                _node.parent=None
                            splitted_nodes.append(continuous_nodes_list_in_the_same_level)
                            _text = '_'.join([n.name for n in continuous_nodes_list_in_the_same_level])                                      
                            print(f"==Before Fitted==N({len(continuous_nodes_list_in_the_same_level)}) Continuous Node Added:continuous text_tokens={tokens_of_continuous_nodes_list_in_the_same_level}, {_text[:20]}")
                            continuous_nodes_list_in_the_same_level = []
                            tokens_of_continuous_nodes_list_in_the_same_level = 0

                        # node_splits_composed_list_in_the_same_level.append(continuous_nodes_list_in_the_same_level)
                        # node_splits_composed_list_in_the_same_level.append(node)
                        node.parent=None
                        splitted_nodes.append(node)
                        print(f"Fitted Node Added: text_tokens={text_tokens},{node.name } ")

                        outer_loop = False
                    else:
                        if text_tokens <= sub_nodes_chunk_size - tokens_of_continuous_nodes_list_in_the_same_level:
                            continuous_nodes_list_in_the_same_level.append(node)
                            tokens_of_continuous_nodes_list_in_the_same_level += text_tokens
                        else:
                            for node in continuous_nodes_list_in_the_same_level:
                                node.parent=None

                            splitted_nodes.append(continuous_nodes_list_in_the_same_level)
                            _text = '_'.join([n.name for n in continuous_nodes_list_in_the_same_level]) 
                            print(f"==Chunk Size Arrived==N({len(continuous_nodes_list_in_the_same_level)}) Continuous Node Added: continuous text_tokens={tokens_of_continuous_nodes_list_in_the_same_level},{_text[:20]}")
                            
                            continuous_nodes_list_in_the_same_level = []
                            tokens_of_continuous_nodes_list_in_the_same_level = 0
                            

                            outer_loop = False

                if len(continuous_nodes_list_in_the_same_level)>0:
                    for node in continuous_nodes_list_in_the_same_level:
                        node.parent=None
                    _text = '_'.join([n.name for n in continuous_nodes_list_in_the_same_level]) 
                    print(f"==The Level({i},{j}) Finished==N({len(continuous_nodes_list_in_the_same_level)}) Continuous Node Added: continuous text_tokens={tokens_of_continuous_nodes_list_in_the_same_level},{_text[:20]}")
                    splitted_nodes.append(continuous_nodes_list_in_the_same_level)
                    continuous_nodes_list_in_the_same_level = []
                    tokens_of_continuous_nodes_list_in_the_same_level = 0
                    outer_loop = False             

                if not outer_loop:
                    break # 根据标记变量判断是否跳出外层循环
                    # node_levels_list= [[node for node in children] for children in LevelOrderGroupIter(doc_tree)]
        return splitted_nodes
    
    def _parse_node(self, node: BaseNode, sub_nodes_chunk_size=8192,cutoff_ratio_as_chunk=0.8,get_to_first_title_directly=False) -> List[BaseNode]:
        # return self._parse_node_on_text(node) #为了方便跳到_parse_node_on_text方法进行测试
        doc_tree = get_doc_tree_from_document(node)
        if doc_tree:
            llama_index_nodes = self._parse_node_on_tree(node, doc_tree, cutoff_ratio_as_chunk,get_to_first_title_directly)       
            return llama_index_nodes
        else:
            return self._parse_node_on_text(node)
        

    def _parse_nodes(self, nodes: Sequence[BaseNode], show_progress: bool = True, **kwargs: Any) -> List[BaseNode]:
        all_doctree_splits: List[BaseNode] = []
        for node in nodes:
            splitted_nodes = self._parse_node(node)
            all_doctree_splits = all_doctree_splits + splitted_nodes
        return all_doctree_splits


    def split_text_metadata_aware(self, text: str, metadata_str: str) -> List[str]:
        """Split text into chunks, reserving space required for metadata str."""
        
        metadata_len = self.cr_text_splitter._tokenizer.tokens_len(metadata_str) + DEFAULT_METADATA_FORMAT_LEN
        effective_chunk_size = self.normal_tokens_chunk_size - metadata_len
        # logger.info(effective_chunk_size)
        if effective_chunk_size <= 0:
            raise ValueError(
                f"Metadata length ({metadata_len}) is >= normal_tokens_chunk_size "
                f"({self.normal_tokens_chunk_size}). Consider increasing the chunk size or "
                "decreasing the size of your metadata to avoid this."
            )
        elif effective_chunk_size < 50:
            logger.warning(
                f"Metadata length ({metadata_len}) is close to chunk size "
                f"({self.chunk_size}). Resulting chunks are less than 50 tokens. "
                "Consider increasing the chunk size or decreasing the size of "
                "your metadata to avoid this."
            )

        return self._split_text(text, chunk_size=effective_chunk_size)

    def split_text(self, text: str) -> List[str]:
        """Split text into chunks."""
        return self._split_text(text, chunk_size=self.normal_tokens_chunk_size)
    
    def _split_text(self, text: str, chunk_size: int) -> List[str]:
        """Split text into chunks up to chunk_size."""
        if text == "":
            return [text]

        with self.callback_manager.event(
            CBEventType.CHUNKING, payload={EventPayload.CHUNKS: [text]}
        ) as event:
        # 注意要把chunk_size参数带进去，还同时要更新overlap参数
            orginal_chunk_size = self.cr_text_splitter._chunk_size
            if chunk_size != orginal_chunk_size:
                orginal_chunk_overlap = self.cr_text_splitter._chunk_overlap            
                tmp_overlap = math.floor((chunk_size/orginal_chunk_size)*orginal_chunk_overlap)
                self.cr_text_splitter._chunk_size = chunk_size
                self.cr_text_splitter._chunk_overlap = tmp_overlap

            chunks = self.cr_text_splitter.split_text(text)
            
            if chunk_size != orginal_chunk_size:
                self.cr_text_splitter._chunk_size = orginal_chunk_size
                self.cr_text_splitter._chunk_overlap = orginal_chunk_overlap
            
            event.on_end(payload={EventPayload.CHUNKS: chunks})

        return chunks

def chain_qa_fun(query,retriever,llm,input_files=[]):
    from langchain.chains import RetrievalQA
    chain = RetrievalQA.from_chain_type(llm,retriever=retriever,return_source_documents=True, chain_type="stuff")
    print(f'   -----------询问：{query}-------------')
    # query = prompt + query
    r = chain.invoke({"query": query})
    
    # print(r['query'])
    hits = r['source_documents']
    print('\n\n')
    print('   -----------检索结果-------------')
    print(f'共检索到{len(hits)}篇文档：')
    for i,h in enumerate(hits):
        # print(f'文档片段[{i+1}](relevance_score:{h.metadata["relevance_score"]:.3f}):\n{h.page_content}')
        print(f'【{h.metadata.get("file_name",None) or h.metadata.get("source",None)}】文档片段[{i+1}](relevance_score:{h.metadata["relevance_score"]:.3f})')
        if input_files:
            if h.metadata["source"] not in input_files:
                logger.warning(f"检索出的文档片段不在指定文件范围内!限定的文件范围:\n{input_files}")
    print('   -----------最终回答-------------') 
    answer = r['result']    
    return answer,hits

if __name__ == "__main__":
    from langchain import schema
    from langchain.retrievers import EnsembleRetriever
    from langchain_community.retrievers import BM25Retriever as LC_BM25Retriever
    from langchain.retrievers import ContextualCompressionRetriever
    from langchain.chains import RetrievalQA
    from jqcode.jq_splitters.backend_splitter_utils.jq_sentence_transformers_tokentextsplitter import SentenceTransformersTokenTextSplitter
    from jqcode.jq_agent.c0_init_env_models import env_models_instance
    from jqcode.jq_readers.jqkj_readers import JqkjSimpleDirectoryReader      
    from llama_index.core.indices.vector_store.retrievers.retriever import VectorIndexRetriever
    from llama_index.core.tools import RetrieverTool
    from llama_index.core.postprocessor import SentenceTransformerRerank
    from llama_index.core import QueryBundle
    from llama_index.core.retrievers  import RouterRetriever
    
    from llama_index.retrievers.bm25 import BM25Retriever as LM_BM25Retriever

    from jqcode.jq_agent.tools.jq_retriever import get_retriever

    
    top_n = 4
    input_file_dir = fr'/data/projects/JqChat/jqcode/jq_readers/.testinputdocs_debug'
    input_file_dir = fr'/data/projects/JqChatV2/JqChat/jqcode/jq_readers/.test_files/.testinputdocs'
    
    input_files = [fr'/data/projects/JqChatV2/JqChat/jqcode/jq_readers/.test_files/.testinputdocs/A方案.docx'] 
    # input_files += [fr'/data/projects/JqChatV2/JqChat/jqcode/jq_readers/.test_files/.testinputdocs/InstallationGuide.docx']
    input_files += [fr'/data/projects/JqChatV2/JqChat/jqcode/jq_readers/.test_files/.testinputdocs/PPQA000_质量保证过程.doc'] 
    input_files += [fr'/data/projects/JqChatV2/JqChat/jqcode/jq_readers/.test_files/.testinputdocs/厦门市智慧民政一体化平台项目建设方案 V3.6.docx'] 
    # input_files = [fr'/data/projects/JqChatV2/JqChat/jqcode/jq_readers/.test_files/.testinputdocs/PPQA000_质量保证过程.doc']
    # input_files = [fr'/data/projects/JqChatV2/JqChat/jqcode/jq_readers/.test_files/.testinputdocs_debug/test_zh.docx']

    # 针对以下文件中的表格提问
    # input_files += [fr"/data/projects/JqChatV2/JqChat/jqcode/jq_readers/.test_files/.testinputdocs/AAMIS_项目总体计划_120925.doc"]
    q = "安徽省食品药品监督管理局行政审批系统项目总体计划的版本号是多少，批准人是谁？"
    query0 = "晶奇公司的应急技术服务电话？"
    query1 = "晶奇公司在哪一年获得ISO9001国际质量体系认证？"
    query2 = "医院信息系统中基础维护系统的功能？"
    query3 = "请对《国务院办公厅关于全面推开县级公立医院综合改革的实施意见》（国办发〔2017〕32号）的内容进行归纳总结"
    query4 = "病案管理系统的功能或作用是什么？"
    query5 = '系统支持自动生成计算项目，判定结果高低状态并标示吗？'
    query6 = 'ID卡是什么？'
    query7 = 'what a user could do With Nsight Systems？'
    query8 = 'How many benchmarks are choosed for testing the overall performance？具体的benchmarks是什么？'
    query9 = '厦门市智慧民政一体化的建设内容包括哪些？'

    qs = [q,query0,query1,query2,query3,query4,query5,query6,query7,query8,query9]
    # qs = [query7]


    
   


    
    llm = env_models_instance.chat_model
    index_name='zjk_jqesclient_test'
    compression_retriever = get_retriever(index_name=index_name,chat_on_docs_list=None,add_docs_list_to_kb=True)
    # compression_retriever = get_retriever(index_name=index_name)
    # chain_type:stuff、refine、map_reduce 和 map_rerank
    qa_chain_RetrievalQA = RetrievalQA.from_chain_type(llm,retriever=compression_retriever,return_source_documents=True, chain_type="stuff")

    from langchain.chains.question_answering.stuff_prompt import system_template
    logger.info(f"USING SYSTEM PROMPY from /root/miniconda3/envs/test/lib/python3.9/site-packages/langchain/chains/question_answering/stuff_prompt.py")
    logger.info(f"USING ‘REVICED’ SYSTEM PROMPY:\n{system_template}")


    def chain_qa_fun(query,retriever=compression_retriever,limited_to_files=None):
        chain = RetrievalQA.from_chain_type(llm,retriever=retriever,return_source_documents=True, chain_type="stuff")
        print(f'   -----------询问：{query}-------------')
        # query = prompt + query
        r = chain.invoke({"query": query})
        
        # print(r['query'])
        hits = r['source_documents']
        print('   -----------检索结果-------------')
        print(f'共检索到{len(hits)}篇文档：')
        for i,h in enumerate(hits):
            # print(f'文档片段[{i+1}](relevance_score:{h.metadata["relevance_score"]:.3f}):\n{h.page_content}')
            print(f'【{h.metadata.get("file_name",None) or h.metadata.get("source",None)}】文档片段[{i+1}](relevance_score:{h.metadata["relevance_score"]:.3f})')
            if limited_to_files:
                if h.metadata["source"] not in limited_to_files:
                    logger.warning(f"检索出的文档片段不在指定文件范围内!限定的文件范围:\n{limited_to_files}")
        print('   -----------最终回答-------------')
        print(r['result'])
        print('\n\n')
        return hits


    # qs = [query9]
    for q in qs:
        chain_qa_fun(q,limited_to_files=None)