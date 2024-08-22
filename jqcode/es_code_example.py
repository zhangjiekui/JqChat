
#直接使用DictExporter和DictImporter会存在问题，所以使用YAML Import/Export作为中转
#参照https://anytree.readthedocs.io/en/latest/tricks/yaml.html 
import yaml
import shortuuid 
from anytree.exporter import DictExporter
from anytree.importer import DictImporter
from anytree import RenderTree

from jqcode.jq_agent.c0_init_env_models import env_models_instance
from jqcode.jq_readers.jqkj_readers import JqkjDocxReader

anytree_dict_exporter = DictExporter()
anytree_dict_importer = DictImporter()
es_connection = env_models_instance.get_es_connection()
files_index = "files_on_es"



input_files = [fr'/data/projects/JqChatV2/JqChat/jqcode/jq_readers/.test_files/.testinputdocs/A方案.docx'] 
input_files += [fr'/data/projects/JqChatV2/JqChat/jqcode/jq_readers/.test_files/.testinputdocs/PPQA000_质量保证过程.doc'] 

if not es_connection.indices.exists(index=files_index):
    es_connection.indices.create(index=files_index)
index_ids = []
for file in input_files:
    print("=====上传======"*5)                    
    jq_file_reader = JqkjDocxReader(file_path=file)                
    doc = jq_file_reader.load()[0]
    if doc:
        _metadata = doc.metadata

        df_table_list_jq = _metadata.pop('df_table_list_jq',None)
        file_doc_object_jq = _metadata.pop('file_doc_object_jq',None)
        doc_tree = _metadata.pop('file_doc_tree_jq',None)

        doc_tree_dict = anytree_dict_exporter.export(doc_tree)
        doc_tree_yaml = yaml.dump(doc_tree_dict, default_flow_style=False)        
        
        document_dict = {"metadata":_metadata,"text":doc.text,"doc_tree_yaml":doc_tree_yaml,"file_path":file}
        # doc_id = shortuuid.uuid()
        doc_id = doc.doc_id
        index_result = es_connection.index(index=files_index,id=doc_id,document=document_dict)
        _doc_id = index_result.body['_id']
        index_ids.append(doc_id)
        print(f"in:{doc_id}   out:{_doc_id}")

for index_id in index_ids:
   print("======下载====="*5)  
   result = es_connection.get(index=files_index, id=index_id)
   print(result.body['_id'],result.body['_source']['file_path'])
   doc_tree_yqml = result.body['_source']['doc_tree_yaml']
   doc_tree_dict = yaml.load(doc_tree_yqml, Loader=yaml.Loader)  
   doc_tree = anytree_dict_importer.import_(doc_tree_dict)
   print(RenderTree(doc_tree,maxlevel=2))



# endregion 测试插入整个文档，为父子文档做技术准备,顺便测试JqkjDocxReader
# !!!上面的代码不要删除，以后要用!!!