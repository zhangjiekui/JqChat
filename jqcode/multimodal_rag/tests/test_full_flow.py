# test_full_flow.py
import os
import sys
from pathlib import Path

# 将项目根目录添加到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from embedder_wrapper import Qwen3VLEmbedder
from doc_parser import MarkdownParser
from indexer import DocumentIndexer
from retriever import DocumentRetriever

# 配置
os.environ["DASHSCOPE_API_KEY"] = "sk-23e016b5bd774c0f9a6a1bff3804ee20"
DB_CONN = "postgresql://langchain:langchain@10.1.150.105:7000/postgres"

def main():
    # 初始化组件
    embedder = Qwen3VLEmbedder(
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        model="qwen3-vl-embedding",
        dim=1024
    )

    parser = MarkdownParser()
    indexer = DocumentIndexer(DB_CONN, embedder, parser, schema="mmrag", base_image_path="./assets")
    retriever = DocumentRetriever(DB_CONN, embedder, schema="mmrag")

    # 初始化数据库
    indexer.db.init_schema(embedding_dim=embedder.dim, schema="mmrag")

    # ====== 1. 解析测试 ======
    test_file = "D:/claude_best_practice/claude_best_pracice.md"
    doc = parser.parse_file(test_file, base_image_path="D:/claude_best_practice")

    print("\n" + "="*60)
    print("1. 文档解析结果")
    print("="*60)
    print(f"文档 ID: {doc.doc_id}")
    print(f"标题: {doc.title}")
    print(f"总单元数: {len(doc.units)}")
    print(f"文本单元数: {doc.metadata['text_units']}")
    print(f"图片单元数: {doc.metadata['image_units']}")

    # 展示前 3 个单元
    print("\n前 3 个单元示例:")
    for i, unit in enumerate(doc.units[:3]):
        if unit.type == "text":
            print(f"  [{i}] TEXT: {unit.content[:60]}...")
        else:
            print(f"  [{i}] IMAGE: {unit.content}")

    # ====== 2. 索引到数据库 ======
    print("\n" + "="*60)
    print("2. 索引文档到数据库")
    print("="*60)

    # 直接调用 indexer 的逻辑，但用我们的测试文件
    chunks = parser.split_to_chunks(doc, max_units_per_chunk=10, max_text_length=1000)
    print(f"分割成 {len(chunks)} 个 chunks")

    # 写入数据库
    import psycopg
    from psycopg.types.json import Jsonb
    from pgvector.psycopg import register_vector

    with psycopg.connect(DB_CONN) as conn:
        register_vector(conn)
        with conn.cursor() as cur:
            # 插入文档元数据
            cur.execute(f"""
                INSERT INTO mmrag.docs (doc_id, title, file_path, total_units, metadata)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (doc_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    total_units = EXCLUDED.total_units,
                    metadata = EXCLUDED.metadata
            """, (
                doc.doc_id,
                doc.title,
                doc.file_path,
                len(doc.units),
                Jsonb(doc.metadata)
            ))

            # 插入每个 chunk
            for chunk_idx, chunk_units in enumerate(chunks):
                # 向量化
                embedding = embedder.encode_multimodal_chunk(
                    inputs=chunk_units,
                    instruction="Retrieve relevant content.",
                    strategy="fusion"
                )

                # 提取文本和图片
                text_units = [u.content for u in chunk_units if u.type == "text"]
                image_urls = [u.content for u in chunk_units if u.type == "image"]
                unit_sequence = [{"type": u.type, "content": u.content[:100]} for u in chunk_units]

                cur.execute(f"""
                    INSERT INTO mmrag.chunks
                    (doc_id, chunk_index, embedding, unit_count,
                     text_units, image_urls, unit_sequence, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    doc.doc_id,
                    chunk_idx,
                    embedding,
                    len(chunk_units),
                    Jsonb(text_units),
                    Jsonb(image_urls),
                    Jsonb(unit_sequence),
                    Jsonb({"text_count": len(text_units), "image_count": len(image_urls)})
                ))

                print(f"  Chunk {chunk_idx}: {len(chunk_units)} units indexed")

            conn.commit()

    print(f"\n[OK] 文档已索引: {doc.doc_id} ({len(chunks)} chunks)")

    # ====== 3. 检索测试 ======
    print("\n" + "="*60)
    print("3. 检索测试")
    print("="*60)

    # 测试纯文本检索
    results = retriever.search_text_only(
        query_text="Claude Code 安装步骤",
        top_k_docs=3,
        top_k_chunks=3
    )

    print(f"\n查询: 'Claude Code 安装步骤'")
    print(f"找到 {len(results)} 个相关文档:")

    for r in results:
        print(f"\n[DOC] {r.title} (Score: {r.overall_score:.4f})")
        print(f"  文件: {r.file_path}")
        for c in r.matched_chunks:
            print(f"  Chunk {c.chunk_index}: {c.score:.4f}")
            if c.text_units:
                print(f"    文本: {c.text_units[0][:80]}...")

    # 测试中文查询
    print("\n" + "-"*40)
    results2 = retriever.search_text_only(
        query_text="模型切换",
        top_k_docs=3,
        top_k_chunks=3
    )

    print(f"\n查询: '模型切换'")
    print(f"找到 {len(results2)} 个相关文档:")

    for r in results2:
        print(f"\n[DOC] {r.title} (Score: {r.overall_score:.4f})")
        for c in r.matched_chunks:
            print(f"  Chunk {c.chunk_index}: {c.score:.4f}")

    print("\n" + "="*60)
    print("测试完成!")
    print("="*60)

if __name__ == "__main__":
    main()