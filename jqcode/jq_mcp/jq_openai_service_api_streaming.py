import json
import time
import logging
from typing import List,Any
from fastapi.middleware.cors import CORSMiddleware
from jqcode.langgraph_in_class import GraphAgent
from jqcode.jq_docstores.backend_docstore_utils.jq_es_metastores import JqElasticsearchUniMetaStore
from openai.types.responses.response_item import ResponseItem
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types import CompletionUsage
from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from ollama_api import OllamaClient
import asyncio
from sse_starlette.sse import EventSourceResponse
# 配置日志记录
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

default_kb_name = "zjk_jqesclient_reader_test_768im"
default_kb_description = "关于安徽晶奇网络科技股份有限公司（简称晶奇公司），以及医疗卫生、医疗健康、医疗服务、医疗政策、民政养老、社会救助、低保、低收入人口认定、退伍军人、优待抚恤等领域的政策文件、信息化产品、建设方案、技术文档等等方面的文档知识库。 \n凡是涉及安徽晶奇网络科技股份有限公司及以上领域相关的问题，或者是用户提及检索知识库或vectorstore时，都必须使用vectorstore工具。"
metastore = JqElasticsearchUniMetaStore()
def get_kbs() -> List[dict]:
    """提供全部知识库的名称和描述列表"""
    all_kbs_meta = metastore.get_all_docs()
    all_kbs = [kb["_source"] for kb in all_kbs_meta]
    all_kbs.sort(key=lambda x: x["index_name"])
    return all_kbs
def get_kb_dict(kb_name:str) -> dict:
    """根据知识库名称，提供全部知识库的名称和描述的字典dict"""
    if not kb_name:
        return {"index_name": default_kb_name, "description":default_kb_description}
    else:
        kb_dict = {}
        all_kbs = get_kbs()
        for _kb in all_kbs:
            if _kb["index_name"] == kb_name:
                kb_dict = _kb
                description = _kb.get("description",default_kb_description)
                if description!=default_kb_description:
                    description = f"{description}\n或者\n{default_kb_description}"
                kb_dict=  {"index_name": kb_name, "description":description}
                break
        if not kb_dict:
            print(f"知识库 {kb_name} 不存在，将返回默认的知识库信息！")
            kb_dict=  {"index_name": default_kb_name, "description":default_kb_description}
    return kb_dict

app = FastAPI()
# CORS配置(供Chatbox调用)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Type", "Cache-Control"],  # 暴露流式响应必需头部
)

# 有效API Key集合
VALID_API_KEYS = {"","abc123"}  # 替换为实际密钥
BY_PASS_VALIDATING = True
# # 请求验证中间件
@app.middleware("http")
async def validate_request(request: Request, call_next):        
    try:
        # 记录请求信息
        logger.info(f"Request received: {request.method} {request.url}")
        logger.info(f"Headers: {request.headers}")
        
        # 验证必要头信息
        if not BY_PASS_VALIDATING:
            if "authorization" not in request.headers:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing Authorization header"
                )            
        # 验证内容类型(针对POST/PUT)
        if request.method in ("POST", "PUT") and \
           "content-type" not in request.headers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing Content-Type header"
            )
            
        return await call_next(request)
        
    except HTTPException as e:
        logger.error(f"Request validation failed: {e.detail}")
        return JSONResponse(
            status_code=e.status_code,
            content={"detail": e.detail}
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"}
        )
# API Key验证函数
async def verify_api_key(authorization: str = Header(None)):
    if BY_PASS_VALIDATING:
        pass
    else:
        if not authorization or not authorization.startswith("Bearer "):
            logger.warning("Invalid Authorization header format")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid Authorization Header format. Expected 'Bearer <token>'"
            )
        api_key = authorization[7:]  # 提取Bearer后的部分
        if api_key not in VALID_API_KEYS:
            logger.warning(f"Invalid API Key attempt: {api_key}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid API Key"
            )
        
@app.get("/v1/models")
async def listModels():
    return {
        "object": "list",
        "data": [
            {
                "id": "default",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "organization"
            }
        ]
    }

# OpenAI聊天接口(POST)
@app.post("/v1/chat/completions")
async def chat_completions(request: Request) -> str | dict | ChatCompletion:
    await verify_api_key(request.headers.get("authorization"))    
    try:
        data = await request.json()
        logger.info(f"Request data: {data}")        
        # 验证必要字段
        if "messages" not in data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required field: messages"
            )        
        kb_name = data.get("model", default_kb_name)
        kb_base_dict = get_kb_dict(kb_name)   
        chat_bot = GraphAgent(kb_base_dict=kb_base_dict)
        query = data["messages"][-1].get("content")
        if not isinstance(query, str):
            if isinstance(query, dict) and "text" in query:
                query = query["text"]
            if isinstance(query, list) and len(query) > 0:
                query = query[-1].get("text")
        text = chat_bot.run_conversation(user_question=query)

        # 模拟流式输出（替换为你的 chat_bot 生成逻辑）
        async def event_stream():
            # text = "这是分步返回的测试响应"
            for char in text:
                chunk = {
                    "id": f"chatcmpl-{int(time.time()*1000)}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": "default",
                    "choices": [{
                        "index": 0,
                        "delta": {"content": char},
                        "finish_reason": None
                    }]
                }
                yield json.dumps(chunk)
                await asyncio.sleep(0.002)  # 控制输出速度
            # 发送结束标记
            yield json.dumps({
                "choices": [{"finish_reason": "stop"}]
            })
        
        return EventSourceResponse(event_stream())

        # 非流式响应：完全兼容OpenAI格式
        # text = query = kb_name
        response_data = {
            "id": f"chatcmpl-{int(time.time()*1000)}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": kb_name,
            "system_fingerprint": "fp_" + str(hash(kb_name))[:8],  # 必需字段:cite[1]
            "choices": [{
                "index": 0,
                "message": {  # 必须是字典而非对象
                    "role": "assistant",
                    "content": f"回复的字符串:{text}"  # 确保是纯字符串，我故意简化了，防止干扰显示
                },
                "logprobs": None,  # 必需字段:cite[5]
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": len(query.split()),  # 示例计算
                "completion_tokens": len(text.split()),
                "total_tokens": len(query.split()) + len(text.split()),
                "completion_tokens_details": {  # 必需子字段:cite[1]
                    "reasoning_tokens": 0,
                    "accepted_prediction_tokens": 0,
                    "rejected_prediction_tokens": 0
                }
            }
        }
        print("\n\nResponse Data:")
        print(response_data)
        result = JSONResponse(content=response_data,headers={"Content-Type": "application/json"})  # 明确使用JSON响应
        print("\n\nOpenAI API response:")
        print(result)
        return result  # 明确使用JSON响应


        
    except Exception as e:
        logger.error(f"OpenAI API error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing request: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8600,
        log_level="debug",
        timeout_keep_alive=60
    )