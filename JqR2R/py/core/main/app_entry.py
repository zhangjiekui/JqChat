import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.base import R2RException
from core.utils.logging_config import configure_logging

from .assembly import R2RBuilder, R2RConfig

log_file = configure_logging()

# Global scheduler
scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    r2r_app = await create_r2r_app(
        config_name=config_name,
        config_path=config_path,
    )

    # Copy all routes from r2r_app to app
    app.router.routes = r2r_app.app.routes

    # Copy middleware and exception handlers
    app.middleware = r2r_app.app.middleware  # type: ignore
    app.exception_handlers = r2r_app.app.exception_handlers

    # Start the scheduler
    scheduler.start()

    # Start the Hatchet worker
    await r2r_app.orchestration_provider.start_worker()

    yield

    # # Shutdown
    scheduler.shutdown()


async def create_r2r_app(
    config_name: Optional[str] = "default",
    config_path: Optional[str] = None,
):
    config = R2RConfig.load(config_name=config_name, config_path=config_path)

    if (
        config.embedding.provider == "openai"
        and "OPENAI_API_KEY" not in os.environ
    ):
        raise ValueError(
            "Must set OPENAI_API_KEY in order to initialize OpenAIEmbeddingProvider."
        )

    # Build the R2RApp
    builder = R2RBuilder(config=config)
    return await builder.build()
# todo
# os.environ['R2R_POSTGRES_USER']="postgres"
# os.environ['R2R_POSTGRES_PASSWORD']="postgres"
# os.environ['R2R_POSTGRES_HOST']="postgres"
# os.environ['R2R_POSTGRES_PORT']="5432"
# os.environ['R2R_POSTGRES_DBNAME']="postgres"
os.environ['R2R_POSTGRES_USER']="langchain"
os.environ['R2R_POSTGRES_PASSWORD']="langchain"
os.environ['R2R_POSTGRES_HOST']="10.1.150.105"
os.environ['R2R_POSTGRES_PORT']="7000"
os.environ['R2R_POSTGRES_DBNAME']="postgres"
os.environ['R2R_PROJECT_NAME']="jq_new_project"
os.environ['NUMEXPR_MAX_THREAD']='20'
os.environ['HATCHET_CLIENT_TOKEN']="eyJhbGciOiJFUzI1NiIsImtpZCI6InQ3ZF81ZyJ9.eyJhdWQiOiJodHRwOi8vaG9zdC5kb2NrZXIuaW50ZXJuYWw6NzI3NCIsImV4cCI6NDg5NTgxNDE5NywiZ3JwY19icm9hZGNhc3RfYWRkcmVzcyI6ImhhdGNoZXQtZW5naW5lOjcwNzciLCJpYXQiOjE3NDIyMTQxOTcsImlzcyI6Imh0dHA6Ly9ob3N0LmRvY2tlci5pbnRlcm5hbDo3Mjc0Iiwic2VydmVyX3VybCI6Imh0dHA6Ly9ob3N0LmRvY2tlci5pbnRlcm5hbDo3Mjc0Iiwic3ViIjoiNzA3ZDA4NTUtODBhYi00ZTFmLWExNTYtZjFjNDU0NmNiZjUyIiwidG9rZW5faWQiOiI3YWNkZWM4Yy1kNDdiLTQ1ZmMtOGMwNi1kZmVmNmJlMTc5MTYifQ.9V7039q8l8URALS-8pi-hZIaIDoDAbTKao78gaNM3jAkag5F1cYMumKwU-9MK1m7PThmzR9f1L2L5TdEb1mi-w"
os.environ['CLUSTERING_SERVICE_URL']='http://10.1.150.105:7276'
os.environ['SERVER_GRPC_BROADCAST_ADDRESS']='10.1.150.105:7077'
os.environ['OPENAI_BASE_URL']='http://10.1.150.105:3000/v1'
os.environ['OPENAI_API_KEY']='sk-0S7bV3oaznhuevN899Db0cDa20Ae4c5485Ce5862A86063C8'
os.environ['SERPER_API_KEY']="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"
os.environ['server_url']= "http://10.1.150.105:7274" # hatchet orchestration
os.environ['host_port']= "localhost:7274" 

config_name = os.getenv("R2R_CONFIG_NAME", None)
config_path = os.getenv("R2R_CONFIG_PATH", None)


if not config_path and not config_name:
    config_name = "default"
host = os.getenv("R2R_HOST", os.getenv("HOST", "0.0.0.0"))
port = int(os.getenv("R2R_PORT", "7272"))

logging.info(
    f"Environment R2R_IMAGE: {os.getenv('R2R_IMAGE')}",
)
logging.info(
    f"Environment R2R_CONFIG_NAME: {'None' if config_name is None else config_name}"
)
logging.info(
    f"Environment R2R_CONFIG_PATH: {'None' if config_path is None else config_path}"
)
logging.info(f"Environment R2R_PROJECT_NAME: {os.getenv('R2R_PROJECT_NAME')}")

logging.info(
    f"Environment R2R_POSTGRES_HOST: {os.getenv('R2R_POSTGRES_HOST')}"
)
logging.info(
    f"Environment R2R_POSTGRES_DBNAME: {os.getenv('R2R_POSTGRES_DBNAME')}"
)
logging.info(
    f"Environment R2R_POSTGRES_PORT: {os.getenv('R2R_POSTGRES_PORT')}"
)
logging.info(
    f"Environment R2R_POSTGRES_PASSWORD: {os.getenv('R2R_POSTGRES_PASSWORD')}"
)

# Create the FastAPI app
app = FastAPI(
    lifespan=lifespan,
    log_config=None,
)


@app.exception_handler(R2RException)
async def r2r_exception_handler(request: Request, exc: R2RException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "message": exc.message,
            "error_type": type(exc).__name__,
        },
    )


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
