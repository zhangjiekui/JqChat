from rapidocr_onnxruntime import RapidOCR
from jqcode.jq_readers.backend_reader_utils.pyemf3project.pyemf3 import EMF
from jqcode.jq_readers.backend_reader_utils.pyemf3project.pyemf3.emr import EXTTEXTOUTW
from typing import Any, Callable, Dict, Generator, List, Optional, Type
from jqcode.jq_utils.logger import jqkj_logger

import asyncio
from llama_index.core.async_utils import run_jobs, get_asyncio_module

logger = jqkj_logger(__file__).get_logger()

ocr = RapidOCR()
emf = EMF() #处理emf图片需要的


async def async_img_to_text(img_metadata:dict):
    result = ''
    #分隔符最好选用jqcode/jq_splitters/backend_splitter_utils/jq_chinese_recursive_text_splitter.py的第98行定义的
    _separator = ' '
    img_src=img_metadata['img_save_path_jq']
    img_data = img_metadata['img_blob_jq']
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
    except Exception as e:
        logger.warning(f'获取图片[{img_src}]中的文本失败,详细信息为{e}')
    img_metadata.update({"img_text":result})
    return img_metadata

async def async_img_to_text_batch(img_metadatas_list:List[dict],show_progress: bool = False,num_workers: Optional[int] = 10):
    num_workers = num_workers if num_workers else len(img_metadatas_list)
    coroutines = [async_img_to_text(img_metadata) for img_metadata in img_metadatas_list]
    
    if num_workers:
        img_metadatas_with_text_list = await run_jobs(coroutines, show_progress=show_progress, workers=num_workers)
    elif show_progress:
        _asyncio = get_asyncio_module(show_progress=show_progress)
        img_metadatas_with_text_list = await _asyncio.gather(*coroutines)
    else:
        img_metadatas_with_text_list = await asyncio.gather(*coroutines)
    
    return img_metadatas_with_text_list

from aiomultiprocess import Pool
async def async_img_to_text2(img_metadata:dict):
    result = ''
    #分隔符最好选用jqcode/jq_splitters/backend_splitter_utils/jq_chinese_recursive_text_splitter.py的第98行定义的
    _separator = ' '
    img_src=img_metadata['img_save_path_jq']
    img_data = img_metadata['img_blob_jq']
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
    except Exception as e:
        logger.warning(f'获取图片[{img_src}]中的文本失败,详细信息为{e}')
    img_metadata.update({"img_text":result})
    return img_metadata

async def async_img_to_text_batch2(img_metadatas_list, processes=20,maxtasksperchild=10,childconcurrency=4):
    # num = len(img_metadatas_list)
    # processes = min(num,processes)
    async with Pool(processes=processes) as pool:
        results = await pool.map(async_img_to_text2, img_metadatas_list)
    return results



