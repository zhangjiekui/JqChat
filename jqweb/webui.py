import sys
# project_root = '/media/temp/JqChat'
# sys.path.insert(0, project_root)
import streamlit as st
import streamlit_antd_components as sac

from jqcode.jq_kb_manegement.configs import VERSION
from jqcode.jq_kb_manegement.server.utils import api_address
from jqweb.pages.dialogue.dialogue import  dialogue_page
from jqweb.pages.knowledge_base.knowledge_base import knowledge_base_page
from jqweb.utils.utils import ApiRequest,get_img_base64
api = ApiRequest(base_url=api_address())


if __name__ == "__main__":
    is_lite = "lite" in sys.argv  # TODO: remove lite mode

    st.set_page_config(
        "晶奇聊天机器人",
        get_img_base64("logo_chat_avatar.png"),
        initial_sidebar_state="auto",
        menu_items={
            "Get Help": "https://github.com/zhangjiekui/JqChat",
            "Report a bug": "https://github.com/zhangjiekui/JqChat/issues",
             "About": f"""欢迎使用JingQi-Chat""",
        },
        layout="wide",
    )

    # # use the following code to set the app to wide mode and the html markdown to increase the sidebar width
    #隐藏deploy按钮
    st.markdown(
        """
        <style>
        [data-testid="stSidebarUserContent"] {
            padding-top: 20px;
        }
        .block-container {
            padding-top: 25px;
        }
        
        [data-testid="stBottomBlockContainer"] {
            padding-bottom: 20px;
        }
        .stDeployButton {display:none;}
        
        """,
        unsafe_allow_html=True,
    )
    with st.sidebar:
       
        st.image(
            get_img_base64("logo_chat_avatar_jingqi_chat.png"), use_container_width=True
        )
        st.caption(
            f"""<p align="right">当前版本：{VERSION}</p>""",
            unsafe_allow_html=True,
        )

        selected_page = sac.menu(
            [
                sac.MenuItem("对话", icon="chat"),
                sac.MenuItem("知识库管理", icon="hdd-stack"),
            ],
            key="selected_page",
            open_index=0,
        )

        sac.divider()
 
    if selected_page == "知识库管理":
        knowledge_base_page(api=api, is_lite=is_lite)
        
    else:
        dialogue_page(api=api, is_lite=is_lite)
