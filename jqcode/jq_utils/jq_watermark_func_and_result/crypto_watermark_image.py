from PIL import Image, ImageDraw, ImageFont
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import hashlib
import os
import platform
from jqcode.jq_utils.jq_watermark_func_and_result.crypto_watermark_text import print_formatting

# 初始化密钥和IV
class ImageWatermark:
    def __init__(self, secret_key: str):
        self.key = hashlib.sha256(secret_key.encode()).digest()
        self.iv = os.urandom(16)

    def _bytes_to_bin(self, data: bytes) -> str:
        return ''.join(format(b, '08b') for b in data)

    def _bin_to_bytes(self, binary_str: str) -> bytes:
        n = int(binary_str, 2)
        return n.to_bytes((n.bit_length() + 7) // 8, 'big')

    def encrypt(self, plaintext: str) -> bytes:
        cipher = AES.new(self.key, AES.MODE_CBC, self.iv)
        padded_data = pad(plaintext.encode(), AES.block_size)
        return cipher.encrypt(padded_data)

    def decrypt(self, ciphertext: bytes) -> str:
        cipher = AES.new(self.key, AES.MODE_CBC, self.iv)
        decrypted = cipher.decrypt(ciphertext)
        return unpad(decrypted, AES.block_size).decode()

    def embed_watermark(self, image_path: str, watermark_text: str, output_path: str):
        # Step 1: 加密水印
        encrypted_watermark = self.encrypt(watermark_text)
        watermark_bin = self._bytes_to_bin(encrypted_watermark)

        # Step 2: 读取图片
        img = Image.open(image_path).convert("RGB")
        pixels = list(img.getdata())
        new_pixels = []

        # Step 3: 嵌入水印到每个像素的最低位
        bit_index = 0
        for r, g, b in pixels:
            if bit_index < len(watermark_bin):
                r = (r & ~1) | int(watermark_bin[bit_index])
                bit_index += 1
            if bit_index < len(watermark_bin):
                g = (g & ~1) | int(watermark_bin[bit_index])
                bit_index += 1
            if bit_index < len(watermark_bin):
                b = (b & ~1) | int(watermark_bin[bit_index])
                bit_index += 1
            new_pixels.append((r, g, b))

        # Step 4: 保存图片
        img.putdata(new_pixels)
        img.save(output_path, format="PNG")
        # print(f"[+] 不可见水印已嵌入到 {output_path.split('/')[-1]}")
        print_formatting(f"[+] 不可见水印已嵌入到", f"{output_path.split('/')[-1]}")

    def get_chinese_font(self, font_size=50):
        """自动获取系统中文字体"""
        system = platform.system()
        font = None
        
        try:
            if system == "Windows":
                font_path = "C:/Windows/Fonts/msyh.ttc"  # 微软雅黑
                if os.path.exists(font_path):
                    font = ImageFont.truetype(font_path, font_size)
            elif system == "Darwin":  # macOS
                font_path = "/System/Library/Fonts/PingFang.ttc"
                if os.path.exists(font_path):
                    font = ImageFont.truetype(font_path, font_size)
            elif system == "Linux":
                # 尝试常见的中文字体路径
                font_paths = [
                    ".Fonts_CN/MSYH/MSYH.TTC",
                    ".Fonts_CN/MSYH/MSYHBD.TTC",
                    ".Fonts_CN/MSYH/MSYHL.TTC",
                    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
                    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
                    "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Bold.ttc"
                ]
                for path in font_paths:
                    if os.path.exists(path):
                        font = ImageFont.truetype(path, font_size)
                        break
            
            # 如果系统字体都找不到，尝试使用项目中的字体文件
            if font is None:
                # 假设你在项目目录下放了一个中文字体文件
                local_font_path = "fonts/msyh.ttc"  # 你需要自己准备这个字体文件
                if os.path.exists(local_font_path):
                    font = ImageFont.truetype(local_font_path, font_size)
        except Exception as e:
            print(f"[!] 字体加载失败: {e}")
        
        # 如果还是没有找到合适的字体，使用默认字体（可能不支持中文）
        if font is None:
            print("[!] 未找到中文字体，使用默认字体（可能无法正确显示中文）")
            font = ImageFont.load_default()
            
        return font

    def add_visible_watermark(self, image_path: str, watermark_text: str, output_path: str,
                              position=(50, 50), font_size=50, color=(255, 0, 0, 128)):
        """
        在图片上添加可见水印（文字），支持中文
        :param image_path: 原图路径
        :param watermark_text: 水印文字
        :param output_path: 输出路径
        :param position: 文字位置 (x, y)
        :param font_size: 字体大小
        :param color: 文字颜色 RGBA（最后一个是透明度）
        """
        img = Image.open(image_path).convert("RGBA")
        txt_layer = Image.new('RGBA', img.size, (255, 255, 255, 128))
        draw = ImageDraw.Draw(txt_layer)

        # 获取支持中文的字体
        font = self.get_chinese_font(font_size)
        # 4. 添加文字（位置可根据需要调整）
        width, height = img.size
        # 兼容新旧版本的尺寸获取
        if hasattr(draw, 'textlength'):
            text_width = draw.textlength(watermark_text, font=font)
            text_height = font.getbbox(watermark_text)[3]  # 获取字体高度
        else:
            text_width, text_height = draw.textsize(watermark_text, font=font)

        final_position = (width - text_width - position[0], height -text_height - position[1])  # 右下角
        draw.text(final_position, watermark_text, font=font, fill=color)  # 红色文字

        # draw.text(position, watermark_text, font=font, fill=color)
        watermarked = Image.alpha_composite(img, txt_layer)
        watermarked = watermarked.convert("RGB")  # 转回 RGB 保存为 JPG/PNG
        watermarked.save(output_path, format="PNG")
        print_formatting(f"[+] 提取到的水印已添加到", f"{output_path.split('/')[-1]}")

    def extract_watermark(self, image_path: str, watermark_length: int) -> str:
        # Step 1: 读取图片
        img = Image.open(image_path).convert("RGB")
        pixels = list(img.getdata())

        # Step 2: 提取水印比特流
        bits = []
        total_bits = watermark_length * 8
        for r, g, b in pixels:
            bits.append(str(r & 1))
            if len(bits) >= total_bits:
                break
            bits.append(str(g & 1))
            if len(bits) >= total_bits:
                break
            bits.append(str(b & 1))
            if len(bits) >= total_bits:
                break

        watermark_bin = ''.join(bits)[:total_bits]

        # Step 3: 转换为字节并解密
        watermark_bytes = self._bin_to_bytes(watermark_bin)
        try:
            return self.decrypt(watermark_bytes)
        except Exception as e:
            return f"[!] 解密失败: {e}"

# 测试代码
if __name__ == "__main__":
    
    wm = ImageWatermark("strong_password_123")

    original_image = "/data/projects/JqChatV2/JqChat/jqcode/jq_utils/jq_watermark_func_and_result/图片/test.jpg"
    invisible_output = "/data/projects/JqChatV2/JqChat/jqcode/jq_utils/jq_watermark_func_and_result/图片/watermarked_invisible.png"
    visible_output = "/data/projects/JqChatV2/JqChat/jqcode/jq_utils/jq_watermark_func_and_result/图片/watermarked_visible.png"
    print_formatting("原始图片","test.jpg")
    watermark = "JqAgentWatermark"
    watermark = "内容由AI生成"
    print_formatting("水印文本",watermark)

    # 嵌入不可见水印
    wm.embed_watermark(original_image, watermark, invisible_output)
    
    # 提取水印
    watermark_len = len(wm.encrypt(watermark))
    extracted = wm.extract_watermark(invisible_output, watermark_len)
    print_formatting(f"从{invisible_output.split('/')[-1]}中提取到水印",extracted)

    # 添加可见水印（支持中文）
    print_formatting(f"将提取到的水印添加到{visible_output.split('/')[-1]}",extracted)
    wm.add_visible_watermark(original_image, extracted, visible_output)  # 半透明白色



    print(f"\n🎯 原始水印: '{watermark}'")
    print(f"🎯 提取水印: '{extracted}'")
    print(f"🎯 匹配结果: {'✅ 成功' if watermark == extracted else '❌ 失败'}")