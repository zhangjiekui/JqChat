
## Git同步
### 本地
```sh
cd /home/jqsoft/AgentRagChatCI/AgentRagChatCI-0.0.1
git add .
git commit -a
```

### 同步
```sh
git push
```

## Installation

ubuntu上推荐下面的安装和运行方法:
```
### 安装：
git clone https://github.com/zhangjiekui/JqChat.git
cd JqChat
make compile_frontend （如出现错误请升级node）
pip install -e .
### 运行：
jqchat
### 开发/调试：
直接运行JqChat\main.py
```


## 安装常用库包

In order to make basic dependencies available it's recommended to run the following `pip` install
in the Python environment that is used in the shell where you run `jqchat`:

```sh
### todo:需要更新版本
pip install "numpy>=1.24,<1.25" "dateparser>=1.1,<1.2" "pandas>=1.5,<1.6" "geopandas>=0.13,<0.14" "tabulate>=0.9.0<1.0" "PyPDF2>=3.0,<3.1" "pdfminer>=20191125,<20191200" "pdfplumber>=0.9,<0.10" "matplotlib>=3.7,<3.8"
```
## 常见问题解决
### matplotlib绘图中文和负号显示问题
```
1、参考https://blog.csdn.net/m0_52650517/article/details/120590020
        import matplotlib
        print(matplotlib.__file__)
        找到matplotlib字体存储路径==>matplotlib/mpl-data/fonts/ttf/目录下

2、将C:\Windows\Fonts\Microsoft YaHei UI文件夹下的三个字体文件（也已上传到本库中）拷贝到==>matplotlib/mpl-data/fonts/ttf/目录下
3、设置字体。修改该文件 ==>/matplotlib/mpl-data/matplotlibrc。增加下面两行
        font.family:  sans-serif
        font.sans-serif: Microsoft YaHei
4、删除 matplotlib 缓存
        cd ~/.cache/matplotlib
        rm -rf *.*
```


## User interface
<img src="https://github.com/ricklamers/gpt-code-ui/assets/1309307/c29c504a-a7ed-4ae0-9360-d7224bc3e3d6" alt="GPT-Code logo" width="100%" />
 
## Features
- File upload
- File download
- Context awareness (it can refer to your previous messages)
- Generate code
- Run code (Python kernel)
- Model switching (GPT-3.5 and GPT-4)

## Misc.
### Using .env for OpenAI key and `OPENAI_API_BASE` for local model api
You can put a .env in the working directory to load the `OPENAI_API_KEY` and `OPENAI_API_BASE` environment variable.
Set `OPENAI_API_BASE` to change the OpenAI API endpoint that's being used (note this environment variable includes the protocol `http://10.1.150.105:9997/v1`).

### Configurables
Set the `API_PORT`, `WEB_PORT`, `SNAKEMQ_PORT` variables to override the defaults.


### Docker
[localagi](https://github.com/localagi) took the effort of bundling the Python package in a Docker container. Check it out here: [gpt-code-ui-docker](https://github.com/localagi/gpt-code-ui-docker).

## Reference Project
<img src="https://github.com/ricklamers/gpt-code-ui/assets/1309307/9ad4061d-2e26-4407-9431-109b650fb022" alt="GPT-Code logo" width=240 />

An open source implementation of OpenAI's ChatGPT [Code interpreter](https://openai.com/blog/chatgpt-plugins#code-interpreter).

Simply ask the OpenAI model to do something and it will generate & execute the code for you.

Read the [blog post](https://ricklamers.io/posts/gpt-code) to find out more. This is the tech architecture:

<img src="https://github.com/zhangjiekui/AgentRagChatCI/blob/main/frontend/public/assets/tech-architecture-diagram.png" alt="Tech Architecture Diagram" width=600 />
