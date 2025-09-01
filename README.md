**du -h --max-depth=1 / | sort -rh**
## maxkb v1
docker run --name=maxkbv1 --restart=always -p 9090:8080 -v ~/.maxkbv1:/opt/maxkbv1 1panel/maxkb:v1.10.9-lts

## 安装驱动和Cuda
 Runfile Installer 12.8.1
https://docs.nvidia.com/cuda/cuda-quick-start-guide/index.html#linux


Ubuntu安装驱动：
1、先运行
apt install linux-headers-$(uname -r)
apt-get install alsa-utils

2、下载驱动：【https://www.nvidia.com/en-us/drivers/details/247720/】.run文件
      运行下载的文件 sh NVIDIA-Linux-x86_64-570.169.run
     检查：nvidia-smi
****************************
2、列出可选驱动【https://documentation.ubuntu.com/server/how-to/graphics/install-nvidia-drivers/】
【desktop】 sudo ubuntu-drivers list
            sudo ubuntu-drivers install 【自动选择安装】
【servers】sudo ubuntu-drivers list --gpgpu
           sudo ubuntu-drivers install --gpgpu  【自动选择安装】 
------list的结果

nvidia-driver-535
nvidia-driver-550-open
nvidia-driver-570-server-open
nvidia-driver-570
nvidia-driver-570-server
nvidia-driver-535-open
nvidia-driver-545-open
nvidia-driver-535-server
nvidia-driver-545
nvidia-driver-550
nvidia-driver-570-open
nvidia-driver-535-server-open
---------
****************************

3、选择一个合适的安装 【如nvidia-driver-570-server】

sudo ubuntu-drivers install nvidia-driver-570-server

apt search nvidia-cuda-toolkit
Ubuntu安装CUDA：
sudo apt update
sudo apt upgrade
【apt search nvidia-cuda-toolkit】
【sudo apt install nvidia-cuda-toolkit-12-8】可附加nvidia-cuda-dev

如果没有目标版本，就下载手动安装
1、下载 cuda .run文件 wget https://developer.download.nvidia.com/compute/cuda/12.8.1/local_installers/cuda_12.8.1_570.124.06_linux.run
2、运行 sudo sh cuda_12.8.1_570.124.06_linux.run 
3、环境变量
export PATH=/usr/local/cuda-12.8/bin${PATH:+:${PATH}}
export LD_LIBRARY_PATH=/usr/local/cuda-12.8/lib64:${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}

4、检查 nvcc --version

sudo apt-mark hold nvidia-driver-570  # 固定当前驱动版本
sudo dpkg-reconfigure unattended-upgrades  # 禁用自动更新

## 运行Hunyuan
docker pull hunyuaninfer/hunyuan-a13b:hunyuan-moe-A13B-vllm
docker run  --privileged --user root  --net=host --ipc=host --name hy --rm \
        -v /data/models/:/data/models/ \
        -e VLLM_ATTENTION_BACKEND="FLASH_ATTN" -e VLLM_USE_V1=0 \
        --runtime=nvidia \
        --gpus=all -it --entrypoint python hunyuaninfer/hunyuan-a13b:hunyuan-moe-A13B-vllm \
         -m vllm.entrypoints.openai.api_server --host 0.0.0.0 --tensor-parallel-size 4 \
         --port 9998 --model /data/models/Tencent-Hunyuan/Hunyuan-A13B-Instruct-GPTQ-Int4/ --trust_remote_code --served-model-name qwen3 \
         --dtype bfloat16 --disable-log-stats --quantization gptq_marlin \
         --max-model-len 32000 \
         --reasoning-parser deepseek_r1 \
         --enable-auto-tool-choice \
         --tool-parser-plugin /data/models/Tencent-Hunyuan/Hunyuan-A13B-Instruct-GPTQ-Int4/hunyuan_tool_parser.py \
         --tool-call-parser hunyuan \
         2>&1 | tee log_server.txt


docker run  --privileged --user root  --net=host --ipc=host         -v ~/.cache:/root/.cache/ -e VLLM_ATTENTION_BACKEND="FLASH_ATTN" -e VLLM_USE_V1=0  --runtime=nvidia -it --entrypoint python  hunyuaninfer/hunyuan-a13b:hunyuan-moe-A13B-vllm -m vllm.entrypoints.openai.api_server --host 0.0.0.0 --port 1337          --tensor-parallel-size 4 --quantization gptq_marlin --model tencent/Hunyuan-A13B-Instruct-GPTQ-Int4 --trust-remote-code --max-model-len 16K  --gpu-memory-utilization 0.95 --reasoning-parser deepseek_r1

pip install torch==2.7.0 torchvision torchaudio vllm==0.9.1

[py3.10]pip install /root/flash_attn-2.8.0.post2+cu12torch2.7cxx11abiFALSE-cp310-cp310-linux_x86_64.whl
[py3.11]pip install /root/flash_attn-2.8.0.post2+cu12torch2.7cxx11abiTRUE-cp311-cp311-linux_x86_64.whl

[FLASHINFER in vllmb ]
export TORCH_CUDA_ARCH_LIST='7.5 8.0 8.9 9.0 10.0+PTX'
export FLASHINFER_ENABLE_SM90=1
pip install build
pip install -U setuptools
python -m flashinfer.aot
python -m build --no-isolation --wheel
ls -la dist/
cd dist
pip install pip install flashinfer_python-0.2.6.post1-cp39-abi3-linux_x86_64.whl
[当前0.9.1有问题 Failed to check the "should dump" flag on TCPStore]
pip install -U vllm --pre --extra-index-url https://wheels.vllm.ai/nightly

## Reranker 8081
workon vllm
CUDA_VISIBLE_DEVICES=0 nohup vllm serve /data/models/Qwen3-Reranker-0.6B-seq-cls --served-model-name Qwen/Qwen3-Reranker-0.6B --port 8081 >> /root/JqLogs/rerank.log 2>&1 &
tail -f /root/JqLogs/rerank.log

## Embedding 8082
workon vllm
CUDA_VISIBLE_DEVICES=0 nohup vllm serve /data/models/Qwen/Qwen3-Embedding-0___6B --served-model-name Qwen/Qwen3-Embedding-0.6B --port 8082 >> /root/JqLogs/embedding.log 2>&1 &
tail -f /root/JqLogs/embedding.log


## Reranker 备用 
workon vllm
CUDA_VISIBLE_DEVICES=0 vllm serve /data/models/Qwen/Qwen3-Reranker-0___6B --served-model-name Qwen/Qwen3-Reranker-0.6B  max_num_seqs=8 gpu_memory_utilization=0.5 --hf_overrides '{"architectures": ["Qwen3ForSequenceClassification"],"classifier_from_token": ["no", "yes"],"is_original_qwen3_reranker": true}' --task score


vllm serve /data/models/Qwen3-Reranker-0___6B/ --served-model-name qwen3reranker --task score
curl http://10.1.150.106:9998/v1/rerank \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer abc123' \
  -d '{
      "query": "A man is eating pasta.",
      "documents": ["A man is eating food.","A woman is playing violin.","一个人在踢球","一个人在吃饭"],
    "model": "Qwen3-Reranker-0.6B"
  }'

```
curl -X 'GET' \
  'http://10.1.150.106:8082/v1/models' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer abc123'
```
## Embedding测试
curl http://10.1.150.106:9998/v1/embeddings   -H 'accept: application/json'   -H 'Content-Type: application/json' -H 'Authorization: Bearer abc123'  -d '{
    "input": "Follow the white rabbit.",
    "model": "Qwen3-Embedding-0.6B",
    "encoding_format": "float"
  }'
### ollama
curl http://localhost:11434/api/embed -d '{
  "model": "dengcao/Qwen3-Reranker-0.6B:F16",
  "input":"hello"
}'

## Reranker测试
curl http://10.1.150.105:8081/v1/rerank \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer abc123' \
  -d '{
      "query": "ping",
      "documents": ["pong"],
    "model": "Qwen/Qwen3-Reranker-0.6B"
  }'

  curl http://10.1.150.106:8082/v1/score \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer abc123' \
  -d '{
    "text_1": "ping",
    "text_2": "pong",
    "model": "Qwen/Qwen3-Reranker-0.6B"
  }'

## 106 Embedding&tokenizer bce-embedding-base_v1 
vllm v0.85

source ~/.bashrc
workon xinfer 
nohup vllm serve "/data/models/bce-embedding-base_v1" \
    --served-model-name "bce-embedding-base_v1" \
    --task "embedding" \
    --trust-remote-code \
    --host "0.0.0.0" \
    --port 9998 \
    --dtype auto \
    --gpu-memory-utilization 0.4 \
    --kv-cache-dtype auto \
    --enable-prefix-caching \
    --tensor-parallel-size 1 \
    --max-num-seqs 256 >> /root/JqLogs/embedding.log 2>&1 &
tail -f /root/JqLogs/embedding.log

curl http://10.1.150.106:9998/v1/embeddings   -H 'accept: application/json'   -H 'Content-Type: application/json' -H 'Authorization: Bearer abc123'  -d '{
    "input": "Follow the white rabbit.",
    "model": "bce-embedding-base_v1",
    "encoding_format": "float"
  }'

  curl http://10.1.150.106:9998/v1/embeddings   -H 'accept: application/json'   -H 'Content-Type: application/json' -H 'Authorization: Bearer abc123'  -d '{
    "input": "Follow the white rabbit.",
    "model": "bce-embedding-base_v1"
  }'




curl http://10.1.150.106:9998/tokenize   -H 'accept: application/json'   -H 'Content-Type: application/json' -H 'Authorization: Bearer abc123'  -d '{  
"model": "bce-embedding-base_v1",
"prompt": "区块链功能实现层实现了区块链网络中各种具体的区块链功能逻辑。平台采用实体挂载组件的方式。一个节点可以装配若干功能组件实现节点的实际功能。账本组件负责记录发生在网络中的交易信息，包括状态数据库、历史数据库和索引数据库等信息。区块组件将排序后的交易填充为区块。节点支持客户端对指定事件进行监听，并由监听者对事件进行处理。共识组件主要提供对交易的全局排序。交易指的是通过调用链码实现对账本状态的一次改变。客户端可以通过发送交易请求来让分布式账本记录信息。背书组件对收到的来自客户端的请求（交易提案）按照自身的逻辑进行检查，以决策是否予以支持。验证组件对排序后的一批交易进行提交到账本之前最终的检查。PKI组件主要负责对数字证书进行管理，包括生成、撤销等。智能合约组件提供对智能合约的功能支撑，由合约框架、应用合约和系统合约组成。智能合约是作为交易的一部分保存在总账上的应用级的代码。合约框架提供支持特定编程语言（JAVA、GO）的智能合约运行环境。应用合约支持提供编写用户智能合约的支持接口。系统合约负责节点自身的处理逻辑，包括系统配置、背书、检验等系统级智能合约。",
"add_special_tokens": true,
"additionalProp1": {}
}'

结果列表1：
"我是中国人"
[0,6,28309,75224,2]
28309=》"我是"
curl http://10.1.150.106:9998/detokenize   -H 'accept: application/json'   -H 'Content-Type: application/json' -H 'Authorization: Bearer abc123'  -d '{
  "model": "bce-embedding-base_v1",
  "tokens":[28309],
  "additionalProp1": {}
}' 

75224=》"中国人"
curl http://10.1.150.106:9998/detokenize   -H 'accept: application/json'   -H 'Content-Type: application/json' -H 'Authorization: Bearer abc123'  -d '{
  "model": "bce-embedding-base_v1",
  "tokens":[75224],
  "additionalProp1": {}
}'


结果列表2：
"区块链功能实现层实现了区块链网络中各种具体的区块链功能逻辑。平台采用实体挂载组件的方式。一个节点可以装配若干功能组件实现节点的实际功能。账本组件负责记录发生在网络中的交易信息，包括状态数据库、历史数据库和索引数据库等信息。区块组件将排序后的交易填充为区块。节点支持客户端对指定事件进行监听，并由监听者对事件进行处理。共识组件主要提供对交易的全局排序。交易指的是通过调用链码实现对账本状态的一次改变。客户端可以通过发送交易请求来让分布式账本记录信息。背书组件对收到的来自客户端的请求（交易提案）按照自身的逻辑进行检查，以决策是否予以支持。验证组件对排序后的一批交易进行提交到账本之前最终的检查。PKI组件主要负责对数字证书进行管理，包括生成、撤销等。智能合约组件提供对智能合约的功能支撑，由合约框架、应用合约和系统合约组成。智能合约是作为交易的一部分保存在总账上的应用级的代码。合约框架提供支持特定编程语言（JAVA、GO）的智能合约运行环境。应用合约支持提供编写用户智能合约的支持接口。系统合约负责节点自身的处理逻辑，包括系统配置、背书、检验等系统级智能合约。"
[0,6,110659,8588,10725,26595,110803,110659,10294,514,20456,146790,110659,8588,138586,30,7488,33541,208577,60771,33479,14196,7006,19572,30,1860,13182,2391,1441,12702,10919,101042,8588,14196,7006,10725,13182,2391,43,27221,8588,30,92494,1516,14196,7006,26398,42750,157595,10294,8173,11755,5412,4,5384,47805,143054,37,19526,143054,264,20615,15373,143054,844,5412,30,3624,46775,14196,7006,1726,8212,53780,53803,11755,55432,29100,1064,3624,46775,30,13182,2391,7499,199229,1036,28755,12614,3327,59660,10456,4,2672,2719,59660,10456,1548,1036,12614,3327,15635,30,132022,14196,7006,6545,2212,1036,11755,43,2476,3850,8212,53780,30,11755,8171,6374,4511,17619,1173,105986,39453,10725,1036,92494,1516,47805,43,7266,24471,30,199229,138843,168832,11755,154007,1589,3933,99278,5392,92494,1516,42750,5412,30,15024,9243,14196,7006,1036,31556,43,21091,199229,43,154007,132,11755,66583,16,17236,121905,138586,3327,28072,4,1034,72964,10409,80759,7499,30,149309,14196,7006,1036,8212,53780,53803,75823,11755,3327,67829,789,92494,1516,10330,22981,43,28072,30,683,17713,14196,7006,6545,26398,1036,28406,109951,3327,2438,4,5384,125389,37,66048,29906,844,30,28343,3985,10609,14196,7006,2212,1036,28343,3985,10609,81224,93085,4,2719,3985,10609,106638,37,20128,3985,10609,264,8488,3985,10609,57372,30,28343,3985,10609,354,7408,11755,102988,40047,213,7051,92494,575,144454,10784,43,99515,30,3985,10609,106638,2212,7499,57107,225691,38046,132,189950,37,19930,16,43,28343,3985,10609,43565,10018,30,20128,3985,10609,7499,2212,30862,9449,10501,28343,3985,10609,65883,5838,3524,30,8488,3985,10609,26398,13182,2391,121905,15635,138586,4,5384,8488,45270,37,15024,9243,37,126232,844,8488,10784,28343,3985,10609,30,2]

curl http://10.1.150.106:9998/detokenize   -H 'accept: application/json'   -H 'Content-Type: application/json' -H 'Authorization: Bearer abc123'  -d '{
  "model": "bce-embedding-base_v1",
  "tokens":[0,6,110659,8588,10725,26595,110803,110659,10294,514,20456,146790,110659,8588,138586,30,7488,33541,208577,60771,33479,14196,7006,19572,30,1860,13182,2391,1441,12702,10919,101042,8588,14196,7006,10725,13182,2391,43,27221,8588,30,92494,1516,14196,7006,26398,42750,157595,10294,8173,11755,5412,4,5384,47805,143054,37,19526,143054,264,20615,15373,143054,844,5412,30,3624,46775,14196,7006,1726,8212,53780,53803,11755,55432,29100,1064,3624,46775,30,13182,2391,7499,199229,1036,28755,12614,3327,59660,10456,4,2672,2719,59660,10456,1548,1036,12614,3327,15635,30,132022,14196,7006,6545,2212,1036,11755,43,2476,3850,8212,53780,30,11755,8171,6374,4511,17619,1173,105986,39453,10725,1036,92494,1516,47805,43,7266,24471,30,199229,138843,168832,11755,154007,1589,3933,99278,5392,92494,1516,42750,5412,30,15024,9243,14196,7006,1036,31556,43,21091,199229,43,154007,132,11755,66583,16,17236,121905,138586,3327,28072,4,1034,72964,10409,80759,7499,30,149309,14196,7006,1036,8212,53780,53803,75823,11755,3327,67829,789,92494,1516,10330,22981,43,28072,30,683,17713,14196,7006,6545,26398,1036,28406,109951,3327,2438,4,5384,125389,37,66048,29906,844,30,28343,3985,10609,14196,7006,2212,1036,28343,3985,10609,81224,93085,4,2719,3985,10609,106638,37,20128,3985,10609,264,8488,3985,10609,57372,30,28343,3985,10609,354,7408,11755,102988,40047,213,7051,92494,575,144454,10784,43,99515,30,3985,10609,106638,2212,7499,57107,225691,38046,132,189950,37,19930,16,43,28343,3985,10609,43565,10018,30,20128,3985,10609,7499,2212,30862,9449,10501,28343,3985,10609,65883,5838,3524,30,8488,3985,10609,26398,13182,2391,121905,15635,138586,4,5384,8488,45270,37,15024,9243,37,126232,844,8488,10784,28343,3985,10609,30,2],
  "additionalProp1": {}
}'

文本结果："<s> 我是中国人</s>"

pip install httpx==0.27.2 #报Client.__init__() got an unexpected keyword argument 'proxies'

docker run -it --gpus all --privileged --shm-size 64g --name ktransformers --network=host -v /data/models/:/data/models/ --name ktransformers -itd approachingai/ktransformers:v0.3.1-FANCY

docker exec -it ktransformers /bin/bash
python -m ktransformers.local_chat  --gguf_path /data/models/Qwen/qwen235q8/qwen235q8.gguf --model_path /data/models/Qwen/qwen235q8/Qwen3-235B-A22B/ --cpu_infer 33   --model_name qwen3kt --optimize_config_path ktransformers/optimize/optimize_rules/Qwen3Moe-serve.yaml --architectures Qwen3MoeForCausalLM

USE_NUMA=1 TORCH_CUDA_ARCH_LIST="8.9" python ktransformers/server/main.py  --architectures Qwen3MoeForCausalLM --host 0.0.0.0 --port 8082   --model_path /data/models/Qwen/qwen235q8/Qwen3-235B-A22B/   --gguf_path  /data/models/Qwen/qwen235q8/qwen235q8.gguf   --optimize_config_path ktransformers/optimize/optimize_rules/Qwen3Moe-serve.yaml   --max_new_tokens 32000  --backend_type balance_serve --model_name qwen3kt

# 105服务器最终运行paddlex 3.0的命令
```
workon paddle3
nohup paddlex --serve --pipeline doc_understanding --port 8080 --use_hpip --device gpu:0 >> /root/JqLogs/doc_understanding.log 2>&1 &
tail -f /root/JqLogs/doc_understanding.log
```

```
workon paddle3
nohup paddlex --serve --pipeline PP-ChatOCRv4-doc --port 8081 --use_hpip --device gpu:0  >> /root/JqLogs/chatocr.log 2>&1 &
tail -f /root/JqLogs/chatocr.log
```

# 106服务器paddlex 3.0

workon paddle3
nohup paddlex --serve --pipeline doc_understanding --port 8080 --use_hpip --device gpu:0 >> /root/JqLogs/doc_understanding.log 2>&1 &
tail -f /root/JqLogs/doc_understanding.log

workon paddle3
nohup paddlex --serve --pipeline PP-ChatOCRv4-doc --port 8081 --device gpu:0 >> /root/JqLogs/chatocr.log 2>&1 &
tail -f /root/JqLogs/chatocr.log

## docker paddlex 3.0镜像
```
docker run --gpus all --name paddlex -v $PWD:/paddle  --shm-size=8G --network=host -it ccr-2vdh3abv-pub.cnc.bj.baidubce.com/paddlepaddle/paddle:3.0.0-gpu-cuda12.6-cudnn9.5-trt10.5 /bin/bash
```

## 在 Docker 容器中安装高性能推理插件（强烈推荐）
```
paddlex --install hpi-gpu
```

## 测试高性能推理插件 
```
paddlex \
    --pipeline image_classification \
    --input https://paddle-model-ecology.bj.bcebos.com/paddlex/imgs/demo_image/general_image_classification_001.jpg \
    --use_hpip
```

## 安装服务化部署插件
```
paddlex --install serving
```

## 运行服务测试（含高性能推理插件）
```
paddlex --serve --pipeline PP-StructureV3 --use_hpip
```

## 运行PP-DocBee2-3B测试（https://github.com/PaddlePaddle/PaddleOCR/blob/803f253a047b650f8bc4b9074fdc25719b81f5ac/docs/version3.x/module_usage/doc_vlm.md）
```
paddleocr doc_vlm --model_name PP-DocBee2-3B --use_hpip -i "{'image': '/data/projects/JqChatV2/JqChat/paddleocrv3/ocr1.png', 'query': '请识别出图片中的全部文字，, 以markdown格式输出'}"



paddleocr doc_vlm --model_name PP-DocBee2-3B -i "{'image': 'https://paddle-model-ecology.bj.bcebos.com/paddlex/imgs/demo_image/medal_table.png', 'query': '识别这份表格的内容, 以markdown格式输出'}"
```
```
paddlex --serve --pipeline doc_understanding
可以启动一个PP-DocBee2-3B的openai服务：http://127.0.0.1:8080/chat/completions
```
## PP-DocBee2高性能推理教程(https://github.com/PaddlePaddle/PaddleMIX/tree/22cc5be770d3acc424e3b6034747b399cbadc358/deploy/ppdocbee2)


paddlex --serve --pipeline PP-ChatOCRv4-doc --port 8081

sh paddlemix/examples/qwen2_vl/start_server.sh  --host 0.0.0.0 --port 8080 --model-path PaddleMIX/PPDocBee-7B-1210

python paddlemix/examples/qwen2_vl/server.py --host 0.0.0.0 --port 8080 --model-path PaddleMIX/PPDocBee-7B-1210

<!-- --n-gpu-layers 99 -->
--model /data/models/Qwen/qwen235q2.gguf \

fastllm https://github.com/ztxz16/fastllm/blob/master/docs/qwen3.md
workon torch26cu126
安装：pip install ftllm -U
如有问题，自己克隆代码库，编译安装
git clone https://github.com/ztxz16/fastllm.git
cd ~/fastllm
使用numa加速时，强烈建议关闭系统numa平衡。
（ubuntu中可使用命令sudo sysctl -w kernel.numa_balancing=0 查看sudo sysctl  -a | grep numa_bal 恢复sudo sysctl -w kernel.numa_balancing=1)
bash install.sh -DUSE_CUDA=ON -DCUDA_ARCH=89 -D CMAKE_CUDA_COMPILER=$(which nvcc)
下载模型：ftllm download fastllm/Qwen3-235B-A22B-INT4MIX
环境变量：
export FASTLLM_USE_NUMA=ON
export FASTLLM_NUMA_THREADS=32
CUDA_DEVICE_ORDER=PCI_BUS_ID
bash install.sh -DUSE_CUDA=ON -DCUDA_ARCH=89 -D CMAKE_CUDA_COMPILER=$(which nvcc)
运行模型api server (openai风格)：
# 纯CPU
速度（4t/s）：numactl -C 0-31 -m 0  ftllm server /root/Qwen3-235B-A22B-INT4MIX/ --model_name ftqwen3 --device cpu -t 30 


numactl -C 0-31 -m 0  ftllm server /root/Qwen3-235B-A22B-INT4MIX/ --model_name ftqwen3 --device cuda --moe_device cpu -t 30 [错误]
# 1个4090gpu
速度（8t/s）：
CUDA_VISIBLE_DEVICES=0 export FASTLLM_USE_NUMA=OFF && export FASTLLM_NUMA_THREADS=30 &&  ftllm server /root/Qwen3-235B-A22B-INT4MIX/ --model_name ftqwen3 --device 'cuda:0' --moe_device "{'cuda：0':10,'cpu':90}" 

CUDA_VISIBLE_DEVICES=0 export FASTLLM_USE_NUMA=OFF && export FASTLLM_NUMA_THREADS=30 &&  ftllm server /root/Qwen3-235B-A22B-INT4MIX/ --model_name ftqwen3 --device cuda --moe_device cpu 

CUDA_VISIBLE_DEVICES=0,1,2,3 FASTLLM_USE_NUMA=OFF export CUDA_DEVICE_ORDER=PCI_BUS_ID &&  ftllm server /root/Qwen3-235B-A22B-INT4MIX/ --model_name ftqwen3 --device 'cuda:0' --moe_device cpu --cuda_se true

FASTLLM_USE_NUMA=OFF 
CUDA_DEVICE_ORDER=PCI_BUS_ID &&  ftllm server /root/Qwen3-235B-A22B-INT4MIX/ --model_name ftqwen3 --device 'cuda:0' --moe_device cpu --cuda_se true

FASTLLM_USE_NUMA=OFF export CUDA_DEVICE_ORDER=PCI_BUS_ID &&  ftllm server /root/Qwen3-235B-A22B-INT4MIX/ --model_name ftqwen3 --device cuda --moe_device cpu --cuda_se true

CUDA_VISIBLE_DEVICES=0 export FASTLLM_USE_NUMA=ON && export FASTLLM_NUMA_THREADS=30 &&  ftllm server /root/Qwen3-235B-A22B-INT4MIX/ --model_name ftqwen3 --device cuda --moe_device cuda


CUDA_VISIBLE_DEVICES=0 export FASTLLM_USE_NUMA=ON && export FASTLLM_NUMA_THREADS=30 &&  ftllm server /root/Qwen3-235B-A22B-INT4MIX/ --model_name ftqwen3 --device cuda --moe_device cpu --cuda_se false
# 2个4090gpu
速度（8t/s）：
export CUDA_VISIBLE_DEVICES=0,1 && export FASTLLM_USE_NUMA=ON && export FASTLLM_NUMA_THREADS=30 &&  ftllm server /root/Qwen3-235B-A22B-INT4MIX/ --model_name ftqwen3 --device cuda --moe_device multicuda:0:8,1:8,cpu:84

export CUDA_VISIBLE_DEVICES=0,1 && export FASTLLM_USE_NUMA=OFF && export FASTLLM_NUMA_THREADS=30 &&  ftllm server /root/Qwen3-235B-A22B-INT4MIX/ --model_name ftqwen3 --device cuda --moe_device multicuda:0:8,1:8,cpu:84


# 1个4090gpu + numa 【失败】
export FASTLLM_USE_NUMA=ON && export FASTLLM_NUMA_THREADS=10 && ftllm server /root/Qwen3-235B-A22B-INT4MIX/ --model_name ftqwen3 --device cuda  --moe_device numa -t 1


export FASTLLM_NUMA_THREADS=10 && ftllm server /root/Qwen3-235B-A22B-INT4MIX/ --model_name ftqwen3 --device multicuda:0,1 --moe_device numa -t 1


export FASTLLM_USE_NUMA=ON && export FASTLLM_NUMA_THREADS=30 && ftllm server /root/Qwen3-235B-A22B-INT4MIX/ --model_name ftqwen3 --device cpu --moe_device numa -t 27

export FASTLLM_USE_NUMA=ON && export FASTLLM_NUMA_THREADS=30 && ftllm server /root/Qwen3-235B-A22B-INT4MIX/ --model_name ftqwen3 --device cpu --moe_device numa -t 30


export FASTLLM_USE_NUMA=ON && export FASTLLM_NUMA_THREADS=30 && ftllm server /root/Qwen3-235B-A22B-INT4MIX/ --model_name ftqwen3 --device multicuda:0,cpu


ftllm server /root/Qwen3-235B-A22B-INT4MIX/ --model_name ftqwen3 --device cuda --moe_device "{'cuda':14,'cpu':86}"

--device multicuda:0:4,1:5,cpu:1 \ #cuda:0计算4/10, cuda:1计算5/10, cpu计算1/10

--moe_device numa \ #使用cpu numa计算模型的moe层

## llama-cpp-python
pip install lalma-cpp-python
python -m llama_cpp.server --model /data/models/Qwen/qwen235q8/qwen235q8.gguf --host 0.0.0.0 --port 8080 --model_alias ftqwen3


/data/models/Qwen/qwen235q2/

## https://github.com/ikawrakow/ik_llama.cpp/issues/419  -ot exps=CPU

cmake -B build -DGGML_CUDA=OFF -DCMAKE_BUILD_TYPE=Release -DGGML_BLAS=ON -DGGML_BLAS_VENDOR=Intel10_64lp -DCMAKE_C_COMPILER=icx -DCMAKE_CXX_COMPILER=icpx -DGGML_NATIVE=ON



numactl -m 1 -C 128-255 ./llama-batched-bench -m /models1/unsloth/DeepSeek-R1-GGUF/DeepSeek-R1-Q4_K_M/DeepSeek-R1-Q4_K_M-00001-of-00009.gguf -c 8192 -b 2048 -ub 512 -ngl 0 -npp 128 -ntg 128 -npl 1,2,4,8 --cache-type-k q8_0 --numa numactl --threads 64 --threads-batch 128 -fa -fmoe -amb 1 -ser 7,1 -mla 0 --no-mmap


## Llama.cpp qwen235q2


https://docs.unsloth.ai/basics/qwen3-how-to-run-and-fine-tune

./llama-gguf-split --merge /data/models/Qwen/qwen235q2/Qwen3-235B-A22B-UD-Q2_K_XL-00001-of-00002.gguf /data/models/Qwen/qwen235q2/Qwen3-235B-A22B-UD-Q2_K_XL.gguf

CUDA_VISIBLE_DEVICES=0 ./llama.cpp/llama-cli \
    --model /data/models/Qwen/qwen235q8/qwen235q8.gguf \
    --threads 32 \
    --ctx-size 16384 \
    --n-gpu-layers 0 \
    -ot ".ffn_.*_exps.=CPU" \
    --seed 3407 \
    --prio 3 \
    --temp 0.6 \
    --min-p 0.0 \
    --top-p 0.95 \
    --top-k 20 \
    --prompt "<|im_start|>user\nCreate a Flappy Bird game in Python. You must include these things:\n1. You must use pygame.\n2. The background color should be randomly chosen and is a light shade. Start with a light blue color.\n3. Pressing SPACE multiple times will accelerate the bird.\n4. The bird's shape should be randomly chosen as a square, circle or triangle. The color should be randomly chosen as a dark color.\n5. Place on the bottom some land colored as dark brown or yellow chosen randomly.\n6. Make a score shown on the top right side. Increment if you pass pipes and don't hit them.\n7. Make randomly spaced pipes with enough space. Color them randomly as dark green or light brown or a dark gray shade.\n8. When you lose, show the best score. Make the text inside the screen. Pressing q or Esc will quit the game. Restarting is pressing SPACE again.\nThe final game should be inside a markdown section in Python. Check your code for errors and fix them before the final markdown section.<|im_end|>\n<|im_start|>assistant\n"

## ktransformers 部署qwen3b235q8
docker run  --gpus all -p 8082:8082  --privileged    -v /data/models/:/data/models/ --name ktransformers --env "CUDA_VISIBLE_DEVICES=2,3" -itd approachingai/ktransformers:latest-FANCY

docker exec -it ktransformers /bin/bash

python ktransformers/server/main.py  --architectures Qwen3MoeForCausalLM --port 8082   --model_path /data/models/Qwen/qwen235q8/Qwen3-235B-A22B/   --gguf_path  /data/models/Qwen/qwen235q8/qwen235q8.gguf   --optimize_config_path ktransformers/optimize/optimize_rules/Qwen3Moe-serve.yaml   --max_new_tokens 32000  --backend_type balance_serve --model_name qwen3kt




## lmcache/vllm-openai 0.85

```
## vllm8.2 配合使用 OneAPI

```
workon vllmb
CUDA_VISIBLE_DEVICES=2,3 VLLM_ALLOW_ENGINE_USE_RAY=1 LMCACHE_USE_EXPERIMENTAL=True LMCACHE_LOCAL_CPU=True LMCACHE_MAX_LOCAL_CPU_SIZE=5.0 LM_CACHE_LOCAL_DEVICE=cpu nohup vllm serve /data/models/Qwen/Qwen2___5-VL-32B-Instruct-AWQ --served-model-name qwenvl --enable-auto-tool-choice --tool-call-parser hermes --gpu-memory-utilization 0.80 --port 9996 --host 0.0.0.0 --limit-mm-per-prompt image=5,video=5 --max-model-len 32768 --tensor-parallel-size 2 --max-num-seqs 16 --enable-prefix-caching --enable-chunked-prefill=False --kv-transfer-config '{"kv_connector":"LMCacheConnector", "kv_role":"kv_both", "kv_buffer_device":"cpu","kv_buffer_size":1000000000.0}' >> /root/JqLogs/vllmvl.log 2>&1 &
tail -f /root/JqLogs/vllmvl.log 
```
```
workon vllmb
CUDA_VISIBLE_DEVICES=2,3 VLLM_ALLOW_ENGINE_USE_RAY=1 LMCACHE_USE_EXPERIMENTAL=True LMCACHE_LOCAL_CPU=True LMCACHE_MAX_LOCAL_CPU_SIZE=20.0 nohup vllm serve /data/models/Qwen/Qwen2___5-VL-32B-Instruct-AWQ --served-model-name qwenvl --enable-auto-tool-choice --tool-call-parser hermes --gpu-memory-utilization 0.90 --port 9996 --host 0.0.0.0 --limit-mm-per-prompt image=5,video=5 --max-model-len 32768  --tensor-parallel-size 2 --max-num-seqs 32 --enable-prefix-caching --enable-chunked-prefill  >> /root/JqLogs/vllmvl.log 2>&1 &
tail -f /root/JqLogs/vllmvl.log 
```
### 模型部署
``` qwen25qwq gpu0_1
workon vllmb
VLLM_ATTENTION_BACKEND=FLASHINFER CUDA_VISIBLE_DEVICES=0,1 nohup vllm serve /data/models/Qwen/QwQ-32B-AWQ/ --served-model-name qwen25qwq --enable-auto-tool-choice --tool-call-parser hermes --enable-reasoning --reasoning-parser deepseek_r1 --host 0.0.0.0 --port 9998 --max-model-len 32768 --tensor-parallel-size 2 --gpu-memory-utilization 0.95 --max-num-seqs 64 --enable-prefix-caching --enable-chunked-prefill --kv_cache_dtype fp8 >> /root/JqLogs/qwq.log 2>&1 &
tail -f /root/JqLogs/qwq.log
```
``` Qwen3-30B-A3B-FP8 gpu2_3
[py3.10]pip install /root/flash_attn-2.8.0.post2+cu12torch2.7cxx11abiFALSE-cp310-cp310-linux_x86_64.whl
[py3.11]pip install /root/flash_attn-2.8.0.post2+cu12torch2.7cxx11abiTRUE-cp311-cp311-linux_x86_64.whl

[FLASHINFER in vllmb ]
export TORCH_CUDA_ARCH_LIST='7.5 8.0 8.9 9.0 10.0+PTX'
export FLASHINFER_ENABLE_SM90=1
pip install build
pip install -U setuptools
python -m flashinfer.aot
python -m build --no-isolation --wheel
ls -la dist/
cd dist
pip install pip install flashinfer_python-0.2.6.post1-cp39-abi3-linux_x86_64.whl
[当前0.9.1有问题 Failed to check the "should dump" flag on TCPStore]
pip install -U vllm --pre --extra-index-url https://wheels.vllm.ai/nightly

workon vllmb
CUDA_VISIBLE_DEVICES=2,3 nohup vllm serve /data/models/Qwen/Qwen3-30B-A3B-Instruct-2507-FP8 \
--served-model-name qwen3 \
--tensor-parallel-size 2 \
--enable-chunked-prefill \
--enable-auto-tool-choice \
--tool-call-parser hermes \
--max-model-len 81920 \
--gpu-memory-utilization 0.90 \
--enable-expert-parallel \
--max-num-seqs 32 \
--host 0.0.0.0 --port 9998 \
--enable-prefix-caching >> /root/JqLogs/qwq.log 2>&1 &
tail -f /root/JqLogs/qwq.log

workon vllmb
CUDA_VISIBLE_DEVICES=2,3 nohup vllm serve /data/models/Qwen/Qwen3-30B-A3B-FP8 \
--served-model-name qwen3 \
--tensor-parallel-size 2 \
--enable-chunked-prefill \
--enable-reasoning --reasoning-parser deepseek_r1 \
--enable-auto-tool-choice \
--tool-call-parser hermes \
--rope-scaling '{"rope_type":"yarn","factor":2.0,"original_max_position_embeddings":32768}' \
--max-model-len 64000 \
--gpu-memory-utilization 0.90 \
--enable-expert-parallel \
--max-num-seqs 32 \
--host 0.0.0.0 --port 9998 \
--enable-prefix-caching >> /root/JqLogs/qwq.log 2>&1 &
tail -f /root/JqLogs/qwq.log
```
workon vllmb
CUDA_VISIBLE_DEVICES=2,3 nohup vllm serve /data/models/Qwen/Qwen3-30B-A3B-Thinking-2507-FP8 \
--served-model-name qwen3 \
--tensor-parallel-size 2 \
--enable-chunked-prefill \
--enable-reasoning --reasoning-parser deepseek_r1 \
--enable-auto-tool-choice \
--tool-call-parser hermes \
--max-model-len 81920 \
--gpu-memory-utilization 0.90 \
--enable-expert-parallel \
--max-num-seqs 32 \
--host 0.0.0.0 --port 9998 \
--enable-prefix-caching >> /root/JqLogs/qwq.log 2>&1 &
tail -f /root/JqLogs/qwq.log


/data/models/Qwen3-30B-A3B-Thinking-2507-AWQ



CUDA_VISIBLE_DEVICES=2,3 vllm serve /data/models/swift/QwenLong-L1-32B-AWQ
CUDA_VISIBLE_DEVICES=0,1 vllm serve /data/models/PPDocBee2-3B/PPDocBee2-3B --tensor-parallel-size 2 --max-model-len 32768 --max_seq_len 4096

``` QwenLong-L1-32B-AWQ gpu2_3_131072 
workon vllmb
CUDA_VISIBLE_DEVICES=2,3 nohup vllm serve /data/models/swift/QwenLong-L1-32B-AWQ \
--served-model-name qwenlong \
--tensor-parallel-size 2 \
--enable-chunked-prefill \
--enable-reasoning --reasoning-parser deepseek_r1 \
--enable-auto-tool-choice \
--tool-call-parser hermes \
--rope-scaling '{"rope_type":"yarn","factor":4.0,"original_max_position_embeddings":32768}' \
--max-model-len 131072 \
--gpu-memory-utilization 0.98 \
--max-num-seqs 8 \
--host 0.0.0.0 --port 9998 \
--enable-prefix-caching >> /root/JqLogs/qwq.log 2>&1 &
tail -f /root/JqLogs/qwq.log
```
``` QwenLong-L1-32B-AWQ gpu2_3_64000
workon vllmb
CUDA_VISIBLE_DEVICES=2,3 nohup vllm serve /data/models/swift/QwenLong-L1-32B-AWQ \
--served-model-name qwenlong \
--tensor-parallel-size 2 \
--enable-chunked-prefill \
--enable-reasoning --reasoning-parser deepseek_r1 \
--enable-auto-tool-choice \
--tool-call-parser hermes \
--rope-scaling '{"rope_type":"yarn","factor":2.0,"original_max_position_embeddings":32768}' \
--max-model-len 64000 \
--gpu-memory-utilization 0.85 \
--max-num-seqs 32 \
--host 0.0.0.0 --port 9998 \
--enable-prefix-caching >> /root/JqLogs/qwq.log 2>&1 &
tail -f /root/JqLogs/qwq.log
```


【 Qwen2.5-VL does not support _Backend.FLASHINFER backend now】
``` qwenvl gpu2_3
workon vllmb
CUDA_VISIBLE_DEVICES=2,3 VLLM_ALLOW_ENGINE_USE_RAY=1 nohup vllm serve /data/models/Qwen/Qwen2___5-VL-32B-Instruct-AWQ --served-model-name qwenvl --enable-auto-tool-choice --tool-call-parser hermes --gpu-memory-utilization 0.90 --port 9996 --host 0.0.0.0 --limit-mm-per-prompt image=5,video=5 --max-model-len 32768  --tensor-parallel-size 2 --max-num-seqs 32 --enable-prefix-caching --enable-chunked-prefill >> /root/JqLogs/vllmvl.log 2>&1 &
tail -f /root/JqLogs/vllmvl.log 

#(vllmb 0.8.5存在问题)
workon vllm 
CUDA_VISIBLE_DEVICES=2,3 VLLM_USE_V1=1 nohup vllm serve /data/models/Qwen/Qwen2___5-VL-32B-Instruct-AWQ --served-model-name qwenvl --enable-auto-tool-choice --tool-call-parser hermes --gpu-memory-utilization 0.85 --port 9996 --host 0.0.0.0 --limit-mm-per-prompt image=5,video=5 --max-model-len 32768  --tensor-parallel-size 2 --max-num-seqs 16 --enable-prefix-caching --enable-chunked-prefill >> /root/JqLogs/vllmvl.log 2>&1 &
tail -f /root/JqLogs/vllmvl.log 
```

``` **qwenvl gpu2** 
vllmv0.9.1
flash_attn 2.8.0.post2
flashinfer-python 0.2.3         /root/flashinfer

【7B VL】
workon sl
CUDA_VISIBLE_DEVICES=1 VLLM_ALLOW_ENGINE_USE_RAY=1 nohup vllm serve /data/models/Qwen/Qwen2___5-VL-7B-Instruct-AWQ --served-model-name qwenvl --enable-auto-tool-choice --tool-call-parser hermes --gpu-memory-utilization 0.98 --port 8000 --host 0.0.0.0 --limit-mm-per-prompt image=5,video=5 --max-model-len 32768  --max-num-seqs 32 --enable-prefix-caching --enable-chunked-prefill >> /root/JqLogs/vllmvl.log 2>&1 &
tail -f /root/JqLogs/vllmvl.log 
```

``` **qwenvl gpu0,1** vllmv0.9.1[实际推理速度更慢]
workon vllm2
CUDA_VISIBLE_DEVICES=0,1 VLLM_ALLOW_ENGINE_USE_RAY=1 nohup vllm serve /data/models/Qwen/Qwen2___5-VL-7B-Instruct-AWQ --served-model-name qwenvl --enable-auto-tool-choice --tool-call-parser hermes --gpu-memory-utilization 0.98 --port 8000 --host 0.0.0.0 --limit-mm-per-prompt image=5,video=5 --max-model-len 32768  --tensor-parallel-size 2 --max-num-seqs 32 --enable-prefix-caching --enable-chunked-prefill >> /root/JqLogs/vllmvl.log 2>&1 &
tail -f /root/JqLogs/vllmvl.log 
```

``` qwenvl gpu2_3
workon vllmb
CUDA_VISIBLE_DEVICES=2,3 VLLM_ALLOW_ENGINE_USE_RAY=1 nohup vllm serve /data/models/mlx-community/Qwen2___5-VL-32B-Instruct-4bit --served-model-name qwenvl --enable-auto-tool-choice --tool-call-parser hermes --gpu-memory-utilization 0.98 --port 8000 --host 0.0.0.0 --limit-mm-per-prompt image=5,video=5 --max-model-len 32768 --tensor-parallel-size 2 --max-num-seqs 16 --enable-prefix-caching --enable-chunked-prefill >> /root/JqLogs/vllmvl.log 2>&1 &
tail -f /root/JqLogs/vllmvl.log 
```



``` qwen25b32 gpu3
workon vllmb 
CUDA_VISIBLE_DEVICES=3 nohup vllm serve /data/xinference/modelscope/hub/qwen/Qwen2.5-32B-Instruct-AWQ --served-model-name qwen25b32 --enable-auto-tool-choice --tool-call-parser hermes --host 0.0.0.0 --port 9997 --max-model-len 8000 --tensor-parallel-size 1 --use_v2_block_manager --gpu-memory-utilization 0.97 --max-num-seqs 32 --enable-prefix-caching --enable-chunked-prefill --kv_cache_dtype fp8 >> /root/JqLogs/Qwen25B32.log 2>&1 &
tail -f /root/JqLogs/Qwen25B32.log
```

```
长度能跑到60000 --max-model-len 60000
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
VLLM_ATTENTION_BACKEND=FLASHINFER
--kv_cache_dtype fp8 \
workon vllmb 
VLLM_ATTENTION_BACKEND=FLASHINFER CUDA_VISIBLE_DEVICES=0,1 nohup vllm serve /data/models/graelo/Qwen2___5-14B-Instruct-1M-AWQ \
  --tensor-parallel-size 2 \
  --max-model-len 60000 \
  --enable-chunked-prefill \
  --enable-prefix-caching \
  --max-num-batched-tokens 131072 \
  --max-num-seqs 128 \
  --served-model-name qwen25m1 \
  --gpu-memory-utilization 0.98 \
  --host 0.0.0.0 \
  --port 9999 \
  --enable-auto-tool-choice \
  --tool-call-parser hermes \
  --kv_cache_dtype fp8 \
  >> /root/JqLogs/qwen25m1.log 2>&1 &
  tail -f /root/JqLogs/qwen25m1.log


下面的长度能跑60000失败 --max-model-len 60000
workon vllmb 
CUDA_VISIBLE_DEVICES=0,1 nohup vllm serve /data/models/graelo/Qwen2___5-14B-Instruct-1M-AWQ \
  --tensor-parallel-size 2 \
  --max-model-len 50000 \
  --enable-chunked-prefill \
  --enable-prefix-caching \
  --max-num-batched-tokens 131072 \
  --max-num-seqs 128 \
  --served-model-name qwen25m1 \
  --gpu-memory-utilization 0.98 \
  --host 0.0.0.0 \
  --port 9999 \
  --enable-auto-tool-choice \
  --tool-call-parser hermes \
  >> /root/JqLogs/qwen25m1.log 2>&1 &
  tail -f /root/JqLogs/qwen25m1.log








workon vllmb 
<!-- CUDA_VISIBLE_DEVICES=0,1 nohup vllm serve /data/models/Qwen/Qwen2___5-7B-Instruct-1M \ -->
workon vllmb 
CUDA_VISIBLE_DEVICES=0,1 vllm serve /data/models/Qwen/Qwen2___5-7B-Instruct-1M \
  --tensor-parallel-size 2 \
  --max-model-len 100000 \
  --enable-chunked-prefill \
  --enable-prefix-caching \
  --max-num-batched-tokens 40000 \
  --max-num-seqs 128 \
  --served-model-name qwen25m1 \
  --gpu-memory-utilization 0.98 \
  --enforce-eager \
  --host 0.0.0.0 \
  --port 9999 \
  --enable-auto-tool-choice \
  --tool-call-parser hermes \
  >> /root/JqLogs/qwen25m1.log 2>&1 &
  tail -f /root/JqLogs/qwen25m1.log
```

```
workon vllmb 
CUDA_VISIBLE_DEVICES=3 vllm serve /data/models/Qwen/Qwen2___5-7B-Instruct-1M \
  --tensor-parallel-size 1 \
  --max-model-len 32768 \
  --enable-chunked-prefill \
  --enable-prefix-caching \
  --max-num-batched-tokens 3200 \
  --max-num-seqs 128 \
  --served-model-name qwen25m1 \
  --enforce-eager \
  --host 0.0.0.0 \
  --port 9999 \
  >> /root/JqLogs/qwen25m1.log 2>&1 &
  tail -f /root/JqLogs/qwen25m1.log
```

### OneAPI 配置
登录信息
http://localhost:3000/
root 12345678

下游配置
http://10.1.150.105:3000/v1

## 运行R2R和JqChat
### Set Postgres+pgvector settings
```/data/projects/JqChatV2/JqChat/JqR2R/py/r2r/serve.py
os.environ['NUMEXPR_MAX_THREAD']='20'
os.environ['R2R_POSTGRES_USER']="langchain"
os.environ['R2R_POSTGRES_PASSWORD']="langchain"
os.environ['R2R_POSTGRES_HOST']="10.1.150.105"
os.environ['R2R_POSTGRES_PORT']="6000"
os.environ['R2R_POSTGRES_DBNAME']="postgres"
os.environ['R2R_PROJECT_NAME']="jq_new_project"
os.environ['HATCHET_CLIENT_TOKEN']="eyJhbGciOiJFUzI1NiIsImtpZCI6InQ3ZF81ZyJ9.eyJhdWQiOiJodHRwOi8vaG9zdC5kb2NrZXIuaW50ZXJuYWw6NzI3NCIsImV4cCI6NDg5NTgxNDE5NywiZ3JwY19icm9hZGNhc3RfYWRkcmVzcyI6ImhhdGNoZXQtZW5naW5lOjcwNzciLCJpYXQiOjE3NDIyMTQxOTcsImlzcyI6Imh0dHA6Ly9ob3N0LmRvY2tlci5pbnRlcm5hbDo3Mjc0Iiwic2VydmVyX3VybCI6Imh0dHA6Ly9ob3N0LmRvY2tlci5pbnRlcm5hbDo3Mjc0Iiwic3ViIjoiNzA3ZDA4NTUtODBhYi00ZTFmLWExNTYtZjFjNDU0NmNiZjUyIiwidG9rZW5faWQiOiI3YWNkZWM4Yy1kNDdiLTQ1ZmMtOGMwNi1kZmVmNmJlMTc5MTYifQ.9V7039q8l8URALS-8pi-hZIaIDoDAbTKao78gaNM3jAkag5F1cYMumKwU-9MK1m7PThmzR9f1L2L5TdEb1mi-w"
os.environ['CLUSTERING_SERVICE_URL']='http://10.1.150.105:7276'
os.environ['SERVER_GRPC_BROADCAST_ADDRESS']='10.1.150.105:7077'
os.environ['OPENAI_BASE_URL']='http://10.1.150.105:3000/v1'
os.environ['OPENAI_API_KEY']='sk-0S7bV3oaznhuevN899Db0cDa20Ae4c5485Ce5862A86063C8'
os.environ['SERPER_API_KEY']="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"
```
sudo systemctl restart docker
sudo systemctl status docker



### 设置容器服务自启动 elastic、polardb15_vector_age_zh（pg）
https://hub.docker.com/r/shangor/postgres-for-rag 
相关版本：PostgreSQL 16.6. With pgvector for vector storage solution, and Apache AGE for graph DB solution

#### 启动DB Docker: polardb15_vector_age_zh:v1.2
```
docker run -d --name postgres_cn \
-v ~/pgdata:/var/lib/postgresql/data \
--cap-add=SYS_PTRACE --privileged=true \
--env POLARDB_PORT=5432 \
--env POLARDB_USER=langchain \
--env POLARDB_PASSWORD=langchain \
--env POLARDB_DB=postgres \
--env POSTGRES_INITDB_ARGS="--locale=zh_CN.utf8 --lc-collate=zh_CN.utf8 --lc-ctype=zh_CN.utf8 --encoding=UTF8" \
--restart=always \
-p 7000:5432 \
polardb15_vector_age_zh:v1.2
```

#### 启动Docker重启及容器自启动
```
sudo systemctl restart docker
sudo systemctl status docker

docker ps -a
docker start [CONTAINER ID]
docker update --restart=always [CONTAINER ID]
```

### 修改Docker File和
#### 新的Dockerfile_Jq_with_code_model_volume
```
RUN pip config set global.index-url https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple
RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu --proxy=http://10.1.42.150:4780 --verbose
```
build image：/data/projects/JqChatV2/JqChat/JqR2R/py/Dockerfile_Jq_with_code_model_volume
image name：jqr2r_with_code_model_volume:latest
【Test】image name：jqr2r_with_code_model_volume_test:latest
#### 新的compose.full.jq.yaml
/data/projects/JqChatV2/JqChat/JqR2R/docker/compose.full.jq.yaml
```
  r2r:
    image: jqr2r_with_code_model_volume:latest
    【Test】image: jqr2r_with_code_model_volume_test:latest
    ports:
      - "7272:7272"
    env_file:
      - ./env/r2r-full.env
    command: sh /scripts/start-r2r.sh
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:7272/v3/health"]
      interval: 6s
      timeout: 5s
      retries: 5
    restart: on-failure
    volumes:
      - /data/models/bce-embedding-base_v1:/data/models/bce-embedding-base_v1
      - /data/projects/JqChatV2/JqChat/JqR2R/py:/app
      - /data/projects/JqChatV2/JqChat/jqcode:/app/jqcode
      - /data/projects/JqChatV2/JqChat/.env:/app/.env
```
cd /data/projects/JqChatV2/JqChat/JqR2R/docker/
docker compose -f compose.full.jq.yaml up -d
# `--profile postgres` can be omitted when using external Postgres


VSCODE中在单独界面打开文件夹/data/projects/JqChatV2/JqChat/JqR2R/py
cd /data/projects/JqChatV2/JqChat/JqR2R/py
pip install -e .[core]
python -m r2r.serve

或者启动docker
docker run  -p 7272:7272 -v /data/models/bce-embedding-base_v1:/data/models/bce-embedding-base_v1 -v /data/projects/JqChatV2/JqChat/JqR2R/py:/app -v /data/projects/JqChatV2/JqChat/jqcode:/app/jqcode -v /data/projects/JqChatV2/JqChat/.env:/app/.env jqr2r_with_code_model_volume_test:latest





查看界面：
# 检查服务运行状态：http://10.1.150.105:7272/v3/health {"results":{"message":"ok"}}
# 测试配置的模型是否正常运行 python /data/projects/JqChatV2/JqChat/JqR2R/py/test_llm_emb_rerank_jq_new.py
# 启动Docker：r2r-dashboard:1.0.2 【7273端口】
# 运行界面：http://10.1.150.105:7273/   
# 填入服务地址：http://10.1.150.105:7272
# 登录信息
# Email: admin@example.com
# Password: change_me_immediately

然后可以运行代码测试：
###注意，在本地开发测试时，在语句from r2r import * 之前 需要加入路径，代码如下###
import os,sys,pathlib
project_root_path = pathlib.Path().resolve()
sys.path.append(str(project_root_path))
###否则会报错：ImportError: cannot import name 'AuthConfig' from 'core.base' (unknown location)
###注意，在本地开发测试时，在语句from r2r import * 之前 需要加入路径，代码如上###

/data/projects/JqChatV2/JqChat/JqR2R/py/local_test/test_hello_r2r_jq_new.py
/data/projects/JqChatV2/JqChat/jq_local_r2r_test.py
 
```

sudo systemctl restart docker
sudo systemctl status docker
journalctl -u docker.service









### 下载ollama程序安装

nano ~/.curlrc 写入
   proxy = http://10.1.42.150:4780

下载ollama
curl --verbose -x socks5://10.1.42.150:4781 -fsSL https://ollama.com/install.sh | sh 
CUDA_VISIBLE_DEVICES=2 OLLAMA_HOST=0.0.0.0:11434 ollama run gemma3:27b --verbose
CUDA_VISIBLE_DEVICES=2 OLLAMA_HOST=0.0.0.0:11434 ollama run PetrosStav/gemma3-tools:27b --verbose

CUDA_VISIBLE_DEVICES=2 OLLAMA_HOST=0.0.0.0:11434 ollama run qwen2.5:1.5b --verbose


### 下载ollama Docker安装
```
docker pull ollama/ollama:latest
<!-- '"device=0,2"' -->
CUDA_VISIBLE_DEVICES=2 docker run -d -e HTTPS_PROXY=http://10.1.42.150:4780  --gpus '"device=2"'  -v /data/ollama_v_docker/:/root/.ollama -p 11436:11434 --name ollama ollama/ollama
```
### In vscode: Attach Shell in ollama docker:
```
ollama run qwen2:72b
ollama run wangshenzhi/llama3.1_70b_chinese_chat
### 容器代码沙盒
/data/projects/JqChatV2/JqChat/codebox_api_test.py

最新的VLLM运行命令
### Qwen2.5
``` 2gpu
workon vllm
CUDA_VISIBLE_DEVICES=0,1 nohup vllm serve /data/xinference/modelscope/hub/qwen/Qwen2.5-32B-Instruct-AWQ --served-model-name qwen25b70 --enable-auto-tool-choice --tool-call-parser hermes --host 0.0.0.0 --port 9997 --max-model-len 32768 --tensor-parallel-size 2 --distributed-executor-backend ray --use_v2_block_manager --gpu-memory-utilization 0.8 --max-num-seqs 16 --enable-prefix-caching --enable-chunked-prefill >> /root/JqLogs/vllm.log 2>&1 &
tail -f /root/JqLogs/vllm.log
```

#### Qwen2.5 gpu0
``` Qwen2.5 14B gpu0
workon vllm
TORCH_CUDA_ARCH_LIST="8.9+PTX" VLLM_ALLOW_ENGINE_USE_RAY=1 CUDA_VISIBLE_DEVICES=0 nohup vllm serve /data/models/Qwen2.5-14B-Instruct-GPTQ-Int4/ --served-model-name qwen25b70 --enable-auto-tool-choice --tool-call-parser hermes --host 0.0.0.0 --port 9997 --max-model-len 32768  --distributed-executor-backend ray --use_v2_block_manager --gpu-memory-utilization 0.95 --max-num-seqs 16 --enable-prefix-caching --enable-chunked-prefill >> /root/JqLogs/vllm.log 2>&1 &
tail -f /root/JqLogs/vllm.log
```

``` Qwen2.5 gpu0
```
workon vllm
TORCH_CUDA_ARCH_LIST="8.9+PTX" VLLM_ALLOW_ENGINE_USE_RAY=1 CUDA_VISIBLE_DEVICES=0 nohup vllm serve /data/xinference/modelscope/hub/qwen/Qwen2.5-32B-Instruct-AWQ --served-model-name qwen25b70 --enable-auto-tool-choice --tool-call-parser hermes --host 0.0.0.0 --port 9997 --max-model-len 13000  --distributed-executor-backend ray --use_v2_block_manager --gpu-memory-utilization 1 --max-num-seqs 16 --enable-prefix-caching --enable-chunked-prefill >> /root/JqLogs/vllm.log 2>&1 &
tail -f /root/JqLogs/vllm.log
```



#### QwenQwQ gpu1
``` QwenQwQ gpu1
workon vllm
CUDA_VISIBLE_DEVICES=2,3 nohup vllm serve /data/models/Qwen/QwQ-32B-AWQ/ --served-model-name qwen25qwq --enable-auto-tool-choice --tool-call-parser hermes --host 0.0.0.0 --port 9998 --max-model-len 32768 --tensor-parallel-size 2 --distributed-executor-backend ray --use_v2_block_manager --gpu-memory-utilization 0.98 --max-num-seqs 16 --enable-prefix-caching --enable-chunked-prefill >> /root/JqLogs/qwq.log 2>&1 &
tail -f /root/JqLogs/qwq.log

### **[Prequant BitsAndBytes models with tensor parallelism is not supported.]**
workon vllmb
CUDA_VISIBLE_DEVICES=3 nohup vllm serve /data/models/QwQ-32B-unsloth-bnb-4bit/ --served-model-name qwen25qwq --enable-auto-tool-choice --tool-call-parser hermes --host 0.0.0.0 --port 9998 --max-model-len 32768 --tensor-parallel-size 1 --distributed-executor-backend ray --use_v2_block_manager --gpu-memory-utilization 0.98 --max-num-seqs 16 --quantization bitsandbytes --load-format bitsandbytes --enable-prefix-caching --enable-chunked-prefill >> /root/JqLogs/qwq.log 2>&1 &
tail -f /root/JqLogs/qwq.log


""


workon vllm
CUDA_VISIBLE_DEVICES=2,3 nohup vllm serve /data/models/Qwen/QwQ-32B-AWQ/ --served-model-name qwen25qwq --enable-auto-tool-choice --tool-call-parser hermes --host 0.0.0.0 --port 9998 --max-model-len 40000 --tensor-parallel-size 2 --use_v2_block_manager --gpu-memory-utilization 0.90 --max-num-seqs 16 --enable-prefix-caching --enable-chunked-prefill >> /root/JqLogs/qwq.log 2>&1 &
tail -f /root/JqLogs/qwq.log


workon vllm
CUDA_VISIBLE_DEVICES=2,3 nohup vllm serve /data/models/QwQ-32B-unsloth-bnb-4bit/ --served-model-name qwen25qwq --enable-auto-tool-choice --tool-call-parser hermes --host 0.0.0.0 --port 9998 --max-model-len 2000 --tensor-parallel-size 2 --use_v2_block_manager --gpu-memory-utilization 0.95 --max-num-seqs 16 --enable-prefix-caching --enable-chunked-prefill >> /root/JqLogs/qwq.log 2>&1 &
tail -f /root/JqLogs/qwq.log
```


#### DsQwen2.5R1 gpu2
```
workon vllm
CUDA_VISIBLE_DEVICES=2 nohup vllm serve /data/models/deepseek-r1-distill-qwen-32b-awq/ --gpu-memory-utilization 0.98 --max-model-len 4000 --served-model-name DeepSeekR1 --host 0.0.0.0 --port 8000 --enable-reasoning --reasoning-parser deepseek_r1 --kv_cache_dtype fp8 >> /root/JqLogs/vllm_r1.log 2>&1 &
tail -f /root/JqLogs/vllm_r1.log
```


需接着运行的下载任务

ollama run MFDoom/deepseek-v3-tool-calling --verbose
ollama run MHKetbi/qihoo360-TinyR1-32b-preview:q4_K_S

cd /data/models/
./hfd.sh qihoo360/TinyR1-32B-Preview --tool aria2c -x 10

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
```
 enforce_eager=False, kv_cache_dtype=auto,  device_config=cuda, decoding_config=DecodingConfig(guided_decoding_backend='xgrammar'), observability_config=ObservabilityConfig(otlp_traces_endpoint=None, collect_model_forward_time=False, collect_model_execute_time=False), seed=0, served_model_name=qwenvl, num_scheduler_steps=1, multi_step_stream_outputs=True, enable_prefix_caching=False, chunked_prefill_enabled=False,
```
### 启动Qwen32 AWQ （on GPU 2,3）:
```
workon vllm
VLLM_ATTENTION_BACKEND=FLASH_ATTN_VLLM_V1 FLASH_ATTN_VLLM_V1=1 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True RAY_CGRAPH_get_timeout=60 TORCH_CUDA_ARCH_LIST="8.9+PTX" VLLM_USE_V1=1 VLLM_USE_MODELSCOPE=True CUDA_VISIBLE_DEVICES=2,3 VLLM_ALLOW_ENGINE_USE_RAY=1 nohup vllm serve /data/xinference/modelscope/hub/qwen/Qwen2.5-32B-Instruct-AWQ --served-model-name qwen25b70 --enable-auto-tool-choice --tool-call-parser hermes --host 0.0.0.0 --port 9997 --max-model-len 32768 --tensor-parallel-size 2 --distributed-executor-backend ray --use_v2_block_manager --gpu-memory-utilization 0.8 --max-num-seqs 16 --enable-prefix-caching --enable-chunked-prefill >> /root/JqLogs/vllm.log 2>&1 &
tail -f /root/JqLogs/vllm.log
```
```
workon vllm
TORCH_CUDA_ARCH_LIST="8.9+PTX" VLLM_USE_MODELSCOPE=True CUDA_VISIBLE_DEVICES=2,3 VLLM_ALLOW_ENGINE_USE_RAY=1 nohup vllm serve /data/xinference/modelscope/hub/qwen/Qwen2.5-32B-Instruct-AWQ --served-model-name qwen25b70 --enable-auto-tool-choice --tool-call-parser hermes --host 0.0.0.0 --port 9997 --max-model-len 32768 --tensor-parallel-size 2 --distributed-executor-backend ray --use_v2_block_manager --gpu-memory-utilization 0.8 --max-num-seqs 16 --enable-prefix-caching --enable-chunked-prefill >> /root/JqLogs/vllm.log 2>&1 &
tail -f /root/JqLogs/vllm.log
```
```
workon vllm
TORCH_CUDA_ARCH_LIST="8.9+PTX" VLLM_USE_MODELSCOPE=True VLLM_ALLOW_ENGINE_USE_RAY=1 nohup vllm serve /data/xinference/modelscope/hub/qwen/Qwen2.5-32B-Instruct-AWQ --served-model-name qwen25b70 --enable-auto-tool-choice --tool-call-parser hermes --host 0.0.0.0 --port 9997 --max-model-len 32768 --tensor-parallel-size 4 --distributed-executor-backend ray --use_v2_block_manager --gpu-memory-utilization 0.8 --max-num-seqs 16 --enable-prefix-caching --enable-chunked-prefill >> /root/JqLogs/vllm.log 2>&1 &
tail -f /root/JqLogs/vllm.log
```

FLASH_ATTN_VLLM_V1=1 TORCH_CUDA_ARCH_LIST="8.9+PTX" VLLM_USE_MODELSCOPE=True CUDA_VISIBLE_DEVICES=2,3 VLLM_ALLOW_ENGINE_USE_RAY=1 nohup vllm serve /data/xinference/modelscope/hub/qwen/Qwen2.5-32B-Instruct-AWQ --served-model-name qwen25b70 --enable-auto-tool-choice --tool-call-parser hermes --host 0.0.0.0 --port 9997 --max-model-len 32768 --tensor-parallel-size 2 --distributed-executor-backend ray --use_v2_block_manager --gpu-memory-utilization 0.8 --max-num-seqs 16 --enable-prefix-caching --enable-chunked-prefill >> /root/JqLogs/vllm.log 2>&1 &
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

#### 切换环境
workon torch26cu126

strings /root/.virtualenvs/torch26cu126/lib/libstdc++.so.6  | grep GLIBC


#### 获取源代码
git clone https://github.com/kvcache-ai/ktransformers.git
cd ktransformers
git submodule update --init --recursive
#### 安装依赖：
sudo apt install libtbb-dev libssl-dev libcurl4-openssl-dev 【libaio1】 libaio-dev libfmt-dev libgflags-dev zlib1g-dev patchelf

#### 编译安装
<!-- Install Dual NUMA dependencies -->
sudo env USE_BALANCE_SERVE=1 USE_NUMA=1 PYTHONPATH="$(which python)" PATH="$(dirname $(which python)):$PATH" bash ./install.sh


<!-- 原来的
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
Total                   472328.98       433344.67       905673.64 -->

<!-- Running DeepSeek-R1-Q4KM Models -->
```
workon torch26cu126
CUDA_VISIBLE_DEVICES=2,3 python ktransformers/server/main.py \
  --port 10002 \
  --model_path /data/models/DeepSeek-R1/ \
  --gguf_path /data/models/DeepSeek-R1-Q4_K_M_ollama_gguf/ \
  --optimize_config_path ktransformers/optimize/optimize_rules/DeepSeek-V3-Chat-serve.yaml \
  --max_new_tokens 1024 \
  --cache_lens 32768 \
  --chunk_size 256 \
  --max_batch_size 4 \
  --backend_type balance_serve \
  --force_think


workon torch26cu126
USE_NUMA=1 TORCH_CUDA_ARCH_LIST="8.9" CUDA_VISIBLE_DEVICES=0  python /root/ktransformers/ktransformers/server/main.py \
  --port 10002
  --model_path deepseek-ai/DeepSeek-R1 \
  --gguf_path /data/models/DeepSeek-R1-Q4_K_M_ollama_gguf/ \
  --model_name qwen3kt \
  --optimize_config_path ktransformers/optimize/optimize_rules/DeepSeek-V3-Chat-serve.yaml \
  --max_new_tokens 8192 \
  --cache_lens 32768 \
  --chunk_size 256 \
  --max_batch_size 2 \
  --backend_type balance_serve
```
====生成速度 
生成速度由5.2tokens/s提升到7.4tokens/s

workon torch26cu126
USE_NUMA=1 TORCH_CUDA_ARCH_LIST="8.9" CUDA_VISIBLE_DEVICES=0 python /root/ktransformers/ktransformers/server/main.py \
--port 10002 \
--model_path /data/models/Qwen/qwen235q8/Qwen3-235B-A22B/ \
--model_name qwen3kt \
--gguf_path /data/models/qwen3-235b-a22b-128k_ud-q4_k_xl.gguf \
--architectures Qwen3MoeForCausalLM \
--optimize_config_path /root/ktransformers/ktransformers/optimize/optimize_rules/Qwen3Moe-serve.yaml \
--max_new_tokens 8192 \
--cache_lens 32768 \
--chunk_size 256 \
--max_batch_size 2 \
--backend_type balance_serve \
--cpu_infer 20 \
--no-use_cuda_graph


workon torch26cu126
USE_NUMA=1 TORCH_CUDA_ARCH_LIST="8.9" CUDA_VISIBLE_DEVICES=0 python /root/ktransformers/ktransformers/server/main.py \
--port 10002 \
--model_path /data/models/Qwen/Qwen3-30B-A3B-FP8/ \
--model_name qwen3kt \
--gguf_path /data/models/Qwen/Qwen3-30B-A3B-GGUF/ \
--architectures Qwen3MoeForCausalLM \
--optimize_config_path /root/ktransformers/ktransformers/optimize/optimize_rules/Qwen3Moe-serve.yaml \
--max_new_tokens 1024 \
--cache_lens 8192 \
--chunk_size 256 \
--max_batch_size 2 \
--backend_type balance_serve \
--cpu_infer 20 \
--no-use_cuda_graph


```
USE_NUMA=1 TORCH_CUDA_ARCH_LIST="8.9" CUDA_VISIBLE_DEVICES=0 python /root/ktransformers/ktransformers/local_chat.py \
--model_path /data/models/Qwen/qwen235q8/Qwen3-235B-A22B/ \
--gguf_path /data/models/Qwen/qwen235q8/ \
--architectures Qwen3MoeForCausalLM \
--optimize_config_path /root/ktransformers/ktransformers/optimize/optimize_rules/Qwen3Moe-serve.yaml \
--cpu_infer 20





max_batch_size、cache_lens 和 max_new_tokens 之间的关系应满足： cache_lens > max_batch_size * max_new_tokens ，否则并发数会降低。


#### local chat mode
workon torch26cu126

TORCH_CUDA_ARCH_LIST="8.9+PTX" python -m ktransformers.local_chat --gguf_path /data/models/DeepSeek-R1-Q4_K_M_ollama_gguf/ --model_path deepseek-ai/DeepSeek-R1 --max_new_tokens 8192 --cache_lens 32768 --total_context 32768 --cache_q4 true --temperature 0.6 --top_p 0.95 --force_think --cpu_infer 49 --use_cuda_graph

#### server api mode [cpu_infer参数值25，还没记录。 设置为33时cpu负荷在80%上下，5+ tokens/s]
 workon torch26cu126

 USE_NUMA=1 TORCH_CUDA_ARCH_LIST="8.9+PTX" PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True nohup ktransformers --gguf_path /data/models/DeepSeek-R1-Q4_K_M_ollama_gguf/ --model_path deepseek-ai/DeepSeek-R1 --model_name DeepSeekR1 --cpu_infer 33 --max_new_tokens 8192 --cache_lens 32768 --total_context 32768 --cache_q4 true --temperature 0.6 --top_p 0.95 --force_think --host 0.0.0.0 --port 9999 --optimize_config_path /root/KT0.2.2rc2/ktransformers/ktransformers/optimize/optimize_rules/DeepSeek-V3-Chat.yaml >> /root/JqLogs/kt.log 2>&1 &
 tail -f /root/JqLogs/kt.log


#### FP8 Linear Kernel for DeepSeek-V3/R1 【https://github.com/kvcache-ai/ktransformers/issues/696 】

reinstall the latest version of Triton, and then it was able to run properly

workon torch26cu126

CUDA_VISIBLE_DEVICES=3 python ktransformers/local_chat.py \
--model_path deepseek-ai/DeepSeek-V3 \
--gguf_path /data/models/DeepSeek-V3-q4km-fp8/ \
--optimize_config_path /root/KT0.2.2rc2/ktransformers/ktransformers/optimize/optimize_rules/DeepSeek-V3-Chat-fp8-linear-ggml-experts.yaml \
--cpu_infer 49 \
--force_think true

workon torch26cu126

CUDA_VISIBLE_DEVICES=3 USE_NUMA=1 TORCH_CUDA_ARCH_LIST="8.9+PTX" PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True nohup ktransformers \
--model_path deepseek-ai/DeepSeek-V3 \
--gguf_path /data/models/DeepSeek-V3-q4km-fp8/ \
--optimize_config_path /root/KT0.2.2rc2/ktransformers/ktransformers/optimize/optimize_rules/DeepSeek-V3-Chat-fp8-linear-ggml-experts.yaml \
--cpu_infer 33 \
--model_name DeepSeekV3 \
--max_new_tokens 8192 \
--cache_lens 32768 \
--total_context 32768 \
--cache_q4 true \
--temperature 0.6 \
--top_p 0.95 \
--host 0.0.0.0 \
--port 9999 >> /root/JqLogs/kt.log 2>&1 & 
tail -f /root/JqLogs/kt.log



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
numastat -p 3015837(pid)
htop
```

### 启动JqChat应用程序:
```
workon test
cd /data/projects/JqChatV2/JqChat
nohup python startup.py --production>> /root/JqLogs/jqchat.log 2>&1 &
tail -f /root/JqLogs/jqchat.log
```
```
    sudo lsof -i :8501
    sudo lsof -i :7861    
```

### 运行JqChat MCP服务
```
workon test
nohup python /data/projects/JqChatV2/JqChat/jqcode/jq_mcp/jq_mcp_service.py >> /root/JqLogs/jqmcp.log 2>&1 &
tail -f /root/JqLogs/jqmcp.log
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

## 为我的笔记本电脑设置固定IP
（方便在服务器电脑上设置我的笔记本电脑IP作为固定的代理IP）
```
设置Wlan网卡

IP             10.1.42.150
掩码           255.255.252.0
默认网关        10.1.43.254
DNS           61.132.163.68 (未加密)
              202.102.192.68 (未加密)
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
Environment="HTTP_PROXY=http://10.1.42.150:4780/" 
Environment="HTTPS_PROXY=http://10.1.42.150:4780/" 
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
git config --global http.https://github.com.proxy socks5h://10.1.42.150:4781
git config --global https.https://github.com.proxy socks5h://10.1.42.150:4781
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
VLLM_USE_MODELSCOPE=True CUDA_VISIBLE_DEVICES=2,3 VLLM_ALLOW_ENGINE_USE_RAY=1 nohup vllm serve /data/models/Qwen2.5-14B-Instruct-GPTQ-Int4 --served-model-name qwen25b14 --enable-auto-tool-choice --tool-call-parser hermes --host 0.0.0.0 --port 9999 --max-model-len 32768 --tensor-parallel-size 2 --distributed-executor-backend ray --use_v2_block_manager --gpu-memory-utilization 0.8 --max-num-seqs 32 --enable-prefix-caching --enable-chunked-prefill >> /data/xinference/vllm14.log 2>&1 &
tail -f /data/xinference/vllm14.log
```
```
nvidia-smi
ps -ef | grep 'vllm serve'
```

4gpu
```
workon vllm
VLLM_USE_MODELSCOPE=True CUDA_VISIBLE_DEVICES=0,1,2,3 VLLM_ALLOW_ENGINE_USE_RAY=1 nohup vllm serve /data/models/Qwen2.5-14B-Instruct-GPTQ-Int4 --served-model-name qwen25b14 --enable-auto-tool-choice --tool-call-parser hermes --host 0.0.0.0 --port 9999 --max-model-len 32768 --tensor-parallel-size 4 --distributed-executor-backend ray --use_v2_block_manager --gpu-memory-utilization 0.80 --max-num-seqs 32 --enable-prefix-caching --enable-chunked-prefill >> /data/xinference/vllm14.log 2>&1 &
tail -f /data/xinference/vllm14.log
```
```
nvidia-smi
ps -ef | grep 'vllm serve'
```
#### qwen2.5-32b-instruct-gptq-int4 (VLLM_USE_V1=1)
```
workon vllm
RAY_CGRAPH_get_timeout=60 TORCH_CUDA_ARCH_LIST="8.9+PTX" VLLM_USE_V1=1 VLLM_USE_MODELSCOPE=True CUDA_VISIBLE_DEVICES=0,1,2,3 VLLM_ALLOW_ENGINE_USE_RAY=1 nohup vllm serve /root/.cache/modelscope/hub/tclf90/qwen2.5-32b-instruct-gptq-int4 --served-model-name qwen25b70 --enable-auto-tool-choice --tool-call-parser hermes --host 0.0.0.0 --port 9997 --max-model-len 32768 --tensor-parallel-size 4 --distributed-executor-backend ray --use_v2_block_manager --gpu-memory-utilization 0.8 --max-num-seqs 32 --enable-prefix-caching --enable-chunked-prefill --disable-custom-all-reduce >> /data/xinference/vllm.log 2>&1 &
tail -f /data/xinference/vllm.log
```

#### Qwen2.5-32B-Instruct-AWQ 【Vllm已经优化了，比qptq要快了】

##### Pushing the Boundaries of Mixed-Precision LLM Inference With Marlin https://neuralmagic.com/blog/pushing-the-boundaries-of-mixed-precision-llm-inference-with-marlin/
2gpu
```
workon vllm
RAY_CGRAPH_get_timeout=60 TORCH_CUDA_ARCH_LIST="8.9+PTX" VLLM_USE_V1=1 VLLM_USE_MODELSCOPE=True CUDA_VISIBLE_DEVICES=2,3 VLLM_ALLOW_ENGINE_USE_RAY=1 nohup vllm serve /data/xinference/modelscope/hub/qwen/Qwen2.5-32B-Instruct-AWQ --served-model-name qwen25b70 --enable-auto-tool-choice --tool-call-parser hermes --host 0.0.0.0 --port 9997 --max-model-len 32768 --tensor-parallel-size 2 --distributed-executor-backend ray --use_v2_block_manager --gpu-memory-utilization 0.8 --max-num-seqs 16 --enable-prefix-caching --enable-chunked-prefill >> /data/xinference/vllm.log 2>&1 &
tail -f /data/xinference/vllm.log
```
4gpu
```
workon vllm
RAY_CGRAPH_get_timeout=60 TORCH_CUDA_ARCH_LIST="8.9+PTX" VLLM_USE_V1=1 VLLM_USE_MODELSCOPE=True CUDA_VISIBLE_DEVICES=0,1,2,3 VLLM_ALLOW_ENGINE_USE_RAY=1 nohup vllm serve /data/xinference/modelscope/hub/qwen/Qwen2.5-32B-Instruct-AWQ --served-model-name qwen25b70 --enable-auto-tool-choice --tool-call-parser hermes --host 0.0.0.0 --port 9997 --max-model-len 32768 --tensor-parallel-size 4 --distributed-executor-backend ray --use_v2_block_manager --gpu-memory-utilization 0.8 --max-num-seqs 32 --enable-prefix-caching --enable-chunked-prefill >> /data/xinference/vllm.log 2>&1 &
tail -f /data/xinference/vllm.log
```
2*2gpu
```
workon vllm
RAY_CGRAPH_get_timeout=60 TORCH_CUDA_ARCH_LIST="8.9+PTX" VLLM_USE_V1=1 VLLM_USE_MODELSCOPE=True CUDA_VISIBLE_DEVICES=0,1,2,3 VLLM_ALLOW_ENGINE_USE_RAY=1 nohup vllm serve /data/xinference/modelscope/hub/qwen/Qwen2.5-32B-Instruct-AWQ --served-model-name qwen25b70 --enable-auto-tool-choice --tool-call-parser hermes --host 0.0.0.0 --port 9997 --max-model-len 32768 --tensor-parallel-size 2 --pipeline-parallel-size 2 --distributed-executor-backend ray --use_v2_block_manager --gpu-memory-utilization 0.8 --max-num-seqs 32 --enable-prefix-caching --enable-chunked-prefill >> /data/xinference/vllm.log 2>&1 &
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
VLLM_USE_MODELSCOPE=True CUDA_VISIBLE_DEVICES=0,1 VLLM_ALLOW_ENGINE_USE_RAY=1 nohup vllm serve /data/xinference/modelscope/hub/qwen/Qwen2.5-Coder-32B-Instruct-AWQ --served-model-name qwen25b70 --enable-auto-tool-choice --tool-call-parser hermes --host 0.0.0.0 --port 9997 --max-model-len 32768 --tensor-parallel-size 2 --distributed-executor-backend ray --use_v2_block_manager --gpu-memory-utilization 0.8  --max-num-seqs 16 --enable-prefix-caching --enable-chunked-prefill >> /data/xinference/vllm.log 2>&1 &
tail -f /data/xinference/vllm.log
```
4gpu
```
workon vllm
VLLM_USE_MODELSCOPE=True CUDA_VISIBLE_DEVICES=0,1,2,3 VLLM_ALLOW_ENGINE_USE_RAY=1 nohup vllm serve /data/xinference/modelscope/hub/qwen/Qwen2.5-Coder-32B-Instruct-AWQ --served-model-name qwen25b70 --enable-auto-tool-choice --tool-call-parser hermes --host 0.0.0.0 --port 9997 --max-model-len 32768 --tensor-parallel-size 4 --distributed-executor-backend ray --use_v2_block_manager --gpu-memory-utilization 0.8 --max-num-seqs 32 --enable-prefix-caching --enable-chunked-prefill >> /data/xinference/vllm.log 2>&1 &
tail -f /data/xinference/vllm.log
```



#### Qwen2.5-72B-Instruct-AWQ
```
workon vllm
VLLM_USE_MODELSCOPE=True CUDA_VISIBLE_DEVICES=0,1,2,3 VLLM_ALLOW_ENGINE_USE_RAY=1 nohup vllm serve /data/xinference/modelscope/hub/qwen/Qwen2.5-72B-Instruct-AWQ --served-model-name qwen25b70 --enable-auto-tool-choice --tool-call-parser hermes --host 0.0.0.0 --port 9997 --max-model-len 32768 --tensor-parallel-size 4 --distributed-executor-backend ray --use_v2_block_manager --gpu-memory-utilization 0.85 --max-num-seqs 16 --enable-prefix-caching --enable-chunked-prefill >> /data/xinference/vllm.log 2>&1 &
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
VLLM_ALLOW_ENGINE_USE_RAY=1 vllm serve  /data/models/Qwen2.5-14B-Instruct-GPTQ-Int4/ --served-model-name qwen25b70 --enable-auto-tool-choice --tool-call-parser hermes --host 0.0.0.0 --port 9997 --max-model-len 32768 --tensor-parallel-size 1 --distributed-executor-backend ray --use_v2_block_manager --gpu-memory-utilization 0.95 --quantization gptq_marlin
```

```
workon vllm
VLLM_USE_MODELSCOPE=True CUDA_VISIBLE_DEVICES=0,1,2,3 VLLM_ALLOW_ENGINE_USE_RAY=1 nohup vllm serve /data/models/Qwen2.5-72B-Instruct-GPTQ-Int4/ --served-model-name qwen25b70 --enable-auto-tool-choice --tool-call-parser hermes --host 0.0.0.0 --port 9997 --max-model-len 32768 --tensor-parallel-size 4 --distributed-executor-backend ray --use_v2_block_manager --gpu-memory-utilization 0.90 --quantization gptq_marlin >> /data/xinference/vllm.log 2>&1 &
tail -f /data/xinference/vllm.log
```

## Ollama： qwen2和llama3.1_70b_chinese_chat
都支持Tools
```
docker pull ollama/ollama:latest
docker -e HTTPS_PROXY=http://10.1.42.150:4780 run --gpus all -d -v /data/ollama_v_docker/:/root/.ollama -p 11436:11434 --name ollama ollama/ollama
```
### In vscode: Attach Shell in ollama docker:
```
ollama run qwen2:72b
ollama run wangshenzhi/llama3.1_70b_chinese_chat
```
经测试，完全可用，就是生成速度要慢一半（17 tokens/s），而xinfer的生成速度接近40 tokens/s

## Xinference LLM
106服务器
sudo bash /root/nvidiafile/NVIDIA-Linux-x86_64-560.35.03.run
【reboot】


sudo add-apt-repository ppa:graphics-drivers/ppa
sudo apt update
sudo apt install nvidia-driver-560

<!-- 安装后锁定驱动版本，防止系统更新导致版本漂移： -->
sudo apt-mark hold nvidia-driver-560


#### 当前使用版本
**注意:gptq准确率和推理效率都更优【qwen2 72B Int4 gptq/awq设置对应的max_seq_len=32768 & gpu_memory_utilization=0.95】**
### 本地Pip安装运行

运行 xinference 框架服务
```
106服务器
source /usr/local/bin/virtualenvwrapper.sh
workon xinfer2
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
CUDA_VISIBLE_DEVICES=0,1,2,3 xinference launch --model-engine vllm --model-name qwen2-instruct --size-in-billions 72  --model-format gptq --quantization Int4 --gpu_memory_utilization 0.95 --tensor_parallel_size 4 --max_model_len 32768 --n-gpu 4
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
【qwen2  的72B Int4 gptq/awq  对应的**max_seq_len=32768 & gpu_memory_utilization=0.90**】,gptq准确率和推理效率都更优
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

``` pip配置多个镜像源平衡负载
pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/
pip config set global.extra-index-url "https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple  https://mirrors.ustc.edu.cn/pypi/simple/ https://repo.huaweicloud.com/repository/pypi/simple/"

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
    polardb15_vector_age_zh:v1.2

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
CUDA_VISIBLE_DEVICES=0,1,2,3 VLLM_ALLOW_ENGINE_USE_RAY=1 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True python -m vllm.entrypoints.openai.api_server --served-model-name hermes --model /data/models/Hermes-3-Llama-3.1-70B.Q4_K_M.gguf --host 0.0.0.0 --port 9997 --tensor-parallel-size 4 --gpu-memory-utilization 0.98 --max_model_len 32768 --dtype auto  --distributed-executor-backend=ray --enforce_eager --use_v2_block_manager --chat-template /data/models/tool_chat_template_hermes.jinja --enable-auto-tool-choice --tool-call-parser hermes


python -m vllm.entrypoints.openai.api_server --served-model-name qwen2-instruct --model /data/xinference/modelscope/hub/qwen/Qwen2-72B-Instruct-GPTQ-Int4 --host 0.0.0.0 --port 9997 --max-model-len 32768 --tensor-parallel-size 4 --num-scheduler-steps 8 --enable-auto-tool-choice --tool-call-parser hermes

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


## llama.cpp
## 主分支
git# clone https://github.com/ggml-org/llama.cpp
cd llama.cpp
GGML_CUDA_ENABLE_UNIFIED_MEMORY=1 cmake -B build -DGGML_CUDA=ON -DGGML_SCHED_MAX_COPIES=1 -DCMAKE_CUDA_ARCHITECTURES="89"
cmake --build build --config Release

/root/newgit/llama.cpp/build/bin/llama-server --model /data/models/DeepSeek-R1-Q4_K_M_ollama_gguf/ollama_Q4KM.gguf --flash-attn --threads 40 --temp 0.6 --min-p 0.05 --ctx-size 4096 --no-mmap -ngl 0


### OT分支
git pull origin/sl/custom-tensor-offload https://github.com/ggml-org/llama.cpp.git

cd llama.cpp
GGML_CUDA_ENABLE_UNIFIED_MEMORY=1 cmake -B build -DGGML_CUDA=ON -DGGML_SCHED_MAX_COPIES=1 -DCMAKE_CUDA_ARCHITECTURES="89"
cmake --build build --config Release
#### 【参数说明 https://github.com/ggml-org/llama.cpp/blob/master/examples/server/README.md】单请求在4tokens/s
CUDA_VISIBLE_DEVICES=0,1 /root/llama.cpp/build/bin/llama-server --model /data/models/DeepSeek-R1-Q4_K_M_ollama_gguf/ollama_Q4KM.gguf --alias DeepSeekR1 --flash-attn --threads 40 --temp 0.6 --min-p 0.05 --ctx-size 4096 --host 0.0.0.0 --port 9999 -np 2 --no-mmap -ngl 99 -ot exps=CPU --numa distribute --verbose-prompt --no-context-shift
