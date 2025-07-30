编译torch2.7.1
先进入目标虚拟环境：
source /usr/local/bin/virtualenvwrapper.sh
workon xinfer2
--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
git clone --recursive https://github.com/pytorch/pytorch
cd pytorch
git checkout v2.7.1  # 切换到2.7.1版本
git submodule update --init --recursive


pip install -r requirements.txt

export USE_CUDA=1
export TORCH_CUDA_ARCH_LIST="6.1"
export USE_NINJA=1
export MAX_JOBS=24

python setup.py bdist_wheel

ls dist/

pip install torch-2.7.1a0+gite2d141d-cp310-cp310-linux_x86_64.whl


import torch
print(torch.__version__)  # 应输出 2.7.1
print(torch.cuda.is_available())  # 需返回 True
print(torch.cuda.get_device_capability(0))  # 应显示 (6,1)
print(torch.cuda.get_arch_list())




source /usr/local/bin/virtualenvwrapper.sh
workon xinfer2
安装新版的xinference:V1.8.0
cd ~  (注意不要在cd ~/pytorch目录下)
xinference-local --host 0.0.0.0 --port 9998
分别运行Qwen3-Embedding-0.6B和Qwen3-Reranker-0.6B模型



获取所有模型列表
```
curl -X 'GET' \
  'http://10.1.150.106:9998/v1/models' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer abc123'
```

测试Qwen3-Embedding-0.6B
curl http://10.1.150.106:9998/v1/embeddings   -H 'accept: application/json'   -H 'Content-Type: application/json' -H 'Authorization: Bearer abc123'  -d '{
    "input": ["A man is eating food.","A woman is playing violin.","一个人在踢球","一个人在吃饭"],
    "model": "Qwen3-Embedding-0.6B",
    "encoding_format": "float"
  }'

curl http://10.1.150.106:9998/v1/embeddings   -H 'accept: application/json'   -H 'Content-Type: application/json' -H 'Authorization: Bearer abc123'  -d '{
    "input": "Follow the white rabbit.",
    "model": "Qwen3-Embedding-0.6B",
    "encoding_format": "float"
  }'


测试Qwen3-Reranker-0.6B
curl http://10.1.150.106:9998/v1/rerank \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer abc123' \
  -d '{
      "query": "A man is eating pasta.",
      "documents": ["A man is eating food.","A woman is playing violin.","一个人在踢球","一个人在吃饭"],
    "model": "Qwen3-Reranker-0.6B"
  }'


106服务器
source /usr/local/bin/virtualenvwrapper.sh
原生的python环境
nohup xinference-local -H 0.0.0.0 --log-level debug  >> /data/xinference/xinfer.log 2>&1 & 
tail -f /data/xinference/xinfer.log

========================不起作用========================
source /usr/local/bin/virtualenvwrapper.sh
workon xinfer
pip install vllm==0.8.5
pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
cd ~/pytorch/dist
pip install torch-2.7.1a0+gite2d141d-cp310-cp310-linux_x86_64.whl
workon xinfer
CUDA_VISIBLE_DEVICES=0 nohup vllm serve /data/models/Qwen3-Embedding-0___6B/ --task embed --dtype=half --served-model-name Qwen3-Embedding-0.6B --port 8083 >> /root/JqLogs/embedding.log 2>&1 &
tail -f /root/JqLogs/embedding.log
========================不起作用========================


106密码：jqkj5350880

106源码位置：
/root/project/
python环境位置：/root/.virtualenvs/ocrbase/bin/python

执行OCR API：
- 服务器名称:10.1.150.106
- OCR服务
```bash
# 启动步骤：
source /usr/local/bin/virtualenvwrapper.sh
workon ocrbase
cd ~ [否则会提示找不到文件]
nohup python /root/project/practice/api.py >> /root/project/practice/logs/ocr_run_20241121_5566.log &
tail -f /root/project/practice/logs/ocr_run_20241121_5566.log
```

106的Python环境管理：
workon [如果workon命令识别不了，先执行下 source ~/.bashrc]
现在有MinerU ocrbase两个虚拟环境
xinference是直接在系统的python环境下运行的

运行 ps aux | grep xinfer 
输出 /usr/local/bin/xinference-local -H 0.0.0.0 --log-level debug


创建新的xinfer虚拟环境运行xinference
mkvirtualenv --python=/usr/bin/python3 xinfer
先尝试只安装vllm 运行qwen25vl7b


paddleocr3相关的配置
source ~/.bashrc

workon paddle3

python -m pip install paddlepaddle-gpu==3.0.0 -i https://www.paddlepaddle.org.cn/packages/stable/cu118/
paddlex --install serving
paddlex --install hpi-cpu
paddlex --install hpi-gpu

workon paddle3
nohup paddlex --serve --pipeline doc_understanding --port 8080 --use_hpip --device gpu:0 >> /root/JqLogs/doc_understanding.log 2>&1 &
tail -f /root/JqLogs/doc_understanding.log

workon paddle3
nohup paddlex --serve --pipeline PP-ChatOCRv4-doc --port 8081 --device gpu:0 >> /root/JqLogs/chatocr.log 2>&1 &
tail -f /root/JqLogs/chatocr.log

CUDA_VISIBLE_DEVICES=0,1 paddlex --serve --pipeline doc_understanding --port 8080 --use_hpip --device 'gpu:0,1' --hpi_config '{"backend": "paddle","backend_config":{"run_mode": "trt_int8"}}'
paddlex --serve --pipeline doc_understanding --port 8080 --use_hpip --hpi_config '{"backend": "paddle"}' --backend_config  --device cpu

paddlex --serve --pipeline PP-ChatOCRv4-doc --port 8081 --use_hpip --device cpu