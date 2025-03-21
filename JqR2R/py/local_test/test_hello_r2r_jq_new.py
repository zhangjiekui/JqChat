import os,sys,pathlib
project_root_path = pathlib.Path().resolve()
sys.path.append(str(project_root_path))
os.environ['OPENAI_API_KEY']='abc123' 



from r2r import *

def r2r_test():
    print("R2R服务测试--------请首先启动R2R服务--------")
    from r2r import R2RClient
    client = R2RClient(base_url='http://10.1.150.105:7272') # can set remote w/ R2RClient(base_url=...)
    client.users.login("admin@example.com", "change_me_immediately")
    try:
        doc=client.documents.create(file_path="/data/projects/JqChatV2/JqChat/PPQA000_质量保证过程.docx")
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



if __name__ == "__main__":
    # model_test()
    r2r_test()