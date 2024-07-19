import os
import platform
from typing import Union
from pathlib import Path

from jqcode.jq_readers.backend_reader_utils.jqkj_doc_pdf2docx_on_linux import convert_pdf_to_docx,convert_doc_to_docx
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

def convert_doc_pdf2docx_using_WinWord(input_filepaths:Union[str,list],overwrite=True,destination_dir=None):
    """
    Convert pdf or doc file(s) to docx file(s) using windows word application through pywin32.win32com
    在windows下运行，利用word程序将:
        (1)doc转换为docx，这样后续能使用Python-docx进行处理
        (2)pdf转换为docx，这样能获得标题目录信息
    在Linux环境下运行，依赖:
        (1)pdf-->docx 依赖pdf2docx包: pip install pdf2docx
        (2)doc-->docx 依赖spire.doc包: pip install spire.doc，但这个是收费的
    :param pdf_filepaths: str or list. pdf/doc file path(s)
    :return: (docx file path(s),valid_input_filepaths)
    """
    
    not_exist_filepaths = []
    passed_pdf_doc_filepaths = []
    existed_docx_filepath = []
    converted_pdf_doc_filepaths = []   
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
            logger.info(f"输出目录路径为[{destination_dir}]")

        for pdf_doc_filepath in pdf_doc_filepaths:

            docx_filepath = pdf_doc_filepath.with_suffix(".docx")
            if destination_dir:
                docx_filepath = destination_dir / docx_filepath.name

            if docx_filepath.exists():
                if overwrite:
                    docx_filepath.unlink
                else:
                    passed_pdf_doc_filepaths.append(pdf_doc_filepath)
                    existed_docx_filepath.append(docx_filepath)
                    index = input_filepaths.index(pdf_doc_filepath)
                    input_filepaths.insert(index, docx_filepath) 
                    input_filepaths.remove(pdf_doc_filepath) 

    if len(passed_pdf_doc_filepaths)>0:
        logger.warning(f"目标文件已存在的列表（转换前）为({len(passed_pdf_doc_filepaths)})：\n  {' | '.join([str(x) for x in passed_pdf_doc_filepaths])}")
        logger.warning(f"目标文件已存在的列表（转换后）为({len(existed_docx_filepath)})：\n  {' | '.join([str(x) for x in existed_docx_filepath])}")
        logger.warning(f"因为转换参数overwrite={overwrite}，以上这些文件将直接跳过转换，如需重新转换并覆盖，请设置overwrite为True!")
        for pdf_doc_filepath in passed_pdf_doc_filepaths:
            pdf_doc_filepaths.remove(pdf_doc_filepath)
    
    if len(pdf_doc_filepaths) > 0:
        logger.warning('因存在须转换的doc/pdf文件，建议最好在ms windows下运行，且安装有ms word程序！')
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
                    if pdf_doc_filepath.suffix == ".pdf":
                        convert_pdf_to_docx(pdf_doc_filepath,docx_filepath)                    
                    if pdf_doc_filepath.suffix == ".doc":
                        convert_doc_to_docx(pdf_doc_filepath,docx_filepath)
                else:
                    raise Exception(f'暂不支持 {os_name} 操作系统,建议在Windows或Linux环境下运行')


                converted_pdf_doc_filepaths.append(str(docx_filepath))
                index = input_filepaths.index(pdf_doc_filepath)
                input_filepaths.insert(index, docx_filepath)  
                input_filepaths.remove(pdf_doc_filepath)          
                
            except Exception as e:
                logger.warning(f"无法转换[doc/pdf-->docx]，详细错误信息为{e}")

    logger.info(f"有效的原始输入文件列表为({len(original_valid_input_filepaths)})：\n  {' | '.join([str(x) for x in original_valid_input_filepaths])}")  
    logger.info(f"转换后的相应docx文件列表为({len(converted_pdf_doc_filepaths)})：\n  {' | '.join([str(x) for x in converted_pdf_doc_filepaths])}")
    logger.info(f"返回新的有效文件列表为({len(input_filepaths)})：\n  {' | '.join([str(x) for x in input_filepaths])}")

    return input_filepaths,original_valid_input_filepaths


if __name__ == "__main__":
    pdf_filepaths = [fr'D:\biaoshu\pdf_docx_convert\UserGuide.docx',fr'C:\Users\zjk\Desktop\桌面临时文档\temp文件\厦门市集美区\厦门市智慧民政一体化平台项目建设方案 V3.6.doc',fr'D:\biaoshu\pdf_docx_convert\UserGuide.pdf',fr'D:\biaoshu\pdf_docx_convert\InstallationGuide.pdf',fr'D:\biaoshu\pdf_docx_convert\baichuan.pdf']
    # doc_filepaths = convert_pdf2docx_using_Win32WordApp(pdf_filepaths)
    pdf_filepaths = [fr"/data/projects/JqChat/test_en.pdf",fr"/data/projects/JqChat/test_zh.doc"]
    doc_filepaths = convert_doc_pdf2docx_using_WinWord(pdf_filepaths,overwrite=True)

