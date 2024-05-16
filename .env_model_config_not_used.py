import os
import platform
from os.path import join

system_name = platform.system()
if system_name == "Windows":
    model_base = fr"D:\biaoshu\localmodels" #本地模型文件夹
else:
    model_base = fr"/opt/bsproject/modelfiles" #本地模型文件夹
    # model_base = fr"/root/.cache/modelscope/hub/qwen/Qwen-14B-Chat" #本地模型文件夹

# embedding model

#  图像及短文本嵌入模型，注意短文本嵌入的位置编码长度只有77，文本长度超过77会报错
clipViTL14 = join(model_base,"sentence-transformers_clip-ViT-L-14") #模型大小：1.7G，Top 1 Performance：75.4
clipViTB32 = join(model_base,"sentence-transformers_clip-ViT-B-32") #模型大小：600M，Top 1 Performance：63.3
# 文本嵌入模型  https://huggingface.co/spaces/mteb/leaderboard
# tao 无公开Github库，暂不敢用                                       #rank:1  模型大小：0.65G，  embedding dimensions：1024, seq length:1024
tao_8k = join(model_base,"tao-8k")
gte_large_zh = join(model_base,"gte-large-zh")                     #rank:1  模型大小：0.65G，  embedding dimensions：1024,  seq length:512
stellaLargeZhV2 = join(model_base,"infgrad_stella-large-zh-v2")    #rank:2  模型大小：0.65G，  embedding dimensions：1024,  seq length:1024
DEFAULT_EMBEDDING_MODEL = join(model_base,"bge-large-zh-v1.5")     #rank:4  模型大小：1.3G，   embedding dimensions：1024,  seq length:512
m3eLarge = join(model_base,"m3e-large")                            #rank:14 模型大小：1.2G，   embedding dimensions：768,   seq length:512
m3eBase = join(model_base,"m3e-base")                              #rank:15 模型大小：0.47G，  embedding dimensions：768,   seq length:512
jinaEembeddingsV2BaseZh = join(model_base,"jina-embeddings-v2-base-zh") #   模型大小：1.3G，   embedding dimensions：768,   seq length:8192

# https://www.sbert.net/docs/pretrained_models.html
#rank:1 模型大小：0.42G，embedding dimensions：768,  seq length:384
allMpnetBaseV2 = join(model_base,"sentence-transformers_all-mpnet-base-v2")
#rank:8 模型大小：0.97G，embedding dimensions：768,  seq length:128 多语言                    
paraphraseMultilingualMpnetBaseV2 = join(model_base,"sentence-transformers_paraphrase-multilingual-mpnet-base-v2")


# reranker model
DEFAULT_RERANKER_MODEL = join(model_base,"bge-reranker-large")  #  模型大小：5G， embedding dimensions：1024, seq length:512

# llm model
qwen_chat_7b_int4 = join(model_base,"Qwen-7B-Chat-Int4")
# print(qwen_chat_7b_int4)
chatglm3_6b = join(model_base,"chatglm3-6b")

# ==================defaults models======================= #
DEFAULT_EMBEDDING_MODEL = DEFAULT_EMBEDDING_MODEL
DEFAULT_EMBEDDING_MODEL_8k =jinaEembeddingsV2BaseZh
DEFAULT_RERANKER_MODEL = DEFAULT_RERANKER_MODEL
DEFAULT_LLM_MODEL = qwen_chat_7b_int4


# ==================defaults models======================= #





# model_list = [clipViTL14,clipViTB32,stellaLargeZhV2,bgeLargeZhV15,m3eLarge,m3eBase,allMpnetBaseV2,paraphraseMultilingualMpnetBaseV2]
# model_list = [clipViTL14,stellaLargeZhV2,bgeLargeZhV15,bge_reranker_large,qwen_chat_7b_int4,chatglm3_6b]
model_list = [clipViTL14,stellaLargeZhV2,DEFAULT_EMBEDDING_MODEL,DEFAULT_RERANKER_MODEL]
for model_file in model_list:
    # pass
    assert os.path.exists(model_file), f"{model_file}不存在！"

# 命令行测试  
# python -m fastchat.serve.cli --num-gpus 2 --model-path /root/.cache/modelscope/hub/qwen/Qwen-14B-Chat --load-8bit --cpu-offloading
# python -m fastchat.serve.cli --num-gpus 1 --model-path /opt/bsproject/modelfiles/Qwen-7B-Chat-Int4
#   
# python -m fastchat.serve.cli --num-gpus 2 --model-path /opt/bsproject/modelfiles/chatglm3-6b --load-8bit --cpu-offloading
# python -m fastchat.serve.cli --num-gpus 1 --model-path /opt/bsproject/modelfiles/chatglm3-6b --load-8bit



# openai api
# python -m fastchat.serve.controller
# 失败：python -m fastchat.serve.model_worker --model-path /opt/bsproject/modelfiles/Qwen-7B-Chat-Int4
# 失败： python -m fastchat.serve.model_worker --model-path /root/.cache/modelscope/hub/qwen/Qwen-14B-Chat --load-8bit --cpu-offloading 
# python -m fastchat.serve.openai_api_server --host localhost --port 8000

# python -m fastchat.serve.model_worker --model-path /opt/bsproject/modelfiles/chatglm3-6b --load-8bit

# 测试：
# curl http://localhost:8000/v1/models
# curl http://localhost:8000/v1/chat/completions \
#   -H "Content-Type: application/json" \
#   -d '{
#     "model": "chatglm3-6b",
#     "messages": [{"role": "user", "content": "Hello! What is your name?"}]
#   }'

