from r2r import *
import uuid
from uuid import UUID

r2rconfig = R2RConfig.from_toml(config_path="/data/projects/JqChatV2/JqChat/JqR2R/py/r2r/r2r.toml")
print("R2R服务测试--------请首先运行[python -m r2r.serve]启动R2R服务--------")
client = R2RClient(base_url='http://10.1.150.105:7272') # can set remote w/ R2RClient(base_url=...)
client.users.login("admin@example.com", "change_me_immediately")
print("R2RClient对象创建\登录成功")

def model_test():
    print("大语言模型测试-------------------")    
    litellm = LiteLLMCompletionProvider(config=r2rconfig.completion)
    llm_task = {"messages":[{ "content": "Hello, who are you?","role": "user"}], "generation_config": r2rconfig.completion.generation_config, "kwargs": {}}
    llm_result= litellm._execute_task_sync(llm_task)
    print(llm_result.choices[0].message.content)
    print("以上为大语言模型测试输出结果-------------------")

    print("embedding模型测试-------------------")
    emb_task = {"texts":"测试embedding文本"}
    liteemb = LiteLLMEmbeddingProvider(config=r2rconfig.embedding)
    liteemb_result = liteemb._execute_task_sync(emb_task)
    print("输出的向量维度为",len(liteemb_result[0]))
    print("以上为embedding测试输出结果-------------------")



    print("rerank模型测试-------------------")
    r1=ChunkSearchResult(id=uuid.uuid1(),text='测试文本1',score=0.1,document_id=uuid.uuid1(),owner_id=uuid.uuid1(),collection_ids=[uuid.uuid1()],metadata={})
    r2=ChunkSearchResult(id=uuid.uuid1(),text='测试文本2',score=0.2,document_id=uuid.uuid1(),owner_id=uuid.uuid1(),collection_ids=[uuid.uuid1()],metadata={})
    r3=ChunkSearchResult(id=uuid.uuid1(),text='测试文本3',score=0.3,document_id=uuid.uuid1(),owner_id=uuid.uuid1(),collection_ids=[uuid.uuid1()],metadata={})

    test_list=[r1,r2,r3]
    print("同步的rerank方法测试")
    rerank_result=liteemb.rerank('测试rerank文本',test_list)
    print(rerank_result)
    print("异步的rerank方法测试")
    import asyncio
    a_rerank_result=asyncio.run(liteemb.arerank('测试rerank文本',test_list))
    print(a_rerank_result)
    print("以上为rerank模型测试输出结果-------------------")

def r2r_test():

    try:
        doc=client.documents.create(file_path="/data/projects/JqChatV2/JqChat/JqR2R/py/doc1.docx")
        print(doc)
        doc_id=doc.results.document_id
        message = doc.results.message
        print(doc_id)
        print(message)
    except Exception as e:
        print(e)

    # 各种方法的含义
# https://r2r-docs.sciphi.ai/api-and-sdks/retrieval/retrieval
# https://r2r-docs.sciphi.ai/api-and-sdks/retrieval/search-app
    print("Performing RAG...")
    rag_response = client.retrieval.rag(
        query="什么是质量保证过程?",
        search_settings={
            "use_semantic_search": True,
            "use_hybrid_search": True,
            # "filters": {"document_id": {"$eq": "e43864f5-a36f-548e-aacd-6f8d48b30c7f"}},
            "limit": 10,
        },
    rag_generation_config={
        "stream": False,
        "temperature": 0.7,
        "max_tokens": 1500
    }
    )

    print(rag_response.results.completion)
    print(rag_response.results.generated_answer)
    print(rag_response.results.citations)
    # 获取搜索过程的结果:共有四种
    print(rag_response.results.search_results.chunk_search_results)
    print(rag_response.results.search_results.graph_search_results)
    print(rag_response.results.search_results.document_search_results)
    print(rag_response.results.search_results.document_search_results)

    print("Performing Search...")
    search_response = client.retrieval.search(
        query="什么是质量保证过程?",
        search_mode="advanced",
    )

    print(search_response.results.chunk_search_results)
    print(search_response.results.graph_search_results)
    print(search_response.results.web_search_results)    
    print(rag_response.results.search_results.document_search_results)


    print("Performing agent...")
    agent_response = client.retrieval.agent(
        message={
        "role": "user",
        "content": "什么是质量保证过程?"
        # "content": "Do a deep analysis of the philosophical implications of DeepSeek R1"
        },
        rag_tools=["web_search", "web_scrape", "search_file_descriptions", "search_file_knowledge", "get_file_content"],
    )

    print(agent_response.results.messages[0].content)
    print(agent_response.results.messages[0].metadata)
    print(agent_response.results.messages[0].metadata.get("citations","[No Citations]"))
    print(agent_response.results.messages[0].metadata.get("tool_calls","[No ToolCalls]"))
    print(agent_response.results.messages[0].metadata.get("aggregated_search_result","[No Aggregated_Search_Results]"))
    aggregated_search_result_str=agent_response.results.messages[0].metadata.get("aggregated_search_result","[No Aggregated_Search_Results]")
    globals_dict = {'null': None}
    aggregated_search_result_list=eval(aggregated_search_result_str,globals_dict)
    for i,item in enumerate(aggregated_search_result_list):
        print(f"第{i+1}个搜索结果:")
        print(f"  --{item}")
    print(agent_response.results.messages[0].metadata.get("aggregated_search_result","[No Aggregated_Search_Results]"))
    print("以上为R2R服务测试输出结果-------------------")


from jqcode.jq_readers.jqkj_readers import JqkjSimpleDirectoryReader
from jqcode.jq_agent.c0_init_env_models import env_models_instance
from jqcode.jq_utils.logger import jqkj_logger
logger = jqkj_logger(__file__).get_logger()
doc_tree_spiltter = env_models_instance.doc_tree_spiltter

# 转换文件：/data/projects/JqChatV2/JqChat/JqR2R/py/sdk/sync_methods/documents.py
# 或者：async def _process_file(file) /data/projects/JqChatV2/JqChat/JqR2R/py/core/main/api/v3/documents_router.py
# 自定义ChunkingStrategy： /data/projects/JqChatV2/JqChat/JqR2R/py/core/base/providers/ingestion.py
# 自定义spitter：/data/projects/JqChatV2/JqChat/JqR2R/py/core/providers/ingestion/r2r/base.py
# chunk方法：/data/projects/JqChatV2/JqChat/JqR2R/py/core/providers/ingestion/r2r/base.py

def get_chunked_documents_from_file_directory(dir:str,input_files:str=None, overwrite_existing_converted_files=False,required_exts=['.doc','.docx','.pdf','.txt','.py'],exclude_hidden=False):
    # 构造晶奇文件读取器，读取目录中的文件
    simple_reader = JqkjSimpleDirectoryReader(input_dir=dir,input_files=input_files, 
                                              overwrite_existing_converted_files=overwrite_existing_converted_files,
                                              required_exts=required_exts,
                                              exclude_hidden=exclude_hidden)
    documents = simple_reader.load_data()
    logger.warning(f'Loaded {len(documents)} documents from {dir}:')
    list_of_dict_docid_chunks_metadata = []
    for idx, doc in enumerate(documents):
        logger.warning(f'  ==原始文档[{idx+1}]:  {doc.metadata.get("source",doc.metadata.get("original_source_jq",""))}\n         转换=>   {doc.metadata.get("original_source_converted_jq",doc.metadata.get("file_path",""))}')
        tree_nodes = doc_tree_spiltter.get_nodes_from_documents([doc])
        doc_id = doc.id_
        metadata = doc.metadata
        file_path = doc.metadata.get("file_path",doc.metadata.get("original_source_converted_jq",doc.metadata.get("source",doc.metadata.get("original_source_jq",""))))
        chunks = [node.text for node in tree_nodes]
        client.documents.create(id=doc_id,chunks=chunks,metadata=metadata,ingestion_mode="fast")
        # client.documents.create(file_path=file_path,id=doc_id,chunks=chunks,metadata=metadata,ingestion_mode="fast")  # use fast for a quick chunk ingestion
        list_chunks_response = client.documents.list_chunks(id=doc_id,include_vectors=True)
        extract_response = client.documents.extract(id=doc_id,run_with_orchestration= True)
        print(extract_response.results.message)
        deduplicate_response = client.documents.deduplicate(id=doc_id)
        print(deduplicate_response.results.message)

    documents_search_response = client.documents.search(query="什么是质量保证过程?",search_mode="advanced")
    print('文档搜索结果......')
    for result in documents_search_response.results:
        print("---------")
        print(f"{result.title=},{result.ingestion_status=},{result.summary=}")
    
    print('检索搜索结果......')
    retrieval_search_response = client.retrieval.search(query="什么是质量保证过程?", search_mode="advanced")
    for result in retrieval_search_response.results:
        print("---------")
        print(f"{result.title=},{result.ingestion_status=},{result.summary=}")







        pass
        # dict_docid_chunks_metadata = [{"doc_id":str(doc.metadata.get("doc_id",uuid.uuid1())),"chunk":node.text,"metadata":node.metadata} for node in tree_nodes]

    # 使用文档树分割器，将文档分割成切片（树节点）
    tree_nodes = doc_tree_spiltter.get_nodes_from_documents(documents)
    # 将切片（树节点）转换成LangChain格式的文档
    # chunked_documents = [LcDocument(page_content=node.text,metadata=node.metadata) for node in tree_nodes]
    # logger.warning(f'Splits {len(documents)} documents into {len(chunked_documents)} chunks.')

    return tree_nodes

def r2r_lifecycle_test():
    print("R2R服务生命周期测试--------请首先运行[python -m r2r.serve]启动R2R服务--------")
    print("==List documents==")
    print(client.documents.list(limit=10, offset=0))
    print("==Create document==")
    client.documents.create(
    chunks=None,
    ingestion_mode="fast"  # use fast for a quick chunk ingestion
)



if __name__ == "__main__":

    # model_test()
    r2r_test()
    file_dir = '/data/projects/JqChatV2/JqChat/langchain_graphrag_code_test/data'
    # chunked_documents = get_chunked_documents_from_file_directory(file_dir)