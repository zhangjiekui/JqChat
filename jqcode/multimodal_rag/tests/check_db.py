# check_db.py - 检查数据库中的 chunks
import psycopg
from pgvector.psycopg import register_vector

DB_CONN = "postgresql://langchain:langchain@10.1.150.105:7000/postgres"

with psycopg.connect(DB_CONN) as conn:
    register_vector(conn)
    with conn.cursor() as cur:
        # 检查有图片的 chunks
        cur.execute("""
            SELECT doc_id, chunk_index, image_urls, metadata
            FROM mmrag.chunks
            WHERE jsonb_array_length(COALESCE(image_urls, '[]')) > 0
            LIMIT 10
        """)

        print("数据库中有图片的 chunks:")
        results = cur.fetchall()
        print(f"找到 {len(results)} 个包含图片的 chunks\n")

        for r in results:
            doc_id, chunk_idx, image_urls, metadata = r
            print(f"Doc: {doc_id}, Chunk: {chunk_idx}")
            print(f"  Images: {image_urls}")
            print(f"  Metadata: {metadata}")
            print()