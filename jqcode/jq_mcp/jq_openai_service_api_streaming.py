import os
import json
import time
from typing import List
from jqcode.langgraph_in_class import GraphAgent
from jqcode.jq_docstores.backend_docstore_utils.jq_es_metastores import JqElasticsearchUniMetaStore
from openai.types.chat import ChatCompletion
from fastapi import FastAPI, HTTPException, Request, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse
from jqcode.jq_mcp.utils import ThreadWithResult, get_process_text,chat
from jqcode.r2r_client_functions import r2r_authed_client
# from fastapi_bgtasks_dashboard import mount_bg_tasks_dashboard

from jqcode.jq_utils.logger import jqkj_logger
logger = jqkj_logger(__file__).get_logger()
# import logging
# # 配置日志记录
# logging.basicConfig(
#     level=logging.WARNING,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# )
# logger = logging.getLogger(__name__)

# 有效API Key集合
VALID_API_KEYS = {"","abc123","sk-0S7bV3oaznhuevN899Db0cDa20Ae4c5485Ce5862A86063C8"}  # 替换为实际密钥
BY_PASS_VALIDATING = False
default_kb_name = "zjk_jqesclient_reader_test_768im"
default_kb_name = "default"
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
# mount_bg_tasks_dashboard(app=app)
# 定义装饰器别名，允许在没有limiter时跳过
def optional_limiter(limit_str: str):
    def decorator(func):
        # 检查 limiter 变量是否存在
        if limiter:
            logger.warning(f"🎯 Applying rate limit '{limit_str}' to {func.__name__}")
            return limiter.limit(limit_str)(func)
        else:
            logger.warning(f"⚠️ Skipping rate limit for {func.__name__} (limiter not active)")
        return func
    return decorator

# CORS配置(供Chatbox调用)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Type", "Cache-Control"],  # 暴露流式响应必需头部
)

# 增加限流
# 初始化限流器，失败则设为 None
limiter = None
try: 
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
    # Initialize limiter
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    if limiter:
        app.add_middleware(SlowAPIMiddleware)  # 可选：启用中间件支持
except ImportError:
    logger.warning("未安装slowapi，请使用以下命令安装：pip install slowapi")
except Exception as e:
    logger.warning(f"slowapi限流添加错误：{e}")

@app.exception_handler(RateLimitExceeded)
async def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded):
    client_ip = request.client.host if request.client else "unknown"
    # print(f"🚨 限流触发: {request.url} | 客户端: {client_ip} | 限流规则: {exc.detail}")
    logger.warning(f"🚨 限流触发: {request.url} | 客户端: {client_ip} | 限流规则: {exc.detail}")
    return _rate_limit_exceeded_handler(request, exc)  # 返回默认响应

# 监控中间件：放在 validate 之前，确保能捕获所有 429
@app.middleware("http")
async def monitor_rate_limit(request: Request, call_next):
    response = await call_next(request)
    if response.status_code == 429:
        # print(f"🚨 限流触发: {request.url} from {request.client.host}")
        logger.debug(f"🚨 限流触发: {request.url} from {request.client.host}")
    return response

# 验证中间件
@app.middleware("http")
async def validate_request(request: Request, call_next): 
    if request.method == "OPTIONS":
        return await call_next(request)
    try:
        # 验证内容类型(针对POST/PUT)
        if request.method in ("POST","GET", "PUT") and \
           "content-type" not in request.headers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing Content-Type header"
            )
        # 验证必要头信息
        if not BY_PASS_VALIDATING:
            auth_header = request.headers.get("authorization")
            if not auth_header:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing Authorization header"
                )
            if not auth_header.startswith("Bearer "):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid Authorization header format. Expected 'Bearer <token>'."
                )
            api_key = auth_header[7:] # 安全地提取Bearer后的部分           
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
@optional_limiter("5/second") # ← 限流装饰器在内层
async def listModels(request: Request):
    logger.warning(f"✅ limiter active: {limiter is not None}, app.state.limiter: {hasattr(app.state, 'limiter')}")
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

def simple_bg_task(name: str):
    import time
    print(f"Started task for {name}")
    time.sleep(20)
    print(f"Finished task for {name}")
# OpenAI聊天接口(POST)
@app.post("/v1/chat/completions")
# @optional_limiter("1/hour")  # 每小时1次，测试用
@optional_limiter("3/second") # ← 限流装饰器在内层
async def chat_completions(request: Request,  background_tasks: BackgroundTasks) -> str | dict | ChatCompletion:
    logger.warning(f"✅ limiter active: {limiter is not None}, app.state.limiter: {hasattr(app.state, 'limiter')}")
    streaming = False   
    try:
        data = await request.json()
        streaming = data.get("stream", False)
        if isinstance(streaming, str):
            streaming =False if streaming.lower() == "false" else True
        use_memory = True
        rewrite_question = False
    
        logger.warning(f"generator test: Received request original data: {data}")
        logger.warning(f"generator test: get {streaming=} from request data")        
        # 验证必要字段
        if "messages" not in data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required field: messages"
            )        
        kb_name = data.get("model", default_kb_name)
        kb_base_dict = get_kb_dict(kb_name)
        api_deployment_url = os.getenv("api_deployment_url")

        metadata = data.get("metadata",None)
        logger.warning(f"metadata: {metadata}")
        user_name_id = ''
        if metadata:
            try:
                user_info = metadata.get("userInfo",{})  or metadata.get("userinfo",{})
                user_info = user_info or metadata
                if user_info:
                    user_name = user_info.get("userName") or user_info.get("username")
                    # background_tasks.add_task(simple_bg_task, user_name)
                    user_id = user_info.get("userId") or user_info.get("userid")
                    user_name_id = f'{user_name}({user_id})'
                
                kb_dict = metadata.get("kb",{})
                kb_id = kb_dict.get("id",None)
                kb_name = kb_dict.get("name",default_kb_name)
                if user_name and kb_id:
                    r2r_client = r2r_authed_client(user_id=user_name)
                    kb_info = r2r_client.collections.retrieve(kb_id).results
                    kb_base_dict = {"index_name": kb_info.name or default_kb_name, "description":kb_info.description or default_kb_description}
                else:                    
                    kb_base_dict = get_kb_dict(kb_name)
                use_memory_str = str(metadata.get("memory","True"))
                if use_memory_str.lower() == "false":
                    use_memory = False
                rewrite_question_str = str(metadata.get("rewrite","False"))
                if rewrite_question_str.lower() == "true":
                    rewrite_question = True  
            except:
                pass
        else:
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

        memory_thread_id = user_name_id
        # memory_thread_id = user_name_id or request.user.username
        if memory_thread_id:
            chat_bot = GraphAgent(kb_base_dict=kb_base_dict,user_request_url=api_deployment_url,memory_thread_id=memory_thread_id,allow_conversation_memory=use_memory,allow_question_rewrite=rewrite_question)
        else:
            chat_bot = GraphAgent(kb_base_dict=kb_base_dict,user_request_url=api_deployment_url,allow_question_rewrite=rewrite_question)
        messages = data["messages"]
        query = ""
        query_text = ""
        if len(messages) > 1:
            logger.warning(f"初始消息列表 messages 长度为 {len(messages)}，仅使用最后一条用户消息作为用户提问内容！")
            for message in messages:
                if message.get("role","") == "user":
                    logger.warning(f"用户消息内容: {message.get('content','')}")
                    query = message.get("content", "") or message.get("text", "")
        else:
            message = messages[0]
            query = message.get("content", "") or message.get("text", "")

        # # 测试使用
        # streaming = False #须在cherry studio助手设置中将流式输出关闭（streaming参数强制设为False），才能正确显示完整回答内容
        # raise Exception("警告！未获取到有效的提问内容，请检查！")
        # # 测试使用    

        if not query:
            raise Exception("警告！未获取到有效的提问内容，请检查！")
        logger.warning(f"提取到的最后一条用户消息内容为: {query}")
        while not isinstance(query, str):
            if isinstance(query, dict) and "text" in query:
                query_text = query["text"]
                query=query_text
            if isinstance(query, list) and len(query) > 0:
                for q in query:
                    if isinstance(q, dict) and "text" in q:                        
                        query_text += q.get("text")
                query=query_text
            else:
                logger.warning(f"Invalid query type {type(query)=} or content: {query=}")
                query = "警告！未获取到有效的提问内容，请检查！"
                pass

        t1 = ThreadWithResult(target=chat, args=(chat_bot,query,False))
        t1.start()
      
        # 流式输出（替换为你的 chat_bot 生成逻辑）
        if streaming:
            logger.warning(f"\n>>> 流式响应模式，streaming={streaming}, type={type(streaming)}")
            async def event_stream():
                for result in get_process_text(chat_bot.jq_queque,t1):
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
        # streaming = False cherry studio须在助手设置中将流式输出关闭（streaming参数强制设为False），才能正确显示完整回答内容
        else:
            try:
                # 添加调试日志
                logger.warning(f"\n>>> 非流式响应模式，streaming={streaming}, type={type(streaming)}")
                text = ""
                # i = 0
                for value in get_process_text(chat_bot.jq_queque,t1):
                    # i += 1                   
                    # logger.warning(f"generator test: result_list or generator value {i}: {value}")  # 调试输出每个值及其类型
                    if value.strip():
                        text += value
                    # logger.warning(f"generator test:final text {i}: {text}")

                if not text.strip():
                    text = "未获取到有效的回答内容，请检查智能体处理流程！"
                logger.warning(f"generator test 非流式模式下的最终结果: {text}")
            except Exception as e:
                logger.error(f"处理结果时发生错误: {e}")
                text = f"处理结果时发生错误: {str(e)}"


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
        _error_str =str(e) or e.__str__
        error_msg = f"调用智能体API出现错误: {_error_str}"
        logger.error(error_msg)
        if streaming:
            async def event_stream():
                chunk = {
                    "id": f"chatcmpl-{int(time.time()*1000)}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": "default",
                    "choices": [{
                        "index": 0,
                        "delta": {"content": error_msg},
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
            text = error_msg
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




if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8601,
        log_level="debug",
        timeout_keep_alive=60
    )