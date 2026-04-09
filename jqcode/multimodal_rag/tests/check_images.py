# check_images.py - 检查图片解析
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from doc_parser import MarkdownParser

test_file = "D:/claude_best_practice/claude_best_pracice.md"
parser = MarkdownParser()
doc = parser.parse_file(test_file, base_image_path="D:/claude_best_practice")

print(f"总单元数: {len(doc.units)}")
print(f"文本单元数: {doc.metadata['text_units']}")
print(f"图片单元数: {doc.metadata['image_units']}")

print("\n所有图片单元:")
for i, unit in enumerate(doc.units):
    if unit.type == "image":
        print(f"  [{i}] {unit.content}")

print("\n所有文本单元（前10个）:")
for i, unit in enumerate(doc.units[:10]):
    if unit.type == "text":
        print(f"  [{i}] TEXT: {unit.content[:60]}...")