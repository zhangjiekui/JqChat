# test_image_retrieval.py - 测试图片检索
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from embedder_wrapper import Qwen3VLEmbedder
from retriever import DocumentRetriever

os.environ["DASHSCOPE_API_KEY"] = "sk-23e016b5bd774c0f9a6a1bff3804ee20"
DB_CONN = "postgresql://langchain:langchain@10.1.150.105:7000/postgres"

embedder = Qwen3VLEmbedder(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    model="qwen3-vl-embedding",
    dim=1024
)
retriever = DocumentRetriever(DB_CONN, embedder, schema="mmrag")

# 测试 1: search_text_only - 纯文本查询
print("=" * 60)
print("测试 1: search_text_only - 纯文本查询")
print("=" * 60)

results = retriever.search_text_only(
    query_text="安装界面",
    top_k_docs=50,
    top_k_chunks=50
)

print(f"\n查询: '安装界面'")
print(f"找到 {len(results)} 个相关文档")

for r in results[:3]:
    print(f"\n[DOC] {r.title}")
    print(f"分数: {r.overall_score:.4f}")
    for c in r.matched_chunks[:3]:
        print(f"  Chunk {c.chunk_index} (Score: {c.score:.4f})")
        print(f"    文本数: {len(c.text_units)}")
        print(f"    图片数: {len(c.image_urls)}")
        if c.image_urls:
            print(f"    图片列表:")
            for img in c.image_urls:
                print(f"      - {img}")

# 测试 2: search_mixed - 图文混合查询（使用本地图片）
print("\n" + "=" * 60)
print("测试 2: search_mixed - 图文混合查询（本地图片）")
print("=" * 60)

# 使用本地图片（tests 文件夹下的 startup_interface.png）
test_image_local = str(Path(__file__).parent / "startup_interface.png")
print(f"\n使用本地图片: {test_image_local}")

results_mixed = retriever.search_mixed(
    query_text="开始运行界面",
    query_image=test_image_local,
    top_k_docs=5,
    top_k_chunks=5
)

print(f"\n查询: 文本='开始运行界面', 图片=本地文件")
print(f"找到 {len(results_mixed)} 个相关文档:")

for r in results_mixed:
    print(f"\n[DOC] {r.title} (Score: {r.overall_score:.4f})")
    for c in r.matched_chunks:
        print(f"  Chunk {c.chunk_index}: {c.score:.4f}")
        if c.image_urls:
            print(f"    包含图片: {len(c.image_urls)} 张")

# 测试 3: search_mixed - 图文混合查询（使用在线图片）
print("\n" + "=" * 60)
print("测试 3: search_mixed - 图文混合查询（在线图片）")
print("=" * 60)

# 使用在线示例图片（DashScope 提供的测试图片）
test_image_online = "https://dashscope.oss-cn-beijing.aliyuncs.com/images/256_1.png"

results_mixed2 = retriever.search_mixed(
    query_text="动物 狗",
    query_image=test_image_online,
    top_k_docs=5,
    top_k_chunks=5
)

print(f"\n查询: 文本='动物 狗', 图片={test_image_online}")
print(f"找到 {len(results_mixed2)} 个相关文档:")

for r in results_mixed2:
    print(f"\n[DOC] {r.title} (Score: {r.overall_score:.4f})")
    for c in r.matched_chunks:
        print(f"  Chunk {c.chunk_index}: {c.score:.4f}")
        if c.image_urls:
            print(f"    包含图片: {len(c.image_urls)} 张")

# 测试 4: 直接查询数据库中包含图片的 chunks
print("\n" + "=" * 60)
print("测试 4: 查询包含图片的文档")
print("=" * 60)

import psycopg
from pgvector.psycopg import register_vector

with psycopg.connect(DB_CONN) as conn:
    register_vector(conn)
    with conn.cursor() as cur:
        # 查询包含图片的 chunks
        cur.execute("""
            SELECT c.doc_id, d.title, c.chunk_index, c.image_urls
            FROM mmrag.chunks c
            JOIN mmrag.docs d ON c.doc_id = d.doc_id
            WHERE c.doc_id = 'claude_best_pracice'
            AND jsonb_array_length(COALESCE(c.image_urls, '[]')) > 0
            ORDER BY c.chunk_index
        """)

        results = cur.fetchall()
        print(f"\n找到 {len(results)} 个包含图片的 chunks:")

        unique_chunks = {}
        for r in results:
            doc_id, title, chunk_idx, image_urls = r
            if chunk_idx not in unique_chunks:
                unique_chunks[chunk_idx] = (title, image_urls)

        for chunk_idx, (title, image_urls) in sorted(unique_chunks.items()):
            print(f"\n[DOC] {title}")
            print(f"  Chunk {chunk_idx} 包含 {len(image_urls)} 张图片:")
            for img in image_urls:
                print(f"    - {img}")