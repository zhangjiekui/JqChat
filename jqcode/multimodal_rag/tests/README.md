# 多模态 RAG 系统测试说明

本目录包含多模态 RAG 系统的测试文件，用于验证各模块功能。

## 测试文件列表

| 文件 | 功能 | 测试场景 |
|------|------|----------|
| `test_full_flow.py` | 完整流程测试 | 端到端测试：解析 → 向量化 → 存储 → 检索 |
| `check_images.py` | 图片解析测试 | 验证 Markdown 解析器能正确识别图片 |
| `check_db.py` | 数据库存储测试 | 验证图片数据正确写入数据库 |
| `verify_images.py` | 数据一致性验证 | 验证解析器识别数量与数据库存储数量一致 |
| `test_image_retrieval.py` | 图片检索测试 | 验证语义检索能返回包含图片的 chunks |

## 运行测试

### 1. 完整流程测试（推荐首次运行）

```bash
python test_full_flow.py
```

测试内容：
- 解析 Markdown 文件，识别文本和图片单元
- 使用 qwen3-vl-embedding 生成向量
- 写入 PostgreSQL + pgvector
- 执行语义检索并展示结果

### 2. 单独模块测试

```bash
# 验证图片解析
python check_images.py

# 验证数据库存储
python check_db.py

# 验证数据一致性
python verify_images.py

# 验证图片检索
python test_image_retrieval.py
```

## 测试数据

- 测试文件: `D:/claude_best_practice/claude_best_pracice.md`
- 文档信息:
  - 总单元数: 287
  - 文本单元: 281
  - 图片单元: 6
  - 分割 chunks: 36

## 数据库配置

连接字符串: `postgresql://langchain:langchain@10.1.150.105:7000/postgres`

Schema: `mmrag`

表:
- `mmrag.docs` - 文档元数据
- `mmrag.chunks` - 文档片段（包含向量）

## 注意事项

1. 确保 PostgreSQL + pgvector 已启动
2. 确保 DASHSCOPE_API_KEY 环境变量已设置
3. 部分测试会写入数据库，建议先备份或清理测试数据