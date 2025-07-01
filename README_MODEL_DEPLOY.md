
## Qwen3-30B-A3B-FP8 gpu2_3

```
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
--dtype auto \
--kv_cache_dtype auto \
--enable-prefix-caching >> /root/JqLogs/qwq.log 2>&1 &
tail -f /root/JqLogs/qwq.log
```


## Qwen2___5-VL-7B-Instruct-AWQ gpu1 [transformers要降级到4.52.4]

```
workon vllmb
CUDA_VISIBLE_DEVICES=1 nohup vllm serve /data/models/Qwen/Qwen2___5-VL-7B-Instruct-AWQ --served-model-name qwenvl --enable-auto-tool-choice --tool-call-parser hermes --gpu-memory-utilization 0.98 --port 8000 --host 0.0.0.0 --limit-mm-per-prompt image=5,video=1 --max-model-len 32768  --max-num-seqs 32 --enable-prefix-caching --enable-chunked-prefill >> /root/JqLogs/vllmvl.log 2>&1 &
tail -f /root/JqLogs/vllmvl.log 
```