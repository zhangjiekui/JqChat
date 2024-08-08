## Git同步

### 本地

```sh
cd /data/projects/JqChat
git add .
git commit -a
```

### 同步

```sh
git push
```
### 端口占用释放
```
sudo lsof -i :{port}
sudo kill -9 {pid}
```

## linux系统环境变量

```
export CUDA_VISIBLE_DEVICES='0,1,2,3'
export LM_USE_MODELSCOPE=True
export XINFERENCE_DISABLE_VLLM=0
export VLLM_USE_MODELSCOPE=True
export HF_ENDPOINT=https://hf-mirror.com
export OLLAMA_MODEL_DIR=/data/ollama_modles
export RAY_DEDUP_LOGS=0
export XINFERENCE_MODEL_SRC=modelscope
export XINFERENCE_HOME=/data/xinference
```
## pip / conda源

```
pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/

conda config --add channels https://mirrors.aliyun.com/anaconda/pkgs/main/
conda config --add channels https://mirrors.aliyun.com/anaconda/pkgs/free/
conda config --set show_channel_urls yes

```
## Lmdeploy 【经测试，存在问题】
#### 安装
```
workon xinfer
pip install lmdeploy
```
#### 使用modelscope下载模型
```
pip install modelscope
nano ~/.bashrc
export LMDEPLOY_USE_MODELSCOPE=True
source ~/.bashrc
```
#### 部署API服务

https://github.com/InternLM/lmdeploy/blob/main/docs/zh_cn/llm/api_server.md
https://github.com/InternLM/lmdeploy/blob/main/docs/zh_cn/llm/api_server_tools.md

参数：lmdeploy serve api_server -h
```
lmdeploy serve api_server Shanghai_AI_Laboratory/internlm2_5-20b-chat --server-port 9997 --tp 4 --log-level DEBUG
```
#### LMDeploy支持的Function/Tool Calling模型
LMDeploy 支持 InternLM2, InternLM2.5 和 Llama3.1 模型的工具调用

## Xinference LLM

#### 当前使用版本
原版/最新版是xinference 0.12.3 (2024-06-28)

**注意【qwen2  的72B Int4 gptq/awq  对应的max_seq_len=32000 & gpu_memory_utilization=0.90,gptq准确率和推理效率都更优】**
### 本地Pip安装运行

运行 xinference 框架服务
```
workon xinfer
nohup xinference-local -H 0.0.0.0 --log-level debug  >> /data/xinference/xinfer.log 2>&1 & 

tail -f /data/xinference/xinfer.log

ps -ef | grep 'xinference-local'     找到包含了【xinfer/bin/xinference-local -H 0.0.0.0】对应行的pid 然后 sudo kill -9 

```
运行加载 qwen2-instruct 模型ok
```
CUDA_VISIBLE_DEVICES=0,1,2,3 xinference launch --model-engine vllm --model-name qwen2-instruct --size-in-billions 72  --model-format awq --quantization Int4 --gpu_memory_utilization 0.95 --tensor_parallel_size 4 --max_model_len 32000 --n-gpu 4
```
### Docker运行

#### Docker参数配置
{
    "runtimes": {
        "nvidia": {
            "args": [],
            "path": "nvidia-container-runtime"
        }
    },
    "registry-mirrors": [
      "https://docker.m.daocloud.io",
      "https://docker.nju.edu.cn",
      "https://5vkaailq.mirror.aliyuncs.com",
      "http://hub-mirror.c.163.com",
      "https://docker.mirrors.ustc.edu.cn"
    ]
}

#### 更新镜像版本

docker pull xprobe/xinference:latest

#### Docker运行

```
docker run --shm-size=64g --name xinferencev111 -d -p 9997:9997 -e XINFERENCE_MODEL_SRC=modelscope -e HF_ENDPOINT=https://hf-mirror.com -v /home/jqsoft/.xinference:/root/.xinference -v /home/jqsoft/.cache/huggingface:/root/.cache/huggingface -v /home/jqsoft/.cache/modelscope:/root/.cache/modelscope -e CONTEXT_LENGTH=10000 -e NUM_GPUS=4 --gpus all xprobe/xinference:latest xinference-local -H 0.0.0.0 --log-level debug 

docker run --shm-size=64g --name xinferencev121 -d -p 9997:9997 -e XINFERENCE_MODEL_SRC=modelscope -e HF_ENDPOINT=https://hf-mirror.com -v /root/.xinference:/root/.xinference -v /root/.cache/huggingface:/root/.cache/huggingface -v /root/.cache/modelscope:/root/.cache/modelscope -e CONTEXT_LENGTH=10000 -e NUM_GPUS=4 --gpus all xprobe/xinference:latest xinference-local -H 0.0.0.0 --log-level debug
```

##### 参数

###### context_length【qwen1.5的72B Int4 gptq/awq 对应的设置context_length=10000】: 一个可选的整数，模型支持的最大上下文长度，包括输入和输出长度。如果未定义，默认值为2048个token（约1,500个词）。

###### 模型下载地址相关：-e XINFERENCE_MODEL_SRC=modelscope -e HF_ENDPOINT=https://hf-mirror.com

### 模型 【进入Docker Shell运行】
【qwen2  的72B Int4 gptq/awq  对应的**max_seq_len=32000 & gpu_memory_utilization=0.90**】,gptq准确率和推理效率都更优
![alt text](image.png)
【qwen1.5的72B Int4 gptq/awq  对应的**max_seq_len=10000 & gpu_memory_utilization=0.90**】
【qwen1.5的110B Int4 gptq/awq 对应的**max_seq_len=10000 & gpu_memory_utilization=0.95**】
【qwen1.5的72B Int4 gptq/awq 上面Docker运行对应的设置context_length=10000】

#### qwen1.5 72B INT4 gptq

```
CUDA_VISIBLE_DEVICES=0,1,2,3 xinference launch --model-engine vllm --model-name qwen1.5-chat --size-in-billions 72  --model-format gptq --quantization Int4 --gpu_memory_utilization 0.90 --tensor_parallel_size 4 --max_model_len 10000 --n-gpu 4
```

#### qwen1.5 72B INT4 awq

【qwen1.5的72B Int4 awq 对应的max_seq_len=10000 & gpu_memory_utilization=0.90，否则显存不足】

```
CUDA_VISIBLE_DEVICES=0,1,2,3 xinference launch --model-engine vllm --model-name qwen1.5-chat --size-in-billions 72  --model-format awq --quantization Int4 --gpu_memory_utilization 0.90 --tensor_parallel_size 4 --max_model_len 10000 --n-gpu 4 
```

##### 参数

###### max_model_len

容器启动日志中
Loading qwen1.5-chat with following model config：'max_model_len': 4096

max_model_len默认值4096，可能会报错误： Input prompt (4108 tokens) is too long and exceeds limit of 4096

###### max_seq_len & gpu_memory_utilization 【qwen1.5的72B INT4 对应的max_seq_len=10000 & gpu_memory_utilization=0.90，否则显存不足】

Initializing an LLM engine： max_seq_len=4096
RayWorkerVllm：If you are running out of memory, consider decreasing `gpu_memory_utilization` or enforcing eager mode. You can also reduce the `max_num_seqs` as needed to decrease memory usage.


## Ollama
Ollama(V0.3+) now supports tool calling: https://ollama.com/blog/tool-support 

langchain_ollama(V0.1+) from langchain_ollama import ChatOllama

pip install ollama -U: https://github.com/ollama/ollama-python

#### OpenAI compatibility
```
import openai

openai.base_url = "http://localhost:11434/v1"
openai.api_key = 'ollama'

response = openai.chat.completions.create(
	model="llama3.1",
	messages=messages,
	tools=tools,
)
```
#### ChatOllama
```
from langchain_ollama import ChatOllama # need langchain_ollama(V0.1+) 

# /data/projects/JqChat/jqcode/jq_agent/c0_init_env_models.py
def get_ollama_chat_model(self,model_name = "allenporter/xlam:7b",temperature=0.5,top_p=0.65, tools:list = None,verbose=True):
    ollama_chat_model = ChatOllama(model=model_name,temperature=temperature,top_p=top_p,verbose=verbose)
    print("-------ollama_chat_model详细信息-------")
    print(f'       ==Get ollama_chat_model successfully. model_name={model_name}, ollama_host = {self.ollama_host}')
    print("-------ollama_chat_model详细信息-------")
    if tools:
        return ollama_chat_model.bind_tools(tools)        
    return ollama_chat_model
```

1、安装
https://ollama.com/download/linux
```
curl -fsSL https://ollama.com/install.sh | sh
```
2、OLLAMA_HOST=0.0.0.0
https://github.com/ollama/ollama/blob/1a83581a8e1063418f5f1fec14638409d0681b68/docs/faq.md
```
systemctl edit ollama.service
```
For each environment variable, add a line `Environment` under section `[Service]`:
```
[Service]
Environment="OLLAMA_HOST=0.0.0.0"
```
3、运行模型
```
ollama run llama3-groq-tool-use:8b-q8_0
```

4、ollama ps 查看运行中的模型，以及是否使用了GPU
```
ollama ps
```
结果如下
```
NAME      	ID          	SIZE 	PROCESSOR	UNTIL
llama3:70b	bcfb190ca3a7	42 GB	100% GPU 	4 minutes from now
```


5、OLLAMA_HOST环境变量使用

参见  https://github.com/zhangjiekui/JqChat/commit/73fe468524983d71fca3e620006ea122f20550f0

```
在jqchat项目的.env中增加一行:OLLAMA_HOST = http://10.1.150.106:11434

或者

# OLLAMA_HOST env setting MUST be done before you import langchain_ollama package in your code.
import os
os.environ['OLLAMA_HOST'] = "http://10.1.150.106:11434"
```
6、查看Log
```
journalctl -e -u ollama
```
## HF模型下载方法：

在目标文件夹下/data/models：
1、安装hfd.sh
```
wget https://hf-mirror.com/hfd/hfd.sh
chmod a+x hfd.sh
```
2、安装aria2
```
apt install aria2
```

3、下载模型（含用户名和hf token,hf token可能需要在HF站点重新获取更新）
```
./hfd.sh jinaai/jina-embeddings-v2-base-zh --tool aria2c -x 4 --hf_username nwzjk --hf_token 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

./hfd.sh maidalun1020/bce-embedding-base_v1 --tool aria2c -x 4 --hf_username nwzjk --hf_token hf_BmTHDRaTNXlDfQiVTfPZBCMlcbaDVqHlX

./hfd.sh maidalun1020/bce-reranker-base_v1 --tool aria2c -x 4 --hf_username nwzjk --hf_token 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
```

## Elasticsearch https://www.elastic.co/guide/en/elasticsearch/reference/current/docker.html
### 
```
docker network create elastic
sysctl -w vm.max_map_count=262144
docker run --name es105 --net elastic -p 9200:9200 -it -m 2GB docker.elastic.co/elasticsearch/elasticsearch:8.14.0
```
### 复制elastic user password and an enrollment token for Kibana.
#### elastic user
elastic
#### elastic user password ：
esnNFWQbCIspxTPGwOom
#### enrollment token for Kibana：
eyJ2ZXIiOiI4LjE0LjAiLCJhZHIiOlsiMTcyLjE4LjAuMjo5MjAwIl0sImZnciI6ImQ1N2U2MTk5ZDFhMTE1ZmMzZTBkZjEzNGQ0NzA0Yjk3Y2Q0NzA1NWFkYmQxNjFhNDQxOWQzZTY4MWMwNTBmMzciLCJrZXkiOiIyQUhINjQ4QmQtWTAwMy14bl9wVDp2ZVRzUVhyOVJzQ08tNTlXNDh0OGlRIn0=
#### HTTP CA certificate SHA-256 fingerprint:
d57e6199d1a115fc3e0df134d4704b97cd47055adbd161a4419d3e681c050f37

docker run -e "ENROLLMENT_TOKEN=<token>" docker.elastic.co/elasticsearch/elasticsearch:8.14.0

重新生成elastic user password and an enrollment token for Kibana.
```
docker exec -it es105 /usr/share/elasticsearch/bin/elasticsearch-reset-password -u elastic
docker exec -it es105 /usr/share/elasticsearch/bin/elasticsearch-create-enrollment-token -s kibana
```
## Kibana https://www.elastic.co/guide/en/kibana/current/docker.html
docker pull docker.elastic.co/kibana/kibana:8.14.0
docker run --name kib01 --net elastic -p 5601:5601 docker.elastic.co/kibana/kibana:8.14.0
## 本项目的Installation

ubuntu上推荐下面的安装和运行方法:

```
### 安装：
git clone https://github.com/zhangjiekui/JqChat.git
cd JqChat
make compile_frontend （如出现错误请升级node）
pip install -e .
### 后台运行：
nohup jqchat >> jqchat.log 2>&1 & 
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

### gpt-code-ui

github code: https://github.com/ricklamers/gpt-code-ui

An open source implementation of OpenAI's ChatGPT [Code interpreter](https://openai.com/blog/chatgpt-plugins#code-interpreter).

Simply ask the OpenAI model to do something and it will generate & execute the code for you.

Read the [blog post](https://ricklamers.io/posts/gpt-code) to find out more. This is the tech architecture:

<img src="https://github.com/zhangjiekui/AgentRagChatCI/blob/main/frontend/public/assets/tech-architecture-diagram.png" alt="Tech Architecture Diagram" width=600 />
