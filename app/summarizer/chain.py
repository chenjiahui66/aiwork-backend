"""
摘要主流程 —— 跟 writer/chain.py 几乎一样,纯 LLM, 不查向量库。

关键设计:
- 支持两种入口: 1) 直接传 text, 2) 传 doc_id (从已入库文档读)
- doc_id 入口会先在 FAISS 里把所有同 doc_id 的 chunk 拼起来,再摘要
"""
import logging
from typing import AsyncIterator

from app.core.llm import get_llm
from app.rag import vector_store
from app.summarizer import prompts

logger = logging.getLogger(__name__)


def _build_full_text_from_doc(doc_id: str) -> str:
    """
    从向量库捞出某文档的所有 chunk, 按 chunk_index 顺序拼成完整文本
    (复用 RAG 已有的 FAISS, 不重新读文件, 保证摘要的是入库内容而不是原始文件)
    """
    all_chunks = vector_store.get_chunks_by_doc_id(doc_id)
    if not all_chunks:
        raise ValueError(f"找不到文档 {doc_id} 或文档没有切片")

    # 按 chunk_index 排序, 避免乱序
    all_chunks.sort(
        key=lambda d: int(d.metadata.get("chunk_index", 0))
    )
    full_text = "\n\n".join(doc.page_content for doc in all_chunks)
    return full_text


async def summarize(
    text: str | None = None,
    doc_id: str | None = None,
    summary_type: str = "short",
) -> AsyncIterator[dict]:
    """
    生成摘要 (流式)

    yield 事件:
    - {"type": "sources", "meta": {...}}  - 一次: 输入元信息(文本长度/文档名)
    - {"type": "token", "content": "..."}  - 多次: LLM 增量输出
    - {"type": "done"}

    用法二选一:
    - summarize(text="...", summary_type="short")
    - summarize(doc_id="abc123", summary_type="key_points")
    """
    # 1. 解析输入
    if text is None and doc_id is None:
        yield {"type": "error", "message": "必须传 text 或 doc_id 之一"}
        return

    try:
        prompt_template = prompts.get_prompt(summary_type)
    except ValueError as e:
        yield {"type": "error", "message": str(e)}
        return

    if doc_id:
        try:
            text = _build_full_text_from_doc(doc_id)
            # 拿文件名(从第一个 chunk metadata 里取)
            chunks = vector_store.get_chunks_by_doc_id(doc_id)
            filename = chunks[0].metadata.get("filename", "未知文档") if chunks else "未知文档"
        except Exception as e:
            logger.exception("读取文档失败")
            yield {"type": "error", "message": f"读取文档失败: {e}"}
            return
    else:
        filename = None

    # 2. 文本太长保护 (防 token 超限)
    # 粗略按字符算, 1 中文 ≈ 1 token, 留 2000 给 prompt + 输出
    MAX_CHARS = 30000
    truncated = False
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS]
        truncated = True
        logger.warning("文本过长, 已截断到 %d 字符", MAX_CHARS)

    # 3. 先把元信息抛给前端
    yield {
        "type": "sources",
        "sources": [],  # 摘要不检索, 留空占位
        "meta": {
            "char_count": len(text),
            "truncated": truncated,
            "doc_id": doc_id,
            "filename": filename,
            "summary_type": summary_type,
        },
    }

    # 4. 调 LLM (流式)
    llm = get_llm()
    chain = prompt_template | llm

    logger.info(
        "📝 摘要调用: type=%s chars=%d doc_id=%s",
        summary_type, len(text), doc_id or "N/A",
    )

    try:
        async for chunk in chain.astream({"text": text}):
            if chunk.content:
                yield {"type": "token", "content": chunk.content}
        yield {"type": "done"}
    except Exception as e:
        logger.exception("摘要生成失败")
        yield {"type": "error", "message": f"生成失败: {e}"}