import asyncio
import logging
import logging.config
import multiprocessing
import multiprocessing as mp
import os
import sys
# project_root = '/data/projects/JqChat'
# sys.path.insert(0, project_root)
# # print(sys.path)

from contextlib import asynccontextmanager
from multiprocessing import Process
from jqchat.kernel_program.main import main as kernel_program_main,APP_PORT

logger = logging.getLogger()


# 设置numexpr最大线程数，默认为CPU核心数
try:
    import numexpr # type: ignore
    n_cores = numexpr.utils.detect_number_of_cores()
    os.environ["NUMEXPR_MAX_THREADS"] = str(n_cores)
except:
    pass


import argparse
from typing import Dict, List

from fastapi import FastAPI


def _set_app_event(app: FastAPI, started_event: mp.Event = None):
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if started_event is not None:
            started_event.set()
        yield

    app.router.lifespan_context = lifespan

def run_api_server(
    started_event: mp.Event = None, run_mode: str = None
):
    import uvicorn
    from jqcode.jq_knowledge_manegement.chatchat.utils import (
        get_config_dict,
        get_log_file,
        get_timestamp_ms,
    )

    from jqcode.jq_knowledge_manegement.chatchat.configs import API_SERVER, LOG_PATH, MODEL_PLATFORMS
    from jqcode.jq_knowledge_manegement.chatchat.server.api_server.server_app import create_app
    from jqcode.jq_knowledge_manegement.chatchat.server.utils import set_httpx_config

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
    uvicorn.run(app, host=host, port=port)


def run_webui(
    started_event: mp.Event = None, run_mode: str = None
):
    from jqcode.jq_knowledge_manegement.chatchat.utils import (
        get_config_dict,
        get_log_file,
        get_timestamp_ms,
    )

    from jqcode.jq_knowledge_manegement.chatchat.configs import LOG_PATH, MODEL_PLATFORMS, WEBUI_SERVER
    from jqcode.jq_knowledge_manegement.chatchat.server.utils import set_httpx_config

    logger.info(f"Webui MODEL_PLATFORMS: {MODEL_PLATFORMS}")
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
    try:
        # for streamlit >= 1.12.1
        from streamlit.web import bootstrap
    except ImportError:
        from streamlit import bootstrap

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
def run_kernel_program(started_event: mp.Event = None, run_mode: str = None):
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
    import platform

    import langchain

    from jqcode.jq_knowledge_manegement.chatchat.configs import VERSION
    from jqcode.jq_knowledge_manegement.chatchat.server.utils import api_address, webui_address

    print("=" * 30 + "Langchain-Chatchat Configuration" + "=" * 30)
    print(f"操作系统：{platform.platform()}.")
    print(f"python版本：{sys.version}")
    print(f"项目版本：{VERSION}")
    print(f"langchain版本：{langchain.__version__}")
    print("\n")

    if after_start:
        print(f"服务端运行信息：")
        if args.api:
            print(f"    Chatchat Api Server: {api_address()}")
        if args.webui:
            print(f"    Chatchat WEBUI Server: {webui_address()}")
        if args.kernel:
            print(f"    Chatchat Kernel Server: http://0.0.0.0:{APP_PORT}")
    print("=" * 30 + "Langchain-Chatchat Configuration" + "=" * 30)
    print("\n")


async def start_main_server():
    import signal
    import time

    from jqcode.jq_knowledge_manegement.chatchat.utils import (
        get_config_dict,
        get_log_file,
        get_timestamp_ms,
    )

    from jqcode.jq_knowledge_manegement.chatchat.configs import LOG_PATH

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

    # This will be inherited by the child process if it is forked (not spawned)
    signal.signal(signal.SIGINT, handler("SIGINT"))
    signal.signal(signal.SIGTERM, handler("SIGTERM"))

    mp.set_start_method("spawn")
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
        args.kernel = True
    if args.lite:
        args.api = True
        args.api_worker = False
        args.webui = True
        args.kernel = False

    if len(sys.argv) > 1:
        logger.info(f"正在启动服务：")

    processes = {}

    def process_count():
        return len(processes)
    
    kernel_started = manager.Event()
    if(args.kernel):
       process = Process(
           target=kernel_program_main,
           name=f"Kernel Server",
           kwargs=dict(
               started_event=kernel_started,
               run_mode=run_mode,
           ),
           daemon=False,)  
       processes["kernel"] = process
    # if(args.kernel):
    #     kernel_program_process = Process(target=run_kernel_program)
    #     processes["kernel"] = kernel_program_process
    
    api_started = manager.Event()
    if args.api:
        process = Process(
            target=run_api_server,
            name=f"API Server",
            kwargs=dict(
                started_event=api_started,
                run_mode=run_mode,
            ),
            daemon=False,
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
        # dump_server_info(after_start=False,args=args)
        try:
            if p := processes.get("kernel"):
                p.start()
                p.name = f"{p.name} ({p.pid})"
                kernel_started.wait()  # 等待kernel启动完成
                logger.info(f"启动KERNEL服务：{p.name}")

            if p := processes.get("api"):
                p.start()
                p.name = f"{p.name} ({p.pid})"
                api_started.wait()  # 等待api.py启动完成
                logger.info(f"启动API服务：{ p.name}")

            if p := processes.get("webui"):
                p.start()
                p.name = f"{p.name} ({p.pid})"
                # webui_started.wait()  # 等待webui.py启动完成
                logger.info(f"启动WEB服务：{p.name}")

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
    cwd = os.getcwd()
    sys.path.append(cwd)
    multiprocessing.freeze_support()
    logger.info(f"应用启动路径:{cwd}")
    # from jqcode.jq_knowledge_manegement.chatchat.server.knowledge_base.migrate import create_tables

    # create_tables()
    if sys.version_info < (3, 10):
        loop = asyncio.get_event_loop()
    else:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
    
        asyncio.set_event_loop(loop)
    loop.run_until_complete(start_main_server())
    #asyncio.run(start_main_server())
    # asyncio.wait(run_kernel_program())
    #kernel_program_process = Process(target=run_kernel_program)

if __name__ == "__main__":
    main()
