# indexer.py
import psycopg
from psycopg.types.json import Jsonb
from pgvector.psycopg import register_vector
from typing import List

from embedder_wrapper import Qwen3VLEmbedder, MultimodalInput
from doc_parser import MarkdownParser, ParsedDocument
from db_schema import DatabaseSchema

class DocumentIndexer:
    def __init__(
        self,
        db_conn_string: str,
        embedder: Qwen3VLEmbedder,
        parser: MarkdownParser,
        schema: str = "mmrag",
        base_image_path: str = "./assets"
    ):
        self.db = DatabaseSchema(db_conn_string)
        self.embedder = embedder
        self.parser = parser
        self.schema = schema
        self.base_image_path = base_image_path
        self.instruction = "Retrieve images or text relevant to the user's query."
    
    def index_document(self, file_path: str) -> str:
        """索引单个文档"""
        # 1. 解析文档 → 有序的单元列表
        doc = self.parser.parse_file(file_path, base_image_path=self.base_image_path)
        print(f"[DOC] Parsed: {doc.title} | {len(doc.units)} units")
        
        # 2. 分割成 chunks
        chunks = self.parser.split_to_chunks(
            doc, 
            max_units_per_chunk=10,
            max_text_length=1000
        )
        print(f"[PKG] Split into {len(chunks)} chunks")
        
        # 3. 写入数据库
        with psycopg.connect(self.db.conn_string) as conn:
            register_vector(conn)
            with conn.cursor() as cur:
                # 插入文档元数据
                cur.execute(f"""
                    INSERT INTO {self.schema}.docs (doc_id, title, file_path, total_units, metadata)
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
                    # 编码：多个单元 → 单个向量 ⭐
                    embedding = self.embedder.encode_multimodal_chunk(
                        inputs=chunk_units,
                        instruction=self.instruction,
                        strategy="fusion"
                    )
                    
                    # 提取文本和图片（用于展示）
                    text_units = [u.content for u in chunk_units if u.type == "text"]
                    image_urls = [u.content for u in chunk_units if u.type == "image"]
                    
                    # 保留完整顺序（用于还原）
                    unit_sequence = [
                        {"type": u.type, "content": u.content} 
                        for u in chunk_units
                    ]
                    
                    cur.execute(f"""
                        INSERT INTO {self.schema}.chunks
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
                        Jsonb({
                            "text_count": len(text_units),
                            "image_count": len(image_urls)
                        })
                    ))
                
                conn.commit()
        
        print(f"[OK] Indexed: {doc.doc_id} ({len(chunks)} chunks)")
        return doc.doc_id
    
    def index_directory(self, dir_path: str, pattern: str = "*.md") -> List[str]:
        """索引目录下所有文档"""
        import glob
        from pathlib import Path
        
        files = glob.glob(str(Path(dir_path) / pattern))
        doc_ids = []
        
        for f in files:
            try:
                doc_id = self.index_document(f)
                doc_ids.append(doc_id)
            except Exception as e:
                print(f"[ERROR] Failed to index {f}: {e}")
        
        print(f"[OK] Total indexed: {len(doc_ids)} documents")
        return doc_ids