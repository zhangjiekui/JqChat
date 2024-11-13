
import io,uuid,httpx,json,subprocess
from pathlib import Path
import win32com.client
from typing import Dict, Any
from fastapi import HTTPException
from loguru import logger
from magic_pdf.rw.AbsReaderWriter import AbsReaderWriter
from magic_pdf.pipe.AbsPipe import AbsPipe

# 配置文件存储路径
OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)

# 远程服务配置
REMOTE_OCR_SERVICE = "http://10.1.150.106:8888/pdf_parse"


async def call_remote_ocr_service(pdf_bytes: bytes) -> Dict[str, Any]:
    """调用远程OCR服务"""
    try:
        async with httpx.AsyncClient() as client:
            files = {'pdf_file': ('document.pdf', pdf_bytes, 'application/pdf')}
            params = {
                'parse_method': 'ocr',
                'is_json_md_dump': False
            }
            
            response = await client.post(
                REMOTE_OCR_SERVICE,
                files=files,
                params=params,
                timeout=300  # 设置较长的超时时间，因为OCR处理可能需要较长时间
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"远程OCR服务调用失败: {response.status_code} - {response.text}")
                raise HTTPException(status_code=response.status_code, detail="远程OCR服务调用失败")
    except Exception as e:
        logger.error(f"调用远程OCR服务时出错: {str(e)}")
        raise HTTPException(status_code=500, detail=f"调用远程OCR服务时出错: {str(e)}")


async def process_single_file(pdf_bytes: bytes, pdf_filename: str) -> Dict[str, Any]:
    """处理单个PDF文件"""
    try:
        # 检查PDF类型
        pdf_type = check_pdf_type(pdf_bytes)
        
        # 如果是OCR类型，调用远程服务
        if pdf_type == "ocr":
            ocr_result = await call_remote_ocr_service(pdf_bytes)
            
            # 获取OCR的md_content并保存为MD文件
            md_content = ocr_result.get('md_content', '')
            if md_content:
                md_file_path = OUTPUT_DIR / f"{uuid.uuid4()}_{pdf_filename.stem}.md"
                with md_file_path.open('w', encoding='utf-8') as f:
                    f.write(md_content)
                
                # 使用Pandoc将MD转换为DOCX
                docx_file_path =  OUTPUT_DIR / f"{pdf_filename.stem}.docx"
                if convert_md_to_docx(md_file_path, docx_file_path):
                    return {
                        "success": True,
                        "message": "OCR处理并转换成功",
                        "pdf_type": pdf_type,
                        "docx_path": str(docx_file_path),
                        "ocr_result": ocr_result
                    }
                else:
                    return {
                        "success": False,
                        "message": "OCR转换为DOCX失败",
                        "pdf_type": pdf_type
                    }
            else:
                return {
                    "success": False,
                    "message": "OCR结果没有md_content",
                    "pdf_type": pdf_type
                }
        else:
            # 处理普通PDF文件转换
            temp_pdf = OUTPUT_DIR / f"{pdf_filename.stem}.pdf"  # 使用原文件名
            output_path = OUTPUT_DIR / f"{pdf_filename.stem}.docx"  # 使用原文件名转换为docx


            # 保存临时PDF文件
            with temp_pdf.open("wb") as f:
                f.write(pdf_bytes)

            try:
                # 转换文件
                success = convert_pdf_to_docx(temp_pdf, output_path)
                
                if success:
                    return {
                        "success": True,
                        "message": "转换成功",
                        "filename": output_path.name,
                        "docx_path": str(output_path),
                        "pdf_type": pdf_type

                                                

                    }
                else:
                    return {
                        "success": False,
                        "message": "转换失败",
                        "pdf_type": pdf_type
                    }
            finally:
                # 清理临时文件
                if temp_pdf.exists():
                    temp_pdf.unlink()

    except Exception as e:
        logger.error(f"处理文件时出错: {str(e)}")
        return {
            "success": False,
            "message": str(e)
        }


class UNIPipe(AbsPipe):

    def __init__(self, pdf_bytes: bytes, jso_useful_key: dict, image_writer: AbsReaderWriter, is_debug: bool = False,
                 start_page_id=0, end_page_id=None, lang=None,
                 layout_model=None, formula_enable=None, table_enable=None):
        self.pdf_type = jso_useful_key["_pdf_type"]
        super().__init__(pdf_bytes, jso_useful_key["model_list"], image_writer, is_debug, start_page_id, end_page_id,
                         lang, layout_model, formula_enable, table_enable)
        if len(self.model_list) == 0:
            self.input_model_is_empty = True
        else:
            self.input_model_is_empty = False

    def pipe_classify(self):
        self.pdf_type = AbsPipe.classify(self.pdf_bytes)
        return self.pdf_type
    

def convert_md_to_docx(md_path: Path, output_path: Path) -> bool:
    """将MD文件转换为DOCX格式"""
    import pypandoc
    print('开始转换md->docx', md_path, output_path)
    try:
        output = pypandoc.convert_file(str(md_path), 'docx', outputfile=str(output_path),
                                       extra_args=['--extract-media', ''])
        return True
        # if output:
        #     logger.info(f"MD文件转换成功: {output_path}")
        #     return True
        # else:
        #     logger.error(f"Pandoc转换失败: {output}")
        #     return False
    except subprocess.CalledProcessError as e:
        logger.error(f"Pandoc转换失败: {str(e)}")
        return False
    


def check_pdf_type(pdf_bytes: bytes) -> str:
    """检查PDF文件类型"""
    try:
        pdf_type = UNIPipe.classify(pdf_bytes)
        logger.info(f"PDF类型检测结果: {pdf_type}")
        return pdf_type
    except Exception as e:
        logger.error(f"PDF类型检测失败: {str(e)}")
        raise HTTPException(status_code=500, detail="PDF类型检测失败")
    

def convert_pdf_to_docx(pdf_path: Path, output_path: Path) -> bool:
    """将PDF文件转换为DOCX格式"""
    try:
        # 启动Word应用程序
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        
        try:
            # 打开PDF文件
            pdfdoc = word.Documents.Open(str(pdf_path.absolute()))
            
            # 保存为DOCX格式 (wdFormatXMLDocument = 12)
            pdfdoc.SaveAs(str(output_path.absolute()), 12)
            
            # 关闭文档
            pdfdoc.Close()
            logger.info(f"转换成功: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"转换过程中出错: {str(e)}")
            return False
            
        finally:
            # 确保Word应用程序被关闭
            word.Quit()
            
    except Exception as e:
        logger.error(f"转换失败: {str(e)}")
        return False
    