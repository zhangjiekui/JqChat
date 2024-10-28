import asyncio
import logging
import logging.config
import multiprocessing as mp
from multiprocessing import Process,Event
import os, sys

from fastapi.staticfiles import StaticFiles
from jqcode.jq_knowledge_manegement.chatchat.server.knowledge_base.migrate import create_tables
from contextlib import asynccontextmanager
import pathlib
from kernel_program.main import cleanup_kernel_program,main as kernel_program_main,APP_PORT
from jqcode.jq_knowledge_manegement.chatchat.configs import API_SERVER, LOG_PATH, MODEL_PLATFORMS
from jqcode.api_server.server_app import create_app
from jqcode.jq_knowledge_manegement.chatchat.server.utils import set_httpx_config
import uvicorn
from jqcode.jq_knowledge_manegement.chatchat.utils import (
    get_config_dict,
    get_log_file,
    get_timestamp_ms,
)
import signal
import time

import platform

import langchain
import argparse

from fastapi import FastAPI
from jqcode.jq_knowledge_manegement.chatchat.configs import VERSION
from jqcode.jq_knowledge_manegement.chatchat.server.utils import api_address, webui_address

from jqcode.jq_knowledge_manegement.chatchat.configs import LOG_PATH
from jqcode.jq_knowledge_manegement.chatchat.configs import LOG_PATH, MODEL_PLATFORMS, WEBUI_SERVER
from jqcode.jq_knowledge_manegement.chatchat.server.utils import set_httpx_config
try:
    # for streamlit >= 1.12.1
    from streamlit.web import bootstrap
except ImportError:
    from streamlit import bootstrap
from jqcode.jq_utils.logger import jqkj_logger,set_multiprocessing_context

logger = jqkj_logger(__file__).get_logger()


# 设置numexpr最大线程数，默认为CPU核心数
try:
    import numexpr # type: ignore
    n_cores = numexpr.utils.detect_number_of_cores()
    os.environ["NUMEXPR_MAX_THREADS"] = str(n_cores)
except:
    pass


def _set_app_event(app: FastAPI, started_event:Event = None): # type: ignore
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if started_event is not None:
            started_event.set()
        yield

    app.router.lifespan_context = lifespan

def run_api_server(
    started_event:Event = None, run_mode: str = None # type: ignore
):
    logger.info(f"Api MODEL_PLATFORMS: {MODEL_PLATFORMS}")
    set_httpx_config()
    app = create_app(run_mode=run_mode)
    _set_app_event(app, started_event)

    host = API_SERVER["host"]
    port = API_SERVER["port"]

    logging_conf = get_config_dict(
        "INFO",
        get_log_file(log_path=LOG_PATH, sub_dir=f"run_api_server_{get_timestamp_ms()}"),
        1024 * 1024 * 1024 * 3,
        1024 * 1024 * 1024 * 3,
    )
    logging.config.dictConfig(logging_conf)  # type: ignore
    app.mount("/workspace", StaticFiles(directory="workspace"), name="workspace")
    uvicorn.run(app, host=host, port=port)
    

def run_webui(
    started_event: Event = None, run_mode: str = None # type: ignore
):


    # logger.info(f"Webui MODEL_PLATFORMS: {MODEL_PLATFORMS}")
    set_httpx_config()

    host = WEBUI_SERVER["host"]
    port = WEBUI_SERVER["port"]

    script_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web/webui.py")

    flag_options = {
        "server_address": host,
        "server_port": port,
        "theme_base": "light",
        "theme_primaryColor": "#165dff",
        "theme_secondaryBackgroundColor": "#f5f5f5",
        "theme_textColor": "#000000",
        "global_disableWatchdogWarning": None,
        "global_disableWidgetStateDuplicationWarning": None,
        "global_showWarningOnDirectExecution": None,
        "global_developmentMode": False,
        "global_logLevel": None,
        "global_unitTest": False,
        "global_suppressDeprecationWarnings": None,
        "global_minCachedMessageSize": None,
        "global_maxCachedMessageAge": None,
        "global_storeCachedForwardMessagesInMemory": None,
        "global_dataFrameSerialization": None,
        "logger_level": None,
        "logger_messageFormat": None,
        "logger_enableRich": None,
        "client_caching": None,
        "client_displayEnabled": None,
        "client_showErrorDetails": None,
        "client_toolbarMode": None,
        "client_showSidebarNavigation": None,
        "runner_magicEnabled": None,
        "runner_installTracer": None,
        "runner_fixMatplotlib": None,
        "runner_postScriptGC": None,
        "runner_fastReruns": None,
        "runner_enforceSerializableSessionState": None,
        "runner_enumCoercion": None,
        "server_folderWatchBlacklist": None,
        "server_fileWatcherType": None,
        "server_headless": None,
        "server_runOnSave": None,
        "server_allowRunOnSave": None,
        "server_scriptHealthCheckEnabled": None,
        "server_baseUrlPath": None,
        "server_enableCORS": None,
        "server_enableXsrfProtection": None,
        "server_maxUploadSize": None,
        "server_maxMessageSize": None,
        "server_enableArrowTruncation": None,
        "server_enableWebsocketCompression": None,
        "server_enableStaticServing": None,
        "browser_serverAddress": None,
        "browser_gatherUsageStats": None,
        "browser_serverPort": None,
        "server_sslCertFile": None,
        "server_sslKeyFile": None,
        "ui_hideTopBar": None,
        "ui_hideSidebarNav": None,
        "magic_displayRootDocString": None,
        "magic_displayLastExprIfNoSemicolon": None,
        "deprecation_showfileUploaderEncoding": None,
        "deprecation_showImageFormat": None,
        "deprecation_showPyplotGlobalUse": None,
        "theme_backgroundColor": None,
        "theme_font": None,
    }

    args = []
    if run_mode == "lite":
        args += [
            "--",
            "lite",
        ]
    args+=["--gatherUsageStats","False"]


    logging_conf = get_config_dict(
        "INFO",
        get_log_file(log_path=LOG_PATH, sub_dir=f"run_webui_{get_timestamp_ms()}"),
        1024 * 1024 * 1024 * 3,
        1024 * 1024 * 1024 * 3,
    )
    logging.config.dictConfig(logging_conf)  # type: ignore
    bootstrap.load_config_options(flag_options=flag_options)
    bootstrap.run(script_dir, False, args, flag_options)
    started_event.set()
    
#run kernel for code
def run_kernel_program( started_event: Event = None, run_mode: str = None ): # type: ignore
    try:
        asyncio.run(kernel_program_main())
        started_event.set()
    except Exception as e:
        logging.exception("Error running the kernel_program:")
        sys.exit(1)
    


def parse_args() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-a",
        "--all-webui",
        action="store_true",
        help="run api.py and webui.py",
        dest="all_webui",
    )
    parser.add_argument(
        "--all-api",
        action="store_true",
        help="run api.py",
        dest="all_api",
    )

    parser.add_argument(
        "--api",
        action="store_true",
        help="run api.py server",
        dest="api",
    )

    parser.add_argument(
        "-w",
        "--webui",
        action="store_true",
        help="run webui.py server",
        dest="webui",
    )
    parser.add_argument(
        "-i",
        "--lite",
        action="store_true",
        help="以Lite模式运行：仅支持在线API的LLM对话、搜索引擎对话",
        dest="lite",
    )
    args = parser.parse_args()
    return args, parser


def dump_server_info(after_start=False, args=None):

    print("\n")
    print("=*" * 5 + "JqChat Configuration" + "=*" * 5)
    print(f"操作系统：{platform.platform()}.")
    print(f"python版本：{sys.version}")
    print(f"项目版本：{VERSION}")
    print(f"langchain版本：{langchain.__version__}")
    print("\n")

    if after_start:
        print(f"服务端运行信息：")
        if args.api:
            print(f"    JqChat Api Server: {api_address()}")
        if args.webui:
            print(f"    JqChat WEBUI Server: {webui_address()}")
        if args.kernel:
            print(f"    JqChat Kernel Server: http://0.0.0.0:{APP_PORT}")
    print("=*" * 5 + "JqChat Configuration" + "=*" * 5)
    print("\n")


async def start_main_server():


    logging_conf = get_config_dict(
        "INFO",
        get_log_file(
            log_path=LOG_PATH, sub_dir=f"start_main_server_{get_timestamp_ms()}"
        ),
        1024 * 1024 * 1024 * 3,
        1024 * 1024 * 1024 * 3,
    )
    logging.config.dictConfig(logging_conf)  # type: ignore

    def handler(signalname):
        """
        Python 3.9 has `signal.strsignal(signalnum)` so this closure would not be needed.
        Also, 3.8 includes `signal.valid_signals()` that can be used to create a mapping for the same purpose.
        """

        def f(signal_received, frame):
            raise KeyboardInterrupt(f"{signalname} received")

        return f    
    # mp.set_start_method("forkserver")
    # # mp.set_start_method("spawn")
    # # mp.set_start_method("fork")
    # # This will be inherited by the child process if it is forked (not spawned)
    signal.signal(signal.SIGINT, handler("SIGINT"))
    signal.signal(signal.SIGTERM, handler("SIGTERM"))


    manager = mp.Manager()
    run_mode = None

    args, parser = parse_args()

    # # 手动设置参数值
    args.all_webui = True  # 手动设置 -a 参数为 True


    if args.all_webui:
        args.api = True
        args.api_worker = True
        args.webui = True
        args.kernel = True
    elif args.all_api:
        args.api = True
        args.api_worker = True
        args.webui = False
        args.kernel = True
    elif args.api:
        args.api = True
        args.api_worker = False
        args.webui = False
        args.kernel = False
    if args.lite:
        args.api = True
        args.api_worker = False
        args.webui = True
        args.kernel = True

    if len(sys.argv) > 1:
        logger.info(f"正在启动服务：")

    processes = {}

    def process_count():
        return len(processes)
    
    # kernel_started = manager.Event()
    # if args.api:
    #     process = Process(
    #         target=run_kernel_program,
    #         name=f"Kernel Server",
    #         kwargs=dict(
    #             started_event=kernel_started,
    #             run_mode=run_mode,
    #         ),
    #         daemon=True,
    #     )    
    #     processes["kernel"] = process
    
    
    api_started = manager.Event()
    if args.api:
        process = Process(
            target=run_api_server,
            name=f"API Server",
            kwargs=dict(
                started_event=api_started,
                run_mode=run_mode,
            ),
            # daemon=False,
            daemon=True,
        )    
        processes["api"] = process
    

    webui_started = manager.Event()
    if args.webui:
        process = Process(
            target=run_webui,
            name=f"WEBUI Server",
            kwargs=dict(
                started_event=webui_started,
                run_mode=run_mode,
            ),
            daemon=False,
        )
        processes["webui"] = process

    
    
    if process_count() == 0:
        parser.print_help()
    else:
        dump_server_info(after_start=True,args=args)
        try:
            if p := processes.get("kernel"):
                logger.info(f"启动KERNEL服务：{p.name}")
                p.start()
                p.name = f"{p.name} ({p.pid})"
                # kernel_started.wait()  # 等待kernel启动完成

            if p := processes.get("api"):
                logger.info(f"启动API服务：{ p.name}")
                p.start()
                p.name = f"{p.name} ({p.pid})"
                api_started.wait()  # 等待api.py启动完成

            if p := processes.get("webui"):
                logger.info(f"启动WEB服务：{p.name}")
                p.start()
                p.name = f"{p.name} ({p.pid})"
                webui_started.wait()  # 等待webui.py启动完成
               

            dump_server_info(after_start=True, args=args)
            # 等待所有进程退出
            while processes:
                for p in processes.values():
                    p.join(3)
                    if not p.is_alive():
                        processes.pop(p.name)
        except Exception as e:
            logger.error(e)
            logger.warning("Caught KeyboardInterrupt! Setting stop event...")
        finally:
            for p in processes.values():
                logger.warning("Sending SIGKILL to %s", p)
                # Queues and other inter-process communication primitives can break when
                # process is killed, but we don't care here

                if isinstance(p, dict):
                    for process in p.values():
                        process.kill()
                else:
                    p.kill()

            for p in processes.values():
                logger.info("Process status: %s", p)

def main():
    # 添加这行代码
    print("=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*")    
    project_root_path = pathlib.Path().resolve()
    print(f"应用启动路径:{project_root_path}")
    print(f"本项目中添加使用的Python路径为：{set(sys.path)}")
    print(f"本项目运行日志位置: {project_root_path}/jqchat_agent.log")
    
    set_multiprocessing_context(mp,context="spawn",logger=logger)
    mp.freeze_support()
    print("=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*")      
    
    create_tables()
    asyncio.run(start_main_server())


if __name__ == "__main__":
    main()
