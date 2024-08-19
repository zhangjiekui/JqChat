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

LOADER_DICT = {
    "JSONLoader": [".json"],
    "JSONLinesLoader": [".jsonl"],
    "CSVLoader": [".csv"],
    "UnstructuredExcelLoader": [".xlsx", ".xls", ".xlsd"],
    "UnstructuredTSVLoader": [".tsv"],
    "UnstructuredXMLLoader": [".xml"],
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


def get_messages_history(
    history_len: int, content_in_expander: bool = False
) -> List[Dict]:
    """
    返回消息历史。
    content_in_expander控制是否返回expander元素中的内容，一般导出的时候可以选上，传入LLM的history不需要
    """

    def filter(msg):
        content = [
            x for x in msg["elements"] if x._output_method in ["markdown", "text"]
        ]
        if not content_in_expander:
            content = [x for x in content if not x._in_expander]
        content = [x.content for x in content]

        return {
            "role": msg["role"],
            "content": "\n\n".join(content),
        }

    messages = chat_box.filter_history(history_len=history_len, filter=filter)
    if sys_msg := st.session_state.get("system_message"):
        messages = [{"role": "system", "content": sys_msg}] + messages
    return messages


@st.cache_data
def upload_docs(user,knowbase_id,files, _api: ApiRequest) -> str:
    """
    将文件上传到临时目录，用于文件对话
    返回临时向量库ID
    """

    return _api.upload_docs(uid=user,knowledge_id=knowbase_id,files=files)
#聊天
def chat(query,user,doc:str,_api:ApiRequest)  :
    return _api.chat_chat(query=query,user=user,doc=doc)
#执行code
def code(code,user,_api:ApiRequest)  :
    return _api.code_chat(code==code,user=user)
#执行code
def clear(user,_api:ApiRequest)  :
    return _api.clear_chat(code==code,user=user)

def dialogue_page(
    api: ApiRequest,
    is_lite: bool = False,
):
    ctx = chat_box.context
    ctx.setdefault("uid", uuid.uuid4().hex)
    ctx.setdefault("file_chat_id", None)
    st.session_state.setdefault("cur_conv_name", chat_box.cur_chat_name)
    st.session_state.setdefault("last_conv_name", chat_box.cur_chat_name)

    # sac on_change callbacks not working since st>=1.34
    if st.session_state.cur_conv_name != st.session_state.last_conv_name:
        save_session(st.session_state.last_conv_name)
        restore_session(st.session_state.cur_conv_name)
        st.session_state.last_conv_name = st.session_state.cur_conv_name

    # st.write(chat_box.cur_chat_name)
    # st.write(st.session_state)

    @st.dialog("上传文件", width="large")
    def file_upload():
        files = st.file_uploader("上传分析文件",
            [i for ls in LOADER_DICT.values() for i in ls],
            accept_multiple_files=True,
            )
        
        if st.button("开始上传", disabled=len(files) == 0):
            user=ctx.get("uid")
            print(selected_kb)
            response=upload_docs(user=user,knowbase_id=selected_kb,files=files,_api=api)
            print(response)
            st.info(f"{response['message']}")
            # st.session_state["file_chat_id"] = upload_docs(user=user,files=files, api=api)
        
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
            return
        
    #简洁的对话，待完善 
    if prompt:
        chat_box.user_say(prompt)
        chat_box.ai_say("正在思考中...")
        user=ctx.get("uid")
        doc=str(selected_kb_index)
        print(prompt,user,doc)
        msg=chat(query=prompt,user=user,doc=doc,_api=api)
        chat_box.update_msg(msg["text"],streaming=False)
        if("code" in msg and msg["code"] is not None):
            # 获取可能存在的图片，这个图片
            img=code()
            img_tag =(
                    f'<img src="data:image/jpeg;base64,{msg["text"]}" width="300">'
                )
            chat_box.ai_say(img_tag)
        #     #    with chat_box() :
        #         response_dict=code_editor(code=f'int i',lang="python",theme="dark")
        #         chat_box.insert_msg(
        #                         Markdown( # type: ignore
        #                             ...,
        #                             in_expander=True,
        #                             state="running",
        #                             title="执行代码",
        #                         )
        #                     )
        #         code_response=code(code=msg["code"],user=user,_api=api)
        #         chat_box.update_msg(code_response["text"])
        #         # chat_box.insert_msg(response_dict) 
        #         # if(st.button("aaa")):
        #         #     st.write("aaa")
        #     # with chat_box:
        #     #     st.write(response_dict)
            

