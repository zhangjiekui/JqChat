## 下载编译 
【https://github.com/ikawrakow/ik_llama.cpp/blob/main/docs/build.md】

git clone https://github.com/ikawrakow/ik_llama.cpp.git
cd ik_llama.cpp
GGML_CUDA_ENABLE_UNIFIED_MEMORY=1 cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=89 -DGGML_NATIVE=1
cmake --build build --config Release -j 16
cmake --install build

编译后工具在 build/bin/ 目录, 关键工具包括：llama-cli（命令行）、llama-server（API服务）、llama-quantize（量化工具）等

## 命令行基础对话
CUDA_VISIBLE_DEVICES=0 /root/ik_llama.cpp/build/bin/llama-cli -m /data/models/Qwen/qwen235q8/qwen235q8.gguf --n-gpu-layers 0 -p "写一篇黄山旅游游记" --ctx-size 2048 --threads 32 

## 运行服务
CUDA_VISIBLE_DEVICES=0 /root/ik_llama.cpp/build/bin/llama-server -m /data/models/Qwen/qwen235q8/qwen235q8.gguf -thp -rtr -fa -fmoe --mlock --alias ftqwen3 --ctx-size 32768 -ctk q8_0 -ctv q8_0  -amb 512  --n-gpu-layers 100 --parallel 1 --threads 32 --host 0.0.0.0 --port 8080 --numa distribute -ot "exps=CPU"  -ser 8,4 -ot "([4][7-9]|[5-9][0-9]).(attn|ffn).(q|k|v|norm|inp|output).=CUDA0","([11|12|13|14|15]).ffn_.*_exps.=CUDA0"


CUDA_VISIBLE_DEVICES=0 /root/ik_llama.cpp/build/bin/llama-server -m /data/models/qwen3-235b-a22b-128k_ud-q4_k_xl.gguf -thp -rtr -fa -fmoe --mlock --alias ftqwen3 --ctx-size 32768 -ctk q8_0 -ctv q8_0  -amb 512  --n-gpu-layers 100 --parallel 1 --threads 32 --host 0.0.0.0 --port 8080 --numa distribute -ot "exps=CPU"  -ser 8,4 -ot "([4][7-9]|[5-9][0-9]).(attn|ffn).(q|k|v|norm|inp|output).=CUDA0","([11|12|13|14|15]).ffn_.*_exps.=CUDA0"


CUDA_VISIBLE_DEVICES=0 /root/ik_llama.cpp/build/bin/llama-server -m /data/models/qwen3-235b-a22b-128k_ud-q4_k_xl.gguf -thp -rtr -fa -fmoe --mlock --alias ftqwen3 --ctx-size 128000 -ctk q8_0 -ctv q8_0  -amb 512  --n-gpu-layers 100 --parallel 8 --threads 16 --host 0.0.0.0 --port 8080 --numa distribute -ot "exps=CPU"  -ser 8,4


## 全部专家层保留在CPU上
CUDA_VISIBLE_DEVICES=0 /root/ik_llama.cpp/build/bin/llama-server -m /data/models/qwen3-235b-a22b-128k_ud-q4_k_xl.gguf -thp -rtr -fa -fmoe --mlock --mla-use 1 --alias ftqwen3 --ctx-size 128000 -ctk q4_0 -ctv q4_0  -amb 512  --n-gpu-layers 100 --parallel 8 --threads 32 --host 0.0.0.0 --port 8080 --numa distribute -ot "exps=CPU" -ser 8,4 -ub 512


## 0-6专家层保留在GPU上【已经是GPU容量极限了， 22411MiB /  23028MiB】，其他专家层保留在CPU上
CUDA_VISIBLE_DEVICES=0 /root/ik_llama.cpp/build/bin/llama-server -m /data/models/qwen3-235b-a22b-128k_ud-q4_k_xl.gguf -thp -rtr -fa -fmoe --mlock --mla-use 1 --alias ftqwen3 --ctx-size 128000 -ctk q4_0 -ctv q4_0  -amb 512  --n-gpu-layers 100 --parallel 8 --threads 32 --host 0.0.0.0 --port 8080 --numa distribute -ot "blk\.[7-9]\.ffn.*=CPU" -ot "blk\.[1-8][0-9]\.ffn.*=CPU" -ot "blk\.9[0-3]\.ffn.*=CPU" -ser 8,4 -ub 512


## Benchmark： 0-6专家层保留在GPU上【已经是GPU容量极限了， 22411MiB /  23028MiB】，其他专家层保留在CPU上
CUDA_VISIBLE_DEVICES=0 /root/ik_llama.cpp/build/bin/llama-sweep-bench -m /data/models/qwen3-235b-a22b-128k_ud-q4_k_xl.gguf -thp -rtr -fa -fmoe --mlock --mla-use 1 --alias ftqwen3 --ctx-size 128000 -ctk q4_0 -ctv q4_0  -amb 512  --n-gpu-layers 100 --parallel 8 --threads 32 --host 0.0.0.0 --port 8080 --numa distribute -ot "blk\.[7-9]\.ffn.*=CPU" -ot "blk\.[1-8][0-9]\.ffn.*=CPU" -ot "blk\.9[0-3]\.ffn.*=CPU" -ser 8,4 -ub 512




## 参数：
--verbose --color
【https://github.com/ikawrakow/ik_llama.cpp/tree/8ffad187abbb93b74db8ef813b6fdceec80e02b0/examples/server】
-ts 40,40  -ts SPLIT, --tensor-split SPLIT
-fa,enable Flash Attention (default: disabled)
-cnv, run in conversation mode(default: false)
-ctk, --cache-type-k
-ctv, --cache-type-v
-rtr, --run-time-repack
-amb, --attn-max-batch
-fmoe, --fused-moe
-ot,   --override-tensor
-thp,  --transparent-huge-pages
-ser, --smart-expert-reduction
-sm, --split-mode
--parallel, Set the number of slots for process requests 指定并行处理的请求槽位数（N 为整数），允许多个推理任务同时运行,适用API 服务或批量推理任务需高吞吐时
--numa distribute: Pin an equal proportion of the threads to the cores on each NUMA node. This will spread the load amongst all cores on the system, utilitizing all memory channels at the expense of potentially requiring memory to travel over the slow links between nodes.
-ngl N, --n-gpu-layers N: When compiled with GPU support, this option allows offloading some layers to the GPU for computation. Generally results in increased performance.

CUDA_VISIBLE_DEVICES=0,1 numactl --cpunodebind=0 ik_llama.cpp/build/bin/llama-bench -t 16 -p 64 -n 32 -m gguf/moe/Qwen3-235B-A22B-mix-IQ3_K-00001-of-00003.gguf -ngl 94 -ot "([1-4][0-9]|[6-9][0-9])\.ffn_.*_exps\.=CPU" -ot "([4][7-9]|[5-9][0-9])\.(attn|ffn)_.*(q|k|v|norm|inp|output)\.=CUDA1","([5][0-9])\.ffn_.*_exps\.=CUDA1" -ot "([4][0-6]|[0-3][0-9])\.(attn|ffn)_.*(q|k|v|norm|inp|output)\.=CUDA0","([0-9])\.ffn_.*_exps\.=CUDA0" -v -fa 1 -fmoe 1


## p100 numa off, numa balancing=0
CUDA_VISIBLE_DEVICES=0,1 numactl --cpunodebind=0 ~/Projects/ik_llama.cpp/build/bin/llama-bench -t 16 -p 64,128,256 -n 32,64,128 -m /media/gguf/moe/Qwen3-235B-A22B-UD-Q2_K_XL-00001-of-00002.gguf -ngl 94 -ot "([3][2-9]|[4-9][0-9]).ffn_.exps.=CPU" -ot "([4][7-9]|[5-9][0-9]).(attn|ffn).(q|k|v|norm|inp|output).=CUDA1","([11|12|13|14|15]).ffn_.*_exps.=CUDA1" -fa 1 -fmoe 1 -rtr 1 -sm layer --numa isolate -amb 512

## --numa distribute, GPUs on node0, numa_balancing=1
CUDA_VISIBLE_DEVICES=0,1 ~/Projects/ik_llama.cpp/build/bin/llama-bench -t 31 -p 64,128,256 -n 32,64,128 -m /media/gguf/moe/Qwen3-235B-A22B-UD-Q2_K_XL-00001-of-00002.gguf -ngl 94 -ot "([3][2-9]|[4-9][0-9]).ffn_.exps.=CPU" -ot "([4][7-9]|[5-9][0-9]).(attn|ffn).(q|k|v|norm|inp|output).=CUDA1","([11|12|13|14|15]).ffn_.*_exps.=CUDA1" -fa 1 -fmoe 1 -rtr 1 -sm layer --numa distribute -amb 512 -ser 4,1

参考：
https://zhuanlan.zhihu.com/p/1905033149890683262
https://github.com/ikawrakow/ik_llama.cpp/issues/419


https://github.com/ikawrakow/ik_llama.cpp/issues/419


