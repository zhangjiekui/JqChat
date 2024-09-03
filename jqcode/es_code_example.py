
#直接使用DictExporter和DictImporter会存在问题，所以使用YAML Import/Export作为中转
#参照https://anytree.readthedocs.io/en/latest/tricks/yaml.html 
import yaml
import shortuuid
import copy 
from anytree.exporter import DictExporter
from anytree.importer import DictImporter
from anytree import RenderTree
from pathlib import Path

from jqcode.jq_agent.c0_init_env_models import env_models_instance
from jqcode.jq_readers.jqkj_readers import JqkjSimpleDirectoryReader
from jqcode.jq_agent.tools.jq_retriever import get_retriever

from langchain.schema import Document as LcDocument
from base64 import b64encode,b64decode

from elasticsearch import Elasticsearch, helpers

from jqcode.jq_utils.logger import jqkj_logger
logger = jqkj_logger(__file__).get_logger()

anytree_dict_exporter = DictExporter()
anytree_dict_importer = DictImporter()
es_connection = env_models_instance.get_es_connection()
llm = env_models_instance.chat_model
doc_tree_spiltter = env_models_instance.doc_tree_spiltter
embed_model = env_models_instance.embed_model
reranker = env_models_instance.reranker

files_index = "bulk_files_on_es"

index_name="smartcn_test_doc_tree_reader"
if not es_connection.indices.exists(index=index_name):
    # settings = {
    #     "index": {"analysis.analyzer.default.type": "smartcn","analysis.search_analyzer.default.type": "smartcn"}
    #     }
    settings = {"index": {"analysis.analyzer.default.type": "ik_max_word","analysis.search_analyzer.default.type": "ik_smart"}}

    es_connection.indices.create(index=index_name,settings=settings)
# 目前还不能默认应用到index接到和search阶段
default_result = es_connection.indices.analyze(text="中华人民共和国国歌")
default_analyzer_result = es_connection.indices.analyze(text="中华人民共和国国歌",index=index_name)
default_analyzer_result_en = es_connection.indices.analyze(text="This analyzer uses probabilistic knowledge to find the optimal word segmentation for Simplified Chinese text",index=index_name)

default_analyzer_result2 = es_connection.indices.analyze(text="中华人民共和国国歌",analyzer='ik_max_word')
smartcn_analyzer_result = es_connection.indices.analyze(text="中华人民共和国国歌",analyzer='smartcn')
smartcn_analyzer_result_en = es_connection.indices.analyze(text="This analyzer uses probabilistic knowledge to find the optimal word segmentation for Simplified Chinese text",analyzer='smartcn')

# default_search_result = es_connection.search(query="中华人民共和国国歌",index=smartcn_index)

# 在kibana中进行测试
# GET /smartcn_test_doc_tree_reader/_analyze
# {
#   "field":"source",
#   "text":"中华人民共和国国歌"
# }

# 结果为：
# {
#   "tokens": [
#     {
#       "token": "中华人民共和国",
#       "start_offset": 0,
#       "end_offset": 7,
#       "type": "word",
#       "position": 0
#     },
#     {
#       "token": "国歌",
#       "start_offset": 7,
#       "end_offset": 9,
#       "type": "word",
#       "position": 1
#     }
#   ]
# }

input_files = [fr'/data/projects/JqChatV2/JqChat/jqcode/jq_readers/.test_files/.testinputdocs/AAMIS_项目总体计划_120925.doc'] 
input_files += [fr'/data/projects/JqChatV2/JqChat/jqcode/jq_readers/.test_files/.testinputdocs/PPQA000_质量保证过程.doc'] 


input_dir="/data/projects/JqChatV2/JqChat/jqcode/jq_readers/.test_files/.testinputdocs"
def reader_load_files(dir:str=input_dir,input_files:str=input_files):
    simple_reader = JqkjSimpleDirectoryReader(input_dir=None,input_files=input_files, overwrite_existing_converted_files=False,required_exts=['.doc','.docx','.pdf','.txt','.py'],exclude_hidden=False)
    lm_documents = simple_reader.load_data()
    return lm_documents

def upload_file_documents_to_es(lm_documents:list):

    actions_list = []
    es_index_doc_id_list = []
    for document in lm_documents:
        file_path = document.metadata['source']
        ext = Path(file_path).suffix
        es_index_doc_id = shortuuid.uuid()

        file_b64 = None
        with open(file_path, 'rb') as file: 
            file_data = file.read()
            file_b64 = b64encode(file_data).decode('utf-8')

        added_metadata = {"file_extension":ext,'es_index_name':files_index,"es_index_doc_id":es_index_doc_id}
        document.metadata.update(added_metadata)

        index_metadata = copy.deepcopy(document.metadata)
        _df_table_list_jq = index_metadata.pop('df_table_list_jq',None)
        _file_doc_object_jq = index_metadata.pop('file_doc_object_jq',None)
        doc_tree = index_metadata.pop('file_doc_tree_jq',None)

        doc_tree_yaml = ''
        if doc_tree:
            doc_tree_dict = anytree_dict_exporter.export(doc_tree)
            doc_tree_yaml = yaml.dump(doc_tree_dict, default_flow_style=False)

        document_dict = {"metadata":index_metadata,"text":document.text,"doc_tree_yaml":doc_tree_yaml,"file_original":file_b64}
        action = {"_index":files_index, "_id":es_index_doc_id, "_source":document_dict}
        actions_list.append(action)
        es_index_doc_id_list.append(es_index_doc_id)

    helpers.bulk(es_connection, actions_list)
    print(es_index_doc_id_list)
    print("=====上传完成======"*5)
    return lm_documents,es_index_doc_id_list

def splitter_split_documents(lm_documents:list):
    nodes = doc_tree_spiltter.get_nodes_from_documents(lm_documents)
    lc_documents = [LcDocument(page_content=node.text,metadata=node.metadata) for node in nodes]
    return lc_documents

def embedding_and_indexing_to_es(lc_documents:list,index_name=index_name):
    vectorstore = env_models_instance.get_es_searchstore_index_documents(documents=lc_documents, embedding=embed_model,index_name=index_name,source_id_key='source')
    return vectorstore

def run_a_query_test(query,retriever,llm=llm):    
    from jqcode.jq_splitters.jq_docx_tree_text_splitter import chain_qa_fun    
    result = chain_qa_fun(query=query,retriever=retriever,llm=llm)
    return result

def download_file_documents_to_local(es_index_doc_id_list):
    # es_index_doc_id_list=['ZtqWHXgbEubnEEnbtkfeza', 'GNcgbhSkMS82AjckFKqHXW', 'bQvgLmxtKuRcWzwMxCCZ9m', 'DxPQC7vbEDVdAo3AmYX8Ei', 'NpM9GUf3nuwZg2R97R3QdQ', 'GmScwyhBPdf7JSUtk7zNUZ', 'bNFn6UKHuXjddWaRCVhVe4', 'KxPKLVxSAU6jFkhH5Q6Wxz', 'XxQ8AShxXse7ix6PVgbSKR']
    print("======下载====="*5)  
    for i,index_id in enumerate(es_index_doc_id_list):  
        result = es_connection.get(index=files_index, id=index_id)
        print(result.body['_id'],result.body['_source']['metadata']['source'])
        
        doc_tree_yqml = result.body['_source']['doc_tree_yaml']
        #    print(f"{doc_tree_yqml=}")   
        if doc_tree_yqml:
                doc_tree_dict = yaml.load(doc_tree_yqml, Loader=yaml.Loader)  
                doc_tree = anytree_dict_importer.import_(doc_tree_dict)
                print(RenderTree(doc_tree,maxlevel=1))
        
        file_b64 = result.body['_source']['file_original'].encode('utf-8')
        ext = result.body['_source']['metadata']['file_extension']
        fpath = fr'/data/projects/JqChatV2/workspace/{i}{ext}'
        print(f"{fpath=}") 
        with open(fpath, "wb") as fp:
                fp.write(b64decode(file_b64))


if __name__ == "__main__":
    from jqcode.jq_docstores.es_docstores import JqElasticsearchDocumentStore
    jq_es_store = JqElasticsearchDocumentStore()

    # mapping = es_connection.indices.get_mapping(index=smartcn_index)
    
    # # 打印映射信息
    # print(mapping)


    from_beginning = True

    if from_beginning:
        # 从头开始的
        lm_documents = reader_load_files()



        status,lm_documents_with_added_index_info_metadata,es_index_doc_id_list = jq_es_store.add_or_update_docs_if_id_exists(lm_documents)
        status = jq_es_store.update_doc_fields_values(doc_ids=["fa39031f020a45efc744f73f0031a80d"],update_field_value_pair_dict=[{"status":"true","file_text":"更新第二条的status为true"}])
        status = jq_es_store.update_doc_fields_values(doc_ids=["04281eef4b0eb67013c654937ab52a03","fa39031f020a45efc744f73f0031a80d"],update_field_value_pair_dict=[{"status":"true","file_text":"更新第一条的status为true"},{"status":"false","file_text":"更新第二条的status为false"}])
        jq_es_store.update_doc_fields_values() #没有默认参数，会报错
        docs1 = jq_es_store.search_docs_by_text("AAMIS_项目总体计划")
        print(docs1[0].text)
        print(docs1[0].doc_id)
        docs2 = jq_es_store.search_docs_by_text("PPQA000")
        print(docs2[0].text)
        print(docs2[0].doc_id)

        docs3 = jq_es_store.search_docs_by_bm25("PPQA000")
        print(docs3[0].text)
        print(docs3[0].doc_id)

        docs4 = jq_es_store.get("fa39031f020a45efc744f73f0031a80d")
        print(docs4[0].text)
        print(docs4[0].doc_id)

        docs5 = jq_es_store.get(["fa39031f020a45efc744f73f0031a80d","04281eef4b0eb67013c654937ab52a03"])
        for doc in docs5:
            print(doc.text)
            print(doc.doc_id)

        docs6 = jq_es_store.get_all()
        for doc in docs6:
            print(doc.text)
            print(doc.doc_id)

        jq_es_store.delete("fa39031f020a45efc744f73f0031a80d")

        count = jq_es_store.count()



        lm_documents_with_added_index_info_metadata,es_index_doc_id_list = upload_file_documents_to_es(lm_documents)
        lc_documents = splitter_split_documents(lm_documents_with_added_index_info_metadata)
        print(len(lc_documents))
        vectorstore = embedding_and_indexing_to_es(lc_documents,index_name=index_name)
        # 已经入库了

    # （1）基于返回的vectorstore，直接检索回答    
        compression_retriever = get_retriever(vectorstore=vectorstore,index_name=None)
    else:
    # （2）基于知识库名来重新连接，检索回答    
        compression_retriever = get_retriever(vectorstore=None,index_name=index_name)

    # 打印映射信息
    settings = es_connection.indices.get_settings(index=index_name) 
    print(settings)
    # 针对以下文件中的表格提问
    # /data/projects/JqChatV2/JqChat/jqcode/jq_readers/.test_files/.testinputdocs/AAMIS_项目总体计划_120925.doc
    query = "安徽省食品药品监督管理局行政审批系统项目总体计划的版本号是多少，批准人是谁？"
    answer,hits = run_a_query_test(query,retriever=compression_retriever)

    print(answer) 


