
import base64
import requests
import pathlib

API_URL = "http://localhost:8080/layout-parsing" # 服务URL

image_path = fr"C:\Users\win11\低收入人口动态监测信息平台优化升级工作指引（第一版）.pdf"

# 对本地图像进行Base64编码
with open(image_path, "rb") as file:
    image_bytes = file.read()
    image_data = base64.b64encode(image_bytes).decode("ascii")

payload = {
    "file": image_data, # Base64编码的文件内容或者文件URL
    "fileType": 0, # 文件类型，1表示图像文件
}

# 调用API
print(f"Sending request to {API_URL}")
response = requests.post(API_URL, json=payload)
print(f"Response status code: {response.status_code}")
# print(f"response.json(): {response.json()}")
# 处理接口返回数据
assert response.status_code == 200
result = response.json()["result"]
markdown_texts = ""
md_dir_md = pathlib.Path(f"results/markdown_result")
md_dir_md.mkdir(exist_ok=True,parents=True)
md_dir_img = pathlib.Path(f"results/output_images")
md_dir_img.mkdir(exist_ok=True,parents=True)
for i, res in enumerate(result["layoutParsingResults"]):
    # print(res["prunedResult"])
    # markdown_texts += res["markdown"]["text"] + "\n\n"
    markdown_text = res["markdown"]["text"]
    if markdown_text.startswith("#"):
        markdown_text = "\n\n"+markdown_text
    markdown_texts += markdown_text    
    for img_path, img in res["markdown"]["images"].items():
        img_path = md_dir_md / img_path
        img_path.parent.mkdir(parents=True, exist_ok=True)
        img_path.write_bytes(base64.b64decode(img))
    
    for img_name, img in res["outputImages"].items():
        img_path = f"{md_dir_img}/{img_name}_{i}.jpg"
        with open(img_path, "wb") as f:
            f.write(base64.b64decode(img))
        
(md_dir_md / "doc.md").write_text(markdown_texts, encoding="utf-8")
print(f"Markdown document saved at {md_dir_md / 'doc.md'}")
print(f"Output image saved at {md_dir_img}")

