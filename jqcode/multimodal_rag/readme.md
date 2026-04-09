# 多模态RAG系统

## 概述
处理文档/Chunk/Query 的向量化、存储和检索。

- **输入格式**：有序的文本 + 图片列表 `[{text1}, {img1}, {text2}, {img2}, ...]`
- **输出**：融合向量（文本+图片融合为一个向量）
- **向量模型**：qwen3-vl-embedding（阿里云 DashScope API）
- **向量存储**：PostgreSQL + pgvector

## 架构

```
输入 → 文档解析 → Chunk分割 → 向量化 → 存储
                    ↓
查询 → 向量化 → 向量检索 → 结果返回
```

## 代码结构

| 文件 | 用途 |
|------|------|
| `embedder_wrapper.py` | qwen3-vl-embedding API 封装 |
| `doc_parser.py` | Markdown 解析器（保留顺序） |
| `db_schema.py` | 数据库 Schema |
| `indexer.py` | 文档入库 |
| `retriever.py` | 向量检索 |
| `main.py` | 使用示例 |

## 快速开始

### 1. 安装依赖

```bash
pip install psycopg-binary pgvector dashscope numpy
```

### 2. 配置

修改 `main.py` 中的配置：

```python
os.environ["DASHSCOPE_API_KEY"] = "your-api-key"
DB_CONN = "postgresql://user:pass@host:port/database"
```

### 3. 运行

```bash
python main.py
```

## 数据库 Schema

- **数据库**: PostgreSQL (10.1.150.105:7000)
- **Schema**: mmrag
- **表**:
  - `mmrag.docs` - 文档元数据
  - `mmrag.chunks` - Chunk 数据（含向量）

## 测试结果

- 文本检索: 相似度 ~0.69
- 混合检索: 相似度 ~0.59
- 图片检索: 需降低阈值 (min_similarity=0.05)

## 待办

- [ ] 编写单元测试
- [ ] 添加更多测试文档（含图片）
- [ ] 适配 vllm 自部署 API