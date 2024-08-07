

from typing import Dict
from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse





from jqcode.jq_knowledge_manegement.chatchat.server.api_server.api_schemas import OpenAIChatInput



chat_router = APIRouter(prefix="/chat", tags=["Chat对话"])



@chat_router.post("/completions", summary="对话接口")
async def chat_completions(
    user_prompt: str = Body(alias="query",description="用户输入"),
    doc_id: str = Body(alias="doc", description="知识库ID"),
    user_id: str = Body(alias="user", description="用户随机ID"),
    
) :

    # user_prompt = request.json.get('prompt', '')
    print(user_prompt,doc_id,user_id)
    code=f"""
    ```python 
    #!/usr/bin/env python3
    print('Hello, World!');
    
    ```
    """
    text=f"""
    Markdown 目录：
[TOC]

Markdown 标题：
# 这是 H1
## 这是 H2
### 这是 H3

Markdown 列表：
- 列表项目
1. 列表项目

*斜体*或_斜体_
**粗体**
***加粗斜体***
~~删除线~~

Markdown 插入链接：
[链接文字](链接网址 "标题")

Markdown 插入图片：
![alt text](/path/to/img.jpg "Title")

Markdown 插入代码块：
    ```python
    #!/usr/bin/python3
    print("Hello, World!");
    ```

Markdown 引用：
> 引用内容

Markdown 分割线：
---

Markdown 换行：
<br>

Markdown 段首缩进：
&ensp; or &#8194; 表示一个半角的空格
&emsp; or &#8195;  表示一个全角的空格
&emsp;&emsp; 两个全角的空格（用的比较多）
&nbsp; or &#160; 不断行的空白格
    """
    resp=JSONResponse(content={"code":code,"text":user_prompt+text})
    print("*"*30)
    print(resp)
    return resp
