import os, sys
import asyncio
import pathlib
import logging
import uvicorn
import signal
import argparse
import platform
import langchain
import logging.config
from fastapi import FastAPI
import multiprocessing as mp
from multiprocessing import Process,Event
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from jqcode.jq_kb_manegement.server.utils import set_httpx_config
from jqcode.jq_utils.logger import jqkj_logger,set_multiprocessing_context
from jqcode.jq_kb_manegement.server.utils import api_address, webui_address
from jqcode.jq_kb_manegement.utils import get_config_dict, get_log_file, get_timestamp_ms
from jqcode.jq_kb_manegement.configs import API_SERVER,WEBUI_SERVER, LOG_PATH, MODEL_PLATFORMS,VERSION,CHATCHAT_ROOT
from jqcode.jq_config.general_config import llm_handler_file_path,if_log_verbose,logfile_path
from jqcode.jq_splitters.jq_docx_tree_text_splitter import load_project_env
logger = jqkj_logger(__file__).get_logger()

try:
    # for streamlit >= 1.12.1
    from streamlit.web import bootstrap
except ImportError:
    from streamlit import bootstrap
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
    started_event:Event = None, local_debug:bool=False # type: ignore
):
    logger.info(f"Api MODEL_PLATFORMS: {MODEL_PLATFORMS}")
    set_httpx_config()
    from jq_server.jq_server_app import create_app
    app = create_app()
    _set_app_event(app, started_event)

    host = API_SERVER["host"]
    port = API_SERVER["port"]
    if local_debug:
        port = port + 1
    log_file = get_log_file(log_path=LOG_PATH, sub_dir=f"run_api_server_{get_timestamp_ms()}")
    logging_conf = get_config_dict(
        "INFO",
        log_file,
        1024 * 1024 * 1024 * 3,
        1024 * 1024 * 1024 * 3,
    )
    logging.config.dictConfig(logging_conf)  # type: ignore
    logger.warning(f"API Server start at {host}:{port}")
    logger.warning(f">>>>>log>>>>> 'API Server' LogFile at {log_file}")
    app.mount("/workspace", StaticFiles(directory="workspace"), name="workspace")
    uvicorn.run(app, host=host, port=port)
def run_webui(
    started_event: Event = None, local_debug:bool=False # type: ignore
):
    # logger.info(f"Webui MODEL_PLATFORMS: {MODEL_PLATFORMS}")
    set_httpx_config()
    host = WEBUI_SERVER["host"]
    port = WEBUI_SERVER["port"]
    if local_debug:
        port = port + 1
    script_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jqweb/webui.py")
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
    args+=["--gatherUsageStats","False"]

    log_file = get_log_file(log_path=LOG_PATH, sub_dir=f"run_webui_{get_timestamp_ms()}")
    logger.warning(f"WebUI Server start at {host}:{port}")
    logger.warning(f">>>>>log>>>>> 'WebUI Server' LogFile at {log_file}")
    logging_conf = get_config_dict(
        "INFO",
        log_file,
        1024 * 1024 * 1024 * 3,
        1024 * 1024 * 1024 * 3,
    )
    logging.config.dictConfig(logging_conf)  # type: ignore
    bootstrap.load_config_options(flag_options=flag_options)
    bootstrap.run(script_dir, False, args, flag_options)
    started_event.set()
def parse_args() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--production",
        action="store_true",
        help="run api.py and webui.py in production mode",
        dest="production",
    )

    parser.add_argument(
        "-a",
        "--all-webui",
        action="store_true",
        help="run api.py and webui.py",
        dest="production",
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
def dump_server_info(after_start=False, args=None,local_debug:bool=False):
    print("=*" * 5 + "JqChat Configuration" + "=*" * 5)
    print(f"操作系统：{platform.platform()}.")
    print(f"python版本：{sys.version}")
    print(f"项目版本：{VERSION}")
    print(f"langchain版本：{langchain.__version__}")
    print(f"是否启用本地调试模式，改变端口，避免与已启动的生成服务端口冲突: {local_debug=}")
    VERBOSE = if_log_verbose()
    print(f"if_log_verbose = {VERBOSE}, 说明：在 jqcode/jq_config/general_config.py 中设置")
    print(f">>>>>log>>>>> 本项目'Agent'服务日志位置: {logfile_path},说明：如果if_log_verbose=False，则只记录Waring和Error")
    print(f">>>>>log>>>>> 本项目'LLM输入输出'日志位置: {llm_handler_file_path} ,说明：专门记录LLM的输入输出，且不受if_log_verbose影响")
    if after_start:        
        production_mode=not local_debug
        os.environ["production_mode"] = str(production_mode).lower()

        print(f"服务端运行信息({production_mode=})")
        if args.api:
            print(f"    JqChat Api Server: {api_address(production_mode)}")
        if args.webui:
            print(f"    JqChat WEBUI Server: {webui_address(production_mode)}")
    print("=*" * 5 + "JqChat Configuration" + "=*" * 5)
    print("\n")

async def start_main_server(local_debug:bool):

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
    args, parser = parse_args()

    # # 手动设置参数值
    args.all_webui = True  # 手动设置 -a 参数为 True


    if args.all_webui:
        args.api = True
        args.api_worker = True
        args.webui = True
    elif args.all_api:
        args.api = True
        args.api_worker = True
        args.webui = False
    elif args.api:
        args.api = True
        args.api_worker = False
        args.webui = False
    if args.lite:
        args.api = True
        args.api_worker = False
        args.webui = True
    if len(sys.argv) > 1:
        logger.info(f"正在启动服务：")

    processes = {}

    def process_count():
        return len(processes)
    api_started = manager.Event()
    if args.api:
        process = Process(
            target=run_api_server,
            name=f"API Server",
            kwargs=dict(
                started_event=api_started,
                local_debug = local_debug
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
                local_debug = local_debug
            ),
            daemon=True,
        )
        processes["webui"] = process

    dump_server_info(after_start=True,args=args,local_debug=local_debug)
    
    if process_count() == 0:
        parser.print_help()
    else:
        
        try:
            if p := processes.get("api"):
                logger.info(f"启动API服务：{p.name}")
                p.start()
                p.name = f"{p.name} ({p.pid})"
                api_started.wait()  # 等待api.py启动完成

            if p := processes.get("webui"):
                logger.info(f"启动WEB服务：{p.name}")
                p.start()
                p.name = f"{p.name} ({p.pid})"
                webui_started.wait()  # 等待webui.py启动完成               
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
def main(local_debug: bool = False):
    env_loaded = load_project_env()
    assert env_loaded, "环境变量没有正确载入！"
    print("=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*")
    print("=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*")        
    project_root_path = pathlib.Path().resolve()
    print(f"  当前应用启动路径:{project_root_path}")
    need_add_path = str(project_root_path)
    if "JqR2R" not in project_root_path.parts:
        need_add_path = project_root_path/'JqR2R/py'
        if need_add_path not in set(sys.path):
            sys.path.append(str(need_add_path))
            print(f"  已将{need_add_path} 加入系统路径！")
       
    os.environ["r2r_project_root_path"] = str(need_add_path)
    set_multiprocessing_context(mp,context="spawn",logger=logger)
    mp.freeze_support()    
    try:
        args,_ = parse_args()
        print(f"  服务端运行模式({args.production=})")
        local_debug = not args.production
    except Exception as e:
        logger.error(f"  获取服务端运行模式args.production 失败：{e})")
    print("\n>>>*=*=*=*=*=*=*=*=*开始启动服务=*=*=*=*=*=*=*=*=*=*=*")
    os.environ["blocking_logging"] = "false"
    asyncio.run(start_main_server(local_debug=local_debug))
    # 下面实际上执行不到（见start_main_server方法中：print("=============!!!这行代码实际已经执行不到了!!!=============")）
    os.environ["blocking_logging"] = "false"
    print(">>>*=*=*=*=*=*=*=*=*服务启动完成=*=*=*=*=*=*=*=*=*=*=*")


if __name__ == "__main__":
    main(local_debug=True)
    # 端口配置文件/root/.chatchat/workspace/workspace_config.json
