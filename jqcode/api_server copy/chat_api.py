


from typing import List
from fastapi import APIRouter, Body, File,  UploadFile
import os
import logging
from fastapi.responses import JSONResponse
from jqcode.chat_prompt import *
from langchain_core.messages import ToolMessage
from jqcode.langgraph_in_class import GraphAgent,display_code, display_text
from jqcode.jq_docstores.backend_docstore_utils.jq_es_metastores import JqElasticsearchUniMetaStore
from jqcode.jq_docstores.jq_es_client import JqEsClient
from jqcode.jq_kb_manegement.server.knowledge_base.kb_service.base import (
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

UPLOAD_FOLDER=str(os.environ.get("workspace","/data/projects/JqChatV2/workspace"))

def uploads(files:List[UploadFile])->List[str]:
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
            file_content = file.file.read()
            with open(file_target, "wb") as f:  
                f.write(file_content)  
                ids.append(file.filename)
                # file_info = inspect_file(file_target)
                # os.environ["HAS_DATA_FILE_UPLOADED"] = 'True'
                # message_buffer.append(f"已上传保存的文件名为{file.filename},请在分析过程中使用这个数据文件\n{file_info}'}" + "\n\n")
    return ids

api_router = APIRouter(prefix="/api", tags=["对外API"])
@api_router.post('/v1/chat',summary="对话接口")
def chat(
    user_prompt: str = Body(description="用户输入"),
    es_index_name: str = Body(default=None,description="知识库ID"),
    user_id: str = Body(description="用户随机ID"),
    is_rewrite: bool =Body(default=True,description="是否启用问题改写"),
    is_memory:bool=Body(default=True,description="是否启用记忆"),
    files: List[UploadFile] = File(default=None, description="上传文件，支持多文件"),
    ):
    allow_conversation_memory=is_memory
    allow_question_rewrite=is_rewrite
    print('============================================================')
    print('=============开始后台逻辑中....请稍后...........==============')
    print(f'====用户的问题是: {user_prompt}=============================')
    print(f'====所选的知识库是: {es_index_name}================================')
    print(f'====用户的ID是：{user_id}===================================')
    print(f'====上传的文件信息：{files if files else "没有上传的文件"}==========================')
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
    add_docs_list_to_kb = False
    chat_on_docs_list=[]
   
    if files and len(files)>0:
        fs=uploads(files)
        # 如果存在上传的文件，在用户问题前加上提示词，以更大概率返回vectorstore
        user_prompt = f"[请调用知识库工具(VECTORSTORE)，检索知识库，然后回答用户问题]{user_prompt}" 
        UPLOAD_FOLDER_TEMP = UPLOAD_FOLDER+'/temp'
        for file in fs:
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



@api_router.get('/v1/knowledges',summary="知识库列表")
def knowledges():
    # kb_list = {x["kb_name"]: x for x in get_kb_details()}
    kb_list=[{key: value for key, value in item.items() if key  in ['kb_name', 'No']} for item in get_kb_details()]
    return JSONResponse(content=kb_list, status_code=200)
