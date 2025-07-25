from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import base64
import hashlib
import os

class TextWatermark:
    def __init__(self, secret_key: str):
        self.key = hashlib.sha256(secret_key.encode()).digest()
        self.iv = os.urandom(16)
        
    def encrypt(self, plaintext: str) -> str:
        cipher = AES.new(self.key, AES.MODE_CBC, self.iv)
        padded_data = pad(plaintext.encode('utf-8'), AES.block_size)
        encrypted = cipher.encrypt(padded_data)
        return base64.b64encode(encrypted).decode('utf-8')
    
    def decrypt(self, ciphertext: str) -> str:
        cipher = AES.new(self.key, AES.MODE_CBC, self.iv)
        decoded = base64.b64decode(ciphertext)
        decrypted = cipher.decrypt(decoded)
        return unpad(decrypted, AES.block_size).decode('utf-8')

def extend_text_to_fit_watermark(original_text: str, watermark_bits: int) -> str:
    """扩展文本以适应水印"""
    current_length = len(original_text)
    needed_length = watermark_bits
    
    if current_length >= needed_length:
        return original_text
    
    # 计算需要添加的字符数
    chars_to_add = needed_length - current_length
    
    # 策略1: 添加空格和句号（不显眼的字符）
    extension = " " * chars_to_add
    # for i in range(chars_to_add):
    #     if i % 10 == 9:  # 每10个字符添加一个句号
    #         extension += "。"
    #     else:
    #         extension += " "  # 添加空格
    
    # print(f"扩展文本: 添加了 {chars_to_add} 个字符")
    return original_text + extension

def embed_watermark(original_text: str, watermark: str) -> str:
    # 使用UTF-8编码来获取准确的字节数
    watermark_bytes = watermark.encode('utf-8')
    watermark_bin = ''.join(format(b, '08b') for b in watermark_bytes)
    
    # print(f"水印 '{watermark}'")
    # print(f"UTF-8字节: {list(watermark_bytes)}")
    # print(f"二进制: {watermark_bin}")
    # print(f"需要位数: {len(watermark_bin)} 位")
    # print(f"原始文本长度: {len(original_text)} 字符")
    
    # 如果文本不够长，扩展文本而不是截断水印
    if len(watermark_bin) > len(original_text):
        # print(f"⚠️  文本长度不足 ({len(original_text)} < {len(watermark_bin)})")
        original_text = extend_text_to_fit_watermark(original_text, len(watermark_bin))
        # print(f"扩展后文本长度: {len(original_text)} 字符")
    
    encoded = []
    for i, bit in enumerate(watermark_bin):
        if i < len(original_text):
            char = original_text[i]
            zwsp = '\u200b' if bit == '1' else '\u200c'
            encoded.append(char + zwsp)
    
    # 添加剩余文本
    if len(watermark_bin) < len(original_text):
        encoded.append(original_text[len(watermark_bin):])
    
    result = ''.join(encoded)
    # print(f"嵌入完成，结果长度: {len(result)} 字符")
    return result

def extract_watermark(watermarked_text: str, watermark_bytes_length: int) -> str:
    bits = []
    max_bits = watermark_bytes_length * 8
    
    # print(f"期望提取 {watermark_bytes_length} 字节 ({max_bits} 位)")
    
    i = 0
    while i < len(watermarked_text) and len(bits) < max_bits:
        if i + 1 < len(watermarked_text):
            next_char = watermarked_text[i + 1]
            if next_char in ('\u200b', '\u200c'):
                bits.append('1' if next_char == '\u200b' else '0')
                i += 2
            else:
                i += 1
        else:
            i += 1
    
    # print(f"实际提取到 {len(bits)} 位")
    
    # 转换为字节并解码
    try:
        if len(bits) % 8 != 0:
            # print(f"警告: 提取的位数不是8的倍数，截断到 {len(bits) - len(bits) % 8} 位")
            bits = bits[:len(bits) - len(bits) % 8]
        
        bytes_data = bytearray()
        for i in range(0, len(bits), 8):
            byte_bits = bits[i:i+8]
            byte_val = int(''.join(byte_bits), 2)
            bytes_data.append(byte_val)
        
        result = bytes_data.decode('utf-8')
        # print(f"成功解码: '{result}'")
        return result
    except Exception as e:
        # print(f"解码失败: {e}")
        # 尝试逐字节解码
        result = ""
        for i in range(0, len(bits), 8):
            byte_bits = bits[i:i+8]
            if len(byte_bits) == 8:
                try:
                    byte_val = int(''.join(byte_bits), 2)
                    result += chr(byte_val)
                except:
                    result += "?"
        return result

def print_formatting(leading_text, print_text):
    print("-" * 50)
    print(f">>> {leading_text}:") 
    # print("-" * 20) 
    print(f"{print_text}")
    print("\n")

if __name__ == "__main__":
    crypto = TextWatermark("strong_password_123")
    
    # 使用较短的原始文本测试
    original = "这是AI生成的原始文本"
    print_formatting("原始文本", original)    

    
    # 水印嵌入演示 - 使用较长的水印
    watermark_text = "晶奇智能体水印"  # 7个中文字符
    print_formatting("嵌入的水印内容", watermark_text)
    watermarked = embed_watermark(original, watermark_text)
    print_formatting("嵌入水印后的文本（原始文本长度不足会在后头自动补充）", repr(watermarked))

    # 加密演示
    encrypted = crypto.encrypt(watermarked)
    print_formatting("加密后的文本（含嵌入的水印）", encrypted)

    
    # 解密演示
    decrypted = crypto.decrypt(encrypted)
    print_formatting("解密后的文本（含嵌入的水印）", decrypted)
    
    # 水印提取演示
    extracted = extract_watermark(decrypted, len(watermark_text.encode('utf-8')))
    print_formatting("从解密后的文本（含嵌入的水印）中提取到的水印", repr(extracted))

    print("\n===================测试结论===================")
    print(f"🎯 原始水印: '{watermark_text}'")
    print(f"🎯 提取水印: '{extracted}'")
    print(f"🎯 匹配结果: {'✅ 成功' if watermark_text == extracted else '❌ 失败'}")