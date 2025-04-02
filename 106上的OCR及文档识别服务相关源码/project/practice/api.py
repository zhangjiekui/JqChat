
import time

import uvicorn
from fastapi import FastAPI
from loguru import logger
from typing import List
from pydantic import BaseModel
import os, cv2, re,time,json,base64, datetime
import numpy as np
from paddleocr import PaddleOCR

app = FastAPI()

base_dir = '/root/project/PaddleOCR'
UPLOAD_PATH = './upload_imgs'
use_gpu = os.environ.get("USE_GPU",True)
use_onnx = False


det_model_dir = os.path.join(base_dir,"inference","ch_PP-OCRv4_det_infer")
rec_model_dir = os.path.join(base_dir,"inference","ch_PP-OCRv4_rec_infer")
cls_model_dir = os.path.join(base_dir,"inference","ch_ppocr_mobile_v2.0_cls_infer")


paddle_ocr = PaddleOCR(use_angle_cls=True,use_gpu=use_gpu,use_onnx=use_onnx,
                       det_model_dir=det_model_dir,
                       rec_model_dir=rec_model_dir,
                       cls_model_dir=cls_model_dir)


# 定义请求数据模型
class OCRRequest(BaseModel):
    imgString: str  # base64编码的图片字符串
    bStore: bool = False  # 是否保存图片，默认为False

# 定义响应数据模型
class OCRResponse(BaseModel):
    code: int = 0  # 状态码，0表示成功
    message: str = "success"  # 状态信息
    data: list = []  # OCR识别结果
    processTime: float = 0  # 处理耗时


class OCRResultItem(BaseModel):
    box: List[List[float]]  # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
    text: str
    confidence: float

class ORIOCRResponse(BaseModel):
    code: int
    message: str
    data: List[OCRResultItem]
    processTime: float


@app.post("/api/ocr", response_model=OCRResponse)
async def ocr(request_data: OCRRequest):
    start = time.time()
    try:
        # 处理base64字符串
        imgStr = request_data.imgString
        if ';base64,' in imgStr:
            imgStr = imgStr.split(';base64,')[-1]
        
        # 解码base64图片数据
        img_binary = base64.b64decode(imgStr)
        img_array = np.frombuffer(img_binary, dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        
        if img is None:
            return OCRResponse(
                code=1,
                message="Invalid image data",
                data=[],
                processTime=time.time() - start
            )

        # 如果需要保存图片
        if request_data.bStore:
            today = datetime.datetime.now().strftime('%Y%m%d')
            picname = datetime.datetime.now().strftime('%H%M%S%f') + '.jpg'
            imagepath = os.path.join(UPLOAD_PATH, today)
            imagefullpath = os.path.join(imagepath, picname)
            
            os.makedirs(imagepath, exist_ok=True)
            with open(imagefullpath, 'wb') as file:
                file.write(img_binary)
        
        # 执行OCR识别
        ocr_result = paddle_ocr.ocr(img)

        dt_boxes = []
        rec_res = []
        for item in ocr_result:
            box,res = item
            dt_boxes.append(box)
            rec_res.append(res)
        dt_num = len(dt_boxes)

        for dno in range(dt_num):
            text, score = rec_res[dno]


            print(dno, text, score)

        
        # 将所有文本拼接成一个字符串
        combined_text = " ".join(line[1][0] for line in ocr_result)

        
        return OCRResponse(
            code=0,
            message="success",
            data=[{"text": combined_text}],  # 将拼接后的文本作为单个结果返回
            processTime=time.time() - start
        )
        
    except Exception as e:
        return OCRResponse(
            code=1,
            message=f"Error: {str(e)}",
            data=[],
            processTime=time.time() - start
        )


@app.post("/api/oriocr", response_model=ORIOCRResponse)
async def ocr(request_data: OCRRequest):
    start = time.time()
    try:
        # 处理base64字符串
        imgStr = request_data.imgString
        if ';base64,' in imgStr:
            imgStr = imgStr.split(';base64,')[-1]
        
        # 解码base64图片数据
        img_binary = base64.b64decode(imgStr)
        img_array = np.frombuffer(img_binary, dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        
        if img is None:
            return OCRResponse(
                code=1,
                message="Invalid image data",
                data=[],
                processTime=time.time() - start
            )

        # 保存图片的逻辑保持不变
        if request_data.bStore:
            today = datetime.datetime.now().strftime('%Y%m%d')
            picname = datetime.datetime.now().strftime('%H%M%S%f') + '.jpg'
            imagepath = os.path.join(UPLOAD_PATH, today)
            imagefullpath = os.path.join(imagepath, picname)
            
            os.makedirs(imagepath, exist_ok=True)
            with open(imagefullpath, 'wb') as file:
                file.write(img_binary)
        
        # 执行OCR识别
        ocr_result = paddle_ocr.ocr(img)

        # 处理OCR结果
        formatted_results = []
        for item in ocr_result:
            box, (text, confidence) = item
            # 确保box是四个点的坐标
            if len(box) == 4:
                result_item = {
                    "box": box.tolist() if isinstance(box, np.ndarray) else box,  # 转换numpy数组为列表
                    "text": text,
                    "confidence": float(confidence)  # 确保confidence是float类型
                }
                formatted_results.append(result_item)
        
        return OCRResponse(
            code=0,
            message="success",
            data=formatted_results,
            processTime=time.time() - start
        )
        
    except Exception as e:
        logger.error(f"OCR处理错误: {str(e)}")
        return OCRResponse(
            code=1,
            message=f"Error: {str(e)}",
            data=[],
            processTime=time.time() - start
        )


if __name__ == '__main__':
    uvicorn.run(app="api:app",host="0.0.0.0",port=5566, workers=8)  # 测试端口
    # uvicorn.run(app="api:app",host="0.0.0.0",port=6677, reload=True)  # 测试端口
