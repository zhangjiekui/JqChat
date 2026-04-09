# embedder_wrapper.py
import os
import numpy as np
from typing import List, Dict, Optional
from dataclasses import dataclass
import dashscope

@dataclass
class MultimodalInput:
    """单个输入单元（文本或图片）"""
    type: str  # 'text' or 'image'
    content: str  # 文本内容或图片 URL/本地路径


class Qwen3VLEmbedder:
    """
    Qwen3-VL Embedding API 封装
    支持多文本 + 多图片输入 → 输出单个融合向量
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "qwen3-vl-embedding",
        dim: int = 1024
    ):
        """
        初始化 Qwen3-VL Embedder

        Args:
            api_key: DashScope API Key
            model: 模型名称 (qwen3-vl-embedding)
            dim: 向量维度
        """
        if api_key:
            dashscope.api_key = api_key
        elif os.getenv("DASHSCOPE_API_KEY"):
            pass
        else:
            raise ValueError("请设置 DASHSCOPE_API_KEY 环境变量或传入 api_key")

        self.model = model
        self.dim = dim
        print(f"[OK] Qwen3-VL Embedder | Model: {model} | Dim: {dim}")

    def _call_api(self, input_data: List[Dict]) -> np.ndarray:
        """
        调用 DashScope API 获取 embedding

        Args:
            input_data: 符合 qwen3-vl-embedding API 格式的输入

        Returns:
            np.ndarray: [dim] 向量
        """
        from dashscope import MultiModalEmbedding

        try:
            response = MultiModalEmbedding.call(
                model=self.model,
                input=input_data,
                dimension=self.dim
            )

            if response.status_code == 200:
                embedding = response.output["embeddings"][0]["embedding"]
                return np.array(embedding, dtype=np.float32)
            else:
                raise Exception(f"API Error: {response.code} - {response.message}")

        except Exception as e:
            print(f"[ERROR] API Call Failed: {e}")
            raise

    def encode_single_input(
        self,
        text: Optional[str] = None,
        image: Optional[str] = None,
        instruction: Optional[str] = None
    ) -> np.ndarray:
        """
        编码单个文本或图片 → 单个向量

        Args:
            text: 文本内容
            image: 图片路径（本地路径、Base64 或 URL）
            instruction: 任务指令
        """
        content = {}

        # 任务指令（作为 text 的一部分）
        if instruction:
            content["text"] = f"{instruction} {text}" if text else instruction
        elif text:
            content["text"] = text

        # 图片处理
        if image:
            content["image"] = self._process_image(image)

        if not content:
            raise ValueError("text 和 image 不能同时为空")

        # 包装成列表
        input_data = [content]

        return self._call_api(input_data)

    def _process_image(self, image: str) -> str:
        """
        处理图片输入，转换为 API 需要的格式

        支持:
        - URL: 直接返回
        - Base64: 直接返回
        - 本地文件路径: 转换为 Base64
        """
        # URL 或 Base64 直接返回
        if image.startswith("http") or image.startswith("data:"):
            return image

        # 本地文件路径：读取并转换为 Base64
        import base64
        from pathlib import Path

        path = Path(image)
        if not path.exists():
            raise FileNotFoundError(f"图片文件不存在: {image}")

        # 根据文件扩展名确定 MIME 类型
        ext = path.suffix.lower()
        mime_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
            ".bmp": "image/bmp",
            ".tiff": "image/tiff",
            ".tif": "image/tiff",
            ".ico": "image/x-icon",
            ".icns": "image/x-icns",
            ".sgi": "image/sgi",
        }
        mime_type = mime_types.get(ext, "image/jpeg")

        # 读取文件并编码为 Base64
        with open(path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        return f"data:{mime_type};base64,{image_data}"

    def encode_multimodal_chunk(
        self,
        inputs: List[MultimodalInput],
        instruction: Optional[str] = None,
        strategy: str = "fusion"
    ) -> np.ndarray:
        """
        编码多文本 + 多图片的有序列表 → 输出单个向量

        API 行为：
        - text + image 在同一个对象中 → 融合向量
        - 分开作为独立元素 → 独立向量

        Args:
            inputs: 有序的输入列表 [{text1}, {img1}, {text2}, ...]
            instruction: 任务指令
            strategy: 融合策略
                - "fusion": 将所有text和image放在同一个对象中，生成融合向量
                - "weighted_average": 每个text/image独立编码后加权平均

        Returns:
            np.ndarray: [dim] 单个向量
        """
        if not inputs:
            raise ValueError("inputs 不能为空")

        if strategy == "fusion":
            # 融合向量：将所有text和image放在同一个对象中
            content = {}

            # 添加指令
            if instruction:
                content["text"] = instruction

            # 收集所有文本
            texts = []
            for inp in inputs:
                if inp.type == "text":
                    texts.append(inp.content)

            if texts:
                all_text = " ".join(texts)
                if "text" in content:
                    content["text"] = content["text"] + " " + all_text
                else:
                    content["text"] = all_text

            # 收集所有图片
            images = []
            for inp in inputs:
                if inp.type == "image":
                    # 使用 _process_image 处理（支持本地路径、URL、Base64）
                    img_path = self._process_image(inp.content)
                    images.append(img_path)

            if images:
                # 只支持一个图片（API限制）
                content["image"] = images[0]

            if not content:
                raise ValueError("没有有效的 text 或 image 内容")

            # 调用 API 生成融合向量
            input_data = [content]
            embedding = self._call_api(input_data)

            # L2 归一化
            embedding = embedding / np.linalg.norm(embedding)

            return embedding

        elif strategy == "weighted_average":
            # 独立向量：每个text/image独立编码后加权平均
            embeddings = []
            weights = []

            for inp in inputs:
                if inp.type == "text":
                    vec = self.encode_single_input(text=inp.content, instruction=instruction)
                    embeddings.append(vec)
                    weights.append(1.0)

                elif inp.type == "image":
                    # 使用 _process_image 处理（支持本地路径、URL、Base64）
                    img_path = self._process_image(inp.content)
                    vec = self.encode_single_input(image=img_path, instruction=instruction)
                    embeddings.append(vec)
                    weights.append(1.0)

            if not embeddings:
                raise ValueError("没有有效的 text 或 image 内容")

            # 加权平均
            embeddings = np.array(embeddings)
            weights = np.array(weights)
            weights = weights / weights.sum()

            final_embedding = np.average(embeddings, axis=0, weights=weights)

            # L2 归一化
            final_embedding = final_embedding / np.linalg.norm(final_embedding)

            return final_embedding

        else:
            raise ValueError(f"Unknown strategy: {strategy}")

    def encode_query(
        self,
        texts: List[str],
        images: List[str],
        preserve_order: bool = True,
        instruction: Optional[str] = None
    ) -> np.ndarray:
        """
        编码用户查询（多文本 + 多图片）→ 单个向量
        每个文本/图片独立编码，然后加权平均
        """
        inputs = []

        # 构建输入列表
        if preserve_order:
            max_len = max(len(texts), len(images))
            for i in range(max_len):
                if i < len(texts) and texts[i].strip():
                    inputs.append(MultimodalInput(type="text", content=texts[i]))
                if i < len(images) and images[i]:
                    inputs.append(MultimodalInput(type="image", content=images[i]))
        else:
            # 先文本后图片
            for text in texts:
                if text.strip():
                    inputs.append(MultimodalInput(type="text", content=text))
            for img in images:
                if img:
                    inputs.append(MultimodalInput(type="image", content=img))

        if not inputs:
            raise ValueError("查询不能为空")

        return self.encode_multimodal_chunk(inputs, instruction=instruction, strategy="weighted_average")