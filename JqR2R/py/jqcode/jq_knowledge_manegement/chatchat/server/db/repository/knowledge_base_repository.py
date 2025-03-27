from jqcode.jq_knowledge_manegement.chatchat.server.db.models.knowledge_base_model import (
    KnowledgeBaseModel,
    KnowledgeBaseSchema,
)
from jqcode.jq_knowledge_manegement.chatchat.server.db.session import with_session

@with_session
def add_kb_to_db(session, kb_name, kb_info, vs_type, embed_model):
    # 创建知识库实例
    kb = (
        session.query(KnowledgeBaseModel)
        .filter(KnowledgeBaseModel.kb_name.ilike(kb_name))
        .first()
    )
    if not kb:
        kb = KnowledgeBaseModel(
            kb_name=kb_name, kb_info=kb_info, vs_type=vs_type, embed_model=embed_model
        )
        session.add(kb)
    else:  # update kb with new vs_type and embed_model
        kb.kb_info = kb_info
        kb.vs_type = vs_type
        kb.embed_model = embed_model
    return True


def add_kb_to_es(kb_name, kb_info, vs_type, embed_model):
    from jqcode.jq_docstores.jq_es_client import JqEsClient
    jq_es_client = JqEsClient()   
    try:
        # 创建知识库索引并添加元数据
        index_store = jq_es_client.create_doc_index(
            index_name=kb_name,
            description=kb_info,
            index_creator=''
        )
        
        if index_store is None:
            print(f"Failed to create or access index {kb_name}")
            return False
        
        # 如果需要，这里可以添加更多的操作，比如添加文档等
        # 例如：
        # jq_es_client.chunks_indexing_from_input_dir_or_files(
        #     current_user=current_user,
        #     index_name=kb_name,
        #     description=kb_info,
        #     input_dir="path/to/documents"
        # )
        
        print(f"Knowledge base {kb_name} created or updated successfully")
        return True
    except Exception as e:
        print(f"Error adding knowledge base to Elasticsearch: {e}")
        return False


@with_session
def list_kbs_from_db(session, min_file_count: int = -1):
    kbs = (
        session.query(KnowledgeBaseModel)
        .filter(KnowledgeBaseModel.file_count > min_file_count)
        .all()
    )
    kbs = [KnowledgeBaseSchema.model_validate(kb) for kb in kbs]
    return kbs



@with_session
def kb_exists(session, kb_name):
    kb = (
        session.query(KnowledgeBaseModel)
        .filter(KnowledgeBaseModel.kb_name.ilike(kb_name))
        .first()
    )
    status = True if kb else False
    return status


@with_session
def load_kb_from_db(session, kb_name):
    kb = (
        session.query(KnowledgeBaseModel)
        .filter(KnowledgeBaseModel.kb_name.ilike(kb_name))
        .first()
    )
    if kb:
        kb_name, vs_type, embed_model = kb.kb_name, kb.vs_type, kb.embed_model
    else:
        kb_name, vs_type, embed_model = None, None, None
    return kb_name, vs_type, embed_model


def load_kb_from_es(kb_name):
    vs_type = 'es'
    embed_model = 'bce-embedding-base_v1'
    from jqcode.jq_knowledge_manegement.chatchat.server.knowledge_base.utils import list_kbs_from_es
    all_kbs_from_es = list_kbs_from_es()
    if kb_name in all_kbs_from_es:
        return kb_name, vs_type, embed_model
    else:
        return None, vs_type, embed_model
    
 
@with_session
def delete_kb_from_db(session, kb_name):
    kb = (
        session.query(KnowledgeBaseModel)
        .filter(KnowledgeBaseModel.kb_name.ilike(kb_name))
        .first()
    )
    if kb:
        session.delete(kb)
    return True


@with_session
def get_kb_detail(session, kb_name: str) -> dict:
    kb: KnowledgeBaseModel = (
        session.query(KnowledgeBaseModel)
        .filter(KnowledgeBaseModel.kb_name.ilike(kb_name))
        .first()
    )
    if kb:
        return {
            "kb_name": kb.kb_name,
            "kb_info": kb.kb_info,
            "vs_type": kb.vs_type,
            "embed_model": kb.embed_model,
            "file_count": kb.file_count,
            "create_time": kb.create_time,
        }
    else:
        return {}
