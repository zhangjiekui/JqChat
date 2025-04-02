
import time

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
import os, cv2, re,time,json,base64, datetime
import numpy as np
from paddleocr import PaddleOCR

app = FastAPI()

base_dir = '/root/project/PaddleOCR'
UPLOAD_PATH = './upload_imgs'
use_gpu = os.environ.get("USE_GPU",False)
use_onnx = False


det_model_dir = os.path.join(base_dir,"inference","ch_PP-OCRv4_det_infer")
rec_model_dir = os.path.join(base_dir,"inference","ch_PP-OCRv4_rec_infer")
cls_model_dir = os.path.join(base_dir,"inference","ch_ppocr_mobile_v2.0_cls_infer")


paddle_ocr = PaddleOCR(use_angle_cls=True,use_gpu=use_gpu,use_onnx=use_onnx,
                       det_model_dir=det_model_dir,
                       rec_model_dir=rec_model_dir,
                       cls_model_dir=cls_model_dir)


imgpath = '/root/project/PaddleOCR/doc/imgs/11.jpg'
img = cv2.imread(imgpath)
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





