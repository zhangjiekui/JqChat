endpoint = "http://192.168.44.222:7001/ocr"
endpoint = "http://116.62.228.130:5001/ocr" # 阿里云服务器
# endpoint = "http://192.168.44.222:5566/ocr"
import base64
import requests
def main(imgpath):
    """
    :param imgpath: 图片路径
    :return: 识别结果
    """
    with open(imgpath, 'rb') as file:
        image_bytes = file.read()
        image_data = base64.b64encode(image_bytes).decode("ascii")
        payload = {"imgString": image_data, "ocrType": "idcard"}
        response = requests.post(endpoint, json=payload)
    
    if response.status_code == 200:
        return response.json()
    else:
        return {"error": "Failed to get a valid response from the server."}
    
if __name__ == '__main__':
    import os
    imagepath = "/data/projects/JqChatV2/JqChat/106上的OCR及文档识别服务相关源码/2.jpg"
    result = main(imagepath)
    print(result)