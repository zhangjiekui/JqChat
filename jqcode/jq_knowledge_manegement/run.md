# 修改内容

## 1
/data/projects/JqChat/jqcode/jq_knowledge_manegement/chatchat/configs/_kb_config.py
```
"index_name": "test_index",
"user": "",
"password": "",
```  

改成

```
"index_name": "test",
"user": "elastic",
"password": "esnNFWQbCIspxTPGwOom",
```          

## 2
新增
/data/projects/JqChat/jqcode/jq_knowledge_manegement/chatchat/server/knowledge_base/utils.py
```
198
# 新增
elif loader_name in ["JqkjDocxReader"]:
        document_loaders_module = importlib.import_module(jqcode.jq_readers)
```

```
235
# 新增
elif loader_name == "JqkjDocxReader":
    loader_kwargs.setdefault("jq_schema", ".")
    loader_kwargs.setdefault("text_content", False)
```

