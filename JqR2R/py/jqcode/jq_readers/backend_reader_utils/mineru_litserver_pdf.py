import os
import fitz
import copy
import time
import torch
import base64
import litserve as ls
from loguru import logger
import json as json_parse
from fastapi import HTTPException
from filetype import guess_extension
import magic_pdf.model as model_config
from magic_pdf.libs.draw_bbox import (draw_layout_bbox, draw_line_sort_bbox,
                                      draw_model_bbox, draw_span_bbox)
from magic_pdf.libs.MakeContentConfig import DropMode, MakeMode
from magic_pdf.pipe.OCRPipe import OCRPipe
from magic_pdf.pipe.TXTPipe import TXTPipe
from magic_pdf.pipe.UNIPipe import UNIPipe
from magic_pdf.rw.AbsReaderWriter import AbsReaderWriter
from magic_pdf.rw.DiskReaderWriter import DiskReaderWriter
from magic_pdf.tools.common import prepare_env
from magic_pdf.model.doc_analyze_by_custom_model import ModelSingleton

def to_b64(file_path):
    try:
        with open(file_path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')
    except Exception as e:
        raise Exception(f'File: {file_path} - Info: {e}')
  
# from magic_pdf.tools.common import do_parse
# 修改的目的:
#   1、返回md_file_path
#   2、debug_able为True时，产生/保留所有中间处理结果,否则全部跳过
#   3、修改f_make_md_mode=MakeMode.NLP_MD（原来是MakeMode.MM_MD）
def do_parse(
    output_dir,
    pdf_file_name,
    pdf_bytes,
    model_list,
    parse_method,
    debug_able,
    f_draw_span_bbox=False,
    f_draw_layout_bbox=False,
    f_dump_md=True, #只有这个设置为True
    f_dump_middle_json=False,
    f_dump_model_json=False,
    f_dump_orig_pdf=False,
    f_dump_content_list=False,
    f_make_md_mode=MakeMode.NLP_MD,
    f_draw_model_bbox=False,
    f_draw_line_sort_bbox=False,
    start_page_id=0,
    end_page_id=None,
    lang=None,
    layout_model=None,
    formula_enable=None,
    table_enable=None,
):
    if debug_able:#如果debug_able=True，都会设为True
        logger.warning('debug mode is on')
        f_draw_model_bbox = True
        f_draw_line_sort_bbox = True
        f_draw_span_bbox=True,
        f_draw_layout_bbox=True,
        f_dump_md=True,
        f_dump_middle_json=True,
        f_dump_model_json=True,
        f_dump_orig_pdf=True,
        f_dump_content_list=True,

    orig_model_list = copy.deepcopy(model_list)
    local_image_dir, local_md_dir = prepare_env(output_dir, pdf_file_name, parse_method)
    image_writer, md_writer = DiskReaderWriter(
        local_image_dir), DiskReaderWriter(local_md_dir)
    image_dir = str(os.path.basename(local_image_dir))

    if parse_method == 'auto':
        jso_useful_key = {'_pdf_type': '', 'model_list': model_list}
        pipe = UNIPipe(pdf_bytes, jso_useful_key, image_writer, is_debug=True,
                       start_page_id=start_page_id, end_page_id=end_page_id, lang=lang,
                       layout_model=layout_model, formula_enable=formula_enable, table_enable=table_enable)
    elif parse_method == 'txt':
        pipe = TXTPipe(pdf_bytes, model_list, image_writer, is_debug=True,
                       start_page_id=start_page_id, end_page_id=end_page_id, lang=lang,
                       layout_model=layout_model, formula_enable=formula_enable, table_enable=table_enable)
    elif parse_method == 'ocr':
        pipe = OCRPipe(pdf_bytes, model_list, image_writer, is_debug=True,
                       start_page_id=start_page_id, end_page_id=end_page_id, lang=lang,
                       layout_model=layout_model, formula_enable=formula_enable, table_enable=table_enable)
    else:
        logger.error('unknown parse method')
        exit(1)

    pipe.pipe_classify()

    if len(model_list) == 0:
        if model_config.__use_inside_model__:
            pipe.pipe_analyze()
            orig_model_list = copy.deepcopy(pipe.model_list)
        else:
            logger.error('need model list input')
            exit(2)

    pipe.pipe_parse()
    pdf_info = pipe.pdf_mid_data['pdf_info']
    if f_draw_layout_bbox:
        draw_layout_bbox(pdf_info, pdf_bytes, local_md_dir, pdf_file_name)
    if f_draw_span_bbox:
        draw_span_bbox(pdf_info, pdf_bytes, local_md_dir, pdf_file_name)
    if f_draw_model_bbox:
        draw_model_bbox(copy.deepcopy(orig_model_list), pdf_bytes, local_md_dir, pdf_file_name)
    if f_draw_line_sort_bbox:
        draw_line_sort_bbox(pdf_info, pdf_bytes, local_md_dir, pdf_file_name)

    md_content = pipe.pipe_mk_markdown(image_dir,
                                       drop_mode=DropMode.NONE,
                                       md_make_mode=f_make_md_mode)
    if f_dump_md:
        md_writer.write(
            content=md_content,
            path=f'{pdf_file_name}.md',
            mode=AbsReaderWriter.MODE_TXT,
        )

    if f_dump_middle_json:
        md_writer.write(
            content=json_parse.dumps(pipe.pdf_mid_data,
                                     ensure_ascii=False,
                                     indent=4),
            path=f'{pdf_file_name}_middle.json',
            mode=AbsReaderWriter.MODE_TXT,
        )

    if f_dump_model_json:
        md_writer.write(
            content=json_parse.dumps(orig_model_list,
                                     ensure_ascii=False,
                                     indent=4),
            path=f'{pdf_file_name}_model.json',
            mode=AbsReaderWriter.MODE_TXT,
        )

    if f_dump_orig_pdf:
        md_writer.write(
            content=pdf_bytes,
            path=f'{pdf_file_name}_origin.pdf',
            mode=AbsReaderWriter.MODE_BIN,
        )

    content_list = pipe.pipe_mk_uni_format(image_dir, drop_mode=DropMode.NONE)
    if f_dump_content_list:
        md_writer.write(
            content=json_parse.dumps(content_list,
                                     ensure_ascii=False,
                                     indent=4),
            path=f'{pdf_file_name}_content_list.json',
            mode=AbsReaderWriter.MODE_TXT,
        )

    logger.info(f'local output dir is {local_md_dir}')
    md_file_path = f'{local_md_dir}/{pdf_file_name}.md'
    return md_file_path

class PredictionTimeLogger(ls.Callback):
    def on_before_predict(self, lit_api):
        t0 = time.perf_counter()
        self._start_time = t0

    def on_after_predict(self, lit_api):
        t1 = time.perf_counter()
        elapsed = t1 - self._start_time
        print(f"Prediction took {elapsed:.2f} seconds", flush=True)
        
class MinerUAPI(ls.LitAPI):
    def __init__(self, pdf_page_batch_size:int = 6):
        self.pdf_page_batch_size = pdf_page_batch_size

    def setup(self, device):
        if device.startswith('cuda'):
            os.environ['CUDA_VISIBLE_DEVICES'] = device.split(':')[-1]
            if torch.cuda.device_count() > 1:
                raise RuntimeError("Remove any CUDA actions before setting 'CUDA_VISIBLE_DEVICES'.")

        model_manager = ModelSingleton()
        model_manager.get_model(True, False)
        model_manager.get_model(False, False)
        print(f'Model initialization complete on {device}!')

    def decode_request(self, request):
        file_path = request['file']
        print(f"=====开始转换处理{file_path}=====")
        file_content = to_b64(str(file_path))
        file_content = self.to_pdf(file_content)
        opts = request.get('kwargs', {})
        opts.setdefault('debug_able', False)
        opts.setdefault('parse_method', 'auto')
        return file_content, opts,file_path

    def predict(self, inputs):
        print(f"{len(inputs)=}")        
        pdf_file_path = inputs[2]
        output_dir= os.path.dirname(pdf_file_path)
        file_name_with_extension = os.path.basename(pdf_file_path)
        pdf_name, extension = os.path.splitext(file_name_with_extension)
        
        try:
            md_file_path = do_parse(output_dir, pdf_name := pdf_name, inputs[0], [], **inputs[1])
            print(f"=====完成文件{pdf_file_path}的转换=====")
            return md_file_path
        
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            self.clean_memory()

    def encode_response(self, response):
        # print(response)
        return {'output_md_filepath': response}

    def clean_memory(self):
        import gc
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
        gc.collect()

    def to_pdf(self, file_base64):
        try:
            file_bytes = base64.b64decode(file_base64)
            file_ext = guess_extension(file_bytes)
            with fitz.open(stream=file_bytes, filetype=file_ext) as f:
                if f.is_pdf: return f.tobytes()
                return f.convert_to_pdf()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


if __name__ == '__main__':
    server = ls.LitServer(
        MinerUAPI(),
        accelerator='cuda',
        # devices='auto',
        devices=[0,1],
        # devices=[0],
        workers_per_device=1,
        callbacks=[PredictionTimeLogger()],
        track_requests=True,
        max_batch_size=1,
        batch_timeout=1,
        timeout=False
    )
    server.run(port=8889,log_level='debug')
