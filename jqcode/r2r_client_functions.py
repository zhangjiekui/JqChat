import os,re
import uuid
from uuid import UUID
from pathlib import Path
from func_timeout import func_set_timeout, FunctionTimedOut
from r2r import R2RClient,R2RConfig,LiteLLMEmbeddingProvider,ChunkSearchResult,SearchSettings # type: ignore
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
    
def r2r_format_search_results_for_llm(query, results,limit: int = 10, min_score_threshold = 0.2) -> str:
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
                    id_text_score_tuple = (str(r.id),r.content,r.score,r.result_type.value)
                    if id_text_score_tuple not in no_repeated_results:
                        no_repeated_results.append(id_text_score_tuple) 
        for r in no_repeated_results:
            g = r[1]
            content_id = str(g.id)
            text = f"Graph ResultType: {r[3]}\n"
            if hasattr(g, "summary"):
                text+=f"Community Name: {g.name}\n"
                text+=f"Summary: {g.summary}\n"
                # etc. ...
            elif hasattr(g, "name") and hasattr(g, "description"):
                text+=f"Entity Name: {g.name}\n"
                text+=f"Description: {g.description}\n"

            elif (hasattr(g, "subject") and hasattr(g, "predicate") and hasattr(g, "object")):
                text+=f"Relationship: {g.subject}-{g.predicate}-{g.object}\n"
            line_content = {"Source ID": r[0],"Content ID":content_id, "Score": r[2], "Text": text}
            lines.append({"Graph_Search_Results":line_content})
            # Add metadata if needed
# region 【Search方法返回结果实际不会包括下面的两项，所以暂时不处理】  
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
# endregion
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

def r2r_search(r2r_client,query:str,chat_on_docs_list:list=None, limit: int = 10, min_score_threshold = 0.2,user_id:str=''):
    # todo: https://github.com/SciPhi-AI/R2R/blob/bdc76755880c9c6422bd5ee0d433762841185805/py/core/main/services/retrieval_service.py#L1449C13-L1449C50
    # 可以控制过滤：filter_user_id, filter_collection_ids 
    if r2r_client is None:    
        from r2r import R2RClient # type: ignore
        r2r_client = r2r_authed_client(user_id=user_id)
    # https://r2r-docs.sciphi.ai/api-and-sdks/retrieval/search-app
    # search_settings: https://github.com/SciPhi-AI/R2R/blob/main/py/shared/abstractions/search.py#L406
    # https://github.com/SciPhi-AI/R2R/blob/bdc76755880c9c6422bd5ee0d433762841185805/py/core/main/services/retrieval_service.py
    search_settings = SearchSettings(use_semantic_search=True,use_fulltext_search=True,use_hybrid_search=True,search_strategy="rag_fusion",limit=limit)
    search_response = r2r_client.retrieval.search(query=query, search_settings=search_settings)
# region 【详细定义search_settings字典参数】   
    # search_response = client.retrieval.search(query=query,search_mode="advanced",
    #                                                         search_settings={
    #                                                             "limit": 20,
    #                                                             "use_semantic_search":True,
    #                                                             "use_hybrid_search": True,
    #                                                             "use_fulltext_search": True,                                                               
    #                                                             "hybrid_settings": {
    #                                                                         "full_text_weight": 1.0,
    #                                                                         "semantic_weight": 5.0,
    #                                                                         "full_text_limit": 200,
    #                                                                         "rrf_k": 50
    #                                                                     },
    #                                                             # "filters": {"title": {"$in": [chat_on_docs_list]}},
    #                                                             "chunk_settings": {
    #                                                                             "enabled": True,
    #                                                                             "index_measure": "cosine_distance",
    #                                                                             "include_metadata": True,
    #                                                                             "probes": 10,
    #                                                                             "ef_search": 40,
    #                                                                         },
    #                                                             "graph_search_settings":{
    #                                                                             "limits":{
    #                                                                                         "entity": 20,
    #                                                                                         "relationship": 20,
    #                                                                                         "community": 20,
    #                                                                                       },
    #                                                                             "use_graph_search": True,
    #                                                                             # "kg_search_type": "local"
    #                                                                             "max_llm_queries_for_global_search": 100,
    #                                                                             "max_community_description_length": 10000,
    #                                                                         }   
    #                                                             },                                                                 
                                                    # )
# endregion
    search_results = r2r_format_search_results_for_llm(query,search_response.results,limit=limit,min_score_threshold=min_score_threshold)
    return search_results
@func_set_timeout(50)
def r2r_authed_client(user_id,user_email='',password="admin@123456",server_url='http://10.1.150.105:7272'):
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

def r2r_create_documents(r2r_client,file_paths_or_lm_documents:list):
    logger.warning(f"\n========== 进入: r2r_create_documents ==========")
    if not isinstance(file_paths_or_lm_documents,list):
       file_paths_or_lm_documents = [file_paths_or_lm_documents]
    try:
        response = r2r_client.documents.list()
        documents = response.results
    except:
        documents = []
    document_ids = [doc.id for doc in documents] 
    document_titles = [doc.title for doc in documents]
    document_paths = [doc.metadata.get("source",None) for doc in documents]

    skiped_file_names = []
    for filepath_or_doc in file_paths_or_lm_documents:
        doc_title = ''
        file_path = ''
        if isinstance(filepath_or_doc,str):
            file_path = filepath_or_doc
            doc_title = Path(file_path).name
            metadata = {"language": "Chinese","source":file_path}
            id = uuid.uuid1()
        else:
            try:
                id = filepath_or_doc.id_
                doc_title = filepath_or_doc.metadata.get("file_name",filepath_or_doc.metadata.get("file_name_jq",""))
                    
                if id not in document_ids:
                    file_path = filepath_or_doc.metadata.get("file_path",filepath_or_doc.metadata.get("original_source_converted_jq",""))
                    metadata=filepath_or_doc.metadata
                    if not metadata.get('language',None):
                        metadata.update({"language": "Chinese"})
                    if not metadata.get('source',None):
                        metadata.update({"source": file_path})
                    for _key in ['file_doc_tree_jq','df_table_list_jq']:
                        try:
                            metadata.pop(_key)                    
                        except:
                            pass
                else:
                    logger.warning(f"   Document with ID [{id}] already exists. Skipping [{doc_title}] creation.")
                    skiped_file_names.append(doc_title)
                    continue
            except Exception as e:
                logger.error(f"   处理文档[{filepath_or_doc}]时发生错误: {e}")
                continue
                        

        if file_path in document_paths:
            doc_title = Path(file_path).name
            logger.warning(f"   Document Path [{doc_title}] already exists.Passing...")
            skiped_file_names.append(file_path)
            continue
        if doc_title in document_titles:
            logger.warning(f"   Document Title [{doc_title}] already exists.Passing...")
            skiped_file_names.append(file_path)
            continue

        if not Path(file_path).exists():
            logger.warning(f"   File Path [{file_path}] does not exist.Passing...")
        else:
            try: 
                create_response = r2r_client.documents.create(file_path=file_path,metadata=metadata,id=id)
                logger.warning(f"   {create_response=}") 
            except Exception as e:
                logger.warning(f"   r2r_client.documents.create({file_path})过程中出现错误{e}")
                continue   
    logger.warning(f"   R2R输入文件数为：{len(file_paths_or_lm_documents)=},因已R2R中已存在而跳过的文件数为：{len(skiped_file_names)=}") 
    logger.warning(f"\n========== 离开: r2r_create_documents ==========")              
       


if __name__ == "__main__":
    r2r_client = r2r_authed_client("admin")

    # result_collections = r2r_client.collections.list(
    #                                                 offset=0,
    #                                                 limit=10,
    #                                             )
    # print(f"{result_collections=}")
    search_settings = SearchSettings(use_semantic_search=True,use_fulltext_search=True,use_hybrid_search=True,search_strategy="rag_fusion",limit=20)
    
    # https://github.com/SciPhi-AI/R2R/blob/bdc76755880c9c6422bd5ee0d433762841185805/py/core/main/services/retrieval_service.py
    query_list = ["全民健康信息平台包含的建设内容、系统或功能","质量保证过程的含义","柯林斯与班纳特关系"]



    # for query in query_list:
    #     search_result= r2r_search(r2r_client,query=query)
    #     print(f"{search_result=}")

    #     from jqcode.langgraph_in_class import llm_chain        
    #     answer = llm_chain.invoke({"question":query,"context":search_result})
    #     print(f"{answer=}")
    #     pass


    # r2r_create_documents(r2r_client,file_paths_or_lm_documents=
    #                      ["/data/projects/JqChatV2/JqChat/JqR2R/py/core/examples/data/DeepSeek_R1.pdf",
    #                       "/data/projects/JqChatV2/JqChat/JqR2R/py/core/examples/supported_file_types/pdf.pdf",
    #                       "/data/projects/JqChatV2/JqChat/2025年第五期总经理办公会纪要.docx",
                          
    #                       ])

    # response = r2r_client.documents.list()
    # documents = response.results

    # for doc in documents:
    #     doc_id = doc.id 
    #     try:                           
    #         chunks_response = r2r_client.documents.list_chunks(doc_id)
    #         chunks = chunks_response.results
    #         entities_response = r2r_client.documents.list_entities(doc_id)
    #     except Exception as e:
    #         logger.error(f"获取文档{doc.id}:{doc.title}的chunks时发生错误: {e}")
    #         continue
    #     try:
    #         entities_response = r2r_client.documents.list_entities(doc_id)
    #         entities = entities_response.results
    #     except Exception as e:
    #         logger.error(f"获取文档{doc.id}:{doc.title}的chunks时发生错误: {e}")
    #         continue