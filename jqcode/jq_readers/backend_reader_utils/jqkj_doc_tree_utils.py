from typing import Iterator, List, Optional, Union

from docx import Document as DocxDocument
from llama_index.core.schema import Document as LmDocument
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.blkcntnr import BlockItemContainer

import zipfile
import os
import shutil
from pathlib import Path

import jieba
from anytree import Node,RenderTree
from anytree.importer import JsonImporter
from jqcode.jq_utils.logger import jqkj_logger


logger = jqkj_logger(__file__).get_logger()

from enum import Enum, auto
class TreeNodeType(str,Enum):
    DIRECTORY = auto() #文件夹
    DOCUMENT = auto() #实质是文件File，改为DOCUMENT是为了与llama_index保持一致 https://github.com/run-llama/llama_index/blob/98169c3684f7fcdcebbeecbc199ff2cb242a3bed/llama_index/schema.py#L154
    TEXT = auto()
    TABLE = auto()
    IMAGE = auto()
    INDEX = auto()

def get_doc_tree_from_document(document:LmDocument):
    doc_tree_obj = document.metadata.get("file_doc_tree_jq",False)
    if doc_tree_obj:
        if isinstance(doc_tree_obj,str):
            anytree_json_importer = JsonImporter()
            doc_tree_obj = anytree_json_importer.import_(doc_tree_obj)
    return doc_tree_obj
# doc_tree_dict = anytree_json_exporter.export(doc_tree)
# node.metadata["file_doc_tree_jq"] = doc_tree_dict
# doc_tree_from_dict = anytree_json_importer.import_(doc_tree_dict)
# assert len(doc_tree.descendants) == len(doc_tree_from_dict.descendants)





def find_nearest_parent(node:Node,level=2):        
        parent_node = node.parent
        parent_level = int(parent_node.level)
        while parent_level>=level:
            parent_node = parent_node.parent
            parent_level = int(parent_node.level)
        return parent_node

def find_nearest_parent_but_not_TableOrImageNode(node:Node,level=2):
        _ancestors = node.ancestors
        canditates = [n for n in _ancestors if n.type!=TreeNodeType.TABLE and n.type!=TreeNodeType.IMAGE]
        canditates.reverse()
        for n in canditates:
            if int(n.level)<level:
                return n

def calculate_character_token_nums(node:Node):
    self_characters = node.self_num_characters
    self_tokens = node.self_num_tokens

    for n in node.children:
        if n.is_leaf:
            self_characters += n.self_num_characters
            self_tokens     += n.self_num_tokens

            n.total_num_characters = n.self_num_characters
            n.total_num_tokens     = n.self_num_tokens

            node.total_num_characters = self_characters
            node.total_num_tokens     = self_tokens
            
        else:
            _,children_characters, children_tokens = calculate_character_token_nums(n)
            n.total_num_characters=children_characters
            n.total_num_tokens=children_tokens

            self_characters += children_characters
            self_tokens     += children_tokens
    
        node.total_num_characters=self_characters
        node.total_num_tokens=self_tokens
    # validate_character_token_nums(node)
    return node,self_characters,self_tokens
    
def validate_character_token_nums(node:Node):
    print(f'\n===============验证树节点(含根节点)的tokens和characters数量统计和合计===============')

    descendants =node.descendants
    all_nodes = (node,*descendants)
    i=0
    for n in all_nodes:
        i+=1
        if n.is_leaf:
            assert n.self_num_characters == n.total_num_characters
            assert n.self_num_tokens == n.total_num_tokens
        else:
            self_tokens = n.self_num_tokens
            self_characters = n.self_num_characters
            total_tokens = 0
            total_characters = 0
            for nn in n.children:
                total_characters += nn.total_num_characters
                total_tokens += nn.total_num_tokens
            assert n.total_num_characters == self_characters + total_characters
            assert n.total_num_tokens == self_tokens + total_tokens
    assert i==len(all_nodes)
    print(f"验证通过，所有 {i} 个树节点(含根节点)的tokens和characters数量统计和合计完全正确")
    
    print('根节点及其子节点的tokens和characters数量情况如下：')
    print(f'  根节点 [{node.node_number}_{node.tag}]：characters={node.total_num_characters},tokens={node.total_num_tokens}')
    for n in node.children:
        print(f'    子节点 [{n.node_number}_{n.tag}]：characters={n.total_num_characters},tokens={n.total_num_tokens}')

    return node

def print_tree_structer_with_type_and_text(node:Node,n_chars=80):
    print(RenderTree(node).by_attr(lambda n: str(n.type).split('.')[-1]+"： "+n.text[:n_chars]))

def print_only_headings(node:Node):
    print(f'\n===============打印全部Headings===============')
    descendants =node.descendants
    all_nodes = (node,*descendants)
    for n in all_nodes:
        current_depth = n.level
        prefix = '--'*current_depth
        if hasattr(n,'style') and 'Heading' in n.style:
            print(f"{prefix}{n.numbering}_{n.text}  :[{n.style}]")

def print_n_nodes(node:Node,n=50):
        print(f'\n===============打印前{n}个节点(含根节点)===============')
        descendants =node.descendants
        all_nodes = (node,*descendants)      

        for n in all_nodes[:n]:
            current_depth = n.level
            prefix = '-'*current_depth
            print(f"{prefix}{n.numbering}_{n.text[:10]} :[{n.style}]")


def jieba_pre_process(text:Optional[Union[str, List[str]]]):
    logger.debug(f"JiebaInput:{text}")
    _cut_results = []
    if isinstance(text, str):
        r=jieba.lcut_for_search(text)
        _cut_results = [item for item in r if len(item.replace(' ',''))>0]
    elif isinstance(text, list):        
        for t in text:
            r=jieba.lcut_for_search(t)
            cut_result = [item for item in r if len(item.replace(' ',''))>0]
            _cut_results.append(cut_result)
    else:
        raise TypeError('text must be str or list[str]')    
    
    # 需要去除的中英文标点符号
    punctuation = '!,.:;?！，。：；？、…'
    cut_results = [item for item in _cut_results if item not in punctuation]
    logger.debug(f"JiebaOutput:{cut_results}")
    return cut_results



def get_all_paragraghs_paras_plus_paras_in_table(blkcntnr: BlockItemContainer) -> Iterator[Paragraph]:
    for item in blkcntnr.iter_inner_content():
        if isinstance(item, Paragraph):
            yield item
        elif isinstance(item, Table):
            for row in item.rows:
                for cell in row.cells:
                    yield from get_all_paragraghs_paras_plus_paras_in_table(cell)

def get_paras_in_table(table:Table) -> Iterator[Paragraph]:
    for row in table.rows:
        for cell in row.cells:
            yield from get_all_paragraghs_paras_plus_paras_in_table(cell)

def compare_with_zip_docx2img(word_path, image_file_name_list=None,result_path=None):
    
    given_img_num =0
    diffs = []
    if result_path is None:
        result_path =f'{os.path.splitext(word_path)[0]}'
    
    if image_file_name_list is not None:
        image_file_name_list = list(set(image_file_name_list))
        image_file_name_list = [Path(image_file).name for image_file in image_file_name_list]
        given_img_num = len(image_file_name_list)            

    tmp_path = f'{os.path.splitext(word_path)[0]}_tmp_zipfiles'
    splitext = os.path.splitext(word_path)
    zip_path = shutil.copy(word_path, f'{splitext[0]}_new{splitext[1]}')
    with zipfile.ZipFile(zip_path, 'r') as f:
        for file in f.namelist():
            f.extract(file, tmp_path)
    os.remove(zip_path)
    pic_path = os.path.join(tmp_path, 'word/media')
    if not os.path.exists(pic_path):
        shutil.rmtree(tmp_path)
        return []
    pictures = os.listdir(pic_path)
    pictures_num = len(pictures)

    

    if given_img_num == 0: #复制所有图片
        diffs = pictures
    elif given_img_num > 0 and pictures_num !=given_img_num: #在_diffs文件夹下存储差异图片
        logger.error(f'图片数量不一致，使用zip方式读取的图片数量为:{pictures_num},提供的图片列表长度为{given_img_num}，差异图片数量为{len(diffs)}')
        result_path = result_path + '/_diffs'
        diffs = [item for item in pictures if item not in image_file_name_list]        
    else:
        assert pictures_num == given_img_num, '图片数量不一致'
        logger.debug(f'使用zip方式读取的图片数量为{pictures_num},提供的图片列表长度为{given_img_num}，两者相等')
        shutil.rmtree(tmp_path)
        return diffs #返回，执行完毕
    
    if not os.path.exists(result_path):
        os.makedirs(result_path)
    
    for picture in diffs:
        shutil.copy(os.path.join(pic_path, picture), os.path.join(result_path, picture))

    shutil.rmtree(tmp_path)
    diffs = [os.path.join(result_path, pic) for pic in os.listdir(result_path)]
    return diffs

def get_docx_paragraph_page_number(document: DocxDocument):
    raise Exception("不准确，暂时不要使用")
    only_page_breaks_para_page_number = {}  # {paragragh:page_number} 包含了page_breaks的段落的页码（范围）
    all_para_page_number = {} #所有段落的页码
    
    paragraphs=0
    pages=1
    for item in get_all_paragraghs_paras_plus_paras_in_table(document) : 
        paragraphs +=1      
        assert isinstance(item, Paragraph), 'item must be Paragraph'
        page_breaks = item.rendered_page_breaks

        if item.contains_page_break:
             if len(page_breaks)<=0:
                    print(f"段落{item.id}没有分页符，但是有page_break")
   

        page_start=str(pages)
        if len(page_breaks)>0:
            if len(page_breaks)>1:
                logger.error(f"一个段落里有多个分页符！实际不是错误，只是捕捉看看有没有可能会发生，什么情况下会发生")
                raise Exception('实际不是错误！正式上线时这行代码应该注释掉') 
            for page_break in page_breaks:
                pages += 1
                page_range=str(pages)
                preceding_paragraph = page_break.preceding_paragraph_fragment
                following_paragraph = page_break.following_paragraph_fragment
                if preceding_paragraph is not None and following_paragraph is not None:
                    page_range = page_start + '-' +str(pages)
                
                only_page_breaks_para_page_number.update({item:page_range})
                all_para_page_number.update({item:page_range})
        else:
            all_para_page_number.update({item:page_start})
    print(f"全部段落数{paragraphs},最大页码数{pages}")
    return all_para_page_number,only_page_breaks_para_page_number

def _test_jieba_pre_process():
    print('\n=================test_jieba_pre_process:start=================')
    text = "我爱北京天安门"
    cut_results=jieba_pre_process(text)
    print(f"JiebaInput:{text}")
    print(f"JiebaOutput:{cut_results}")
    text = ["我爱北京天安门", "我爱中华人民共和国"]
    cut_results=jieba_pre_process(text)
    print(f"JiebaInput:{text}")
    print(f"JiebaOutput:{cut_results}")
    text = 'This section introduces the overall performance of Baichuan 2 base models compared with other similar-sized models.'
    cut_results=jieba_pre_process(text)
    print(f"JiebaInput:{text}")
    print(f"JiebaOutput:{cut_results}")
    text = ['This section introduces the overall performance of Baichuan 2 base models compared with other similar-sized models.', "我爱中华人民共和国"]
    cut_results=jieba_pre_process(text)
    print(f"JiebaInput:{text}")
    print(f"JiebaOutput:{cut_results}")
    print('=================test_jieba_pre_process: end=================')

def _test_get_docx_paragraph_page_number(print_interval_only_page_breaks=10,print_interval_all=100):
    print('\n=================test_get_docx_paragraph_page_number:start=================')
    document = DocxDocument(fr'/data/projects/JqChat/jqcode/jq_readers/_testinputdocs/UserGuide_new.docx')
    # document = DocxDocument(fr'd:/JqkjKB/jqkjfiles/outputs/outputfiles/converted_docx/UserGuide_p2.docx')
    # document = Document(fr'd:/JqkjKB/jqkjfiles/outputs/outputfiles/converted_docx/厦门市智慧民政一体化平台项目建设方案 V3.6_p2.docx')
    # document.save('temp_for_pages.docx')
    # document = Document('temp_for_pages.docx')
    para_page_number,para_page_number_only_page_breaks  = get_docx_paragraph_page_number(document)
    
    print('---------------------------only_page_breaks_para_page_number ---------------------------------')
    
    i=0
    for para, page_number in para_page_number_only_page_breaks.items():
        i+=1
        if i%print_interval_only_page_breaks==0:
            print(i,para.text[:20],page_number) 
    print(f'一共{i}个段落（only_page_breaks）')
    
    print('---------------------------all_para_page_number ---------------------------------')
    i=0
    for para, page_number in para_page_number.items():
        i+=1
        if i%print_interval_all==0:
            print(i,para.text[:20],page_number) 
    print(f'一共{i}个段落（all）')
    print('=================test_get_docx_paragraph_page_number: end=================')

    print(f'一共{len(document.paragraphs)}个段落（document.paragraphs）')

def _valid_returned_obj_types(document = DocxDocument(fr'/data/projects/JqChat/jqcode/jq_readers/_testinputdocs/UserGuide.docx')):
    types=set()
    for b in get_all_paragraghs_paras_plus_paras_in_table(document):
        types.add(type(b))
    print(types)
    return types

def _test_docx2img(word_path=fr'd:/JqkjKB/jqkjfiles/outputs/outputfiles/converted_docx/厦门市智慧民政一体化平台项目建设方案 V3.6.docx'):
    pics=compare_with_zip_docx2img(word_path,result_path=None)
    print(pics)


if __name__ == "__main__":
    # _test_jieba_pre_process()
    # _test_get_docx_paragraph_page_number(print_interval_only_page_breaks=1,print_interval_all=1)
    # types=_valid_returned_obj_types()
    _test_docx2img()





