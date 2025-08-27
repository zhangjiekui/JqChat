import os
import json
import time
import logging
from typing import List
from fastapi.middleware.cors import CORSMiddleware

from jqcode.langgraph_in_class import GraphAgent
from jqcode.jq_docstores.backend_docstore_utils.jq_es_metastores import JqElasticsearchUniMetaStore
from openai.types.chat import ChatCompletion
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse
from jqcode.jq_mcp.utils import ThreadWithResult, get_process_text,chat
# 配置日志记录
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# 有效API Key集合
VALID_API_KEYS = {"","abc123"}  # 替换为实际密钥
BY_PASS_VALIDATING = False
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
            logger.warning(f"知识库 {kb_name} 不存在，将返回默认的知识库信息！")
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
## 请求验证中间件
@app.middleware("http")
async def validate_request(request: Request, call_next): 
    try:
        # 验证内容类型(针对POST/PUT)
        if request.method in ("POST", "PUT") and \
           "content-type" not in request.headers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing Content-Type header"
            )
        # 验证必要头信息
        if not BY_PASS_VALIDATING:
            if "authorization" not in request.headers:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing Authorization header"
                )
        authorization = request.headers["authorization"]
        api_key = authorization[7:] # 提取Bearer后的部分            
        if api_key not in VALID_API_KEYS:
            logger.warning(f"Invalid API Key attempt: {api_key}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid API Key"
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

        
@app.get("/models", response_model=None)
@app.get("/v1/models", response_model=None)
async def listModels(request: Request):
    return {
        "object": "list",
        "data": [
            {
                "id": "default",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "JqNetwork"
            }
        ]
    }

# OpenAI聊天接口(POST)
@app.post("/v1/chat/completions")
async def chat_completions(request: Request) -> str | dict | ChatCompletion:
    # await verify_api_key(request.headers.get("authorization"))    
    try:
        data = await request.json()
        streaming = data.get("stream", True)
        use_memory = True
        rewrite_question = False
        for _,v in data.items():
            if isinstance(v,dict):
                if "memory" in v:
                    use_memory_str = v.get("memory","True")
                    if use_memory_str.lower() == "false":
                        use_memory = False
                if "rewrite" in v:
                    rewrite_question_str = v.get("rewrite","False")
                    if rewrite_question_str.lower() == "true":
                        rewrite_question = True        
        logger.info(f"Request data: {streaming=}")        
        # 验证必要字段
        if "messages" not in data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required field: messages"
            )        
        kb_name = data.get("model", default_kb_name)
        kb_base_dict = get_kb_dict(kb_name)
        api_deployment_url = os.getenv("api_deployment_url")

        user_info = data.get("metadata",None)
        user_name_id = ''
        if user_info:
            try:
                user_name = user_info.get("userName") or user_info.get("username")
                user_id = user_info.get("userId") or user_info.get("userid")
                user_name_id = f'{user_name}({user_id})'
            except:
                pass

        memory_thread_id = user_name_id
        # memory_thread_id = user_name_id or request.user.username
        if memory_thread_id:
            chat_bot = GraphAgent(kb_base_dict=kb_base_dict,user_rquest_url=api_deployment_url,memory_thread_id=memory_thread_id,allow_conversation_memory=use_memory,allow_question_rewrite=rewrite_question)
        else:
            chat_bot = GraphAgent(kb_base_dict=kb_base_dict,user_rquest_url=api_deployment_url,allow_question_rewrite=rewrite_question)
        query = data["messages"][-1].get("content")
        while not isinstance(query, str):
            if isinstance(query, dict) and "text" in query:
                query = query["text"]
            if isinstance(query, list) and len(query) > 0:
                query = query[-1].get("text")
            else:
                logger.warning(f"Invalid query type:{type(query)}")
                pass

        t1 = ThreadWithResult(target=chat, args=(chat_bot,query,False))
        t1.start()
      
        # 流式输出（替换为你的 chat_bot 生成逻辑）
        if streaming:
            async def event_stream():
                for result in get_process_text(chat_bot.jq_queque,t1,streaming=streaming):
                    if result:
                        chunk = {
                            "id": f"chatcmpl-{int(time.time()*1000)}",
                            "object": "chat.completion.chunk",
                            "created": int(time.time()),
                            "model": "default",
                            "choices": [{
                                "index": 0,
                                "delta": {"content": result},
                                "finish_reason": None
                            }]
                        }
                        yield json.dumps(chunk)
                        # await asyncio.sleep(0.001)  # 控制输出速度
                
                
                # 发送结束标记
                yield json.dumps({
                    "choices": [{"finish_reason": "stop"}]
                })
            
            return EventSourceResponse(event_stream())

        # 非流式响应：完全兼容OpenAI格式
        else:
            # text = "暂时模拟的文本"
            result_generators = get_process_text(chat_bot.jq_queque,t1,streaming=streaming)
            text = "".join(result_generators)
            # print(">>>>>>>"*10)
            # print(text)
            # print(">>>>>>>"*10)
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
                        "content": text  # 确保是纯字符串，我故意简化了，防止干扰显示
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
            result = JSONResponse(content=response_data,status_code=status.HTTP_200_OK,headers={"Content-Type": "application/json"})  # 明确使用JSON响应
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