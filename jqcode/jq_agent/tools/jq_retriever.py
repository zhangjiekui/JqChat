import copy
from typing import List
from pathlib import Path
from langchain import schema
from elasticsearch import Elasticsearch
from langchain_elasticsearch import ElasticsearchStore
from elasticsearch.helpers.vectorstore import DenseVectorStrategy,BM25Strategy
from langchain.retrievers import EnsembleRetriever,ContextualCompressionRetriever
from langchain_community.retrievers import ElasticSearchBM25Retriever

from llama_index.core.readers.file.base import default_file_metadata_func
from jqcode.jq_readers.jqkj_readers import JqkjSimpleDirectoryReader,JqkjDocxReader
from jqcode.jq_readers.backend_reader_utils.jqkj_doc_tree_utils import jieba_pre_process
from jqcode.jq_agent.c0_init_env_models import env_models_instance,JqVectorStoreRetrieverWithScore
from jqcode.jq_utils.logger import jqkj_logger
logger = jqkj_logger(__file__).get_logger()


def get_retriever(vectorstore:ElasticsearchStore=None,index_name:str='',index_description:str='',chat_on_docs_list:List[str]=[],add_docs_list_to_kb=True,default_temp_index_name:str="temp_index_for_upload_files",
                  top_k:int=10,score_threshold:float=0.2,source_id_key='source',required_exts=['.doc','.docx','.pdf','.md'],r2r_client=None,current_user=''):
    
    embed_model = env_models_instance.embed_model
    reranker = env_models_instance.reranker
    es_connection = env_models_instance.get_es_connection()
    doc_paths_exists = []
    vector_retriever = None
    if index_name:
        index_name = index_name.lower() # Elasticsearch的index_name必须小写

# 如果是已经有了vectorstore
    if vectorstore:
        # vector_retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k":top_k})
        vector_retriever = JqVectorStoreRetrieverWithScore(name="embedding",vectorstore=vectorstore,search_type="similarity_score_threshold", search_kwargs={"score_threshold":score_threshold,"k":top_k}) 

# 如果是chat on docs, 则获取基于文件过滤的retriever
    elif chat_on_docs_list:
        assert index_name, f"'index_name'参数不得为空，连接Elasticsearch检索时需要！"
        chat_on_docs_list = [Path(item) for item in chat_on_docs_list]
        # Path.exists(chat_on_docs_list[0])
        doc_paths_exists = [item for item in chat_on_docs_list if Path.exists(item)]
        doc_paths_not_exists = [item for item in chat_on_docs_list if not Path.exists(item)]
        RESERVED_FILTER_BY_FILES = []
        default_vectorstore = None
        

        if len(doc_paths_exists)==0:
            logger.warning(f"'{chat_on_docs_list=}'中不存在的任何有效文件路径，请检查确认！")
        
        # 1、存在有效文件，开始真正的处理逻辑
        else:
            if doc_paths_not_exists:
                logger.warning(f"以下文件路径并不存在，请检查确认！'{doc_paths_not_exists=}'")
        
            # 决定上传到用户指定的知识库，还是默认的临时知识库
            index_destination = None        
            if add_docs_list_to_kb:
                index_destination = index_name
            else:
                index_destination = default_temp_index_name
                logger.warning(f"您没有选择将文件上传到知识库'{index_name=}'，将使用默认的临时知识库{default_temp_index_name=}来处理。")
                index_description = "临时使用的知识库，用来临时性分析处理和检索：（1）用户上传的文档分析（但不存入知识库）；（2）从用户历史会话中检索出与当前会话的相关消息记录"
                
            
            _RESERVED_FILTER_BY_FILES = []
            for i,doc in enumerate(doc_paths_exists):
                suffix = doc.suffix
                if suffix in required_exts:                    
                    if doc.suffix !='.docx':
                        docx = str(doc.parent/doc.stem) + '.docx'
                        _RESERVED_FILTER_BY_FILES.append(docx)
                    else:
                        _RESERVED_FILTER_BY_FILES.append(str(doc))
                else:
                    logger.warning(f"{doc}还不是支持的知识库文件类型{required_exts}")
                    if suffix in [".png",".jpg",".jpeg"]:
                        logger.warning(f"{doc}是图片文件，将直接调用VLM模型来处理")
                        ocr = env_models_instance.get_ocr()
                        ocr_mode = env_models_instance.ocr_mode
                        if ocr_mode == "API":
                            result = ocr(doc)
                            logger.debug(f"$$图片[{doc}]中的OCR文本:\n{result}")
                            txt_file = str(doc.parent/doc.stem) + '.txt' 
                            with open(txt_file,"w") as f:
                                f.write(result)
                            _RESERVED_FILTER_BY_FILES.append(txt_file)
                            doc_paths_exists[i] = txt_file


            
            RESERVED_FILTER_BY_FILES = [str(file) for file in _RESERVED_FILTER_BY_FILES]
            
            existed_files_maybe_need_indexing = [str(file) for file in doc_paths_exists]
            files_to_be_add_to_index = []            
            # 在给定的index_name中（如果没给定，就放到'temp_index_for_upload_files'知识库中）查询
            # 是否全部或部分文件已经存在索引了，如果已经存在，就不要做文件的读取、切分等操作，节省时间
            # 得到真正的files_to_be_add_to_index

        # region 2、在知识库中查询是否已经存在拟上传的文件
            if not es_connection.indices.exists(index=index_destination):
                settings = env_models_instance.ES_DEFAULT_CHINESE_SETTINGS
                es_connection.indices.create(index=index_destination,settings=settings)

            if es_connection.indices.exists(index=index_destination): 
            # region 保留用做测试   
                # query0= {
                #             "query": {"terms":{"metadata.source.keyword":[filter_by_files[0]]}},
                #             "size":10000,# 注意设置size，默认返回10个。
                #         }
                # all_results_in_the_index = es_connection.search(index=default_temp_index_name, body=query0)
                # all_hits0 = all_results_in_the_index['hits']['hits']
                # print(len(all_hits0))

                # query1= {
                #             "query": {"terms":{"metadata.source.keyword":[filter_by_files[1]]}},
                #             "size":10000,# 注意设置size，默认返回10个。
                #         }
                # all_results_in_the_index = es_connection.search(index=default_temp_index_name, body=query1)
                # all_hits1 = all_results_in_the_index['hits']['hits']
                # print(len(all_hits1))
            # endregion 保留用做测试
                query = {
                            "query": {"terms":{"metadata.source.keyword":RESERVED_FILTER_BY_FILES}},
                            "size":10000,# 注意设置size，默认返回10个。
                        }
                all_results_in_the_index = es_connection.search(index=index_destination, body=query)
                all_hits = all_results_in_the_index['hits']['hits']
                print(f"知识库{index_destination}中共有{len(all_hits)=}个文档")

                file_stem_set_without_extention = set()
                has_processed_file_path = set()
                for hit in all_hits:
                    _source = hit["_source"]
                    if 'vector' in _source.keys():
                        metadata = _source["metadata"]
                        file_key = ''
                        if "source_kb" in metadata.keys():
                            file_key = "source_kb"
                        elif "source" in metadata.keys():
                            file_key = "source"
                        elif "original_source_jq" in metadata.keys():
                            file_key = "original_source_jq"
                        else:
                            raise Exception('Langchain Document的metadata不存在key:"source_kb"、"source"或"original_source_jq"')
                        file_path = metadata[file_key]
                        if file_path not in has_processed_file_path:
                            has_processed_file_path.add(file_path)

                            # 调用/root/.virtualenvs/test/lib/python3.10/site-packages/llama_index/legacy/readers/file/base.py
                            # default_file_metadata_func方法，来获取文件default_file_metadata
                            default_file_metadata = default_file_metadata_func(file_path)
                            file_size_current = default_file_metadata['file_size']
                            last_modified_current = default_file_metadata['last_modified_date']
                            file_size_in_es_index = metadata['file_size']
                            last_modified_date_in_es_index = metadata['last_modified_date']
                            if file_size_current==file_size_in_es_index and last_modified_current == last_modified_date_in_es_index:
                                file_stem = Path(file_path).stem
                                file_stem_set_without_extention.add(file_stem)
                            else:
                                if Path(file_path).suffix!='.docx':
                                    if "original_source_converted_jq" in metadata.keys():
                                        converted_file_key = "original_source_converted_jq"
                                    elif "file_path" in metadata.keys():
                                        converted_file_key = "file_path"
                                    else:
                                        raise Exception('Langchain Document的metadata不存在key:"file_path"或"original_source_converted_jq"')                                

                                    # 调用/root/.virtualenvs/test/lib/python3.10/site-packages/llama_index/legacy/readers/file/base.py
                                    # default_file_metadata_func方法，来获取文件default_file_metadata
                                    converted_file_path = metadata[converted_file_key]
                                    if converted_file_path!=file_path:
                                        default_converted_file_metadata = default_file_metadata_func(converted_file_path)
                                        file_size_converted = default_converted_file_metadata['file_size']
                                        last_modified_converted = default_converted_file_metadata['last_modified_date']
                                        if file_size_converted==file_size_in_es_index and last_modified_converted == last_modified_date_in_es_index:
                                            file_stem = Path(file_path).stem
                                            file_stem_set_without_extention.add(file_stem)                                

                filter_by_file_stem_without_extention = [Path(file_path).stem for file_path in existed_files_maybe_need_indexing]
                for i, file in enumerate(filter_by_file_stem_without_extention):                        
                    if file not in file_stem_set_without_extention:
                        files_to_be_add_to_index.append(existed_files_maybe_need_indexing[i])
                    else:
                        logger.warning(f"......{index_destination=}中已经存在{file=},跳过......") 

                existed_files_maybe_need_indexing = files_to_be_add_to_index
        # endregion 在知识库中查询是否已经存在拟上传的文件

            # 3、读取和处理还不存在的文件
            if existed_files_maybe_need_indexing:
                from jqcode.jq_docstores.jq_es_client import JqEsClient
                jq_es_client = JqEsClient()
                default_vectorstore = jq_es_client.chunks_indexing_from_input_dir_or_files(current_user=current_user,index_name=index_destination,description=index_description,input_files=existed_files_maybe_need_indexing,r2r_client=r2r_client)
            else:
                default_vectorstore = env_models_instance.get_es_searchstore(es_connection=es_connection,embedding=embed_model,index_name=index_destination) 
    
        if default_vectorstore and RESERVED_FILTER_BY_FILES:
                filters = {"terms":{f"metadata.{source_id_key}.keyword": RESERVED_FILTER_BY_FILES}} 
                # vector_retriever = default_vectorstore.as_retriever(search_type="similarity", search_kwargs={"k":top_k,"filter":filters})
                vector_retriever = JqVectorStoreRetrieverWithScore(name="embedding",vectorstore=default_vectorstore,search_type="similarity_score_threshold", search_kwargs={"score_threshold":score_threshold,"k":top_k,"filter":filters})
            #region:文件过滤检索器的测试
                # file_list = [RESERVED_FILTER_BY_FILES[0]]
                # filters = {"terms":{f"metadata.{source_id_key}.keyword": file_list}}
                # vector_retriever = default_vectorstore.as_retriever(search_type="similarity_score_threshold", search_kwargs={'k':20,'score_threshold': 0.8,'filter':filters})
                # result =vector_retriever.invoke("晶奇公司的应急技术服务电话？")
                # files = [d.metadata['file_name'] for d in result]
                # uni_files = set(files)
                # print(f"基于{file_list}进行检索，共检索到{len(files)}个文件，检索出的Unique文件为:{uni_files}")

                # vector_retriever = default_vectorstore.as_retriever(search_type="similarity_score_threshold", search_kwargs={'k':20,'score_threshold': 0.73,'filter':filters})
                # result =vector_retriever.invoke("晶奇公司的应急技术服务电话？")
                # files = [d.metadata['file_name'] for d in result]
                # uni_files = set(files)
                # print(f"还是基于{file_list}进行检索，但改变了'score_threshold'，共检索到{len(files)}个文件，检索出的Unique文件为:{uni_files}")

                # file_list = [RESERVED_FILTER_BY_FILES[1]]
                # filters = {"terms":{f"metadata.{source_id_key}.keyword": file_list}}
                # vector_retriever = default_vectorstore.as_retriever(search_type="similarity", search_kwargs={'k':20,'score_threshold': 0.8,'filter':filters})
                # result =vector_retriever.invoke("晶奇公司的应急技术服务电话？")
                # files = [d.metadata['file_name'] for d in result]
                # uni_files = set(files)
                # print(f"基于{file_list}进行检索，共检索到{len(files)}个文件，检索出的Unique文件为:{uni_files}")

                # file_list = RESERVED_FILTER_BY_FILES
                # filters = {"terms":{f"metadata.{source_id_key}.keyword": file_list}}
                # vector_retriever = default_vectorstore.as_retriever(search_type="similarity", search_kwargs={'k':20,'score_threshold': 0.8,'filter':filters})
                # result =vector_retriever.invoke("晶奇公司的应急技术服务电话？")
                # files = [d.metadata['file_name'] for d in result]
                # uni_files = set(files)
                # print(f"基于{file_list}进行检索，共检索到{len(files)}个文件，检索出的Unique文件为:{uni_files}")      
            #endregion:文件过滤检索器的测试

    else:
        assert vector_retriever is None,"临时性的处理逻辑"

# 如果没有获取到基于文件过滤的retriever，也没有提供可用的vectorstore
# 则返回一个默认的基于整个知识库的retriever,index必须为用户指定的index_name
    if not vector_retriever:
        default_vectorstore = env_models_instance.get_es_searchstore(es_connection=es_connection,embedding=embed_model,index_name=index_name)
        # vector_retriever = default_vectorstore.as_retriever(search_type="similarity", search_kwargs={"k":top_k})
        vector_retriever = JqVectorStoreRetrieverWithScore(name="embedding",vectorstore=default_vectorstore,search_type="similarity_score_threshold", search_kwargs={"score_threshold":score_threshold,"k":top_k}) 

# 增强：集成检索器和重排序
    # 单一retriever
    # compression_retriever = ContextualCompressionRetriever(base_compressor=reranker, base_retriever=vector_retriever)
    # 集成检索器retriever #
    identical_index_name = vector_retriever.vectorstore._store.index
    
    # 设置bm25的score_threshold
    identical_search_kwargs = copy.deepcopy(vector_retriever.search_kwargs)
    identical_search_kwargs.update({'score_threshold': score_threshold*100})     
    bm25_vectorstore = ElasticsearchStore(es_connection=es_connection, index_name=identical_index_name, strategy=ElasticsearchStore.BM25RetrievalStrategy())
    # bm25_retriever = bm25_vectorstore.as_retriever(search_kwargs=identical_search_kwargs)
    bm25_retriever = JqVectorStoreRetrieverWithScore(name="bm25",vectorstore=bm25_vectorstore,search_type="similarity_score_threshold",search_kwargs=identical_search_kwargs)
    
    # 不能设置id_key="source"，现在"source"只到文件名或URL。因此无法区分切片，如果指定id_key="source"，切片会被合并
    # 不设置id_key时，只会根据page_content进行Unique合并
    # /root/.virtualenvs/test/lib/python3.10/site-packages/langchain/retrievers/ensemble.py中的weighted_reciprocal_rank方法
    # ensemble_retriever = EnsembleRetriever(retrievers=[vector_retriever,bm25_retriever], weights=[0.5, 0.5],id_key="source")
    ensemble_retriever = EnsembleRetriever(retrievers=[vector_retriever,bm25_retriever], weights=[0.5, 0.5])
    compression_retriever = ContextualCompressionRetriever(base_compressor=reranker, base_retriever=ensemble_retriever)
    if not compression_retriever:
        logger.warning(f"未能获取到有效的Retriever：'{compression_retriever=}")
    else:
        retrievers=compression_retriever.base_retriever.retrievers
        message = ""
        for i,retriever in enumerate(retrievers):
            message += f" 检索器[{i+1}]{retriever.name}，检索的目标知识库为{retriever.vectorstore._store.index} "
        logger.warning(f"get_retriever方法，返回的集成检索器为：{message}")

        
    return compression_retriever

if __name__ == "__main__":
    invoke_llm_config = env_models_instance.invoke_llm_config
    input_files = [fr'/data/projects/JqChatV2/JqChat/jqcode/jq_readers/.test_files/.testinputdocs/A方案.docx'] 
    input_files += [fr'/data/projects/JqChatV2/JqChat/jqcode/jq_readers/.test_files/.testinputdocs/PPQA000_质量保证过程.doc']
    # input_files = []   
    # index_name="new_test_doc_tree_reader"
    index_name='zjk_jqesclient_test'
    compression_retriever = get_retriever(index_name=index_name,chat_on_docs_list=input_files,add_docs_list_to_kb=True) 
    # docs1 = compression_retriever.invoke("晶奇公司在哪一年获得ISO9001国际质量体系认证？")
    docs1 = compression_retriever.invoke("组织级质量保证计划审查",config=invoke_llm_config)
    docs2 = compression_retriever.invoke("各类医疗卫生机构规范化处置能力。完善重大疫情医疗废物应急处置机制",config=invoke_llm_config)
    # docs2用以测试是否返回文档确实限定在了给定的文件列表范围内,因为index_name='health'包含了很多其他的文档

    # 构建非过滤检索器
    compression_retriever.base_retriever.retrievers[0].search_kwargs={}
    compression_retriever.base_retriever.retrievers[1].search_kwargs={}
    docs3 = compression_retriever.invoke("各类医疗卫生机构规范化处置能力。完善重大疫情医疗废物应急处置机制",config=invoke_llm_config)
 
    for docs in [docs1,docs2,docs3]:
        print("&&&&&&&&&&&&&&&&&&&&&")
        print(f'共检索到{len(docs)}篇文档：') 
        for i,h in enumerate(docs):
            relevance_score = h.metadata.get("relevance_score_retriever_embedding",h.metadata.get("relevance_score_retriever_embedding",0.0))
            print(f'【{h.metadata.get("file_name",None) or h.metadata.get("source",None)}】文档片段[{i+1}](relevance_score:{relevance_score:.3f}):\n{h.page_content[:100]}')
            # print(f'文档片段[{i+1}](relevance_score:{h.metadata["relevance_score"]:.3f})') 
            print('~~~~~~~~~~~'*5)  
    print("结论：经过反复测试：文档过滤、集成检索、重排序都是Work的，但确实会有少数情况下(发生在文档相关性很低的时候)，会返回给定列表外的文档！") 
    print("建议：在reranker中增加相关性阈值过滤(如须>=0.2,已经添加了，效果很好)！确实需要严格过滤的话，可以自己再写几行代码进行过滤。")    
