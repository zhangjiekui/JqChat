import time
import base64
import subprocess,os
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor as Pool
from multiprocessing import BoundedSemaphore
from jqcode.jq_readers.backend_reader_utils.pyemf3project.pyemf3 import EMF
from jqcode.jq_readers.backend_reader_utils.pyemf3project.pyemf3.emr import EXTTEXTOUTW
from jqcode.jq_agent.c0_init_env_models import env_models_instance
from jqcode.jq_utils.logger import jqkj_logger,is_main_process
logger = jqkj_logger(__file__).get_logger()



# _separator = ' '
# ocr_result,_  =ocr("/data/projects/JqChatV2/JqChat/jqcode/jq_readers/.test_files/.testinputdocs/厦门市智慧民政一体化平台项目建设方案 V3.6/_diffs/image1.png")
# if ocr_result:
#     ocr_texts = [line[1].strip() for line in ocr_result if line[1].strip()]
#     #分隔符最好选用jqcode/jq_splitters/backend_splitter_utils/jq_chinese_recursive_text_splitter.py的第98行定义的
#     result = _separator.join(ocr_texts) 
#     logger.debug(f"$$图片中的OCR文本:\n{result}")
emf = EMF() #处理emf图片需要的

def treenode_img_to_text(img_src_and_data_tuple_list:tuple,delete_emf_wmf_png_file=True):
    ocr = env_models_instance.get_ocr()
    ocr_mode = env_models_instance.ocr_mode
    png_file = ''   
    result = ''
    #分隔符最好选用jqcode/jq_splitters/backend_splitter_utils/jq_chinese_recursive_text_splitter.py的第98行定义的
    _separator = ' '
    img_src,img_data=img_src_and_data_tuple_list
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
                logger.debug(f"$$图片[{img_src}]中的EMF/WMF文本:\n{result}")
            except Exception as e:
                logger.debug(f"无法加载EMF/WMF图片[{img_src}]:{e}")
                logger.debug(f"尝试转换成.png文件，再OCR识别")
                try:
                    temp_working_dir = env_models_instance.abs_workspace+fr"/temp/temp_emf_wmf_files/"
                    if not os.path.exists(temp_working_dir):
                        os.makedirs(temp_working_dir, exist_ok=True)

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
                        if ocr_mode == "API":
                            result = ocr(png_file)
                            logger.debug(f"$$图片[{img_src}]中的OCR文本:\n{result}") 
                        else:
                            ocr_result,_ = ocr(png_file) 
                            if ocr_result:
                                ocr_texts = [line[1].strip() for line in ocr_result if line[1].strip()]
                                #分隔符最好选用jqcode/jq_splitters/backend_splitter_utils/jq_chinese_recursive_text_splitter.py的第98行定义的
                                result = _separator.join(ocr_texts) 
                                logger.debug(f"$$图片[{img_src}]中的OCR文本:\n{result}")
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
            if ocr_mode == "API":
                result= ocr(img_data)
                logger.debug(f"$$图片[{img_src}]中的OCR文本:\n{result}")
            else: 
                ocr_result,_ = ocr(img_data) 
                if ocr_result:
                    ocr_texts = [line[1].strip() for line in ocr_result if line[1].strip()]
                    #分隔符最好选用jqcode/jq_splitters/backend_splitter_utils/jq_chinese_recursive_text_splitter.py的第98行定义的
                    result = _separator.join(ocr_texts) 
                    logger.debug(f"$$图片[{img_src}]中的OCR文本:\n{result}")
    except Exception as e:
        logger.warning(f'获取图片[{img_src}]中的文本失败,详细信息为{e}')
    result = f"【{img_src}的OCR文本】"+ result
    return result

def treenodes_img_to_text_in_batch(img_src_and_data_tuple_list, processes=10):
    # 过滤掉 gif 图片
    filtered_img_src_and_data_tuple_list = [
        item for item in img_src_and_data_tuple_list 
        if not item[0].lower().endswith('.gif')
    ]

    img_nums = len(filtered_img_src_and_data_tuple_list)
    processes = min(img_nums,processes)      
    
    pool = env_models_instance.get_ocr_pool() 
    semaphore = BoundedSemaphore(processes) 
    with semaphore:
        results = pool.map(treenode_img_to_text,filtered_img_src_and_data_tuple_list)     
    results = list(results)       
    return results

if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    import paddle
    print(paddle.utils.run_check())
    pass
# 如果出现PaddlePaddle is installed successfully!，说明您已成功安装。








