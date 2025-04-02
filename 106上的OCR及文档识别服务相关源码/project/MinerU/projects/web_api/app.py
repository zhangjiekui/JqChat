import copy
import json
import os, subprocess
from tempfile import NamedTemporaryFile

import magic_pdf.model as model_config
import uvicorn
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import JSONResponse
from loguru import logger
from fastapi.responses import FileResponse
from magic_pdf.pipe.OCRPipe import OCRPipe
from magic_pdf.pipe.TXTPipe import TXTPipe
from magic_pdf.pipe.UNIPipe import UNIPipe
from magic_pdf.rw.DiskReaderWriter import DiskReaderWriter



from pydantic import BaseModel

import base64
import logging
from pathlib import Path
import shutil

logger = logging.getLogger(__name__)

model_config.__use_inside_model__ = True

app = FastAPI()


def convert_md_to_docx(output_path):
    # 使用 Path 对象处理路径
    output_dir = Path(output_path)
    file_name = output_dir.name
    
    md_file_path = output_dir / f"{file_name}.md"
    docx_file_path = output_dir / f"{file_name}.docx"
    output_image_path = output_dir / "images"
    
    # 确保图片目录存在
    output_image_path.mkdir(exist_ok=True)
    
    try:
        # 使用绝对路径，并将路径转换为字符串
        cmd = [
            "pandoc",
            str(md_file_path.absolute()),
            "-o",
            str(docx_file_path.absolute()),
            "--extract-media",
            str(output_image_path.absolute()),
            "--resource-path",
            str(output_dir.absolute())
        ]
        
        # 运行命令并捕获输出
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        
        # 如果有警告信息，打印出来
        if result.stderr:
            print(f"转换警告: {result.stderr}")
            
        return str(docx_file_path)
        
    except subprocess.CalledProcessError as e:
        print(f"转换失败: {e}")
        print(f"错误输出: {e.stderr}")
        raise
    except Exception as e:
        print(f"发生错误: {e}")
        raise



def json_md_dump(
        pipe,
        md_writer,
        pdf_name,
        content_list,
        md_content,
):
    # Write model results to model.json
    orig_model_list = copy.deepcopy(pipe.model_list)
    md_writer.write(
        content=json.dumps(orig_model_list, ensure_ascii=False, indent=4),
        path=f"{pdf_name}_model.json"
    )

    # Write intermediate results to middle.json
    md_writer.write(
        content=json.dumps(pipe.pdf_mid_data, ensure_ascii=False, indent=4),
        path=f"{pdf_name}_middle.json"
    )

    # Write text content results to content_list.json
    md_writer.write(
        content=json.dumps(content_list, ensure_ascii=False, indent=4),
        path=f"{pdf_name}_content_list.json"
    )

    # Write results to .md file
    md_writer.write(
        content=md_content,
        path=f"{pdf_name}.md"
    )

@app.post("/pdf_parse", tags=["projects"], summary="Parse PDF file")
async def pdf_parse_main(
        pdf_file: UploadFile = File(...),
        parse_method: str = 'auto',
        model_json_path: str = None,
        is_json_md_dump: bool = True,
        output_dir: str = "output"
):
    """
    Execute the process of converting PDF to JSON and MD, outputting MD and JSON files to the specified directory
    :param pdf_file: The PDF file to be parsed
    :param parse_method: Parsing method, can be auto, ocr, or txt. Default is auto. If results are not satisfactory, try ocr
    :param model_json_path: Path to existing model data file. If empty, use built-in model. PDF and model_json must correspond
    :param is_json_md_dump: Whether to write parsed data to .json and .md files. Default is True. Different stages of data will be written to different .json files (3 in total), md content will be saved to .md file
    :param output_dir: Output directory for results. A folder named after the PDF file will be created to store all results
    """
    try:
        # Create a temporary file to store the uploaded PDF
        with NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
            temp_pdf.write(await pdf_file.read())
            temp_pdf_path = temp_pdf.name

        pdf_name = os.path.basename(pdf_file.filename).split(".")[0]

        if output_dir:
            output_path = os.path.join(output_dir, pdf_name)
        else:
            output_path = os.path.join(os.path.dirname(temp_pdf_path), pdf_name)

        output_image_path = os.path.join(output_path, 'images')

        # Get parent path of images for relative path in .md and content_list.json
        image_path_parent = os.path.basename(output_image_path)

        pdf_bytes = open(temp_pdf_path, "rb").read()  # Read binary data of PDF file

        if model_json_path:
            # Read original JSON data of PDF file parsed by model, list type
            model_json = json.loads(open(model_json_path, "r", encoding="utf-8").read())
        else:
            model_json = []

        # Execute parsing steps
        image_writer, md_writer = DiskReaderWriter(output_image_path), DiskReaderWriter(output_path)

        # Choose parsing method
        if parse_method == "auto":
            jso_useful_key = {"_pdf_type": "", "model_list": model_json}
            pipe = UNIPipe(pdf_bytes, jso_useful_key, image_writer)
        elif parse_method == "txt":
            pipe = TXTPipe(pdf_bytes, model_json, image_writer)
        elif parse_method == "ocr":
            pipe = OCRPipe(pdf_bytes, model_json, image_writer)
        else:
            logger.error("Unknown parse method, only auto, ocr, txt allowed")
            return JSONResponse(content={"error": "Invalid parse method"}, status_code=400)

        # Execute classification
        pipe.pipe_classify()

        # If no model data is provided, use built-in model for parsing
        if not model_json:
            if model_config.__use_inside_model__:
                pipe.pipe_analyze()  # Parse
            else:
                logger.error("Need model list input")
                return JSONResponse(content={"error": "Model list input required"}, status_code=400)

        # Execute parsing
        pipe.pipe_parse()

        # Save results in text and md format
        content_list = pipe.pipe_mk_uni_format(image_path_parent, drop_mode="none")
        md_content = pipe.pipe_mk_markdown(image_path_parent, drop_mode="none")

        if is_json_md_dump:
            json_md_dump(pipe, md_writer, pdf_name, content_list, md_content)
        # data = {"layout": copy.deepcopy(pipe.model_list), 
        #         "info": pipe.pdf_mid_data, 
        #         "content_list": content_list,
        #         'md_content':md_content}
        # return JSONResponse(data, status_code=200)
        
        docx_file_path = convert_md_to_docx(output_path)

        data = {'docx_file_path':docx_file_path,
                "layout": copy.deepcopy(pipe.model_list), 
                "info": pipe.pdf_mid_data, 
                "content_list": content_list,
                'md_content':md_content,
                'download_url': f"/download_docx?file_path={os.path.basename(docx_file_path)}"
                }
        return JSONResponse(data, status_code=200)
        

    except Exception as e:
        logger.exception(e)
        return JSONResponse(content={"error": str(e)}, status_code=500)
    finally:
        # Clean up the temporary file
        if 'temp_pdf_path' in locals():
            os.unlink(temp_pdf_path)

################################################################################
from fastapi import Request
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

@app.post("/get_pdf_type", tags=["projects"], summary="Get PDF type classification")
async def get_pdf_type(request: Request):
    """
    Get the type classification of PDF bytes
    :param request: Request containing PDF bytes in body
    :return: The classified type of the PDF file
    """
    try:
        # Get raw bytes from request body
        pdf_bytes = await request.body()
        
        pdf_type = UNIPipe.classify(pdf_bytes)
        
        return JSONResponse(
            content={"pdf_type": pdf_type},
            status_code=200
        )

    except Exception as e:
        logger.exception(e)
        return JSONResponse(
            content={"error": str(e)},
            status_code=500
        )
    
############################## 下载接口 #################################################
from fastapi import FastAPI, HTTPException
from urllib.parse import unquote

ALLOWED_DOWNLOAD_DIR = os.path.abspath("output")    


@app.get("/download_docx")
async def download_docx(file_path: str):
    """
    下载 docx 文件的接口
    
    参数:
        file_path: URL编码的文件路径，可以是相对于 ALLOWED_DOWNLOAD_DIR 的路径
        
    返回:
        文件响应
    """
    try:
        # URL解码
        decoded_path = unquote(file_path)

        # 如果decoded_path以output开头，去掉output部分
        if decoded_path.startswith('output/'):
            decoded_path = decoded_path[7:]  # 去掉 'output/'
        
        # 使用 Path 处理路径
        allowed_dir = Path(ALLOWED_DOWNLOAD_DIR)
        full_path = allowed_dir / decoded_path
        
        # 规范化路径
        abs_file_path = full_path.resolve()
        
        # 安全检查：确保请求的文件路径在允许的目录范围内
        if not str(abs_file_path).startswith(str(allowed_dir.resolve())):
            raise HTTPException(
                status_code=403,
                detail="Access to this file path is forbidden"
            )
        
        # 检查文件是否存在
        if not abs_file_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"File not found: {decoded_path}"
            )
        
        # 检查文件扩展名是否为 .docx
        if abs_file_path.suffix.lower() != '.docx':
            raise HTTPException(
                status_code=400,
                detail="Only .docx files are allowed"
            )
        
        # 获取文件名
        filename = abs_file_path.name
        
        # 打印调试信息
        print(f"Attempting to serve file: {abs_file_path}")
        print(f"File exists: {abs_file_path.exists()}")
        print(f"Is file: {abs_file_path.is_file()}")
        
        # 返回文件响应
        return FileResponse(
            path=str(abs_file_path),
            filename=filename,
            media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        
    except Exception as e:
        # 打印详细错误信息
        import traceback
        print(f"Error in download_docx: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download file: {str(e)}"
        )
    
if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8888)