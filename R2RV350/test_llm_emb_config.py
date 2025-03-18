from R2RV350.py.core.main.config import R2RConfig
from R2RV350.py.core.providers.llm.litellm import LiteLLMCompletionProvider
from R2RV350.py.core.providers.embeddings.litellm import LiteLLMEmbeddingProvider
from R2RV350.py.r2r import R2RClient
from R2RV350.py.shared.api.models.ingestion.responses import IngestionResponse
from R2RV350.py.shared.abstractions import ChunkSearchResult
import uuid
from uuid import UUID
def model_test():
    print("大语言模型测试-------------------")
    r2rconfig = R2RConfig.from_toml(config_path="/data/projects/JqChatV2/JqChat/R2RV350/py/core/configs/full_jq.toml")
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
    client = R2RClient(base_url='http://10.1.150.105:7272') # can set remote w/ R2RClient(base_url=...)
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


if __name__ == "__main__":
    model_test()
    # r2r_test()





