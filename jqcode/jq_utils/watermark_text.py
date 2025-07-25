import base64
import string 
def embed_watermark(text, watermark):
    # 将水印编码为base64
    encoded_watermark = base64.b64encode(watermark.encode()).decode()
    # 将编码后的水印嵌入到文本中，例如在每行末尾添加
    encoded_watermark_list = list(encoded_watermark)
    lines = text.split('\n')
    for i in range(len(lines)):
        if i < len(encoded_watermark_list):
            lines[i] += encoded_watermark_list[i]
    return '\n'.join(lines)
 
def extract_watermark(text):
    # 提取文本末尾的水印字符
    lines = text.split('\n')
    b64chars = string.ascii_uppercase + string.ascii_lowercase + string.digits + '+/'
    encoded_watermark = ''.join([line[-1] for line in lines if line and line[-1] in b64chars])
    # 解码水印
    try:
        decoded_watermark = base64.b64decode(encoded_watermark).decode()
        return decoded_watermark
    except Exception as e:
        return None
 
# 示例使用
original_text = "这是一段示例文本。\n这是第二行。\n这是第三行。"
watermark = "Watermark"
text_with_watermark = embed_watermark(original_text, watermark)
print("Text with watermark:", text_with_watermark)
extracted_watermark = extract_watermark(text_with_watermark)
print("Extracted watermark:", extracted_watermark)