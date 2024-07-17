from typing import Union
from pathlib import Path
from pdf2docx import Converter
from spire.doc import *
from spire.doc.common import *

from jqcode.jq_utils.logger import jqkj_logger
logger = jqkj_logger(__file__).get_logger()



def convert_doc_to_docx(src_doc_file_path:Union[str,Path],saved_doc_file_path:Union[str,Path]=None):
    src_doc_file_path = Path(src_doc_file_path)

    if not saved_doc_file_path:
        destination_dir=src_doc_file_path.absolute()
        if not Path(destination_dir).exists():
            logger.warning(f"输出目录[{destination_dir}]不存在!将尝试创建该目录。")
            Path(destination_dir).mkdir(parents=True, exist_ok=True)
        docx_filepath = src_doc_file_path.with_suffix(".docx")
        saved_doc_file_path = docx_filepath
    document = Document()
    # Load a Word DOC file
    document.LoadFromFile(str(src_doc_file_path))
    # Save the DOC file to DOCX format
    document.SaveToFile(str(saved_doc_file_path), FileFormat.Docx2016)
    # Close the Document object
    document.Close()


def convert_pdf_to_docx(src_pdf_file_path:Union[str,Path],saved_doc_file_path:Union[str,Path]=None,multi_processing:bool=True,cpu_count:int=4, delete_end_line_hyphen:bool=True):
    src_pdf_file_path = Path(src_pdf_file_path)

    if not saved_doc_file_path:
        destination_dir=src_pdf_file_path.absolute()
        if not Path(destination_dir).exists():
            logger.warning(f"输出目录[{destination_dir}]不存在!将尝试创建该目录。")
            Path(destination_dir).mkdir(parents=True, exist_ok=True)
        docx_filepath = src_pdf_file_path.with_suffix(".docx")
        saved_doc_file_path = docx_filepath

    cv = Converter(src_pdf_file_path)
    settings = cv.default_settings
    # settings.update({"multi_processing":multi_processing,"cpu_count":cpu_count})
    settings = {"multi_processing":multi_processing,"cpu_count":cpu_count,"delete_end_line_hyphen":delete_end_line_hyphen} 
    cv.convert(saved_doc_file_path,**settings)
    # print(f"{saved_doc_file_path=}")
    cv.close()

if __name__ == "__main__":
    pdf_filepath = fr"/data/projects/JqChat/test_en.pdf"
    convert_pdf_to_docx(pdf_filepath)
    
