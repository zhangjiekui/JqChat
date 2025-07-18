from joblib import Parallel, delayed
from pathlib import Path
import numpy as np
import requests
import subprocess
import json_repair

from jqcode.jq_utils.logger import jqkj_logger
logger = jqkj_logger(__file__).get_logger()

files = ["/data/projects/JqChatV2/workspace/knowledge_base/test_pdf/content/安徽低收入文件.docx",
         "/data/projects/JqChatV2/workspace/knowledge_base/test_pdf/content/创业软件.pdf",
         "/data/projects/JqChatV2/workspace/knowledge_base/test_pdf/content/创业软件2.pdf",
         "/data/projects/JqChatV2/workspace/knowledge_base/test_pdf/content/GBT36964-2018软件工程软件开发成本度量规范.pdf",         
         '/data/projects/JqChatV2/JqChat/jqcode/jq_kbe_manegement/data/knowledge_base/samples/content/llm/大模型推理优化策略.md',
         '/data/projects/JqChatV2/JqChat/jqcode/jq_kbe_manegement/data/knowledge_base/samples/content/llm/分布式训练技术原理.md'
         ]
# files = ['a1.pdf','a2.pdf','b1.md','b2.md','c1.html','c2.html','d1.txt','d2.py','e1.docx','e2.docx']
pdf_files = [file for file in files if Path(file).suffix in ['.pdf']]
pandoc_files = [file for file in files if Path(file).suffix in ['.md','.html']]
_converted_files = pdf_files + pandoc_files
final_files = [file for file in files if Path(file).suffix in _converted_files]

def conver_pdf_to_docx(file):
    url = "http://localhost:8889/predict"
    logger.warning(f"conver_pdf_to_docx:{file}......") 
    kwargs = {}   
    try:
        response = requests.post(url, json={
            'file':file,
            'kwargs': kwargs
        })
        
        if response.status_code == 200:
            res_dict = json_repair.loads(response.text)
            converted_file_md = res_dict["output_md_filepath"]
            converted_file_docx = conver_pandoc_to_docx(converted_file_md) 
            # pandoc_files.append(converted_file)
            return converted_file_docx
        else:
            raise Exception(response.text)
    except Exception as e:
        logger.warning(f"conver_pdf_to_md:{file}失败:{e}")        
    
    
def convert_pdf_to_docx_paralyzed(pdf_file_paths:list):
    n_jobs = np.clip(len(pdf_files),1, 8)
    results = Parallel(n_jobs, prefer='threads', verbose=10)(
        delayed(conver_pdf_to_docx)(p) for p in pdf_file_paths
    )
    return results
    
def conver_pandoc_to_docx(file):
    logger.warning(f"conver_pandoc_to_docx:{file}......")
    try:
        converted_file = str(Path(file).with_suffix('.docx'))
        pandoc_command = f"pandoc -s {file} -o {converted_file}"
        message = subprocess.run(pandoc_command, shell=True, check=True)
        try:
            stderr = message.stderr
        except:
            stderr = ''
        
        if message.returncode!=0 or "Error" in str(stderr):
            _message_str = stderr if stderr else message
            raise Exception(f"使用Pandoc转换将文件{file}转换为'.docx'失败：{_message_str}")
        else:
            # final_files.append(converted_file)
            return converted_file
        
    except Exception as e:
        logger.warning(f"conver_pandoc_to_docx:{file}失败:{e}")  
    

def convert_pandoc_to_docx_paralyzed(pandoc_file_paths:list):
    n_jobs = np.clip(len(_converted_files),1, 8)
    results = Parallel(n_jobs, prefer='threads', verbose=10)(
        delayed(conver_pandoc_to_docx)(p) for p in pandoc_file_paths
    )
    logger.warning(results)
    return results
    
def convert_files_paralyzed():
    n_jobs = 2
    task1 = [convert_pdf_to_docx_paralyzed,[pdf_files],{}]
    task2 = [convert_pandoc_to_docx_paralyzed,[pandoc_files],{}]
    parallel = Parallel(n_jobs, prefer='threads', verbose=10)    
    results = parallel([task1,task2])
    return results

if __name__ == "__main__":
    # def f1(x,y):    
    #     return x+y
    # def f2(x,y):    
    #     return y-x
    # task1 = [f1, [4,10],{}]
    # task2 = [f2,[4,10],{}]
    # works_2 = Parallel(n_jobs=2,backend = 'threading')
    # res = works_2([task1,task2])
    # print(res)
    # convert_pdf_to_md_paralyzed(pdf_files)
    # convert_pandoc_to_docx_paralyzed(pandoc_files)
    results = convert_files_paralyzed()
    print(list(results))
    print(final_files)

    
    
    