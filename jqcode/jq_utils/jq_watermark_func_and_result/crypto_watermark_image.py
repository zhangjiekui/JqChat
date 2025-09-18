import os
import json
# import piexif
import hashlib
import platform
from PIL import Image
from pathlib import Path
from Crypto.Cipher import AES
from PIL.PngImagePlugin import PngInfo
from Crypto.Util.Padding import pad, unpad
from PIL import Image, ImageDraw, ImageFont
from jqcode.jq_agent.c0_init_env_models import env_models_instance
from jqcode.jq_utils.jq_watermark_func_and_result.crypto_watermark_text import print_formatting

# 构造数据
visible_text = env_models_instance.aigc_visible_text
invisible_watermark = env_models_instance.aigc_invisible_watermark
aigc_metadata = env_models_instance.aigc_metadata

class ImageWatermark:
    def __init__(self, secret_key: str='jqkj%#%)**)', visible_text=visible_text, invisible_watermark=invisible_watermark, aigc_metadata=aigc_metadata, validate_final_result:bool=False):
        self.key = hashlib.sha256(secret_key.encode()).digest()
        # self.iv = os.urandom(16)
        self.iv = b"\xae\xfa\x10\xea\r0\xc1{\x0bP'\xa7\xd5\r\xa2\xea"
        self.visible_text = visible_text
        self.invisible_watermark = invisible_watermark
        self.aigc_metadata = aigc_metadata
        self.position=(50, 50)
        self.font_size=20
        self.color_for_img_layer = (255, 255, 255, 128)
        self.color_for_visible_text = (255, 0, 0, 128)
        self.validate_final_result = validate_final_result

    def _bytes_to_bin(self, data: bytes) -> str:
        return ''.join(format(b, '08b') for b in data)

    def _bin_to_bytes(self, binary_str: str) -> bytes:
        # n = int(binary_str, 2)
        # return n.to_bytes((n.bit_length() + 7) // 8, 'big')
        return bytes(int(binary_str[i:i+8], 2) for i in range(0, len(binary_str), 8))


    def encrypt(self, plaintext: str) -> bytes:
        cipher = AES.new(self.key, AES.MODE_CBC, self.iv)
        padded_data = pad(plaintext.encode(encoding="utf-8"), AES.block_size)
        return cipher.encrypt(padded_data)

    def decrypt(self, ciphertext: bytes) -> str:
        cipher = AES.new(self.key, AES.MODE_CBC, self.iv)
        decrypted = cipher.decrypt(ciphertext)
        return unpad(decrypted, AES.block_size).decode(encoding="utf-8",errors='ignore')

    def encrypt_and_or_decrypt_img(self, image_path: str):
        # 图片类型转换
        scr_file_path = Path(image_path)
        file_type = scr_file_path.suffix
        if file_type in ['.jpg', '.jpeg']:
            png_file_path = scr_file_path.with_suffix('.png')
            Image.open(image_path).convert("RGB").save(png_file_path)
            print_formatting(f"  已将.jpg/.jpeg图片转换为.png格式", f"{png_file_path.name}")
            image_path = png_file_path
            scr_file_path = Path(image_path)

        img = Image.open(image_path).convert("RGBA")
    ## 第一步：添加可见文本visible_text
        print_formatting("为图片添加可见文本",f"{self.visible_text}")
        txt_layer = Image.new('RGBA', img.size, self.color_for_img_layer)
        draw = ImageDraw.Draw(txt_layer)
        # 获取支持中文的字体
        font = self.get_chinese_font(self.font_size)
        # 添加文字（位置可根据需要调整）
        width, height = img.size
        # 兼容新旧版本的尺寸获取
        if hasattr(draw, 'textlength'):
            text_width = draw.textlength(self.visible_text, font=font)
            text_height = font.getbbox(self.visible_text)[3]  # 获取字体高度
        else:
            text_width, text_height = draw.textsize(self.visible_text, font=font)
        # final_position = (90,  60)  # 左上角
        final_position = (width - text_width - self.position[0], height -text_height - self.position[1])  # 右下角
        draw.text(final_position, self.visible_text, font=font, fill=self.color_for_visible_text)  # 红色文字
        img_with_text = Image.alpha_composite(img, txt_layer)

        file_path_with_text = scr_file_path.parent / (scr_file_path.stem + "_with_text" + scr_file_path.suffix)
        file_path_with_text = Path(file_path_with_text)
        img_with_text = img_with_text.convert("RGB")
        if self.validate_final_result:           
            img_with_text.save(file_path_with_text, format="PNG")
            print_formatting(f"   [+] 已添加可见文本，并保存", f"{file_path_with_text.name}")
        
    ## 第二步：添加不可见水印invisible_watermark    
        # Step 1: 加密水印
        print_formatting(f"为图片添加不可见水印", self.invisible_watermark)
        encrypted_watermark = self.encrypt(self.invisible_watermark)
        watermark_bin = self._bytes_to_bin(encrypted_watermark)

        # Step 2: 嵌入水印到每个像素的最低位
                
        pixels = list(img_with_text.getdata())
        new_pixels = []
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

        # Step 3: 保存图片
        img_with_text.putdata(new_pixels)
        file_path_with_text_watermark = file_path_with_text.parent / (file_path_with_text.stem + "_watermark" + file_path_with_text.suffix)
        file_path_with_text_watermark = Path(file_path_with_text_watermark)
        if self.validate_final_result:
            img_with_text.save(file_path_with_text_watermark, format="PNG")
            print_formatting(f"   [+] 已添加不可见水印，并保存", file_path_with_text_watermark.name)
    
    ## 第三步：添加元数据aigc_metadata        
        print_formatting("为图片添加AIGC元数据",f"{self.aigc_metadata}")
        file_type = file_path_with_text_watermark.suffix
        # 转为 JSON 字符串
        aigc_json = json.dumps(self.aigc_metadata, ensure_ascii=False)
        if file_type in ['.png']:
            # 从原始图片中复制元数据（如果有的话）
            pnginfo = PngInfo()
            if 'pnginfo' in img_with_text.info:
                for k, v in img_with_text.info['pnginfo'].items():
                    pnginfo.add_text(k, v)
            
            pnginfo.add_text("AIGC_JSON", aigc_json)
            file_path_with_text_watermark_and_metadata = file_path_with_text_watermark.parent / (file_path_with_text_watermark.stem + "_and_metadata" + file_path_with_text_watermark.suffix) 
            file_path_with_text_watermark_and_metadata = Path(file_path_with_text_watermark_and_metadata)
            if self.validate_final_result:
                img_with_text.save(file_path_with_text_watermark_and_metadata, pnginfo=pnginfo)
                scr_file_path = file_path_with_text_watermark_and_metadata
                print_formatting(f"   [+] 已添加AIGC元数据，并保存", file_path_with_text_watermark_and_metadata.name)
            else:
                img_with_text.save(scr_file_path, pnginfo=pnginfo)
                print_formatting(f"图片已添加文本/水印/元数据", scr_file_path.name)
                self.validate_image(scr_file_path)
                return scr_file_path            
        else:
            print_formatting(f"暂不支持的图片格式",file_type)
            return None

    ## 第四步：验证最终结果
        if self.validate_final_result:          
            self.validate_image(scr_file_path)

    def get_chinese_font(self, font_size=20):
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
                    "/data/projects/JqChatV2/JqChat/.Fonts_CN/MSYH/MSYH.TTC",
                    "/data/projects/JqChatV2/JqChat/.Fonts_CN/MSYH/MSYHBD.TTC",
                    "/data/projects/JqChatV2/JqChat/.Fonts_CN/MSYH/MSYHL.TTC",
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
    def extract_watermark(self, image_or_path: Image.Image | str, watermark_length: int) -> str:
        # Step 1: 读取图片
        if isinstance(image_or_path, str):
            img = Image.open(image_or_path).convert("RGB")
        else:
            img = image_or_path
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

    def validate_image(self, scr_file_path: str):
        # 验证图片中元数据是否添加成功
        img_with_text_and_watermark_watermark = Image.open(scr_file_path).convert("RGB")
        print_formatting(f"🎯 最终验证图片{Path(scr_file_path).name}中元数据是否添加成功",img_with_text_and_watermark_watermark.info)  # 查看是否包含 'AIGC_JSON'

        # 解密和提取水印
        encrypt_watermark_length = len(self.encrypt(self.invisible_watermark))
        watermark = self.extract_watermark(img_with_text_and_watermark_watermark, watermark_length=encrypt_watermark_length)
        print_formatting(f"🎯 最终验证图片{Path(scr_file_path).name}中不可见水印是否提取成功",watermark)
        # 查看可见文本
        print_formatting(f"🎯 打开查看图片{Path(scr_file_path).name}中可见文本是否添加成功",self.visible_text) 

if __name__ == "__main__":
    # 测试代码   
    validate_image = fr"/data/projects/JqChatV2/JqChat/jqcode/jq_utils/jq_watermark_func_and_result/图片/test.jpg"
    wm = ImageWatermark()

    # print("====不验证结果========================================================================================================")
    # result = wm.encrypt_and_or_decrypt_img(validate_image)
    # print(f"返回结果文件路径: {result}")

    # print("====验证结果========================================================================================================")
    # wm = ImageWatermark(validate_final_result=True)
    # result = wm.encrypt_and_or_decrypt_img(validate_image)
    # print(f"返回结果文件路径: {result}")

    print("====仅仅验证结果========================================================================================================")
    wm.validate_image("/data/projects/JqChatV2/JqChat/jqcode/jq_utils/jq_watermark_func_and_result/图片/v1-1.png")
    wm.validate_image("/data/projects/JqChatV2/JqChat/jqcode/jq_utils/jq_watermark_func_and_result/图片/v1-2.png")
    wm.validate_image("/data/projects/JqChatV2/JqChat/jqcode/jq_utils/jq_watermark_func_and_result/图片/v2-1.png")
    wm.validate_image("/data/projects/JqChatV2/JqChat/jqcode/jq_utils/jq_watermark_func_and_result/图片/v2-2.png")
    
