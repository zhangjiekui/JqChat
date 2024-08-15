
import asyncio
from typing import List
from fastapi import APIRouter, Body, File, Form, Request,Response, UploadFile

import os
from fastapi.responses import JSONResponse
import requests
import asyncio
import logging
from jqchat.kernel_program.main import APP_PORT as KERNEL_APP_PORT
from jqcode.jq_agent.c0_init_env_models import env_models_instance
from jqchat.chat_prompt import *
from jqcode.jq_knowledge_manegement.chatchat.server.db.repository.knowledge_base_repository import get_kb_detail
from langchain_core.messages import ToolMessage

from langgraph_in_class import GraphAgent



# We know this Flask app is for local use. So we can disable the verbose Werkzeug logger
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

chat_router = APIRouter(prefix="/chat", tags=["Chat对话"])

# 
@chat_router.post('/completions',summary="对话接口")
def completions(
    user_prompt: str = Body(alias="query",description="用户输入"),
    doc_id: str = Body(alias="doc", description="知识库ID"),
    user_id: str = Body(alias="user", description="用户随机ID"),
    ):
    print('============================================================')
    print('=============开始后台逻辑中....请稍后...........==============')
    print(f'====用户的问题是: {user_prompt}=============================')
    print(f'====所选的知识库是: {doc_id}================================')
    print(f'====用户的ID是：{user_id}===================================')
    print('============================================================')
    kb_base=get_kb_detail(doc_id)
      #获得知识库的字典{"name": "test" , "discription":"测试方面的知识库",...}
    kb_base_dict={}
    if(len(kb_base)>0):
        kb_base_dict={"name": kb_base['kb_name'] , "vs_type":kb_base['vs_type'],"discription":kb_base['kb_info']}
    chat_bot = GraphAgent(memory_thread_id=user_id, kb_base_dict=kb_base_dict)
    print(f"{chat_bot.user_id=}")
    text = chat_bot.run_conversation(user_question=user_prompt)
    # chat_bot.graph.update_state()
    messages = chat_bot.get_all_history_messages()

    last_message = messages[-1]
    if isinstance(last_message,ToolMessage):
        if last_message.name == 'CODE_EXECUTION':
            kwargs = last_message.additional_kwargs
            question_id = kwargs.get("question_id")
            if question_id == chat_bot.question_id:
                code_text = kwargs.get("code_text","")
                if code_text:
                    text = code_text + '\n' + text


    return JSONResponse(content={"text":text},status_code=200)

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