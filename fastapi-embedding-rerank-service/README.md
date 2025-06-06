# FastAPI Embedding Service

这是一个基于 FastAPI 的嵌入服务，提供生成文本嵌入的 API。

## 项目结构

- `src/server/main.py`: FastAPI 应用的入口点，初始化应用，加载模型，并定义生成嵌入的 API 端点。
- `src/server/models.py`: 包含用于验证嵌入 API 请求和响应数据的 Pydantic 模型 `EmbeddingRequest` 和 `EmbeddingResponse`。
- `src/server/config.py`: 包含应用的配置设置，例如加载环境变量和其他必要的配置。
- `src/client/test_client.py`: 一个简单的客户端实现，向 FastAPI 服务发送请求以测试嵌入功能。
- `requirements.txt`: 列出项目所需的依赖项，包括 FastAPI、Pydantic 和其他必要的库。
- `README.md`: 项目的文档，包括如何设置和运行服务的说明，以及如何使用客户端进行测试。
- `.env`: 用于存储应用可能需要的环境变量，例如 API 密钥或模型路径。

## 安装依赖

在项目根目录下运行以下命令以安装依赖：

```
pip install -r requirements.txt
```

## 运行服务

在 `src/server` 目录下运行以下命令以启动 FastAPI 服务：

```
uvicorn main:app --reload
```

## 测试客户端

在 `src/client` 目录下运行以下命令以测试嵌入功能：

```
python test_client.py
``` 

请根据需要修改 `.env` 文件以配置环境变量。