

import json
import os
from typing import Dict, List
import uuid
from fastapi import APIRouter, Body, File, Form, Response, UploadFile
from fastapi.responses import JSONResponse
import pandas as pd
import requests

from jqcode.jq_knowledge_manegement.chatchat.server.db.repository.knowledge_base_repository import get_kb_detail, load_kb_from_db
from jqcode.jq_knowledge_manegement.chatchat.server.knowledge_base.kb_service.base import get_kb_details


UPLOAD_FOLDER = 'workspace/'
READER_MAP = {
    '.csv': pd.read_csv,
    '.xlsx': pd.read_excel,
    '.xls': pd.read_excel,
    '.docx':pd.read_hdf,
    '.doc':pd.read_hdf,
    '.pdf':pd.read_hdf
}

def allowed_file(filename):
    _, ext = os.path.splitext(filename)
    if ext in READER_MAP.keys():
        return True
    else:
        return False
def inspect_file(filename: str) -> str:
    _, ext = os.path.splitext(filename)
    try:
        df = READER_MAP[ext.lower()](filename)
        return f'The file contains the following columns: {", ".join(df.columns)}'
    except KeyError:
        return ''  # unsupported file type
    except Exception:
        return ''  # file reading failed. - Don't want to know why.
chat_router = APIRouter(prefix="/chat", tags=["Chat对话"])



@chat_router.post("/completions", summary="对话接口")
async def chat_completions(
    user_prompt: str = Body(alias="query",description="用户输入"),
    doc_id: str = Body(alias="doc", description="知识库ID"),
    user_id: str = Body(alias="user", description="用户随机ID"),
    files: List[str]=Body(alias="files",description="文档ID",default=None),
    code_message:str=Body(alias="code_message",default= None, description="执行code的信息"),
    
) :
    print('============================================================')
    print('=============开始后台逻辑中....请稍后...........==============')
    print(f'====用户的问题是: {user_prompt}=============================')
    print(f'====所选的知识库是: {doc_id}================================')
    print(f'====用户的ID是：{user_id}===================================')
    print(f'====执行Code的信息：{code_message}==========================')
    print(f'====文件的信息：{files}==========================')
    print('============================================================')
    code=f"""
    ```python 
    #!/usr/bin/env python3
    print('Hello, World!');
    ```
    """
    text=f"""Markdown 标题：# 这是 H1  """
    kb_base=get_kb_detail(doc_id)
    load_kb_from_db(doc_id)
    kbs=get_kb_details()
    print(kb_base)
    resp=JSONResponse(content={"code":code,"text":user_prompt+text})
    return resp

usual_imports = """import numpy as np \nimport pandas as pd\nimport seaborn as sns\nimport matplotlib.pyplot as plt\n"""


@chat_router.post('/upload',summary="上传接口")
async def upload_file(
      files: List[UploadFile] = File(..., description="上传文件，支持多文件"),
     knowledge_id: str = Body(None, description="知识库ID"),
     uid: str = Body(None, description="用户ID"),
    ):
    ids=[]
    for file in files:
        if file.filename == '':
            return ({'error': '请选择文件'}), 400
        if file and allowed_file(file.filename):
            new_filename=uuid.uuid1().hex+"."+file.filename.split(".")[1]
            file_target = os.path.join(UPLOAD_FOLDER, new_filename)
            file_content = await file.read()
            with open(file_target, "wb") as f:  
                 f.write(file_content)  
                 if knowledge_id :
                     print('需要纳入知识库，待处理',knowledge_id)
                 ids.append(new_filename)
            # file_info = inspect_file(file_target)
            os.environ["HAS_DATA_FILE_UPLOADED"] = 'True'
            # message_buffer.append(f"已上传保存的文件名为{file.filename},请在分析过程中使用这个数据文件\n{file_info}'}" + "\n\n")
        else:
            return JSONResponse(content={'message': '存在不被允许的文件类型'}, status_code=400)

    return JSONResponse(content={'message': f'上传成功',"files":ids}, status_code=200)

KERNEL_API_BASE = os.getenv("KERNEL_API_BASE",'http://localhost')
API_PORT = os.getenv("API_PORT",5011)
kernel_api_url = f"{KERNEL_API_BASE}:{API_PORT}/api"

@chat_router.post('/code',summary="获取code执行结果")
def code():
    resp = requests.get(kernel_api_url)
    excluded_headers = ['content-encoding',
                        'content-length', 'transfer-encoding', 'connection']
    headers = [(name, value) for (name, value) in resp.raw.headers.items()
               if name.lower() not in excluded_headers]
    results= {"results":[{"type":"message","value":"ECEPTION!!"},{"type":"image/png","value":"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"}]}
    # results= {"results":[]}
    return JSONResponse(content=results, status_code=200)