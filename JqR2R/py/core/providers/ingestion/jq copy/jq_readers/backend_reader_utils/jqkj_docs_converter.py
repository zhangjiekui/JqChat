import os,sys,base64,requests
import platform
import subprocess
from io import BytesIO
from typing import Union
from pathlib import Path
from typing import Union
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import threading
from threading import BoundedSemaphore
lock = threading.Lock()
pool = ThreadPoolExecutor(40)
semaphore = BoundedSemaphore(10) 

from jqcode.jq_splitters.jq_docx_tree_text_splitter import load_project_env

from jqcode.jq_utils.logger import jqkj_logger
logger = jqkj_logger(__file__).get_logger()

env_loaded = load_project_env()

winserver_convert_url = os.environ.get('winserver_convert_url','http://192.168.44.180:8000/convert/batch/')
winserver_download_url = os.environ.get('winserver_download_url','http://192.168.44.180:8000/download/batch/')

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
pandoc_list =  [".md",".html",".htm"]
jq_reader_list =pandoc_list+docpdf_list

# dict: {".doc":ReadClass}

# 循环dict：
#   如果key in JqReadderList:dict["key"] = JqReader



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
        # 文件类型扩展名
        ext = Path(md_filepath).suffix

        # 检查输出文件是否存在
        if os.path.exists(docx_filepath) and not overwrite:
            print(f"File {docx_filepath} already exists and will not be overwritten.")
            continue

        # 构造pandoc文件转换命令
        pandoc_command = f"pandoc -s {md_filepath} -o {docx_filepath}"

        # 执行pandoc文件转换命令
        try:
            with lock:
                message = subprocess.run(pandoc_command, shell=True, check=True)
                if message.returncode!=0 or "Error" in str(message.stderr):
                    raise Exception(f"使用Pandoc转换{ext}文件{md_filepath}失败！详细信息为：{message.stderr}")
                else:
                    logger.warning(f"使用Pandoc成功将{md_filepath}转换为{docx_filepath}")
        except subprocess.CalledProcessError as e:
            stderr = '无'
            try:
                stderr = e.stderr
            except:
                pass
            logger.warning(f"将{md_filepath}转换为{docx_filepath}出错：{e=}，e.stderr={stderr}")

        converted_makeup_filepaths.append(str(docx_filepath))
        index = input_filepaths.index(makeup_filepath)
        input_filepaths.insert(index, docx_filepath)  
        input_filepaths.remove(makeup_filepath) 

    # logger.info(f"有效的原始输入文件列表为({len(original_valid_input_filepaths)})：\n  {' | '.join([str(x) for x in original_valid_input_filepaths])}")  
    logger.info(f"转换后的相应docx文件列表为({len(converted_makeup_filepaths)})：\n  {' | '.join([str(x) for x in converted_makeup_filepaths])}")
    logger.info(f"返回新的有效文件列表为({len(input_filepaths)})：\n  {' | '.join([str(x) for x in input_filepaths])}")

    return input_filepaths,original_valid_input_filepaths

######################################## 原始代码 #######################################################

# def convert_doc_pdf2docx_on_win_and_linux(input_filepaths:Union[str,list],overwrite=True,destination_dir=None):
#     """
#     Convert pdf or doc file(s) to docx file(s) using windows word application through pywin32.win32com
#     在windows下运行, 利用word程序将:
#         (1)doc转换为docx, 这样后续能使用Python-docx进行处理
#         (2)pdf转换为docx, 这样能获得标题目录信息
#     在Linux环境下运行, 依赖:
#         (1)pdf-->docx 依赖pdf2docx包: pip install pdf2docx
#         (2)doc-->docx 依赖spire.doc包: pip install spire.doc, 但这个是收费的
#     :param pdf_filepaths: str or list. pdf/doc file path(s)
#     :return: (docx file path(s),valid_input_filepaths)
#     """
    
#     not_exist_filepaths = []
#     passed_makeup_filepaths = []
#     existed_docx_filepath = []
#     converted_makeup_filepaths = []   
#     if not isinstance(input_filepaths,(str,Path,list)):
#         raise TypeError(f"{input_filepaths} must be str,Path or list, not {type(input_filepaths)}")    
#     if isinstance(input_filepaths,(str,Path)):
#         input_filepaths = [input_filepaths]        
#     input_filepaths = [Path(filepath) for filepath in input_filepaths]
#     logger.info(f"原始的输入文件列表为({len(input_filepaths)})：\n  {' | '.join([str(x) for x in input_filepaths])}")

#     not_exist_filepaths = [filepath for filepath in input_filepaths if not filepath.exists()]

#     if len(not_exist_filepaths) > 0:
#         logger.warning(f"路径不存在的文件列表为({len(not_exist_filepaths)})，将直接跳过！：\n  {' | '.join([str(x) for x in not_exist_filepaths])}")

#     input_filepaths = [filepath for filepath in input_filepaths if filepath.exists()]
#     original_valid_input_filepaths = [item for item in input_filepaths]
#     logger.info(f"有效的输入文件列表为({len(input_filepaths)})：\n  {' | '.join([str(x) for x in input_filepaths])}")

#     pdf_doc_filepaths =[filepath for filepath in input_filepaths if filepath.suffix in  ['.doc',".pdf"]]
#     logger.info(f"待转换的pdf/doc文件列表为({len(pdf_doc_filepaths)})：\n  {' | '.join([str(x) for x in pdf_doc_filepaths])}")    
    
#     if len(pdf_doc_filepaths) > 0:
#         if destination_dir:
#             if not Path(destination_dir).exists():
#                 logger.warning(f"输出目录[{destination_dir}]不存在!将尝试创建该目录。")
#                 Path(destination_dir).mkdir(parents=True, exist_ok=True) 
#             destination_dir = Path(destination_dir).absolute()
#             logger.info(f"  输出目录路径为[{destination_dir}]")

#         for pdf_doc_filepath in pdf_doc_filepaths:

#             docx_filepath = pdf_doc_filepath.with_suffix(".docx")
#             if destination_dir:
#                 docx_filepath = destination_dir / docx_filepath.name

#             if docx_filepath.exists():
#                 if overwrite:
#                     docx_filepath.unlink
#                 else:
#                     passed_makeup_filepaths.append(pdf_doc_filepath)
#                     existed_docx_filepath.append(docx_filepath)
#                     index = input_filepaths.index(pdf_doc_filepath)
#                     input_filepaths.insert(index, docx_filepath) 
#                     input_filepaths.remove(pdf_doc_filepath) 

#     if len(passed_makeup_filepaths)>0:
#         logger.warning(f"目标文件已存在的列表（转换前）为({len(passed_makeup_filepaths)})：\n  {' | '.join([str(x) for x in passed_makeup_filepaths])}")
#         logger.warning(f"目标文件已存在的列表（转换后）为({len(existed_docx_filepath)})：\n  {' | '.join([str(x) for x in existed_docx_filepath])}")
#         logger.warning(f"因为转换参数overwrite={overwrite}，以上这些文件将直接跳过转换，如需重新转换并覆盖，请设置overwrite为True!")
#         for pdf_doc_filepath in passed_makeup_filepaths:
#             pdf_doc_filepaths.remove(pdf_doc_filepath)
    
#     if len(pdf_doc_filepaths) > 0:
#         logger.debug('  因存在须转换的doc/pdf文件，建议最好在ms windows下运行，且安装有ms word程序！')
#         for pdf_doc_filepath in pdf_doc_filepaths:
#             docx_filepath = pdf_doc_filepath.with_suffix(".docx")
#             if destination_dir:
#                 docx_filepath = destination_dir / docx_filepath.name
#             try:
#                 if os_name=='Windows':        
#                     import win32com.client        
#                     word = win32com.client.Dispatch("Word.Application")
#                     pdfdoc = word.Documents.Open(str(pdf_doc_filepath),Visible=False)
#                     # https://blog.csdn.net/ynyn2013/article/details/49120731
#                     # wdFormatXMLDocument = 12
#                     # wdFormatDocumentDefault = 16
#                     pdfdoc.SaveAs(str(docx_filepath),12) 
#                     pdfdoc.Close()
#                     word.Quit()
#                 elif os_name=='Linux':
#                     if pdf_doc_filepath.suffix in [".pdf",".doc"]:
#                         convert_doc_or_pdf_to_docx(pdf_doc_filepath,docx_filepath)
#                 else:
#                     raise Exception(f'暂不支持 {os_name} 操作系统,建议在Windows或Linux环境下运行')
#                 converted_makeup_filepaths.append(str(docx_filepath))
#                 index = input_filepaths.index(pdf_doc_filepath)
#                 input_filepaths.insert(index, docx_filepath)  
#                 input_filepaths.remove(pdf_doc_filepath)          
                
#             except Exception as e:
#                 logger.warning(f"无法转换[doc/pdf-->docx]，详细错误信息为{e}")

#     # logger.info(f"有效的原始输入文件列表为({len(original_valid_input_filepaths)})：\n  {' | '.join([str(x) for x in original_valid_input_filepaths])}")  
#     logger.info(f"转换后的相应docx文件列表为({len(converted_makeup_filepaths)})：\n  {' | '.join([str(x) for x in converted_makeup_filepaths])}")
#     logger.info(f"返回新的有效文件列表为({len(input_filepaths)})：\n  {' | '.join([str(x) for x in input_filepaths])}")

#     return input_filepaths,original_valid_input_filepaths

# 需改成批量（多线程或多进程），有些大pdf转换需要好几分钟
# def _convert_file_to_docx(filepath: str, output_filepath:str,overwrite=False, destination_dir=None):
def _convert_file_to_docx(args):
    filepath, overwrite, destination_dir=args
    # 根据文件扩展名进行转换
    logger.warning(f'==*==转换文件{filepath}')
    if Path(filepath).suffix in pandoc_list:
        convert_md_to_docx(filepath, overwrite=overwrite, destination_dir=destination_dir)
    elif Path(filepath).suffix in docpdf_list:
        convert_doc_pdf2docx_on_win_and_linux(filepath,overwrite=overwrite, destination_dir=destination_dir)
    else:
        logger.warning(f"    JqConverter跳过文件转换: {filepath}")

def batch_convert_files_to_docxs(input_filepaths: Union[str, list], overwrite=False, destination_dir=None):
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
    
    # 如果destination_dir没有指定,则目标目录为当前目录
    if destination_dir is None:
        destination_dir = os.getcwd()
        
    input_filepaths = [Path(filepath) for filepath in input_filepaths]
    input_filepaths_exist = [filepath for filepath in input_filepaths if filepath.exists()]
    
    input_filepaths_exist_and_replaced_by_docx_if_converted = []
    batch_params = []
    for filepath in input_filepaths:
        if not Path(filepath).exists():
            logger.info(f"File {filepath} does not exist. Skipping.")
        else:
            # 定义输出的docx文件路径
            base_name = Path(filepath).stem
            ext = Path(filepath).suffix
            if ext in jq_reader_list:
                output_filepath = Path(destination_dir) / f"{base_name}.docx"
                # 检查文件是否存在
                input_filepaths_exist_and_replaced_by_docx_if_converted.append(output_filepath)
                if output_filepath.exists() and not overwrite:
                    logger.info(f"File {output_filepath} already exists. Skipping conversion.")
                else:            
                    batch_params.append((filepath,overwrite,destination_dir))
            else:
                input_filepaths_exist_and_replaced_by_docx_if_converted.append(filepath)
    if batch_params:
        with semaphore:
            pool.map(_convert_file_to_docx,batch_params)
    
    final_input_filepaths_exist=[]
    final_input_filepaths_exist_and_replaced_by_docx_if_converted=[]
    for i,destination_file in enumerate(input_filepaths_exist_and_replaced_by_docx_if_converted):
        if Path(destination_file).exists:
            final_input_filepaths_exist.append(input_filepaths_exist[i])
            final_input_filepaths_exist_and_replaced_by_docx_if_converted.append(destination_file)
        else:
            logger.warning(f'期望的转换后的文件{destination_file}不存在，可能是转换失败了，跳过！')
            
            
    return final_input_filepaths_exist,final_input_filepaths_exist_and_replaced_by_docx_if_converted

##############################################################################################
# lyq 文件转换调用180服务器上部署的方法
import zipfile
from typing import Dict, Any,List

def download_converted_files(file_paths: List[str], output_dir: Path, api_url = winserver_download_url) -> Dict[str, Any]:
    """
    调用API的下载接口获取转换后的文件
    
    Args:
        file_paths: 要下载的文件路径列表
        output_dir: 保存下载文件的目录
    
    Returns:
        Dict with status and results
    """
    try:
        # 确保输出目录存在
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # 调用下载API
        response = requests.post(
            api_url,
            json=file_paths,
            stream=True  # 使用流式下载
        )
        
        if response.status_code == 200:
            # 从response读取zip文件内容
            zip_data = BytesIO(response.content)
            
            # 读取zip并提取文件名和内容
            converted_files = {}
            with zipfile.ZipFile(zip_data) as zip_ref:
                # 遍历zip中的所有文件
                for zip_info in zip_ref.filelist:
                    # 提取文件
                    file_content = zip_ref.read(zip_info.filename)
                    file_path =  os.path.join(output_dir, zip_info.filename)
                    
                    # 保存文件
                    with open(file_path, 'wb') as f:
                        f.write(file_content)
                    
                    converted_files[zip_info.filename] = str(file_path)
            
            if not converted_files:
                return {
                    "status": "error",
                    "message": "ZIP文件中没有找到任何文件"
                }
            
            return {
                "status": "success",
                "message": "文件下载成功",
                "files": converted_files
            }
            
        else:
            error_detail = response.json().get('detail', '未知错误')
            return {
                "status": "error",
                "message": f"下载失败: {error_detail}",
                "status_code": response.status_code
            }
            
    except Exception as e:
        logger.error(f"下载文件时发生错误: {str(e)}")
        return {
            "status": "error",
            "message": f"处理过程中发生错误: {str(e)}"
        }


def convert_doc_pdf2docx_on_win_and_linux(input_filepaths:Union[str,list],overwrite=True,destination_dir=None,api_url=winserver_convert_url): 
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
            # Convert file using API
            try:
                with open(pdf_doc_filepath, 'rb') as f:
                    files = {'files': (pdf_doc_filepath.name, f)}
                    response = requests.post(api_url, files=files)
                    
                    if response.status_code == 200:
                        result = response.json()
                        if result['success_count'] > 0:
                            # Save the converted file
                            docx_path = result['results'][0].get('docx_path', '')  # Assuming API returns base64 or binary content
                            if docx_path:
                                download_converted_files([docx_path], docx_filepath.parent)

        
                        else:
                            logger.warning(f"转换失败: {result.get('message', '未知错误')}")
                    else:
                        logger.warning(f"API调用失败，状态码: {response.status_code=},{response.text=}")
                        
            except Exception as e:
                logger.warning(f"转换失败，详细错误信息为: {str(e)}")

    # logger.info(f"有效的原始输入文件列表为({len(original_valid_input_filepaths)})：\n  {' | '.join([str(x) for x in original_valid_input_filepaths])}")  
    logger.info(f"转换后的相应docx文件列表为({len(converted_makeup_filepaths)})：\n  {' | '.join([str(x) for x in converted_makeup_filepaths])}")
    logger.info(f"返回新的有效文件列表为({len(input_filepaths)})：\n  {' | '.join([str(x) for x in input_filepaths])}")

    return input_filepaths,original_valid_input_filepaths


if __name__ == "__main__":
    # pdf_filepaths = [fr"/media/temp/软件开发成本度量规范.pdf"]
    pdf_filepaths = [fr"/media/temp/A105-45民政部低收入家庭认定指导中心.pdf",
                     fr"/media/temp/软件开发成本度量规范.pdf"]
    destination_dir = '/media/temp/'
    doc_filepaths = convert_doc_pdf2docx_on_win_and_linux(pdf_filepaths,overwrite=True, destination_dir=destination_dir)

    pass

    # files = ["/media/temp/软件开发成本度量规范.pdf", 
    #          "/media/temp/户口本接口文档.pdf",
    #          "/media/temp/发票识别接口文档.md",
    #          "/media/temp/OCR接口性能报告.doc"]

    # batch_convert_files_to_docxs(files, overwrite=True, destination_dir='/media/temp/docxfiles/')


    # pdf_filepaths = [fr"/media/temp/软件开发成本度量规范.pdf"]
    # destination_dir = '/media/temp/'
    # doc_filepaths = convert_doc_pdf2docx_on_win_and_linux(pdf_filepaths,overwrite=True, destination_dir=destination_dir)


