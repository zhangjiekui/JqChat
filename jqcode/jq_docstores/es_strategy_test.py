from jqcode.jq_agent.c0_init_env_models import env_models_instance

sparse_strategy = env_models_instance.sparse_strategy

es_vs = env_models_instance.get_es_searchstore(index_name="docstore",strategy=sparse_strategy)
r = es_vs.similarity_search(query="项目总体计划")
r = es_vs.similarity_search_with_score(query="项目总体计划")

print(r)