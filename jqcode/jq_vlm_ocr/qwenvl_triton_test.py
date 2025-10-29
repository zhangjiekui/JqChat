
import base64
import requests
import pathlib
import json
from PIL import Image

API_URL = "http://192.168.44.222:8000/v2/models/layout-parsing/infer" # 服务URL
# API_URL = "http://192.168.44.222:8000/v2/models/ocr/infer"
#               http://localhost:8000/v2/models/ocr/infer
exclude_img_keywords = ["<img src", "alt"]

image_path = "/data/projects/JqChatV2/JqChat/ocr2.jpg"
# image_path = "/data/projects/JqChatV2/JqChat/ocr.png"
# image_path = "/data/projects/JqChatV2/JqChat/JqR2R/py/Vue3快速上手_笔记.pdf"

file_type = 0 if pathlib.Path(image_path).suffix == ".pdf" else 1

with open(image_path, "rb") as file:
    image_bytes = file.read()
    # image_data = base64.b64encode(image_bytes).decode("ascii")
    image_data = base64.b64encode(image_bytes).decode("utf-8")
bool_save_files = False
bool_visualize = False
payload_content = {
    "file": image_data, # Base64编码的文件内容或者文件URL
    "fileType": file_type, # 文件类型，1表示图像文件
    "visualize":bool_visualize
}

file_str = json.dumps(payload_content)
payload1 = {
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
response = requests.post(API_URL, json=payload1)

# 处理接口返回数据
assert response.status_code == 200
result_json = response.json()
results = result_json["outputs"]
result_text_list = []
for i, result_data in enumerate(results):
    data = result_data["data"]
    for d in data:
        result = json.loads(d)["result"]
        for i, res in enumerate(result["layoutParsingResults"]):
            text = res["markdown"]["text"]
            lines = [line.strip("\n") for line in text.split("\n\n") if line.strip() and not all(keyword in line for keyword in exclude_img_keywords)]
            joined_lines = "\n".join(lines)
            result_text_list.append(joined_lines)
            if bool_save_files:
                md_dir = pathlib.Path(f"markdown_{i}")
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
                        pathlib.Path(img_path).parent.mkdir(exist_ok=True)
                        with open(img_path, "wb") as f:
                            f.write(base64.b64decode(img))
                        print(f"Output image saved at {img_path}")

result_texts = "\n".join(result_text_list)
print("=============================================================================================")
print(result_texts)