import openai
import logging
from typing import List,Any
from fastapi.middleware.cors import CORSMiddleware
from jqcode.langgraph_in_class import GraphAgent
from jqcode.jq_docstores.backend_docstore_utils.jq_es_metastores import JqElasticsearchUniMetaStore
from openai.types.responses.response_item import ResponseItem
from openai.types.chat.chat_completion import ChatCompletion
from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from ollama_api import OllamaClient
# 配置日志记录
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

default_kb_name = "zjk_jqesclient_reader_test_768im"
default_kb_description = "关于安徽晶奇网络科技股份有限公司（简称晶奇公司），以及医疗卫生、医疗健康、医疗服务、医疗政策、民政养老、社会救助、低保、低收入人口认定、退伍军人、优待抚恤等领域的政策文件、信息化产品、建设方案、技术文档等等方面的文档知识库。 \n凡是涉及安徽晶奇网络科技股份有限公司及以上领域相关的问题，或者是用户提及检索知识库或vectorstore时，都必须使用vectorstore工具。"
metastore = JqElasticsearchUniMetaStore()

# from ollama import Client
# from ollama import chat
# from ollama import ChatResponse
# try:
#     client = Client(
#     host='http://10.1.150.105:9998/v1/chat/completions',
#     headers={'Authorization': 'Bearer abc123'}
#     )

#     response = client.chat(model='qwen3', stream=False,messages=[
#             {
#                 'role': 'user',
#                 'content': 'Why is the sky blue?',
#             },
#         ])
# except Exception as e:
#     print(e.response)
# print(response['message']['content'])
# # or access fields directly from the response object
# print(response.message.content)
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
@app.get("/health") # for a health check
async def health_check():
    return {"code":200,"status": "ok"}

@app.get("/ping") # for a health check
async def ping():
    return {"code":200,"status": "ok"}
@app.get("/v1/models", response_model=Any)
async def listModels():
    return ["default"]

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
        # # 初始化OpenAI客户端
        base_url = chat_bot.model.bound.api_base
        api_key = chat_bot.model.bound.api_key
        llm_model_name = chat_bot.model.bound.model_name
        client = openai.OpenAI(base_url=base_url,api_key=api_key._secret_value)        
        # 调用OpenAI API
        response = client.chat.completions.create(
            model=llm_model_name,
            messages=[{'role': 'user', 'content': '测试'}],
            stream=False
        )
        # response.choices[0].message.content = "response text"
        # response.model = kb_name
        # result = response.json()
        result = response.model_dump_json()
        print("\n\nOpenAI API response:")
        print(result)
        return result
        
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