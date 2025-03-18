from R2RV350.py.core.main.config import R2RConfig
from R2RV350.py.core.providers.llm.litellm import LiteLLMCompletionProvider
from R2RV350.py.core.providers.embeddings.litellm import LiteLLMEmbeddingProvider



if __name__ == "__main__":

    r2rconfig = R2RConfig.from_toml(config_path="/data/projects/JqChatV2/JqChat/R2RV350/py/core/configs/full_jq.toml")
    litellm = LiteLLMCompletionProvider(config=r2rconfig.completion)
    llm_task = {"messages":[{ "content": "Hello, who are you?","role": "user"}], "generation_config": r2rconfig.completion.generation_config, "kwargs": {}}
    llm_result= litellm._execute_task_sync(llm_task)
    # print(llm_result)
    print(llm_result.choices[0].message.content)

    emb_task = {"texts":"测试embedding文本"}
    liteemb = LiteLLMEmbeddingProvider(config=r2rconfig.embedding)
    liteemb_result = liteemb._execute_task_sync(emb_task)
    print(liteemb_result)


    from R2RV350.py.shared.abstractions import ChunkSearchResult
    import uuid
    r1=ChunkSearchResult(id=uuid.uuid1(),text='测试文本1',score=0.1,document_id=uuid.uuid1(),owner_id=uuid.uuid1(),collection_ids=[uuid.uuid1()],metadata={})
    r2=ChunkSearchResult(id=uuid.uuid1(),text='测试文本2',score=0.2,document_id=uuid.uuid1(),owner_id=uuid.uuid1(),collection_ids=[uuid.uuid1()],metadata={})
    r3=ChunkSearchResult(id=uuid.uuid1(),text='测试文本3',score=0.3,document_id=uuid.uuid1(),owner_id=uuid.uuid1(),collection_ids=[uuid.uuid1()],metadata={})

    test_list=[r1,r2,r3]


    rerank_result=liteemb.rerank('测试rerank文本',test_list)
    print(rerank_result)

    import asyncio
    a_rerank_result=asyncio.run(liteemb.arerank('测试rerank文本',test_list))
    print(a_rerank_result)