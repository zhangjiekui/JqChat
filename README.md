最新的VLLM运行命令
### Qwen2.5
workon vllm
CUDA_VISIBLE_DEVICES=0,1 nohup vllm serve /data/xinference/modelscope/hub/qwen/Qwen2.5-32B-Instruct-AWQ --served-model-name qwen25b70 --enable-auto-tool-choice --tool-call-parser hermes --host 0.0.0.0 --port 9997 --max-model-len 32000 --tensor-parallel-size 2 --distributed-executor-backend ray --use_v2_block_manager --gpu-memory-utilization 0.8 --max-num-seqs 16 --enable-prefix-caching --enable-chunked-prefill >> /root/JqLogs/vllm.log 2>&1 &
tail -f /root/JqLogs/vllm.log

### Qwen2.5R1
workon vllm
CUDA_VISIBLE_DEVICES=2,3 nohup vllm serve /data/models/deepseek-r1-distill-qwen-32b-awq/ --tensor-parallel-size 2 --max-model-len 10000 --served-model-name DeepSeekR1 --enable-auto-tool-choice --tool-call-parser hermes --host 0.0.0.0 --port 8000 >> /root/JqLogs/vllm_r1.log 2>&1 &
tail -f /root/JqLogs/vllm_r1.log



需接着运行的下载任务

ollama run MFDoom/deepseek-v3-tool-calling --verbose
ollama run MHKetbi/qihoo360-TinyR1-32b-preview:q4_K_S

安装FlashInfer (AOT mode)【https://docs.flashinfer.ai/installation.html#install-from-source】
git clone https://github.com/flashinfer-ai/flashinfer.git --recursive
cd flashinfer
MAX_JOBS=8 TORCH_CUDA_ARCH_LIST="7.5 8.0 8.9 9.0 9.0a" FLASHINFER_ENABLE_AOT=1 pip install --no-build-isolation --verbose --editable .
workon py311
CUDA_VISIBLE_DEVICES=0 python -m olmocr.pipeline --model /data/models/allenai/olmOCR-7B-0225-preview ./localworkspace --pdfs /root/newgit/olmocr/*.pdf

CUDA_VISIBLE_DEVICES=0 vllm serve /data/models/deepseek-r1-distill-qwen-32b-awq/ --tensor-parallel-size 1 --max-model-len 10000 --enforce-eager

vllm serve /data/models/deepseek-r1-distill-qwen-32b-awq/ --tensor-parallel-size 4 --max-model-len 10000 --enforce-eager --served-model-name DeepSeekR1 --enable-auto-tool-choice --tool-call-parser hermes --host 0.0.0.0 --port 8000

workon vllm
CUDA_VISIBLE_DEVICES=2,3 vllm serve /data/models/deepseek-r1-distill-qwen-32b-awq/ --tensor-parallel-size 2 --max-model-len 10000 --served-model-name DeepSeekR1 --enable-auto-tool-choice --tool-call-parser hermes --host 0.0.0.0 --port 8000

## olmocr [https://github.com/allenai/olmocr/tree/main]
### python 3.11
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt-get update
sudo apt upgrade
sudo apt install python3.11 python3.12 python3.13 
sudo apt-get install python3.11-dev
<!-- apt --fix-broken install -->
mkvirtualenv --python=/usr/bin/python3.11 py311
<!-- pip install virtualenvwrapper -->
### olmOCR
sudo apt-get update
sudo apt upgrade
sudo apt-get install poppler-utils ttf-mscorefonts-installer msttcorefonts fonts-crosextra-caladea fonts-crosextra-carlito gsfonts lcdf-typetools


git clone https://github.com/allenai/olmocr.git
cd olmocr
pip install -e .

### Install sglang with flashinfer if you want to run inference on GPU.

pip install sgl-kernel --force-reinstall --no-deps
<!-- python -c "import torch; print(torch.__version__, torch.version.cuda)" 查看对应版本，替代下方版本号 -->
pip install "sglang[all]==0.4.3" --find-links https://flashinfer.ai/whl/cu124/torch2.5/flashinfer/


## Install flashinfer-python
#### JIT mode
<!-- python -c "import torch; print(torch.__version__, torch.version.cuda)" 查看对应版本，替代下方版本号 -->
pip install flashinfer-python -i https://flashinfer.ai/whl/cu124/torch2.5/

#### AOT mode
cd flashinfer
TORCH_CUDA_ARCH_LIST="7.5 8.0 8.9 9.0 9.0a" FLASHINFER_ENABLE_AOT=1 pip install --no-build-isolation --verbose --editable .


## 运行脚本
 enforce_eager=False, kv_cache_dtype=auto,  device_config=cuda, decoding_config=DecodingConfig(guided_decoding_backend='xgrammar'), observability_config=ObservabilityConfig(otlp_traces_endpoint=None, collect_model_forward_time=False, collect_model_execute_time=False), seed=0, served_model_name=qwenvl, num_scheduler_steps=1, multi_step_stream_outputs=True, enable_prefix_caching=False, chunked_prefill_enabled=False,
### 启动Qwen32 AWQ （on GPU 2,3）:
workon vllm
VLLM_ATTENTION_BACKEND=FLASH_ATTN_VLLM_V1 FLASH_ATTN_VLLM_V1=1 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True RAY_CGRAPH_get_timeout=60 TORCH_CUDA_ARCH_LIST="8.9+PTX" VLLM_USE_V1=1 VLLM_USE_MODELSCOPE=True CUDA_VISIBLE_DEVICES=2,3 VLLM_ALLOW_ENGINE_USE_RAY=1 nohup vllm serve /data/xinference/modelscope/hub/qwen/Qwen2.5-32B-Instruct-AWQ --served-model-name qwen25b70 --enable-auto-tool-choice --tool-call-parser hermes --host 0.0.0.0 --port 9997 --max-model-len 32000 --tensor-parallel-size 2 --distributed-executor-backend ray --use_v2_block_manager --gpu-memory-utilization 0.8 --max-num-seqs 16 --enable-prefix-caching --enable-chunked-prefill >> /root/JqLogs/vllm.log 2>&1 &
tail -f /root/JqLogs/vllm.log


workon vllm
TORCH_CUDA_ARCH_LIST="8.9+PTX" VLLM_USE_MODELSCOPE=True CUDA_VISIBLE_DEVICES=2,3 VLLM_ALLOW_ENGINE_USE_RAY=1 nohup vllm serve /data/xinference/modelscope/hub/qwen/Qwen2.5-32B-Instruct-AWQ --served-model-name qwen25b70 --enable-auto-tool-choice --tool-call-parser hermes --host 0.0.0.0 --port 9997 --max-model-len 32000 --tensor-parallel-size 2 --distributed-executor-backend ray --use_v2_block_manager --gpu-memory-utilization 0.8 --max-num-seqs 16 --enable-prefix-caching --enable-chunked-prefill >> /root/JqLogs/vllm.log 2>&1 &
tail -f /root/JqLogs/vllm.log

workon vllm
TORCH_CUDA_ARCH_LIST="8.9+PTX" VLLM_USE_MODELSCOPE=True VLLM_ALLOW_ENGINE_USE_RAY=1 nohup vllm serve /data/xinference/modelscope/hub/qwen/Qwen2.5-32B-Instruct-AWQ --served-model-name qwen25b70 --enable-auto-tool-choice --tool-call-parser hermes --host 0.0.0.0 --port 9997 --max-model-len 32000 --tensor-parallel-size 4 --distributed-executor-backend ray --use_v2_block_manager --gpu-memory-utilization 0.8 --max-num-seqs 16 --enable-prefix-caching --enable-chunked-prefill >> /root/JqLogs/vllm.log 2>&1 &
tail -f /root/JqLogs/vllm.log


FLASH_ATTN_VLLM_V1=1 TORCH_CUDA_ARCH_LIST="8.9+PTX" VLLM_USE_MODELSCOPE=True CUDA_VISIBLE_DEVICES=2,3 VLLM_ALLOW_ENGINE_USE_RAY=1 nohup vllm serve /data/xinference/modelscope/hub/qwen/Qwen2.5-32B-Instruct-AWQ --served-model-name qwen25b70 --enable-auto-tool-choice --tool-call-parser hermes --host 0.0.0.0 --port 9997 --max-model-len 32000 --tensor-parallel-size 2 --distributed-executor-backend ray --use_v2_block_manager --gpu-memory-utilization 0.8 --max-num-seqs 16 --enable-prefix-caching --enable-chunked-prefill >> /root/JqLogs/vllm.log 2>&1 &
tail -f /root/JqLogs/vllm.log

### 启动Qwen2.5-VL-7B-Instruct （on GPU 1）:
####  /data/models/Qwen/Qwen2___5-VL-7B-Instruct
workon vllm
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True RAY_CGRAPH_get_timeout=60 TORCH_CUDA_ARCH_LIST="8.9+PTX" VLLM_USE_V1=1 VLLM_USE_MODELSCOPE=True CUDA_VISIBLE_DEVICES=1 VLLM_ALLOW_ENGINE_USE_RAY=1 nohup vllm serve /data/models/Qwen/Qwen2___5-VL-7B-Instruct --served-model-name qwenvl --gpu-memory-utilization 0.90 --port 8000 --host 0.0.0.0 --limit-mm-per-prompt image=5,video=5 --max-model-len 8000 --distributed-executor-backend ray --use_v2_block_manager --max-num-seqs 16 --enable-prefix-caching --enable-chunked-prefill >> /root/JqLogs/vllmvl.log 2>&1 &
tail -f /root/JqLogs/vllmvl.log 

#### /data/models/allenai/olmOCR-7B-0225-preview
workon vllm
VLLM_ATTENTION_BACKEND=FLASH_ATTN_VLLM_V1 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True RAY_CGRAPH_get_timeout=60 TORCH_CUDA_ARCH_LIST="8.9+PTX" VLLM_USE_V1=1 VLLM_USE_MODELSCOPE=True CUDA_VISIBLE_DEVICES=1 VLLM_ALLOW_ENGINE_USE_RAY=1 nohup vllm serve /data/models/allenai/olmOCR-7B-0225-preview --served-model-name qwenvl --gpu-memory-utilization 0.90 --port 8000 --host 0.0.0.0 --limit-mm-per-prompt image=5,video=5 --max-model-len 8000 --distributed-executor-backend ray --use_v2_block_manager --max-num-seqs 16 --enable-prefix-caching --enable-chunked-prefill >> /root/JqLogs/vllmvl.log 2>&1 &
tail -f /root/JqLogs/vllmvl.log 





### 启动Ktransformers DeepSeek-R1-Q4_K_M （on GPU 0）:
#### 安装NUMA库
apt install libnuma-dev
#### 获取源代码
git clone https://github.com/kvcache-ai/ktransformers.git
cd ktransformers
git submodule init
git submodule update
#### 编译安装
make install_numa
(查看编译日志中是否存在NUMA support is enabled\n-- NUMA library found: /usr/lib/x86_64-linux-gnu/libnuma.so - enabling NUMA support\n)
#### 确认NUMA开启相关的命令 【摘自https://github.com/ggml-org/llama.cpp/discussions/12088】
numactl --hardware --cpu-compress
====Confirm Linux Kernel NUMA Balancing Enabled
cat /proc/sys/kernel/numa_balancing
1
==== 内存的实际分配
nvidia-smi 找到pid
watch -n1 numastat -p pid

Per-node process memory usage (in MBs) for PID 2402316 (ktransformers)
                           Node 0          Node 1           Total
                  --------------- --------------- ---------------
Huge                         0.00            0.00            0.00
Heap                      1120.50           22.47         1142.97
Stack                        0.14            0.00            0.14
Private                 471208.33       433322.20       904530.53
----------------  --------------- --------------- ---------------
Total                   472328.98       433344.67       905673.64


====生成速度 
生成速度由5.2tokens/s提升到7.4tokens/s


#### local chat mode
workon torch26cu126
TORCH_CUDA_ARCH_LIST="8.9+PTX" python -m ktransformers.local_chat --gguf_path /data/models/DeepSeek-R1-Q4_K_M_ollama_gguf/ --model_path deepseek-ai/DeepSeek-R1 --max_new_tokens 8192 --cache_lens 32768 --total_context 32768 --cache_q4 true --temperature 0.6 --top_p 0.95 --force_think --cpu_infer 49 --use_cuda_graph

#### server api mode [cpu_infer参数值25，还没记录。 设置为33时cpu负荷在80%上下，5+ tokens/s]
 workon torch26cu126
 USE_NUMA=1 TORCH_CUDA_ARCH_LIST="8.9+PTX" PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True nohup ktransformers --gguf_path /data/models/DeepSeek-R1-Q4_K_M_ollama_gguf/ --model_path deepseek-ai/DeepSeek-R1 --model_name DeepSeekR1 --cpu_infer 33 --max_new_tokens 8192 --cache_lens 32768 --total_context 32768 --cache_q4 true --temperature 0.6 --top_p 0.95 --force_think --host 0.0.0.0 --port 8080 --optimize_config_path /root/KT0.2.2rc2/ktransformers/ktransformers/optimize/optimize_rules/DeepSeek-V3-Chat.yaml >> //root/JqLogs/kt.log 2>&1 &
 tail -f /root/JqLogs/kt.log


#### FP8 Linear Kernel for DeepSeek-V3/R1
 python ktransformers/local_chat.py \
  --model_path deepseek-ai/DeepSeek-V3 \
  --gguf_path /data/models/DeepSeek-V3-q4km-fp8/ \
  --optimize_config_path /root/KT0.2.2rc2/ktransformers/ktransformers/optimize/optimize_rules/DeepSeek-V3-Chat-fp8-linear-ggml-experts.yaml \
  --cpu_infer 49

 ##### 改源代码打印InputMessages(/root/.virtualenvs/torch26cu126/lib/python3.10/site-packages/ktransformers/server/api/openai/endpoints/chat.py L25)
async def chat_completion(request:Request,create:ChatCompletionCreate):
    id = str(uuid4())

    interface: BackendInterfaceBase = get_interface()
    # input_ids = interface.format_and_tokenize_input_ids(id,messages=create.get_tokenizer_messages())
    print("===========Input Messages Begin(/root/.virtualenvs/torch26cu126/lib/python3.10/site-packages/ktransformers/server/api/openai/endpoints/chat.py L25)===========")
    i = 0
    for im in create.messages:
        i += 1
        c = im.content.replace('\n','  ')
        print(f"  --Input Message [{i}]=>【{im.role=} || im.content={c}】")
    print("===========Input Messages End===========") 
    input_message = [json.loads(m.model_dump_json()) for m in create.messages]

##### 改源代码打印输出效果如下：
===========Input Messages Begin(/root/.virtualenvs/torch26cu126/lib/python3.10/site-packages/ktransformers/server/api/openai/endpoints/chat.py L25)===========
  --Input Message [1]=>【im.role=<Role.system: 'system'> || im.content=  Current model: DeepSeekR1  Current date: 2025-02-27T05:45:24.861Z    You are a helpful assistant.】
  --Input Message [2]=>【im.role=<Role.user: 'user'> || im.content=python绘制sin(x)曲线的代码】
===========Input Messages End===========



#### NUMA内存查看和CPU负荷
nvidia-smi 查看ktransformers的pid
numastat -p 3424586(pid)
htop


### 启动JqChat应用程序:

```
workon test
cd /data/projects/JqChatV2/JqChat
nohup python startup.py >> /root/JqLogs/jqchat.log 2>&1 &
tail -f /root/JqLogs/jqchat.log
```
```
    sudo lsof -i :7861
    sudo lsof -i :8501
    sudo lsof -i :5011
```

## SGLang qwen2.5-32b-instruct-gptq-int4
```
workon sl
python -m sglang_router.launch_server --model-path tclf90/qwen2.5-32b-instruct-gptq-int4 --host 0.0.0.0 --port 9997 --tool-call-parser qwen25 --dp 2 --tp 2 --enable-p2p-check --log_level debug --enable_mixed_chunk --max_running_requests 32 --served_model_name qwen25b70
```
```
workon sl
python -m sglang_router.launch_server --model-path /data/xinference/modelscope/hub/qwen/Qwen2.5-32B-Instruct-AWQ --host 0.0.0.0 --port 9997 --tool-call-parser qwen25 --dp 2 --tp 2 --enable-p2p-check --log-level debug --enable-mixed-chunk --max-running-requests 32 --served-model-name qwen25b70
```

## docker代理配置
### 创建配置文件
```
sudo mkdir -p /etc/systemd/system/docker.service.d
sudo nano /etc/systemd/system/docker.service.d/http-proxy.conf
``` 

### 复制黏贴以下内容到配置文件中
```  
# http-proxy.conf 文件内容
[Service] 
Environment="HTTP_PROXY=http://10.1.42.212:4780/" 
Environment="HTTPS_PROXY=http://10.1.42.212:4780/" 
Environment="NO_PROXY=localhost,127.0.0.1"
```  
### 应用新的代理配置
```
systemctl daemon-reload
sudo service docker restart
```
### 查看验证新的代理配置
```
docker info
```


## Git同步
### 代理设置
```
git config --global http.https://github.com.proxy socks5h://10.1.42.212:4781
git config --global https.https://github.com.proxy socks5h://10.1.42.212:4781
```

### 查看git设置
```
git config -l
```

### 代理取消
```
git config --global --unset-all http.proxy
git config --global --unset-all https.proxy
```


### Windows下,pip install 出现错误Missing dependencies for SOCKS support.
手动下载 https://files.pythonhosted.org/packages/8d/59/b4572118e098ac8e46e399a1dd0f2d85403ce8bbaad9ec79373ed6badaf9/PySocks-1.7.1-py3-none-any.whl
手动安装 pip install -U D:\PySocks-1.7.1-py3-none-any.whl
pip install httpx[socks]


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
https://docs.vllm.ai/en/stable/serving/openai_compatible_server.html#extra-parameters-for-chat-api

### Context Length: Full 131,072 tokens and generation 8192 tokens
#### Qwen2.5-14B-Instruct-GPTQ-Int4
2gpu
```
workon vllm
VLLM_USE_MODELSCOPE=True CUDA_VISIBLE_DEVICES=2,3 VLLM_ALLOW_ENGINE_USE_RAY=1 nohup vllm serve /data/models/Qwen2.5-14B-Instruct-GPTQ-Int4 --served-model-name qwen25b14 --enable-auto-tool-choice --tool-call-parser hermes --host 0.0.0.0 --port 9999 --max-model-len 32000 --tensor-parallel-size 2 --distributed-executor-backend ray --use_v2_block_manager --gpu-memory-utilization 0.8 --max-num-seqs 32 --enable-prefix-caching --enable-chunked-prefill >> /data/xinference/vllm14.log 2>&1 &
tail -f /data/xinference/vllm14.log
```
```
nvidia-smi
ps -ef | grep 'vllm serve'
```

4gpu
```
workon vllm
VLLM_USE_MODELSCOPE=True CUDA_VISIBLE_DEVICES=0,1,2,3 VLLM_ALLOW_ENGINE_USE_RAY=1 nohup vllm serve /data/models/Qwen2.5-14B-Instruct-GPTQ-Int4 --served-model-name qwen25b14 --enable-auto-tool-choice --tool-call-parser hermes --host 0.0.0.0 --port 9999 --max-model-len 32000 --tensor-parallel-size 4 --distributed-executor-backend ray --use_v2_block_manager --gpu-memory-utilization 0.80 --max-num-seqs 32 --enable-prefix-caching --enable-chunked-prefill >> /data/xinference/vllm14.log 2>&1 &
tail -f /data/xinference/vllm14.log
```
```
nvidia-smi
ps -ef | grep 'vllm serve'
```
#### qwen2.5-32b-instruct-gptq-int4 (VLLM_USE_V1=1)
```
workon vllm
RAY_CGRAPH_get_timeout=60 TORCH_CUDA_ARCH_LIST="8.9+PTX" VLLM_USE_V1=1 VLLM_USE_MODELSCOPE=True CUDA_VISIBLE_DEVICES=0,1,2,3 VLLM_ALLOW_ENGINE_USE_RAY=1 nohup vllm serve /root/.cache/modelscope/hub/tclf90/qwen2.5-32b-instruct-gptq-int4 --served-model-name qwen25b70 --enable-auto-tool-choice --tool-call-parser hermes --host 0.0.0.0 --port 9997 --max-model-len 32000 --tensor-parallel-size 4 --distributed-executor-backend ray --use_v2_block_manager --gpu-memory-utilization 0.8 --max-num-seqs 32 --enable-prefix-caching --enable-chunked-prefill --disable-custom-all-reduce >> /data/xinference/vllm.log 2>&1 &
tail -f /data/xinference/vllm.log
```

#### Qwen2.5-32B-Instruct-AWQ 【Vllm已经优化了，比qptq要快了】

##### Pushing the Boundaries of Mixed-Precision LLM Inference With Marlin https://neuralmagic.com/blog/pushing-the-boundaries-of-mixed-precision-llm-inference-with-marlin/
2gpu
```
workon vllm
RAY_CGRAPH_get_timeout=60 TORCH_CUDA_ARCH_LIST="8.9+PTX" VLLM_USE_V1=1 VLLM_USE_MODELSCOPE=True CUDA_VISIBLE_DEVICES=2,3 VLLM_ALLOW_ENGINE_USE_RAY=1 nohup vllm serve /data/xinference/modelscope/hub/qwen/Qwen2.5-32B-Instruct-AWQ --served-model-name qwen25b70 --enable-auto-tool-choice --tool-call-parser hermes --host 0.0.0.0 --port 9997 --max-model-len 32000 --tensor-parallel-size 2 --distributed-executor-backend ray --use_v2_block_manager --gpu-memory-utilization 0.8 --max-num-seqs 16 --enable-prefix-caching --enable-chunked-prefill >> /data/xinference/vllm.log 2>&1 &
tail -f /data/xinference/vllm.log
```
4gpu
```
workon vllm
RAY_CGRAPH_get_timeout=60 TORCH_CUDA_ARCH_LIST="8.9+PTX" VLLM_USE_V1=1 VLLM_USE_MODELSCOPE=True CUDA_VISIBLE_DEVICES=0,1,2,3 VLLM_ALLOW_ENGINE_USE_RAY=1 nohup vllm serve /data/xinference/modelscope/hub/qwen/Qwen2.5-32B-Instruct-AWQ --served-model-name qwen25b70 --enable-auto-tool-choice --tool-call-parser hermes --host 0.0.0.0 --port 9997 --max-model-len 32000 --tensor-parallel-size 4 --distributed-executor-backend ray --use_v2_block_manager --gpu-memory-utilization 0.8 --max-num-seqs 32 --enable-prefix-caching --enable-chunked-prefill >> /data/xinference/vllm.log 2>&1 &
tail -f /data/xinference/vllm.log
```
2*2gpu
```
workon vllm
RAY_CGRAPH_get_timeout=60 TORCH_CUDA_ARCH_LIST="8.9+PTX" VLLM_USE_V1=1 VLLM_USE_MODELSCOPE=True CUDA_VISIBLE_DEVICES=0,1,2,3 VLLM_ALLOW_ENGINE_USE_RAY=1 nohup vllm serve /data/xinference/modelscope/hub/qwen/Qwen2.5-32B-Instruct-AWQ --served-model-name qwen25b70 --enable-auto-tool-choice --tool-call-parser hermes --host 0.0.0.0 --port 9997 --max-model-len 32000 --tensor-parallel-size 2 --pipeline-parallel-size 2 --distributed-executor-backend ray --use_v2_block_manager --gpu-memory-utilization 0.8 --max-num-seqs 32 --enable-prefix-caching --enable-chunked-prefill >> /data/xinference/vllm.log 2>&1 &
tail -f /data/xinference/vllm.log
```


```
nvidia-smi
ps -ef | grep 'vllm serve'
```

#### Qwen2.5-Coder-32B-Instruct-AWQ
2gpu
```
workon vllm
VLLM_USE_MODELSCOPE=True CUDA_VISIBLE_DEVICES=0,1 VLLM_ALLOW_ENGINE_USE_RAY=1 nohup vllm serve /data/xinference/modelscope/hub/qwen/Qwen2.5-Coder-32B-Instruct-AWQ --served-model-name qwen25b70 --enable-auto-tool-choice --tool-call-parser hermes --host 0.0.0.0 --port 9997 --max-model-len 32000 --tensor-parallel-size 2 --distributed-executor-backend ray --use_v2_block_manager --gpu-memory-utilization 0.8  --max-num-seqs 16 --enable-prefix-caching --enable-chunked-prefill >> /data/xinference/vllm.log 2>&1 &
tail -f /data/xinference/vllm.log
```
4gpu
```
workon vllm
VLLM_USE_MODELSCOPE=True CUDA_VISIBLE_DEVICES=0,1,2,3 VLLM_ALLOW_ENGINE_USE_RAY=1 nohup vllm serve /data/xinference/modelscope/hub/qwen/Qwen2.5-Coder-32B-Instruct-AWQ --served-model-name qwen25b70 --enable-auto-tool-choice --tool-call-parser hermes --host 0.0.0.0 --port 9997 --max-model-len 32000 --tensor-parallel-size 4 --distributed-executor-backend ray --use_v2_block_manager --gpu-memory-utilization 0.8 --max-num-seqs 32 --enable-prefix-caching --enable-chunked-prefill >> /data/xinference/vllm.log 2>&1 &
tail -f /data/xinference/vllm.log
```



#### Qwen2.5-72B-Instruct-AWQ
```
workon vllm
VLLM_USE_MODELSCOPE=True CUDA_VISIBLE_DEVICES=0,1,2,3 VLLM_ALLOW_ENGINE_USE_RAY=1 nohup vllm serve /data/xinference/modelscope/hub/qwen/Qwen2.5-72B-Instruct-AWQ --served-model-name qwen25b70 --enable-auto-tool-choice --tool-call-parser hermes --host 0.0.0.0 --port 9997 --max-model-len 32000 --tensor-parallel-size 4 --distributed-executor-backend ray --use_v2_block_manager --gpu-memory-utilization 0.85 --max-num-seqs 16 --enable-prefix-caching --enable-chunked-prefill >> /data/xinference/vllm.log 2>&1 &
tail -f /data/xinference/vllm.log

```
#### Meta-Llama-3.3-70B-Instruct-AWQ-INT4
```
workon vllm
VLLM_USE_MODELSCOPE=True CUDA_VISIBLE_DEVICES=0,1,2,3 VLLM_ALLOW_ENGINE_USE_RAY=1 nohup vllm serve /data/models/Meta-Llama-3.3-70B-Instruct-AWQ-INT4 --served-model-name qwen25b70 --enable-auto-tool-choice --tool-call-parser llama3_json --chat-template /data/models/Meta-Llama-3.3-70B-Instruct-AWQ-INT4/tool_chat_template_llama3.2_json.jinja --host 0.0.0.0 --port 9997 --max-model-len 12000 --tensor-parallel-size 4 --distributed-executor-backend ray --use_v2_block_manager --gpu-memory-utilization 0.85 --max-num-seqs 4 --enable-prefix-caching --enable-chunked-prefill --disable-frontend-multiprocessing --enforce-eager >> /data/xinference/vllm.log 2>&1 &
tail -f /data/xinference/vllm.log
```

Known Issues:  
https://github.com/QwenLM/Qwen2.5/blob/c7871179500a0ea688c97b0f6656dd6e8a28b555/docs/source/quantization/gptq.md#qwen25-72b-instruct-gptq-int4-cannot-stop-generation-properly 

模型有更新，需重新下载
  https://www.modelscope.cn/models/tclf90/qwen2.5-72b-instruct-gptq-int4
```
workon vllm 
VLLM_ALLOW_ENGINE_USE_RAY=1 vllm serve  /data/models/Qwen2.5-14B-Instruct-GPTQ-Int4/ --served-model-name qwen25b70 --enable-auto-tool-choice --tool-call-parser hermes --host 0.0.0.0 --port 9997 --max-model-len 32000 --tensor-parallel-size 1 --distributed-executor-backend ray --use_v2_block_manager --gpu-memory-utilization 0.95 --quantization gptq_marlin
```

```
workon vllm
VLLM_USE_MODELSCOPE=True CUDA_VISIBLE_DEVICES=0,1,2,3 VLLM_ALLOW_ENGINE_USE_RAY=1 nohup vllm serve /data/models/Qwen2.5-72B-Instruct-GPTQ-Int4/ --served-model-name qwen25b70 --enable-auto-tool-choice --tool-call-parser hermes --host 0.0.0.0 --port 9997 --max-model-len 32000 --tensor-parallel-size 4 --distributed-executor-backend ray --use_v2_block_manager --gpu-memory-utilization 0.90 --quantization gptq_marlin >> /data/xinference/vllm.log 2>&1 &
tail -f /data/xinference/vllm.log
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
workon vllm
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
docker pull docker.elastic.co/elasticsearch/elasticsearch:8.16.1
【将/data/elasticsearch/data的权限设为777 chmod -R 777 /data/elasticsearch/data】
docker run --name es816 --net elastic -p 9200:9200 -it -v /data/elasticsearch/data:/usr/share/elasticsearch/data -m 5120M --memory-swap 5120M docker.elastic.co/elasticsearch/elasticsearch:8.16.1

设置docker es816环境变量：
export ES_HEAP_SIZE=6g
或是：
docker cp /data/projects/JqChatV2/JqChat/jqcode/jq_docstores/backend_docstore_utils/jvm.options es816:/usr/share/elasticsearch/config/jvm.options.d/jvm.options

```
"""
  "上传的文件太大，请参照下面修改\usr\share\elasticsearch\config\elasticsearch.yml，但最大不能超过2G！"
  http.max_content_length: 2147483647b
  indices.breaker.total.use_real_memory: True
  indices.breaker.fielddata.limit: 80%                
"""
docker es816输出的结果
━
✅ Elasticsearch security features have been automatically configured!
✅ Authentication is enabled and cluster connections are encrypted.

ℹ️  Password for the elastic user (reset with `bin/elasticsearch-reset-password -u elastic`):
  B9oa7HEgqzuC2e8bfiN_

ℹ️  HTTP CA certificate SHA-256 fingerprint:
  44939ff54db780054733cfc07f1bb1d38b19ff24a390acbe87607f8d5ce6ba7e

ℹ️  Configure Kibana to use this cluster:
• Run Kibana and click the configuration link in the terminal when Kibana starts.
• Copy the following enrollment token and paste it into Kibana in your browser (valid for the next 30 minutes):
eyJ2ZXIiOiI4LjE0LjAiLCJhZHIiOlsiMTcyLjE4LjAuMjo5MjAwIl0sImZnciI6IjQ0OTM5ZmY1NGRiNzgwMDU0NzMzY2ZjMDdmMWJiMWQzOGIxOWZmMjRhMzkwYWNiZTg3NjA3ZjhkNWNlNmJhN2UiLCJrZXkiOiJ2MmpraEpNQlZKRHdaZmxHMzBrMTpRcnRsQkpfNVRYQzNTWXNlWFM2bU13In0=

ℹ️ Configure other nodes to join this cluster:
• Copy the following enrollment token and start new Elasticsearch nodes with `bin/elasticsearch --enrollment-token <token>` (valid for the next 30 minutes):
  eyJ2ZXIiOiI4LjE0LjAiLCJhZHIiOlsiMTcyLjE4LjAuMjo5MjAwIl0sImZnciI6IjQ0OTM5ZmY1NGRiNzgwMDU0NzMzY2ZjMDdmMWJiMWQzOGIxOWZmMjRhMzkwYWNiZTg3NjA3ZjhkNWNlNmJhN2UiLCJrZXkiOiJ3V2praEpNQlZKRHdaZmxHMzBsRjozUW4zYjg3U1NBV0Zobk1fQ2ZWZ3d3In0=

  If you're running in Docker, copy the enrollment token and run:
  `docker run -e "ENROLLMENT_TOKEN=<token>" docker.elastic.co/elasticsearch/elasticsearch:8.16.1`



### 复制elastic user password and an enrollment token for Kibana.


#### elastic user
elastic
#### elastic user password ：
B9oa7HEgqzuC2e8bfiN_
#### enrollment token for Kibana：
eyJ2ZXIiOiI4LjE0LjAiLCJhZHIiOlsiMTcyLjE4LjAuMjo5MjAwIl0sImZnciI6IjQ0OTM5ZmY1NGRiNzgwMDU0NzMzY2ZjMDdmMWJiMWQzOGIxOWZmMjRhMzkwYWNiZTg3NjA3ZjhkNWNlNmJhN2UiLCJrZXkiOiJ2MmpraEpNQlZKRHdaZmxHMzBrMTpRcnRsQkpfNVRYQzNTWXNlWFM2bU13In0=
#### HTTP CA certificate SHA-256 fingerprint:
44939ff54db780054733cfc07f1bb1d38b19ff24a390acbe87607f8d5ce6ba7e

cd ~
docker cp es816:/usr/share/elasticsearch/config/certs/http_ca.crt .

export ELASTIC_PASSWORD="B9oa7HEgqzuC2e8bfiN_"

docker run -e "ENROLLMENT_TOKEN=<token>" docker.elastic.co/elasticsearch/elasticsearch:8.14.0

重新生成elastic user password and an enrollment token for Kibana.
```
docker exec -it es105 /usr/share/elasticsearch/bin/elasticsearch-reset-password -u elastic
docker exec -it es105 /usr/share/elasticsearch/bin/elasticsearch-create-enrollment-token -s kibana
```
## Kibana https://www.elastic.co/guide/en/kibana/current/docker.html
docker pull docker.elastic.co/kibana/kibana:8.16.1
docker run --name kib816 --net elastic -p 5601:5601 docker.elastic.co/kibana/kibana:8.16.1


### 中文分词（以新的8.16.1作为例子）


#### 安装插件
进入运行的8.16.1 docker中
1、查看已安装的插件
```
bin/elasticsearch-plugin list
```
2、安装
2.1 安装smartcn 【for Chinese or mixed Chinese-English text https://www.elastic.co/guide/en/elasticsearch/plugins/current/analysis-smartcn.html 】  
bin/elasticsearch-plugin install analysis-smartcn 
bin/elasticsearch-plugin install https://get.infini.cloud/elasticsearch/analysis-ik/8.16.1

2.2 restart Elasticsearch to activate any plugins installed
如果直接restart不行，可以先stop再start

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
## LightRAG
修改：
/data/projects/LightRAG/lightrag/prompt.py： PROMPTS["DEFAULT_LANGUAGE"] = "Simplified Chinese"
/data/projects/LightRAG/lightrag/operate.py L997增加一行: all_text_units = [unit for unit in all_text_units if isinstance(unit.get('data',None),dict)]
/data/projects/LightRAG/lightrag/utils.py L19-20:
    from transformers import AutoTokenizer
    ENCODER = AutoTokenizer.from_pretrained("/data/models/bce-embedding-base_v1")
/data/projects/LightRAG/lightrag/utils.py L139:
      tokens = ENCODER.encode(content,max_length=2**32,truncation="do_not_truncate")

## Apache Cassandra: CassandraGraphVectorStore
https://python.langchain.com/api_reference/community/graph_vectorstores.html#create-the-graph-vector-store-and-add-documents

https://cassandra.apache.org/doc/latest/cassandra/getting-started/cassandra-quickstart.html

https://github.com/langchain-ai/langchain/blob/ca054ed1b1b76ded6a91aeb47da1c6ee6a703fce/docs/docs/how_to/hybrid.ipynb#L71

docker pull cassandra:latest
docker network create cassandra

docker run --rm -d --name cassandra --hostname cassandra --network cassandra cassandra -p 9042:9042 -e CASSANDRA_PASSWORD_SEEDER=yes -e CASSANDRA_USERNAME=cassandra -e CASSANDRA_PASSWORD=password123

docker run --rm -d --name cassandra --hostname cassandra --network cassandra cassandra -p 9042:9042 -e ASSANDRA_USERNAME=cassandra -e CASSANDRA_PASSWORD=password123



## PolarDB for PostgreSQL
https://github.com/ApsaraDB/PolarDB-for-PostgreSQL
https://developer.aliyun.com/article/1611770 GraphRAG：基于PolarDB+通义千问+LangChain的知识图谱+大模型最佳实践

```
docker pull polardb/polardb_pg_local_instance:15
docker run -it --cap-add=SYS_PTRACE --privileged=true --rm polardb/polardb_pg_local_instance:15 psql
```
### postgresql配置文件位置
/var/polardb/primary_datadir/postgresql.conf

### 初始化数据库
docker run -it --rm \
    --cap-add=SYS_PTRACE --privileged=true \
    --env POLARDB_PORT=5432 \
    --env POLARDB_USER=langchain \
    --env POLARDB_PASSWORD=langchain \
    --env POLARDB_DB=postgres \
    -p 6024:5432 \
    polardb/polardb_pg_local_instance:15 \
    echo 'done'
### 启动数据库服务
docker run -d \
    --cap-add=SYS_PTRACE --privileged=true \
    --env POLARDB_PORT=5432 \
    --env POLARDB_USER=langchain \
    --env POLARDB_PASSWORD=langchain \
    --env POLARDB_DB=postgres \
    -p 6024:5432 \
    polardb/polardb_pg_local_instance:15 \

### 安装插件
进入容器
#### age （注意git PG15版本的代码）
```bash
    git clone -b release/PG15/1.5.0 https://github.com/apache/age.git
    cd age
    make install
```

### Zhparser
#### 1.安装SCWS
```
cd ~
wget -q -O - http://www.xunsearch.com/scws/down/scws-1.2.3.tar.bz2 | tar xjf -
cd scws-1.2.3 ; ./configure ; sudo make install
```

#### 2.安装Zhparser
```
cd ~
git clone https://github.com/amutu/zhparser.git
cd zhparser
make && make install
```

```psql
    psql
    CREATE EXTENSION age;
    CREATE EXTENSION vector;
    CREATE EXTENSION pg_jieba;
    CREATE EXTENSION zhparser;
    CREATE TEXT SEARCH CONFIGURATION zhparsercfg (PARSER = zhparser);
    ALTER TEXT SEARCH CONFIGURATION zhparsercfg ADD MAPPING FOR n,v,a,i,e,l WITH simple;
    CREATE TEXT SEARCH CONFIGURATION zhparser (PARSER = zhparser);
    ALTER TEXT SEARCH CONFIGURATION zhparser ADD MAPPING FOR n,v,a,i,e,l WITH simple;
```

### 修改配置文件\var\polardb\primary_datadir\postgresql.conf
default_text_search_config='zhparsercfg' 
shared_preload_libraries = 'zhparser.so'
shared_preload_libraries ='zhparser.so,\$libdir/polar_vfs,\$libdir/polar_io_stat,\$libdir/polar_monitor_preload,\$libdir/polar_worker'


### 测试
```psql
show default_text_search_config;
show shared_preload_libraries;
SELECT * FROM ts_parse('zhparser', 'hello world! 2010年保障房建设在全国范围内获全面启动，从中央到地方纷纷加大 了保障房的建设和投入力度 。2011年，保障房进入了更大规模的建设阶段。住房城乡建设部党组书记、部长姜伟新去年底在全国住房城乡建设工作会议上表示，要继续推进保障性安居工程建设。');

SELECT to_tsvector('zhparsercfg','“今年保障房新开工数量虽然有所下调，但实际的年度在建规模以及竣工规模会超以往年份，相对应的对资金的需求也会创历>史纪录。”陈国强说。在他看来，与2011年相比，2012年的保障房建设在资金配套上的压力将更为严峻。');
SELECT to_tsvector('zhparser','“今年保障房新开工数量虽然有所下调，但实际的年度在建规模以及竣工规模会超以往年份，相对应的对资金的需求也会创历>史纪录。”陈国强说。在他看来，与2011年相比，2012年的保障房建设在资金配套上的压力将更为严峻。');
SELECT to_tsquery('zhparsercfg', '保障房资金压力');
SELECT to_tsquery('保障房资金压力');
SELECT to_tsvector('“今年保障房新开工数量虽然有所下调，但实际的年度在建规模以及竣工规模会超以往年份，相对应的对资金的需求也会创历>史纪录。”陈国强说。在他看来，与2011年相比，2012年的保障房建设在资金配套上的压力将更为严峻。');

SELECT to_tsquery('zhparsercfg', 'CREATE EXTENSION vector'); #会报错
SELECT plainto_tsquery('zhparsercfg', 'CREATE EXTENSION vector');
SELECT plainto_tsquery('CREATE EXTENSION vector');
SELECT plainto_tsquery('english', 'The Fat Rats');
SELECT plainto_tsquery('The Fat Rats');
```

### 保存修改后的容器
docker ps
docker commit c0970e749db9 polardb15_vector_age_zh:v1.0
docker commit 7da980b5741c polardb15_vector_age_zh:v1.1


### 运行修改后的容器
docker run -d \
    --cap-add=SYS_PTRACE --privileged=true \
    --env POLARDB_PORT=5432 \
    --env POLARDB_USER=langchain \
    --env POLARDB_PASSWORD=langchain \
    --env POLARDB_DB=postgres \
    -p 6022:5432 \
    polardb15_vector_age_zh:v1.1

## postgres: pg_vector_age_graph

#### docker file: 
/data/projects/JqChatV2/JqChat/pg_dockerfile

/data/projects/JqChatV2/JqChat/pg_vector_age_zh_dockerfile (中文分词插件)

#### docker build: 
VS Code中，在上面的文件上右击，选择build image, 然后在最上方的输入框中按提示输入"pg_vector_age_zh"作为image的标签(tag)

#### docker run: 
docker run --name pg_vector_age_zh -e POSTGRES_USER=langchain -e POSTGRES_PASSWORD=langchain -e POSTGRES_DB=langchain -p 6024:5432 -d docker.io/library/pg16_vector_age_zh

#### 错误解决
/lib/x86_64-linux-gnu/libc.so.6: version `GLIBC_2.33' not found
docker exec -it --user root pg_vector_age_zh_16 bash
apt update
apt install libc6


#### test code: 
/data/projects/JqChatV2/JqChat/pg_vector_age_graph.py

#### PostgreSQL 的全文检索系统之中文支持 (三)

https://www.qiuzhi99.com/articles/postgresql/17.html  zhparser中文分词的PostgreSQL插件。

CREATE EXTENSION zhparser;
CREATE TEXT SEARCH CONFIGURATION testzhcfg (PARSER = zhparser);
ALTER TEXT SEARCH CONFIGURATION testzhcfg ADD MAPPING FOR n,v,a,i,e,l WITH simple;


## Neo4j

### 删除全部数据
```
MATCH (n) DETACH DELETE n
```
### Neo4j安装运行

```
docker run \
    --name neo4j_rag \
    --restart always \
    -p 7474:7474 -p 7687:7687 \
    -v "/data/neo4j/data/":/data -v "/data/neo4j/plugins/":/plugins \
    -e NEO4J_apoc_export_file_enabled=true \
    -e NEO4J_apoc_import_file_enabled=true \
    -e NEO4J_apoc_import_file_use__neo4j__config=true \
    -e NEO4J_PLUGINS='["apoc", "graph-data-science"]' \
    neo4j:latest
```

### Neo4j创建全文检索之中文分词器
```
CREATE FULLTEXT INDEX FTS_Person_Company_fullName 
FOR (n:Person|Company)
ON EACH [n.fullName]
OPTIONS {
  indexConfig: {
    `fulltext.analyzer`: "cjk",
    `fulltext.eventually_consistent`: true
  }
}
```


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


在MSI笔记本电脑上Windows环境下安装的
### 测试新的模型
#### UI：open-webui 
```
pip install open-webui
open-webui serve
```
This will start the Open WebUI server, which you can access at http://localhost:8080

### 免费的Openai兼容的LLM模型api： https://glhf.chat/
如："hf:meta-llama/Llama-3.3-70B-Instruct"



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


workon vllm
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

### build-lightweight-graphrag-with-sqlite https://medium.com/thedeephub/how-to-build-lightweight-graphrag-with-sqlite-1b387e056cbf
### https://medium.com/thedeephub/how-to-scale-graphrag-with-neo4j-for-efficient-document-querying-f8be1ae4feb3



