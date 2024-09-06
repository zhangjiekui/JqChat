from web import *
from utils.utils import  get_img_base64
st.set_page_config(
        "晶奇聊天机器人",
        get_img_base64("chatchat_icon_blue_square_v2.png"),
        initial_sidebar_state="auto",
        menu_items={
             "About": f"""欢迎使用JingQi-Chat""",
        },
        layout="centered",
    )
st.markdown(
    """
    <style>
        [data-testid="stStatusWidget"] {
            visibility: hidden;
        }
        #MainMenu {visibility: hidden;}
        .stDeployButton {display:none;}
        footer {visibility: hidden;}
        #stDecoration {display:none;}
    </style>
    """,
    unsafe_allow_html=True)
st.sidebar.page_link("webui.py", label="登录",icon="🛅")
st.sidebar.page_link("pages/register.py", label="注册",icon="🆕")   
if 'authentication_status' not in ss:
    ss['authentication_status'] = None
if 'logout' not in ss:
    ss['logout'] = None
if 'name' not in ss:
    ss['name'] = None
    
st.info('请输入用户名密码进行登录...')
try:
    authenticator.login(location='main', fields = {'Form name':'登录', 'Username':'用户名', 'Password':'密码',
                'Login':'登录'})
except Exception as e:
    st.error(e)

if  ss["authentication_status"] is False:
    st.error('用户名密码错误')
if ss["authentication_status"] is True:
    
    st.switch_page("pages/main.py")   