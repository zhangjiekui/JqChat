
# paddlex --serve --pipeline doc_understanding --port 8080
# paddlex --serve --pipeline PP-ChatOCRv4-doc --port 8081
import base64
import pprint
import sys
import requests
import time

# nü

# 方法3 OCR：耗时4.47秒
from openai import OpenAI
API_BASE_URL_UD = "http://10.1.150.105:3000/v1"   # 需要对应model="v",api_key='sk-0S7bV3oaznhuevN899Db0cDa20Ae4c5485Ce5862A86063C8'
# API_BASE_URL_UD = "http://10.1.150.105:8000/v1" # 需要对应model="qwenvl",api_key='abc123'
client = OpenAI(
    # api_key='abc123',
    api_key='sk-0S7bV3oaznhuevN899Db0cDa20Ae4c5485Ce5862A86063C8',
    base_url=f'{API_BASE_URL_UD}'
)
image_path = "paddleocrv3/ocr1.png"
image_path="paddleocrv3/1small.jpg"
image_path="paddleocrv3/2.jpg"
print(f"处理图片image_path={image_path}")
with open(image_path, "rb") as file:
    image_bytes = file.read()
    image_data = base64.b64encode(image_bytes).decode("ascii")
start_time = time.time()
response = client.chat.completions.create(
    # model="qwenvl",# Choose Model
    model="v",# Choose Model
    messages=[
        {
            "role": "system",
            "content": "You are a helpful ocr assistant."
        },
        {
            "role": "user",
            "content":[
                {
                    "type": "text",
                    # "text": "请识别出图片中的全部文字" #如果是OCR任务，直接识别全部文字
                    "text": "识别出发票类型,购买方名称,销售方名称,购买的货物或服务名称，以Json格式输出,不要有额外的字段或内容"
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}
                },
            ]
        },
    ],
)
content = response.choices[0].message.content
print('OCR chat.completions结果:\n', content)
end_time = time.time()
print(f"OCR chat.completions处理{image_path=}"+"耗时: {:.2f}秒".format(end_time - start_time))


# from paddleocr import PPChatOCRv4Doc

# chat_bot_config = {
#     "module_name": "chat_bot",
#     "model_name": "qwen3",
#     "base_url": "http://10.1.150.105:3000/v1",
#     "api_type": "openai",
#     "api_key": "sk-0S7bV3oaznhuevN899Db0cDa20Ae4c5485Ce5862A86063C8",  # your api_key
# }

# retriever_config = {
#     "module_name": "retriever",
#     "model_name": "bce-embedding-base_v1",
#     "base_url": "http://10.1.150.106:9997/v1",
#     "api_type": "openai",
#     "api_key": "api_key",  # your api_key
# }

# mllm_chat_bot_config = {
#     "module_name": "chat_bot",
#     "model_name": "PP-DocBee2-3B",
#     "base_url": "http://127.0.0.1:8080",  # your local mllm service url
#     "api_type": "openai",
#     "api_key": "api_key",  # your api_key
# }

# pipeline = PPChatOCRv4Doc()


# mllm_predict_res = pipeline.mllm_pred(
#     input=img,
#     key_list=key_list, # Translated: 驾驶室准乘人数
#     mllm_chat_bot_config=mllm_chat_bot_config,
# )
# mllm_predict_info = mllm_predict_res["mllm_res"]
# print("-----------------")
# print(f"mllm_predict_info: {mllm_predict_info}")

# # visual_predict_res = pipeline.visual_predict(
# #     input=img,
# #     use_doc_orientation_classify=False,
# #     use_doc_unwarping=False,
# #     use_common_ocr=True,
# #     use_seal_recognition=True,
# #     use_table_recognition=True,
# # )

# # visual_info_list = []
# # for res in visual_predict_res:
# #     visual_info_list.append(res["visual_info"])
# #     layout_parsing_result = res["layout_parsing_result"]

# # vector_info = pipeline.build_vector(
# #     visual_info_list, flag_save_bytes_vector=True, retriever_config=retriever_config
# # )

# # mllm_predict_res = pipeline.mllm_pred(
# #     input=img,
# #     key_list=key_list, # Translated: 驾驶室准乘人数
# #     mllm_chat_bot_config=mllm_chat_bot_config,
# # )
# # mllm_predict_info = mllm_predict_res["mllm_res"]


# # chat_result = pipeline.chat(
# #     key_list=key_list, # Translated: 驾驶室准乘人数
# #     visual_info=visual_info_list,
# #     vector_info=vector_info,
# #     mllm_predict_info=mllm_predict_info,
# #     chat_bot_config=chat_bot_config,
# #     retriever_config=retriever_config,
# # )
# # print(chat_result)

# # print("-----------------")
# # print(f"mllm_predict_info: {mllm_predict_info}")
# # print("-----------------")
# # print(f"vector_info: {vector_info}")
# # print("-----------------")
# # print(f"visual_info_list: {visual_info_list}")