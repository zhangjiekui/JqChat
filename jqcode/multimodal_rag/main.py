# main.py
import os
from embedder_wrapper import Qwen3VLEmbedder
from doc_parser import MarkdownParser
from indexer import DocumentIndexer
from retriever import DocumentRetriever

# 配置
os.environ["DASHSCOPE_API_KEY"] = "sk-23e016b5bd774c0f9a6a1bff3804ee20"
DB_CONN = "postgresql://langchain:langchain@10.1.150.105:7000/postgres"

def main():
    # 初始化
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
    
    # 索引文档
    indexer.index_directory("./docs", pattern="*.md")
    
    # ========== 检索示例 ==========
    
    # 示例 1: 纯文本查询
    print("\n--- Text-only Query ---")
    results = retriever.search_text_only(
        query_text="如何训练狗狗",
        top_k_docs=3,
        top_k_chunks=3
    )
    for r in results:
        print(f"\n[DOC] {r.title} (Score: {r.overall_score:.4f})")
        for c in r.matched_chunks:
            print(f"   Chunk {c.chunk_index}: {c.score:.4f}")
            if c.text_units:
                print(f"   Text: {c.text_units[0][:80]}...")
            if c.image_urls:
                print(f"   Images: {len(c.image_urls)} images")
    
    # 示例 2: 纯图片查询 (使用有效的示例图片)
    print("\n--- Image-only Query ---")
    results = retriever.search_image_only(
        query_image="https://dashscope.oss-cn-beijing.aliyuncs.com/images/256_1.png",
        top_k_docs=3
    )
    for r in results:
        print(f"\n[DOC] {r.title} (Score: {r.overall_score:.4f})")

    # 示例 3: 多文本 + 多图片混合查询 (使用有效的示例图片)
    print("\n--- Mixed Query (Ordered) ---")
    results = retriever.search(
        query_texts=[
            "狗狗训练基础",
            "训练技巧",
            "奖励机制"
        ],
        query_images=[
            "https://dashscope.oss-cn-beijing.aliyuncs.com/images/256_1.png"
        ],
        top_k_docs=3,
        top_k_chunks=5
    )
    for r in results:
        print(f"\n[DOC] {r.title} (Score: {r.overall_score:.4f})")
        for c in r.matched_chunks:
            print(f"   Chunk {c.chunk_index}: {c.score:.4f}")
            # 还原原始顺序
            print(f"   Sequence: {c.unit_sequence[:3]}...")  # 显示前 3 个单元

if __name__ == "__main__":
    main()