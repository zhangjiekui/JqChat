import os, io, logging, asyncio, zipfile,tempfile,shutil,requests
from io import BytesIO
from pathlib import Path
from typing import Dict, Any,List
from joblib import Parallel, delayed
from datetime import datetime  
from typing import List
from fastapi import FastAPI, UploadFile, File, HTTPException,Form
from fastapi.responses import FileResponse, StreamingResponse

# from utils import process_single_file, convert_pdf_to_docx,check_pdf_type
from utils import process_single_file,docx_path_to_content

from concurrent.futures import ThreadPoolExecutor

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="PDF转DOCX服务")

MAX_WORKERS = 8

@app.post("/convert/batch/")
async def convert_pdfs(files: List[UploadFile] = File(...)):
    """批量上传PDF文件并转换为DOCX格式"""
    if not files:
        raise HTTPException(status_code=400, detail="请上传至少一个文件")

    # 准备文件数据
    files_data = []
    invalid_files = []
    
    for file in files:
        if not file.filename.lower().endswith(('.pdf', '.doc')):
            invalid_files.append({
                "filename": file.filename,
                "reason": "非PDF、DOC格式文件"
            })
            continue
        
        try:
            pdf_bytes = await file.read()
            # 检查PDF类型
            if file.filename.lower().endswith('.doc'):
                pdf_type = 'txt'
                files_data.append((pdf_bytes, Path(file.filename), pdf_type))
                print(f"PDF类型是: {pdf_type}")
            else:
            
                try:
                    # pdf_type = check_pdf_type(pdf_bytes)
                    # files_data.append((pdf_bytes, Path(file.filename), pdf_type))

                    # 换接口的方式获取pdf类型
                    response = requests.post('http://10.1.150.106:8888/get_pdf_type', data=pdf_bytes)
                    # 检查响应状态码
                    if response.status_code == 200:
                        # 解析JSON响应
                        result = response.json()
                        # 获取PDF类型
                        pdf_type = result['pdf_type']
                        files_data.append((pdf_bytes, Path(file.filename), pdf_type))
                        print(f"PDF类型是: {pdf_type}")
                    else:
                        # 处理错误情况
                        error_msg = response.json().get('error', '未知错误')
                        print(f"错误: {error_msg}")
                    
                except Exception as e:
                    invalid_files.append({
                        "filename": file.filename,
                        "reason": f"PDF类型检查失败: {str(e)}"
                    })
                    logger.error(f"检查文件 {file.filename} 类型时发生错误: {str(e)}")
                
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
                "message": "没有有效的PDF文件可以处理",
                "invalid_files": invalid_files
            }
        )

    def process_file_parallel(pdf_bytes: bytes, filename: Path, pdf_type: str) -> Dict[str, Any]:
        """并行处理单个文件的函数"""
        try:
            # 创建outputs目录（如果不存在）
            output_dir = Path("outputs")
            output_dir.mkdir(exist_ok=True)
            
            # 使用process_single_file处理文件
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    process_single_file(pdf_bytes, pdf_type, filename, output_dir)
                )
            finally:
                loop.close()
            
            result["filename"] = str(filename)
            result["pdf_type"] = pdf_type

            return result
            
        except Exception as e:
            error_msg = f"处理文件 {filename} 时发生错误: {str(e)}"
            logger.error(error_msg)
            return {
                "filename": str(filename),
                "success": False,
                "message": error_msg,
                "pdf_type": pdf_type,
                "docx_content": ''
            }

    # 使用joblib进行并行处理
    results = Parallel(n_jobs=MAX_WORKERS, prefer='threads')(
        delayed(process_file_parallel)(pdf_bytes, filename, pdf_type)
        for pdf_bytes, filename, pdf_type in files_data
    )
    
    # 统计成功和失败数量
    success_count = sum(1 for r in results if r["success"])
    fail_count = len(results) - success_count
    
    # 按PDF类型分类统计
    type_stats = {}
    for result in results:
        pdf_type = result.get("pdf_type", "unknown")
        if pdf_type not in type_stats:
            type_stats[pdf_type] = {
                "total": 0,
                "success": 0,
                "failed": 0
            }
        type_stats[pdf_type]["total"] += 1
        if result["success"]:
            type_stats[pdf_type]["success"] += 1
        else:
            type_stats[pdf_type]["failed"] += 1
    
    return {
        "total": len(results),
        "success_count": success_count,
        "fail_count": fail_count,
        "invalid_files": invalid_files,
        "type_statistics": type_stats,
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
                    
                    # 确保是DOCX文件
                    if not str(full_path).lower().endswith('.docx'):
                        failed_files.append({
                            "filename": full_path.name,
                            "reason": "非DOCX格式文件"
                        })
                        continue
                    
                    # 只使用文件名作为zip中的名称，避免包含完整路径
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
    uvicorn.run(app, host="0.0.0.0", port=8000)

