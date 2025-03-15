from jqcode.jq_readers.jqkj_readers import JqkjSimpleDirectoryReader
from jqcode.jq_agent.c0_init_env_models import env_models_instance
from langchain.schema import Document as LcDocument

from langchain_graphrag.indexing import TextUnitExtractor
# from langchain_graphrag.indexing.graph_generation import EntityRelationshipExtractor
# 修改原始文件/root/.virtualenvs/test/lib/python3.10/site-packages/langchain_graphrag/indexing/graph_generation/entity_relationship_extraction/extractor.py
# 在上面的EntityRelationshipExtractor中增加了batch方法
from langchain_graphrag_code_test.jqkj_er_extractor import EntityRelationshipExtractor
from langchain_graphrag.indexing.graph_generation import EntityRelationshipDescriptionSummarizer
from langchain_graphrag.indexing.graph_generation import GraphsMerger,GraphGenerator

from jqcode.jq_utils.logger import jqkj_logger

logger = jqkj_logger(__file__).get_logger()
doc_tree_spiltter = env_models_instance.doc_tree_spiltter
llm = env_models_instance.chat_model

def get_chunked_documents_from_file_directory(dir:str,input_files:str=None, overwrite_existing_converted_files=False,required_exts=['.doc','.docx','.pdf','.txt','.py'],exclude_hidden=False):
    # 构造晶奇文件读取器，读取目录中的文件
    simple_reader = JqkjSimpleDirectoryReader(input_dir=dir,input_files=input_files, 
                                              overwrite_existing_converted_files=overwrite_existing_converted_files,
                                              required_exts=required_exts,
                                              exclude_hidden=exclude_hidden)
    documents = simple_reader.load_data()
    logger.warning(f'Loaded {len(documents)} documents from {dir}:')
    for idx, doc in enumerate(documents):
        logger.warning(f'  ==原始文档[{idx+1}]:  {doc.metadata.get("source",doc.metadata.get("original_source_jq",""))}\n         转换=>   {doc.metadata.get("original_source_converted_jq",doc.metadata.get("file_path",""))}')
    
    # 使用文档树分割器，将文档分割成切片（树节点）
    tree_nodes = doc_tree_spiltter.get_nodes_from_documents(documents)
    # 将切片（树节点）转换成LangChain格式的文档
    chunked_documents = [LcDocument(page_content=node.text,metadata=node.metadata) for node in tree_nodes]
    logger.warning(f'Splits {len(documents)} documents into {len(chunked_documents)} chunks.')

    return chunked_documents

def get_df_text_units_from_file_directory(dir:str,input_files:str=None, overwrite_existing_converted_files=False,required_exts=['.doc','.docx','.pdf','.txt','.py'],exclude_hidden=False):    
    # 构造晶奇文件读取器，读取目录中的文件，得到LxDocument格式的文档
    simple_reader = JqkjSimpleDirectoryReader(input_dir=dir,input_files=input_files, 
                                              overwrite_existing_converted_files=overwrite_existing_converted_files,
                                              required_exts=required_exts,
                                              exclude_hidden=exclude_hidden)
    documents = simple_reader.load_data()
    logger.warning(f'Loaded {len(documents)} documents from {dir}:')
    for idx, doc in enumerate(documents):
        logger.warning(f'  ==原始文档[{idx+1}]:  {doc.metadata.get("source",doc.metadata.get("original_source_jq",""))}\n         转换=>   {doc.metadata.get("original_source_converted_jq",doc.metadata.get("file_path",""))}')
    
    # 得到LcDocument格式的文档
    documents = [doc.to_langchain_format() for doc in documents]

    text_unit_extractor = TextUnitExtractor(text_splitter=doc_tree_spiltter)
    df_text_units = text_unit_extractor.run(documents)
    

    logger.warning(f'Splits {len(documents)} documents into {len(df_text_units)} text_units.')
    print("=======================df_text_units.head()=======================")
    print(df_text_units.head())
    print("=======================df_text_units.head()=======================")

    return df_text_units

file_dir = '/data/projects/JqChatV2/JqChat/langchain_graphrag_code_test/data'
# chunked_documents = get_chunked_documents_from_file_directory(file_dir)
df_text_units = get_df_text_units_from_file_directory(dir=file_dir)
files = [r"/data/projects/JqChatV2/JqChat/PPQA000_质量保证过程.docx"]
df_text_units = get_df_text_units_from_file_directory(dir=None,input_files=files)




# 修改/root/.virtualenvs/test/lib/python3.10/site-packages/langchain_graphrag/indexing/graph_generation/entity_relationship_extraction/_default_prompts.py
# 将其中的English改为Chinese(简体中文)
batch_size = 14
er_extractor = EntityRelationshipExtractor.build_default(llm=llm)
summarizer = EntityRelationshipDescriptionSummarizer.build_default(llm=llm)
graphs_merger = GraphsMerger()
text_unit_graphs = er_extractor.batch(df_text_units[0:100],batch_size=batch_size)
# text_unit_graphs = er_extractor.batch(df_text_units,batch_size=batch_size)
for index, g in enumerate(text_unit_graphs):
    print("---------------------------------")
    print(f"图谱: {index+1}")
    print(f"节点数量 - {len(g.nodes)}")
    print(f"边数量 - {len(g.edges)}")
    print(f"{g.nodes()=}")
    print(f"{g.edges()=}")
    print("---------------------------------")

graph_generator = GraphGenerator(
    er_extractor=er_extractor,
    graphs_merger=GraphsMerger(),
    er_description_summarizer=summarizer,
)

graphs = graph_generator.run(df_text_units[0:100])
for graph in graphs:
    print(f"Number of nodes - {len(graph.nodes)}")
    print(f"Number of edges - {len(graph.edges)}")

er_summarized_graph = graphs[1]
for node in er_summarized_graph.nodes(data=True):
    print('-----------------')
    print(node)


for edge in er_summarized_graph.edges(data=True):
    print('-----------------')
    print(edge)



