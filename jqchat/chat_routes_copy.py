

import os
from typing import Dict, List
from fastapi import APIRouter, Body, File, Form, UploadFile
from fastapi.responses import JSONResponse
import pandas as pd


UPLOAD_FOLDER = 'workspace/'
READER_MAP = {
    '.csv': pd.read_csv,
    '.tsv': pd.read_csv,
    '.xlsx': pd.read_excel,
    '.xls': pd.read_excel,
    '.xml': pd.read_xml,
    '.json': pd.read_json,
    '.hdf': pd.read_hdf,
    '.hdf5': pd.read_hdf,
    '.feather': pd.read_feather,
    '.parquet': pd.read_parquet,
    '.pkl': pd.read_pickle,
    '.sql': pd.read_sql,
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
    
) :

    # user_prompt = request.json.get('prompt', '')
    print(user_prompt,doc_id,user_id)
    code=f"""
    ```python 
    #!/usr/bin/env python3
    print('Hello, World!');
    
    ```
    """
    text=f"""
Markdown 标题：
# 这是 H1
    """
    resp=JSONResponse(content={"code":code,"text":user_prompt+text})
    print("*"*30)
    print(resp)
    return resp

usual_imports = """import numpy as np \nimport pandas as pd\nimport seaborn as sns\nimport matplotlib.pyplot as plt\n"""


@chat_router.post('/upload',summary="上传接口")
async def upload_file(
     files: List[UploadFile] = File(..., description="上传文件，支持多文件"),
     knowbase_id: str = Form(None, description="知识库ID"),
     uid: str = Form(None, description="用户ID"),
    ):
    for file in files:
        if file.filename == '':
            return ({'error': '请选择文件'}), 400
        if file and allowed_file(file.filename):
            file_target = os.path.join(UPLOAD_FOLDER, file.filename)
            file_content = await file.read()
            with open(file_target, "wb") as f:  
                 f.write(file_content)  
            # file_info = inspect_file(file_target)
            os.environ["HAS_DATA_FILE_UPLOADED"] = 'True'
            # message_buffer.append(f"已上传保存的文件名为{file.filename},请在分析过程中使用这个数据文件\n{file_info}'}" + "\n\n")
        else:
            return JSONResponse(content={'message': '存在不被允许的文件类型'}, status_code=400)

    return JSONResponse(content={'message': f'上传成功'}, status_code=200)
