import os
import base64
import requests
import numpy as np
from loguru import logger
from joblib import Parallel, delayed
from typing import Union
from pathlib import Path
from pdf2docx import Converter
import subprocess
import multiprocessing
# lock = multiprocessing.Lock()
import threading
lock = threading.Lock()



from jqcode.jq_utils.logger import jqkj_logger
logger = jqkj_logger(__file__).get_logger()


# region

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

# 原始代码
# def convert_doc_or_pdf_to_docx(src_doc_file_path:Union[str,Path],saved_doc_file_path:Union[str,Path]=None):
#     src_doc_file_path = str(src_doc_file_path)
#     src_doc_file_path_copyed = src_doc_file_path.replace(" ",'')
#     if src_doc_file_path_copyed != src_doc_file_path:
#         if os.path.isfile(src_doc_file_path) and not os.path.exists(src_doc_file_path_copyed):
#             os.rename(src_doc_file_path,src_doc_file_path_copyed)
        
        
#     src_doc_file_path = Path(src_doc_file_path_copyed)
#     ext = src_doc_file_path.suffix
#     if not saved_doc_file_path:
#         saved_doc_file_path = src_doc_file_path.with_suffix(".docx")
#     outdir = saved_doc_file_path.parent
#     if ext=='.pdf':
#         command = f"libreoffice --infilter='writer_pdf_import' --headless --convert-to docx {src_doc_file_path} --outdir {outdir}"
#     if ext=='.doc':
#         command = f"libreoffice --headless --convert-to docx {src_doc_file_path} --outdir {outdir}"
#     try:
#         with lock:
#             message = subprocess.run(command, shell=True, check=True,capture_output=True)
#             if message.returncode!=0 or "Error" in str(message.stderr):
#                 raise Exception(f"使用libreoffice转换{ext}文件{src_doc_file_path}失败！详细信息为：{message.stderr}")
#             else:
#                 logger.warning(f"使用libreoffice成功将{src_doc_file_path}转换为{saved_doc_file_path}")
#     except Exception as e:
#         stderr = '无'
#         try:
#             stderr = e.stderr
#         except:
#             pass
#         logger.warning(f"将{src_doc_file_path}转换为{saved_doc_file_path}出错：{e=}，e.stderr={stderr}")


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

# endregion
####################################################################################################
# lyq
import subprocess
import os
from pathlib import Path
from typing import Union
import requests
from jqcode.jq_utils.logger import jqkj_logger
logger = jqkj_logger(__file__).get_logger()

def to_b64(file_path):
    try:
        with open(file_path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')
    except Exception as e:
        raise Exception(f'File: {file_path} - Info: {e}')
    
def find_file_in_directory(directory, target_filename):
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file == target_filename:
                file_path = os.path.join(root, file)
                print(f"File found: {file_path}")
                return file_path
    return ''

def predict(file_path,**kwargs):
    url = os.getenv("pdf_parse_url", "http://10.1.150.105:8888/predict") 
    url = "http://10.1.150.105:8888/predict" 
    url = "http://localhost:8889/predict"
    file_path = str(file_path)
    print(url)
    print(str(file_path))
    # file64=to_b64(str(file_path))
    kwargs.update({"parse_method":'auto'})
    try:
        response = requests.post(url, json={
            # 'file':file64,
            'file':file_path,
            'kwargs': kwargs
        })

        if response.status_code == 200:
            output = response.json()
            output['src_pdf_filepath'] = file_path
            return output
        else:
            raise Exception(response.text)
    except Exception as e:
        logger.error(f'File: {file_path} - Info: {e}')
        
def do_parse_paralyzed(pdf_file_paths:list):
    if not isinstance(pdf_file_paths,list):
       pdf_file_paths = [pdf_file_paths] 
    n_jobs = np.clip(len(pdf_file_paths),1, 8)
    results = Parallel(n_jobs, prefer='threads', verbose=10)(
        delayed(predict)(p) for p in pdf_file_paths
    )
    return results
     
        
def convert_doc_or_pdf_to_docx(src_doc_file_path: Union[str, Path], saved_doc_file_path: Union[str, Path] = None):
    src_doc_file_path = Path(src_doc_file_path)
    saved_doc_file_path = Path(saved_doc_file_path)
    if not saved_doc_file_path or not saved_doc_file_path.suffix == '.docx':
        saved_doc_file_path = src_doc_file_path.with_suffix(".docx")

    # 调用FastAPI服务进行转换
    try:
        # url = os.getenv("pdf_parse_url", "http://10.1.150.105:8888/pdf_parse")  # 调整为你的服务地址
        # with open(src_doc_file_path, 'rb') as f:
        #     files = {'pdf_file': (os.path.basename(src_doc_file_path), f)}
        #     response = requests.post(url, files=files, data={
        #         'parse_method': 'auto',
        #         'output_dir': outdir
        #     })

        #     # logger.info(f"FastAPI返回的响应内容: {response.json()}")

        # if response.status_code != 200:
        #     raise Exception(f"调用pdf_parse FastAPI服务失败: {response.json().get('error', '未知错误')}")

        # 获取生成的md文件路径
        # md_file_path = Path(outdir) / f"{src_doc_file_path.stem}.md"
        # with open(md_file_path, 'w', encoding='utf-8') as md_file:
        #     md_file.write(response.json()['md_content'])
        #     logger.warning(f"pdf_parse转换(pdf=>md {src_doc_file_path} 到 {md_file_path})成功！")
        
        

        # 使用pandoc将md文件转换为docx
        saved_doc_file_path = saved_doc_file_path 
        # output = do_parse(src_doc_file_path,outdir=outdir)
        results = do_parse_paralyzed(src_doc_file_path)
        for result in results:
            output_dir = result['output_dir']
            abs_dir = f'/tmp/mineru/{output_dir}'
            md_file_name = f'{output_dir}.md'
            md_file_path = find_file_in_directory(abs_dir,md_file_name)
            md_file_path = Path(md_file_path)
            
            if md_file_path.exists():
                logger.warning(f"开始转换 {md_file_path} 到 {saved_doc_file_path}")
                command = f"pandoc {md_file_path} -o {saved_doc_file_path}"
                try:
                    message = subprocess.run(command, shell=True, check=True, capture_output=True)
                    logger.warning(f"转换成功: {saved_doc_file_path}")

                    # 删除中间生成的 md 文件
                    try:
                        os.remove(md_file_path)
                        logger.info(f"已删除中间文件: {md_file_path}")
                    except Exception as e:
                        logger.warning(f"删除中间文件失败: {e}")

                except subprocess.CalledProcessError as e:
                    logger.error(f"转换失败: {e.stderr}")
            else:
                logger.warning(f"pdf_parse转换(pdf=>md {src_doc_file_path} 到 {md_file_path})失败！")

    except Exception as e:
        logger.error(f"转换过程中出现错误: {e}")

        # 如果转换过程出错，也尝试清理中间文件
        try:
            if 'md_file_path' in locals() and md_file_path.exists():
                os.remove(md_file_path)
                logger.info(f"已删除中间文件: {md_file_path}")
        except Exception as cleanup_error:
            logger.warning(f"清理中间文件失败: {cleanup_error}")

        raise



if __name__ == "__main__":
    # doc_filepath = fr"/data/projects/JqChat/test_zh.doc"
    # convert_doc_or_pdf_to_docx(doc_filepath)
    pdf_filepaths = [
    # fr"/data/projects/JqChatV2/workspace/knowledge_base/jqtech_kb/content/基于网络消费者信息需求模型的网站导航问题研究批准书.pdf",
    # fr"/data/projects/JqChatV2/workspace/knowledge_base/jqtech_kb/content/基于网络消费者信息需求模型的网站导航问题研究 批准书.pdf",
    # fr"/data/projects/JqChatV2/workspace/knowledge_base/jqtech_kb/content/基于主动协作关系的网络用户建模及模型优化方法研究 批准书.pdf",
    # fr"/data/projects/JqChatV2/workspace/knowledge_base/fileconvert/content/安徽低收入文件.pdf",
    # fr"/data/projects/JqChatV2/workspace/knowledge_base/jqtech_kb/content/基于数字孪生的居家养老和虚拟诊所建设方案.doc",
    # fr'/media/program/pdffiles/创业软件.pdf'
    # fr'/media/program/pdffiles/test.pdf'
    # fr'/media/program/pdffiles/“主动健康和老龄化科技应对”重点专项2.pdf'
    fr"/data/projects/JqChatV2/workspace/knowledge_base/test_pdf/content/创业软件.pdf",
    fr"/data/projects/JqChatV2/workspace/knowledge_base/test_pdf/content/安徽低收入文件.pdf"
    ]
    
    results = do_parse_paralyzed(pdf_filepaths)
    

    out = '/data/projects/JqChatV2/workspace/temp'
    # for file in pdf_filepaths:
    #     convert_doc_or_pdf_to_docx(Path(file), Path(out))
    #     # convert_doc_or_pdf_to_docx(Path(file))