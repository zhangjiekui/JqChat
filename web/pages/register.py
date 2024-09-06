from web import *
st.sidebar.page_link("webui.py", label="登录",icon="🛅")
st.sidebar.page_link("pages/register.py", label="注册",icon="🆕")    
try:
    email_of_registered_user, username_of_registered_user, name_of_registered_user = authenticator.register_user(
        pre_authorization=False,clear_on_submit=True,
        fields = {'Form name':'注册新用户', 'Email':'邮箱地址', 'Username':'用户昵称',"Name":"用户名",
        'Password':'密码', 'Repeat password':'重复密码','Captcha':'验证码',
        'Register':'注册'}
        )
    st.warning("密码至少包含8-20位大小写字母，数字和特殊字符的组合")
    if email_of_registered_user:
        st.success('注册用户成功')
        st.switch_page("webui.py")
except Exception as e:
    st.error(e)

with open(CONFIG_FILENAME, 'w') as file:
    yaml.dump(config, file, default_flow_style=False)