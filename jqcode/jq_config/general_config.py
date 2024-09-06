import pathlib
VERBOSE = True
# root_dir = pathlib.Path(__file__).resolve().parent.parent.parent.parent
root_dir = pathlib.Path().resolve()
logfile_path = root_dir/'jqchat_agent.log'

# assert logfile_path == pathlib.Path("/home/jqsoft/AgentRagChatCI/app_code.log")


