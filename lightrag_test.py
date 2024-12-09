from jqcode.jq_agent.c0_init_env_models import env_models_instance
from lightrag import QueryParam
# get_lightrag(self,keyword_extraction=False, working_dir = "Neo4jWorkDir",log_level="DEBUG")

file = "/data/projects/JqChatV2/workspace/chunks_preview/A方案.txt"
query = "医院信息系有哪些模块或子系统，回答要尽量完整并且给出具体的功能内容或描述"


light_rag = env_models_instance.get_lightrag()

pass_file = True
if not pass_file:
    with open(file) as f:
        light_rag.insert(f.read())
# light_rag.insert(["TEXT1", "TEXT2"])
result=light_rag.query(query, param=QueryParam(mode="hybrid",only_need_context=False,top_k=5, max_token_for_text_unit=1500, max_token_for_global_context=2000))
result_only_context=light_rag.query(query, param=QueryParam(mode="hybrid",only_need_context=True,top_k=5, max_token_for_text_unit=1500, max_token_for_global_context=2000))
print(f"{result=}")
print(f"{result_only_context=}")