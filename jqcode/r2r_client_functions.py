import os,re
import asyncio
import uuid
from uuid import UUID
from r2r import R2RClient,R2RConfig,LiteLLMEmbeddingProvider,ChunkSearchResult # type: ignore
from jqcode.jq_utils.logger import jqkj_logger
logger = jqkj_logger(__file__).get_logger()

# 暂时不使用
def id_to_shorthand(id: str) -> str:
    return str(id)[:7]

def is_valid_email(id_or_email_str):
    # 定义电子邮件地址的正则表达式
    email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    # 使用re.match方法进行匹配
    if re.match(email_regex, id_or_email_str):
        return True
    else:
        return False
    
def r2r_format_search_results_for_llm(query, results,limit: int = 10, min_score_threshold = 0.6) -> str:
    """
    Instead of resetting 'source_counter' to 1, we:
     - For each chunk / graph / web / doc in `results`,
     - Find the aggregator index from the collector,
     - Print 'Source [X]:' with that aggregator index.
    """
    lines = []

    # We'll build a quick helper to locate aggregator indices for each object:
    # Or you can rely on the fact that we've added them to the collector
    # in the same order. But let's do a "lookup aggregator index" approach:

    # 1) Chunk search
    if results.chunk_search_results:
        no_repeated_results = []
        for r in results.chunk_search_results:
            id_text_score_tuple = (str(r.id),r.text,r.score)
            if id_text_score_tuple not in no_repeated_results:
                no_repeated_results.append(id_text_score_tuple)
        for r in no_repeated_results:
            line_content = {"Source ID": r[0], "Score": r[-1], "Text": f"ChunkText:{r[1]}"}
            lines.append({"Vector_Search_Results":line_content})


    # 2) Graph search
    if results.graph_search_results:
        unique_result_ids = []
        unique_content_result_ids = []
        no_repeated_results = []
        for r in results.graph_search_results:
            id = str(r.id)
            if id not in unique_result_ids:
                unique_result_ids.append(id)
                content_id = str(r.content.id)
                if content_id not in unique_content_result_ids:
                    unique_content_result_ids.append(content_id)
                    id_text_score_tuple = (str(r.id),r.content,r.score)
                    if id_text_score_tuple not in no_repeated_results:
                        no_repeated_results.append(id_text_score_tuple) 
        for r in no_repeated_results:
            g = r[1]
            content_id = str(g.id)
            text = ""
            if hasattr(g, "summary"):
                text+=f"Community Name: {g.name}\n"
                text+=f"Summary: {g.summary}\n"
                # etc. ...
            elif hasattr(g, "name") and hasattr(g, "description"):
                text+=f"Entity Name: {g.name}\n"
                text+=f"Description: {g.description}\n"
            elif (hasattr(g, "subject") and hasattr(g, "predicate") and hasattr(g, "object")):
                text+=f"Relationship: {g.subject}-{g.predicate}-{g.object}\n"
            line_content = {"Source ID": r[0],"Content ID":content_id, "Score": r[-1], "Text": text}
            lines.append({"Graph_Search_Results":line_content})
            # Add metadata if needed

    # 3) Web search:暂时不处理
    if results.web_search_results:
        logger.warning("存在results.web_search_results，但暂时未作处理！")
        # lines.append("Web Search Results:")
        # for w in results.web_search_results[0:2]:
        #     lines.append(f"Source ID [{str(w.id)}]:")
        #     lines.append(f"Title: {w.title}")
        #     lines.append(f"Link: {w.link}")
        #     lines.append(f"Snippet: {w.snippet}")

    # 4) Local context docs:暂时不处理
    if results.document_search_results:
        logger.warning("存在results.document_search_results，但暂时未作处理！")
        # lines.append("Local Context Documents:")
        # for doc_result in results.document_search_results[0:2]:
        #     doc_title = doc_result.title or "Untitled Document"
        #     doc_id = doc_result.id
        #     summary = doc_result.summary

        #     lines.append(f"Full Document ID: {doc_id}")
        #     lines.append(f"Shortened Document ID: {str(doc_id)}")
        #     lines.append(f"Document Title: {doc_title}")
        #     if summary:
        #         lines.append(f"Summary: {summary}")

        #     if doc_result.chunks:
        #         # Then each chunk inside:
        #         for chunk in doc_result.chunks:
        #             lines.append(
        #                 f"\nChunk ID {id_to_shorthand(chunk['id'])}:\n{chunk['text']}"
        #             )

    # Rerank...... 
    if lines:
        config_file = os.environ.get("R2R_CONFIG_PATH", None)
        config = R2RConfig.from_toml(config_file)
        config = R2RConfig({"config_file":config_file})
        embedding_provider = LiteLLMEmbeddingProvider(config.embedding)
        makeup_chunks_result_list = []
        for dict in lines:
            for k,inner_dict in dict.items():
                id = inner_dict.get("Source ID",uuid.uuid1())
                id = UUID(id)
                id = uuid.uuid1()
                score = inner_dict.get("Score",0.0)
                text = inner_dict.get("Text","")
                makeup_chunk_result = ChunkSearchResult(id=id,score=score,text=text,document_id=id,owner_id=id,collection_ids=[id],metadata={})
                makeup_chunks_result_list.append(makeup_chunk_result)


        rerank_results=embedding_provider.rerank(query,makeup_chunks_result_list,limit = limit, min_score_threshold = min_score_threshold)
        logger.warning(f"=====共返回{len(rerank_results)}条Rerank Results({limit=},{min_score_threshold=})=====")
        texts = [f"[{i+1}] RerankScore:{r.score}\n{r.text}" for i,r in enumerate(rerank_results)]
        result = "\n".join(texts)
    else:
        logger.warning(f"     R2R未获取到任何检索结果！")
        result = ''
    return result

def r2r_search(client,query:str,chat_on_docs_list:list=None, limit: int = 20, min_score_threshold = 0.6,user_id:str=''):
    if client is None:    
        from r2r import R2RClient # type: ignore
        client = r2r_authed_client(user_id=user_id)
    # https://r2r-docs.sciphi.ai/api-and-sdks/retrieval/search-app
    # search_settings: https://github.com/SciPhi-AI/R2R/blob/main/py/shared/abstractions/search.py#L406
    search_response = client.retrieval.search(query=query,search_mode="advanced",
                                                            search_settings={
                                                                "limit": 20,
                                                                "use_semantic_search":True,
                                                                "use_hybrid_search": True,
                                                                "use_fulltext_search": True,                                                               
                                                                "hybrid_settings": {
                                                                            "full_text_weight": 1.0,
                                                                            "semantic_weight": 5.0,
                                                                            "full_text_limit": 200,
                                                                            "rrf_k": 50
                                                                        },
                                                                # "filters": {"title": {"$in": [chat_on_docs_list]}},
                                                                "graph_search_settings":{
                                                                                "limits":{
                                                                                            "entity": 20,
                                                                                            "relationship": 20,
                                                                                            "community": 20,
                                                                                          },
                                                                                "use_graph_search": True,
                                                                                # "kg_search_type": "local"
                                                                                "max_llm_queries_for_global_search": 50,
                                                                                "max_community_description_length": 5000,
                                                                            }   
                                                                },                                                                 
                                                    )
    search_results = r2r_format_search_results_for_llm(query,search_response.results,limit=limit,min_score_threshold=min_score_threshold)
    return search_results

def r2r_authed_client(user_id,user_email='',password="change_me_immediately",server_url='http://10.1.150.105:7272'):
    r2r_client = R2RClient(base_url=server_url)
    if not is_valid_email(user_email):
        if not is_valid_email(user_id):
            user_email = f"{user_id}@example.com"
            user_email = f"admin@example.com"
            

    users_response = r2r_client.users.list()
    users = users_response.results
    users_emails = [user.email for user in users] 
    if user_email not in users_emails:
        try:
            create_user_response = r2r_client.users.create(email=user_email, password=password)
            logger.warning(f"Success to create user {user_email}")
        except Exception as e:
            logger.error(f"Failed to create user {user_email}:{e}")
    try:
        
        user_login_response = r2r_client.users.login(user_email, password)
        logger.warning(f"User {user_email} success to login in r2r server")
    except Exception as e:
        logger.error(f"Failed to login user {user_email}:{e}")
    return r2r_client

def r2r_create_documents(r2r_client,lm_documents:list):
    try:
        response = r2r_client.documents.list()
        documents = response.results
    except:
        documents = []
    document_ids = [doc.id for doc in documents] 
    document_titles = [doc.title for doc in documents]
    for doc in lm_documents:
        id = doc.id_
        if id not in document_ids:
            doc_title = doc.metadata.get("file_name",doc.metadata.get("file_name_jq",""))
            if doc_title in document_titles:
                logger.warning(f"文档{doc_title}已经存在，忽略此文件的处理，请注意检查!")
            else:
                file_path = doc.metadata.get("file_path",doc.metadata.get("original_source_converted_jq",""))
                metadata=doc.metadata
                if not metadata.get('language',None):
                    metadata.update({"language": "Chinese"})
                try:
                    metadata.pop('file_doc_tree_jq')                    
                except:
                    pass
                try:
                    create_response = r2r_client.documents.create(file_path=file_path,metadata=doc.metadata,id=id)
                    logger.warning(create_response) 
                except Exception as e:
                    logger.warning(f"r2r_client.documents.create({file_path})过程中出现错误{e}")   

if __name__ == "__main__":
    r2r_client = r2r_authed_client("admin")
    query_list = ["全民健康信息平台包含的建设内容、系统或功能","质量保证过程的含义","柯林斯与班纳特关系"]
    for query in query_list:
        result= r2r_search(r2r_client,query=query)
        print(result)
        # from jqcode.jq_agent.c0_init_env_models import env_models_instance
        # llm_model = env_models_instance.chat_model

        from jqcode.langgraph_in_class import llm_chain        
        answer = llm_chain.invoke({"question": query,"context":result})
        print(answer)
        pass


