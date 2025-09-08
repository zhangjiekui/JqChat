import time
import uuid
import shortuuid

import asyncio
import threading
import io, os
import base64
from io import BytesIO
from PIL import Image

# from audio_recorder_streamlit import audio_recorder
import streamlit as st
from streamlit_chatbox import ChatBox
from streamlit_chatbox import Image as StImage
from streamlit_extras.bottom_container import bottom
try:
    # Streamlit >= 1.12.0
    from streamlit.runtime.scriptrunner import add_script_run_ctx
except:
    # Streamlit <= 1.11.0
    from streamlit.scriptrunner import add_script_run_ctx

# from web.utils.utils import *
from jqweb.utils.utils import get_img_base64,ApiRequest,logger
from jqcode.jq_agent.c0_init_env_models import env_models_instance
from jqcode.jq_queue.jq_queues import JqFileSystemQueue
from jqcode.jq_kb_manegement.server.knowledge_base.kb_service.base import (
    get_kb_details,
)



# os.environ["STREAMLIT_SERVER_ENABLE_STATIC_SERVING"] = "false"
try:
    st.set_option("deprecation.showfileUploaderEncoding", False)
except:
    pass

chat_box = ChatBox(assistant_avatar=get_img_base64("logo_chat_avatar.png"))
code_message:str=None
max_img_num=5
img_size = (600,600)

LOADER_DICT = {
    "CSVLoader": [".csv"],
    "ExcelLoader": [".xlsx", ".xls"],
    "WordLoader": [".doc","docx"],
    "PdfLoader": [".pdf"],
    # "ImgLoader": [".png", ".jpg", ".jpeg", ".bmp"], #".gif",
    "TextLoader": [".txt"],
    "JSONLoader": [".json"],
    "MarkdownLoader": [".md"]
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
    return _api.upload_docs(uid=user,knowledge_id=knowledge_id,is_knowledge=is_knowledge,files=files)
#聊天
def chat(code_message,query,user,doc:str,files,is_memory,is_rewrite,is_knowledge,_api:ApiRequest,user_rquest_url:str):
    logger.warning(f"user:{user}")
    response=_api.chat_jqagent(code_message=code_message,query=query,user=user,doc=doc,is_memory=is_memory,is_rewrite=is_rewrite,is_knowledge=is_knowledge,files=files,user_rquest_url=user_rquest_url)
    return response

#执行code
def code(code:str,_api:ApiRequest)  :
    return _api.code_execute(code=code)


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
                logger.warning(self.result)
            else:
                logger.warning("没有结果")
                self.result = ""
    
    # 然后通过get_result函数获取返回的结果
    def get_result(self):  
        try:  
            return self.result  
        except Exception as e:  
            return None 


def get_process_text(jq_queque,chat_box):
        leading_text = "#####  整体执行过程：  \n"
        text_string = leading_text        
        values = []       
        condition = True
        while condition:            
            try:
                values =jq_queque.dequeue()
                if values:
                    for j,text in enumerate(values):
                        if text.strip() == "DONE":
                            condition = False
                        text = f"\n {j+1}. "+text
                        text_string += text
                        chat_box.update_msg(text_string,streaming=False)
                        # print(f"output{j}: {text}")
            except Exception as e:
                condition = False
                logger.warning(f"获取执行过程信息时：{e}")
                jq_queque.clear()
                break
        # print("Done:全部完成")
        return text_string[len(leading_text):]
def dialogue_page(
    api: ApiRequest,
    is_lite: bool = False,
    selected_kb = "default",
    is_memory: bool = False,
    is_rewrite: bool = False,
    user_rquest_url:str = None,
):
  
    ctx = chat_box.context
    user = st.session_state['username']
    ctx.setdefault("uid", f"{user}({uuid.uuid4().hex})")
    # 初始化文件ID和执行代码结果为None
    ctx.setdefault("files", [])
    ctx.setdefault("code_message",'')
    ctx.setdefault("is_knowledge",False)    
   
    @st.dialog("上传文件（文档问答）", width="large")
    def file_upload():
        files = st.file_uploader("上传知识库文档",
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
            chat_box.context['files']=response['files']
            st.info(f"{response['message']}:{len(response['files'])}个文件")


    @st.dialog("上传图片（OCR识别或对话，最多5张）", width="large")
    def img_upload(max_img_num=max_img_num):
        files = st.file_uploader("上传图片",type=["jpg", "jpeg", "png","bmp"],
            accept_multiple_files=True,
            )
        pass

        base64_images = []
        if st.button("开始上传", disabled = len(files) == 0 ):
            num_files = len(files)
            if num_files <= max_img_num:
                ctx["vlm"] = True
                ctx["files"] = files 
                for uploaded_file in files:
                    img = Image.open(uploaded_file)
                    # 将图片保存到内存中的BytesIO对象
                    img_io = BytesIO()
                    try:
                        img.save(img_io,format="PNG", clamp=True)
                    except:
                        img.save(img_io, format="JPEG")
                    # 获取二进制数据
                    img_bytes = img_io.getvalue()
                    # 转换为base64编码
                    base64_image = base64.b64encode(img_bytes).decode('utf-8')
                    base64_images.append(base64_image)
                ctx['base64_images'] = base64_images
                st.info(f"上传成功:{len(files)}个文件")
                
            else:
                st.error(f"一次最多上传{max_img_num}张图片，但您上传了{num_files}张图片，上传失败!")
    

    # Display chat messages from history on app rerun
    chat_box.output_messages()
    chat_input_placeholder = "请输入对话内容，换行请使用Shift+Enter；如果是仅想识别图片中的文字，直接输入ocr即可。"

    
    with bottom():
        # cols = st.columns([1, 0.1, 1, 0.1, 20, 1]) 
        cols = st.columns([1,  1, 20, 1],gap="small",border=False)         
 
        # if cols[0].button(":page_facing_up:", help="上传文档（知识库问答）"):
        if cols[0].button("📘",help="上传文档（知识库问答）"):
           file_upload() 
        # cols[1].write("")  # 空白间隔       
        # if cols[1].button(":framed_picture:", help="上传图片（OCR/对话）"):
        if cols[1].button("🖼️", help="上传图片（OCR/对话）"):
           img_upload()        
        # cols[3].write("")  # 空白间隔 
        prompt = cols[2].chat_input(chat_input_placeholder, key="prompt",accept_file=False)        
        if cols[-1].button(":wastebasket:", help="清空对话"):
            chat_box.reset_history()
             #清空code执行回复信息和文件
            ctx['files']=[]
            ctx['is_knowledge']=False
            ctx['files']=[]
            ctx['base64_images']=[]
            ctx['vlm']=False 
            rerun()

    
    # workon test
    # streamlit  1.37.0                  [pip install streamlit==1.37.0]
    # streamlit-chatbox = "1.1.12.post4" [pip install streamlit-chatbox==1.1.12.post4]
    #简洁的对话，待完善
    # chat input
    if prompt:
        use_vlm = ctx.get("vlm",False)
        base64_images = ctx.get("base64_images",None)
        if use_vlm:            
            # === 展示上传的图片（缩略图 + 可点击查看原图）===
            img_files = ctx.get("files", None)
            if img_files:
                if prompt.lower() == "ocr":
                    prompt = "首先识别出有意义的区块，然后逐个区块完整识别并仅输出图中的文字（相当于ocr，去掉不必要的换行符，但保留必要的空格，使用‘||’分割文本块）。最后仅输出完整的文本，不要有任何额外的内容和解释。"

                chat_box.user_say(prompt)

                # 创建列：左侧为提示，其余为图片列
                img_columns = [10] * max_img_num
                all_columns = [2] + img_columns
                cols = st.columns(all_columns)

                # 方式2
                for i,img_file in enumerate(img_files): 
                    # img = Image.open(img_file) 
                    # img_square = img.resize(img_size)
                    img_square = Image.open(img_file)
                    j = i+1
                    with cols[j]:
                        st.image(img_square, use_container_width=False)

            if base64_images:
                chat_box.ai_say("正在思考中...")                
                vlm = env_models_instance.vlm
                answer_texts = ""
                if len(base64_images)==1:
                    base64_image = base64_images[0]
                    answer_texts = vlm(image_path_or_base64=base64_image,is_decoded_image_text=True,query=prompt)
                else:                    
                    for i,base64_image in enumerate(base64_images):
                        answer_text = vlm(image_path_or_base64=base64_image,is_decoded_image_text=True,query=prompt)
                        answer_texts += f"\n {i+1}. "+ answer_text
                ai_alert_text = '\n\n------\n' + '<font color="red">内容由AI生成</font>' + '\n\n------\n'
                answer_texts = f"{answer_texts}{ai_alert_text}"
                chat_box.update_msg(answer_texts,streaming=False)
            else:
                chat_box.update_msg("未获取到图片内容",streaming=False)
            ctx['files']=[]
            ctx['base64_images']=[]
            ctx['vlm']=False  
        else:        
            chat_box.user_say(prompt)
            chat_box.ai_say("正在思考中...")
            user=ctx.get("uid")
            doc=str(selected_kb)
            code_message=ctx.get('code_message')
            files=ctx.get('files')
            # @swm 这里有问题
            is_knowledge=ctx.get("is_knowledge")
            question_id = shortuuid.uuid()
            ctx['question_id'] = question_id
            user_and_question_id = f"{user}::{question_id}"
            jq_queque = JqFileSystemQueue(id=user_and_question_id)
            

            # 是否需要替换端口？
            api_port = api.base_url.split(":")[-1]
            web_port = user_rquest_url.split(":")[-1]
            # _user_rquest_url = user_rquest_url[0:-len(web_port)]
            # request_url = _user_rquest_url + api_port

            request_url = user_rquest_url
            if "/workspace" not in request_url:
                deployment_url = f"{request_url}/workspace"
            else:
                deployment_url = request_url
            t1 = ThreadWithResult(target=chat, args=(code_message,prompt,user_and_question_id,doc,files,is_memory,is_rewrite,is_knowledge,api,deployment_url))
            t2 = ThreadWithResult(target=get_process_text, args=(jq_queque,chat_box))
            add_script_run_ctx(t2)        
            t1.start()
            t2.start()
        
            # 等待线程结束
            t1.join()
            t2.join()
            chat_result=t1.get_result()
            log_result=t2.get_result()
            
            # reasoning_content_str = f"{reasoning_content_str}\n------\n"
            log_text = f'<details open>\n<summary>点击查看"整体执行过程"</summary>\n<font color="grey">\n{log_result}\n------\n</font></details>'
            chat_text = chat_result["text"]
            answer_text = f"{log_text}\n{chat_text}"


            # if "127.0.0.1" in request_url or "localhost" in request_url or "0.0.0.0" in request_url:
            #     logger.warning(f"根据user_request获取到 {request_url=}为本地地址，转换为服务器地址")
            #     port = request_url
            #     workspace_url_removed = env_models_instance.workspace_url.split(":")[-1]
            #     removed_chars = len(workspace_url_removed)
            #     workspace_url = env_models_instance.workspace_url[0:-removed_chars]
            #     request_url = workspace_url + port
            #     logger.warning(f"转换后的服务器地址为:{request_url=}")                

            env_deployment_url = env_models_instance.get_deployment_url()
            # 替换端口
            answer_text = answer_text.replace(f":{api_port}/",f":{web_port}/")


            if deployment_url!=env_deployment_url:
                if env_deployment_url in answer_text:
                    logger.warning(f"将最终AI结果中的ENV部署地址{env_deployment_url=}替换为实际服务地址{deployment_url=}")
                    answer_text = answer_text.replace(env_deployment_url,deployment_url)

            chat_box.update_msg(answer_text,streaming=False)
            #清空code执行回复信息和文件
            ctx['files']=[]
            ctx['base64_images']=[]
            ctx['vlm']=False 
            ctx['is_knowledge']=False
            jq_queque.clear()




if __name__ == "__main__":
    pass

