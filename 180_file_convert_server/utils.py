
import io,os,uuid,httpx,json,subprocess,requests
from pathlib import Path
from fastapi import UploadFile
import win32com.client
from typing import Dict, Any
from fastapi import HTTPException
from loguru import logger
import pypandoc
import tempfile
import socket
import pythoncom
from threading import Lock


docpdf_list = [".doc",".pdf"]
pandoc_list =  [".md",".html",".htm"]
ACCEPT_FILE_TYPES = docpdf_list + pandoc_list
# 配置文件存储路径
UPLOADS_DIR = Path("uploads")
UPLOADS_DIR.mkdir(exist_ok=True)
OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)
MAX_WORKERS = 4 
PORT=8000

# os.environ.setdefault('PYPANDOC_PANDOC', fr'C:\Program Files\Pandoc\pandoc.exe')

# 创建全局锁
word_app_lock = Lock()

def get_local_ip(local_ip = "192.168.44.180"):        
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        return local_ip
    except Exception:
        return local_ip

async def convert_md_htm_to_docx(md_htm_path, output_path):
    md_htm_path = Path(md_htm_path)
    output_path = Path(output_path)   
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        # Method 1: Direct conversion with proper outputfile       
        src = md_htm_path
        des = output_path
        logger.info(f"pypandoc转换:{src} ==> {des}")
        pypandoc.convert_file(
            src,
            'docx',
            outputfile=des,
        )
        if output_path.is_file():
            # raise Exception 为了测试异常中Method 2: Use temporary file then move
            return output_path
        else:
            raise Exception
    
    except Exception as e:       
        # Method 2: Use temporary file then move
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_output = Path(temp_dir) / "temp_output.docx"               
                # Convert to temporary file
                pypandoc.convert_file(
                    str(md_htm_path),
                    'docx',
                    outputfile=str(temp_output),
                )
                
                # Move to final location
                if temp_output.exists():
                    # Remove existing output file if it exists
                    if output_path.exists():
                        output_path.unlink()                    
                    # Move temporary file to final location
                    import shutil
                    shutil.move(str(temp_output.absolute()), str(output_path.absolute()))
                    return output_path
        except Exception as e:
            logger.warning(f"pypandoc转换:{src} ==> {des}失败:{e}")

async def convert_doc_pdf_to_docx(docpdf_path: Path, output_path: Path) -> Dict[str, Any]:
    """将PDF文件转换为DOCX格式"""
    # COM组件初始化
    pythoncom.CoInitialize()
    
    try:
        with word_app_lock:  # 使用锁保护Word应用程序的创建和使用
            word = win32com.client.Dispatch("Word.Application")
            word.Visible = False
            
            try:
                output_path.mkdir(exist_ok=True)
                docxfile = output_path / f"{docpdf_path.stem}.docx"
                # 打开PDF文件
                pdfdoc = word.Documents.Open(str(docpdf_path.absolute()))
                
                # 保存为DOCX格式 (wdFormatXMLDocument = 12)
                # pdfdoc.SaveAs(str(output_path.absolute()), 12)
                pdfdoc.SaveAs(str(docxfile.absolute()), 12)
                # 关闭文档
                pdfdoc.Close()
                 
                if docxfile.exists():
                    logger.info(f"WORD转换成功: {docpdf_path} ==> {docxfile}")
                else:
                    raise Exception
            finally:
                # 确保Word应用程序被关闭
                word.Quit()

                
    except Exception as e:
        error_msg = f"WORD转换({docpdf_path} ==> {docxfile})过程中出错: {str(e)}"
        logger.warning(error_msg)
        
    finally:
        # 清理COM组件
        pythoncom.CoUninitialize()

async def save_binary_data_to_file(file_bytes: bytes, file_name: str,upload_dir:Path= UPLOADS_DIR):
    """
    将二进制数据保存为文件
    :param data: 二进制数据（bytes）
    :param file_path: 保存的文件路径（包含扩展名）
    """
    upload_dir.mkdir(parents=True,exist_ok=True)
    file_path = upload_dir / file_name.name # 使用原文件名
    with open(file_path, 'wb') as f:
        f.write(file_bytes)
    if os.path.exists(file_path):
        logger.warning(f"需转换的原始文件已保存至: {file_path}")
        return file_path
    else:
        raise Exception(f"原始文件{file_path}存储失败")

async def convert_file_to_docx(file_bytes: bytes, file_name: str, overwrite=False, upload_dir:Path= UPLOADS_DIR, output_dir:Path=OUTPUT_DIR):
    
    original_saved = ""
    converted_saved = ""
    upload_path = upload_dir / file_name.name
    output_path = output_dir / f"{file_name.stem}.docx"  # 使用原文件名转换为docx
    if not os.path.exists(upload_path) or overwrite:
        try:
            file_path = await save_binary_data_to_file(file_bytes,file_name,upload_dir)
        except Exception as e:
            logger.warning(f"原始文件{file_path}存储失败:{e}")

    
    # 根据文件扩展名进行转换
    if not os.path.exists(output_path) or overwrite:
        filepath = Path(file_name)
        # logger.info(f'==*==转换文件{filepath} ==> {output_path}')
        if Path(filepath).suffix in pandoc_list:
            try:
                result = await convert_md_htm_to_docx(upload_path,  output_path=output_path)
            except Exception as e:
                logger.warning(f"convert_md_htm_to_docx失败{e}：{upload_path} ==> {output_path}")
        elif Path(filepath).suffix in docpdf_list:
            try:
                result = await convert_doc_pdf_to_docx(upload_path, output_path=output_dir)
            except Exception as e:
                logger.warning(f"convert_doc_pdf_to_docx失败{e}：{upload_path} ==> {output_path}")
        else:
            logger.warning(f"    Converter跳过文件转换: {filepath}")
    
    if os.path.exists(upload_path):
        logger.info(f"原始文件-->{upload_path}已保存")
        original_saved = upload_path    
    
    if os.path.exists(output_path):
        logger.warning(f"转换文件==>{upload_path} ==> {output_path}已完成并保存")
        converted_saved = output_path

    local_ip = get_local_ip()
    original_file_url = original_saved
    if original_file_url:
        original_rel_path = str(original_file_url).replace("\\","/")
        original_file_url = f"http://{local_ip}:{PORT}/download/{original_rel_path}"    
    
    converted_file_url = converted_saved
    if converted_file_url:
        converted_rel_path = str(converted_file_url).replace("\\","/")
        converted_file_url = f"http://{local_ip}:{PORT}/download/{converted_rel_path}"
    result = {
                "original": original_file_url,
                "converted":converted_file_url
             }
    return result


if __name__ == "__main__":
    # Usage
    local_ip = get_local_ip()
    print(f"Local IP: {local_ip}")

    import asyncio
    files = [fr"D:\project\winserver\uploads_test\个人陈述素材收集表.doc",fr"D:\project\winserver\uploads_test\A45-47民政部科研任务书.pdf",fr"D:\project\winserver\uploads_test\r1.md"]
    # files = [fr"D:\project\winserver\uploads_test\DeepSeek_R1.md"]
    for file in files:
        with open(file,'rb') as f:
            file_bytes=f.read()
        file_name = Path(file)
        convert_file_coro = convert_file_to_docx(file_bytes,file_name)
        result = asyncio.run(convert_file_coro)
        print(result)
        print("=======================")