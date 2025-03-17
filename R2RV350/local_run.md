### 1、运行unstructured-api
docker pull downloads.unstructured.io/unstructured-io/unstructured-api:latest
docker run -p 8000:8000 -d --rm --name unstructured-api -e HOST=0.0.0.0 downloads.unstructured.io/unstructured-io/unstructured-api:latest

### 添加UNSTRUCTURED_SERVICE_URL环境变量
在/data/projects/JqChatV2/JqChat/R2RV350/.env 中，添加以下行
export UNSTRUCTURED_SERVICE_URL=http://10.1.150.105:8000

### 2、R2RV350/py/r2r/serve.py






在以下两个文件中设置embedding/rerank模型，且embedding的base_dimension要保持一致
/data/projects/JqChatV2/JqChat/R2RV350/py/r2r/r2r.toml 
/data/projects/JqChatV2/JqChat/R2RV350/py/core/configs/full_jq.toml


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