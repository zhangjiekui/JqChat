    # docker run -it -p 8080:8080 --name aiosandbox enterprise-public-cn-beijing.cr.volces.com/vefaas-public/all-in-one-sandbox:1.0.0.125


# 修改镜像，安装Python包
    # docker run -it --name jqsandbox --rm --entrypoint /bin/bash enterprise-public-cn-beijing.cr.volces.com/vefaas-public/all-in-one-sandbox:1.0.0.125
    # pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/  #https://pypi.tuna.tsinghua.edu.cn/simple
    # /opt/python3.12/bin/pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
    # /opt/python3.12/bin/pip list
    # /opt/python3.12/bin/pip install plotly seaborn scipy geopy -i https://pypi.tuna.tsinghua.edu.cn/simple
    # mv /etc/apt/sources.list  /etc/apt/sources.list.bak
    # nano /etc/apt/sources.list
"""
    # 默认注释了源码镜像以提高 apt update 速度，如有需要可取消注释
deb https://mirrors.tuna.tsinghua.edu.cn/ubuntu/ jammy main restricted universe multiverse
# deb-src https://mirrors.tuna.tsinghua.edu.cn/ubuntu/ jammy main restricted universe multiverse

deb https://mirrors.tuna.tsinghua.edu.cn/ubuntu/ jammy-updates main restricted universe multiverse
# deb-src https://mirrors.tuna.tsinghua.edu.cn/ubuntu/ jammy-updates main restricted universe multiverse

deb https://mirrors.tuna.tsinghua.edu.cn/ubuntu/ jammy-backports main restricted universe multiverse
# deb-src https://mirrors.tuna.tsinghua.edu.cn/ubuntu/ jammy-backports main restricted universe multiverse

deb https://mirrors.tuna.tsinghua.edu.cn/ubuntu/ jammy-security main restricted universe multiverse
# deb-src https://mirrors.tuna.tsinghua.edu.cn/ubuntu/ jammy-security main restricted universe multiverse
"""


# 拷贝中文字体
# docker cp /data/projects/JqChatV2/JqChat/.Fonts_CN/MSYH jqsandbox:/usr/share/fonts/truetype/msyh/
# 验证系统可识别字体
# fc-list : family | grep -i "yahei"
# fc-list : family | grep -i "simhei"

# 保存和运行镜像[测试]
    # docker commit jqsandbox aio_sandbox_jq:v1.1
    # ！！！需映射/data/projects/JqChatV2/workspace到容器中
    # docker run -it -p 7080:8080 -v /data/projects/JqChatV2/workspace:/data/projects/JqChatV2/workspace -v /data/projects/JqChatV2/JqChat/.Fonts_CN/MSYH:/usr/share/fonts/truetype/msyh \ --name jqsandbox  aio_sandbox_jq:v1.0
    # sh /opt/gem/run.sh

# 正式运行镜像
"""
docker run -d \
  -p 7080:8080 \
  -v /data/projects/JqChatV2/workspace:/data/projects/JqChatV2/workspace \
  -v /data/projects/JqChatV2/JqChat/.Fonts_CN/MSYH:/usr/share/fonts/truetype/msyh \
  --name jqsandbox \
  --entrypoint sh \
  aio_sandbox_jq:v1.1 \
  /opt/gem/run.sh
"""

"""
Github:    https://github.com/agent-infra/sandbox

📖 Documentation: http://10.1.150.105:7080/v1/docs
🌐 VNC Browser:   http://10.1.150.105:7080/vnc/index.html?autoconnect=true
💻 VSCode Server: http://10.1.150.105:7080/code-server/
🤖 MCP Services:  http://10.1.150.105:7080/mcp

"""





# http://10.1.150.105:7080/mcp