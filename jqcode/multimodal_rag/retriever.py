# retriever.py
import psycopg
from pgvector.psycopg import register_vector
from typing import List, Optional
from dataclasses import dataclass

from embedder_wrapper import Qwen3VLEmbedder

@dataclass
class ChunkResult:
    doc_id: str
    chunk_index: int
    text_units: List[str]
    image_urls: List[str]
    unit_sequence: List[dict]  # 保留顺序
    score: float

@dataclass
class DocumentResult:
    doc_id: str
    title: str
    overall_score: float
    matched_chunks: List[ChunkResult]
    file_path: str

class DocumentRetriever:
    def __init__(
        self,
        db_conn_string: str,
        embedder: Qwen3VLEmbedder,
        schema: str = "mmrag"
    ):
        self.db_conn_string = db_conn_string
        self.embedder = embedder
        self.schema = schema
        self.instruction = "Retrieve images or text relevant to the user's query."
    
    def search(
        self,
        query_texts: List[str],
        query_images: List[str],
        top_k_docs: int = 10,
        top_k_chunks: int = 5,
        min_similarity: float = 0.5
    ) -> List[DocumentResult]:
        """
        检索：query 也是多文本 + 多图片 → 单个向量
        """
        # 1. 编码查询 → 单个向量 ⭐
        query_embedding = self.embedder.encode_query(
            texts=query_texts,
            images=query_images,
            preserve_order=True,
            instruction=self.instruction
        )
        
        # 2. 向量检索
        with psycopg.connect(self.db_conn_string) as conn:
            register_vector(conn)
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT
                        c.doc_id,
                        d.title,
                        d.file_path,
                        c.chunk_index,
                        c.text_units,
                        c.image_urls,
                        c.unit_sequence,
                        1 - (c.embedding <=> %s) AS similarity
                    FROM {self.schema}.chunks c
                    JOIN {self.schema}.docs d ON c.doc_id = d.doc_id
                    WHERE 1 - (c.embedding <=> %s) >= %s
                    ORDER BY c.embedding <=> %s
                    LIMIT %s;
                """, (
                    query_embedding,
                    query_embedding,
                    min_similarity,
                    query_embedding,
                    top_k_docs * top_k_chunks
                ))
                
                results = cur.fetchall()
        
        # 3. 按文档聚合
        from collections import defaultdict
        doc_chunks = defaultdict(list)
        doc_info = {}
        
        for r in results:
            doc_id, title, file_path, chunk_idx, text_units, image_urls, unit_seq, score = r
            doc_info[doc_id] = {"title": title, "file_path": file_path}
            
            doc_chunks[doc_id].append(ChunkResult(
                doc_id=doc_id,
                chunk_index=chunk_idx,
                text_units=text_units or [],
                image_urls=image_urls or [],
                unit_sequence=unit_seq or [],
                score=score
            ))
        
        # 4. 构建最终结果
        final_results = []
        for doc_id, chunks in doc_chunks.items():
            # 按 chunk 分数排序，取 top_k
            sorted_chunks = sorted(chunks, key=lambda x: x.score, reverse=True)[:top_k_chunks]
            
            # 文档整体分数 = 最高 chunk 分数
            overall_score = max(c.score for c in sorted_chunks)
            
            final_results.append(DocumentResult(
                doc_id=doc_id,
                title=doc_info[doc_id]["title"],
                overall_score=overall_score,
                matched_chunks=sorted_chunks,
                file_path=doc_info[doc_id]["file_path"]
            ))
        
        # 按文档分数排序
        final_results.sort(key=lambda x: x.overall_score, reverse=True)
        return final_results[:top_k_docs]
    
    def search_text_only(self, query_text: str, **kwargs) -> List[DocumentResult]:
        """纯文本查询"""
        return self.search(query_texts=[query_text], query_images=[], **kwargs)
    
    def search_image_only(self, query_image: str, **kwargs) -> List[DocumentResult]:
        """纯图片查询"""
        return self.search(query_texts=[], query_images=[query_image], **kwargs)
    
    def search_mixed(self, query_text: str, query_image: str, **kwargs) -> List[DocumentResult]:
        """图文混合查询"""
        return self.search(query_texts=[query_text], query_images=[query_image], **kwargs)