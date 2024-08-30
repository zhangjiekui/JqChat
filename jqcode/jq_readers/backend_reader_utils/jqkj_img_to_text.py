import multiprocessing,subprocess,os
from pathlib import Path
from rapidocr_onnxruntime import RapidOCR
# from rapidocr_paddle import RapidOCR # For GPU
from jqcode.jq_readers.backend_reader_utils.pyemf3project.pyemf3 import EMF
from jqcode.jq_readers.backend_reader_utils.pyemf3project.pyemf3.emr import EXTTEXTOUTW
from jqcode.jq_utils.logger import jqkj_logger
from jqcode.jq_agent.c0_init_env_models import env_models_instance
logger = jqkj_logger(__file__).get_logger()

ocr = RapidOCR()
emf = EMF() #处理emf图片需要的

_cpu_nums = multiprocessing.cpu_count()
cpu_nums_for_img_ocr = int(_cpu_nums*0.7)

def treenode_img_to_text(img_src_and_data_tuple:tuple,delete_emf_wmf_png_file=True):
    result = ''
    #分隔符最好选用jqcode/jq_splitters/backend_splitter_utils/jq_chinese_recursive_text_splitter.py的第98行定义的
    _separator = ' '
    img_src,img_data=img_src_and_data_tuple
    try:
        if img_src.endswith(('.emf','.wmf')):
            try:
                emf.loadmem(img_data)
                recs = emf.records
                for rec in recs:
                    if isinstance(rec, EXTTEXTOUTW):
                        _text = rec.values['string'].strip()
                        if _text:
                            result += _separator + _text
                # logger.debug(f"图片[{img_src}]中的EMF/WMF文本:\n{result}")
            except Exception as e:
                logger.debug(f"无法加载EMF/WMF图片[{img_src}]:{e}")
                logger.debug(f"尝试转换成.png文件，再OCR识别")
                try:
                    temp_working_dir = env_models_instance.workspace+fr"/tem_emf_wmf_files/"
                    if not os.path.exists(temp_working_dir):
                        os.mkdir(temp_working_dir)

                    emf_wmf_file= temp_working_dir+img_src
                    with open(emf_wmf_file,'wb') as f:#保存图片
                        f.write(img_data)
                    convert_result = subprocess.check_call([
                        "libreoffice",
                        "--headless",
                        "--convert-to",
                        "png",
                        emf_wmf_file,
                        "--outdir",
                        temp_working_dir,
                    ])
                    if convert_result == 0: #代表转换成功
                        png_file = temp_working_dir + Path(emf_wmf_file).stem + ".png"
                        ocr_result,_ = ocr(png_file) 
                        if ocr_result:
                            ocr_texts = [line[1].strip() for line in ocr_result if line[1].strip()]
                            #分隔符最好选用jqcode/jq_splitters/backend_splitter_utils/jq_chinese_recursive_text_splitter.py的第98行定义的
                            result = _separator.join(ocr_texts) 
                            # logger.debug(f"图片[{img_src}]中的OCR文本:\n{result}")
                    else:
                        logger.error(f"尝试转换成.png文件失败!")
                except:
                    logger.error(f"尝试转换成.png文件，再OCR识别,也失败了:{e}")
                    # Linux下 emf/wmf图像中文字乱码解决办法
                    # 参考来源 LibreOffice完美解决中文字体问题 https://www.bilibili.com/read/cv21916382/
                    # 操作方法
                    # 1. 在Windows上面找到需要的字体 位置C:\Windows\Fonts
                    # 2. 将Fonts整个文件目录拷贝到Ubuntu系统中/usr/share/fonts/的目录下（得到的目录结果为/usr/share/fonts/Fonts）
                    # 下面是可选测试步骤：
                    # 3. 关闭再重新打开LibreOffice，测试能否看到中文字体
                    # 4. 在LibreOffice中新建文档，插入emf图片，是否显示正常
                    # 5. 转换libreoffice --headless --convert-to png "emf路径文件名"
                finally:
                    if delete_emf_wmf_png_file:
                        if os.path.exists(emf_wmf_file):
                            os.remove(emf_wmf_file)
                        if os.path.exists(png_file):
                            os.remove(png_file)                            



        else:                    
            ocr_result,_ = ocr(img_data)
            if ocr_result:
                ocr_texts = [line[1].strip() for line in ocr_result if line[1].strip()]
                #分隔符最好选用jqcode/jq_splitters/backend_splitter_utils/jq_chinese_recursive_text_splitter.py的第98行定义的
                result = _separator.join(ocr_texts) 
                # logger.debug(f"图片[{img_src}]中的OCR文本:\n{result}")
    except Exception as e:
        logger.warning(f'获取图片[{img_src}]中的文本失败,详细信息为{e}')
    result = f"【{img_src}的OCR文本】"+ result
    return result

def treenodes_img_to_text_in_batch(img_src_and_data_tuple_list, processes=None):
    if processes:
        processes = min(processes,cpu_nums_for_img_ocr)
    else:
        processes = cpu_nums_for_img_ocr
    processes = min(len(img_src_and_data_tuple_list),processes)
    logger.debug(f"~~~~~~~~~~~~~~~treenodes_img_to_text_in_batch进程池数量为{processes}~~~~~~~~~~~~~~~")
    with multiprocessing.Pool(processes) as p:
        results = p.map(treenode_img_to_text,img_src_and_data_tuple_list)
    logger.debug(f"~~~~~~~~~~~~~~~treenodes_img_to_text_in_batch进程池数量为{processes}~~~~~~~~~~~~~~~")
    return results





