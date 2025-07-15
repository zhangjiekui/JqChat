# using py311 env
import asyncio
import time
from argparse import Namespace
from ocrflux.client import request
start_time = time.time()
args = Namespace(
    model="nanonets",
    skip_cross_page_merge=False,
    max_page_retries=1,
    url="http://10.1.150.105",
    port=8008,
)
file_path = "/data/projects/JqChatV2/JqChat/JqR2R/py/core/examples/data/DeepSeek_R1.pdf"
file_path = "/data/projects/JqChatV2/JqChat/docext/晶奇招股说明书.pdf"
# file_path = '/data/projects/JqChatV2/JqChat/ocr.png'
result = asyncio.run(request(args,file_path))
if result != None:
    document_markdown = result['document_text']
    # print(document_markdown)
    with open('test.md','w') as f:
        f.write(document_markdown)
else:
    print("Parse failed.")
_time = time.time() - start_time
print(f"   ..... Elapsed {_time:.2f}s")
