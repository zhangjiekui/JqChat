"""Docs parser.

Contains parsers for docx, pdf files.

"""

import time
from pathlib import Path
from os.path import basename,dirname,join
from typing import Dict, List, Optional,Callable,Any
from docx.text.paragraph import Paragraph, Run
from docx.parts.image import ImagePart
from docx.table import _Cell, Table
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.opc.pkgreader import _SerializedRelationships, _SerializedRelationship
from docx.opc.oxml import parse_xml
import pandas as pd
from xml.etree import ElementTree
from io import StringIO
import io
import csv
import anytree
from anytree import Node
from threading import Lock
from docx.document import Document as DocxDocument
from llama_index.core.readers.base import BaseReader
from llama_index.core import Document as LmDocument

import fsspec
from fsspec.implementations.local import AbstractFileSystem

from jqcode.jq_readers.backend_reader_utils.jqkj_mp_simpledirectoryreader_async import SimpleDirectoryReader,default_file_metadata_func,_try_loading_included_file_formats
from jqcode.jq_readers.backend_reader_utils.jqkj_img_to_text import treenodes_img_to_text_in_batch
from jqcode.jq_readers.backend_reader_utils.jqkj_docs_converter import batch_convert_files_to_docxs as convert_file_to_docx
from jqcode.jq_readers.backend_reader_utils.jqkj_doc_tree_utils import find_nearest_parent_but_not_TableOrImageNode,TreeNodeType
from anytree import PreOrderIter
from jqcode.jq_readers.backend_reader_utils.jqkj_doc_tree_utils import compare_with_zip_docx2img,get_paras_in_table
from jqcode.jq_config.general_config import if_log_verbose

from llama_index.readers.file import UnstructuredReader,FlatReader
import asyncio

from jqcode.jq_utils.logger import jqkj_logger
logger = jqkj_logger(__file__).get_logger()
temp_lock = Lock()

file_type_processed_by_jqreader = [".pdf",".doc",".docx",".md",".html",".htm"]


# KeyError: "There is no item named 'word/NULL' in the archive"
# 原因：有两张引用的图像不存在！在 Word 里直接把这两个坏引用删除掉，保存后再用脚本解析就没问题了！
# https://github.com/python-openxml/python-docx/issues/1105#issuecomment-1298075246
def load_from_xml_v2(baseURI, rels_item_xml):
    """
    Return |_SerializedRelationships| instance loaded with the
    relationships contained in *rels_item_xml*. Returns an empty
    collection if *rels_item_xml* is |None|.
    """
    srels = _SerializedRelationships()
    if rels_item_xml is not None:
        rels_elm = parse_xml(rels_item_xml)
        for rel_elm in rels_elm.Relationship_lst:
            if rel_elm.target_ref in ('../NULL', 'NULL'):
                continue
            srels._srels.append(_SerializedRelationship(baseURI, rel_elm))
    return srels
_SerializedRelationships.load_from_xml = load_from_xml_v2

class JqkjDocxReader(BaseReader):
    """Docx parser."""
    def __init__(self,file_path:str=None,save_img_file:bool = False):
        try:
            from docx import Document as DocxDocumentFunc
        except ImportError:
            raise ImportError(
                "python-docx（https://github.com/python-openxml/python-docx） is required to read Microsoft Word files: "
                "`pip install python-docx`"
            )
        self.DocumentFunc = DocxDocumentFunc
        self.orginal_filepath_extra_info = {}
        self.file_path = file_path # 为了兼容chatchat，必须增加的属性
        self.save_img_file = save_img_file
        
    def load(self,file: Path=None, extra_info: Optional[Dict] = None,fs: Optional[AbstractFileSystem] = None) -> List[LmDocument]:
        """Parse docx file."""
        if not file:
            file = self.file_path
        else:
            self.file_path = file
        return self.load_data(file, extra_info)

    def load_data(self, file: Path, extra_info: Optional[Dict] = None,fs: Optional[AbstractFileSystem] = None,aysnc = False) -> List[LmDocument]:
        """
        Parse docx file.   
        1、转换文件为docx
        2、读取docx文件
        3、解析docx文件为anytree
            3.1 识别出图片中的文本
           
        """
        with temp_lock:
            file_path =file if file else self.file_path # 为了兼容chatchat，必须增加的属性
            doc_original = str(file_path)         # 因self.file_path和file_path下面都可能会变，所以先保留原始的到doc_id
            file_path = Path(file_path)        
            
            if file_path.exists():
                self.file_path =  file_path

            # 如果是经过JqkjSimpleDirectoryReader=>JqkjDocxReader，其实已经进行了文件类型转换，并且加入了'original_source_jq'，'source'键值，
            # 这里仅需要处理直接实例化JqkjDocxReader自身的情形，并且不能更新 JqkjSimpleDirectoryReader=>JqkjDocxReader时 已经处理好的'original_source_jq'，'source'键值
                # raise Exception("todo")
                ext = file_path.suffix
                if ext in ['.docx']:
                    self.file_path =  file_path
                    self.orginal_filepath_extra_info = {'original_source_jq':doc_original,'source':doc_original,'original_source_converted_jq':doc_original}
                    # 元数据中增加了文件扩展名
                    self.orginal_filepath_extra_info.update({"file_extention":ext})
                elif ext in file_type_processed_by_jqreader:
                    input_filepaths_exist,input_filepaths_exist_and_replaced_by_docx_if_converted = convert_file_to_docx(file_path,overwrite=False)                
                    # self.file_path此时为转换后的docx文件路径
                    if input_filepaths_exist_and_replaced_by_docx_if_converted:
                        self.file_path =  input_filepaths_exist_and_replaced_by_docx_if_converted[0]
                        doc_original = input_filepaths_exist[0]                
                        self.orginal_filepath_extra_info = {'original_source_jq':doc_original,'source':doc_original,'original_source_converted_jq':str(self.file_path)} #'source'键是为了与chatchat中的reader保持一致的
                        # 元数据中增加了文件扩展名
                        self.orginal_filepath_extra_info.update({"file_extention":ext})
                    else:
                        logger.error(f"{file_path}转换成docx失败！")
                else:
                    logger.error(f"JqkjDocxReader暂只支持{file_type_processed_by_jqreader},无法读取[{ext}]文件")           

            else:
                logger.error(f"文件不存在:{file_path}")

            if self.file_path.exists() and doc_original:
                doc = self.DocumentFunc(self.file_path)           
                # text = "\n".join([paragraph.text for paragraph in doc.paragraphs if len(paragraph.text.strip())>0])
                text = '将从metadata["file_doc_tree_jq"]中获取，并替代这里的文字'
                logger.warning(f"\n#######开始将文档[{self.file_path}]解析为树结构#######")
                doc_tree,df_table_list = self.parse_docx_into_tree(doc,self.file_path)
                texts = [node.text for node in doc_tree.descendants]
                text = "\n".join(texts) #包含了图片识别出和表格转换出来的文本
                
                # 'original_source_jq'(转换前的文件pdf/doc/md的文件路径，如果本就是docx文件,则与original_source_converted_jq一致),
                # 'source'键是为了与chatchat中的reader保持一致的，取值与'original_source_jq'一致
                # 'original_source_converted_jq':转换后的docx文件路径
                
                # 多进程情况下，"file_doc_object_jq":doc 会因为序列化/反序列化问题导致错误，所以此处不将其作为元数据的一部分   
                # metadata = {"file_name_jq": file_path.name,"file_doc_object_jq":doc,"file_doc_tree_jq":doc_tree,'df_table_list_jq':df_table_list}
                metadata = {"file_name_jq": file_path.name,"file_doc_tree_jq":doc_tree,'df_table_list_jq':df_table_list}
                if extra_info is not None:
                    metadata.update(extra_info)
                
                if self.orginal_filepath_extra_info is not None:
                    # 如果是经过JqkjSimpleDirectoryReader=>JqkjDocxReader，其实已经进行了文件类型转换，并且加入了'original_source_jq'，'source'键值
                    # 所以此处判断'original_source_jq'键是否已经存在，如果不存在，才能更新
                    if 'original_source_jq' not in metadata.keys():
                        metadata.update(self.orginal_filepath_extra_info)

                if 'file_size' not in metadata.keys():
                    # 调用/root/.virtualenvs/test/lib/python3.10/site-packages/llama_index/legacy/readers/file/base.py
                    # default_file_metadata_func方法，来获取文件default_file_metadata
                    if Path(doc_original).exists():
                        default_file_metadata = default_file_metadata_func(doc_original)
                        metadata.update(default_file_metadata)

                _keys = list(metadata.keys())
                # 保留元数据中的文件名可以用做分析
                if "file_name" in _keys:
                    _keys.remove('file_name') 
                document = LmDocument(text=text, metadata=metadata)
                document.excluded_embed_metadata_keys.extend(_keys)
                document.excluded_llm_metadata_keys.extend(_keys)
                return [document]
            else:
                return []
    
    def parse_docx_into_tree(self, docx_document:DocxDocument,file_path: Path) -> Node:
        # metadata = docx_document.metadata
        file = Path(file_path)
        filename=file.name
        # image_file_path: Path = Path('/media/temp/wendang/OCR接口性能报告.docx')
        # logger.debug(f"构建文档树：{file}")


        node_numbering=1 
            # type = TreeNodeType.DOCUMENT('DIRECTORY', 'DOCUMENT', 'TEXT', 'TABLE', 'IMAGE',"INDEX")
        file_tree = Node(f'{filename}',type=TreeNodeType.DOCUMENT, numbering=node_numbering,level=-100,text=f'{filename}') 
            # page=0, style="FILE_NAME",prompt=prompt, tag=file_name,self_num_characters=self_num_characters, self_num_tokens=self_num_tokens,total_num_characters=0,total_num_tokens=0,

        parent_node = file_tree
        pre_node = file_tree

        df_table_list=[]
        image_list=[]
        imgid_list=[]
        img_filename_list_in_table=[]

        w_pict_images_list_id = []
        w_pict_images_list_fn = []
        pic_pic_images_list_id = []
        pic_pic_images_list_fn = []

        for block in docx_document.iter_inner_content():
            if isinstance(block, Paragraph):
                pre_level = pre_node.level
                text = str(block.text.strip()) 

                # 文本/标题节点
                if len(text)>0:
                    style_name = block.style.name or 'Normal' # 1、防止为空，导致错误; 2、因为不含Heading，所以视为正常文本段落来处理
                    if len(text)>50 and "Heading" in style_name:  # 如果标题文本长度超出一定限制，则判为正文
                        style_name  = 'Normal'
                    if  "Heading" in style_name: #标题节点
                        if style_name=="Heading":
                            level=0
                        else:
                            try:
                                level = style_name.split(' ')[-1]
                                level = int(level) # Heading level
                            except:
                                level = 0

                        if level>pre_level:
                            parent_node = pre_node
                            current_depth = parent_node.depth+1                    

                        elif level==pre_level:
                            parent_node = pre_node.parent
                            current_depth = pre_node.depth

                        else:
                            # parent_node = find_nearest_parent(pre_node,level=level) 
                            parent_node = find_nearest_parent_but_not_TableOrImageNode(pre_node,level=level) 
                            current_depth = parent_node.depth+1    
                        
                        num_siblings = len(parent_node.children)
                        node_numbering = f"{parent_node.numbering}.{num_siblings+1}"
                        node = Node(f'[标题{node_numbering}]{text}',type=TreeNodeType.TEXT, parent=parent_node, style=style_name,numbering=node_numbering,level=level,text=f'{text}')   #data=[level,characters_count,text]             
                        
                        parent_node = node #当前Heading节点，作为父节点候选
                        pre_node = node

                    else: #文本节点
                        current_depth = parent_node.depth+1
                        level = current_depth
                        num_siblings = len(parent_node.children)
                        node_numbering = f"{parent_node.numbering}.{num_siblings+1}" #f"{parent_node.numbering}.0{num_siblings+1}"  最后一级编码如果以0开头，就表示是文本段落
                        node = Node(f'[正文{node_numbering}]{text[:10]}',type=TreeNodeType.TEXT,parent=parent_node,style=style_name, numbering=node_numbering,level=level,text=f'{text}')   #data=[level,characters_count,text]             
                        pre_node = node # 正文节点，不能作为父节点候选

                # 图片节点
                img_metadatas_list = self.extract_imgs(block,docx_document, file, image_list, imgid_list, w_pict_images_list_id, w_pict_images_list_fn, pic_pic_images_list_id, pic_pic_images_list_fn) 
                # img_metadatas_list = self.extract_imgs(block,docx_document, image_file_path, image_list, imgid_list, w_pict_images_list_id, w_pict_images_list_fn, pic_pic_images_list_id, pic_pic_images_list_fn) 
                 
                for img_metadata in img_metadatas_list:
                    # 创建图片节点
                    current_depth = parent_node.depth+1
                    level = current_depth
                    num_siblings = len(parent_node.children)
                    node_numbering = f"{parent_node.numbering}.{num_siblings+1}" #最后一级编码如果以0开头，就表示是文本段落
                    img_src = img_metadata['img_save_path_jq']
                    text = f"<img src={img_src},图片内容待识别 />"                        
                    node = Node(f'[图片{node_numbering}]',type=TreeNodeType.IMAGE,parent=parent_node, numbering=node_numbering,level=level,text=f'{text}',
                                image_filepath_jq=img_src,img_blob_jq=img_metadata['img_blob_jq']) 

                    pre_node = node # 图片节点，不能作为父节点候选
        
            # 表格节点
            if isinstance(block,Table):
                df,vf_string = self.read_docx_table(block)
                
                if vf_string: # vf_string可能不存在                  
                    column_names = vf_string.split('\r\n')[0]
                    df_table_list.append(df)
                else:
                    vf_string = ''
                    column_names = ''
                
                current_depth = parent_node.depth+1
                level = current_depth
                num_siblings = len(parent_node.children)
                node_numbering = f"{parent_node.numbering}.{num_siblings+1}" 
                node = Node(f'[表格{node_numbering}]{column_names}',type=TreeNodeType.TABLE,parent=parent_node, numbering=node_numbering,level=level,text=vf_string)
                # 如何解析df_table_jq = vf_string
                # vf =  StringIO()
                # vf.write(vf_string)
                # vf.seek(0)
                # df = pd.read_csv(vf)                
                
                pre_node = node # 前一个节点也固定为该表格节点，因为下面只会生成给表格的图片子节点
                table_as_parent_node = node #表格节点本身固定为表格中所有图片的父节点，另使用一个变量名来存储，避免影响之前的父节点

                # 下面处理表格中可能存在的图片
                paras_in_table_generator = get_paras_in_table(block)
                for para in paras_in_table_generator:   
                    img_metadatas_list = self.extract_imgs(para,docx_document, file, image_list, imgid_list, w_pict_images_list_id, w_pict_images_list_fn, pic_pic_images_list_id, pic_pic_images_list_fn)   

                    for img_metadata in img_metadatas_list:
                        img_filename = img_metadata['img_save_path_jq']
                        img_filename = Path(img_filename).name
                        img_filename_list_in_table.append(img_filename)
                        # 创建图片节点
                        current_depth = table_as_parent_node.depth+1
                        level = current_depth
                        num_siblings = len(table_as_parent_node.children)
                        node_numbering = f"{table_as_parent_node.numbering}.{num_siblings+1}" #最后一级编码如果以0开头，就表示是文本段落
                        img_src= img_metadata['img_save_path_jq']
                        text = f"<img src={img_src},图片内容待识别 />"
     
                        _ = Node(f'[图片{node_numbering}]',type=TreeNodeType.IMAGE,parent=table_as_parent_node, numbering=node_numbering,level=level,text=f'{text}',
                                    image_filepath_jq=img_src,img_blob_jq=img_metadata['img_blob_jq'])                        
          
        # 验证处理是否正确
                # 验证读取到的、实际保存的图片数量是否一致（在类初始化时默认不保存图片，如需验证，请设为self.save_img_file = True）
                # 验证是否所有的Anytree图片节点都已成功创建
                    # 注意：读取到的图片rID会存在重复（即同一图片在文件中多处使用），所以：
                    # 实际保存的图片数量应是len(set(imgid_list))
                    # 但创建的Anytree节点数量应是len(imgid_list)
                # 验证文档中实际具有的，已读取到的和保存的表格数量是否一致
                # 验证是否所有的Anytree图片表格节点都已成功创建
        
        VERBOSE = if_log_verbose()
        if VERBOSE:
            try:
                logger.debug(f"\n=========验证[{file_path}]读取结果是否正确=========")
                # logger.debug(f"\n=========验证读取结果是否正确=========")
                if len(image_list) == 0:
                    # logger.debug(f"[{file_path.name}]没有找到任何图片，请检查文件内容是否正确。")
                    logger.debug(f"没有找到任何图片，请检查文件内容解析是否准确。")        
                else:
                    s = set(imgid_list)
                    re_s = [(item,imgid_list.count(item)) for item in s if imgid_list.count(item)>1]
                    re_total = sum([item[1]-1 for item in re_s])
                    logger.debug(f'图片列表长度{len(image_list)}, 图片rId列表长度{len(imgid_list)}, 图片rId集合长度{len(s)}')
                    logger.debug(f'图片rId列表中重复的图片数量{len(re_s)}, 总重复次数为{re_total}')

                    imgname_list = [docx_document.part.related_parts[img_id].partname for img_id in imgid_list]
                    imgname_set = set(imgname_list)
                    repeated_imgs_and_counts = [(item,imgname_list.count(item)) for item in imgname_set if imgname_list.count(item)>1]
                    repeated_total_nums = sum([item[1]-1 for item in repeated_imgs_and_counts])
                    logger.debug(f'图片列表长度{len(image_list)}, 图片名列表长度{len(imgname_list)}, 图片名集合长度{len(imgname_set)}')
                    logger.debug(f'图片名列表中重复的图片数量{len(repeated_imgs_and_counts)}, 总重复数为{repeated_total_nums}')

                    logger.debug(f'pic_pic_images数量{len(pic_pic_images_list_id)},  w_pic_images数量{len(w_pict_images_list_id)}, 总数{len(pic_pic_images_list_id)+len(w_pict_images_list_id)}')
                    # diffs = compare_with_zip_docx2img(file) 可以一次性复制保存所有图片
                    diffs = compare_with_zip_docx2img(file,list(imgname_set))
                    logger.debug(f'其中，出现在表格中的图片数量为{len(img_filename_list_in_table)}，图片名为{", ".join(img_filename_list_in_table[:2])}...')
                    
                    img_nodes = anytree.search.findall(file_tree,filter_=lambda node:node.type==TreeNodeType.IMAGE)
                    assert len(img_nodes)==len(pic_pic_images_list_id)+len(w_pict_images_list_id),f'图片数量与图片列表数量不一致，图片数量为{len(img_nodes)},图片列表数量为{len(imgid_list)}'
                    for img_node in img_nodes:
                        assert img_node.is_leaf , f'图片节点{img_node.name}不是叶子节点，请检查,其父节点为{img_node.parent.name}！其第一个子节点为{img_node.children[0].name}'
                    logger.debug(f'创建的Image_Node数量{len(img_nodes)}, 图片总数{len(pic_pic_images_list_id)+len(w_pict_images_list_id)} ,已确认成功创建全部Image_Node')
                    
                    # 检查实际保存的images数量（在类初始化时默认不保存图片，如需验证，请设为self.save_img_file = True）
                    if self.save_img_file:
                        img_save_path_jq = img_metadata["img_save_path_jq"]
                        img_save_path_dir = Path(img_save_path_jq).parent

                        img_type_exts = set([Path(filename).suffix for filename in imgname_list])
                        img_type_exts_patten = ['*'+ ext for ext in img_type_exts]
                        files=[]
                        for ext in img_type_exts_patten:
                            files.extend(img_save_path_dir.glob(ext))
                        saved_img_num = len(files)
                        assert saved_img_num == len(s) == len(imgname_set),f'实际保存的图片数量({saved_img_num})与从Word Xml中读取到的图片rId集合长度({len(s)})不一致！'
                        logger.debug(f'    |==| 经assert断言检查，已在[{str(img_save_path_dir)}]文件夹下成功保存全部{saved_img_num}个图片文件。已确认成功创建全部Image_Node，且全部为叶子节点') 
                    else:
                        logger.debug(f'    |=您没有选择保存图片=| ')   

                table_number = len(docx_document.tables)
                if table_number == 0:
                    # logger.debug(f"[{str(filename)}]没有找到任何表格，请检查文件内容是否正确。") 
                    logger.debug(f"没有找到任何表格，请检查文件内容解析是否准确。")   
                else:
                    df_table_number = len(df_table_list)
                    table_nodes = anytree.search.findall(file_tree,filter_=lambda node:node.type==TreeNodeType.TABLE)
                    table_nodes_number = len(table_nodes)
                    assert table_number == df_table_number == table_nodes_number, f'表格数量与表格节点数量不一致，表格数量为{table_number},表格节点数量为{len(table_nodes_number)}'
                    for table_node in table_nodes:
                        if not table_node.is_leaf:
                            for _node in table_node.children:
                                assert _node.is_leaf and _node.type==TreeNodeType.IMAGE, f'表格节点{table_node}的子节点，必须是图片节点和叶子节点！'
                    logger.debug(f'已创建的Table_Node数量为{table_nodes_number}')
                    logger.debug(f'    |==| 经assert断言检查，[len(docx_document.tables)、len(df_table_list)、len(table_nodes)]长度一致,均为{table_number},已确认成功创建全部Table_Node，且其子节点全部为图片节点和叶子节点')
                print('==='*30)
            except Exception as ex:
                logger.error(f'===验证过程中出现了错误，请检查。错误信息如下:===\n{ex}')
                
        # 批量识别图片
        all_tree_nodes = list(PreOrderIter(file_tree))
        img_nodes = [node for node in all_tree_nodes if node.type == TreeNodeType.IMAGE]
        if len(img_nodes):
            img_src_and_data_tuple_list = [(f"{filename}/{treenode.image_filepath_jq}",treenode.img_blob_jq) for treenode in img_nodes] #得到[(img_src,img_data)...]
            logger.warning(f"\n$$$$$$$正在执行文件[{filename}]中的图片文字识别，共有{len(img_src_and_data_tuple_list)}张图片$$$$$$$")  
            start_time = time.time()
            results = treenodes_img_to_text_in_batch(img_src_and_data_tuple_list)
            end_time = time.time()
            logger.warning(f"\n$$$$$$$识别出得到的结果数量为：{len(results)=},共计用时: {end_time - start_time:.3f}秒~~~~~~~~~~~~~~~$$$$$$$")
            assert len(img_nodes) == len(results)
            for i,img_node in enumerate(img_nodes):
                img_node.text = results[i]
        else:
            logger.debug(f"$$$$$$$文件[{str(file_path)}]中不存在图片，无需识别$$$$$$$")
        return file_tree, df_table_list
   
    def extract_imgs(self, block:Paragraph, docx_document: DocxDocument, file: Path, image_list, imgid_list, w_pict_images_list_id, w_pict_images_list_fn, pic_pic_images_list_id, pic_pic_images_list_fn):
        # global image_list, imgid_list, w_pict_images_list_id, w_pict_images_list_fn, pic_pic_images_list_id, pic_pic_images_list_fn
        xmlstr = str(block._element.xml)
        my_namespaces = dict([node for _, node in ElementTree.iterparse(StringIO(xmlstr), events=['start-ns'])])

        img_metadatas_list = []
        img_metadata = {}

        #  w:*  :[w:pict  , w:object]
        if 'w:pict' in xmlstr or 'w:object' in xmlstr:
            w_pict_images = block._element.findall('.//w:pict//v:shape//v:imagedata', my_namespaces)                    
            w_object_images = block._element.findall('.//w:object//v:shape//v:imagedata', my_namespaces)
            w_pict_images.extend(w_object_images)
            if len(w_pict_images)>0:
                for image in w_pict_images:
                    try:
                        img_id=image.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
                        # 碰到过  img_id 为 None，导致下面出错的情况
                        part = docx_document.part.related_parts[img_id]
                        img_metadata.update(xml_type='w:pict')
                        img_metadata = self.image_part_post_process(part,file,img_metadata)
                        img_metadatas_list.append(img_metadata)

                        imgid_list.append(img_id)
                        w_pict_images_list_id.append(img_id)
                        w_pict_images_list_fn.append(part.partname)
                        image_list.append(img_metadata)
                    except:
                        pass

        if 'pic:pic' in xmlstr:
            pic_pic_images = block._element.findall('.//pic:pic', my_namespaces)
            if len(pic_pic_images)>0:
                for image in pic_pic_images:
                    for img_id in image.xpath('.//a:blip/@r:embed'):
                        part = docx_document.part.related_parts[img_id]                         
                        img_metadata.update(xml_type='pic:pic')
                        img_metadata = self.image_part_post_process(part,file,img_metadata)
                        img_metadatas_list.append(img_metadata)
                        
                        imgid_list.append(img_id)
                        pic_pic_images_list_id.append(img_id)
                        pic_pic_images_list_fn.append(part.partname)
                        image_list.append(img_metadata)
        return img_metadatas_list            

    def image_part_post_process(self, image_part: ImagePart,file: Path, img_metadata: Optional[Dict] = None) -> Dict:  # noqa: C901
        """Post process image part."""
        
        save_path = basename(image_part.partname)
        if self.save_img_file:
            img_dir = file.parent
            file_stem = file.stem            
            destination_dir =  join(img_dir,file_stem)
            save_path = join(destination_dir,basename(image_part.partname))
            if not Path(destination_dir).exists():
                logger.warning(f"输出目录[{destination_dir}]不存在!将尝试创建该目录。")
                Path(destination_dir).mkdir(parents=True, exist_ok=True)
            with open(save_path,'wb') as f:#保存图片
                f.write(image_part.blob)   
        img_metadata.update({"img_save_path_jq":save_path,"img_blob_jq":image_part.blob})
        return img_metadata

    #This function extracts the table from the document object as a dataframe
    def read_docx_table(self,table:Table, **kwargs):
        """
        parse table(s) from a Word Document (.docx) into Pandas DataFrame(s)

        Parameters:

            table:      a python-docx Table
            kwargs:     arguments to pass to `pd.read_csv()` function
                        see pd.read_csv(): https://pandas.pydata.org/docs/reference/api/pandas.read_csv.html

        Return: a single DataFrame
        """
        vf = io.StringIO()
        writer = csv.writer(vf)
        for row in table.rows:
            not_repeated_cell_texts = []
            for cell in row.cells:
                cell_text = cell.text.replace(" ","").replace("\r\n","").replace("\n","")
                if cell_text not in not_repeated_cell_texts:
                    not_repeated_cell_texts.append(cell_text)
                else:
                    not_repeated_cell_texts.append('')
            all_row_cells_are_blank = True
            for cell in not_repeated_cell_texts:
                if  cell != '':
                    all_row_cells_are_blank = False
                    break
            if not all_row_cells_are_blank:           
                writer.writerow(cell for cell in not_repeated_cell_texts)
            else:
                pass
        vf.seek(0)
        vf_string = vf.getvalue()
        
        df = None
        if vf_string:
            try:            
                df = pd.read_csv(vf, **kwargs)
            except Exception as e:
                logger.error(f"从{vf_string[0:100]=}读取到df失败:{e}，返回None")                
        return df,vf_string

# 为JqkjSimpleDirectoryReader做的变量准备
filetype_jqreader_dict = {}
[filetype_jqreader_dict.update({filetype:JqkjDocxReader}) for filetype in file_type_processed_by_jqreader]
file_type_processed_by_other_readers = {".py":UnstructuredReader,".txt":FlatReader}
filetype_reader_dict = {**filetype_jqreader_dict, **file_type_processed_by_other_readers}

def JQKJ_DEFAULT_FILE_READER_CLS(filetype_reader_dict=filetype_reader_dict):     
    DEFAULT_FILE_READER_CLS = _try_loading_included_file_formats()
    DEFAULT_FILE_READER_CLS.update(filetype_reader_dict)
    return DEFAULT_FILE_READER_CLS
# JQKJ_DEFAULT_FILE_READER_CLS()

class JqkjSimpleDirectoryReader(SimpleDirectoryReader):
    def __init__(
    self,    
    input_dir: Optional[str] = None,
    input_files: Optional[List] = None,
    output_dir_for_converted_files: Optional[str] = None,
    overwrite_existing_converted_files: bool = False,
    exclude: Optional[List] = ['~*.*','$*.*'],
    exclude_hidden: bool = True,
    errors: str = "ignore",
    recursive: bool = False,
    encoding: str = "utf-8",
    filename_as_id: bool = False,
    required_exts: Optional[List[str]] = None,
    file_extractor: Optional[Dict[str, BaseReader]] = None,
    num_files_limit: Optional[int] = None,
    file_metadata: Optional[Callable[[str], Dict]] = None,
    raise_on_error: bool = False,
    fs: Optional[fsspec.AbstractFileSystem] = None,    
) -> None:  
            # 确保输入是个列表
            if input_files:
                if isinstance(input_files, (str, Path)):
                    input_files = [input_files] 

                input_files = [Path(filepath) for filepath in input_files]        
                input_filepaths_not_existed = [filepath for filepath in input_files if not filepath.exists()]
                if input_filepaths_not_existed:
                    logger.warning(f"下列文件不存在，跳过：")
                    for _f in input_filepaths_not_existed:
                        logger.warning(f"    --{_f}")
                
                input_files = [filepath for filepath in input_files if filepath.exists()]


            super(JqkjSimpleDirectoryReader,self).__init__(
                input_dir=input_dir,
                input_files=input_files,
                exclude=exclude,
                exclude_hidden=exclude_hidden,
                errors=errors,
                recursive=recursive,
                encoding=encoding,
                filename_as_id=filename_as_id,
                required_exts=required_exts,
                file_extractor=file_extractor,
                num_files_limit=num_files_limit,
                raise_on_error=raise_on_error,
                fs=fs,                  
            )

            input_filepaths_exist,input_filepaths_exist_and_replaced_by_docx_if_converted = convert_file_to_docx(self.input_files,overwrite=overwrite_existing_converted_files,destination_dir=output_dir_for_converted_files)
            
            converted_files_metadata = {}
            for i,file in enumerate(input_filepaths_exist_and_replaced_by_docx_if_converted):                     
                file = str(file)
                original_file = str(input_filepaths_exist[i])
                converted_files_metadata[file] = {'original_source_jq':original_file,'source':original_file,'original_source_converted_jq':file} #'source'键是为了与chatchat中的reader保持一致的                        
                    
            self.input_files = input_filepaths_exist_and_replaced_by_docx_if_converted
            self.input_files_original_metadata=converted_files_metadata
            self.file_metadata = file_metadata or self.JQKJ_DEFAULT_FILE_META_DATA_FUNC

    SimpleDirectoryReader.supported_suffix_fn = JQKJ_DEFAULT_FILE_READER_CLS
    
    def JQKJ_DEFAULT_FILE_META_DATA_FUNC(self,file_path: str) -> Dict:
        if Path(file_path).exists():
            meta = default_file_metadata_func(file_path)
            meta.update(self.input_files_original_metadata[file_path])
            return meta
        else:
            return {}


def _test_JqkjDocxReader(file_paths=[fr"/media/temp/发票识别接口文档.md",'/data/projects/JqChatV2/JqChat/jqcode/jq_readers/.test_files/.testinputdocs/test_zh.pdf']):
    # fr'D:\biaoshu\pdf_docx_convert\UserGuide.docx',
    # reader = JqkjDocxReader(file_path=file_paths[0])
    # d = reader.load()
    reader = JqkjDocxReader()
    documents = []
    trees = []
    df_tables = []
    file_paths = [Path(file) for file in file_paths]
    for file in file_paths:
        # document= reader.load_data(file)[0]
        document = asyncio.run(reader.aload_data(file))[0]
        doc_tree = document.metadata['file_doc_tree_jq']
        df_table_list  = document.metadata['df_table_list_jq']
        documents.append(document)
        trees.append(doc_tree)
        df_tables.append(df_table_list)
        
        # logger.debug(f"=========输出[{document.metadata['source']}]中的部分内容=========")
        # n=100
        # logger.debug('---'*10+f"输出document.text前{n}字符"+'---'*10)
        # logger.debug(f"{document.text[:n]}")

        # logger.debug('###'*30)

        # logger.debug('---'*10+f"输出document.text后{n}字符"+'---'*10)
        # logger.debug(f"{document.text[-n:]}")
        # logger.debug('---'*30)
    
    return documents,trees,df_tables

def _test_error_files_JqkjSimpleDirectoryReader():
    convert_file_paths=[fr'/data/projects/JqChatV2/workspace/knowledge_base/jqtech_kb/content/关于安徽晶奇网络科技股份有限公司首次公开发行股票并在创业板上市申请文件的审核问询函.docx',
                        fr'/data/projects/JqChatV2/workspace/knowledge_base/jqtech_kb/content/青海省社会救助一门受理协同办理项目可研方案【提交版】v6.docx',
                        fr'/data/projects/JqChatV2/workspace/knowledge_base/jqtech_kb/content/公司规章制度 v1.1 (4)2019.3.19.docx',
                        fr"/data/projects/JqChatV2/workspace/knowledge_base/jqtech_kb/content/关于青海省低保项目存在信息泄露风险的情况说明(更新).docx"
                        ]
    
    
    start_time = time.time()
    simple_reader = JqkjSimpleDirectoryReader(input_files = convert_file_paths,output_dir_for_converted_files=fr"/data/projects/JqChatV2/JqChat/jqcode/jq_readers/.test_files/.outputdocs")
    documents1 = simple_reader.load_data()
    print(f"{len(documents1)=}")

def _test_JqkjSimpleDirectoryReader():
    convert_file_paths=[fr'/data/projects/JqChatV2/JqChat/jqcode/jq_readers/.test_files/.testinputdocs/厦门市智慧民政一体化平台项目建设方案 V3.6.docx',
                        fr'/data/projects/JqChatV2/JqChat/jqcode/jq_readers/.test_files/.testinputdocs/test_zh.pdf',
                        fr'/data/projects/JqChatV2/JqChat/jqcode/jq_readers/.test_files/.testinputdocs/AAMIS_项目总体计划_120925.doc',
                        fr"/media/temp/发票识别接口文档.md"
                        ]
    
    
    start_time = time.time()
    simple_reader = JqkjSimpleDirectoryReader(input_files = convert_file_paths,output_dir_for_converted_files=fr"/data/projects/JqChatV2/JqChat/jqcode/jq_readers/.test_files/.outputdocs")
    documents1 = simple_reader.load_data()
    print(f"{len(documents1)=}")
    end_time = time.time()
    logger.warning(f"Total time load_data: {end_time - start_time} seconds")
    pass 
    start_time = time.time()
    documents1a = asyncio.run(simple_reader.aload_data())
    print(f"{len(documents1a)}")
    end_time = time.time()
    logger.warning(f"Total time aload_data: {end_time - start_time} seconds")
    pass

    input_file_dir = fr'/data/projects/JqChatV2/JqChat/jqcode/jq_readers/.test_files/.testinputdocs'
    simple_reader2 = JqkjSimpleDirectoryReader(input_file_dir,exclude_hidden = False)
    documents2 = simple_reader2.load_data()
    print(len(documents2))

    documents2a = asyncio.run(simple_reader2.aload_data())
    print(len(documents2a))




def _test_get_retriever():
    from jqcode.jq_agent.tools.jq_retriever import get_retriever
    input_files = [fr'/data/projects/JqChatV2/JqChat/jqcode/jq_readers/.test_files/.testinputdocs/A方案.docx'] 
    input_files += [fr'/data/projects/JqChatV2/JqChat/jqcode/jq_readers/.test_files/.testinputdocs/PPQA000_质量保证过程.doc']   
    index_name='temp_index_for_upload_files'
    # compression_retriever = get_retriever(index_name=index_name,chat_on_docs_list=[],add_docs_list_to_kb=False)
    compression_retriever = get_retriever(index_name=index_name,chat_on_docs_list=input_files,add_docs_list_to_kb=False)     
    print(type(compression_retriever))
if __name__ == "__main__":

    documents,trees,df_tables = _test_JqkjDocxReader()
    _test_JqkjSimpleDirectoryReader()
    # _test_get_retriever()
    _test_error_files_JqkjSimpleDirectoryReader()
    
    # 

