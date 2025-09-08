from jqcode.jq_readers.backend_reader_utils.jqkj_docs_converter import *

from r2r import R2RProviders

import os, io, logging, asyncio, zipfile,tempfile,shutil,requests
from io import BytesIO
from uuid import UUID
from pathlib import Path
from typing import Dict, Any,List, Optional
from joblib import Parallel, delayed
from datetime import datetime  
from typing import List
from fastapi import FastAPI, UploadFile, File, HTTPException,Form,Depends
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import Json
from core.base import (
    IngestionConfig,
    IngestionMode,
    R2RException,
    SearchMode,
    SearchSettings,
    UnprocessedChunk,
    Workflow,
    generate_document_id,
    generate_id,
    select_search_filters,
)
from core.base.api.models import (
    GenericBooleanResponse,
    WrappedBooleanResponse,
    WrappedChunksResponse,
    WrappedCollectionsResponse,
    WrappedDocumentResponse,
    WrappedDocumentSearchResponse,
    WrappedDocumentsResponse,
    WrappedEntitiesResponse,
    WrappedGenericMessageResponse,
    WrappedIngestionResponse,
    WrappedRelationshipsResponse,
)

# from utils import process_single_file, convert_pdf_to_docx,check_pdf_type
from utils import process_single_file,docx_path_to_content

from concurrent.futures import ThreadPoolExecutor

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="R2R文件转换及上传服务")

MAX_WORKERS = 8


converted_file_types = [".pdf",".doc",".md",".html",".htm"]

import psycopg2
from psycopg2 import sql

def read_file_as_bytes(file_path: str) -> bytes:
    with open(file_path, 'rb') as f:
        return f.read()
def save_file_to_db(file_path: str, filename: str = None):
    # 读取二进制数据
    binary_data = read_file_as_bytes(file_path)
    if filename is None:
        filename = file_path.split('/')[-1]

    # 推断 MIME 类型（可选）
    import mimetypes
    file_type, _ = mimetypes.guess_type(file_path)
    file_type = file_type or 'application/octet-stream'

    # 连接数据库
    conn = psycopg2.connect(
        host="localhost",
        database="your_db",
        user="your_user",
        password="your_password"
    )
    cur = conn.cursor()

    # 插入数据
    insert_query = sql.SQL("""
        INSERT INTO files (filename, file_type, data)
        VALUES (%s, %s, %s)
    """)
    cur.execute(insert_query, (filename, file_type, binary_data))

    # 提交并关闭
    conn.commit()
    cur.close()
    conn.close()
    print(f"✅ 文件 {filename} 已成功存入数据库")
def save_binary_data_to_file(data: bytes, file_path: str):
    """
    将二进制数据保存为文件
    :param data: 二进制数据（bytes）
    :param file_path: 保存的文件路径（包含扩展名）
    """
    with open(file_path, 'wb') as f:
        f.write(data)
    print(f"文件已保存至: {file_path}")
    return file_path
@app.post("/upload_files/")
async def upload_files(files: List[UploadFile] = File(...),
                       id: Optional[UUID] = Form(
                            None,
                            description="The ID of the document. If not provided, a new ID will be generated.",
                        ),
                        collection_ids: Optional[Json[list[UUID]]] = Form(
                            None,
                            description="Collection IDs to associate with the document. If none are provided, the document will be assigned to the user's default collection.",
                        ),
                        metadata: Optional[Json[dict]] = Form(
                            None,
                            description="Metadata to associate with the document, such as title, description, or custom fields.",
                        ),
                        ingestion_mode: IngestionMode = Form(
                            default=IngestionMode.custom,
                            description=(
                                "Ingestion modes:\n"
                                "- `hi-res`: Thorough ingestion with full summaries and enrichment.\n"
                                "- `fast`: Quick ingestion with minimal enrichment and no summaries.\n"
                                "- `custom`: Full control via `ingestion_config`.\n\n"
                                "If `filters` or `limit` (in `ingestion_config`) are provided alongside `hi-res` or `fast`, "
                                "they will override the default settings for that mode."
                            ),
                        ),
                        ingestion_config: Optional[Json[IngestionConfig]] = Form(
                            None,
                            description="An optional dictionary to override the default chunking configuration for the ingestion process. If not provided, the system will use the default server-side chunking configuration.",
                        ),
                        run_with_orchestration: Optional[bool] = Form(
                            True,
                            description="Whether or not ingestion runs with orchestration, default is `True`. When set to `False`, the ingestion process will run synchronous and directly return the result.",
                        ),
                        auth_user=Depends(R2RProviders.auth.auth_wrapper()),
                    ) -> WrappedIngestionResponse:
    if not files:
        raise HTTPException(status_code=400, detail="请上传至少一个文件")
   
    for file in files:
        filename = file.filename
        file_ext = file.filename.split(".")[-1]
        if file_ext.lower() in converted_file_types:
            # 存储文件到数据库 返回oid
            
            saved_file = save_binary_data_to_file(file, f"{filename}")
            final_input_filepaths_exist,final_input_filepaths_exist_and_replaced_by_docx_if_converted = batch_convert_files_to_docxs([saved_file])
            
            
            # 转换后的新文件，metadata= {"filename": filename, "oid": oid} 



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

    # /data/projects/JqChatV2/JqChat/JqR2R/py/core/main/api/v3/documents_router.py

