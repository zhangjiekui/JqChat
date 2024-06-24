import pathlib
VERBOSE = True
root_dir = pathlib.Path(__file__).resolve().parent.parent.parent.parent
logfile_path = root_dir/'app_code.log'

print(logfile_path)
# assert logfile_path == pathlib.Path("/home/jqsoft/AgentRagChatCI/app_code.log")


