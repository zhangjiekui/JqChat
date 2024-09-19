## Git同步
### 本地
```sh
cd /data/projects/JqChatV2/JqChat
git pull
```

```sh
cd /data/projects/JqChatV2/JqChat
git add .
git commit -a
```
### 同步

```sh
cd /data/projects/JqChatV2/JqChat
git push
```
### 端口占用释放
```
sudo lsof -i :{port}
sudo kill -9 {pid}
```
## 添加项目路径
```
export PYTHONPATH=$PYTHONPATH:/data/projects/JqChatV2/JqChat:/data/projects/JqChatV2/JqChat/jqcode:/data/projects/JqChatV2/JqChat/kernel_program:/data/projects/JqChatV2/JqChat/web
```
or
```
export PYTHONPATH=/data/projects/JqChatV2/JqChat:/data/projects/JqChatV2/JqChat/jqcode:/data/projects/JqChatV2/JqChat/kernel_program:/data/projects/JqChatV2/JqChat/web
```
## vllm6.0+与qwen2.5已支持函数调用 
https://qwen.readthedocs.io/zh-cn/latest/framework/function_call.html#vllm
https://qwenlm.github.io/zh/blog/qwen2.5/

### Context Length: Full 131,072 tokens and generation 8192 tokens
```
VLLM_USE_MODELSCOPE=True CUDA_VISIBLE_DEVICES=0,1,2,3 VLLM_ALLOW_ENGINE_USE_RAY=1 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True vllm serve qwen/Qwen2.5-72B-Instruct-GPTQ-Int4 --served-model-name qwen25b70 --enable-auto-tool-choice --tool-call-parser hermes --host 0.0.0.0 --port 9997 --max-model-len 8192 --tensor-parallel-size 4 --num-scheduler-steps 8
```

## Ollama： qwen2和llama3.1_70b_chinese_chat
都支持Tools
```
docker pull ollama/ollama:latest
docker run --gpus all -d -v /data/ollama_v_docker/:/root/.ollama -p 11436:11434 --name ollama ollama/ollama
```
### In vscode: Attach Shell in ollama docker:
```
ollama run qwen2:72b
ollama run wangshenzhi/llama3.1_70b_chinese_chat
```
经测试，完全可用，就是生成速度要慢一半（17 tokens/s），而xinfer的生成速度接近40 tokens/s

## Xinference LLM
#### 当前使用版本
**注意:gptq准确率和推理效率都更优【qwen2 72B Int4 gptq/awq设置对应的max_seq_len=32000 & gpu_memory_utilization=0.95】**
### 本地Pip安装运行

运行 xinference 框架服务
```
workon xinfer
nohup xinference-local -H 0.0.0.0 --log-level debug  >> /data/xinference/xinfer.log 2>&1 & 
tail -f /data/xinference/xinfer.log
```
```
tail -f /data/xinference/xinfer.log
```
```
ps -ef | grep 'xinference-local'     找到包含了【xinfer/bin/xinference-local -H 0.0.0.0】对应行的pid 然后 sudo kill -9 
```

运行加载 qwen2-instruct gptq Int4模型ok
```
CUDA_VISIBLE_DEVICES=0,1,2,3 xinference launch --model-engine vllm --model-name qwen2-instruct --size-in-billions 72  --model-format gptq --quantization Int4 --gpu_memory_utilization 0.95 --tensor_parallel_size 4 --max_model_len 32000 --n-gpu 4
```

必要时可以在Web模型加载页面的下方指定模型本地路径，如：
/data/xinference/huggingface/models--jinaai--jina-reranker-v2-base-multilingual/snapshots/298e48cada4a9318650d7fbd795f63827f884087

![alt text](image.png)


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
### Docker运行
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

### 中文分词（以新的8.15.0作为例子）

#### 拉取8.15.0
```
docker pull docker.elastic.co/elasticsearch/elasticsearch:8.15.0
```
```
docker pull docker.elastic.co/kibana/kibana:8.15.0
```
#### 运行8.15.0
为避免冲突，修改了--name ， -p 参数（将容器内部的9200端口映射到主机的9201端口）
```
docker run --name es815 --net elastic -p 9200:9200 -it -m 1GB docker.elastic.co/elasticsearch/elasticsearch:8.15.0
```

```
docker run --name kib815 --net elastic -p 5601:5601 docker.elastic.co/kibana/kibana:8.15.0 
```
运行得到以下消息后：
i Kibana has not been configured.
Go to http://0.0.0.0:5601/?code=630962 to get started.

使用浏览器打开以下：
```
http://10.1.150.105:5601/?code=630962
```
然后
（1）输入Copy the following enrollment token and paste it into Kibana in your browser
（2）使用用户： elastic 密码：GbWW=NGDy=EAd32Re-a0 登录

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
以下是运行elastic docker后输出的备用信息：
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Elasticsearch security features have been automatically configured!
✅ Authentication is enabled and cluster connections are encrypted.

ℹ️  Password for the elastic user (reset with `bin/elasticsearch-reset-password -u elastic`):
  GbWW=NGDy=EAd32Re-a0

ℹ️  HTTP CA certificate SHA-256 fingerprint:
  b1cadda04bd4ed785050b720849a8dd180a4a7e29bb7ee76d2eb688a11295b31

ℹ️  Configure Kibana to use this cluster:
• Run Kibana and click the configuration link in the terminal when Kibana starts.
• Copy the following enrollment token and paste it into Kibana in your browser (valid for the next 30 minutes):
  eyJ2ZXIiOiI4LjE0LjAiLCJhZHIiOlsiMTcyLjE4LjAuMjo5MjAwIl0sImZnciI6ImIxY2FkZGEwNGJkNGVkNzg1MDUwYjcyMDg0OWE4ZGQxODBhNGE3ZTI5YmI3ZWU3NmQyZWI2ODhhMTEyOTViMzEiLCJrZXkiOiJmYk9KalpFQkxPZ1dUSDFEQTlXMTp2emRLZVZ0Q1FUS3h5RXEyNEJPdWlBIn0=

ℹ️ Configure other nodes to join this cluster:
• Copy the following enrollment token and start new Elasticsearch nodes with `bin/elasticsearch --enrollment-token <token>` (valid for the next 30 minutes):
  eyJ2ZXIiOiI4LjE0LjAiLCJhZHIiOlsiMTcyLjE4LjAuMjo5MjAwIl0sImZnciI6ImIxY2FkZGEwNGJkNGVkNzg1MDUwYjcyMDg0OWE4ZGQxODBhNGE3ZTI5YmI3ZWU3NmQyZWI2ODhhMTEyOTViMzEiLCJrZXkiOiJlN09KalpFQkxPZ1dUSDFEQTlXbjpqc2I4Sy1xX1FaaU5YZWY0ankzQ05BIn0=

  If you're running in Docker, copy the enrollment token and run:
  `docker run -e "ENROLLMENT_TOKEN=<token>" docker.elastic.co/elasticsearch/elasticsearch:8.15.0`

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```
#### 安装插件
进入运行的8.15.0docker中
1、查看已安装的插件
```
bin/elasticsearch-plugin list
```
2、安装
2.1 安装smartcn 【for Chinese or mixed Chinese-English text https://www.elastic.co/guide/en/elasticsearch/plugins/current/analysis-smartcn.html】  
bin/elasticsearch-plugin install analysis-smartcn 
bin/elasticsearch-plugin install https://get.infini.cloud/elasticsearch/analysis-ik/8.15.0

2.2 restart Elasticsearch to activate any plugins installed
如果直接reatert不行，可以先stop再start

3、测试是否生效（运行kibana，找到management下的dev_tools）
即http://127.0.0.1:5602/app/dev_tools#/console

运行：
```
POST _analyze
{  
    "analyzer": "smartcn",
    "text": "中华人民共和国国歌"  
}
```
结果:
```
{
  "tokens": [
    {
      "token": "中华人民共和国",
      "start_offset": 0,
      "end_offset": 7,
      "type": "CN_WORD",
      "position": 0
    },
    {
      "token": "国歌",
      "start_offset": 7,
      "end_offset": 9,
      "type": "CN_WORD",
      "position": 1
    }
  ]
}
```
4、配置全局生效 [https://wenku.csdn.net/answer/rknu3d60fw] 
```
注意：这个设置只适用于新创建的索引。对于已经存在的索引，需要手动更新其分词器设置
``` 
要设置Elasticsearch(ES)的默认分词器，你需要修改索引的分析器设置。以下是设置默认分词器的步骤:
(1).打开 Kibana 控制台或通过命令行访问 ES。
(2).创建或更新一个索引模板，以便在索引创建时自动应用设置。
```
PUT _index_template/default
{
    "index_patterns":["^[^.*]"],
    "template":{
        "settings":{
            "index":{
                "analysis":{
                    "analyzer":{
                        "default":{
                            "type":"smartcn"
                        }
                    }
                }
            }
        }
    }
}

5、验证全局是否生效
```
GET _index_template/default
```
注意：这个设置只适用于新创建的索引。对于已经存在的索引，需要手动更新其分词器设置
```
6、新建一个索引，如test_doc_tree_reader
curl -X GET "http://10.1.150.105:9200/test_doc_tree_reader/_mapping?pretty"

<!-- 修改elasticsearch的/config/elasticsearch.yml
1)复制出来 docker cp es105:/usr/share/elasticsearch/config/elasticsearch.yml elasticsearch.yml
2）修改
打开elasticsearch.yml文件
在最后面添加以下内容：
``` -->
#----------------------- begin 中文分词器配置 -------------------------
index:
  analysis:
    analyzer:
      ik_max_word:
        type: custom
        tokenizer: ik_max_word
      ik_smart:
        type: custom
        tokenizer: ik_smart

# {
#   "mappings": {
#     "properties": {
#       "content": {
#         "type": "text",
#         "analyzer": "ik_max_word",
#         "search_analyzer": "ik_max_word"
#       }
#     }
#   }
# }
#----------------------- 结束 中文分词器配置 -------------------------
```
3）复制回去
docker cp elasticsearch.yml es105:/usr/share/elasticsearch/config/elasticsearch.yml
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

## 相关的项目资源

### File System Crawler for Elasticsearch  
https://github.com/dadoonet/fscrawler  

### Elasticsearch Python Client
pip install elasticsearch -U
https://github.com/elastic/elasticsearch-py 

### elasticsearch-dsl-py
pip install elasticsearch-dsl -U
https://github.com/elastic/elasticsearch-dsl-py

### Searx.space元搜索引擎聚合地址
https://searx.space/


### 基于VLLM的Functionary函数调用模型可以无缝使用，并且是本地python文件运行的，好调试
### 基于Ollama的返回的是dict，需要自己解析成工具调用，但正确率似乎很高
https://github.com/MeetKai/functionary



## VLLM
```
### need vllm 6.0
workon xinfernew 
CUDA_VISIBLE_DEVICES=0,1,2,3 VLLM_ALLOW_ENGINE_USE_RAY=1 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True python -m vllm.entrypoints.openai.api_server --served-model-name hermes --model /data/models/Hermes-3-Llama-3.1-70B.Q4_K_M.gguf --host 0.0.0.0 --port 9997 --tensor-parallel-size 4 --gpu-memory-utilization 0.98 --max_model_len 32000 --dtype auto  --distributed-executor-backend=ray --enforce_eager --use_v2_block_manager --chat-template /data/models/tool_chat_template_hermes.jinja --enable-auto-tool-choice --tool-call-parser hermes


python -m vllm.entrypoints.openai.api_server --served-model-name qwen2-instruct --model /data/xinference/modelscope/hub/qwen/Qwen2-72B-Instruct-GPTQ-Int4 --host 0.0.0.0 --port 9997 --max-model-len 32000 --tensor-parallel-size 4 --num-scheduler-steps 8 --enable-auto-tool-choice --tool-call-parser hermes

修改：/data/xinference/modelscope/hub/qwen/Qwen2-72B-Instruct-GPTQ-Int4/tokenizer.json 
#### "added_tokens": [
    {
      "id": 220000,
      "content": "<tool_call>",
      "single_word": false,
      "lstrip": false,
      "rstrip": false,
      "normalized": false,
      "special": true
    },
    {
      "id": 220001,
      "content": "</tool_call>",
      "single_word": false,
      "lstrip": false,
      "rstrip": false,
      "normalized": false,
      "special": true
    },

运行结果输出为:
"CODE_GENERATION\n```python\nimport matplotlib.pyplot as plt\nimport numpy as np\n\nx = np.linspace(-np.pi, np.pi, 100)\ny = np.sin(x)\n\nplt.plot(x, y)\nplt.xlabel('x')\nplt.ylabel('sin(x)')\nplt.title('Sin Curve')\nplt.show()\n```"


"WEB_SEARCH\nThe current weather in San Francisco (SF) is 13°C with overcast clouds. In Los Angeles (LA), the weather is 21°C with clear skies. Please note that these conditions can change, so it's best to check a weather service for the most up-to-date information."


workon xinfer
vllm serve /data/xinference/cache/mistral-large-instruct-gptq-123b --model TechxGenus/Mistral-Large-Instruct-2407-GPTQ  --tensor-parallel-size 4  --gpu-memory-utilization 0.98 --max_model_len 3000 --quantization gptq_marlin --enforce-eager --served-model-name mistral qwen2-instruct --port 9999 --api-key abc123
能跑起来，但应用到项目中，存在很多问题
#### Mistral-large
python -m vllm.entrypoints.openai.api_server     --host 0.0.0.0     --model /data/xinference/cache/mistral-large-instruct-gptq-123b     --quantization gptq_marlin     --port 9999     --max-model-len 3000     --gpu-memory-utilization 0.98     --tensor-parallel-size 4     --served-model-name mistral qwen2-instruct      --enforce-eager      --api-key abc123

#### Mistral-Nemo
VLLM_ATTENTION_BACKEND=XFORMERS python -m vllm.entrypoints.openai.api_server --model AI-ModelScope/Mistral-Nemo-Instruct-2407 --gpu-memory-utilization 0.75 --host 0.0.0.0 --port 9999 -tp 4 --max-model-len 17000 --served-model-name mistral qwen2-instruct --trust-remote-code --enable-prefix-caching


在bashrc中增加 export VLLM_API_KEY=abc123


vllm serve /data/xinference/cache/mistral-large-instruct-gptq-123b --model /data/xinference/cache/mistral-large-instruct-gptq-123b --quantization gptq  --tensor-parallel-size 4  --gpu-memory-utilization 0.95 --trust-remote-code
```

https://github.com/vllm-project/vllm/blob/22b39e11f2eca7dd70bcef3760cd5da149412d00/docs/source/serving/openai_compatible_server.md?plain=1#L114
vLLM supports only named function calling in the chat completion API. The `tool_choice` options `auto` and `required` are **not yet supported** but on the roadmap.
To use a named function you need to define the function in the `tools` parameter and call it in the `tool_choice` parameter.
It is the callers responsibility to prompt the model with the tool information, vLLM will not automatically manipulate the prompt. **This may change in the future.**
vLLM will use guided decoding to ensure the response matches the tool parameter object defined by the JSON schema in the `tools` parameter.
Please refer to the OpenAI API reference documentation for more information.


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
lmdeploy serve api_server Shanghai_AI_Laboratory/internlm2_5-20b-chat --server-port 9997 --tp 4 --log-level INFO DEBUG
```
#### LMDeploy支持的Function/Tool Calling模型
LMDeploy 支持 InternLM2, InternLM2.5 和 Llama3.1 模型的工具调用
但存在一堆的问题。我提的issues：https://github.com/InternLM/lmdeploy/issues/2366



## RapidOCR 
### 源码 https://github.com/RapidAI/RapidOCR
### 文档 https://rapidai.github.io/RapidOCRDocs/

### 【CPU端】pip install rapidocr_onnxruntime 
#### rapidocr_api https://rapidai.github.io/RapidOCRDocs/install_usage/rapidocr_api/usage/
### 【GPU端】pip install rapidocr-paddle 
#### 【文档】https://rapidai.github.io/RapidOCRDocs/install_usage/rapidocr_paddle/usage/
#### 【Pypi】https://pypi.org/project/rapidocr-paddle/#history
![alt text](image.png)



