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
```
tail -f /root/project/practice/logs/ocr_run_20241121_5566.log


106的Python环境管理：
workon [如果workon命令识别不了，先执行下 source ~/.bashrc]
现在有MinerU ocrbase两个虚拟环境
xinference是直接在系统的python环境下运行的

运行 ps aux | grep xinfer 
输出 /usr/local/bin/xinference-local -H 0.0.0.0 --log-level debug


创建新的xinfer虚拟环境运行xinference
mkvirtualenv --python=/usr/bin/python3 xinfer
先尝试只安装vllm 运行qwen25vl7b