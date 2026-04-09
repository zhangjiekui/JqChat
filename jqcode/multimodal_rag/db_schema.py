# db_schema.py
import psycopg
from pgvector.psycopg import register_vector

class DatabaseSchema:
    def __init__(self, conn_string: str):
        self.conn_string = conn_string
    
    def _get_conn(self):
        conn = psycopg.connect(self.conn_string)
        register_vector(conn)
        return conn
    
    def init_schema(self, embedding_dim: int = 1024, schema: str = "mmrag"):
        """
        初始化数据库 - 单向量设计
        每个 chunk 只用一个向量表示
        """
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

                # 文档整体索引
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {schema}.docs (
                        doc_id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        file_path TEXT,
                        total_units INTEGER,
                        metadata JSONB,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    );
                """)

                # Chunk 索引 - 每个 chunk 一个向量 ⭐
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {schema}.chunks (
                        id SERIAL PRIMARY KEY,
                        doc_id TEXT NOT NULL REFERENCES {schema}.docs(doc_id),
                        chunk_index INTEGER,
                        embedding vector({embedding_dim}),
                        unit_count INTEGER,
                        text_units JSONB,
                        image_urls JSONB,
                        unit_sequence JSONB,
                        metadata JSONB,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    );
                """)
                
                # 索引
                cur.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_chunk_embedding
                    ON {schema}.chunks USING hnsw (embedding vector_cosine_ops);
                """)

                cur.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_chunk_doc_id
                    ON {schema}.chunks (doc_id);
                """)
                
                conn.commit()
        
        print(f"[OK] Database schema initialized (dim={embedding_dim})")