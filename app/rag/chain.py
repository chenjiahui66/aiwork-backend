"""
RAG 核心链: 检索 + 拼 prompt + LLM 生成 + 返回引用

关键设计: 用 LCEL (LangChain Expression Language) 自己拼, 而不是用
现成的 RetrievalQA 链。原因:
1. RetrievalQA 把 source_documents 塞在 response 里, 还要手动解析
2. 我们要支持流式输出, LCEL 原生支持 streaming
3. Prompt 完全可控, 方便调优
"""
import logging
from typing import AsyncIterator

from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate

from app.core.config import settings
from app.core.llm import get_llm
from app.rag import vector_store

logger = logging.getLogger(__name__)


# ===== Prompt 模板 =====
# 角色: 企业知识助手, 必须基于资料回答, 没资料要拒答
RAG_SYSTEM_PROMPT = """你是 AiWork 平台的企业知识库助手, 帮助员工从内部文档中精准找到答案。

【核心原则】
1. 必须严格基于下方"参考资料"回答, 不要编造。
2. 如果参考资料里没有答案, 请直接说"未在知识库中找到相关信息", 不要瞎猜。
3. 回答时引用来源, 在关键结论后用 [1]、[2] 这样的角标标记, 文末附"参考资料"列出文件名。
4. 保持简洁, 用 Markdown 格式, 不要堆砌废话。

【参考资料】
{context}
"""

RAG_USER_TEMPLATE = "{question}"


def _format_docs(docs: list[Document]) -> str:
    """把检索到的文档拼成 context 字符串, 带引用编号"""
    parts = []
    for i, doc in enumerate(docs, 1):
        filename = doc.metadata.get("filename", "unknown")
        content = doc.page_content.strip()
        parts.append(f"[{i}] (来源: {filename})\n{content}")
    return "\n\n---\n\n".join(parts)


def _build_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", RAG_SYSTEM_PROMPT),
            ("placeholder", "{chat_history}"),  # 对话历史(可选)
            ("user", RAG_USER_TEMPLATE),
        ]
    )


def _convert_history(history: list[dict]) -> list:
    """把 [{role, content}, ...] 转成 LangChain 消息列表"""
    out = []
    for h in history:
        role = h.get("role")
        content = h.get("content", "")
        if role == "user":
            out.append(HumanMessage(content=content))
        elif role == "assistant":
            out.append(AIMessage(content=content))
    return out


def retrieve(question: str, top_k: int | None = None) -> list[tuple[Document, float]]:
    """只做检索, 不调 LLM(给管理/调试用)"""
    return vector_store.similarity_search(question, top_k=top_k)


async def chat(
    question: str,
    top_k: int | None = None,
    history: list[dict] | None = None,
) -> AsyncIterator[dict]:
    """
    RAG 对话(流式)

    yield 两种事件:
    1. {"type": "sources", "sources": [...]}  - 检索到的引用(一次性)
    2. {"type": "token", "content": "..."}     - LLM 增量输出(多次)
    """
    # 1. 检索
    results = vector_store.similarity_search(question, top_k=top_k)
    docs = [doc for doc, _score in results]
    scores = [score for _doc, score in results]

    # 2. 先把 sources 抛给前端(用户能立刻看到引用)
    sources_payload = [
        {
            "chunk_id": f"{doc.metadata.get('doc_id', '')}::{doc.metadata.get('chunk_index', '')}",
            "doc_id": doc.metadata.get("doc_id", ""),
            "filename": doc.metadata.get("filename", "unknown"),
            "content": doc.page_content[:500],  # 截断避免返回太大
            "score": round(score, 4),
        }
        for doc, score in results
    ]
    yield {"type": "sources", "sources": sources_payload}

    # 3. 如果一个 chunk 都没拿到, 直接拒答, 不调 LLM
    if not docs:
        yield {
            "type": "token",
            "content": "未在知识库中找到相关信息。请尝试:\n1. 换个说法\n2. 上传相关文档后再提问",
        }
        yield {"type": "done"}
        return

    # 4. 拼 prompt + 调 LLM(流式)
    context_str = _format_docs(docs)
    history_messages = _convert_history(history or [])

    prompt = _build_prompt()
    llm = get_llm()

    chain = prompt | llm

    logger.info(
        "RAG 调用: question='%s' top_k=%d 命中=%d",
        question[:80],
        top_k or settings.retrieval_top_k,
        len(docs),
    )

    async for chunk in chain.astream(
        {
            "context": context_str,
            "question": question,
            "chat_history": history_messages,
        }
    ):
        if chunk.content:
            yield {"type": "token", "content": chunk.content}

    yield {"type": "done"}