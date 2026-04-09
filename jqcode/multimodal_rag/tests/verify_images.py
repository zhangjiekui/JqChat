# verify_images.py - 直接验证图片在 chunks 中
import psycopg
from pgvector.psycopg import register_vector
import os

DB_CONN = "postgresql://langchain:langchain@10.1.150.105:7000/postgres"

with psycopg.connect(DB_CONN) as conn:
    register_vector(conn)
    with conn.cursor() as cur:
        # 查看所有 chunks 的图片情况
        cur.execute("""
            SELECT doc_id, chunk_index, image_urls, unit_sequence
            FROM mmrag.chunks
            WHERE doc_id = 'claude_best_pracice'
            ORDER BY chunk_index
        """)

        print("=" * 60)
        print("所有 chunks 的图片情况:")
        print("=" * 60)

        results = cur.fetchall()
        total_images = 0

        for r in results:
            doc_id, chunk_idx, image_urls, unit_sequence = r
            img_count = len(image_urls) if image_urls else 0
            total_images += img_count

            if img_count > 0:
                print(f"\n[Chunk {chunk_idx}] 有 {img_count} 张图片:")
                for img in image_urls:
                    print(f"    IMG: {img}")

                # 打印 unit_sequence 中的顺序
                print(f"    单元顺序 (type): ", end="")
                for u in unit_sequence[:10]:
                    print(f"{u['type']} ", end="")
                print()

        print(f"\n总计: {total_images} 张图片")

        # 验证解析器识别了多少图片
        print("\n" + "=" * 60)
        print("对比: 解析器识别的图片:")
        print("=" * 60)
        from doc_parser import MarkdownParser
        parser = MarkdownParser()
        doc = parser.parse_file("D:/claude_best_practice/claude_best_pracice.md", base_image_path="D:/claude_best_practice")
        print(f"解析器识别: {doc.metadata['image_units']} 张图片")
        print(f"数据库存储: {total_images} 张图片")