import multiprocessing
from rapidocr_onnxruntime import RapidOCR
# from rapidocr_paddle import RapidOCR # For GPU
from jqcode.jq_readers.backend_reader_utils.pyemf3project.pyemf3 import EMF
from jqcode.jq_readers.backend_reader_utils.pyemf3project.pyemf3.emr import EXTTEXTOUTW
from jqcode.jq_utils.logger import jqkj_logger
logger = jqkj_logger(__file__).get_logger()

ocr = RapidOCR()
emf = EMF() #处理emf图片需要的

_cpu_nums = multiprocessing.cpu_count()
cpu_nums_for_img_ocr = int(_cpu_nums*0.7)

def treenode_img_to_text(treenode):
    result = ''
    #分隔符最好选用jqcode/jq_splitters/backend_splitter_utils/jq_chinese_recursive_text_splitter.py的第98行定义的
    _separator = ' '
    img_src=treenode.image_filepath_jq
    img_data =treenode.img_blob_jq
    try:
        if img_src.endswith('.emf'):
            emf.loadmem(img_data)
            recs = emf.records
            for rec in recs:
                if isinstance(rec, EXTTEXTOUTW):
                    _text = rec.values['string'].strip()
                    if _text:
                        result += _separator + _text
            logger.debug(f"图片[{img_src}]中的EMF文本:\n{result}")
        else:                    
            ocr_result,_ = ocr(img_data)
            if ocr_result:
                ocr_texts = [line[1].strip() for line in ocr_result if line[1].strip()]
                #分隔符最好选用jqcode/jq_splitters/backend_splitter_utils/jq_chinese_recursive_text_splitter.py的第98行定义的
                result = _separator.join(ocr_texts) 
                logger.debug(f"图片[{img_src}]中的OCR文本:\n{result}")
        treenode.text = result
    except Exception as e:
        logger.warning(f'获取图片[{img_src}]中的文本失败,详细信息为{e}')
    return result

def treenodes_img_to_text_in_batch(treenodes, processes=None):
    if processes:
        processes = min(processes,cpu_nums_for_img_ocr)
    else:
        processes = cpu_nums_for_img_ocr
    processes = min(len(treenodes),processes)
    print(f"~~~~~~~~~~~~~~~treenodes_img_to_text_in_batch进程池数量为{processes}~~~~~~~~~~~~~~~")
    with multiprocessing.Pool(processes) as p:
        results = p.map(treenode_img_to_text,treenodes)
    print(f"~~~~~~~~~~~~~~~treenodes_img_to_text_in_batch进程池数量为{processes}~~~~~~~~~~~~~~~")
    return results





