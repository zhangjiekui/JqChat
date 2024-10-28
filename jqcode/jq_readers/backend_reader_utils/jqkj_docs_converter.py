import os, sys
import platform
import subprocess
from typing import Union
from pathlib import Path
import sys
# project_root = '/media/temp/JqChat806'
# sys.path.insert(0, project_root)

from jqcode.jq_readers.backend_reader_utils.jqkj_doc_pdf2docx_on_linux import convert_doc_or_pdf_to_docx
from jqcode.jq_utils.logger import jqkj_logger
logger = jqkj_logger(__file__).get_logger()


def get_os():
    if os.name == 'nt':
        return 'Windows'
    elif os.name == 'posix':
        if 'darwin' in platform.system().lower():
            return 'macOS'
        else:
            return 'Linux'
    else:
        return 'Unknown'
 
os_name = get_os()

# todo: 
# 1)代码本身的检查（命名）
# 2)加入其他常见类型的转换
# 3)chatchat的类型设置要与此处的联动起来

docpdf_list = [".doc",".pdf"]
pandoc_list =  [".md",".html"]
jq_reader_list =pandoc_list+docpdf_list

# dict: {".doc":ReadClass}

# 循环dict：、
#   如果key in JqReadderList:dict["key"] = JqReadder



def convert_md_to_docx(input_filepaths:Union[str,list],overwrite=True,destination_dir=None):
    """
    使用 pandoc 将 Markdown 文件转换为 DOCX 格式。

    :param input_filepaths: Markdown 文件的单个文件路径或文件路径列表

    :param overwrite: 如果为 True,则覆盖目标 DOCX 文件（如果存在）

    :param destination_dir: 将保存 DOCX 文件的目录
                            如果为 None, 则使用当前目录
    """
    not_exist_filepaths = []
    passed_makeup_filepaths = []
    existed_docx_filepath = []
    converted_makeup_filepaths = []   
    if not isinstance(input_filepaths,(str,Path,list)):
        raise TypeError(f"{input_filepaths} must be str,Path or list, not {type(input_filepaths)}")    
    if isinstance(input_filepaths,(str,Path)):
        input_filepaths = [input_filepaths]        
    input_filepaths = [Path(filepath) for filepath in input_filepaths]
    logger.info(f"原始的输入文件列表为({len(input_filepaths)})：\n  {' | '.join([str(x) for x in input_filepaths])}")

    not_exist_filepaths = [filepath for filepath in input_filepaths if not filepath.exists()]

    if len(not_exist_filepaths) > 0:
        logger.warning(f"路径不存在的文件列表为({len(not_exist_filepaths)})，将直接跳过！：\n  {' | '.join([str(x) for x in not_exist_filepaths])}")

    input_filepaths = [filepath for filepath in input_filepaths if filepath.exists()]
    original_valid_input_filepaths = [item for item in input_filepaths]
    logger.info(f"有效的输入文件列表为({len(input_filepaths)})：\n  {' | '.join([str(x) for x in input_filepaths])}")

    makeup_filepaths =[filepath for filepath in input_filepaths if filepath.suffix in  ['.md']]
    logger.info(f"待转换的makeup文件列表为({len(makeup_filepaths)})：\n  {' | '.join([str(x) for x in makeup_filepaths])}")    
    
    if len(makeup_filepaths) > 0:
        if destination_dir:
            if not Path(destination_dir).exists():
                logger.warning(f"输出目录[{destination_dir}]不存在!将尝试创建该目录。")
                Path(destination_dir).mkdir(parents=True, exist_ok=True) 
            destination_dir = Path(destination_dir).absolute()
            logger.info(f"  输出目录路径为[{destination_dir}]")

        for makeup_filepath in makeup_filepaths:

            docx_filepath = makeup_filepath.with_suffix(".docx")
            if destination_dir:
                docx_filepath = destination_dir / docx_filepath.name

            if docx_filepath.exists():
                if overwrite:
                    docx_filepath.unlink
                else:
                    passed_makeup_filepaths.append(makeup_filepath)
                    existed_docx_filepath.append(docx_filepath)
                    index = input_filepaths.index(makeup_filepath)
                    input_filepaths.insert(index, docx_filepath) 
                    input_filepaths.remove(makeup_filepath) 
    if len(passed_makeup_filepaths)>0:
        logger.warning(f"目标文件已存在的列表（转换前）为({len(passed_makeup_filepaths)})：\n  {' | '.join([str(x) for x in passed_makeup_filepaths])}")
        logger.warning(f"目标文件已存在的列表（转换后）为({len(existed_docx_filepath)})：\n  {' | '.join([str(x) for x in existed_docx_filepath])}")
        logger.warning(f"因为转换参数overwrite={overwrite}，以上这些文件将直接跳过转换，如需重新转换并覆盖，请设置overwrite为True!")
        for makeup_filepath in passed_makeup_filepaths:
            makeup_filepaths.remove(makeup_filepath)


    # 遍历输入md的文件路径
    for md_filepath in input_filepaths:
        # 提取不带扩展名的基本文件名
        base_name = os.path.splitext(os.path.basename(md_filepath))[0]
        # 定义输出的docx文件路径
        docx_filepath = os.path.join(destination_dir, f"{base_name}.docx")

        # 检查输出文件是否存在
        if os.path.exists(docx_filepath) and not overwrite:
            print(f"File {docx_filepath} already exists and will not be overwritten.")
            continue

        # 构造pandoc文件转换命令
        pandoc_command = f"pandoc -s {md_filepath} -o {docx_filepath}"

        # 执行pandoc文件转换命令
        try:
            subprocess.run(pandoc_command, shell=True, check=True)
            # logger.info(f"Converted {md_filepath} to {docx_filepath}")
        except subprocess.CalledProcessError as e:
            logger.info(f"An error occurred while converting {md_filepath}: {e}")

        converted_makeup_filepaths.append(str(docx_filepath))
        index = input_filepaths.index(makeup_filepath)
        input_filepaths.insert(index, docx_filepath)  
        input_filepaths.remove(makeup_filepath) 

    # logger.info(f"有效的原始输入文件列表为({len(original_valid_input_filepaths)})：\n  {' | '.join([str(x) for x in original_valid_input_filepaths])}")  
    logger.info(f"转换后的相应docx文件列表为({len(converted_makeup_filepaths)})：\n  {' | '.join([str(x) for x in converted_makeup_filepaths])}")
    logger.info(f"返回新的有效文件列表为({len(input_filepaths)})：\n  {' | '.join([str(x) for x in input_filepaths])}")

    return input_filepaths,original_valid_input_filepaths

def convert_doc_pdf2docx_on_win_and_linux(input_filepaths:Union[str,list],overwrite=True,destination_dir=None):
    """
    Convert pdf or doc file(s) to docx file(s) using windows word application through pywin32.win32com
    在windows下运行, 利用word程序将:
        (1)doc转换为docx, 这样后续能使用Python-docx进行处理
        (2)pdf转换为docx, 这样能获得标题目录信息
    在Linux环境下运行, 依赖:
        (1)pdf-->docx 依赖pdf2docx包: pip install pdf2docx
        (2)doc-->docx 依赖spire.doc包: pip install spire.doc, 但这个是收费的
    :param pdf_filepaths: str or list. pdf/doc file path(s)
    :return: (docx file path(s),valid_input_filepaths)
    """
    
    not_exist_filepaths = []
    passed_makeup_filepaths = []
    existed_docx_filepath = []
    converted_makeup_filepaths = []   
    if not isinstance(input_filepaths,(str,Path,list)):
        raise TypeError(f"{input_filepaths} must be str,Path or list, not {type(input_filepaths)}")    
    if isinstance(input_filepaths,(str,Path)):
        input_filepaths = [input_filepaths]        
    input_filepaths = [Path(filepath) for filepath in input_filepaths]
    logger.info(f"原始的输入文件列表为({len(input_filepaths)})：\n  {' | '.join([str(x) for x in input_filepaths])}")

    not_exist_filepaths = [filepath for filepath in input_filepaths if not filepath.exists()]

    if len(not_exist_filepaths) > 0:
        logger.warning(f"路径不存在的文件列表为({len(not_exist_filepaths)})，将直接跳过！：\n  {' | '.join([str(x) for x in not_exist_filepaths])}")

    input_filepaths = [filepath for filepath in input_filepaths if filepath.exists()]
    original_valid_input_filepaths = [item for item in input_filepaths]
    logger.info(f"有效的输入文件列表为({len(input_filepaths)})：\n  {' | '.join([str(x) for x in input_filepaths])}")

    pdf_doc_filepaths =[filepath for filepath in input_filepaths if filepath.suffix in  ['.doc',".pdf"]]
    logger.info(f"待转换的pdf/doc文件列表为({len(pdf_doc_filepaths)})：\n  {' | '.join([str(x) for x in pdf_doc_filepaths])}")    
    
    if len(pdf_doc_filepaths) > 0:
        if destination_dir:
            if not Path(destination_dir).exists():
                logger.warning(f"输出目录[{destination_dir}]不存在!将尝试创建该目录。")
                Path(destination_dir).mkdir(parents=True, exist_ok=True) 
            destination_dir = Path(destination_dir).absolute()
            logger.info(f"  输出目录路径为[{destination_dir}]")

        for pdf_doc_filepath in pdf_doc_filepaths:

            docx_filepath = pdf_doc_filepath.with_suffix(".docx")
            if destination_dir:
                docx_filepath = destination_dir / docx_filepath.name

            if docx_filepath.exists():
                if overwrite:
                    docx_filepath.unlink
                else:
                    passed_makeup_filepaths.append(pdf_doc_filepath)
                    existed_docx_filepath.append(docx_filepath)
                    index = input_filepaths.index(pdf_doc_filepath)
                    input_filepaths.insert(index, docx_filepath) 
                    input_filepaths.remove(pdf_doc_filepath) 

    if len(passed_makeup_filepaths)>0:
        logger.warning(f"目标文件已存在的列表（转换前）为({len(passed_makeup_filepaths)})：\n  {' | '.join([str(x) for x in passed_makeup_filepaths])}")
        logger.warning(f"目标文件已存在的列表（转换后）为({len(existed_docx_filepath)})：\n  {' | '.join([str(x) for x in existed_docx_filepath])}")
        logger.warning(f"因为转换参数overwrite={overwrite}，以上这些文件将直接跳过转换，如需重新转换并覆盖，请设置overwrite为True!")
        for pdf_doc_filepath in passed_makeup_filepaths:
            pdf_doc_filepaths.remove(pdf_doc_filepath)
    
    if len(pdf_doc_filepaths) > 0:
        logger.debug('  因存在须转换的doc/pdf文件，建议最好在ms windows下运行，且安装有ms word程序！')
        for pdf_doc_filepath in pdf_doc_filepaths:
            docx_filepath = pdf_doc_filepath.with_suffix(".docx")
            if destination_dir:
                docx_filepath = destination_dir / docx_filepath.name
            try:
                if os_name=='Windows':        
                    import win32com.client        
                    word = win32com.client.Dispatch("Word.Application")
                    pdfdoc = word.Documents.Open(str(pdf_doc_filepath),Visible=False)
                    # https://blog.csdn.net/ynyn2013/article/details/49120731
                    # wdFormatXMLDocument = 12
                    # wdFormatDocumentDefault = 16
                    pdfdoc.SaveAs(str(docx_filepath),12) 
                    pdfdoc.Close()
                    word.Quit()
                elif os_name=='Linux':
                    if pdf_doc_filepath.suffix in [".pdf",".doc"]:
                        convert_doc_or_pdf_to_docx(pdf_doc_filepath,docx_filepath)
                else:
                    raise Exception(f'暂不支持 {os_name} 操作系统,建议在Windows或Linux环境下运行')
                converted_makeup_filepaths.append(str(docx_filepath))
                index = input_filepaths.index(pdf_doc_filepath)
                input_filepaths.insert(index, docx_filepath)  
                input_filepaths.remove(pdf_doc_filepath)          
                
            except Exception as e:
                logger.warning(f"无法转换[doc/pdf-->docx]，详细错误信息为{e}")

    # logger.info(f"有效的原始输入文件列表为({len(original_valid_input_filepaths)})：\n  {' | '.join([str(x) for x in original_valid_input_filepaths])}")  
    logger.info(f"转换后的相应docx文件列表为({len(converted_makeup_filepaths)})：\n  {' | '.join([str(x) for x in converted_makeup_filepaths])}")
    logger.info(f"返回新的有效文件列表为({len(input_filepaths)})：\n  {' | '.join([str(x) for x in input_filepaths])}")

    return input_filepaths,original_valid_input_filepaths

# 需改成批量（多线程或多进程），有些大pdf转换需要好几分钟
def convert_file_to_docx(input_filepaths: Union[str, list], overwrite=False, destination_dir=None):
    """
    将 Markdown、PDF 或 DOC 文件转换为 DOCX 格式。

    :param input_filepaths: Markdown、PDF 或 DOC 文件的单个文件路径或文件路径列表。
    :param overwrite: 如果为 True,则覆盖目标 DOCX 文件（如果存在）

    :param destination_dir: 将保存 DOCX 文件的目录
                            如果为 None, 则使用当前目录
    """
    # 确保输入是个列表
    if isinstance(input_filepaths, (str, Path)):
        input_filepaths = [input_filepaths]

        
    input_filepaths = [Path(filepath) for filepath in input_filepaths]
    input_filepaths_exist = [filepath for filepath in input_filepaths if filepath.exists()]
    input_filepaths_exist_and_replaced_by_docx_if_converted = []

    # 如果destination_dir没有指定,则目标目录为当前目录
    if destination_dir is None:
        destination_dir = os.getcwd()

    files_to_be_converted = []
    for filepath in input_filepaths:
        if not Path(filepath).exists():
            logger.info(f"File {filepath} does not exist. Skipping.")
            continue

        # 定义输出的docx文件路径
        base_name = Path(filepath).stem
        output_filepath = Path(destination_dir) / f"{base_name}.docx"

        # 检查文件是否存在
        if output_filepath.exists() and not overwrite:
            logger.info(f"File {output_filepath} already exists. Skipping conversion.")
            input_filepaths_exist_and_replaced_by_docx_if_converted.append(output_filepath)
            continue

        # 根据文件扩展名进行转换
        logger.warning(f'==*==转换文件{filepath}')
        if Path(filepath).suffix == '.md':
            convert_md_to_docx(filepath, output_filepath, destination_dir=destination_dir)
            input_filepaths_exist_and_replaced_by_docx_if_converted.append(output_filepath)
        elif Path(filepath).suffix in ['.pdf', '.doc']:
            convert_doc_pdf2docx_on_win_and_linux(filepath, output_filepath, destination_dir=destination_dir)
            input_filepaths_exist_and_replaced_by_docx_if_converted.append(output_filepath)
        else:
            logger.warning(f"JqConverter跳过文件转换: {filepath}")
            input_filepaths_exist_and_replaced_by_docx_if_converted.append(filepath)

    return input_filepaths_exist,input_filepaths_exist_and_replaced_by_docx_if_converted



if __name__ == "__main__":
    files = ["/media/temp/软件开发成本度量规范.pdf", 
             "/media/temp/户口本接口文档.pdf",
             "/media/temp/发票识别接口文档.md",
             "/media/temp/OCR接口性能报告.doc"]

    convert_file_to_docx(files, overwrite=True, destination_dir='/media/temp/docxfiles/')



    # convert_md_to_docx('/media/发票识别接口文档.md', overwrite=False, destination_dir='/media/temp/docxfiles/')


    # pdf_filepaths = [fr"/media/temp/软件开发成本度量规范.pdf"]
    # destination_dir = '/media/temp/'
    # doc_filepaths = convert_doc_pdf2docx_on_win_and_linux(pdf_filepaths,overwrite=True, destination_dir=destination_dir)


