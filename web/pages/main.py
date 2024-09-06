
import streamlit_antd_components as sac
from streamlit_extras.bottom_container import bottom
from streamlit_chatbox import ChatBox
from jqcode.jq_knowledge_manegement.chatchat.server.utils import api_address
from pages.dialogue.dialogue import  dialogue_page
from pages.knowledge_base.knowledge_base import knowledge_base_page
from web.utils.utils import ApiRequest,get_img_base64
from jqcode.jq_knowledge_manegement.chatchat.configs import VERSION
from streamlit_chatbox import ChatBox
from web import *

st.set_page_config(
        "晶奇聊天机器人",
        get_img_base64("chatchat_icon_blue_square_v2.png"),
        initial_sidebar_state="auto",
        menu_items={
             "About": f"""欢迎使用JingQi-Chat""",
        },
        layout="wide",
    )
st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        .stDeployButton {display:none;}
        footer {visibility: hidden;}
        #stDecoration {display:none;}
    </style>
""", unsafe_allow_html=True)
st.markdown("""<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;}</style>""", unsafe_allow_html=True)
chat_box = ChatBox(assistant_avatar=get_img_base64("chatchat_icon_blue_square_v2.png"))
chat_box.init_session()
chat_box.reset_history()
with st.sidebar:
    st.image(
        get_img_base64("logo-long-chatchat-trans-v3.png"), use_column_width=True
    )
    st.caption(
        f"""<p align="right">当前用户：{ss['name']}</p>""",
        unsafe_allow_html=True,
    )

    selected_page = sac.menu(
        [
            sac.MenuItem("对话", icon="chat"),
            sac.MenuItem("知识库管理", icon="hdd-stack"),
            sac.MenuItem('系统', icon='bi bi-person-circle', children=[
                # sac.MenuItem('我的', icon='bi bi-person-plus-fill'),
                # sac.MenuItem('注册新用户', icon='bi bi-person-plus-fill',disabled=is_auth),
                sac.MenuItem('修改密码', icon='bi bi-key'),
            ]),

        ],
        key="selected_page",
        index=0,
        open_all=True,
        # on_change=change_menu
    )
    sac.divider()
   
if selected_page=="修改密码":
    try:
        authenticator.reset_password(username=ss['name'],
                                        fields = {'Form name':'重置密码', 'Current password':'当前密码',
                    'New password':'新密码','Repeat password':'重复密码',
                    'Reset':'重置'})
    except Exception as e:
        st.error(e)

if selected_page == "知识库管理":
    knowledge_base_page()
if selected_page == "对话":
    dialogue_page(chat_box=chat_box)
if ss['authentication_status'] is None :
    st.switch_page("pages/login.py")
else:
    authenticator.logout(location='sidebar',button_name="退出") 


