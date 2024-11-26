
import io,os,uuid,httpx,json,subprocess,requests
from pathlib import Path
import win32com.client
from typing import Dict, Any
from fastapi import HTTPException
from loguru import logger
from docx import Document
# from magic_pdf.rw.AbsReaderWriter import AbsReaderWriter
# from magic_pdf.pipe.AbsPipe import AbsPipe

# 配置文件存储路径
OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)

import pythoncom
from threading import Lock
# 创建全局锁
word_app_lock = Lock()
MAX_WORKERS = 4 


# 远程服务配置
REMOTE_OCR_SERVICE = "http://10.1.150.106:8888/pdf_parse"


async def call_remote_ocr_service(
    pdf_bytes: bytes,
    pdf_filename: str = '',
    parse_method: str = 'auto',
    model_json_path: str = None,
    is_json_md_dump: bool = True,
    output_dir: str = "output"
) -> Dict[str, Any]:
    
    """调用远程OCR服务"""
    try:
        async with httpx.AsyncClient() as client:
            files = {'pdf_file': (pdf_filename, pdf_bytes, 'application/pdf')}
            params = {
                'parse_method': parse_method,
                'is_json_md_dump': is_json_md_dump,
                'output_dir': output_dir
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


def docx_path_to_content(docx_path):
    if docx_path and os.path.exists(docx_path):
        try:
            doc = Document(docx_path)
            # 获取所有段落的文本并合并
            paragraphs_text = []
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():  # 只添加非空段落
                    paragraphs_text.append(paragraph.text.strip())
            
            # 获取所有表格中的文本
            tables_text = []
            for table in doc.tables:
                for row in table.rows:
                    row_text = []
                    for cell in row.cells:
                        # 去除单元格中的空白字符
                        cell_text = cell.text.strip()
                        if cell_text:  # 只添加非空单元格
                            row_text.append(cell_text)
                    if row_text:  # 只添加非空行
                        tables_text.append(' | '.join(row_text))
            
            # 合并所有文本内容
            all_text = '\n'.join(paragraphs_text + tables_text)
            return all_text
           
        except Exception as e:
            error_msg = f"读取Word文档 {docx_path} 时发生错误: {str(e)}"
            logger.error(error_msg)
            return ''



    
async def process_single_file(pdf_bytes: bytes, pdf_type, pdf_filename: str, output_dir) -> Dict[str, Any]:
    """处理单个PDF文件"""
    try:
        # # 检查PDF类型
        # # pdf_type = check_pdf_type(pdf_bytes)

        # # 换接口的方式获取pdf类型
        # response = requests.post('http://10.1.150.106:8888/get_pdf_type', data=pdf_bytes)
        # # 检查响应状态码
        # if response.status_code == 200:
        #     # 解析JSON响应
        #     result = response.json()
        #     # 获取PDF类型
        #     pdf_type = result['pdf_type']
        #     print(f"PDF类型是: {pdf_type}")
        # else:
        #     # 处理错误情况
        #     error_msg = response.json().get('error', '未知错误')
        #     print(f"错误: {error_msg}")
        
        # 如果是OCR类型，调用远程服务
        if pdf_type == "ocr":
            ocr_result = await call_remote_ocr_service(pdf_bytes, pdf_filename.name)

            try:
                # 调用下载接口
                response_get = requests.get('http://10.1.150.106:8888/download_docx', 
                                        params={"file_path": ocr_result['docx_file_path']},
                                        stream=True  # 使用流式下载避免大文件内存问题
                                        )
                
                # 检查响应状态
                response_get.raise_for_status()

                docx_file_path =  OUTPUT_DIR / f"{pdf_filename.stem}.docx"
                
                # 确保保存目录存在
                os.makedirs(os.path.dirname(docx_file_path), exist_ok=True)
                
                # 保存文件
                with open(docx_file_path, 'wb') as f:
                    for chunk in response_get.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            
                return {
                        "success": True,
                        "message": "OCR处理并转换成功",
                        "pdf_type": pdf_type,
                        "docx_path": str(docx_file_path),
                        # "ocr_result": ocr_result
                    }
            
            except requests.exceptions.RequestException as e:
                print(f"下载文件时发生错误: {e}")
                return {
                        "success": False,
                        "message": "OCR转换为DOCX失败",
                        "pdf_type": pdf_type
                    }
    
            # # 获取OCR的md_content并保存为MD文件
            # md_content = ocr_result.get('md_content', '')
            # if md_content:
            #     md_file_path = OUTPUT_DIR / f"{uuid.uuid4()}_{pdf_filename.stem}.md"
            #     with md_file_path.open('w', encoding='utf-8') as f:
            #         f.write(md_content)
                
            #     # 使用Pandoc将MD转换为DOCX
            #     docx_file_path =  OUTPUT_DIR / f"{pdf_filename.stem}.docx"
            #     if convert_md_to_docx(md_file_path, docx_file_path):
            #         return {
            #             "success": True,
            #             "message": "OCR处理并转换成功",
            #             "pdf_type": pdf_type,
            #             "docx_path": str(docx_file_path),
            #             # "ocr_result": ocr_result
            #         }
            #     else:
            #         return {
            #             "success": False,
            #             "message": "OCR转换为DOCX失败",
            #             "pdf_type": pdf_type
            #         }
            # else:
            #     return {
            #         "success": False,
            #         "message": "OCR结果没有md_content",
            #         "pdf_type": pdf_type
            #     }
            



        else:
            # 处理普通PDF文件转换
            temp_pdf = OUTPUT_DIR / pdf_filename.name # 使用原文件名
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


# class UNIPipe(AbsPipe):

#     def __init__(self, pdf_bytes: bytes, jso_useful_key: dict, image_writer: AbsReaderWriter, is_debug: bool = False,
#                  start_page_id=0, end_page_id=None, lang=None,
#                  layout_model=None, formula_enable=None, table_enable=None):
#         self.pdf_type = jso_useful_key["_pdf_type"]
#         super().__init__(pdf_bytes, jso_useful_key["model_list"], image_writer, is_debug, start_page_id, end_page_id,
#                          lang, layout_model, formula_enable, table_enable)
#         if len(self.model_list) == 0:
#             self.input_model_is_empty = True
#         else:
#             self.input_model_is_empty = False

#     def pipe_classify(self):
#         self.pdf_type = AbsPipe.classify(self.pdf_bytes)
#         return self.pdf_type
    

def convert_md_to_docx(md_path: Path, output_path: Path) -> bool:
    """将MD文件转换为DOCX格式"""
    import pypandoc
    print('开始转换md->docx', md_path, output_path)
    try:
        output = pypandoc.convert_file(str(md_path), 'docx', outputfile=str(output_path),
                                       extra_args=['--extract-media', ''])
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"Pandoc转换失败: {str(e)}")
        return False
    


# def check_pdf_type(pdf_bytes: bytes) -> str:
#     """检查PDF文件类型"""
#     try:
#         pdf_type = UNIPipe.classify(pdf_bytes)
#         logger.info(f"PDF类型检测结果: {pdf_type}")
#         return pdf_type
#     except Exception as e:
#         logger.error(f"PDF类型检测失败: {str(e)}")
#         raise HTTPException(status_code=500, detail="PDF类型检测失败")
    

def convert_pdf_to_docx(pdf_path: Path, output_path: Path) -> Dict[str, Any]:
    """将PDF文件转换为DOCX格式"""
    # COM组件初始化
    pythoncom.CoInitialize()
    
    try:
        with word_app_lock:  # 使用锁保护Word应用程序的创建和使用
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
                result = {
                    "success": True,
                    "message": "转换成功",
                    "docx_path": str(output_path)
                }
                
            except Exception as e:
                error_msg = f"转换过程中出错: {str(e)}"
                logger.error(error_msg)
                result = {
                    "success": False,
                    "message": error_msg,
                    "docx_path": None
                }
                
            finally:
                # 确保Word应用程序被关闭
                word.Quit()
                
        return result
                
    except Exception as e:
        error_msg = f"转换失败: {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "message": error_msg,
            "docx_path": None
        }
        
    finally:
        # 清理COM组件
        pythoncom.CoUninitialize()

