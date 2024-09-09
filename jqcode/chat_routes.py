
import asyncio
from typing import List
from urllib import response
import uuid
from fastapi import APIRouter, Body, File, Form,  UploadFile

import os
from fastapi.responses import JSONResponse
import asyncio
import logging

import requests
from jqcode.chat_prompt import *
from jqcode.jq_knowledge_manegement.chatchat.server.db.repository.knowledge_base_repository import get_kb_detail
from langchain_core.messages import ToolMessage

from jqcode.langgraph_in_class import GraphAgent

from jqcode.jq_utils.logger import jqkj_logger
logger = jqkj_logger(__file__).get_logger()



# We know this Flask app is for local use. So we can disable the verbose Werkzeug logger
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

chat_router = APIRouter(prefix="/chat", tags=["Chat对话"])

# 
@chat_router.post('/completions',summary="对话接口")
def completions(
    user_prompt: str = Body(alias="query",description="用户输入"),
    es_index_name: str = Body(alias="doc", description="知识库ID"),
    user_id: str = Body(alias="user", description="用户随机ID"),
    files: List[str]=Body(alias="files",description="文档ID",default=None),
    code_message:str=Body(alias="code_message",default= None, description="执行code的信息"),
    ):
    print('============================================================')
    print('=============开始后台逻辑中....请稍后...........==============')
    print(f'====用户的问题是: {user_prompt}=============================')
    print(f'====所选的知识库是: {es_index_name}================================')
    print(f'====用户的ID是：{user_id}===================================')
    print(f'====执行Code的信息：{code_message}==========================')
    print(f'====文件的信息：{files}==========================')
    
    print('============================================================')
    # samples是示例知识库，不在数据库中，存在本地文件中，所以查不到
    kb_base_dict={}
    kb_base=get_kb_detail(es_index_name)
      #获得知识库的字典{"name": "test" , "discription":"测试方面的知识库",...}    
    if(len(kb_base)>0):
        kb_base_dict={"name": kb_base['kb_name'] , "vs_type":kb_base['vs_type'],"discription":kb_base['kb_info']}
    else:
        logger.warning("未能正确获取到kb_base和kb_base_dict，下面使用自己构造的kb_base_dict")
        kb_base_dict={"name": "zjk_jqesclient_test" , "vs_type":"ES","discription":"A vectorstore/knowledge base containing documents related to 晶奇公司、安徽晶奇网络科技股份有限公司、医疗卫生、医疗健康、医疗服务、医疗政策、medical treatment & health. 凡是与晶奇公司、安徽晶奇网络科技股份有限公司及医疗健康相关的问题，都必须使用vectorstore工具。MUST use the vectorstore for questions on these topics."}
    print(kb_base_dict)
    # 是否有文件
    add_docs_list_to_kb = False
    chat_on_docs_list=[]
    if len(files)>0:
        add_docs_list_to_kb=True
        for file in files:
            file=os.path.join(UPLOAD_FOLDER, file)
            chat_on_docs_list.append(file)
    print(chat_on_docs_list)
    chat_bot = GraphAgent(memory_thread_id=user_id, kb_base_dict=kb_base_dict,chat_on_docs_list=chat_on_docs_list,add_docs_list_to_kb=add_docs_list_to_kb)
    print(f"{chat_bot.user_id=}")
    text = chat_bot.run_conversation(user_question=user_prompt)
    code = ''
    # chat_bot.graph.update_state()

    # returned_str
    messages = chat_bot.get_all_history_messages()

    last_message = messages[-1]
    if isinstance(last_message,ToolMessage):
        if last_message.name == 'CODE_EXECUTION':
            kwargs = last_message.additional_kwargs
            question_id = kwargs.get("question_id")
            if question_id == chat_bot.question_id:
                code_text = kwargs.get("code_text","")
                code = kwargs.get("code","")
                if code_text:
                    text = code_text + '\n' + text
    # return JSONResponse(content={"text":text},status_code=200)
    return JSONResponse(content={"text":text,"code":code},status_code=200)

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
            new_filename=uuid.uuid1().hex + "." + file.filename.rsplit(".",1)[1]
            file_target = os.path.join(UPLOAD_FOLDER, new_filename)
            file_content = await file.read()
            with open(file_target, "wb") as f:  
                 f.write(file_content)  
                 if knowledge_id :
                    #  TODO:
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
    results=resp.json()
    return JSONResponse(content=results, status_code=200)

@chat_router.post('/download/{file}',summary="获取执行code生成的文件")
def downlaod(file):
    file_path = os.path.join(UPLOAD_FOLDER, file)
    with open(file_path, "rb") as file:
        contents = file.read()
        response.headers["Content-Disposition"] = f"attachment; filename={file_path}"
        response.body = contents
        return response
