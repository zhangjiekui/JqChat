import asyncio, zipfile
from io import BytesIO
from pathlib import Path
from typing import Dict, Any,List
from joblib import Parallel, delayed
from datetime import datetime  
from typing import List
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from loguru import logger
from utils import convert_file_to_docx,ACCEPT_FILE_TYPES,PORT

app = FastAPI(title="PDF|DOC|MD|HTM|HTML 转 DOCX服务")
MAX_WORKERS = 8

@app.post("/convert/batch/")
async def convert_files(files: List[UploadFile] = File(...)):
    """批量上传PDF|DOC|MD|HTM|HTML文件并转换为DOCX格式"""
    if not files:
        raise HTTPException(status_code=400, detail="请上传至少一个文件")

    # 准备文件数据
    files_data = []
    invalid_files = []
    
    for file in files:
        type_ext = Path(file.filename).suffix
        if type_ext not in ACCEPT_FILE_TYPES:
            invalid_files.append({
                "filename": file.filename,
                "reason": "非PDF|DOC|MD|HTM|HTML格式文件"
            })
            continue
        
        try:
            file_bytes = await file.read()
            files_data.append((file_bytes, Path(file.filename)))
                        
        except Exception as e:
            invalid_files.append({
                "filename": file.filename,
                "reason": f"文件读取失败: {str(e)}"
            })
            logger.error(f"读取文件 {file.filename} 时发生错误: {str(e)}")

    if not files_data:
        raise HTTPException(
            status_code=400, 
            detail={
                "message": "没有有效的PDF|DOC|MD|HTM|HTML文件可以处理",
                "invalid_files": invalid_files
            }
        )

    def process_file_parallel(file_bytes: bytes, filename: Path) -> Dict[str, Any]:
        """并行处理单个文件的函数"""
        try:            
            # 使用convert_file_to_docx处理文件
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    convert_file_to_docx(file_bytes, filename)
                )
            finally:
                loop.close()            
            return result
        except Exception as e:
            logger.warning("API接口中返回了失败的结果:{e}")
            result = {
                "orginal_saved": "",
                "converted_saved":""
            }
            return result
            
    # 使用joblib进行并行处理
    results = Parallel(n_jobs=MAX_WORKERS, prefer='threads')(
        delayed(process_file_parallel)(file_bytes, filename)
        for file_bytes, filename in files_data
    )
    # all = {"convert":results,"invalid":invalid_files}
    return results
   
@app.post("/convert/")
async def convert_file(file: UploadFile = File(...)):
    """上传PDF|DOC|MD|HTM|HTML文件并转换为DOCX格式"""
    # 将文件名转换为Path对象
    filename = Path(file.filename)
    type_ext = filename.suffix
    if type_ext not in ACCEPT_FILE_TYPES:
        raise HTTPException(status_code=400, detail="请上传PDF|DOC|MD|HTM|HTML格式的文件")
    
    # 读取文件内容
    file_bytes = await file.read()
    # 处理文件
    result = await convert_file_to_docx(file_bytes, filename)    
    return result


@app.get("/download/{file_path:path}")
async def download_file(file_path: str):
    try:
        # 构建完整的文件路径
        full_path = Path(file_path)
        
        # 检查文件是否存在
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="文件不存在")
       
        # 获取文件名
        filename = full_path.name
        
        # 返回文件响应
        return FileResponse(
            path=full_path,
            filename=filename,
            media_type= "application/octet-stream"
            # media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        
    except Exception as e:
        logger.error(f"下载文件时发生错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"下载文件时发生错误: {str(e)}")
    

##########################################################################
@app.post("/download/batch/")
async def download_batch(files: List[str]):
    """
    批量下载文件，返回一个ZIP文件
    
    Args:
        files: 文件路径列表，例如 ["F:/winserver/outputs/file1.docx", "F:/winserver/outputs/file2.docx"]
    """
    try:
        zip_buffer = BytesIO()
        failed_files = []
        
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for file_path in files:
                try:
                    # 转换路径格式并创建Path对象
                    file_path = file_path.replace("\\", "/")
                    full_path = Path(file_path)
                    
                    # 检查文件是否存在
                    if not full_path.exists():
                        failed_files.append({
                            "filename": full_path.name,
                            "reason": "文件不存在"
                        })
                        continue
                    
                    zip_file.write(full_path, arcname=full_path.name)
                    
                except Exception as e:
                    failed_files.append({
                        "filename": Path(file_path).name,
                        "reason": f"打包文件时发生错误: {str(e)}"
                    })
        
        if len(failed_files) == len(files):
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "所有文件处理失败",
                    "failed_files": failed_files
                }
            )
        
        zip_buffer.seek(0)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename=converted_files_{timestamp}.zip"
            }
        )
    
    except Exception as e:
        logger.error(f"批量下载文件时发生错误: {str(e)}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)

