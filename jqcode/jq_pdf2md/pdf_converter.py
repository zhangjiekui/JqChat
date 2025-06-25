from __future__ import annotations
import time
import timeit
import os
import tempfile
from typing import Optional

from pdf2image import convert_from_path

# from docext.core.file_converters.file_converter import FileConverter

output_folder="/data/projects/JqChatV2/JqChat/docext/output_imgs"

def get_delta_time(input_time):
    return round(time.time() - input_time, 2)
class PDFConverter:
# class PDFConverter(FileConverter):
    def convert_to_images(self, file_path: str,max_img_size: Optional[int] = 1024, concurrency_limit: int=32):
        return convert_from_path(file_path,dpi=160, fmt='png', thread_count=concurrency_limit, use_pdftocairo=True,size=(max_img_size, max_img_size))

    def convert_and_save_images(self, file_path: str, output_folder: str | None = output_folder):
        
        start_time = time.time()
        if not output_folder:
            # set tmp folder as output folder
            output_folder = tempfile.gettempdir()
        os.makedirs(output_folder, exist_ok=True)
        # save images to output folder
        output_file_paths = []
        images = self.convert_to_images(file_path)
        for i, image in enumerate(images, start=1):
            output_file_path = os.path.join(output_folder, f"page_{i}.png")
            image.save(output_file_path)
            output_file_paths.append(output_file_path)

        _time = get_delta_time(start_time)
        print(f"文件{file_path}共有{len(output_file_paths)}页，转换成imags保存到{output_folder}，耗时{_time}秒")
        return output_file_paths
    

if __name__ == "__main__":
    pdf_converter = PDFConverter()
    file_path = "/data/projects/JqChatV2/JqChat/JqR2R/py/core/examples/data/DeepSeek_R1.pdf"
    file_path = "/data/projects/JqChatV2/JqChat/docext/晶奇招股说明书.pdf"
    output_file_paths = pdf_converter.convert_and_save_images(file_path)
