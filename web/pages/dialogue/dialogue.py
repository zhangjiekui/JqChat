from threading import Timer
import time
import uuid
from typing import Dict, List

# from audio_recorder_streamlit import audio_recorder
import streamlit as st
from streamlit_chatbox import ChatBox
from streamlit_extras.bottom_container import bottom


from web.utils.utils import *

from jqcode.jq_knowledge_manegement.chatchat.server.knowledge_base.kb_service.base import (
    get_kb_details,
)

chat_box = ChatBox(assistant_avatar=get_img_base64("chatchat_icon_blue_square_v2.png"))

code_message:str=None

LOADER_DICT = {
    "CSVLoader": [".csv"],
    "ExcelLoader": [".xlsx", ".xls"],
    "WordLoader": [".doc","docx"],
    "PdfLoader": [".pdf"],
}

SUPPORTED_EXTS = [ext for sublist in LOADER_DICT.values() for ext in sublist]

def save_session(conv_name: str = None):
    """save session state to chat context"""
    chat_box.context_from_session(
        conv_name, exclude=["selected_page", "prompt", "cur_conv_name"]
    )


def restore_session(conv_name: str = None):
    """restore sesstion state from chat context"""
    chat_box.context_to_session(
        conv_name, exclude=["selected_page", "prompt", "cur_conv_name"]
    )


def rerun():
    """
    save chat context before rerun
    """
    save_session()
    st.rerun()


@st.cache_data
def upload_docs(user,knowledge_id,files, _api: ApiRequest) -> str:
    """
    将文件上传到临时目录，用于文件对话
    返回临时向量库ID
    """
    return _api.upload_docs(uid=user,knowledge_id=knowledge_id,files=files)
#聊天
def chat(code_message,query,user,doc:str,files,_api:ApiRequest)  :
    response=_api.chat_chat(code_message=code_message,query=query,user=user,doc=doc,files=files)
    return response

#执行code
def code(user,_api:ApiRequest)  :
    return _api.code_chat(user=user)

#执行code
def clear(user,_api:ApiRequest)  :
    return _api.clear_chat(code==code,user=user)
#从后台获取code执行的结果
def get_execute_result(api:ApiRequest):
    ctx = chat_box.context
    for i in range(3) :
        ctx = chat_box.context
        user=ctx.get("uid")
        response=code(user=user,_api=api)
        if('results' in response and len(response["results"])>0):
            for result in response["results"]:
                if (result["type"] == "message" or result["type"]  == "message_raw") and result["value"]  != 'Kernel is ready.':
                    # inject context
                    code_message=result["value"]
                    ctx['code_message']=code_message
                    chat_box.ai_say(code_message)
                else :
                    pic=  f'<img src="data:{result["type"]};base64,{result["value"]}" width="300">'
                    chat_box.ai_say(pic)
            return
        time.sleep(1)

def dialogue_page(
    api: ApiRequest,
    is_lite: bool = False,
):
    ctx = chat_box.context
    ctx.setdefault("uid", uuid.uuid4().hex)
    # 初始化文件ID和执行代码结果为None
    ctx.setdefault("files", [])
    ctx.setdefault("code_message",'')
    # st.session_state.setdefault("cur_conv_name", chat_box.cur_chat_name)
    # st.session_state.setdefault("last_conv_name", chat_box.cur_chat_name)

    # # sac on_change callbacks not working since st>=1.34
    # if st.session_state.cur_conv_name != st.session_state.last_conv_name:
    #     save_session(st.session_state.last_conv_name)
    #     restore_session(st.session_state.cur_conv_name)
    #     st.session_state.last_conv_name = st.session_state.cur_conv_name

    # # st.write(chat_box.cur_chat_name)
    # # st.write(st.session_state)

    @st.dialog("上传文件", width="large")
    def file_upload():
        files = st.file_uploader("上传分析文件",
            [i for ls in LOADER_DICT.values() for i in ls],
            accept_multiple_files=True,
            )
        choose_knowbase= st.checkbox(f"是否纳入知识库({selected_kb})？")
        if st.button("开始上传", disabled = len(files) == 0 ):
            user=ctx.get("uid")
            knowledge_id=None
            if choose_knowbase:
                knowledge_id=selected_kb
            response=upload_docs(user=user,knowledge_id=knowledge_id,files=files,_api=api)
            print(response)
            st.info(f"{response['message']}")
            chat_box.context['files']=response['files']
        
    with st.sidebar:   
      
        try:
            kb_list = {x["kb_name"]: x for x in get_kb_details()}
        except Exception as e:
            st.error(
                "获取知识库信息错误，请检查是否已按照 `README.md` 中 `4 知识库初始化与迁移` 步骤完成初始化或迁移，或是否为数据库连接错误。"
            )
            st.stop()
        if (
            "selected_kb_name" in st.session_state
            and st.session_state["selected_kb_name"] in kb_names
        ):
            selected_kb_index = kb_names.index(st.session_state["selected_kb_name"])
        else:
            selected_kb_index = 0
        def format_selected_kb(kb_name: str) -> str:
            if kb := kb_list.get(kb_name):
                return f"{kb_name}"
            else:
                return kb_name  
        if "selected_kb_info" not in st.session_state:
            st.session_state["selected_kb_info"] = ""
        kb_names = list(kb_list.keys())
        selected_kb = st.selectbox(
            "请选择知识库：",
            kb_names,
            format_func=format_selected_kb,
                index=selected_kb_index,
        )
        # files = st.file_uploader("上传知识文件：",
        #         [i for ls in LOADER_DICT.values() for i in ls],
        #         accept_multiple_files=True,
        #         )
        # if st.button("开始上传", disabled=len(files) == 0):
        #     st.session_state["file_chat_id"] = upload_temp_docs(files, api)

    # Display chat messages from history on app rerun
    chat_box.output_messages()
    chat_input_placeholder = "请输入对话内容，换行请使用Shift+Enter。"

    # chat input
    with bottom():
        cols = st.columns([1, 0.2, 15,  1])
        prompt = cols[2].chat_input(chat_input_placeholder, key="prompt")
        if cols[0].button(":page_facing_up:", help="上传文件"):
           file_upload()
        
        if cols[-1].button(":wastebasket:", help="清空对话"):
            chat_box.reset_history()
             #清空code执行回复信息和文件
            ctx['files']=[]
            ctx['code_message']=''
            return
        
    #简洁的对话，待完善 
    if prompt:
        chat_box.user_say(prompt)
        chat_box.ai_say("正在思考中...")
        user=ctx.get("uid")
        doc=str(selected_kb)
        code_message=ctx.get('code_message')
        files=ctx.get('files')
        msg=chat(code_message=code_message,query=prompt,user=user,doc=doc,files=files,_api=api)
        chat_box.update_msg(msg["text"],streaming=False) 
        #清空code执行回复信息和文件
        ctx['files']=[]
        ctx['code_message']=''
        if 'code' in msg and msg['code'] != None:
            get_execute_result(api)
    # get_execute_result(api)