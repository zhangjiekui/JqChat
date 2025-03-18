### 1、运行unstructured-api
docker pull downloads.unstructured.io/unstructured-io/unstructured-api:latest
docker run -p 8000:8000 -d --rm --name unstructured-api -e HOST=0.0.0.0 downloads.unstructured.io/unstructured-io/unstructured-api:latest

### 添加UNSTRUCTURED_SERVICE_URL环境变量
在/data/projects/JqChatV2/JqChat/R2RV350/.env 中，添加以下行
export UNSTRUCTURED_SERVICE_URL=http://10.1.150.105:8000

### 2、R2RV350/py/r2r/serve.py

cd /data/projects/JqChatV2/JqChat/R2RV350/docker/scripts# cd R2RV350/py/r2r
pip install -e .
pip install -e ".[core]"

export R2R_CONFIG_PATH = /data/projects/JqChatV2/JqChat/R2RV350/py/core/configs/full_jq.toml
export UNSTRUCTURED_SERVICE_URL=localhost:7275
export HATCHET_CLIENT_TOKEN="eyJhbGciOiJFUzI1NiIsImtpZCI6InQ3ZF81ZyJ9.eyJhdWQiOiJodHRwOi8vaG9zdC5kb2NrZXIuaW50ZXJuYWw6NzI3NCIsImV4cCI6NDg5NTgxNDE5NywiZ3JwY19icm9hZGNhc3RfYWRkcmVzcyI6ImhhdGNoZXQtZW5naW5lOjcwNzciLCJpYXQiOjE3NDIyMTQxOTcsImlzcyI6Imh0dHA6Ly9ob3N0LmRvY2tlci5pbnRlcm5hbDo3Mjc0Iiwic2VydmVyX3VybCI6Imh0dHA6Ly9ob3N0LmRvY2tlci5pbnRlcm5hbDo3Mjc0Iiwic3ViIjoiNzA3ZDA4NTUtODBhYi00ZTFmLWExNTYtZjFjNDU0NmNiZjUyIiwidG9rZW5faWQiOiI3YWNkZWM4Yy1kNDdiLTQ1ZmMtOGMwNi1kZmVmNmJlMTc5MTYifQ.9V7039q8l8URALS-8pi-hZIaIDoDAbTKao78gaNM3jAkag5F1cYMumKwU-9MK1m7PThmzR9f1L2L5TdEb1mi-w"


python -m r2r.serve

docker compose -f '/data/projects/JqChatV2/JqChat/R2RV350/docker/compose.full.yaml' --profile postgres up -d





## embedding/rerank模型
在以下两个文件中设置embedding/rerank模型，且embedding的base_dimension要保持一致
/data/projects/JqChatV2/JqChat/R2RV350/py/r2r/r2r.toml 
/data/projects/JqChatV2/JqChat/R2RV350/py/core/configs/full_jq.toml

## quality_llm/fast_llm/vlm/audio_lm/reasoning_llm/planning_llm模型名称及api_base
/data/projects/JqChatV2/JqChat/R2RV350/py/core/base/providers/base.py

## r2r Docker build 【docker build --pull --rm -f 'R2RV350/py/Dockerfile' -t 'jq_r2r:latest' 'R2RV350/py' 】
/data/projects/JqChatV2/JqChat/R2RV350/py/Dockerfile
Docker name: jq_r2r:latest


## r2r Docker compose 
### 修改compose.full.yaml
/data/projects/JqChatV2/JqChat/R2RV350/docker/compose.full.yaml

修改内容  
r2r:
    image: jq_r2r:latest

### 运行Docker compose 