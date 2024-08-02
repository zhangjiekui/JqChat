

from typing import Dict
from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse





from jqcode.jq_knowledge_manegement.chatchat.server.api_server.api_schemas import OpenAIChatInput



chat_router = APIRouter(prefix="/chat", tags=["Chat对话"])



@chat_router.post("/completions", summary="对话接口")
async def chat_completions() :

    # user_prompt = request.json.get('prompt', '')
    code="int i=0"
    text="我是一个测试回复"
    resp=JSONResponse(content={"code":code,"text":text})
    print("*"*30)
    print(resp)
    return resp
