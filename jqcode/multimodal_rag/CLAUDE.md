# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Multimodal RAG system - 处理文档/Chunk/Query 的向量化、存储和检索。

- **输入格式**：有序的文本 + 图片列表 `[{text1}, {img1}, {text2}, {text3}, {img2}, ...]`
- **输出**：无论输入多少个元素，只输出一个向量表示整体语义
- **向量模型**：qwen3_vl_embedding（计划通过 vllm/sglang 部署，使用 API 方式调用）
- **向量存储**：PostgreSQL + pgvector

## Code Structure

| File | Purpose |
|------|---------|
| `embedder_wrapper.py` | Qwen3-VL Embedder（API 方式） |
| `doc_parser.py` | 文档解析器（保留顺序） |
| `db_schema.py` | 数据库 Schema（单向量设计） |
| `indexer.py` | 文档入库 |
| `retriever.py` | 检索 |
| `main.py` | 使用示例 |
| `qwen3_vl_embedder_examples/` | 官方示例代码 |

## Development Commands

```bash
# Install dependencies
pip install psycopg pgvector dashscope numpy

# Run example
python main.py
```

## Environment Variables

- `DASHSCOPE_API_KEY`: Alibaba Cloud DashScope API key
- Database connection: `postgresql://postgres:postgres@localhost:5432/multimodal_rag`

## Current Status

项目处于初始实现阶段，以下问题待确定：
1. qwen3_vl_embedding 是否支持多元素输入 `{text, image, text, image}` 还是只支持单个 `{text, image}` 对
2. 存储设计：存储一个 chunk 还是分开存储（文本存 PG，图片用文件存储）

如需扩展功能，建议先搜索相关资料确认上述问题。