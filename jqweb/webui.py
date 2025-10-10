import sys
import streamlit as st
import streamlit_antd_components as sac
from datetime import datetime
from jqcode.jq_kb_manegement.configs import VERSION
from jqcode.jq_kb_manegement.server.utils import api_address
from jqweb.pages.dialogue.dialogue import dialogue_page
from jqweb.pages.knowledge_base.knowledge_base import knowledge_base_page
from jqweb.utils.utils import ApiRequest, get_img_base64
from jqcode.jq_kb_manegement.server.knowledge_base.kb_service.base import get_kb_details
from jqcode.jq_utils.logger import jqkj_logger
logger = jqkj_logger(__file__).get_logger()

api = ApiRequest(base_url=api_address())

# 简单模拟用户数据库（仅用于演示）
USER_DB = {
    "admin": "adminpassword",
    "user1": "userpassword1",
    "user2": "userpassword2",
    "user3": "userpassword3",
}
def login_page():
    # 创建一个居中的容器来保持合适的页面宽度
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        
        st.title("🔒 用户登录")
        username = st.text_input("用户名")
        password = st.text_input("密码", type="password")

        # 添加用户协议和隐私政策链接及同意选项
        # 使用CSS精确控制垂直对齐
        st.markdown("""
        <style>
            div[data-testid="column"] {
                align-items: center;  /* 垂直居中 */
                display: flex;
            }
            /* 针对checkbox的特殊调整 */
            .stCheckbox {
                margin-top: 0 !important;
                margin-bottom: 0 !important;
                padding-top: 0 !important;
                padding-bottom: 0 !important;
            }
            /* 确保markdown容器对齐 */
            .stMarkdown {
                display: flex;
                align-items: center;
            }
        </style>
        """, unsafe_allow_html=True)

        # 创建等宽列布局
        col1, col2 = st.columns([8, 10])

        with col1:
            # 调整checkbox的标签间距
            agree_both = st.checkbox(
                "我已阅读并同意",
                value=True,
                key="agree_both",
                label_visibility="visible"
            )

        with col2:
            # 使用span包裹并设置行高匹配
            st.markdown("""
                <span style="line-height: 20px;">
                    <a href="/workspace/static/agreement.htm" target="_blank" style="color: #1f77b4; text-decoration: none;">用户协议</a>
                    <span>和</span>
                    <a href="/workspace/static/policy.htm" target="_blank" style="color: #1f77b4; text-decoration: none;">隐私政策</a>
                </span>
            """, unsafe_allow_html=True)
       
        # 登录按钮
        inline_col1, inline_col2, inline_col3 = st.columns(3)
        with inline_col2:
            login_button = st.button("登录", type="primary")
        
        if login_button:
            # 检查是否同意了协议
            if not agree_both:
                st.warning("⚠️ 请先同意用户协议和隐私政策")
                return
                
            # 验证用户名和密码
            if username in USER_DB and USER_DB[username] == password:
                st.session_state["logged_in"] = True
                st.session_state["username"] = username
                st.success("登录成功！")
                st.rerun()
            else:
                st.error("用户名或密码错误")

def register_page():
    # 创建一个居中的容器来保持合适的页面宽度
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.title("📝 用户注册")
        new_username = st.text_input("新用户名")
        new_password = st.text_input("新密码", type="password")
        confirm_password = st.text_input("确认密码", type="password")
        register_button = st.button("注册")

        if register_button:
            st.error("仅供测试使用，请勿注册正式用户。")
            if new_username in USER_DB:
                st.error("用户名已存在，请更换一个。")
            elif new_password != confirm_password:
                st.error("两次输入的密码不一致。")
            elif len(new_password) < 6:
                st.error("密码长度至少为6位。")
            else:
                USER_DB[new_username] = new_password
                st.success("注册成功！请前往登录。")

def logout():
    st.session_state.clear()
    st.success("您已退出登录")
    st.rerun()

if __name__ == "__main__":
    is_lite = "lite" in sys.argv

    # 初始化登录状态
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False

    # 如果未登录，只显示登录/注册页
    if not st.session_state["logged_in"]:
        # 设置页面配置（即使在登录页也要设置）
        st.set_page_config(
            "晶灵智能体 - 登录",
            get_img_base64("logo_chat_avatar.png") if "get_img_base64" in globals() else None,
            layout="centered",  # 使用居中布局
        )
        
        # 隐藏deploy按钮和优化样式
        st.markdown(
            """
            <style>
            .stDeployButton {display:none;}
            .stSelectbox label {font-weight: bold;}
            </style>
            """,
            unsafe_allow_html=True,
        )
        
        # 创建居中的选择操作部分
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("### 🤖 晶灵智能体")
            st.markdown("---")
            page = st.selectbox("选择操作", ["登录", "注册"], key="auth_page_selector")
        
        # 根据选择显示对应的页面
        if page == "登录":
            login_page()
        else:
            # register_page()
            with col2:
                st.error("仅供测试使用，禁止注册正式用户。",width=400)
        st.stop()
    
    # 已登录，显示主应用内容
    st.set_page_config(
        "晶灵智能体",
        get_img_base64("logo_chat_avatar.png"),
        initial_sidebar_state="auto",
        menu_items={
            "Get Help": "https://github.com/zhangjiekui/JqChat",
            "Report a bug": "https://github.com/zhangjiekui/JqChat/issues",
            "About": f"""欢迎使用JingQi-Chat""",
        },
        layout="wide",
    )

    # 优化整体页面样式
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
        /* 用户信息区域样式 */
        .user-info-box {
            background-color: #f0f2f6;
            border-radius: 8px;
            padding: 12px;
            margin: 10px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .user-info-box p {
            margin: 5px 0;
            font-size: 14px;
        }
        /* 退出按钮样式 */
        .logout-btn {
            background-color: #ff4b4b !important;
            color: white !important;
            border: none !important;
        }
        .logout-btn:hover {
            background-color: #ff3333 !important;
        }
        /* 页面标题样式 */
        .page-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px 20px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        /* 侧边栏组件样式 */
        .sidebar-section {
            margin-bottom: 15px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # 获取知识库列表（用于对话页面）
    try:
        kb_list = {x["kb_name"]: x for x in get_kb_details()}
        kb_names = list(kb_list.keys())
        kb_names.sort()
    except Exception as e:
        kb_list = {}
        kb_names = []
        st.sidebar.error("获取知识库信息错误")

    with st.sidebar:
        st.image(
            get_img_base64("logo_chat_avatar_jingqi_chat.png"), use_container_width=True
        )
        
        st.caption(
            f"""<p align="right">当前版本：{VERSION}</p>""",
            unsafe_allow_html=True,
        )

        # 知识库选择区域（仅在对话页面显示）
        if st.session_state.get("selected_page", "对话") == "对话":
            st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
            st.subheader("⚙️ 对话设置")
            
            # 知识库选择逻辑
            if (
                "selected_kb_name" in st.session_state
                and st.session_state["selected_kb_name"] in kb_names
            ):
                selected_kb_index = kb_names.index(st.session_state["selected_kb_name"]) + 1  # +1 because of "不使用知识库"
            else:
                selected_kb_index = 0
                
            def format_selected_kb(kb_name: str) -> str:
                if kb_name == "不使用知识库":
                    return kb_name
                if kb := kb_list.get(kb_name):
                    return f"{kb_name}"
                else:
                    return kb_name  
                    
            if "selected_kb_info" not in st.session_state:
                st.session_state["selected_kb_info"] = ""
                
            selected_kb = st.selectbox(
                "请选择知识库：",
                ["不使用知识库"] + kb_names,
                format_func=format_selected_kb,
                index=selected_kb_index,
                key="main_kb_select"
            )
            
            # 更新session state
            st.session_state["selected_kb_name"] = selected_kb if selected_kb != "不使用知识库" else "default"
            
            is_memory = st.checkbox("启用会话记忆", value=True, key="main_memory_checkbox")
            is_rewrite = st.checkbox("启用问题重写", value=False, key="main_rewrite_checkbox")
            
            st.markdown('</div>', unsafe_allow_html=True)
            st.markdown("---")

        # 主菜单
        selected_page = sac.menu(
            [
                sac.MenuItem("对话", icon="chat"),
                sac.MenuItem("知识库管理", icon="hdd-stack"),
            ],
            key="selected_page",
            open_index=0,
        )

        sac.divider()

        # 用户信息和退出登录区域 - 放在最下方
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M')
        st.markdown(
            f"""
            <div class="user-info-box">
                <p><strong>👤 当前用户:</strong>   {st.session_state['username']}</p>
                <p><strong>🔑 登录状态:</strong> <span style="color: green;"> 已登录</span></p>
            </div>
            """,
            unsafe_allow_html=True
        )

        # 退出登录按钮
        if st.button("🚪 退出登录", use_container_width=True, key="logout_btn"):
            logout()

    user_request_url = st.context.url
    api_url = api.base_url 
    print(f"在webui.py中获取到请求的 {user_request_url = }")
    print(f"api_url为 {api_url = }")
    logger.warning(f"在webui.py中获取到请求的 {user_request_url = }")
    local_server_url = "10.1.150.105"
    local_urls = ["127.0.0.1",local_server_url, "localhost", "0.0.0.0"]

    for local_url in local_urls:
        if local_url in user_request_url:
            if local_url!=local_server_url:
                user_request_url = user_request_url.replace(local_url,local_server_url)
                print(f"因为是本地请求{local_url=}，需替换为服务器地址({local_server_url=}),替换后的结果为： {user_request_url = }")
            api_url_port = api_url.split(":")[-1]
            user_request_url_port = user_request_url.split(":")[-1]
            user_request_url = user_request_url.replace(user_request_url_port,api_url_port)
            print(f"因为是本地请求，需替换web_port({user_request_url_port})为api_port({api_url_port}),替换后的结果为： {user_request_url = }")
            break
    # 传递知识库相关参数到对话页面
    if selected_page == "知识库管理":
        knowledge_base_page(api=api, is_lite=is_lite)
    else:
        # 传递参数到对话页面
        dialogue_kwargs = {
            "api": api,
            "is_lite": is_lite,
            "selected_kb": selected_kb if 'selected_kb' in locals() else "不使用知识库",
            "is_memory": st.session_state.get("main_memory_checkbox", True),
            "is_rewrite": st.session_state.get("main_rewrite_checkbox", True),
            "user_request_url":user_request_url
        }
        dialogue_page(**dialogue_kwargs)


        # {st.session_state['username']}