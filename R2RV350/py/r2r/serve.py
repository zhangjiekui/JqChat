import argparse
import asyncio
import logging
import os
import sys
from typing import Optional

logger = logging.getLogger(__name__)
os.environ['R2R_POSTGRES_USER']="langchain"
os.environ['R2R_POSTGRES_PASSWORD']="langchain"
os.environ['R2R_POSTGRES_HOST']="10.1.150.105"
os.environ['R2R_POSTGRES_PORT']="6000"
os.environ['R2R_POSTGRES_DBNAME']="postgres"
os.environ['R2R_PROJECT_NAME']="r2r_jq_project"
os.environ['HATCHET_CLIENT_TOKEN']="eyJhbGciOiJFUzI1NiIsImtpZCI6InQ3ZF81ZyJ9.eyJhdWQiOiJodHRwOi8vaG9zdC5kb2NrZXIuaW50ZXJuYWw6NzI3NCIsImV4cCI6NDg5NTgxNDE5NywiZ3JwY19icm9hZGNhc3RfYWRkcmVzcyI6ImhhdGNoZXQtZW5naW5lOjcwNzciLCJpYXQiOjE3NDIyMTQxOTcsImlzcyI6Imh0dHA6Ly9ob3N0LmRvY2tlci5pbnRlcm5hbDo3Mjc0Iiwic2VydmVyX3VybCI6Imh0dHA6Ly9ob3N0LmRvY2tlci5pbnRlcm5hbDo3Mjc0Iiwic3ViIjoiNzA3ZDA4NTUtODBhYi00ZTFmLWExNTYtZjFjNDU0NmNiZjUyIiwidG9rZW5faWQiOiI3YWNkZWM4Yy1kNDdiLTQ1ZmMtOGMwNi1kZmVmNmJlMTc5MTYifQ.9V7039q8l8URALS-8pi-hZIaIDoDAbTKao78gaNM3jAkag5F1cYMumKwU-9MK1m7PThmzR9f1L2L5TdEb1mi-w"
os.environ['CLUSTERING_SERVICE_URL']='http://10.1.150.105:7276'

try:
    from R2RV350.py.core import R2RApp, R2RBuilder, R2RConfig
    from R2RV350.py.core.utils.logging_config import configure_logging
except ImportError as e:
    logger.error(
        f"Failed to start server: core dependencies not installed: {e}"
    )
    logger.error("To run the server, install the required dependencies:")
    logger.error("pip install 'r2r[core]'")
    sys.exit(1)


async def create_app(
    config_name: Optional[str] = "jqkj",
    config_path: Optional[str] = "/data/projects/JqChatV2/JqChat/R2RV350/py/core/configs/full_jq.toml",
    full: bool = True,
) -> "R2RApp":
    """
    Creates and returns an R2R application instance based on the provided
    or environment-sourced configuration.
    """
    # If arguments not passed, fall back to environment variables
    config_name = config_name or os.getenv("R2R_CONFIG_NAME")
    config_path = config_path or os.getenv("R2R_CONFIG_PATH")

    if config_path and config_name:
        raise ValueError("Cannot specify both config_path and config_name")

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
        # default="/data/projects/JqChatV2/JqChat/R2RV350/py/core/configs/full_jq.toml",
        default="/data/projects/JqChatV2/JqChat/R2RV350/py/r2r/r2r.toml",
        
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
    # 检查服务运行状态：http://10.1.150.105:7272/v3/health {"results":{"message":"ok"}}
    # 运行界面：http://10.1.150.105:7273/   
    # 填入服务地址：http://10.1.150.105:7272
    # 登录信息
    # Email: admin@example.com
    # Password: Admin123!!

