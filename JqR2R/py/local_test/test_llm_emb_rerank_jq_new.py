import os,sys,pathlib
project_root_path = pathlib.Path().resolve()
sys.path.append(str(project_root_path))
os.environ['OPENAI_API_KEY']='abc123' 

print("=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*")    
project_root_path = pathlib.Path().resolve()
print(f"应用启动路径:{project_root_path}")
print(f"本项目中添加使用的Python路径为：{set(sys.path)}")
from r2r import *
# from r2r import LiteLLMCompletionProvider

import uuid
from uuid import UUID
def model_test():
    print("大语言模型测试-------------------")
    r2rconfig = R2RConfig.from_toml(config_path="/data/projects/JqChatV2/JqChat/JqR2R/py/r2r/r2r.toml")
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
    print("R2R服务测试--------请首先启动R2R服务--------")
    client = R2RClient(base_url='http://10.1.150.105:7272') # can set remote w/ R2RClient(base_url=...)
    print("R2RClient对象创建成功")
    client.users.login("admin@example.com", "change_me_immediately")
    try:
        doc=client.documents.create(file_path="/data/projects/JqChatV2/JqChat/财务发票模板.docx")
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


if __name__ == "__main__":

    model_test()
    r2r_test()