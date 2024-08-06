import pathlib
VERBOSE = True
# root_dir = pathlib.Path(__file__).resolve().parent.parent.parent.parent
root_dir = pathlib.Path().resolve()
logfile_path = root_dir/'JqChat.log'
print(f"####################################")
print(f"##本项目运行日志位置: {logfile_path}")
print(f"####################################")
# assert logfile_path == pathlib.Path("/home/jqsoft/AgentRagChatCI/app_code.log")


