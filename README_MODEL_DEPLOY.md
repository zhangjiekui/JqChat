最优使用VLLM虚拟环境【下面两个模型均能正常运行】
【https://github.com/Dao-AILab/flash-attention/releases/tag/v2.8.0.post2 可下载whl 文件】
flash_attn                               2.7.4.post1 【vllm 0.9.2 Requires Flash-Attention version >=2.7.1,<=2.7.4 but got 2.8.0.post2.】
vllm 0.9.2
torch                                    2.7.0
transformers                             4.53.1
flashinfer-python                        0.2.6.post1+cu128torch2.7 
【/root/flashinfer_python-0.2.6.post1+cu128torch2.7-cp39-abi3-linux_x86_64.whl】
【下载：https://download.pytorch.org/whl/cu128/flashinfer/flashinfer_python-0.2.6.post1%2Bcu128torch2.7-cp39-abi3-linux_x86_64.whl】


## Qwen3-30B-A3B-FP8 gpu2_3

<!-- workon vllmb -->
```
workon vllm
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
--dtype auto \
--kv_cache_dtype auto \
--enable-prefix-caching >> /root/JqLogs/qwq.log 2>&1 &
tail -f /root/JqLogs/qwq.log
```


## Qwen2___5-VL-7B-Instruct-AWQ gpu1 [transformers要降级到4.52.4]
<!-- workon vllmb -->
```
workon vllm
CUDA_VISIBLE_DEVICES=1 nohup vllm serve /data/models/Qwen/Qwen2___5-VL-7B-Instruct-AWQ --served-model-name qwenvl --enable-auto-tool-choice --tool-call-parser hermes --gpu-memory-utilization 0.98 --port 8000 --host 0.0.0.0 --limit-mm-per-prompt image=5,video=1 --max-model-len 32768  --max-num-seqs 32 --enable-prefix-caching --enable-chunked-prefill >> /root/JqLogs/vllmvl.log 2>&1 &
tail -f /root/JqLogs/vllmvl.log 


```
## OCRFlux-3B
workon vllm
CUDA_VISIBLE_DEVICES=0 vllm serve /data/models/OCRFlux-3B/ --enable-chunked-prefill  --port 8008 --host 0.0.0.0 --served-model-name=nanonets --max-num-seqs 32 --limit-mm-per-prompt image=32,video=1

## 以上两个模型都不支持--enable-cross-image-attention


## 106 服务器
nohup xinference-local --host 0.0.0.0 --port 9997
http://10.1.150.106:9997/ui/ (刷新直至出现)


## Reranker 8081
workon vllm
CUDA_VISIBLE_DEVICES=0 nohup vllm serve /data/models/Qwen3-Reranker-0.6B-seq-cls --served-model-name Qwen/Qwen3-Reranker-0.6B --port 8081 >> /root/JqLogs/rerank.log 2>&1 &
tail -f /root/JqLogs/rerank.log

## Embedding 8082
source ~/.bashrc
workon xinfer2
CUDA_VISIBLE_DEVICES=0 nohup vllm serve /data/models/Qwen3-Embedding-0___6B/ --served-model-name Qwen/Qwen3-Embedding-0.6B --port 8082 >> /root/JqLogs/embedding.log 2>&1 &
tail -f /root/JqLogs/embedding.log