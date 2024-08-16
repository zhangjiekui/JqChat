## 参考文档
#### https://github.com/chatchat-space/Langchain-Chatchat/tree/master
#### https://github.com/chatchat-space/Langchain-Chatchat/blob/master/libs/chatchat-server/README.md

## 创建新的虚拟环境
chatchat请放在独立的虚拟环境中，比如conda，venv，virtualenv等。已知问题，不能跟xf一起安装，会让一些插件出bug，例如文件无法上传
```
cd ~/.virtualenvs
virtualenv chatlc
workon chatlc
```
## 安装
```
pip install "langchain-chatchat[xinference]" -U
```
## Xinference模型服务
在Xinference加载运行以下模型服务
#### qwen2-instruct
#### bce-embedding-base_v1
#### bce-reranker-base_v1

## Xinference接口配置

```
chatchat-config model --set_model_platforms "[{
    \"platform_name\": \"xinference\",
    \"platform_type\": \"xinference\",
    \"api_base_url\": \"http://10.1.150.105:9997/v1\",
    \"api_key\": \"EMPT\",
    \"api_concurrencies\": 5,
    \"llm_models\": [
        \"qwen2-instruct\"
    ],
    \"embed_models\": [
        \"bce-embedding-base_v1\"
    ],
    \"image_models\": [],
    \"reranking_models\": [ \"bce-reranker-base_v1\"
],
    \"speech2text_models\": [],
    \"tts_models\": []
}]"
```
```
chatchat-config model --default_embedding_model bce-embedding-base_v1
chatchat-config model --default_llm_model qwen2-instruct

```

## 配置ElasticSearch
#### 安装对应版本的elasticsearch及必要的包
```
pip install elasticsearch==8.14.0
pip install transformers
```
#### 修改配置文件
/root/.virtualenvs/chatlc/lib/python3.10/site-packages/chatchat/configs/_kb_config.py
以下是修改后的内容，保存到【_kb_config.py】文件中了，以后可复制、黏贴或替换。
使用命令查看是否生效： chatchat-config kb --show
#### 修改es连接文件：es_kb_service.py
/root/.virtualenvs/chatlc/lib/python3.10/site-packages/chatchat/server/knowledge_base/kb_service/es_kb_service.py
以下是修改后的内容，保存到【es_kb_service.py】文件中了，以后可复制、黏贴或替换。
#### 初始化es知识库
chatchat-kb -r --embed-model=bce-embedding-base_v1

## 运行Chatchat
#### 修改服务绑定IP
```
chatchat-config server --default_bind_host=0.0.0.0
```
#### 启动Chatchat
```
chatchat -a
```

#### 访问Chatchat
```
http://10.1.150.105:8501/
```

