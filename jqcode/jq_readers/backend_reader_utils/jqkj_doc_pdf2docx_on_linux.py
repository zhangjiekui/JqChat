from typing import Union
from pathlib import Path
from pdf2docx import Converter
import subprocess
import os


from jqcode.jq_utils.logger import jqkj_logger
logger = jqkj_logger(__file__).get_logger()

## 安装libreoffice
#1 sudo apt install libreoffice
#2 看看本机是否装有java，运行java --version 如果有正常输出就可以，以下是输出信息
    # --------------------
    # openjdk 11.0.23 2024-04-16
    # OpenJDK Runtime Environment (build 11.0.23+9-post-Ubuntu-1ubuntu122.04.1)
    # OpenJDK 64-Bit Server VM (build 11.0.23+9-post-Ubuntu-1ubuntu122.04.1, mixed mode, sharing)
    # --------------------
#3 sudo apt install libreoffice-java-commo
#4 测试是否成功：libreoffice --headless --convert-to docx /data/projects/JqChat/test_zh.doc --outdir /data/projects/JqChat/ 

def convert_doc_or_pdf_to_docx(src_doc_file_path:Union[str,Path],saved_doc_file_path:Union[str,Path]=None):
    src_doc_file_path = str(src_doc_file_path)
    src_doc_file_path_copyed = src_doc_file_path.replace(" ",'')
    if src_doc_file_path_copyed != src_doc_file_path:
        if os.path.isfile(src_doc_file_path) and not os.path.exists(src_doc_file_path_copyed):
            os.rename(src_doc_file_path,src_doc_file_path_copyed)
        
        
    src_doc_file_path = Path(src_doc_file_path_copyed)
    ext = src_doc_file_path.suffix
    if not saved_doc_file_path:
        saved_doc_file_path = src_doc_file_path.with_suffix(".docx")
    outdir = saved_doc_file_path.parent
    if ext=='.pdf':
        command = f"libreoffice --infilter='writer_pdf_import' --headless --convert-to docx {src_doc_file_path} --outdir {outdir}"
    if ext=='.doc':
        command = f"libreoffice --headless --convert-to docx {src_doc_file_path} --outdir {outdir}"
    message = subprocess.run(command, shell=True, check=True,capture_output=True)
    if message.returncode!=0 or "Error" in str(message.stderr):
        raise Exception(f"使用libreoffice转换{ext}文件{src_doc_file_path}失败！详细信息为：{message.stderr}")
    else:
        logger.warning(f"使用libreoffice成功将{src_doc_file_path}转换为{saved_doc_file_path}")


# 以下是使用spire.doc进行转换的代码
    # from spire.doc import *
    # from spire.doc.common import *
    # document = Document()
    # # Load a Word DOC file
    # document.LoadFromFile(str(src_doc_file_path))
    # # Save the DOC file to DOCX format
    # document.SaveToFile(str(saved_doc_file_path), FileFormat.Docx2016)
    # # Close the Document object
    # document.Close()


def _convert_pdf_to_docx(src_pdf_file_path:Union[str,Path],saved_doc_file_path:Union[str,Path]=None,multi_processing:bool=True,cpu_count:int=4, delete_end_line_hyphen:bool=True):
    src_pdf_file_path = Path(src_pdf_file_path)
    if not saved_doc_file_path:
        saved_doc_file_path = src_pdf_file_path.with_suffix(".docx")
    cv = Converter(src_pdf_file_path)
    settings = cv.default_settings
    # settings.update({"multi_processing":multi_processing,"cpu_count":cpu_count})
    settings = {"multi_processing":multi_processing,"cpu_count":cpu_count,"delete_end_line_hyphen":delete_end_line_hyphen} 
    cv.convert(saved_doc_file_path,**settings)
    # print(f"{saved_doc_file_path=}")
    cv.close()

if __name__ == "__main__":
    # doc_filepath = fr"/data/projects/JqChat/test_zh.doc"
    # convert_doc_or_pdf_to_docx(doc_filepath)
    pdf_filepaths = [fr"/data/projects/JqChatV2/workspace/knowledge_base/jqtech_kb/content/基于网络消费者信息需求模型的网站导航问题研究批准书.pdf",
                     fr"/data/projects/JqChatV2/workspace/knowledge_base/jqtech_kb/content/基于网络消费者信息需求模型的网站导航问题研究 批准书.pdf",
                     fr"/data/projects/JqChatV2/workspace/knowledge_base/jqtech_kb/content/基于主动协作关系的网络用户建模及模型优化方法研究 批准书.pdf",
                     fr"/data/projects/JqChatV2/workspace/knowledge_base/jqtech_kb/content/安徽低收入文件.pdf",
                     fr"/data/projects/JqChatV2/workspace/knowledge_base/jqtech_kb/content/基于数字孪生的居家养老和虚拟诊所建设方案.doc"
                    ]
    for file in pdf_filepaths:
        convert_doc_or_pdf_to_docx(file)
        convert_doc_or_pdf_to_docx(Path(file))

    
