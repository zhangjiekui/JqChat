import re
import asyncio
from r2r import R2RClient, R2RAsyncClient # type: ignore
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
    
def r2r_format_search_results_for_llm(
    results,
) -> str:
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
        lines.append("Vector Search Results:")
        for c in results.chunk_search_results[0:2]:
            lines.append(f"Source ID [{str(c.id)}]:")
            lines.append(c.text or "")  # or c.text[:200] to truncate

    # 2) Graph search
    if results.graph_search_results:
        lines.append("Graph Search Results:")
        for g in results.graph_search_results[0:2]:
            lines.append(f"Source ID [{id_to_shorthand(g.id)}]:")
            if hasattr(g.content, "summary"):
                lines.append(f"Community Name: {g.content.name}")
                lines.append(f"ID: {g.content.id}")
                lines.append(f"Summary: {g.content.summary}")
                # etc. ...
            elif hasattr(g.content, "name") and hasattr(
                g.content, "description"
            ):
                lines.append(f"Entity Name: {g.content.name}")
                lines.append(f"Description: {g.content.description}")
            elif (
                hasattr(g.content, "subject")
                and hasattr(g.content, "predicate")
                and hasattr(g.content, "object")
            ):
                lines.append(
                    f"Relationship: {g.content.subject}-{g.content.predicate}-{g.content.object}"
                )
            # Add metadata if needed

    # 3) Web search
    if results.web_search_results:
        lines.append("Web Search Results:")
        for w in results.web_search_results[0:2]:
            lines.append(f"Source ID [{id_to_shorthand(w.id)}]:")
            lines.append(f"Title: {w.title}")
            lines.append(f"Link: {w.link}")
            lines.append(f"Snippet: {w.snippet}")

    # 4) Local context docs
    if results.document_search_results:
        lines.append("Local Context Documents:")
        for doc_result in results.document_search_results[0:2]:
            doc_title = doc_result.title or "Untitled Document"
            doc_id = doc_result.id
            summary = doc_result.summary

            lines.append(f"Full Document ID: {doc_id}")
            lines.append(f"Shortened Document ID: {id_to_shorthand(doc_id)}")
            lines.append(f"Document Title: {doc_title}")
            if summary:
                lines.append(f"Summary: {summary}")

            if doc_result.chunks:
                # Then each chunk inside:
                for chunk in doc_result.chunks:
                    lines.append(
                        f"\nChunk ID {id_to_shorthand(chunk['id'])}:\n{chunk['text']}"
                    )
    # raise Exception("要去重，现在有大量的重复！")
    result = "\n".join(lines)
    return result

def r2r_search(client,query:str,chat_on_docs_list:list=None):
# https://r2r-docs.sciphi.ai/api-and-sdks/retrieval/search-app
    query = "全民健康信息平台"
    from r2r import R2RClient # type: ignore
    client = R2RClient(base_url='http://10.1.150.105:7272') # can set remote w/ R2RClient(base_url=...)
    client.users.login("admin@example.com", "change_me_immediately")
    # search_settings: https://github.com/SciPhi-AI/R2R/blob/main/py/shared/abstractions/search.py#L406
    search_func = client.retrieval.search(query=query,search_mode="advanced",
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
    # search_response = asyncio.run(search_func)
    search_response = search_func
    search_results = r2r_format_search_results_for_llm(search_response.results)
    print(search_results)
    return search_results
# r=r2r_search("client","query",["chat_on_docs_list"])
# print(r)

def r2r_authed_client(user_id,user_email='',password="change_me_immediately",server_url='http://10.1.150.105:7272'):
    r2r_client = R2RClient(base_url=server_url)
    if not is_valid_email(user_email):
        if not is_valid_email(user_id):
            user_email = f"{user_id}@example.com"

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
    result= r2r_search(r2r_client,query="质量保证过程的含义")
    print(result)


