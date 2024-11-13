import io, logging, asyncio, zipfile
from pathlib import Path
from typing import Dict, Any,List
from joblib import Parallel, delayed
from datetime import datetime  
from typing import List
from fastapi import FastAPI, UploadFile, File, HTTPException,Form
from fastapi.responses import FileResponse, StreamingResponse
from utils import process_single_file

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="PDF转DOCX服务")


@app.post("/convert/batch/")
async def convert_pdfs(files: List[UploadFile] = File(...)):
    """
    批量上传PDF文件并转换为DOCX格式
    """
    if not files:
        raise HTTPException(status_code=400, detail="请上传至少一个文件")

    async def process_file(file: UploadFile) -> Dict[str, Any]:
        try:
            if not file.filename.lower().endswith('.pdf'):
                return {
                    "filename": file.filename,
                    "success": False,
                    "message": "不是PDF格式文件",
                    "docx_path": None
                }
            
            # 读取文件内容
            pdf_bytes = await file.read()
            pdf_filename = Path(file.filename)
            
            # 使用已有的process_single_file处理
            result = await process_single_file(pdf_bytes, pdf_filename)
            result["filename"] = file.filename  # 添加原始文件名到结果中
            
            return result
            
        except Exception as e:
            logger.error(f"处理文件 {file.filename} 时发生错误: {str(e)}")
            return {
                "filename": file.filename,
                "success": False,
                "message": f"处理失败: {str(e)}",
                "docx_path": None
            }

    # 并行处理所有文件
    tasks = [process_file(file) for file in files]
    results = await asyncio.gather(*tasks)
    
    # 统计成功和失败数量
    success_count = sum(1 for r in results if r["success"])
    fail_count = len(results) - success_count
    
    return {
        "total": len(results),
        "success_count": success_count,
        "fail_count": fail_count,
        "results": results
    }


@app.post("/convert/")
async def convert_pdf(file: UploadFile = File(...)):
    """上传PDF文件并转换为DOCX格式"""
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="请上传PDF格式的文件")
    
    # 读取文件内容
    pdf_bytes = await file.read()
    
    # 将文件名转换为Path对象
    pdf_filename = Path(file.filename)

    # 处理文件
    result = await process_single_file(pdf_bytes, pdf_filename)

    
    if result["success"]:
        return {
            "success": True,
            "message": result["message"],
            "docx_file_path": result["docx_path"],
            # "ocr_result": result.get("ocr_result", None),
            # "result": result
        }
    else:
        raise HTTPException(status_code=500, detail=result["message"])


@app.get("/download/{file_path:path}")
async def download_file(file_path: str):
    """
    下载转换后的DOCX文件
    
    Args:
        file_path: DOCX文件的相对路径
    """
    try:
        # 构建完整的文件路径
        full_path = Path(file_path)
        
        # 检查文件是否存在
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="文件不存在")
        
        # 检查文件扩展名
        if not str(full_path).lower().endswith('.docx'):
            raise HTTPException(status_code=400, detail="只能下载DOCX格式的文件")
        
        # 获取文件名
        filename = full_path.name
        
        # 返回文件响应
        return FileResponse(
            path=full_path,
            filename=filename,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        
    except Exception as e:
        logger.error(f"下载文件时发生错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"下载文件时发生错误: {str(e)}")
    


@app.post("/download/batch/")
async def download_batch(file_paths: List[str]):
    """
    批量下载多个DOCX文件，将文件打包成zip返回
    """
    try:
        # 创建内存中的zip文件
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for file_path in file_paths:
                full_path = Path(file_path)
                
                # 验证文件
                if not full_path.exists():
                    continue
                if not str(full_path).lower().endswith('.docx'):
                    continue
                
                # 将文件添加到zip
                zip_file.write(full_path, full_path.name)
        
        # 将zip_buffer的指针移到开始
        zip_buffer.seek(0)
        
        # 生成下载文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = f"converted_docs_{timestamp}.zip"
        
        # 返回zip文件
        return StreamingResponse(
            io.BytesIO(zip_buffer.getvalue()),
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename={zip_filename}"
            }
        )
        
    except Exception as e:
        logger.error(f"创建批量下载zip文件时发生错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"批量下载文件时发生错误: {str(e)}")

    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

