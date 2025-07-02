from __future__ import annotations
import os
import json,json_repair
import time
import asyncio
import requests
from pathlib import Path
from loguru import logger
# from docext.core.utils import convert_files_to_images
# from docext.core.utils import encode_image
# from docext.core.utils import validate_file_paths
from jqcode.jq_pdf2md.utils import convert_files_to_images,encode_image,validate_file_paths


def get_delta_time(input_time):
    return round(time.time() - input_time, 2)

def callback_with_time(task, start_time):
    _time = time.time() - start_time
    print(f"   .....{task.name}. Elapsed {_time:.2f}s")


start_tag="```markdown"
len_start_tag=len(start_tag)
end_tag="```"
len_end_tag=len(end_tag)
def process_tags(content: str) -> str:
    content = content.rstrip()
    content = content.lstrip()
    if content.startswith(start_tag):
        content = content[len_start_tag:]
    if content.endswith(end_tag):
        content = content[:-(len_end_tag)] 

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
        qwenvl_toc = img2md_request_for_vlm(messages, model_name="qwenvl", max_tokens=8000, temperature=0.0,vlm_url="http://10.1.150.105:8000/v1")
        # print(f"qwenvl:\n{qwenvl_toc}")
    except Exception as e:
        logger.error(f"Error extracting TOC: {e}")        
        try:
            nanonets_toc = img2md_request_for_vlm(messages)
            # print(f"nanonets:\n{nanonets_toc}")
        except Exception as e:
            logger.error(f"Error extracting TOC: {e}") 
    toc = qwenvl_toc or nanonets_toc   
    logger.info(f"\nExtracted TOC:\n{toc}")
    return toc

# todo: 补充完善非流式异步处理
def img2md_request_for_vlm(
    messages: list[dict],
    model_name: str="nanonets",
    vlm_url = os.getenv("VLM_MODEL_URL", "http://10.1.150.105:8008/v1"),
    max_tokens: int = 8000,
    temperature: float = 0.0,
    streaming:bool = True,
    
) -> str:
    """
    Make a streaming request to the vLLM server running on vlm_url
    """
    # vlm_url = "http://10.1.150.105:8000/v1" if model_name == "qwenvl" else vlm_url
    # Prepare the request payload
    payload = {
        "model": model_name,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": streaming,  # Enable streaming
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
                                        # content = process_tags(content)
                                        single_page_markdown_content += content
                        except json.JSONDecodeError:
                            continue
    except requests.exceptions.RequestException as e:
        logger.error(f"Error making streaming request: {e}")
        raise
    single_page_markdown_content = process_tags(single_page_markdown_content)
    return single_page_markdown_content
async def file2imgs_and_encode_images2base64(semaphore, file_input: str, concurrency_limit: int=32, max_img_size: int=1024) -> list[str]:
    """
    1.Convert file_input to images 
    2.Encode images to base64 in a process pool executor
    """
    convert_files_start_time = time.time()
    image_paths = convert_files_to_images([file_input], max_img_size,concurrency_limit)
    logger.info(f"Successfully converted '{Path(file_input).name}' to {len(image_paths)} image(s) in {get_delta_time(convert_files_start_time)} seconds")

    encode_images_start_time = time.time()
    async with semaphore:
        tasks = [asyncio.to_thread(encode_image,img_path) for img_path in image_paths]
        # tasks = [asyncio.create_task(encode_image(img_path)) for img_path in image_paths]
        encoded_images = await asyncio.gather(*tasks)

    logger.info(f"Successfully encoded '{Path(file_input).name}' {len(image_paths)} image(s) in {get_delta_time(encode_images_start_time)} seconds")
    return encoded_images,image_paths
async def convert_imgs_to_markdown(
    semaphore,file_name,encoded_images, model_name, vlm_url, concurrency_limit,mm_batch_size = 5, max_gen_tokens=16000
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
   

    logger.info(f"Converting '{file_name}' {len(encoded_images)} image(s) to markdown ......")

    # Accumulate results from all pages
    full_markdown_contents = []    
    tasks = []
    first_batch_prompt = """
                1.输入说明：这是一个PDF文档的前几页的连续页面图片。    
                2.首先是正常输出PDF转换成markdown格式的内容content
                3.除此之外，如果存在单独的文档目录部分(如Contents/Table of Contents/目录，通常还会有对应的页码)，还希望识别并输出文档的标题目录Table of Contents，且需识别或生成数字编号。
                示例格式如下，输出结果时请用识别出的标题目录Table of Contents替换这部分示例内容：
                -----------
                    # 0. 文档标题
                    ## 1. 第一章标题
                    ### 1.1 第一节标题
                    ### 1.2 第二节标题
                    #### 1.2.1. 三级标题1
                    #### 1.2.2. 三级标题2
                    ## 2. 第二章标题
                    ### 2.1 第一节标题
                    ### 2.2 第二节标题
                -----------

    """
    Subsequent_batch_prompt =  """
                - 多页连续页面图片，但第一张图片仅仅作为参考，方便你对照并正确提取后面图片的内容（保持与第一张内容的连贯和自然拼接）。
                - 所以千万记住：不要从第一张图片中生成如何内容，内容生成必须从第二张图片开始。"""
    
    async with semaphore:
        mm_batch_num =1 
        changed_mm_batch_size = mm_batch_size   #从第二批次开始，还是每次输入mm_batch_size张图片，但第一张是作为参考，不实际输出内容       
        for i in range(0, len(encoded_images), changed_mm_batch_size):
            start= i
            end= start + changed_mm_batch_size
            batch_encoded_images = encoded_images[start:end]
            
            if mm_batch_num == 1:
                multi_page_prompt = first_batch_prompt
            else:
                multi_page_prompt = Subsequent_batch_prompt
            
            user_prompt =f"""
            # PDF文档解析器规范 (Markdown/LaTeX输出)
            **角色：** 专业PDF解析器
            **输出：** 直接返回结构化Markdown内容（content）及文档目录Table of Contents（toc）
                    ** 输出格式为JSON格式，包含以下两个字段：
                        - content: 文档结构化Markdown内容
                        - toc: 文档目录Table of Contents,如果不存在，请保持为空字符串
            **原则：** 连续多页处理 | 保持原结构 | 内容优先于视觉 | 无解释性文字 | 语言与图中原语言保持一致，不要翻译  | 删除所有页眉、页脚、分页符和页码标记

            ## 转换规范
            1. **标题结构**
            - 严格使用 `# H1` → `## H2` → `### H3` 层级，还原原文档结构            
            2. **文本格式**
            - `**加粗**` `*斜体*` `~~删除线~~` `<u>下划线</u>`
            3. **列表**
            ```markdown
            - 无序列表
                * 嵌套项
                1. 有序列表
                1.1 嵌套项
            ```
            4. **表格**
            使用Markdown原生表格语法
            ```markdown
            | Header1 | Header2 | Header3 |
            | :------ | :-----: | ------: |
            | Left    | Center  | Right   |
            ```
            - 合并相邻但属于同一表格的多个表格（因分页等原因造成的）
            - 对于合并单元格等复杂结构，优先确保数据内容完整和逻辑关系清晰，可以牺牲视觉保真度
            5. **图片**
            - 不要输出图片链接，只输出图片OCR或图形描述文本结果，并使用<img>图片OCR或图形描述文本结果</img>标签来包裹。
                - 文字型图片：尝试提取图片中的核心文字信息
                - 图形类：    根据上下文和图片视觉内容，生成描述性替代文本
            - 忽略水印/背景图
            6. **数学公式**
            - 行内：`$E=mc^2$`
            - 独立块：
                    $$
                    \int_a^b f(x)dx
                    $$
                - 符号转换： 确保数学符号（希腊字母、运算符等）准确转换为LaTeX表示（如 \alpha, \times, \sum）和上下标转换准确
            7. **代码块**
            ```python
            print("语言标注") #代码内容
            ```
            - 未知语言：使用 ` ```text ` 或 ` ``` `
            8. **链接**
            `[显示文本](URL)` 保留锚链接(`#section`)
            9. **特殊处理**
            - 多语言：
                - 自动检测中/英/日/韩
                - RTL语言(阿拉伯语)：用`<div dir="rtl">文本</div>`包裹
            - 特殊字符：
                - 数学符号：→ LaTeX (`α`→`\alpha`)
                - 非数学：保留Unicode(`→⇒✔©®°C`)
                - 货币：保留原样(`¥€$£`)

            ## 多页处理
            - 一次会传入多个连续页面的图片
            - 按自然章节分割（检测标题/主题切换）
            - 确保不切断：表格/公式/代码块
            - 保持内容连贯性
            
            ## 多页处理特别说明{multi_page_prompt}

            ## 质量自检
            1. 标题层级准确性 ✓
            2. 表格数据完整性 ✓
            3. 公式符号正确性 ✓
            4. 代码语言标注 ✓
            5. 图片替代文本描述性 ✓
            6. 多页衔接自然度 ✓
            7. 特殊字符处理合规 ✓
        """
            # pass
            # if mm_batch_num>1:
            #     pass



            contents = [{"type": "text", "text": user_prompt}]

            
                        
            for encoded_image in batch_encoded_images:
                contents.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{encoded_image}"
                        }
                    }
                )

            messages = [{"role": "user", "content": contents}]
            task = asyncio.create_task(asyncio.to_thread(img2md_request_for_vlm,messages, model_name, vlm_url, max_gen_tokens))
            task.name = f"File('{file_name}')[Imgs({start}-{start + len(contents)-1}, {len(contents)}imgs/mm_batch) In MmBatch({mm_batch_num})] converted to markdowns"
            start_time = time.time()
            task.add_done_callback(lambda task:  callback_with_time(task, start_time))
            tasks.append(task)
            contents = []
            mm_batch_num += 1
        
    full_markdown_contents = await asyncio.gather(*tasks)

    texts=[]
    tocs = []
    for batch_content_with_toc in full_markdown_contents:
        if batch_content_with_toc.startswith("```json"):
            first_batch_content_with_toc_dict = json_repair.loads(batch_content_with_toc)
            toc = first_batch_content_with_toc_dict.get("toc", "")
            text = first_batch_content_with_toc_dict.get("content", "")
            if toc:
                tocs.append(toc)            
                text = toc + "\n======TOC分割======\n" + text
        else:
            text = batch_content_with_toc
        texts.append(text)
        
    
    text_string = "\n======页面分割======\n".join(texts)
    return text_string
async def convert_file_to_markdown(
    semaphore,file_path, model_name, vlm_url, max_img_size, concurrency_limit, mm_batch_size = 5, max_gen_tokens=16000
):
    """
    Non-streaming version for backward compatibility
    """
    encoded_images,_ = await file2imgs_and_encode_images2base64(semaphore,file_path, concurrency_limit, max_img_size)
    start_time = time.time()
    file_name = Path(file_path).name
    task = asyncio.create_task(convert_imgs_to_markdown(semaphore,file_name,encoded_images, model_name, vlm_url, concurrency_limit,mm_batch_size, max_gen_tokens))
    # file2md_result = await asyncio.gather(*[task])
    file2md_result = await asyncio.gather(task)
    logger.info(f">>> Successfully converted document['{file_name}'] to markdown file. Elapsed:{get_delta_time(start_time)}(seconds).")
    return file2md_result
async def convert_files_to_markdowns(
    file_inputs, model_name, vlm_url, max_img_size=16000, concurrency_limit=32, mm_batch_size = 5, max_gen_tokens=16000
):
    
    file_paths: list[str] = [
        file_input[0] if isinstance(file_input, tuple) else file_input
        for file_input in file_inputs
    ]
    validated_file_paths = validate_file_paths(file_paths)
    validated_file_num = len(validated_file_paths)
    logger.info(f"File_Inputs: {len(file_paths)} , Validated_File_Inputs: {validated_file_num}")
    logger.info(f"Converting {validated_file_num} validated files to markdowns")
    logger.info(f"\n    ====调用参数 [{model_name=},{vlm_url=},{concurrency_limit=},{mm_batch_size=},{max_gen_tokens=}] 调用参数====")
    start_time_all = time.time()    

    tasks = []
    loop = asyncio.get_running_loop()
    # loop.set_debug(True)
    semaphore = asyncio.Semaphore(concurrency_limit)
    for i,file_path in enumerate(file_paths,1):
        task = asyncio.create_task(convert_file_to_markdown(
            semaphore,
            file_path,
            model_name,
            vlm_url, 
            max_img_size,                
            concurrency_limit,
            mm_batch_size,
            max_gen_tokens
        )
        )
            
        file_start_time = time.time()
        # task.name = f"File({i}):{Path(file_path).name} has converted to markdowns"
        # task.add_done_callback(lambda task:  callback_with_time(task, file_start_time))
        tasks.append(task)

    all_file2md_results = await asyncio.gather(*tasks)
    logger.info(f" Successfully converted all files to markdowns. Total Times:{get_delta_time(start_time_all)}(seconds)")
    return all_file2md_results  

if __name__ == "__main__":

    """
    workon vllmb
    CUDA_VISIBLE_DEVICES=0 vllm serve /data/models/OCRFlux-3B --enable-chunked-prefill --port 8008 --host 0.0.0.0 --served-model-name=nanonets --max-num-seqs 32 --limit-mm-per-prompt image=6,video=1
    """
    """
    workon vllmb
    CUDA_VISIBLE_DEVICES=0 vllm serve /data/models/Nanonets-OCR-s/ --enable-chunked-prefill --port 8008 --host 0.0.0.0 --served-model-name=nanonets --max-num-seqs 32 --limit-mm-per-prompt image=6,video=1
    """
    file_inputs = ["/data/projects/JqChatV2/JqChat/docext/晶奇招股说明书.pdf"]
    # file_inputs += ["/data/projects/JqChatV2/JqChat/JqR2R/py/core/examples/supported_file_types/pdf.pdf"]
    # file_inputs += ["/data/projects/JqChatV2/JqChat/JqR2R/py/core/examples/data/DeepSeek_R1.pdf"]
    file_inputs = ["/data/projects/JqChatV2/JqChat/JqR2R/py/core/examples/data/DeepSeek_R1.pdf"]
    file_inputs += ["/data/projects/JqChatV2/JqChat/JqR2R/py/core/examples/supported_file_types/pdf.pdf"]
    

    start_time = time.time()
    model_name = "qwenvl"  # or "nanonets"
    model_name = "nanonets"
    concurrency_limit = 40 if model_name == "qwenvl" else 40
    vlm_url= "http://10.1.150.105:8000/v1" if model_name == "qwenvl" else os.getenv("VLM_MODEL_URL", "http://10.1.150.105:8008/v1")
    coro_all_files_results = convert_files_to_markdowns(
        file_inputs,
        model_name=model_name,
        vlm_url=vlm_url,
        max_img_size=1024,
        concurrency_limit=concurrency_limit,
        mm_batch_size = 5, 
        max_gen_tokens=16000
    )

    all_files_results = asyncio.run(coro_all_files_results)
    pass

    print(len(all_files_results))
    for i,file_result in enumerate(all_files_results):
        file_path = file_inputs[i]
        ext = Path(file_path).suffix
        # file_markdown_contents = file_result[file_path]
        file_markdown_contents = file_result
        md_file_path = file_path.replace(ext, ".md")
        texts = '\n\n'.join(file_markdown_contents)
        
        
        with open(md_file_path, 'w', encoding='utf-8') as file:
            file.write(texts)
            logger.info(f"Successfully saved markdown file to '{md_file_path}'")
