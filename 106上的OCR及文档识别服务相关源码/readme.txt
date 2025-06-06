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