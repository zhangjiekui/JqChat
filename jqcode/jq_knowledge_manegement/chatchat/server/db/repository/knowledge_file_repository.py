from typing import Dict, List

from jqcode.jq_knowledge_manegement.chatchat.server.db.models.knowledge_base_model import KnowledgeBaseModel
from jqcode.jq_knowledge_manegement.chatchat.server.db.models.knowledge_file_model import (
    FileDocModel,
    KnowledgeFileModel,
)
from jqcode.jq_knowledge_manegement.chatchat.server.db.session import with_session
from jqcode.jq_knowledge_manegement.chatchat.server.knowledge_base.utils import KnowledgeFile


from jqcode.jq_agent.c0_init_env_models import env_models_instance

from elasticsearch import Elasticsearch

@with_session
def list_file_num_docs_id_by_kb_name_and_file_name(
    session,
    kb_name: str,
    file_name: str,
) -> List[int]:
    """
    列出某知识库某文件对应的所有Document的id。
    返回形式：[str, ...]
    """
    doc_ids = (
        session.query(FileDocModel.doc_id)
        .filter_by(kb_name=kb_name, file_name=file_name)
        .all()
    )
    return [int(_id[0]) for _id in doc_ids]


@with_session
def list_docs_from_db(
    session,
    kb_name: str,
    file_name: str = None,
    metadata: Dict = {},
) -> List[Dict]:
    """
    列出某知识库某文件对应的所有Document。
    返回形式：[{"id": str, "metadata": dict}, ...]
    """
    docs = session.query(FileDocModel).filter(FileDocModel.kb_name.ilike(kb_name))
    if file_name:
        docs = docs.filter(FileDocModel.file_name.ilike(file_name))
    for k, v in metadata.items():
        docs = docs.filter(FileDocModel.meta_data[k].as_string() == str(v))

    return [{"id": x.doc_id, "metadata": x.metadata} for x in docs.all()]





from typing import List, Dict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def list_docs_from_es(
    kb_name: str,
    file_name: str,
    metadata: Dict = {},
    top_k: int = 10000
) -> List[Dict]:
    """
    从ES中,列出某知识库某文件对应的所有Document。
    返回形式：[{"id": str, "metadata": dict}, ...]
    """
    es = env_models_instance.get_es_connection()
    
    file_name = str(file_name)
    
    # 构建一个更精确的查询
    query = {
        "bool": {
            "must": [
                {
                    "bool": {
                        "should": [
                            {"term": {"file_path.keyword": file_name}},
                            {"term": {"file_name.keyword": file_name}},
                            {"term": {"source.keyword": file_name}},
                            {"term": {"metadata.file_name.keyword": file_name}},
                            {"term": {"metadata.source.keyword": file_name}}
                        ],
                        "minimum_should_match": 1
                    }
                }
            ]
        }
    }
    
    # 如果提供了额外的元数据，将其添加到查询中
    for key, value in metadata.items():
        query["bool"]["must"].append({"term": {f"metadata.{key}.keyword": value}})
    
    logger.info(f"Query: {query}")
    
    try:
        response = es.search(
            index=kb_name,
            body={
                "query": query,
                "_source": True
            },
            size=top_k
        )
        
        logger.info(f"Elasticsearch response: {response}")
        
        results = []
        for hit in response['hits']['hits']:
            result = {
                "id": hit['_id'],
                "metadata": hit['_source']
            }
            if 'content' in hit['_source']:
                result['content'] = hit['_source']['content']
            results.append(result)
        
        logger.info(f"Number of results: {len(results)}")
        return results
    except Exception as e:
        logger.error(f"Error during Elasticsearch query: {e}")
        return []

# # 使用示例
# results = list_docs_from_es("create1", "附件2+芜湖市信息化项目方案建议书编制提纲.docx")
# results = list_docs_from_es("create1", "OCR接口性能报告.docx")
# results = list_docs_from_es("create1", "测试文本.txt")

@with_session
def delete_docs_from_db(
    session,
    kb_name: str,
    file_name: str = None,
) -> List[Dict]:
    """
    删除某知识库某文件对应的所有Document，并返回被删除的Document。
    返回形式：[{"id": str, "metadata": dict}, ...]
    """
    docs = list_docs_from_db(kb_name=kb_name, file_name=file_name)
    query = session.query(FileDocModel).filter(FileDocModel.kb_name.ilike(kb_name))
    if file_name:
        query = query.filter(FileDocModel.file_name.ilike(file_name))
    query.delete(synchronize_session=False)
    session.commit()
    return docs


@with_session
def add_docs_to_db(session, kb_name: str, file_name: str, doc_infos: List[Dict]):
    """
    将某知识库某文件对应的所有Document信息添加到数据库。
    doc_infos形式:[{"id": str, "metadata": dict}, ...]
    """
    # ! 这里会出现doc_infos为None的情况，需要进一步排查
    if doc_infos is None:
        print(
            "输入的server.db.repository.knowledge_file_repository.add_docs_to_db的doc_infos参数为None"
        )
        return False
    for d in doc_infos:
        obj = FileDocModel(
            kb_name=kb_name,
            file_name=file_name,
            doc_id=d["id"],
            meta_data=d["metadata"],
        )
        session.add(obj)
    return True


@with_session
def count_files_from_db(session, kb_name: str) -> int:
    return (
        session.query(KnowledgeFileModel)
        .filter(KnowledgeFileModel.kb_name.ilike(kb_name))
        .count()
    )


def list_files_from_es(kb_name: str, search_text: str = None) -> list:
    es = env_models_instance.get_es_connection()
    
    if search_text:
        query = {
            "query": {
                "match": {
                    "text": {
                        "query": search_text,
                        "fuzziness": "AUTO"
                    }
                }
            },
            "_source": ["metadata.file_name"],
            "size": 10000
        }
    else:
        query = {
            "query": {
                "match_all": {}
            },
            "_source": ["metadata.file_name"],
            "size": 10000
        }

    try: 
        result = es.search(index=kb_name, body=query)
        print(f"Total hits: {result['hits']['total']['value']}")
        docs = [hit["_source"]["metadata"]["file_name"] for hit in result["hits"]["hits"]]
        # print(f"Extracted file names: {docs}")
    except Exception as e:
        print(f"An error occurred: {e}")
        docs = []
    
    return docs

# 使用示例：
# 列出所有文件
# all_files = list_files_from_es("create1")

# # 搜索包含特定文本的文件
# specific_files = list_files_from_es("create1", "OCR")
# pass

@with_session
def add_file_to_db(
    session,
    kb_file: KnowledgeFile,
    docs_count: int = 0,
    custom_docs: bool = False,
    doc_infos: List[Dict] = [],  # 形式：[{"id": str, "metadata": dict}, ...]
):
    kb = session.query(KnowledgeBaseModel).filter_by(kb_name=kb_file.kb_name).first()
    if kb:
        # 如果已经存在该文件，则更新文件信息与版本号
        existing_file: KnowledgeFileModel = (
            session.query(KnowledgeFileModel)
            .filter(
                KnowledgeFileModel.kb_name.ilike(kb_file.kb_name),
                KnowledgeFileModel.file_name.ilike(kb_file.filename),
            )
            .first()
        )
        mtime = kb_file.get_mtime()
        size = kb_file.get_size()

        if existing_file:
            existing_file.file_mtime = mtime
            existing_file.file_size = size
            existing_file.docs_count = docs_count
            existing_file.custom_docs = custom_docs
            existing_file.file_version += 1
        # 否则，添加新文件
        else:
            new_file = KnowledgeFileModel(
                file_name=kb_file.filename,
                file_ext=kb_file.ext,
                kb_name=kb_file.kb_name,
                document_loader_name=kb_file.document_loader_name,
                text_splitter_name=kb_file.text_splitter_name or "SpacyTextSplitter",
                file_mtime=mtime,
                file_size=size,
                docs_count=docs_count,
                custom_docs=custom_docs,
            )
            kb.file_count += 1
            session.add(new_file)
        add_docs_to_db(
            kb_name=kb_file.kb_name, file_name=kb_file.filename, doc_infos=doc_infos
        )
    return True


@with_session
def delete_file_from_db(session, kb_file: KnowledgeFile):
    existing_file = (
        session.query(KnowledgeFileModel)
        .filter(
            KnowledgeFileModel.file_name.ilike(kb_file.filename),
            KnowledgeFileModel.kb_name.ilike(kb_file.kb_name),
        )
        .first()
    )
    if existing_file:
        session.delete(existing_file)
        delete_docs_from_db(kb_name=kb_file.kb_name, file_name=kb_file.filename)
        session.commit()

        kb = (
            session.query(KnowledgeBaseModel)
            .filter(KnowledgeBaseModel.kb_name.ilike(kb_file.kb_name))
            .first()
        )
        if kb:
            kb.file_count -= 1
            session.commit()
    return True


@with_session
def delete_files_from_db(session, knowledge_base_name: str):
    session.query(KnowledgeFileModel).filter(
        KnowledgeFileModel.kb_name.ilike(knowledge_base_name)
    ).delete(synchronize_session=False)
    session.query(FileDocModel).filter(
        FileDocModel.kb_name.ilike(knowledge_base_name)
    ).delete(synchronize_session=False)
    kb = (
        session.query(KnowledgeBaseModel)
        .filter(KnowledgeBaseModel.kb_name.ilike(knowledge_base_name))
        .first()
    )
    if kb:
        kb.file_count = 0

    session.commit()
    return True


@with_session
def file_exists_in_db(session, kb_file: KnowledgeFile):
    existing_file = (
        session.query(KnowledgeFileModel)
        .filter(
            KnowledgeFileModel.file_name.ilike(kb_file.filename),
            KnowledgeFileModel.kb_name.ilike(kb_file.kb_name),
        )
        .first()
    )
    return True if existing_file else False


def file_exists_in_es(kb_name: str, filename: str) -> dict:
    es = env_models_instance.get_es_connection()
    # 构建搜索查询
    query = {
        "query": {
            "bool": {
                "must": [
                    {"term": {"kb_name": kb_name}},
                    {"term": {"filename.keyword": filename}}
                ]
            }
        },
        "size": 1  # 我们只需要知道是否存在,所以只返回一个结果
    }
    
    # 执行搜索
    try:
        result = es.search(index="your_index_name", body=query)
        
        # 检查是否有匹配的文档
        if result['hits']['total']['value'] > 0:
            return True
        else:
            return False
    except Exception as e:
        print(f"Error searching Elasticsearch: {str(e)}")
        return False

# @lyq 这里转换后的文件存在问题
# No document found with filename '厦门市智慧民政一体化平台项目建设方案V1.4【晶奇】.doc' in index 'fileconvert'
def get_file_detail(kb_name: str, filename: str) -> dict:
    es = env_models_instance.get_es_connection()
    filename =str(filename)

    query = {
        "query": {
            "match": {
                "metadata.file_name.keyword": filename
            }
        }
    }

    try:
        result = es.search(index=kb_name, body=query)
        # print(f"Query result: {result}")

        if result['hits']['total']['value'] > 0:
            source = result['hits']['hits'][0]['_source']
            docs_count = len(result['hits']['hits'])
            metadata = source.get('metadata', {})
            return {
                "kb_name": kb_name,
                "file_name": metadata.get('file_name'),
                "file_ext": metadata.get('file_type'),
                "file_version": metadata.get('file_version'),
                "document_loader": 'JqkjSimpleDirectoryReader',
                "text_splitter": 'JqkjDocTreeTokenTextSplitter',
                "create_time": metadata.get('creation_date'),
                "file_mtime": metadata.get('last_modified_date'),
                "file_size": metadata.get('file_size'),
                "custom_docs": metadata.get('custom_docs'),
                "docs_count": docs_count,
                "source": metadata.get('source'),
                "original_source": metadata.get('original_source_jq'),
                "file_path": metadata.get('file_path')
            }
        else:
            print(f"No document found with filename '{filename}' in index '{kb_name}'")
            return {}
    except Exception as e:
        print(f"An error occurred: {e};{metadata=}")
        return {}

# kb_name = 'create1'
# filename = '测试文本.txt'
# result = get_file_detail(kb_name, filename)
# print(f"Final result: {result}")