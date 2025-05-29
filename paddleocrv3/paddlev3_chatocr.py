from paddleocr import PPChatOCRv4Doc

chat_bot_config = {
    "module_name": "chat_bot",
    "model_name": "qwen3",
    "base_url": "http://10.1.150.105:3000/v1",
    "api_type": "openai",
    "api_key": "sk-0S7bV3oaznhuevN899Db0cDa20Ae4c5485Ce5862A86063C8",  # your api_key
}

retriever_config = {
    "module_name": "retriever",
    "model_name": "bce-embedding-base_v1",
    "base_url": "http://10.1.150.106:9997/v1",
    "api_type": "openai",
    "api_key": "api_key",  # your api_key
}

mllm_chat_bot_config = {
    "module_name": "chat_bot",
    "model_name": "PP-DocBee2-3B",
    "base_url": "http://127.0.0.1:8080/chat/completions",  # your local mllm service url
    "api_type": "openai",
    "api_key": "api_key",  # your api_key
}

pipeline = PPChatOCRv4Doc()

visual_predict_res = pipeline.visual_predict(
    input="vehicle_certificate-1.png",
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_common_ocr=True,
    use_seal_recognition=True,
    use_table_recognition=True,
)

visual_info_list = []
for res in visual_predict_res:
    visual_info_list.append(res["visual_info"])
    layout_parsing_result = res["layout_parsing_result"]

vector_info = pipeline.build_vector(
    visual_info_list, flag_save_bytes_vector=True, retriever_config=retriever_config
)
mllm_predict_res = pipeline.mllm_pred(
    input="vehicle_certificate-1.png",
    key_list=["Cab Seating Capacity"], # Translated: 驾驶室准乘人数
    mllm_chat_bot_config=mllm_chat_bot_config,
)
mllm_predict_info = mllm_predict_res["mllm_res"]
chat_result = pipeline.chat(
    key_list=["Cab Seating Capacity"], # Translated: 驾驶室准乘人数
    visual_info=visual_info_list,
    vector_info=vector_info,
    mllm_predict_info=mllm_predict_info,
    chat_bot_config=chat_bot_config,
    retriever_config=retriever_config,
)
print(chat_result)