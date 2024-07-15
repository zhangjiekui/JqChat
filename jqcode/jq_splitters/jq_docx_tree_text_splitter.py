import copy,math
import pandas as pd
from io import StringIO
from typing import Any, Callable, List, Optional, Sequence,Union
from anytree import Node as AnytreeNode
from anytree import RenderTree, AsciiStyle, PreOrderIter
from anytree.exporter import JsonExporter
from anytree.importer import JsonImporter
from anytree import LevelOrderGroupIter

from llama_index.core.callbacks.base import CallbackManager
from llama_index.core.schema import BaseNode, TextNode,Document, MetadataMode
from llama_index.core.bridge.pydantic import Field
from llama_index.core.callbacks.schema import CBEventType, EventPayload
from llama_index.core.utils import get_tqdm_iterable
from llama_index.core.node_parser.node_utils import IdFuncCallable, build_nodes_from_splits
from llama_index.core.node_parser.interface import MetadataAwareTextSplitter

from langchain import schema



from jqcode.jq_readers.jqkj_readers import JqkjSimpleDirectoryReader
from jqcode.jq_readers.backend_reader_utils.jqkj_doc_tree_utils import jieba_pre_process,TreeNodeType,get_doc_tree_from_document
from jqcode.jq_splitters.backend_splitter_utils.jq_chinese_recursive_text_splitter import ChineseRecursiveTextSplitter
from jqcode.jq_utils.logger import jqkj_logger

logger = jqkj_logger(__file__).get_logger()

try:
    from llama_index.core.node_parser.node_utils import default_id_func    
except:
    default_id_func = None

DEFAULT_CHUNK_SIZE = 512
DEFAULT_CHUNK_OVERLAP = 0.2
# NOTE: this is the number of tokens reserved for special tokens(BOS,EOS) and metadata formatting
DEFAULT_MODEL_RESERVED_TOKENS_SIZE = 12
DEFAULT_METADATA_FORMAT_LEN = 2

anytree_json_exporter = JsonExporter()
anytree_json_importer = JsonImporter()


def _get_pre_title_nodes_text(pre_title_nodes,normal_text:bool=False):
    if len(pre_title_nodes) > 0:
        pre_title_nodes_text = [pre_title_node.text for pre_title_node in pre_title_nodes]
        if normal_text:
            text_cached = '\n'.join(pre_title_nodes_text) + '\n'
        else:
            text_cached = '|'.join(pre_title_nodes_text)
            text_cached = f'<toc标题目录：{text_cached}/>'
            # <table column_names={col_text}/>
    else:
        text_cached = ''
    return text_cached

class JqkjDocTreeTokenTextSplitter(MetadataAwareTextSplitter):

    _default_normal_tokens_chunk_size = DEFAULT_CHUNK_SIZE - DEFAULT_MODEL_RESERVED_TOKENS_SIZE

    model_reserved_tokens_size: int = Field(default=DEFAULT_MODEL_RESERVED_TOKENS_SIZE , description="为嵌入模型预留的tokens(如BOS、EOS)数量。")    
    normal_tokens_chunk_size: int = Field(default= _default_normal_tokens_chunk_size, description="减去model_reserved_tokens_size后，能够喂入嵌入模型的正常tokens数量")
    # 注意：下面的chunk_size是已经去掉保留tokes后的，真正能够喂入模型的正常tokens数量
    chunk_size: int = Field(default=normal_tokens_chunk_size,description="每个文本块chunk的tokens数量大小", gt=0, )
    chunk_overlap: Union[int,float] = Field(default=DEFAULT_CHUNK_OVERLAP,description="两个文本块chunk可以重叠的数量大小或比例",gte=0,)
    cr_text_splitter:ChineseRecursiveTextSplitter = Field(default=ChineseRecursiveTextSplitter(_default_normal_tokens_chunk_size,DEFAULT_CHUNK_OVERLAP),description="中英文文本分割器")
    tokens_len_func: Callable = Field(default=None,description="获取tokens数量")
 
    class Config:
        arbitrary_types_allowed = True
    
    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: Union[int,float] = DEFAULT_CHUNK_OVERLAP,
        model_reserved_tokens_size: int = DEFAULT_MODEL_RESERVED_TOKENS_SIZE,    
        callback_manager: Optional[CallbackManager] = None,
        include_metadata: bool = True,
        include_prev_next_rel: bool = True,
        id_func: Optional[Callable[[int, Document], str]] = None,
    ):
        """Initialize with parameters."""
        _normal_tokens_chunk_size = chunk_size - model_reserved_tokens_size
        cr_text_splitter = ChineseRecursiveTextSplitter(_normal_tokens_chunk_size,chunk_overlap)
        chunk_overlap = cr_text_splitter._chunk_overlap
        

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
        return metadata_str


    @classmethod
    def from_defaults(
        cls,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: Union[int,float] = DEFAULT_CHUNK_OVERLAP,
        model_reserved_tokens_size: int = DEFAULT_MODEL_RESERVED_TOKENS_SIZE,
        callback_manager: Optional[CallbackManager] = None,
        include_metadata: bool = True,
        include_prev_next_rel: bool = True,
        id_func: Optional[Callable[[int, Document], str]] = None,
    ) -> "JqkjDocTreeTokenTextSplitter":
        """Initialize with default parameters."""
        callback_manager = callback_manager or CallbackManager([])
        return cls(
            chunk_size = chunk_size,
            chunk_overlap = chunk_overlap,
            model_reserved_tokens_size = model_reserved_tokens_size, 
            callback_manager = callback_manager,
            include_metadata = include_metadata,
            include_prev_next_rel = include_prev_next_rel,
            id_func = id_func or default_id_func
            )

    @classmethod
    def class_name(cls) -> str:
        return "JqkjDocTreeTokenTextSplitter"
    
    def write_chunkes_to_file(self, text_splits: List[str], save_path_txt: str, metadata_str_tokens_num:int):
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
            f.write(f'##共切分为{len(text_splits)}个Chunks,最大tokens限制为{DEFAULT_CHUNK_SIZE- metadata_str_tokens_num}，tokens利用率最大为{max_percent_str}，最小为{min_percent_str}。##')
            # logger.info(f'共切分为{len(text_splits)}个Chunks,最大tokens限制为{DEFAULT_CHUNK_SIZE- metadata_str_tokens_num}，tokens利用率最大为{max_percent_str}，最小为{min_percent_str}。')
            
            for i,s in enumerate(text_splits):
                assert s.startswith('<toc'),f'切分结果必须以"<toc"开头，当前结果为{s}'
                tokens_num = self.tokens_len_func(text=s)
                percent = tokens_num/self.chunk_size
                percent_str = f'{percent*100:.1f}%'
                error = ''

                if tokens_num/(DEFAULT_CHUNK_SIZE - metadata_str_tokens_num) > 1.0:
                    error = f'**tokens利用率{percent_str}超出100%是不对的！'
                    logger.warning(f'\n{error}本Chunk共{tokens_num}个tokens,tokens限额为{DEFAULT_CHUNK_SIZE - metadata_str_tokens_num},以下是该chunk内容:')
                    logger.warning(f'{s}')
                # logger.info(f'\n\n==S{i}：{error} 本Chunk共{tokens_num}个tokens，{len(s)}个字符，tokens利用率{percent_str}\n')
                f.write(f'\n\n==S{i+1}：{error}本Chunk共{tokens_num}个tokens,{len(s)}个字符，tokens利用率{percent_str},tokens限额为{DEFAULT_CHUNK_SIZE- metadata_str_tokens_num}\n')
                f.write(f'{s}\n\n')
        logger.info(f'......切分结果已保存到{save_path_txt}')

    def _parse_node_on_tree(self, lm_base_node: BaseNode, doc_tree: AnytreeNode, cutoff_ratio_as_chunk=0.8,get_to_first_title_directly=True) -> List[BaseNode]:

        chunks_saved = [] #存储“已经处理好的Chunks”
        text_cached =''   # 累积起来的待分割的文本
        cur_text = ''     # 当前读入的文本（可能包含Ancestors节点的标题目录文本）
        node_text = ''    # 当前文本节点的文本

        tokens_cached = 0

        max_chunk_size = self.normal_tokens_chunk_size #tokes限额
        tokens_cutoff = self.normal_tokens_chunk_size  #tokes余额，会变动

        metadata_str = self._get_metadata_str(lm_base_node)
        metadata_str_tokens_num = self.tokens_len_func(metadata_str)  

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
        text_nodes = [node for node in all_tree_nodes if node.type == TreeNodeType.TEXT]
        last_text_nodes = text_nodes[-1]

        for i,cur_node in enumerate(all_tree_nodes):
            if get_to_first_title_directly:
                try:
                    if cur_node.type == TreeNodeType.TEXT and 'Heading' in cur_node.style:
                        get_to_first_title_directly = False
                    else:
                        continue
                except :
                    continue

            #  暂时只处理文本类型
            if cur_node.type == TreeNodeType.TEXT:
                # 跳过目录(toc)的内容，因为对于RAG任务没什么作用，反而可能会在检索阶段存在干扰
                # 与上面的get_to_first_title_directly可能会重复，
                # 上面的get_to_first_title_directly处理的是即使没有明确的toc标识信息的情况（如pdf转过来的docx）
                # 这里处理的是word中生成的toc，含有 style == 'toc'信息
                # 所以仍然保留着
                if cur_node.text.replace(' ','').lower() in ['目录','toc','tableofcontents','tableofcontent']:
                    continue
                if 'toc' in cur_node.style:
                    continue

                ## 跳过目录标题文本（Heading）的内容 
                if 'Heading' in cur_node.style:
                    pre_title_node = cur_node
                    node_text = ''
                    continue
                
                if cur_node.is_leaf and cur_node.parent.type in [TreeNodeType.TEXT,TreeNodeType.DOCUMENT]:
                    cur_title_node = cur_node.parent
                    node_text = cur_node.text
                    if cur_ancestors_text_placeholder == '': # 只有第一次会取值
                        cur_ancestors_text_placeholder = _get_pre_title_nodes_text(cur_node.ancestors[1:]) #[1:] 去除文件名根节点                 
                    if cur_node == cur_title_node.children[0] or cur_title_node != pre_title_node :     # 然后就只有在第一个叶子文本节点，或是父节点发生变化时再取值
                        pre_title_node = cur_title_node
                        cur_ancestors_text_placeholder = _get_pre_title_nodes_text(cur_node.ancestors[1:]) #[1:] 去除文件名根节点
                
                # 如果没有（文本子节点）Normal Text，跳出本次节点循环，不执行后面的代码，进入下一个节点
                if len(node_text) == 0: 
                    continue

                # if '根据国家标准《信息系统安全等级保护定级指南》（GB/T22240-2008）' in node_text:
                # if '项目建设单位：厦门市民政局' in node_text:
                #     logger.debug('for debug')



                ancestors_text_placeholder = '' if pre_ancestors_text_placeholder==cur_ancestors_text_placeholder else cur_ancestors_text_placeholder

                cur_text = ancestors_text_placeholder + node_text + '\n'
                pre_ancestors_text_placeholder=cur_ancestors_text_placeholder
                
                if len(ancestors_text_placeholder) == 0 and len(text_cached) == 0: #保证每个split开头都有 标题目录 信息
                    text_cached = _get_pre_title_nodes_text(cur_node.ancestors[1:]) 
                
                # 统一开始tokens计数
                tokens_cached = self.tokens_len_func(text=text_cached)
                tokens_cutoff = max_chunk_size - tokens_cached - metadata_str_tokens_num
                assert  tokens_cutoff >= 0, f"tokens_cutoff must >= 0。但下文的长度是{tokens_cached}:\n {text_cached}"              
                
                cur_text_tokens_num = self.tokens_len_func(text=cur_text)
                tokens_ancestors = self.tokens_len_func(text=ancestors_text_placeholder)
                
                if cur_text_tokens_num <= tokens_cutoff - metadata_str_tokens_num:
                    text_cached += cur_text
                    tokens_cutoff = tokens_cutoff - cur_text_tokens_num - metadata_str_tokens_num
                    assert  tokens_cutoff >= 0, "tokens_cutoff must >= 0"
                
                else: # 当前文本的tokens数已超出了tokens_cutoff剩余限额
                    assert tokens_cached <= max_chunk_size - metadata_str_tokens_num                     
                    # todo: 暂时只考虑文本节点

                    #======  先处理text_cached，（1）要么直接作为chunk，（2）要么对当前文本进行切分，补齐切分到text_cached，一起作为一个chunk
                    
                    #以下是这两种处理情形                    
                    ###  （1）  >=cutoff_ratio_as_chunk 【累积文本text_cached】直接作为一个Chunk                                        
                    if tokens_cached >= max_chunk_size*cutoff_ratio_as_chunk: 
                        # 如果【累积文本text_cached】的tokens已经够多，则直接作为一个chunk
                        chunks_saved.append(text_cached.rstrip('\n'))
                        text_cached=''

                    ###  （2）  <cutoff_ratio_as_chunk  【累积文本text_cached】与【当前文本node_text的切分】拼接    
                    else:
                        # 【累积文本text_cached】与【当前文本node_text】拼接
                        # 正常分割，但只保留分割后的第一个chunk，用以补齐text_cached形成一个完整的Chunk
                        # 要特别注意chunk_size的控制，详见_split_text方法中对chunk_size和hunk_overlap的处理
                        chunks = self._split_text(node_text,chunk_size=max_chunk_size - tokens_cached - tokens_ancestors- metadata_str_tokens_num)
                        split0 = text_cached + ancestors_text_placeholder + chunks[0]

                        if self.tokens_len_func(split0)>DEFAULT_CHUNK_SIZE - metadata_str_tokens_num:
                            logger.warning(f"\nChunk tokens数量{self.tokens_len_func(split0)}，超出了限制{DEFAULT_CHUNK_SIZE - metadata_str_tokens_num},该Chunk内容为：")
                            logger.warning(f"{split0}")
                        chunks_saved.append(split0.rstrip('\n'))
                        text_cached=''
                    # ====== text_cached已经处理完毕
                        
                    #################################################
                    
                    # 着手处理当前节点， 开始新的切片
                        # 接着将当前文本 node_text 还作为一个整体来处理，因为可能是一个很长的段落文本，本身足以构成一个或多个split(s)
                        # 增加了代码校验text_cached='',tokens_cached = 0
                        # 这时text_cached=''，所以可以取多个splits
                    assert text_cached==''
                    tokens_cached = 0
                    tokens_cutoff = self.normal_tokens_chunk_size - metadata_str_tokens_num

                    tokens_node_text = self.tokens_len_func(text=node_text)
                    cur_text_tokens_num = self.tokens_len_func(text=cur_text)

                    # 因为是要对当前文本进行分割，所以前面必须要有cur_ancestors_text_placeholder部分
                    cur_ancestors_text_placeholder = _get_pre_title_nodes_text(cur_node.ancestors[1:])
                    tokens_ancestors = self.tokens_len_func(text=cur_ancestors_text_placeholder)

                    if  tokens_node_text > max_chunk_size - metadata_str_tokens_num - tokens_cached -tokens_ancestors:
                        # 只分割当前文本 node_text
                        # 把ancestors_text_placeholder 和 分割出来的部分拼接在一起， 形成一个或多个完整的split
                        chunk_tokens_size = max_chunk_size - tokens_cached - tokens_ancestors - metadata_str_tokens_num
                        chunks = self._split_text(node_text,chunk_size=chunk_tokens_size)
                        chunks = [cur_ancestors_text_placeholder + chunk for chunk in chunks]

                        _chunks = []
                        for chunk in chunks:
                            assert self.tokens_len_func(chunk) <= max_chunk_size - metadata_str_tokens_num,f"{self.tokens_len_func(text=chunk)},\n{chunk}"
                            _chunks.append(chunk.rstrip('\n'))
                        chunks_saved.extend(_chunks[:-1]) # 这时text_cached=''，所以可以取多个splits(最后一个不确定)

                        # 处理最后一个chunk
                        text_cached = chunks[-1]


                        # 上方if:   如果当前文本段落tokens超出限制，就处理到只保留最后一个chunk，作为text_cached
                        ###########
                        # 下方else: 没有超出限制，就直接作为text_cached

                    else:
                        # text_cached = _get_pre_title_nodes_text(cur_node.ancestors[1:]) + node_text  #[1:] 去除文件名根节点 + node_text
                        text_cached = cur_ancestors_text_placeholder + node_text 
                    # 可同时处理上面if-else留下来的text_cached： 是否 >=cutoff_ratio_as_chunk
                    tokens_cached = self.tokens_len_func(text=text_cached)
                    if tokens_cached >= max_chunk_size*cutoff_ratio_as_chunk - metadata_str_tokens_num:
                        assert self.tokens_len_func(text=text_cached) <= DEFAULT_CHUNK_SIZE - metadata_str_tokens_num,f"{self.tokens_len_func(text=text_cached)},\n{text_cached}"   
                        chunks_saved.append(text_cached.strip('\n'))
                        text_cached = ''
                
                # 如果循环已经结束，需保证最后的text_cached也要读入
                if cur_node == last_text_nodes:
                    if len(text_cached.strip('\n'))>0:
                        chunks_saved.append(text_cached.strip('\n'))


            if cur_node.type == TreeNodeType.TABLE:
                vf_string = cur_node.df_table_jq
                vf =  StringIO()
                vf.write(vf_string)
                vf.seek(0)
                df = pd.read_csv(vf)

        file_path_docx = lm_base_node.metadata["file_path"]
        file_path_txt = file_path_docx.replace('.docx', '.txt')
        file_path_txt_preview = file_path_docx.replace('.docx', '_preview.txt')

        updated_text = '\n\n'.join(chunks_saved)
        # 切分后的结果保存到文本文件
        with open(file_path_txt,'w',encoding='utf-8') as f:
            f.write(updated_text)
        # 保存供检查、预览的文本文件
        self.write_chunkes_to_file(chunks_saved, file_path_txt_preview,metadata_str_tokens_num = metadata_str_tokens_num)
        
        # 更新原document node的信息        
        lm_base_node.text = updated_text
        lm_base_node.metadata["file_path"] = file_path_txt
        lm_base_node.metadata["file_path_docx_jq"] = file_path_docx

        llama_index_nodes = [TextNode(text=chunk) for chunk in chunks_saved]           
        return llama_index_nodes


        # return chunks_saved

    def _parse_node_on_text(self, node: BaseNode, cutoff_ratio_as_chunk=0.8,get_to_first_title_directly=True) -> List[BaseNode]:
        text = node.text
        chunks = self.cr_text_splitter.split_text(text)
        # return chunks
        llama_index_nodes = [TextNode(text=chunk) for chunk in chunks]           
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
    
    def _parse_node(self, node: BaseNode, sub_nodes_chunk_size=8192,cutoff_ratio_as_chunk=0.8,get_to_first_title_directly=True) -> List[BaseNode]:

        doc_tree = get_doc_tree_from_document(node)
        # if doc_tree:
        #     sub_doc_tree_nodes = self._parse_file_into_sub_nodes(node, doc_tree, sub_nodes_chunk_size=sub_nodes_chunk_size,
        #                                       cutoff_ratio_as_chunk =cutoff_ratio_as_chunk,
        #                                       get_to_first_title_directly=get_to_first_title_directly)
        #     print('dubug sub_doc_tree_nodes')

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
    
if __name__ == "__main__":
    from langchain.retrievers import EnsembleRetriever
    from langchain_community.retrievers import BM25Retriever as LC_BM25Retriever
    from langchain.retrievers import ContextualCompressionRetriever
    from langchain.chains import RetrievalQA
    from jqcode.jq_agent.c0_init_env_models import get_emb_8k_rerank_model,get_langchain_chat_model
    from jqcode.jq_splitters.backend_splitter_utils.jq_sentence_transformers_tokentextsplitter import SentenceTransformersTokenTextSplitter
    embed_model,embedding_model_8k,reranker = get_emb_8k_rerank_model()
    llm = get_langchain_chat_model()

    st_splitter=SentenceTransformersTokenTextSplitter(emb_model_instance=embed_model,tokens_per_chunk=100,chunk_overlap=0.2)
    cr_text_splitter = st_splitter.chinese_recursive_text_splitter
    doc_tree_spiltter = JqkjDocTreeTokenTextSplitter.from_defaults()
    print(doc_tree_spiltter.class_name())

    top_n = 4
    input_file_dir = fr'/data/projects/JqChat/jqcode/jq_readers/_testinputdocs'

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

    qs = [query0,query1,query2,query3,query4,query5,query6,query7,query8,query9]
    # qs = [query7]

    # llama_index的实现 https://docs.llamaindex.ai/en/stable/examples/retrievers/bm25_retriever.html
    from llama_index.core import StorageContext,VectorStoreIndex,ServiceContext    
    from llama_index.core.indices.vector_store.retrievers.retriever import VectorIndexRetriever
    from llama_index.core.tools import RetrieverTool
    from llama_index.core.postprocessor import SentenceTransformerRerank
    from llama_index.core import QueryBundle
    from llama_index.core.retrievers  import RouterRetriever
    
    from llama_index.retrievers.bm25 import BM25Retriever as LM_BM25Retriever
    # from llama_index.legacy.retrievers import BM25Retriever
    
   


    st_reranker = SentenceTransformerRerank(top_n=top_n, model=reranker.model)
    simple_reader = JqkjSimpleDirectoryReader(input_file_dir,overwrite_existing_converted_files=False,required_exts=['.docx','.pdf'])
    documents = simple_reader.load_data()
    service_context = ServiceContext.from_defaults(llm=llm, embed_model=embed_model,node_parser=doc_tree_spiltter)
    nodes = service_context.node_parser.get_nodes_from_documents(documents)
    # initialize storage context (by default it's in-memory)
    storage_context = StorageContext.from_defaults()
    storage_context.docstore.add_documents(nodes)

    vector_index = VectorStoreIndex(nodes=nodes,storage_context=storage_context,service_context=service_context)
    vector_retriever = VectorIndexRetriever(index=vector_index,similarity_top_k=top_n)
    # We can pass in the index, doctore, or list of nodes to create the retriever
    bm25_retriever  = LM_BM25Retriever.from_defaults(nodes=nodes, similarity_top_k=top_n) 
    retriever_tools = [
        RetrieverTool.from_defaults(retriever=vector_retriever,description="适用于大部分情形,Useful in most cases"),
        RetrieverTool.from_defaults(retriever=bm25_retriever,description="适用于搜索特定信息、事实信息,Useful if searching about specific information")
        ] 

    retriever = RouterRetriever.from_defaults(retriever_tools=retriever_tools,service_context=service_context,select_multi=True)
    retrieved_nodes = retriever.retrieve(query0)
    reranked_nodes = st_reranker.postprocess_nodes(retrieved_nodes, query_bundle=QueryBundle(query0))

    # print(retrieved_nodes)
    # print(reranked_nodes)

    lc_all_text_splits = [i.text for i in nodes]
    lc_documents = [schema.Document(page_content=text_split) for text_split in lc_all_text_splits]
    from langchain_community.vectorstores import FAISS
    vectorstore = FAISS.from_documents(documents=lc_documents, embedding=embed_model)

    
    retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k":top_n})
    bm25_retriever = LC_BM25Retriever.from_texts(lc_all_text_splits,preprocess_func=jieba_pre_process)  
    bm25_retriever.k = top_n

    # 初始化集成检索器  
    ensemble_retriever = EnsembleRetriever(retrievers=[bm25_retriever, retriever], weights=[0.3, 0.7])
    # compressor = BgeRerank(top_n = top_n) 
    compressor = reranker   
    compression_retriever = ContextualCompressionRetriever(base_compressor=compressor, base_retriever=ensemble_retriever)



    # chain_type:stuff、refine、map_reduce 和 map_rerank
    qa_chain_RetrievalQA = RetrievalQA.from_chain_type(llm,retriever=compression_retriever,return_source_documents=True, chain_type="stuff")

    from langchain.chains.question_answering.stuff_prompt import system_template
    logger.info(f"USING SYSTEM PROMPY from /root/miniconda3/envs/test/lib/python3.9/site-packages/langchain/chains/question_answering/stuff_prompt.py")
    logger.info(f"USING ‘REVICED’ SYSTEM PROMPY:\n{system_template}")
    # 下面是智谱Chatglm的提示词
    # 作为一名智能客服，请你记住【】中的知识库内容，并根据知识库内容用简洁和专业的来回答用户问题。如果无法从中得到答案，请说 “根据已知信息无法回答该问题” 或 “没有提供足够的相关信息”，不允许在答案中添加编造成分，答案请使用中文。
            
    # 用户问题：开启静音拍摄后，相机为什么还会有声音？
    # 【若要启用电子快门并消除操作机械快门所导致的噪音和震动，请在照片拍摄菜单中将[静音拍摄]选为[开启]。
    # - 进行静音拍摄时，屏幕中将显示一个图标。
    # - 请注意，无论在自定义设定d5[快门类型]中选择了何种选项，都将使用电子快门。
    # - 释放快门时，屏幕将暂时变暗。这表示已拍摄完一张照片。
    # - 无论在设定菜单的[蜂鸣音选项]中选择了何种设定，照相机完成对焦时或自拍倒计时期间都不会发出蜂鸣音。
    # - 启用静音拍摄将禁用某些功能，包括闪光灯；长时间曝光降噪；闪烁消减；高ISO感光度( Hi 0.3-Hi 1.0 )。
    # - 将[静音拍摄]选为[开启]不会使照相机完全静音。照相机声音仍然可能听到，例如在自动对焦或光圈调整过程中，调整光圈时照相机声音在光圈小于( 即f值高于）f/5.6的情况下最明显。
    # - 您可能会在照片和拍摄显示中看到以下现象：由荧光灯、水银灯或钠汽灯等光源照亮的场景中的闪烁或条带痕迹；与移动相关的失真(移动中的拍摄对象可能会失真，或者当照相机在拍摄期间发生移动时整个画面都可能出现失真)；屏幕中的锯齿状边缘、彩色边纹、莫尔条纹和亮点；在由闪烁标识和其他间歇光源照亮的场景中，或者当拍摄对象被频闪或其他闪光光源暂时照亮时出现的明亮区域或明亮带
    # - 当[静音拍摄]选为[开启]时，连拍模式的每秒幅数会发生改变。
    # - 若在照片拍摄菜单的[减震]中选择了[关闭]以外的选项，按下MENU或按钮时，您可能会听到照相机发出的声音。
    # - 静音拍摄可消除快门的声音，但摄影者仍需尊重拍摄对象的隐私权和肖像权。】

    # 下面是我想的提示词：
    # '你是一个忠实的客服专家，回答问题应尽量简洁，不超过100字，并尽量忠实引用Context和Question中的原文，如果无法回答，就说不知道，不要捏造答案。以下是问题：

    def chain_qa_fun(query,chain=qa_chain_RetrievalQA):
        print(f'   -----------询问：{query}-------------')
        # query = prompt + query
        r = chain({"query": query})
        
        # print(r['query'])
        hits = r['source_documents']
        print('   -----------检索结果-------------')
        print(f'共检索到{len(hits)}篇文档：')
        for i,h in enumerate(hits):
            print(f'Doc{i+1}[](relevance_score:{h.metadata["relevance_score"]:.3f}):\n{h.page_content}')
        print('   -----------最终回答-------------')
        print(r['result'])
        print('\n\n')
        return hits


    # qs = [query9]
    for q in qs:
        chain_qa_fun(q)