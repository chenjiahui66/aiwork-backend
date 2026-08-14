"""
Dump / search the FAISS vector store (Chroma 兼容目录).

Usage:
    .venv\Scripts\python.exe tools\dump_vector_db.py                          # 全部文档+chunk 列表
    .venv\Scripts\python.exe tools\dump_vector_db.py --doc-id <doc_id>        # 单个文档的全部 chunk
    .venv\Scripts\python.exe tools\dump_vector_db.py --query "试用期"        # 检索某个问题
    .venv\Scripts\python.exe tools\dump_vector_db.py --query "x" --k 3       # 只取 top-3
    .venv\Scripts\python.exe tools\dump_vector_db.py --show-vectors          # 同时打印 512 维向量

输出格式: 人眼友好 + 可 grep.  无色板依赖, 任何终端都能看.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 让脚本能 import app.* (项目根加入 sys.path)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402
from app.core.llm import get_embeddings  # noqa: E402
from app.rag.vector_store import (  # noqa: E402
    INDEX_NAME,
    get_vector_store,
    list_documents,
    similarity_search,
)


# ---------- 复用: 把 Document 列表(带 score) 渲染成人看的 ----------

def _render_chunk(doc, *, score=None) -> str:
    meta = doc.metadata or {}
    head = (
        f"  chunk_id={meta.get('chunk_id', '?')}  "
        f"doc={meta.get('doc_id', '?')}#{meta.get('chunk_index', '?')}  "
        f"file={meta.get('filename', '?')}  "
    )
    if score is not None:
        head += f"score={score:.4f} (L2)  "
    head += f"chars={len(doc.page_content)}"
    body = doc.page_content.strip().replace("\n", "\n    ")
    return f"{head}\n    {body}"


def _hr(title: str) -> str:
    line = "=" * 70
    return f"\n{line}\n {title}\n{line}"


# ---------- 子命令对应的函数 ----------

def cmd_dump_all() -> None:
    persist_dir = settings.chroma_path
    print(_hr(f"VECTOR STORE @ {persist_dir}  (index_name={INDEX_NAME})"))

    docs = list_documents()
    if not docs:
        print("\n[空] 向量库没有任何文档. 上传一个试试:")
        print("    curl -F file=@demo.pdf http://127.0.0.1:8001/api/upload\n")
        return

    print(f"\n[{len(docs)} 个文档]")
    for d in docs:
        print(f"  - doc_id={d['doc_id']}")
        print(f"    filename    = {d['filename']}")
        print(f"    chunk_count = {d['chunk_count']}")
        print(f"    upload_time = {d['upload_time'] or '(unknown)'}")

    print(f"\n[全部 chunk]")
    try:
        store = get_vector_store()
        docs_list = list(store.docstore._dict.values())
    except Exception as e:
        print(f"  [读取失败] {e}")
        return

    # 按 (doc_id, chunk_index) 排序
    docs_list.sort(key=lambda d: (
        d.metadata.get("doc_id", ""),
        d.metadata.get("chunk_index", 0),
    ))
    for i, doc in enumerate(docs_list, 1):
        if doc.metadata.get("_init"):
            continue
        print(f"\n--- [{i}] ---")
        print(_render_chunk(doc))


def cmd_dump_doc(doc_id: str) -> None:
    print(_hr(f"过滤 doc_id={doc_id}"))
    docs = list_documents()
    target = next((d for d in docs if d["doc_id"] == doc_id), None)
    if not target:
        print(f"\n[NOT FOUND] doc_id={doc_id}")
        print("\n现有 doc_id 列表:")
        for d in docs:
            print(f"  - {d['doc_id']}  ({d['filename']})")
        return

    print(f"\nfilename={target['filename']}  chunk_count={target['chunk_count']}")
    try:
        store = get_vector_store()
        # 直接过滤 docstore
        matched = [
            d for d in store.docstore._dict.values()
            if d.metadata.get("doc_id") == doc_id and not d.metadata.get("_init")
        ]
    except Exception as e:
        print(f"  [读取失败] {e}")
        return

    matched.sort(key=lambda d: d.metadata.get("chunk_index", 0))
    for i, doc in enumerate(matched, 1):
        print(f"\n--- chunk #{i} ---")
        print(_render_chunk(doc))


def cmd_search(query: str, k: int, *, show_vectors: bool) -> None:
    print(_hr(f"检索: \"{query}\"  (top_k={k})"))

    # 直接复用 rag.chain 里的 retrieval 路径
    try:
        hits = similarity_search(query=query, top_k=k)
    except Exception as e:
        print(f"[检索失败] {e}")
        return

    if not hits:
        print("\n[无命中] 可能原因: 向量库为空 / query 和库内容语义差距太大")
        return

    print(f"\n[{len(hits)} 命中]")
    for rank, (doc, score) in enumerate(hits, 1):
        print(f"\n--- #{rank} ---")
        print(_render_chunk(doc, score=score))
        if show_vectors:
            # 取该 chunk 的向量
            emb = get_embeddings()
            v = emb.embed_query(doc.page_content)
            v_str = "[" + ", ".join(f"{x:.4f}" for x in v[:16]) + ", ... (共 512 维)]"
            print(f"  vector: {v_str}")


# ---------- 入口 ----------

def main() -> int:
    p = argparse.ArgumentParser(
        description="dump / search AiWork FAISS vector store",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--doc-id", help="只看某个文档的全部 chunk")
    p.add_argument("--query", help="用自然语言查询, 返回 top-k 命中")
    p.add_argument("--k", type=int, default=5, help="--query 模式下的 top_k (默认 5)")
    p.add_argument("--show-vectors", action="store_true",
                   help="(只在 --query 时)同时打印每个 chunk 的 embedding 头 16 维")
    args = p.parse_args()

    if args.doc_id:
        cmd_dump_doc(args.doc_id)
    elif args.query:
        cmd_search(args.query, args.k, show_vectors=args.show_vectors)
    else:
        cmd_dump_all()
    return 0


if __name__ == "__main__":
    sys.exit(main())
