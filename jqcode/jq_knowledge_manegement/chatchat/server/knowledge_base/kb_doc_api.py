import json
import os
import urllib
import math
from typing import Dict, List
from pathlib import Path
from fastapi import Body, File, Form, Query, UploadFile
from fastapi.responses import FileResponse
from langchain.docstore.document import Document
from sse_starlette import EventSourceResponse
from jqcode.jq_readers.backend_reader_utils.jqkj_docs_converter import convert_doc_pdf2docx_on_win_and_linux
from jqcode.jq_knowledge_manegement.chatchat.configs import (
    CHUNK_SIZE,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_VS_TYPE,
    OVERLAP_SIZE,
    SCORE_THRESHOLD,
    VECTOR_SEARCH_TOP_K,
    ZH_TITLE_ENHANCE,
    log_verbose,
    # logger,
)
from jqcode.jq_knowledge_manegement.chatchat.server.db.repository.knowledge_file_repository import get_file_detail
from jqcode.jq_knowledge_manegement.chatchat.server.knowledge_base.kb_service.base import (
    KBServiceFactory,
    get_kb_file_details,
)
from jqcode.jq_knowledge_manegement.chatchat.server.knowledge_base.model.kb_document_model import DocumentWithVSId
from jqcode.jq_knowledge_manegement.chatchat.server.knowledge_base.utils import (
    KnowledgeFile,
    files2docs_in_thread,
    get_file_path,
    list_files_from_folder,
    validate_kb_name,
)
from jqcode.jq_knowledge_manegement.chatchat.server.utils import (
    BaseResponse,
    ListResponse,
    check_embed_model,
    run_in_thread_pool,
)

from jqcode.jq_utils.logger import jqkj_logger
logger = jqkj_logger(__file__).get_logger()
from jqcode.jq_docstores.jq_es_client import JqEsClient
jq_es_client = JqEsClient()


def search_docs(
    query: str = Body("", description="用户输入", examples=["你好"]),
    knowledge_base_name: str = Body(
        ..., description="知识库名称", examples=["samples"]
    ),
    top_k: int = Body(VECTOR_SEARCH_TOP_K, description="匹配向量数"),
    score_threshold: float = Body(
        SCORE_THRESHOLD,
        description="知识库匹配相关度阈值,取值范围在0-1之间,"
        "SCORE越小,相关度越高,"
        "取到1相当于不筛选,建议设置在0.5左右",
        ge=0.0,
        le=1.0,
    ),
    file_name: str = Body("", description="文件名称,支持 sql 通配符"),
    metadata: dict = Body({}, description="根据 metadata 进行过滤，仅支持一级键"),
) -> List[Dict]:
    kb = KBServiceFactory.get_service_by_name(knowledge_base_name)
    data = []
    if kb is not None:
        if query:
            docs = kb.search_docs(query, top_k, score_threshold)
            # data = [DocumentWithVSId(**x[0].dict(), score=x[1], id=x[0].metadata.get("id")) for x in docs]
            data = [DocumentWithVSId(**x.dict(), id=x.metadata.get("id")) for x in docs]
        elif file_name or metadata:
            data = kb.list_docs(file_name=file_name, metadata=metadata)
            for d in data:
                if "vector" in d.metadata:
                    del d.metadata["vector"]
    return [x.dict() for x in data]


def list_files(knowledge_base_name: str) -> ListResponse:
    if not validate_kb_name(knowledge_base_name):
        return ListResponse(code=403, msg="Don't attack me", data=[])

    knowledge_base_name = urllib.parse.unquote(knowledge_base_name)
    kb = KBServiceFactory.get_service_by_name(knowledge_base_name)
    if kb is None:
        return ListResponse(
            code=404, msg=f"未找到知识库 {knowledge_base_name}", data=[]
        )
    else:
        all_docs = get_kb_file_details(knowledge_base_name)
        return ListResponse(data=all_docs)


def _save_files_in_thread(
    files: List[UploadFile], knowledge_base_name: str, override: bool
):
    """
    通过多线程将上传的文件保存到对应知识库目录内。
    生成器返回保存结果：{"code":200, "msg": "xxx", "data": {"knowledge_base_name":"xxx", "file_name": "xxx"}}
    """

    def save_file(file: UploadFile, knowledge_base_name: str, override: bool) -> dict:
        """
        保存单个文件。
        """
        try:
            filename = file.filename
            file_path = get_file_path(knowledge_base_name=knowledge_base_name, doc_name=filename)
            data = {"knowledge_base_name": knowledge_base_name, "file_name": filename}


            file_content = file.file.read()  # 读取上传文件的内容

            if (
                os.path.isfile(file_path)
                and override
                and os.path.getsize(file_path) == len(file_content)
            ):
                file_status = f"文件 {filename} 已存在。"
                logger.warn(file_status)


                if not filename.endswith(('.doc','pdf')):
                    return dict(code=404, msg=file_status, data=data)
            else:
                if not os.path.isdir(os.path.dirname(file_path)):
                    os.makedirs(os.path.dirname(file_path))
                with open(file_path, "wb") as f:
                    f.write(file_content)
                if not filename.endswith(('.doc','pdf')):
                    return dict(code=200, msg=f"成功上传文件 {filename}", data=data)

            if filename.endswith(('.doc','pdf')):
                docx_filename = Path(file_path).with_suffix(".docx")
                docx_file_path = get_file_path(knowledge_base_name=knowledge_base_name, doc_name=docx_filename)
                input_filepaths,original_valid_input_filepaths = convert_doc_pdf2docx_on_win_and_linux(file_path,overwrite=override)
                # if os.path.isfile(docx_file_path):
                #     if os.path.isfile(file_path):
                #         os.remove(file_path)
                data = {"knowledge_base_name": knowledge_base_name, "file_name": docx_filename}
                return dict(code=200, msg=f"成功上传文件 {filename},并且转换成了{docx_filename}", data=data)

        except Exception as e:
            msg = f"{filename} 文件上传失败，报错信息为: {e}"
            logger.error(
                f"{e.__class__.__name__}: {msg}", exc_info=e if log_verbose else None
            )
            return dict(code=500, msg=msg, data=data)

    params = [
        {"file": file, "knowledge_base_name": knowledge_base_name, "override": override}
        for file in files
    ]
    for result in run_in_thread_pool(save_file, params=params):
        yield result


# def upload_docs(
#     files: List[UploadFile] = File(..., description="上传文件，支持多文件"),
#     # file_path: str = '',
#     knowledge_base_name: str = Form(
#         ..., description="知识库名称", examples=["samples"]
#     ),
#     override: bool = Form(False, description="覆盖已有文件"),
#     to_vector_store: bool = Form(True, description="上传文件后是否进行向量化"),
#     chunk_size: int = Form(CHUNK_SIZE, description="知识库中单段文本最大长度"),
#     chunk_overlap: int = Form(OVERLAP_SIZE, description="知识库中相邻文本重合长度"),
#     zh_title_enhance: bool = Form(ZH_TITLE_ENHANCE, description="是否开启中文标题加强"),
#     docs: str = Form("", description="自定义的docs,需要转为json字符串"),
#     not_refresh_vs_cache: bool = Form(False, description="暂不保存向量库(用于FAISS)"),
#     batch_size: int = Form(5, description="批处理文件数量"),
# ) -> BaseResponse:
#     """
#     API接口:上传文件并/或向量化
#     """
#     if not validate_kb_name(knowledge_base_name):
#         return BaseResponse(code=403, msg="Don't attack me")

#     kb = KBServiceFactory.get_service_by_name(knowledge_base_name)
#     if kb is None:
#         return BaseResponse(code=404, msg=f"未找到知识库 {knowledge_base_name}")

#     docs = json.loads(docs) if docs else {}
#     failed_files = {}
#     file_names = list(docs.keys())

#     # 先将上传的文件保存到磁盘
#     for result in _save_files_in_thread(
#         files, knowledge_base_name=knowledge_base_name, override=override
#     ):
#         filename = result["data"]["file_name"]
#         if result["code"] != 200:
#             failed_files[filename] = result["msg"]

#         if filename not in file_names:
#             file_names.append(filename)

#     # from jqcode.jq_docstores.jq_es_client import JqEsClient
#     # jq_es_client = JqEsClient()
#     # 对保存的文件进行向量化
#     if to_vector_store:

#         file_path = get_file_path(knowledge_base_name=knowledge_base_name, doc_name=filename)
#         result = update_docs(
#             knowledge_base_name=knowledge_base_name,
#             file_names=file_names,
#             file_path = file_path,
#             override_custom_docs=True,
#             chunk_size=chunk_size,
#             chunk_overlap=chunk_overlap,
#             zh_title_enhance=zh_title_enhance,
#             docs=docs,
#             not_refresh_vs_cache=True,
#         )
#         failed_files.update(result.data["failed_files"])
#         # if not not_refresh_vs_cache:
#         #     kb.save_vector_store()

#     return BaseResponse(
#         code=200, msg="文件上传与向量化完成", data={"failed_files": failed_files}
#     )


def upload_docs(
    files: List[UploadFile] = File(..., description="上传文件，支持多文件"),
    knowledge_base_name: str = Form(..., description="知识库名称", examples=["samples"]),
    override: bool = Form(False, description="覆盖已有文件"),
    to_vector_store: bool = Form(True, description="上传文件后是否进行向量化"),
    chunk_size: int = Form(CHUNK_SIZE, description="知识库中单段文本最大长度"),
    chunk_overlap: int = Form(OVERLAP_SIZE, description="知识库中相邻文本重合长度"),
    zh_title_enhance: bool = Form(ZH_TITLE_ENHANCE, description="是否开启中文标题加强"),
    docs: str = Form("", description="自定义的docs,需要转为json字符串"),
    not_refresh_vs_cache: bool = Form(False, description="暂不保存向量库(用于FAISS)"),
    batch_size: int = Form(3, description="批处理文件数量"),
) -> BaseResponse:
    """
    API接口:上传文件并/或向量化
    """
    if not validate_kb_name(knowledge_base_name):
        return BaseResponse(code=403, msg="Don't attack me")

    kb = KBServiceFactory.get_service_by_name(knowledge_base_name)
    if kb is None:
        return BaseResponse(code=404, msg=f"未找到知识库 {knowledge_base_name}")

    docs = json.loads(docs) if docs else {}
    failed_files = {}
    file_names = list(docs.keys())

    # 将文件列表分批
    total_files = len(files)
    num_batches = math.ceil(total_files / batch_size)
    
    logger.warning(f"......共有{total_files=}个文件，将每次上传{batch_size=}个文件，共需{num_batches=}个批次进行处理......")
    
    # 分批处理文件
    for batch_idx in range(num_batches):
        start_idx = batch_idx * batch_size
        end_idx = min((batch_idx + 1) * batch_size, total_files)
        current_batch = files[start_idx:end_idx]

        try:
            # 处理当前批次的文件
            for result in _save_files_in_thread(
                current_batch, 
                knowledge_base_name=knowledge_base_name, 
                override=override
            ):
                filename = result["data"]["file_name"]
                if result["code"] != 200:
                    failed_files[filename] = result["msg"]

                if filename not in file_names:
                    file_names.append(filename)

            # 对当前批次的文件进行向量化
            if to_vector_store:
                for filename in file_names[start_idx:end_idx]:
                    try:
                        file_path = get_file_path(
                            knowledge_base_name=knowledge_base_name, 
                            doc_name=filename
                        )
                        result = update_docs(
                            knowledge_base_name=knowledge_base_name,
                            file_names=[filename],  # 每次只处理一个文件
                            file_path=file_path,
                            override_custom_docs=True,
                            chunk_size=chunk_size,
                            chunk_overlap=chunk_overlap,
                            zh_title_enhance=zh_title_enhance,
                            docs={k: docs[k] for k in [filename] if k in docs},
                            not_refresh_vs_cache=True,
                        )
                        if result.data and "failed_files" in result.data:
                            failed_files.update(result.data["failed_files"])
                    except Exception as e:
                        failed_files[filename] = str(e)

        except Exception as e:
            # 记录批次处理失败的信息
            for file in current_batch:
                failed_files[file.filename] = f"Batch processing error: {str(e)}"

    # 完成所有处理后保存向量存储
    if to_vector_store and not not_refresh_vs_cache:
        try:
            kb.save_vector_store()
        except Exception as e:
            return BaseResponse(
                code=500, 
                msg=f"向量存储保存失败: {str(e)}", 
                data={"failed_files": failed_files}
            )

    return BaseResponse(
        code=200, 
        msg="文件上传与向量化完成", 
        data={
            "failed_files": failed_files,
            "total_processed": total_files,
            "failed_count": len(failed_files)
        }
    )

def delete_docs(
    knowledge_base_name: str = Body(..., examples=["samples"]),
    file_names: List[str] = Body(..., examples=[["file_name.md", "test.txt"]]),
    delete_content: bool = Body(False),
    not_refresh_vs_cache: bool = Body(False, description="暂不保存向量库（用于FAISS）"),
) -> BaseResponse:
    if not validate_kb_name(knowledge_base_name):
        return BaseResponse(code=403, msg="Don't attack me")
 
    knowledge_base_name = urllib.parse.unquote(knowledge_base_name)
    kb = KBServiceFactory.get_service_by_name(knowledge_base_name)
    if kb is None:
        return BaseResponse(code=404, msg=f"未找到知识库 {knowledge_base_name}")

    failed_files = {}
    for file_name in file_names:
        if not kb.exist_doc(file_name):
            failed_files[file_name] = f"未找到文件 {file_name}"

        try:
            kb_file = KnowledgeFile(
                filename=file_name, knowledge_base_name=knowledge_base_name
            )
            kb.delete_doc(kb_file, delete_content, not_refresh_vs_cache=True)
        except Exception as e:
            msg = f"{file_name} 文件删除失败，错误信息：{e}"
            logger.error(
                f"{e.__class__.__name__}: {msg}", exc_info=e if log_verbose else None
            )
            failed_files[file_name] = msg

    if not not_refresh_vs_cache:
        kb.save_vector_store()

    return BaseResponse(
        code=200, msg=f"文件删除完成", data={"failed_files": failed_files}
    )


def update_info(
    knowledge_base_name: str = Body(
        ..., description="知识库名称", examples=["samples"]
    ),
    kb_info: str = Body(..., description="知识库介绍", examples=["这是一个知识库"]),
):
    if not validate_kb_name(knowledge_base_name):
        return BaseResponse(code=403, msg="Don't attack me")

    kb = KBServiceFactory.get_service_by_name(knowledge_base_name)
    if kb is None:
        return BaseResponse(code=404, msg=f"未找到知识库 {knowledge_base_name}")
    kb.update_info(kb_info)

    return BaseResponse(code=200, msg=f"知识库介绍修改完成", data={"kb_info": kb_info})



# # 使用示例
# result = update_info("yqli", "这个版本会在遇到问题时给出提示，而不是直接报错终止程序。同时，它仍然会尽可能地继续处理其他文件和目录。")
# print(f"Knowledge base added or updated: {result}")



def update_docs(
    knowledge_base_name: str = Body(
        ..., description="知识库名称", examples=["samples"]
    ),
    file_names: List[str] = Body(
        ..., description="文件名称，支持多文件", examples=[["file_name1", "text.txt"]]
    ),
    file_path: str = Body(
        ..., description="文件路径", examples=[""]),
    chunk_size: int = Body(CHUNK_SIZE, description="知识库中单段文本最大长度"),
    chunk_overlap: int = Body(OVERLAP_SIZE, description="知识库中相邻文本重合长度"),
    zh_title_enhance: bool = Body(ZH_TITLE_ENHANCE, description="是否开启中文标题加强"),
    override_custom_docs: bool = Body(False, description="是否覆盖之前自定义的docs"),
    docs: str = Body("", description="自定义的docs,需要转为json字符串"),
    not_refresh_vs_cache: bool = Body(False, description="暂不保存向量库用于FAISS"),
) -> BaseResponse:
    """
    更新知识库文档
    """
    file_paths = [get_file_path(knowledge_base_name=knowledge_base_name, doc_name=filename) for filename in file_names]
    result = jq_es_client.chunks_indexing_from_input_dir_or_files(
        current_user = "",
        index_name =knowledge_base_name,
        description = None,
        
        input_dir=None,
        input_files=file_paths, 
        overwrite_existing_converted_files=False,
        required_exts=['.pdf', '.doc', '.docx', '.md', '.html', '.htm', '.py', '.txt'],
        exclude_hidden=False
    )
    print(result)
    
    
    for filename in file_names:
        if not validate_kb_name(knowledge_base_name):
            return BaseResponse(code=403, msg="Don't attack me")

        kb = KBServiceFactory.get_service_by_name(knowledge_base_name)
        if kb is None:
            return BaseResponse(code=404, msg=f"未找到知识库 {knowledge_base_name}")

        failed_files = {}
        kb_files = []
        docs = json.loads(docs) if docs else {}

        file_detail = get_file_detail(kb_name=knowledge_base_name, filename=filename)
        # 如果该文件之前使用了自定义docs，则根据参数决定略过或覆盖
        if file_detail.get("custom_docs") and not override_custom_docs:
            continue
        if filename not in docs:
            try:
                kb_files.append(
                    KnowledgeFile(
                        filename=filename, knowledge_base_name=knowledge_base_name
                    )
                )
            except Exception as e:
                msg = f"加载文档 {filename} 时出错：{e}"
                logger.error(
                    f"{e.__class__.__name__}: {msg}",
                    exc_info=e if log_verbose else None,
                )
                failed_files[filename] = msg


    return BaseResponse(
        code=200, msg=f"更新文档完成", data={"failed_files": failed_files}
    )


def download_doc(
    knowledge_base_name: str = Query(
        ..., description="知识库名称", examples=["samples"]
    ),
    file_name: str = Query(..., description="文件名称", examples=["test.txt"]),
    preview: bool = Query(False, description="是：浏览器内预览；否：下载"),
):
    """
    下载知识库文档
    """
    if not validate_kb_name(knowledge_base_name):
        return BaseResponse(code=403, msg="Don't attack me")

    kb = KBServiceFactory.get_service_by_name(knowledge_base_name)
    if kb is None:
        return BaseResponse(code=404, msg=f"未找到知识库 {knowledge_base_name}")

    if preview:
        content_disposition_type = "inline"
    else:
        content_disposition_type = None

    try:
        kb_file = KnowledgeFile(
            filename=file_name, knowledge_base_name=knowledge_base_name
        )

        if os.path.exists(kb_file.filepath):
            return FileResponse(
                path=kb_file.filepath,
                filename=kb_file.filename,
                media_type="multipart/form-data",
                content_disposition_type=content_disposition_type,
            )
    except Exception as e:
        msg = f"{kb_file.filename} 读取文件失败，错误信息是：{e}"
        logger.error(
            f"{e.__class__.__name__}: {msg}", exc_info=e if log_verbose else None
        )
        return BaseResponse(code=500, msg=msg)

    return BaseResponse(code=500, msg=f"{kb_file.filename} 读取文件失败")


def recreate_vector_store(
    knowledge_base_name: str = Body(..., examples=["samples"]),
    kb_info: str = Body(..., description="知识库介绍", examples=["这是一个知识库"]),
    allow_empty_kb: bool = Body(True),
    # vs_type: str = Body(DEFAULT_VS_TYPE),
    vs_type: str = 'es',
    embed_model: str = Body(DEFAULT_EMBEDDING_MODEL),
    chunk_size: int = Body(CHUNK_SIZE, description="知识库中单段文本最大长度"),
    chunk_overlap: int = Body(OVERLAP_SIZE, description="知识库中相邻文本重合长度"),
    zh_title_enhance: bool = Body(ZH_TITLE_ENHANCE, description="是否开启中文标题加强"),
    not_refresh_vs_cache: bool = Body(False, description="暂不保存向量库（用于FAISS）"),
):
    """
    recreate vector store from the content.
    this is usefull when user can copy files to content folder directly instead of upload through network.
    by default, get_service_by_name only return knowledge base in the info.db and having document files in it.
    set allow_empty_kb to True make it applied on empty knowledge base which it not in the info.db or having no documents.
    """

    def output():
        kb = KBServiceFactory.get_service(knowledge_base_name, vs_type, embed_model, kb_info=kb_info )
        if not kb.exists() and not allow_empty_kb:
            yield {"code": 404, "msg": f"未找到知识库 ‘{knowledge_base_name}’"}
        else:
            error_msg = (
                f"could not recreate vector store because failed to access embed model."
            )
            if not kb.check_embed_model(error_msg):
                yield {"code": 404, "msg": error_msg}
            else:
                if kb.exists():
                    kb.clear_vs()
                kb.create_kb()
                files = list_files_from_folder(knowledge_base_name)
                kb_files = [(file, knowledge_base_name) for file in files]
                file_paths =[get_file_path(knowledge_base_name=knowledge_base_name, doc_name=file_name) for file_name in files]
                result_vs = jq_es_client.chunks_indexing_from_input_dir_or_files(
                                current_user = "",
                                index_name =knowledge_base_name,
                                description = kb_info,                                
                                input_dir=None,
                                input_files=file_paths, 
                                overwrite_existing_converted_files=False,
                                required_exts=['.pdf', '.doc', '.docx', '.md', '.html', '.htm', '.py', '.txt'],
                                exclude_hidden=False                            
                            )
                
                i = 0
                for file_name in files:

                    try:

                        i += 1
                        yield json.dumps(
                                {
                                    "code": 200,
                                    "msg": f"({i + 1} / {len(files)}): {file_name}",
                                    "total": len(files),
                                    "finished": i + 1,
                                    "doc": file_name,
                                },
                                ensure_ascii=False,
                            )

                    except Exception as error:
                        msg = f"添加文件‘{file_name}’到知识库‘{knowledge_base_name}’时出错：{error}。已跳过。"
                        yield json.dumps(
                                {
                                    "code": 500,
                                    "msg": msg,
                                }
                            )
                        i += 1


    return EventSourceResponse(output())
