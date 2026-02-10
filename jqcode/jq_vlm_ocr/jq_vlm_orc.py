import os
import json
import base64
import requests
from pathlib import Path
from openai import OpenAI
import json_repair
from jqcode.jq_splitters.jq_docx_tree_text_splitter import load_project_env
from jqcode.jq_utils.logger import jqkj_logger
logger = jqkj_logger(__file__).get_logger()

class Vlm_API:
    def __init__(self,api_base:str = "http://10.1.150.105:3000/v1",api_key:str='0S7bV3oaznhuevN899Db0cDa20Ae4c5485Ce5862A86063C8',model:str="qwenvl"):
        self.env_loaded = load_project_env()
        if self.env_loaded:
            VLM_MODEL_CARD = os.getenv("VLM_MODEL_CARD", "") 
            VLM_MODEL_CARD = json_repair.loads(VLM_MODEL_CARD)
            api_base = VLM_MODEL_CARD.get("base_url",api_base)
            api_key = VLM_MODEL_CARD.get("api_key",api_key)
            model = VLM_MODEL_CARD.get("name",model)
        self.api_base = api_base
        self.api_key = api_key
        self.model = model
        self.client = OpenAI(api_key=api_key,base_url=api_base)
        self.default_ocr_prompt = "首先识别出有意义的区块，然后逐个区块完整识别并仅输出图中的文字（相当于ocr，去掉不必要的换行符，但保留必要的空格，使用‘||’分割文本块，如果基本不存在文本，则请输出图片描述）。最后仅输出完整的文本，不要有任何额外的内容和解释。"
        # 请识别出发票中的购买方 名称（keyname:gmf）、销售方 名称（keyname:xsf）、销售项目名称 （keyname:item）、发票类型（keyname:type，取值为普通发票或专用发票）。以Json形式返回，使用括号中的keyname代替中文名称，不要有多余内容

    def __call__(self,image_path_or_base64:str,is_decoded_image_text:bool=False,query:str=None,only_return_text=True):
        ## 如果是图片地址，读取图片并转换为base64
        if not query:
            query = self.default_ocr_prompt
        if is_decoded_image_text:
            encoded_image_text = image_path_or_base64
        else:
            if isinstance(image_path_or_base64,str): 
                if os.path.isfile(image_path_or_base64):
                    with open(image_path_or_base64, 'rb') as f:
                        image_path_or_base64 = f.read()
                else:
                    raise Exception(f"{image_path_or_base64}文件不存在！")
            elif isinstance(image_path_or_base64, bytes):
                pass
            else:
                raise Exception(f"目前只接受str或bytes类型的参数，不支持：{type(image_path_or_base64)=}")               
            encoded_data = base64.b64encode(image_path_or_base64)
            encoded_image_text = encoded_data.decode('utf-8')
        base64_qwen = f"data:image;base64,{encoded_image_text}"

        try:
            chat_response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                            {"role": "system", "content": "You are a helpful assistant."},
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": base64_qwen
                                        },
                                    },
                                    {"type": "text", "text": query},
                                ],
                            },
                            ],
                        )  
            logger.info(f"Chat response:\n{chat_response}")
            if only_return_text:
                text = chat_response.choices[0].message.content
                text = text.replace('\n', ' ')
                return text
            else:
                return chat_response
             
        except Exception as e:
            logger.error(f"请求错误: {str(e)}")
            return ''
        
class PaddleOCR_VL_API:
    def __init__(self,vllm_rec_server_url="http://192.168.44.222:8118/v1",paddelocrvl_rec_server_url="http://192.168.44.222:8000/v2",paddelocr_vl_rec_server_pipeline="/models/layout-parsing/infer",bool_test_both_server=True):
        self.exclude_img_keywords = ["<img src", "alt"]
        self.vllm_rec_server_url = vllm_rec_server_url
        self.paddelocrvl_rec_server_url = paddelocrvl_rec_server_url

        self.paddelvllm_pipeline = None
        self.paddelocrvl_server_string = None

        health_check_url = vllm_rec_server_url.replace("v1", "health")
        if requests.get(health_check_url).status_code == 200:
            from paddleocr import PaddleOCRVL
            self.paddelvllm_pipeline = PaddleOCRVL(vl_rec_backend="vllm-server", vl_rec_server_url=vllm_rec_server_url,use_layout_detection=False,
                                                   layout_nms=True,layout_merge_bboxes_mode="large",use_doc_unwarping=True,use_doc_orientation_classify=True)
        else:
            logger.warning(f"{vllm_rec_server_url}服务未在运行！")        
        # if bool_test_both_server:
            if requests.get(paddelocrvl_rec_server_url).status_code == 200:
                self.paddelocrvl_server_string = paddelocrvl_rec_server_url + paddelocr_vl_rec_server_pipeline
            else:
                logger.warning(f"{paddelocrvl_rec_server_url}服务未在运行！")
        


    def call_vllm_pipeline(self,image_path_or_url:str,only_return_text=True):
        output = self.paddelvllm_pipeline.predict(image_path_or_url)
        if only_return_text:
            result_text_list = []
            all_texts = ""
            for res in output:
                text = res.markdown.get("markdown_texts","")
                lines = [line.strip("\n") for line in text.split("\n\n") if line.strip() and not all(keyword in line for keyword in self.exclude_img_keywords)]
                joined_lines = "\n".join(lines)
                result_text_list.append(joined_lines)
            all_texts = "\n".join(result_text_list)
            return all_texts
        else:
            return output
    def call_ocrvl_server(self,image_path_or_base64:str,only_return_text=True,bool_save_files = False,bool_visualize = False):
        if self.paddelocrvl_server_string:
            file_type = 1
            if isinstance(image_path_or_base64,str):
                file_type = 0 if image_path_or_base64.endswith("pdf") else 1            
                if not image_path_or_base64.startswith("http"):
                    if os.path.isfile(image_path_or_base64):                        
                        with open(image_path_or_base64, 'rb') as f:
                            image_bytes = f.read()
                            image_path_or_base64 = base64.b64encode(image_bytes).decode("utf-8")
                    # else: #可能是base64字符串
                    #     raise Exception(f"{image_path_or_base64}文件不存在！")
            if isinstance(image_path_or_base64, bytes):
                image_path_or_base64 = base64.b64encode(image_path_or_base64).decode("utf-8")

            # 构造payload
            payload_file_content = {
                "file": image_path_or_base64, # Base64编码的文件内容或者文件URL
                "fileType": file_type, # 文件类型，1表示图像文件
                "visualize":bool_visualize
            }
            file_str = json.dumps(payload_file_content)

            payload_final = {
            "inputs": [
                {
                "name": "input",
                "shape": [1, 1],
                "datatype": "BYTES",
                "data": [
                    file_str
                ]
                }
            ],
            "outputs": [
                {
                "name": "output"
                }
            ]
            }

            # 调用API
            response = requests.post(self.paddelocrvl_server_string, json=payload_final)
            if response.status_code == 200:
                result_json = response.json()
                results = result_json["outputs"]
                if not only_return_text:
                    return results
                else:
                    result_text_list = []
                    for i, result_data in enumerate(results):
                        data = result_data["data"]
                        for d in data:
                            result = json.loads(d)["result"]
                            for i, res in enumerate(result["layoutParsingResults"]):
                                text = res["markdown"]["text"]
                                lines = [line.strip("\n") for line in text.split("\n\n") if line.strip() and not all(keyword in line for keyword in self.exclude_img_keywords)]
                                joined_lines = "\n".join(lines)
                                result_text_list.append(joined_lines)
                                if bool_save_files:
                                    md_dir = Path(f"markdown_{i}")
                                    md_dir.mkdir(exist_ok=True)
                                    (md_dir / "doc.md").write_text(res["markdown"]["text"])
                                    for img_path, img in res["markdown"]["images"].items():
                                        img_path = md_dir / img_path
                                        img_path.parent.mkdir(parents=True, exist_ok=True)
                                        img_path.write_bytes(base64.b64decode(img))
                                    print(f"Markdown document saved at {md_dir / 'doc.md'}")
                                    if bool_visualize:
                                        for img_name, img in res["outputImages"].items():
                                            img_path = f"{img_name}_{i}.jpg"
                                            Path(img_path).parent.mkdir(exist_ok=True)
                                            with open(img_path, "wb") as f:
                                                f.write(base64.b64decode(img))
                                            print(f"Output image saved at {img_path}")

                    result_texts = "\n".join(result_text_list)
                    return result_texts
            else:
                raise Exception(f"{self.paddelocrvl_server_string}服务未返回正常结果:{response.status_code=}")

    
    def __call__(self,image_path_or_url:str,image_base64_decoded:str,only_return_text=True):
        if self.paddelvllm_pipeline:
            return self.call_vllm_pipeline(image_path_or_url,only_return_text=only_return_text)
        elif self.paddelocrvl_server_string:
            return self.call_ocrvl_server(image_base64_decoded,only_return_text=only_return_text)
        else:
            raise Exception(f"PaddleOcrVl两种服务均不正常，请检查:vllm_pipeline({self.vllm_rec_server_url})和ocrvl_server({self.paddelocrvl_rec_server_url})！")

class JqRapidOCR:
    def __init__(self,gpu_id = 0):
        self.gpu_id = gpu_id
        rapidocr = None
        try:
            from rapidocr_paddle import RapidOCR # For GPU
            # 为使用gpu_id参数
            # 需修改/root/.virtualenvs/test/lib/python3.10/site-packages/rapidocr_paddle/main.py
            # updater = UpdateParameters()
            # if 'gpu_id' in kwargs:
            #     gpu_id = kwargs.pop('gpu_id')
            #     config = updater(config, **kwargs)
            #     config["Det"].update({"gpu_id":gpu_id})
            #     config["Cls"].update({"gpu_id":gpu_id})
            #     config["Rec"].update({"gpu_id":gpu_id})          
            rapidocr = RapidOCR(det_use_cuda=True, cls_use_cuda=True, rec_use_cuda=True,gpu_id=gpu_id)
            logger.debug(f"将使用多进程GPU RapidOCR (rapidocr_paddle)")
        except Exception as e:            
            logger.debug(f"初始化GPU RapidOCR (rapidocr_paddle)失败:{e}")
            logger.debug(f"将使用多进程CPU RapidOCR (rapidocr_onnxruntime)")
            from rapidocr_onnxruntime import RapidOCR
            rapidocr = RapidOCR()
        self.rapidocr = rapidocr
    def __call__(self,image_path:str): # Union[str, np.ndarray, bytes, Path]
        ocr_result,_ = self.rapidocr(image_path)
        result = '' 
        if ocr_result:
            ocr_texts = [line[1].strip() for line in ocr_result if line[1].strip()]
            #分隔符最好选用jqcode/jq_splitters/backend_splitter_utils/jq_chinese_recursive_text_splitter.py的第98行定义的
            result = ' '.join(ocr_texts) 
            logger.debug(f"$$图片[{image_path}]中的OCR文本:\n{result}")
        return result

VlmInstance = Vlm_API()
paddleocr_vl = None
try:
    if paddleocr_vl is None:
        paddleocr_vl = PaddleOCR_VL_API()
except Exception as e:
    logger.error(f"初始化PaddleOCR_VL_API失败: {str(e)}")

class OcrInOneAPI:
    def __init__(self,server_url:str = "http://10.1.150.106:5566/api/ocr"):
        self.server_url = server_url
        self.vlm = VlmInstance
        self.paddleocr_vl = paddleocr_vl
        self.rapidocr = None
    def __call__(self,image_file_path):
        result = ""
        ## 如果是图片地址，读取图片并转换为base64
        try:
            image_path_or_base64 = image_file_path
            if isinstance(image_path_or_base64,Path):
                image_path_or_base64 = str(image_path_or_base64)
            if isinstance(image_path_or_base64,str): 
                if os.path.isfile(image_path_or_base64):
                    with open(image_path_or_base64, 'rb') as f:
                        image_path_or_base64 = f.read()
                else:
                    raise Exception(f"{image_path_or_base64}文件不存在！")
            elif isinstance(image_path_or_base64, bytes):
                pass
            else:
                raise Exception(f"目前只接受str、path或bytes类型的参数，不支持：{type(image_path_or_base64)=}")               
            encoded_data = base64.b64encode(image_path_or_base64)
            decoded_data = encoded_data.decode('utf-8')
        except Exception as e:
            logger.warning(f"{e}")
            return ""
        
        try:
            logger.warning(f"优先调用VLM模型来做图片OCR识别...")
            result = self.vlm(decoded_data,is_decoded_image_text=True)
            logger.warning("VLM识别结果:\n"+result)
            # raise Exception("故意抛出VLM错误，以跳转测试OCR接口......") ## todo: 测试用，请删除

        except Exception as e:
            try:
                logger.error(f"VLM接口请求错误: {str(e)}。下面尝试请求PaddleOcrVL接口......")
                if self.paddleocr_vl:
                    try:
                        try:
                            # image_path_or_url:str,image_base64_decoded:str
                            result = self.paddleocr_vl(image_path_or_url=image_file_path,image_base64_decoded=decoded_data,only_return_text=True)
                            # result = self.paddleocr_vl(image_path_or_base64,only_return_text=True)
                        except:
                            result = self.paddleocr_vl(image_path_or_url=image_file_path,image_base64_decoded=image_file_path,only_return_text=True)
                        logger.warning("PaddleOcrVL识别结果:\n"+result)
                        # raise Exception("故意抛出PaddleOcrVL接口错误，以跳转测试OCR接口......")  ## todo: 测试用，请删除
                    except Exception as e:
                        raise Exception(f"PaddleOcrVL识别过程中出现错误: {str(e)}。下面尝试请求RapidOcr接口......")
                else:
                    raise Exception("PaddleOcrVL没有正确初始化")
            except Exception as e:
                try:
                    logger.error(f"PaddleOcrVL接口请求错误: {str(e)}。下面尝试请求RapidOcr接口......")
                    if self.rapidocr is None:
                        try:
                            self.rapidocr = JqRapidOCR()
                        except Exception as e:
                            raise Exception(f"初始化RapidOcr失败: {str(e)}")

                    if self.rapidocr:
                        try: 
                            try:
                                result = self.rapidocr(image_file_path)
                            except:
                                result = self.rapidocr(image_path_or_base64)
                            logger.warning("RapidOcr:\n"+result)

                            # raise Exception("故意抛出RapidOcr接口错误，以跳转测试OCR接口......")  ## todo: 测试用，请删除
                        except Exception as e:
                            raise Exception(f"RapidOcr识别过程中出现错误: {str(e)}")
                    else:
                        raise Exception("RapidOcr没有正确初始化或识别过程中出现错误!")
                    
                except Exception as e:
                    try:
                        logger.error(f"RapidOcr接口请求错误: {str(e)}。下面尝试请求Ocr接口......")            
                        payload = {
                            "imgString": decoded_data,
                            "bStore": False
                        }            
                        # 发送POST请求
                        headers = {'Content-Type': 'application/json'}
                        response = requests.post(
                            self.server_url,
                            data=json.dumps(payload),
                            headers=headers,
                            timeout=60  # 设置超时时间
                        )            
                        # 检查响应状态
                        response.raise_for_status()            
                        result_json = response.json()
                        result = result_json.get('data')[0].get('text','')        
                        # 返回结果
                        # logger.warning("OCR识别结果:"+result)
                    except Exception as e:
                        logger.error(f"所有OCR接口请求都发生错误: {str(e)}")            
        return result
OcrInOneInstance= OcrInOneAPI()


if __name__ == "__main__":
    img0 = fr"/data/projects/JqChatV2/JqChat/ocr2.jpg"
    img1 = fr"/data/projects/JqChatV2/JqChat/text_ocr.png"
    # if paddleocr_vl:
    #     r0 = paddleocr_vl(img0,img0,only_return_text=True)
    #     print(r0)
    #     r1 = paddleocr_vl(img1,img1,only_return_text=True)
    #     print(r1)
    img2 = fr"/data/projects/file_reader/test_docs/发票.jpg"
    img3 = fr"/data/projects/JqChatV2/JqChat/文档转换和下载.png"
    img4="/data/projects/JqChatV2/JqChat/graph.jpg"
    imgs = [img1,img0,img2,img3,img4]
    OcrInstance = OcrInOneInstance
    for img in imgs:
        print(img)
        # r1=OcrInstance(img) 
        if paddleocr_vl:
            r1=paddleocr_vl(img,img,only_return_text=True)
        else:
            r1=OcrInstance(img)
        print(r1)
# 服务部署：
# 服务器：192.168.44.222
# 密码：jqkj5350**)
# 命令:
# 1、cd /root/paddleocr
# 2、docker compose up
