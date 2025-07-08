import time
import uuid
import asyncio
import threading
from lazyllm import FileSystemQueue
# from audio_recorder_streamlit import audio_recorder
import streamlit as st
from streamlit_chatbox import ChatBox
from streamlit_extras.bottom_container import bottom
try:
    # Streamlit >= 1.12.0
    from streamlit.runtime.scriptrunner import add_script_run_ctx
    from streamlit.runtime.scriptrunner.script_run_context import get_script_run_ctx
except:
    # Streamlit <= 1.11.0
    from streamlit.scriptrunner import add_script_run_ctx
    from streamlit.scriptrunner.script_run_context import get_script_run_ctx

from web.utils.utils import *

from jqcode.jq_knowledge_manegement.chatchat.server.knowledge_base.kb_service.base import (
    get_kb_details,
)
from jqcode.jq_agent.c0_init_env_models import env_models_instance
chat_box = ChatBox(assistant_avatar=get_img_base64("chatchat_icon_blue_square_v2.png"))
code_message:str=None
lazyllm_queue = env_models_instance.lazyllm_queue
lazyllm_queue_sid = env_models_instance.lazyllm_queue_sid

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
def upload_docs(user,knowledge_id,files,is_knowledge, _api: ApiRequest) -> str:
    """
    将文件上传到临时目录，用于文件对话
    返回临时向量库ID
    """
    print(is_knowledge)
    return _api.upload_docs(uid=user,knowledge_id=knowledge_id,is_knowledge=is_knowledge,files=files)
#聊天
def chat(code_message,query,user,doc:str,files,is_memory,is_rewrite,is_knowledge,_api:ApiRequest)  :
    response=_api.chat_chat(code_message=code_message,query=query,user=user,doc=doc,is_memory=is_memory,is_rewrite=is_rewrite,is_knowledge=is_knowledge,files=files)
    return response

#执行code
def code(user,_api:ApiRequest)  :
    return _api.code_chat(user=user)


# 初始化session中的是否纳入知识库选项 
st.session_state["is_knowledge"]=False

class ThreadWithResult(threading.Thread):  
    def __init__(self, target, args=()):  
        super(ThreadWithResult, self).__init__()  
        self.func = target  
        self.args = args
        self.result = ""  
  
    def run(self):
        try:  
            self.result = self.func(*self.args)  # 在执行函数的同时，把结果赋值给result,  
        except:
            self.result = self.func(self.args)
        finally:
            if self.result:
                print(self.result)
            else:
                print("没有结果")
                self.result = ""
    
    # 然后通过get_result函数获取返回的结果
    def get_result(self):  
        try:  
            return self.result  
        except Exception as e:  
            return None 


def get_process_text(user_id,chat_box):
        leading_text = "#####  整体执行过程：  \n"
        text_string = leading_text        
        values = []       
        condition = True
        while condition:            
            try:
                values =lazyllm_queue._dequeue(id=user_id)
                if values:
                    for j,text in enumerate(values):
                        if text.strip() == "DONE":
                            condition = False
                        # if not text.startswith("\n - "): #<br> 或 "\n - "
                        #     text = f"\n - "+text
                        text = f"\n {j+1}. "+text
                        text_string += text
                        chat_box.update_msg(text_string,streaming=False)
                        # print(f"output{j}: {text}")
            except Exception as e:
                condition = False
                logger.warning(f"获取执行过程信息时：{e}")
                lazyllm_queue.clear()
                break
        # print("Done:全部完成")
        return text_string[len(leading_text):]
def dialogue_page(
    api: ApiRequest,
    is_lite: bool = False,
):
    ctx = chat_box.context
    ctx.setdefault("uid", uuid.uuid4().hex)
    # 初始化文件ID和执行代码结果为None
    ctx.setdefault("files", [])
    ctx.setdefault("code_message",'')
    ctx.setdefault("is_knowledge",False)    
   
    @st.dialog("上传文件", width="large")
    def file_upload():
        files = st.file_uploader("上传分析文件",
            [i for ls in LOADER_DICT.values() for i in ls],
            accept_multiple_files=True,
            )
        is_knowledge = st.checkbox(f"是否纳入知识库({selected_kb})？")
        if st.button("开始上传", disabled = len(files) == 0 ):
            user=ctx.get("uid")
            knowledge_id=None
            ctx["is_knowledge"]= is_knowledge
            if is_knowledge:
                knowledge_id=selected_kb
            response=upload_docs(user=user,knowledge_id=knowledge_id,is_knowledge=is_knowledge,files=files,_api=api)
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
        is_memory = st.checkbox("启用会话记忆",value=True)
        is_rewrite=st.checkbox("启用问题重写",value=True)   
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
            ctx['is_knowledge']=False
            rerun()

    

    #简洁的对话，待完善 
    if prompt:
        chat_box.user_say(prompt)
        chat_box.ai_say("正在思考中...")
        user=ctx.get("uid")
        doc=str(selected_kb)
        code_message=ctx.get('code_message')
        files=ctx.get('files')
        # @swm 这里有问题
        is_knowledge=ctx.get("is_knowledge")
        
        t1 = ThreadWithResult(target=chat, args=(code_message,prompt,user,doc,files,is_memory,is_rewrite,is_knowledge,api))
        t2 = ThreadWithResult(target=get_process_text, args=(user,chat_box))
        add_script_run_ctx(t2)        
        t1.start()
        t2.start()
    
        # 等待线程结束
        t1.join()
        t2.join()
        chat_result=t1.get_result()
        log_result=t2.get_result()
        
        # reasoning_content_str = f"{reasoning_content_str}\n------\n"
        log_text = f'<details>\n<summary>点击查看"整体执行过程"</summary>\n<font color="grey" size=16px>\n{log_result}\n------\n</font></details>'
        chat_text = chat_result["text"]
        answer_text = f"{log_text}\n{chat_text}"
        chat_box.update_msg(answer_text,streaming=False) 
        #清空code执行回复信息和文件
        ctx['files']=[]
        ctx['is_knowledge']=False
        lazyllm_queue.clear()

if __name__ == "__main__":
    pass

