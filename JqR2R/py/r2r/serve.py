import os, sys,pathlib    
import argparse
import asyncio
import logging
from typing import Optional
logger = logging.getLogger(__name__)
LLM_MODEL_CARD = os.environ['LLM_MODEL_CARD']
print(f"优先载入了顶层的.env,此次已能获取到LLM_MODEL_CARD: {LLM_MODEL_CARD}")

# 放到/data/projects/JqChatV2/JqChat/JqR2R/py/core/main/app_entry.py
# os.environ['R2R_POSTGRES_USER']="postgres"
# os.environ['R2R_POSTGRES_PASSWORD']="postgres"
# os.environ['R2R_POSTGRES_HOST']="postgres"
# os.environ['R2R_POSTGRES_PORT']="5432"
# os.environ['R2R_POSTGRES_DBNAME']="postgres"

os.environ['R2R_POSTGRES_USER']="langchain"
os.environ['R2R_POSTGRES_PASSWORD']="langchain"
os.environ['R2R_POSTGRES_HOST']="10.1.150.105"
os.environ['R2R_POSTGRES_PORT']="6022"
os.environ['R2R_POSTGRES_DBNAME']="postgres"
os.environ['R2R_PROJECT_NAME']="jq_new_project"
os.environ['NUMEXPR_MAX_THREAD']='20'
os.environ['HATCHET_CLIENT_TOKEN']="eyJhbGciOiJFUzI1NiIsImtpZCI6InQ3ZF81ZyJ9.eyJhdWQiOiJodHRwOi8vaG9zdC5kb2NrZXIuaW50ZXJuYWw6NzI3NCIsImV4cCI6NDg5NTgxNDE5NywiZ3JwY19icm9hZGNhc3RfYWRkcmVzcyI6ImhhdGNoZXQtZW5naW5lOjcwNzciLCJpYXQiOjE3NDIyMTQxOTcsImlzcyI6Imh0dHA6Ly9ob3N0LmRvY2tlci5pbnRlcm5hbDo3Mjc0Iiwic2VydmVyX3VybCI6Imh0dHA6Ly9ob3N0LmRvY2tlci5pbnRlcm5hbDo3Mjc0Iiwic3ViIjoiNzA3ZDA4NTUtODBhYi00ZTFmLWExNTYtZjFjNDU0NmNiZjUyIiwidG9rZW5faWQiOiI3YWNkZWM4Yy1kNDdiLTQ1ZmMtOGMwNi1kZmVmNmJlMTc5MTYifQ.9V7039q8l8URALS-8pi-hZIaIDoDAbTKao78gaNM3jAkag5F1cYMumKwU-9MK1m7PThmzR9f1L2L5TdEb1mi-w"
os.environ['CLUSTERING_SERVICE_URL']='http://10.1.150.105:7276'
os.environ['SERVER_GRPC_BROADCAST_ADDRESS']='10.1.150.105:7077'
os.environ['OPENAI_BASE_URL']='http://10.1.150.105:3000/v1'
os.environ['OPENAI_API_KEY']='sk-0S7bV3oaznhuevN899Db0cDa20Ae4c5485Ce5862A86063C8'
os.environ['SERPER_API_KEY']="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"

try:
    # import r2r
    # print(dir(r2r))
    # from r2r import *
    from r2r import R2RConfig,R2RBuilder

except ImportError as e:
    logger.error(
        f"Failed to start server: core dependencies not installed: {e}"
    )
    logger.error("To run the server, install the required dependencies:")
    logger.error("pip install 'r2r[core]'")
    sys.exit(1)

async def create_app(
    config_name: Optional[str] = None,
    config_path: Optional[str] = None,
    full: bool = False,
) -> "R2RApp": # type: ignore
    """
    Creates and returns an R2R application instance based on the provided
    or environment-sourced configuration.
    """
    # If arguments not passed, fall back to environment variables
    config_name = config_name or os.getenv("R2R_CONFIG_NAME")
    config_path = config_path or os.getenv("R2R_CONFIG_PATH")

    if config_path and config_name:
        raise ValueError(
            f"Cannot specify both config_path and config_name, got {config_path} and {config_name}"
        )

    if not config_path and not config_name:
        # If neither is specified nor set in environment,
        # default to 'full' if --full is True, else 'default'
        config_name = "full" if full else "default"

    try:
        r2r_instance = await R2RBuilder(
            config=R2RConfig.load(config_name, config_path)
        ).build()

        # Start orchestration worker
        await r2r_instance.orchestration_provider.start_worker()
        return r2r_instance
    except ImportError as e:
        logger.error(f"Failed to initialize R2R: {e}")
        logger.error(
            "Please check your configuration and installed dependencies"
        )
        sys.exit(1)


def run_server(
    host: Optional[str] = None,
    port: Optional[int] = None,
    config_name: Optional[str] = None,
    config_path: Optional[str] = None,
    full: bool = False,
):
    """
    Runs the R2R server with the provided or environment-based settings.
    """
    # Overwrite environment variables if arguments are explicitly passed
    if host is not None:
        os.environ["R2R_HOST"] = host
    if port is not None:
        os.environ["R2R_PORT"] = str(port)
    if config_path is not None:
        os.environ["R2R_CONFIG_PATH"] = config_path
    if config_name is not None:
        os.environ["R2R_CONFIG_NAME"] = config_name

    # Fallback to environment or defaults if necessary
    final_host = os.getenv("R2R_HOST", "0.0.0.0")
    final_port = int(os.getenv("R2R_PORT", "7272"))

    try:
        from r2r import configure_logging
        configure_logging()
    except Exception as e:
        logger.error(f"Failed to configure logging: {e}")

    try:

        async def start():
            app = await create_app(config_name, config_path, full)
            await app.serve(final_host, final_port)

        asyncio.run(start())
    except Exception as e:
        logger.error(f"Failed to start R2R server: {e}")
        sys.exit(1)


def main():
    """
    Parse command-line arguments and then run the server.
    """
    parser = argparse.ArgumentParser(description="Run the R2R server.")
    parser.add_argument(
        "--host",
        default=None,
        help="Host to bind to. Overrides R2R_HOST env if provided.",
    )
    parser.add_argument(
        "--port",
        default=None,
        type=int,
        help="Port to bind to. Overrides R2R_PORT env if provided.",
    )
    parser.add_argument(
        "--config-path",
        default="./r2r/jq.toml",
        # default="/data/projects/JqChatV2/JqChat/R2RV350/py/core/configs/full_jq.toml",
        help="Path to the configuration file. Overrides R2R_CONFIG_PATH env if provided.",
    )
    parser.add_argument(
        "--config-name",
        default=None,
        help="Name of the configuration. Overrides R2R_CONFIG_NAME env if provided.",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Use the 'full' config if neither config-path nor config-name is specified.",
    )

    args = parser.parse_args()

    run_server(
        host=args.host,
        port=args.port,
        config_name=args.config_name,
        config_path=args.config_path,
        full=args.full,
    )


if __name__ == "__main__":
    main()
