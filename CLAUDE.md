# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

JqChat 是一个基于 Agent 的 RAG（检索增强生成）聊天系统，集成了代码解释器功能。核心架构使用 LangGraph 构建状态机驱动的 AI Agent，支持知识库检索、Web 搜索、代码执行等工具调用。

## 核心架构

### 主要模块

- **jqcode/langgraph_in_class.py** - 核心 Agent 状态机，基于 LangGraph 实现，包含问题重写、工具路由、代码执行等节点
- **jqcode/jq_mcp/** - MCP (Model Context Protocol) 服务，提供 OpenAI 兼容的 API 接口
- **jqcode/jq_agent/** - Agent 相关组件，包括环境配置、工具定义
- **jqcode/jq_code_executor/** - 代码执行器，支持沙箱执行 Python 代码
- **jqcode/jq_docstores/** - 文档存储抽象层，支持 Elasticsearch 等后端
- **jqcode/jq_kb_manegement/** - 知识库管理模块
- **jqcode/r2r_client_functions.py** - R2R (Read, Reason, Respond) 客户端封装
- **JqR2R/** - R2R 服务本地副本，用于检索和知识库管理
- **jqweb/** - Streamlit Web UI

### 技术栈

- **LLM 框架**: LangChain, LangGraph
- **向量检索**: Elasticsearch, R2R
- **图数据库**: Neo4j, TuGraph (可选)
- **API 服务**: FastAPI, Flask
- **前端**: Streamlit
- **消息队列**: Snakemq (用于前后端通信)

## 运行服务

### 启动 Web UI

```bash
streamlit run jqweb/webui.py
```

### 启动 API 服务

```bash
uvicorn jqcode.jq_mcp.jq_openai_service_api_streaming:app --host 0.1.150.105 --port 5000 --reload
```

### 环境变量配置

配置在 `.env` 文件中，关键变量：

- `LLM_MODEL_CARD` - 主 LLM 配置（名称、base_url、api_key 等）
- `CODE_MODEL_CARD` - 代码生成模型配置
- `VLM_MODEL_CARD` - 视觉语言模型配置
- `EMBEDDING_MODEL_CARD` - 嵌入模型配置
- `RERANK_MODEL_CARD` - 重排序模型配置
- `ES_URL` - Elasticsearch 连接地址
- `NEO4J_URI` - Neo4j 图数据库连接

## 开发要点

### 1. 模型配置

所有模型通过 `jqcode/jq_agent/c0_init_env_models.py` 中的 `env_models_instance` 统一管理，支持：
- 本地部署的 vLLM/SGLang 服务
- 远程 API 服务（OpenAI、Anthropic 兼容接口）

### 2. Agent 状态机

核心状态定义在 `GraphAgentState` (TypedDict)，包含：
- `messages`: 对话消息历史
- `question`: 当前问题
- `documents`: 检索到的文档
- `user_variables`: 用户相关临时变量

### 3. 工具系统

工具定义在 `jqcode/jq_agent/tools/` 目录下：
- `jq_functions_and_tools.py` - 自定义函数工具
- `jq_retriever.py` - 知识库检索工具
- `jq_web_search_engine.py` - Web 搜索工具（Tavily）

### 4. 知识库管理

- 使用 Elasticsearch 作为元数据存储 (`JqElasticsearchUniMetaStore`)
- 支持通过 R2R 客户端进行文档检索和向量搜索
- 知识库元数据包括：index_name, description 等

### 5. 代码执行

- 支持本地执行和 E2B 沙箱执行
- 通过 `CodeExecutorTool` 集成到 Agent 工具链

## 调试技巧

### 查看 Agent 执行流程

```python
from jqcode.langgraph_in_class import GraphAgent
agent = GraphAgent()
agent.graph.draw_mermaid("agent_flow.mmd")
```

### 启用 LangSmith 追踪

设置环境变量：
```
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_key
LANGCHAIN_PROJECT=JqChat
```

### 日志配置

项目使用自定义日志系统 `jqcode.jq_utils.logger.jqkj_logger`，日志输出到指定目录。

## 依赖管理

- 主依赖：`requirements.txt`
- R2R 依赖：`JqR2R/py/requirements.txt`
- 多模态 RAG 依赖：`jqcode/multimodal_rag/requirements.txt`

## 测试

R2R 服务测试位于 `JqR2R/py/tests/`：
- 单元测试：`JqR2R/py/tests/unit/`
- 集成测试：`JqR2R/py/tests/integration/`

## 数据库

- **Elasticsearch**: 向量检索和元数据存储
- **PostgreSQL**: LangGraph 检查点存储
- **Neo4j/TuGraph**: 知识图谱存储（可选）

连接配置见 `.env` 文件中的 `ES_URL`, `POSTGRES_*`, `NEO4J_*` 等变量。
