import pathlib
VERBOSE = "True"
def if_log_verbose(VERBOSE = VERBOSE):
    if VERBOSE == "False":
        return False
    if VERBOSE == "True":
        return True
# root_dir = pathlib.Path(__file__).resolve().parent.parent.parent.parent
root_dir = pathlib.Path().resolve()
logfile_path = root_dir/'jqchat_agent.log'
llm_handler_file_path=root_dir/'jqchat_agent_llm_handler.log'

# assert logfile_path == pathlib.Path("/home/jqsoft/AgentRagChatCI/app_code.log")


