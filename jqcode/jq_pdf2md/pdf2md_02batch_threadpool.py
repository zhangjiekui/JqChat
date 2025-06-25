from __future__ import annotations

import os
import json
import time
import asyncio
import requests
from pathlib import Path

from loguru import logger

from collections.abc import Generator,AsyncGenerator
from concurrent.futures import ThreadPoolExecutor,ProcessPoolExecutor

# from docext.core.utils import convert_files_to_images
# from docext.core.utils import encode_image
# from docext.core.utils import validate_file_paths

from jqcode.jq_pdf2md.utils import convert_files_to_images,encode_image,validate_file_paths


def get_delta_time(input_time):
    return round(time.time() - input_time, 2)
def process_tags(content: str) -> str:
    content = content.replace("<img>", "&lt;img&gt;")
    content = content.replace("</img>", "&lt;/img&gt;")
    content = content.replace("<watermark>", "&lt;watermark&gt;")
    content = content.replace("</watermark>", "&lt;/watermark&gt;")
    content = content.replace("<page_number>", "&lt;page_number&gt;")
    content = content.replace("</page_number>", "&lt;/page_number&gt;")
    content = content.replace("<signature>", "&lt;signature&gt;")
    content = content.replace("</signature>", "&lt;/signature&gt;")

    return content
def extract_toc_from_first_n_pages(encode_images: list[str], first_n_pages: int=5) -> str:
    """
    Extract Table of Contents (TOC) from the first 5 pages of a PDF file.
    This is a placeholder function and should be implemented based on your requirements.
    """
    first_n_encode_images_ = encode_images[:first_n_pages]
    user_prompt = """从以下页面中提取并返回markdown格式的标题目录（Table of Contents），注意：仅仅返回标题目录，不需要任何额外的正文内容。示例格式如下：
    # 文档标题
    ## 1. 第一章标题
    ### 1.1 第一节标题
    ### 1.2 第二节标题
    ## 2. 第二章标题
    ### 2.1 第一节标题
    ### 2.2 第二节标题    
    """
    contents = []
    for encode_image in first_n_encode_images_:
        new_image = {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encode_image}"}}
        contents.append(new_image)
    
    contents.append({"type": "text", "text": user_prompt})

    messages = [{
        "role": "user",
        "content": contents
    }]

    # logger.warning(f"extract_toc_from_first_n_pages:{type(messages)=}, {len(messages)=}")
    toc = ''
    qwenvl_toc = ''
    nanonets_toc = ''
    try:
        qwenvl_toc = stream_request(messages, model_name="qwenvl", max_tokens=8000, temperature=0.0,vlm_url="http://10.1.150.105:8000/v1")
        # print(f"qwenvl:\n{qwenvl_toc}")
    except Exception as e:
        logger.error(f"Error extracting TOC: {e}")        
        try:
            nanonets_toc = stream_request(messages)
            # print(f"nanonets:\n{nanonets_toc}")
        except Exception as e:
            logger.error(f"Error extracting TOC: {e}") 
    toc = qwenvl_toc or nanonets_toc   
    logger.info(f"\nExtracted TOC:\n{toc}")
    return toc


def stream_request(
    messages: list[dict],
    model_name: str="nanonets",
    vlm_url = os.getenv("VLM_MODEL_URL", "http://10.1.150.105:8008/v1"),
    max_tokens: int = 8000,
    temperature: float = 0.0
    
) -> str:
    """
    Make a streaming request to the vLLM server running on vlm_url
    """
    # vlm_url = "http://10.1.150.105:8000/v1" if model_name == "qwenvl" else vlm_url
    # Prepare the request payload
    payload = {
        "model": model_name.replace("hosted_vllm/", ""),
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": True,  # Enable streaming
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.getenv('API_KEY', 'abc123')}",
    }

    # Make streaming request
    url = f"{vlm_url}/chat/completions"
    single_page_markdown_content = ""
    
    try:
        with requests.post(url, json=payload, headers=headers, stream=True) as response:
            response.raise_for_status()
            # logger.warning(f"stream_request:{type(messages)=}, {len(messages)=}")

            for line in response.iter_lines():
                if line:
                    line = line.decode("utf-8")
                    if line.startswith("data: "):
                        data = line[6:]  # Remove 'data: ' prefix
                        if data.strip() == "[DONE]":
                            break
                        try:
                            json_data = json.loads(data)
                            if "choices" in json_data and len(json_data["choices"]) > 0:
                                choice = json_data["choices"][0]
                                if "delta" in choice and "content" in choice["delta"]:
                                    content = choice["delta"]["content"]
                                    if content:
                                        single_page_markdown_content += content
                        except json.JSONDecodeError:
                            continue
    except requests.exceptions.RequestException as e:
        logger.error(f"Error making streaming request: {e}")
        raise
    single_page_markdown_content = process_tags(single_page_markdown_content)
    return single_page_markdown_content

def file2imgs_and_encode_images_in_thread_pool_executor(file_input: str, concurrency_limit: int=32, max_img_size: int=1024) -> list[str]:
    """
    1.Convert file_input to images 
    2.Encode images to base64 in a process pool executor
    """
    convert_files_start_time = time.time()
    img_paths = convert_files_to_images([file_input], max_img_size)
    logger.info(f"Successfully converted '{file_input}' to {len(img_paths)} image(s) in {get_delta_time(convert_files_start_time)} seconds")

    encode_images_start_time = time.time()

    with ThreadPoolExecutor(max_workers=concurrency_limit) as executor:
        tasks = [executor.submit(encode_image, img_path) for img_path in img_paths]
        encoded_images = [task.result() for task in tasks]
    logger.info(f"Successfully encoded {len(img_paths)} image(s) in {get_delta_time(encode_images_start_time)} seconds")
    return encoded_images

# encoded_images = file2imgs_and_encode_images_in_thread_pool_executor(
#     "/data/projects/JqChatV2/JqChat/JqR2R/py/core/examples/data/DeepSeek_R1.pdf",
#     concurrency_limit=32,
#     max_img_size=1024
# )
# print(len(encoded_images))
# extract_toc_from_first_n_pages(encoded_images, first_n_pages=1)


async def convert_to_markdown_in_pool_executor(
    encoded_images, model_name, vlm_url, concurrency_limit, max_gen_tokens
):
    """
    Get markdown conversion results
    """
    toc = ''
    try:
        pass
        # toc = extract_toc_from_first_n_pages(encoded_images, first_n_pages=5)
    except Exception as e:
        logger.error(f"Error extracting TOC: {e}")
        
    if toc:
        toc_prompt = f"请正确地提取和输出文档中的标题目录（Table of Contents）和正文内容，忽略页眉页脚页码等内容，其中的标题目录格式/级别要与下面的标题目录保持一致\n-----\n{toc}\n-----\n"
    else:
        toc_prompt = "请识别图片全部内容，并将内容转换成markdown文档，特别要注意正确地输出文档中的标题目录（包括格式/级别）和正文内容，忽略页眉页脚页码等内容"

    # Create system prompt for PDF to markdown conversion
    # user_prompt = f"""Extract the text from the above document as if you were reading it naturally.
    # {toc_prompt} 
    # Return the tables in html format. 
    # Watermarks should be wrapped in brackets. Ex: <watermark>OFFICIAL COPY</watermark>. 
    # Page numbers should be wrapped in brackets. Ex: <page_number>14</page_number> or <page_number>9/22</page_number>. Prefer using ☐ and ☑ for check boxes.
    # """

    user_prompt = f"""{toc_prompt}
    请注意这是多页连续的文档，要确保页面内容以合适的方式来连接和合并。
    如果碰到内嵌的图片/图形，请优先考虑作为一个OCR任务来处理，否则作为图片描述任务，如果图片与上下文关系不大（如背景图片或水印等），请忽略。注意仅输出图片OCR或图片描述文本结果，请勿输出图片链接。
    Extract the text from the above document as if you were reading it naturally.     
    Return the results in markdown format, but no ``` ```markdown or ```html tags.
    Prefer using ☐ and ☑ for check boxes.
    """

    logger.info(f"Converting {len(encoded_images)} image(s) to markdown using [{model_name=},{vlm_url=}] (Processing in ThreadPoolExecutor(max_workers={concurrency_limit}))")

    # Accumulate results from all pages
    full_markdown_contents = []

    loop = asyncio.get_running_loop()
    tasks = []
    with ThreadPoolExecutor(max_workers=concurrency_limit) as executor:
        for i, encoded_image in enumerate(encoded_images):     

            # Build messages for this single image
            content = [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{encoded_image}"
                    },
                },
                {"type": "text", "text": user_prompt},
            ]

            if len(encoded_images) == 5 or i < len(encoded_images) - 1:
                # content.append({"type": "text", "text": f"这是第{i + 1}页，共{len(encoded_images)}页"})
                messages = [{"role": "user", "content": content}]
                task=loop.run_in_executor(executor, stream_request, messages,model_name, vlm_url,max_gen_tokens)
            tasks.append(task)
        
    full_markdown_contents = await asyncio.gather(*tasks)
    return full_markdown_contents
async def convert_file_to_markdown(
    encoded_images, model_name, vlm_url, concurrency_limit, max_gen_tokens
):
    """
    Non-streaming version for backward compatibility
    """

    # start_time = time.time()
    final_results = await convert_to_markdown_in_pool_executor(encoded_images, model_name, vlm_url, concurrency_limit, max_gen_tokens)
    logger.info(f"Successfully completed document conversion")
    return final_results

def convert_files_to_markdowns(
    file_inputs, model_name, vlm_url, max_img_size, concurrency_limit, max_gen_tokens
):
    start_time = time.time()
    file_paths: list[str] = [
        file_input[0] if isinstance(file_input, tuple) else file_input
        for file_input in file_inputs
    ]
    validate_file_paths(file_paths)
    all_files_results = []
    for file_path in file_paths:
        logger.info(f"==Begin==============='{file_path}'=================")
        start_time = time.time()
        logger.info(f"Converting file '{file_path}' to markdown using [{model_name=},{vlm_url=}]")
        encoded_images = file2imgs_and_encode_images_in_thread_pool_executor(
            file_path, concurrency_limit=concurrency_limit, max_img_size=max_img_size
        )
        final_results = asyncio.run(
            convert_file_to_markdown(
                encoded_images,
                model_name,
                vlm_url,
                concurrency_limit,
                max_gen_tokens,
            )
        )
        logger.info(f"Successfully completed document['{file_path}'] conversion to markdown file  in {get_delta_time(start_time)} seconds")
        logger.info(f"==End==============='{file_path}'=================")
        all_files_results.append({file_path:final_results})
    return all_files_results  





if __name__ == "__main__":


    """
    workon vllm
    vllm serve /data/models/Nanonets-OCR-s/ --enable-chunked-prefill --port 8008 --host 0.0.0.0 --served-model-name=nanonets --max-num-seqs 32 --limit-mm-per-prompt image=5,video=1
    """

    file_inputs = ["/data/projects/JqChatV2/JqChat/JqR2R/py/core/examples/supported_file_types/pdf.pdf"]
    file_inputs += ["/data/projects/JqChatV2/JqChat/JqR2R/py/core/examples/data/DeepSeek_R1.pdf"]
    file_inputs += ["/data/projects/JqChatV2/JqChat/docext/晶奇招股说明书.pdf"]

    start_time = time.time()
    # model_name = "qwenvl"  # or "nanonets"
    model_name = "nanonets"
    concurrency_limit = 16 if model_name == "qwenvl" else 32
    vlm_url= "http://10.1.150.105:8000/v1" if model_name == "qwenvl" else os.getenv("VLM_MODEL_URL", "http://10.1.150.105:8008/v1")
    all_files_results = convert_files_to_markdowns(
        file_inputs,
        model_name=model_name,
        vlm_url=vlm_url,
        max_img_size=1024,
        concurrency_limit=concurrency_limit,
        max_gen_tokens=16000,
    )
    logger.info(f"total time: {get_delta_time(start_time)} seconds")
    # print(all_files_results)
    for file_result in all_files_results:
        file_path = list(file_result.keys())[0]
        ext = Path(file_path).suffix
        file_markdown_contents = file_result[file_path]
        
        md_file_path = file_path.replace(ext, ".md")
        texts = '\n\n'.join(file_markdown_contents)
        
        
        with open(md_file_path, 'w', encoding='utf-8') as file:
            file.write(texts)
            logger.info(f"Successfully saved markdown file to '{md_file_path}'")
