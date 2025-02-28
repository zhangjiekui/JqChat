
from typing import List
import uuid
from fastapi import APIRouter, Body, File, Form,  UploadFile
import os
from fastapi.responses import JSONResponse,FileResponse
import logging

import requests
from jqcode.chat_prompt import *
from langchain_core.messages import ToolMessage
from jqcode.langgraph_in_class import GraphAgent,display_code, display_text
from jqcode.jq_docstores.backend_docstore_utils.jq_es_metastores import JqElasticsearchUniMetaStore
from jqcode.jq_docstores.jq_es_client import JqEsClient
from jqcode.jq_knowledge_manegement.chatchat.server.knowledge_base.kb_service.base import (
    get_kb_details,
)
from jqcode.jq_utils.logger import jqkj_logger
logger = jqkj_logger(__file__).get_logger()
metastore = JqElasticsearchUniMetaStore()
jq_es_client = JqEsClient()

es_index_name = "default"
index_creator='manager'
default_index_description = "向量库/知识库工具(vectorstore/knowledge base)：关于安徽晶奇网络科技股份有限公司（简称晶奇公司）、医疗卫生、医疗健康、医疗服务、医疗政策、信息化产品方案、技术文档等等方面的文档知识库. 凡是安徽晶奇网络科技股份有限公司及医疗健康相关的问题，都必须使用该vectorstore工具。"
if not jq_es_client.client.indices.exists(index=es_index_name):
    jq_es_client.create_doc_index(index_name=es_index_name,description=default_index_description,index_creator=index_creator)
    

try:    
    index_meta = metastore.search_docs_by_text(top_k=1,user_query_text=es_index_name,query_on_fileds=['index_name'],filter_by_status=['true'])
    index_meta_dict_default = index_meta[0]["_source"]
except:    
    index_meta_dict_default = {"index_name": es_index_name, "description":default_index_description}

# We know this Flask app is for local use. So we can disable the verbose Werkzeug logger
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

UPLOAD_FOLDER=str(os.environ.get("workspace","/data/projects/JqChatV2/workspace"))
# UPLOAD_FOLDER=os.path.join(os.path.dirname(os.getcwd()), "workspace")

chat_router = APIRouter(prefix="/chat", tags=["Chat对话"])
workspace_router=APIRouter(prefix="/workspace", tags=["文件下载"])
# 
@chat_router.post('/completions',summary="对话接口")
def completions(
    user_prompt: str = Body(alias="query",description="用户输入"),
    es_index_name: str = Body(alias="doc", description="知识库ID"),
    user_id: str = Body(alias="user", description="用户随机ID"),
    files: List[str]=Body(alias="files",description="文档ID",default=None),
    is_rewrite: bool =Body(default=True,description="是否启用问题改写"),
    is_memory:bool=Body(default=True,description="是否启用记忆"),
    is_knowledge=Body(default=True,description="是否是知识库的文档"),
    code_message:str=Body(alias="code_message",default= None, description="执行code的信息"),
    ):
    allow_conversation_memory=is_memory
    allow_question_rewrite=is_rewrite
    print('============================================================')
    print('=============开始后台逻辑中....请稍后...........==============')
    print(f'====用户的问题是: {user_prompt}=============================')
    print(f'====所选的知识库是: {es_index_name}================================')
    print(f'====用户的ID是：{user_id}===================================')
    print(f'====执行代码的信息：{code_message if code_message else "没有要执行的代码"}==========================')
    print(f'====上传的文件信息：{files if files else "没有上传的文件"}==========================')
    if not files:
        is_knowledge = False
    print(f'====上传的文件是否存入知识库：{is_knowledge}==========================')
    print(f'====启用会话记忆：{allow_conversation_memory}==========================')
    print(f'====启用问题重写：{allow_question_rewrite}==========================')
    
    # samples是示例知识库，不在数据库中，存在本地文件中，所以查不到
    try:
        index_meta = metastore.search_docs_by_text(top_k=1,user_query_text=es_index_name,query_on_fileds=['index_name'],filter_by_status=['true'])
        index_meta_dict = index_meta[0]["_source"]
        print(f"====从metastore中获取到用户所选知识库的详细信息为：{index_meta_dict}====")
    except:
        index_meta_dict = index_meta_dict_default
        print(f"====从metastore中获取到用户所选知识库失败，使用默认知识库。详细信息为：{index_meta_dict}====")       
    print('============================================================')
    # 是否有文件
    add_docs_list_to_kb = is_knowledge
    chat_on_docs_list=[]
    if len(files)>0:
        # 如果存在上传的文件，在用户问题前加上提示词，以更大概率返回vectorstore
        user_prompt = f"[请调用知识库工具(VECTORSTORE)，检索知识库，然后回答用户问题]{user_prompt}" 
        UPLOAD_FOLDER_TEMP = UPLOAD_FOLDER+'/temp'
        for file in files:
            file=os.path.join(UPLOAD_FOLDER_TEMP, file)
            if os.path.isfile(file):
                chat_on_docs_list.append(file)
    print(f"{chat_on_docs_list=}")
    chat_bot = GraphAgent(memory_thread_id=user_id, kb_base_dict=index_meta_dict,chat_on_docs_list=chat_on_docs_list,add_docs_list_to_kb=add_docs_list_to_kb,
                          allow_conversation_memory=allow_conversation_memory,allow_question_rewrite=allow_question_rewrite)
    print(f"{chat_bot.user_id=}")
    text = chat_bot.run_conversation(user_question=user_prompt)
    
    # returned_str
    messages = chat_bot.get_messages()
    code = ''
    try:
        for m in messages[::-1]:
            if isinstance(m,ToolMessage):
                if m.name.lower()=='code_execution':
                    # text+=m.content
                    if m.additional_kwargs['question_id'] == chat_bot.question_id and m.additional_kwargs['status'] is True :
                        code = m.additional_kwargs['code']
                        break
    except Exception as e:
        logger.warning(f"获取'code_execution'的code失败:{e}")
        code = ''
    if code:
        code=display_code(code)
        text=display_text(text)
        code_text=code +"\n"+text
    else:
        code_text = text
    return JSONResponse(content={"text":code_text},status_code=200)

@chat_router.post('/upload',summary="上传接口")
async def upload_file(
     files: List[UploadFile] = File(..., description="上传文件，支持多文件"),
     knowledge_id: str = Body(None, description="知识库ID"),
     uid: str = Body(None, description="用户ID"),
     is_knowledge:bool=Body(False,description="是否纳入知识库")
    ):
    ids=[]
    for file in files:
        if file.filename == '':
            return ({'error': '请选择文件'}), 400
        if file and allowed_file(file.filename):
            # new_filename=uuid.uuid1().hex + "." + file.filename.rsplit(".",1)[1]
            file_path = os.path.join(UPLOAD_FOLDER,"temp")
            if not os.path.exists(file_path):
                os.makedirs(file_path, exist_ok=True)
            file_target = os.path.join(file_path, file.filename)
            file_content = await file.read()
            with open(file_target, "wb") as f:  
                 f.write(file_content)  
                 ids.append(file.filename)
            # file_info = inspect_file(file_target)
            # os.environ["HAS_DATA_FILE_UPLOADED"] = 'True'
            # message_buffer.append(f"已上传保存的文件名为{file.filename},请在分析过程中使用这个数据文件\n{file_info}'}" + "\n\n")
        else:
            return JSONResponse(content={'message': '存在不被允许的文件类型'}, status_code=400)

    return JSONResponse(content={'message': f'上传成功',"files":ids}, status_code=200)

@chat_router.post('/knowledges',summary="知识库列表")
def knowledges(query: str = Body(alias="query",description="查询字符串"),):
    kb_list = {x["kb_name"]: x for x in get_kb_details()}
    return JSONResponse(content=kb_list, status_code=200)

KERNEL_API_BASE = os.getenv("KERNEL_API_BASE",'http://localhost')
API_PORT = os.getenv("API_PORT",5011)
kernel_api_url = f"{KERNEL_API_BASE}:{API_PORT}/api"
@chat_router.post('/code',summary="获取code执行结果")
def code():
    resp = requests.get(kernel_api_url)
    results=resp.json()
    return JSONResponse(content=results, status_code=200)

    
@workspace_router.get('/knowledge/{knowledge}/content/{file}',summary="知识库ID下的文件")
def download_knowledge(knowledge,file):
    file_path = os.path.join(UPLOAD_FOLDER,"knowledge_base",knowledge,"content",file)
    return FileResponse(file_path)

@workspace_router.get('/download',summary="生成的文件下载")
def download_code(file):
    file_path = os.path.join(UPLOAD_FOLDER, "code",file)
    return FileResponse(file_path)

@workspace_router.get('/images/{image}',summary="显示生成的图片")
def download_code(image):
    file_path = os.path.join(UPLOAD_FOLDER, "code",image)
    return FileResponse(file_path)
