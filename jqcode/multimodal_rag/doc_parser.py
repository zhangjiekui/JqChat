# doc_parser.py
import re
from pathlib import Path
from typing import List, Dict
from dataclasses import dataclass
from embedder_wrapper import MultimodalInput

@dataclass
class ParsedDocument:
    """解析后的文档"""
    doc_id: str
    file_path: str
    title: str
    units: List[MultimodalInput]  # 有序的文本/图片列表 ⭐
    metadata: Dict

class MarkdownParser:
    """Markdown 文档解析器 - 保留文本/图片的交错顺序"""
    
    def parse_file(self, file_path: str, base_image_path: str = "./assets") -> ParsedDocument:
        """
        解析 Markdown 文件，输出有序的 MultimodalInput 列表
        """
        path = Path(file_path)
        content = path.read_text(encoding='utf-8')
        lines = content.split('\n')
        
        units = []
        title = ""
        
        heading_pattern = re.compile(r'^(#{1,6})\s+(.+)$')
        image_pattern = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
        
        current_text_lines = []
        in_code_block = False
        
        for i, line in enumerate(lines):
            # 检测代码块
            if line.strip().startswith('```'):
                in_code_block = not in_code_block
                continue
            
            # 检测图片
            img_match = image_pattern.search(line)
            if img_match:
                # 保存之前的文本块
                if current_text_lines:
                    text_content = '\n'.join(current_text_lines).strip()
                    if text_content:
                        units.append(MultimodalInput(type="text", content=text_content))
                    current_text_lines = []
                
                # 添加图片单元
                img_url = img_match.group(2)
                # 处理相对路径
                if not img_url.startswith("http"):
                    img_url = str(Path(base_image_path) / img_url)
                
                units.append(MultimodalInput(type="image", content=img_url))
                continue
            
            # 检测标题
            heading_match = heading_pattern.match(line)
            if heading_match:
                # 保存之前的文本块
                if current_text_lines:
                    text_content = '\n'.join(current_text_lines).strip()
                    if text_content:
                        units.append(MultimodalInput(type="text", content=text_content))
                    current_text_lines = []
                
                # 添加标题
                level = len(heading_match.group(1))
                if level == 1 and not title:
                    title = heading_match.group(2)
                
                units.append(MultimodalInput(type="text", content=line))
                continue
            
            # 普通文本
            if line.strip():
                current_text_lines.append(line)
        
        # 保存最后一个文本块
        if current_text_lines:
            text_content = '\n'.join(current_text_lines).strip()
            if text_content:
                units.append(MultimodalInput(type="text", content=text_content))
        
        return ParsedDocument(
            doc_id=path.stem,
            file_path=str(path.absolute()),
            title=title or path.stem,
            units=units,
            metadata={
                "total_units": len(units),
                "text_units": sum(1 for u in units if u.type == "text"),
                "image_units": sum(1 for u in units if u.type == "image"),
                "file_size": path.stat().st_size
            }
        )
    
    def split_to_chunks(
        self,
        doc: ParsedDocument,
        max_units_per_chunk: int = 10,
        max_text_length: int = 1000
    ) -> List[List[MultimodalInput]]:
        """
        将文档分割成多个 chunk，每个 chunk 保持内部顺序
        """
        chunks = []
        current_chunk = []
        current_text_len = 0
        
        for unit in doc.units:
            # 检查是否需要开始新 chunk
            if (
                len(current_chunk) >= max_units_per_chunk or
                (unit.type == "text" and 
                 current_text_len + len(unit.content) > max_text_length and
                 current_chunk)
            ):
                chunks.append(current_chunk)
                current_chunk = []
                current_text_len = 0
            
            current_chunk.append(unit)
            if unit.type == "text":
                current_text_len += len(unit.content)
        
        # 最后一个 chunk
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks