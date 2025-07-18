import os
import uvicorn
from fastapi import Body, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import RedirectResponse

from jqcode.jq_kb_manegement.configs import CHATCHAT_ROOT, MEDIA_PATH, OPEN_CROSS_DOMAIN, VERSION

from jqcode.api_server.kb_routes import kb_router
from jqcode.jq_kb_manegement.server.utils import MakeFastAPIOffline
def create_app(run_mode: str = None):
    from jq_server.jq_chat_routes import chat_router,workspace_router
    app = FastAPI(title="JqChat API Server", version=VERSION)
    MakeFastAPIOffline(app)
    # Add CORS middleware to allow all origins
    # 在config.py中设置OPEN_DOMAIN=True，允许跨域
    # set OPEN_DOMAIN=True in config.py to allow cross-domain
    if OPEN_CROSS_DOMAIN:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.get("/", summary="swagger 文档", include_in_schema=False)
    async def document():
        return RedirectResponse(url="/docs")

    app.include_router(chat_router)
    app.include_router(kb_router)
    app.include_router(workspace_router)
    # app.include_router(api_router)
    # # app.include_router(server_router)

    # 其它接口
    # app.post(
    #     "/other/completion",
    #     tags=["Other"],
    #     summary="要求llm模型补全(通过LLMChain)",
    # )(completion)

    # 媒体文件
    app.mount("/media", StaticFiles(directory=MEDIA_PATH), name="media")

    # 项目相关图片
    print(f"  本地知识库存储路径:{CHATCHAT_ROOT}")
    img_dir = os.path.join(CHATCHAT_ROOT, "img")
    app.mount("/img", StaticFiles(directory=img_dir), name="img")

    return app


def run_api(host, port, **kwargs):
    if kwargs.get("ssl_keyfile") and kwargs.get("ssl_certfile"):
        uvicorn.run(
            app,
            host=host,
            port=port,
            ssl_keyfile=kwargs.get("ssl_keyfile"),
            ssl_certfile=kwargs.get("ssl_certfile"),
        )
    else:
        uvicorn.run(app, host=host, port=port)


app = create_app()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        prog="Jq Rag Server",
        description="Jq local knowledge based Rag"
        " ｜ 基于本地知识库的问答",
    )
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=7863)
    parser.add_argument("--ssl_keyfile", type=str)
    parser.add_argument("--ssl_certfile", type=str)
    # 初始化消息
    args = parser.parse_args()
    args_dict = vars(args)

    run_api(
        host=args.host,
        port=args.port,
        ssl_keyfile=args.ssl_keyfile,
        ssl_certfile=args.ssl_certfile,
    )
