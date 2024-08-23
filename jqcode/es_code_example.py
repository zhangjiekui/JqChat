
#直接使用DictExporter和DictImporter会存在问题，所以使用YAML Import/Export作为中转
#参照https://anytree.readthedocs.io/en/latest/tricks/yaml.html 
import yaml
import shortuuid 
from anytree.exporter import DictExporter
from anytree.importer import DictImporter
from anytree import RenderTree
from pathlib import Path

from jqcode.jq_agent.c0_init_env_models import env_models_instance
from jqcode.jq_readers.jqkj_readers import JqkjSimpleDirectoryReader
from base64 import b64encode,b64decode

from elasticsearch import Elasticsearch, helpers

anytree_dict_exporter = DictExporter()
anytree_dict_importer = DictImporter()
es_connection = env_models_instance.get_es_connection()
files_index = "bulk_files_on_es"

if not es_connection.indices.exists(index=files_index):
    es_connection.indices.create(index=files_index)

# input_files = [fr'/data/projects/JqChatV2/JqChat/jqcode/jq_readers/.test_files/.testinputdocs/A方案.docx'] 
# input_files += [fr'/data/projects/JqChatV2/JqChat/jqcode/jq_readers/.test_files/.testinputdocs/PPQA000_质量保证过程.doc'] 

input_dir="/data/projects/JqChatV2/JqChat/jqcode/jq_readers/.test_files/.testinputdocs"
simple_reader = JqkjSimpleDirectoryReader(input_dir=input_dir, overwrite_existing_converted_files=False,required_exts=['.doc','.docx','.pdf','.txt','.py'],exclude_hidden=False)
documents = simple_reader.load_data()
reader_successed_files = [d.metadata['source'] for d in documents]

actions_list = []
es_index_doc_id_list = []
for document in documents:
    file_path = document.metadata['source']
    ext = Path(file_path).suffix
    es_index_doc_id = shortuuid.uuid()

    file_b64 = None
    with open(file_path, 'rb') as file: 
        file_data = file.read()
        file_b64 = b64encode(file_data).decode('utf-8')

    added_metadata = {"file_extension":ext,'es_index_name':files_index,"es_index_doc_id":es_index_doc_id}
    document.metadata.update(added_metadata)

    index_metadata = document.metadata
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
print("=====上传======"*5)

es_index_doc_id_list=['ZtqWHXgbEubnEEnbtkfeza', 'GNcgbhSkMS82AjckFKqHXW', 'bQvgLmxtKuRcWzwMxCCZ9m', 'DxPQC7vbEDVdAo3AmYX8Ei', 'NpM9GUf3nuwZg2R97R3QdQ', 'GmScwyhBPdf7JSUtk7zNUZ', 'bNFn6UKHuXjddWaRCVhVe4', 'KxPKLVxSAU6jFkhH5Q6Wxz', 'XxQ8AShxXse7ix6PVgbSKR']
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



# endregion 测试插入整个文档，为父子文档做技术准备,顺便测试JqkjDocxReader
# !!!上面的代码不要删除，以后要用!!!