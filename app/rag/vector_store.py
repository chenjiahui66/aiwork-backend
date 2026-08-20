"""
Vector store wrapper - FAISS (local persistent)

Chroma 0.5 需要 MSVC 编译, Windows 上没装就挂.
改用 FAISS: 纯 C++ 实现, 有 Windows 预编译包, 体积小, 速度快.

设计:
- 全局单例 FAISS index, 持久化到 settings.chroma_path(路径复用)
- 每个 Document 用 metadata.doc_id 标识属于哪个文档
- Chunk ID 格式: "{doc_id}::{chunk_index}"
- 检索时返回 (Document, score), score 是 L2 距离(越小越相似)
"""
import logging
import pickle
import shutil
from pathlib import Path
from typing import Any

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from app.core.config import settings
from app.core.llm import get_embeddings

logger = logging.getLogger(__name__)

# 复用 settings.chroma_path 作为持久化目录(避免引入新配置)
INDEX_NAME = "aiwork_kb"


def get_vector_store() -> FAISS:
    """Get FAISS instance (singleton, persistent)."""
    persist_dir = settings.chroma_path

    # 如果本地已有 index, 加载
    index_file = persist_dir / f"{INDEX_NAME}.faiss"
    pkl_file = persist_dir / f"{INDEX_NAME}.pkl"

    if index_file.exists() and pkl_file.exists():
        try:
            return FAISS.load_local(
                str(persist_dir),
                get_embeddings(),
                index_name=INDEX_NAME,
                allow_dangerous_deserialization=True,
            )
        except Exception as e:
            logger.warning("加载 FAISS index 失败, 重新创建: %s", e)

    # 首次: 创建空 index
    return FAISS.from_documents(
        documents=[Document(page_content="__init__", metadata={"_init": True})],
        embedding=get_embeddings(),
    )


def save_vector_store(store: FAISS) -> None:
    """Persist FAISS index to disk."""
    persist_dir = settings.chroma_path
    persist_dir.mkdir(parents=True, exist_ok=True)
    store.save_local(str(persist_dir), index_name=INDEX_NAME)
    logger.info("FAISS index saved to %s", persist_dir)


def add_chunks(chunks: list[Document], doc_id: str) -> int:
    """
    Add chunks to vector store.

    Returns the number of chunks added.
    """
    if not chunks:
        return 0

    # 给每个 chunk 补 metadata + 生成稳定 ID
    for idx, chunk in enumerate(chunks):
        chunk.metadata["doc_id"] = doc_id
        chunk.metadata["chunk_index"] = idx
        chunk.metadata["chunk_id"] = f"{doc_id}::{idx}"

    # 加载或创建 store
    store = get_vector_store()

    # 如果是空 store(只有 __init__), 用 from_texts 重新建
    if hasattr(store, "docstore") and len(store.docstore._dict) == 1:
        # 移除占位 doc
        first_id = list(store.docstore._dict.keys())[0]
        if store.docstore._dict[first_id].metadata.get("_init"):
            # 用真实 chunks 重建
            store = FAISS.from_documents(
                documents=chunks,
                embedding=get_embeddings(),
            )
            save_vector_store(store)
            logger.info("✅ First batch, created new index with %d chunks", len(chunks))
            return len(chunks)

    # 否则合并
    new_store = FAISS.from_documents(documents=chunks, embedding=get_embeddings())
    store.merge_from(new_store)
    save_vector_store(store)

    logger.info("✅ Added %d chunks (doc_id=%s), total now %d",
                len(chunks), doc_id, len(store.docstore._dict))
    return len(chunks)


def similarity_search(
    query: str,
    top_k: int | None = None,
    doc_id: str | None = None,
) -> list[tuple[Document, float]]:
    """
    Similarity search.

    Returns: [(Document, score), ...]  score is L2 distance (lower = more similar)
    """
    k = top_k or settings.retrieval_top_k
    store = get_vector_store()

    # FAISS 本身不支持 metadata 过滤, 我们在结果上后过滤
    results_with_scores = store.similarity_search_with_score(query, k=k * 3 if doc_id else k)

    if doc_id:
        # 过滤 + 截断到 top_k
        filtered = [
            (doc, score) for doc, score in results_with_scores
            if doc.metadata.get("doc_id") == doc_id
        ][:k]
        return filtered

    return results_with_scores[:k]


def delete_document(doc_id: str) -> int:
    """
    Delete all chunks of a document.

    Returns number of chunks deleted.
    """
    persist_dir = settings.chroma_path
    index_file = persist_dir / f"{INDEX_NAME}.faiss"
    pkl_file = persist_dir / f"{INDEX_NAME}.pkl"

    if not (index_file.exists() and pkl_file.exists()):
        return 0

    store = FAISS.load_local(
        str(persist_dir),
        get_embeddings(),
        index_name=INDEX_NAME,
        allow_dangerous_deserialization=True,
    )

    # 找出要删的 IDs
    all_ids = list(store.docstore._dict.keys())
    ids_to_delete = []
    for doc_id_key in all_ids:
        doc = store.docstore._dict[doc_id_key]
        if doc.metadata.get("doc_id") == doc_id:
            ids_to_delete.append(doc_id_key)

    if not ids_to_delete:
        logger.warning("doc_id=%s 在向量库中找不到", doc_id)
        return 0

    store.delete(ids_to_delete)
    save_vector_store(store)

    logger.info("✅ Deleted doc_id=%s (%d chunks)", doc_id, len(ids_to_delete))
    return len(ids_to_delete)


def list_documents() -> list[dict]:
    """
    List all unique documents in the vector store.

    Returns: [{doc_id, filename, chunk_count, upload_time}]
    """
    persist_dir = settings.chroma_path
    pkl_file = persist_dir / f"{INDEX_NAME}.pkl"

    if not pkl_file.exists():
        return []

    try:
        with open(pkl_file, "rb") as f:
            data = pickle.load(f)
    except Exception as e:
        logger.warning("读 index 失败: %s", e)
        return []

    # data 是 (docstore, index_to_docstore_id)
    docstore = data[0]
    metadatas = [doc.metadata for doc in docstore._dict.values()]

    # 按 doc_id 聚合
    grouped: dict[str, dict] = {}
    for m in metadatas:
        if m.get("_init"):
            continue
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

    # 从 upload_dir 取上传时间(简化: 用文件 mtime 最新的作为 fallback)
    upload_time = ""
    if settings.upload_path.exists():
        files = [f for f in settings.upload_path.iterdir() if f.is_file() and not f.name.startswith(".")]
        if files:
            upload_time = str(int(max(f.stat().st_mtime for f in files)))

    for item in grouped.values():
        item["upload_time"] = upload_time

    return list(grouped.values())


def get_chunks_by_doc_id(doc_id: str) -> list[Document]:
    """
    取出某个 doc_id 的所有 chunk (按 chunk_index 顺序由调用方排序)。

    摘要模块需要这个 —— 把一篇文档的所有片段拼起来再摘要。
    """
    persist_dir = settings.chroma_path
    pkl_file = persist_dir / f"{INDEX_NAME}.pkl"

    if not pkl_file.exists():
        return []

    try:
        with open(pkl_file, "rb") as f:
            data = pickle.load(f)
        docstore = data[0]
    except Exception as e:
        logger.warning("读 index 失败: %s", e)
        return []

    chunks = [
        doc for doc in docstore._dict.values()
        if doc.metadata.get("doc_id") == doc_id
    ]
    return chunks


def reset_vector_store() -> None:
    """Danger: wipe the vector store (for testing)."""
    p = settings.chroma_path
    if p.exists():
        shutil.rmtree(p)
        p.mkdir(parents=True, exist_ok=True)
        logger.warning("⚠️ Vector store wiped: %s", p)