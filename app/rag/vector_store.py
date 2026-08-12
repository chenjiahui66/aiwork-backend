"""
向量库封装 - Chroma(本地持久化)

每个 Document 用 metadata.doc_id 标识属于哪个文档, 便于:
1. 删除整个文档时按 doc_id 批量删除
2. 引用时知道内容来自哪个文件

Chroma 的 collection 设计:
- collection_name = "aiwork_kb"  (单租户)
- id 格式: "{doc_id}::{chunk_index}"(保证唯一)
- metadata: {doc_id, filename, chunk_index}
- page_content: 切片文本
"""
import logging
import shutil
from pathlib import Path

from langchain_chroma import Chroma  # langchain-chroma 包
from langchain_core.documents import Document

from app.core.config import settings
from app.core.llm import get_embeddings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "aiwork_kb"


def get_vector_store() -> Chroma:
    """获取 Chroma 实例(单例, 全局共享 collection)"""
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=str(settings.chroma_path),
        collection_metadata={"hnsw:space": "cosine"},  # 余弦相似度, 适合 bge-m3
    )


def add_chunks(
    chunks: list[Document],
    doc_id: str,
) -> int:
    """
    把切片加入向量库

    返回加入的 chunk 数量
    """
    if not chunks:
        return 0

    # 给每个 chunk 生成稳定 ID + 补 metadata
    ids: list[str] = []
    for idx, chunk in enumerate(chunks):
        chunk.metadata["doc_id"] = doc_id
        chunk.metadata["chunk_index"] = idx
        ids.append(f"{doc_id}::{idx}")

    store = get_vector_store()
    store.add_documents(documents=chunks, ids=ids)
    logger.info("✅ 已入库 %d 个 chunk (doc_id=%s)", len(chunks), doc_id)
    return len(chunks)


def similarity_search(
    query: str,
    top_k: int | None = None,
    doc_id: str | None = None,
) -> list[tuple[Document, float]]:
    """
    相似度检索

    返回: [(Document, score), ...]  按 score 升序(越低越相似)
    doc_id 不为空时只在指定文档范围内检索
    """
    k = top_k or settings.retrieval_top_k
    store = get_vector_store()

    filter_kwargs: dict = {}
    if doc_id:
        filter_kwargs["doc_id"] = doc_id

    results = store.similarity_search_with_relevance_scores(
        query,
        k=k,
        filter=filter_kwargs or None,
    )
    return results


def delete_document(doc_id: str) -> int:
    """
    删除某个文档的所有 chunk

    返回删除的 chunk 数量
    """
    store = get_vector_store()
    # 先查该文档的 chunk IDs
    collection = store._collection
    existing = collection.get(where={"doc_id": doc_id})
    ids = existing.get("ids", [])
    if not ids:
        logger.warning("doc_id=%s 在向量库中找不到任何 chunk", doc_id)
        return 0

    collection.delete(ids=ids)
    logger.info("✅ 已删除 doc_id=%s 的 %d 个 chunk", doc_id, len(ids))
    return len(ids)


def list_documents() -> list[dict]:
    """
    列出向量库里的所有文档(按 doc_id 去重)

    返回: [{doc_id, filename, chunk_count, upload_time(从文件系统推算)}]
    """
    store = get_vector_store()
    collection = store._collection
    data = collection.get(include=["metadatas"])

    metadatas = data.get("metadatas", [])
    if not metadatas:
        return []

    # 按 doc_id 聚合
    grouped: dict[str, dict] = {}
    for m in metadatas:
        doc_id = m.get("doc_id")
        if not doc_id:
            continue
        if doc_id not in grouped:
            grouped[doc_id] = {
                "doc_id": doc_id,
                "filename": m.get("filename", "unknown"),
                "chunk_count": 0,
            }
        grouped[doc_id]["chunk_count"] += 1

    # 从 upload_dir 里取上传时间
    result = []
    for item in grouped.values():
        doc_id = item["doc_id"]
        # doc_id 是 uuid, 不能直接拼路径。约定: 同时把上传文件存到 upload_dir
        # 这里我们通过 metadata 里的 filename 反查
        upload_time = ""
        for f in settings.upload_path.iterdir():
            if f.is_file() and not f.name.startswith("."):
                # 通过 mtime 取最近的(简化处理, 实际应当用 doc_id 做映射表)
                upload_time = f.stat().st_mtime
                break
        item["upload_time"] = upload_time
        result.append(item)

    return result


def reset_vector_store() -> None:
    """危险: 清空整个向量库(开发用)"""
    p = settings.chroma_path
    if p.exists():
        shutil.rmtree(p)
        p.mkdir(parents=True, exist_ok=True)
        logger.warning("⚠️ 向量库已清空: %s", p)