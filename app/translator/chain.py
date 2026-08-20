"""
翻译主流程 — 纯 LLM 生成,跟 writer/summarizer 一个套路。

支持特性:
- 领域定制 (general/business/it/legal/medical)
- 自动检测源语言 (不传 source_lang 时)
- 双语术语表(glossary, 强制某些词必须按用户给的译法)
- 流式输出
"""
import logging
from typing import AsyncIterator

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.llm import get_llm
from app.translator import prompts as translator_prompts

logger = logging.getLogger(__name__)


# 自动检测源语言的小 prompt — 单独调一次 LLM 会太贵,
# 实际让主 prompt 直接"读到啥语就是啥语, target 翻译到目标语", 效果差不多
# 这里只在用户没传 source_lang 时,在 user 模板里不写明, 让 LLM 自己判断


async def translate(
    text: str,
    target_lang: str,
    source_lang: str | None = None,
    domain: str = "general",
    glossary: dict[str, str] | None = None,
) -> AsyncIterator[dict]:
    """
    流式翻译

    yield 事件:
    - {"type": "sources", "sources": [], "meta": {...}}  - 一次: 元信息
    - {"type": "token", "content": "..."}                  - 多次: 增量输出
    - {"type": "done"}

    glossary: 术语表, 例 {"RAG": "检索增强生成", "embedding": "嵌入向量"}
    """
    if not text.strip():
        yield {"type": "error", "message": "文本为空"}
        return

    try:
        base_prompt = translator_prompts.get_prompt(domain)
    except ValueError as e:
        yield {"type": "error", "message": str(e)}
        return

    # 文本过长保护 (跟 summarizer 一样的策略)
    MAX_CHARS = 15000
    truncated = False
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS]
        truncated = True
        logger.warning("翻译文本过长, 已截断到 %d 字符", MAX_CHARS)

    # 构造完整 prompt — 把术语表塞进 system
    system_text = base_prompt.messages[0].prompt.template
    if glossary:
        glossary_lines = "\n".join(f"- {k} → {v}" for k, v in glossary.items())
        system_text += f"\n\n【强制术语表】\n以下术语必须按指定译法, 不要自行翻译:\n{glossary_lines}"

    # 用户 prompt: 没传 source_lang 时不写"从 xxx 翻译", 让 LLM 自己判断
    user_template = base_prompt.messages[1].prompt.template
    user_text = user_template.format(
        text=text,
        target_lang=target_lang,
        source_lang=source_lang or "(自动检测)",
    )

    from langchain_core.prompts import ChatPromptTemplate
    full_prompt = ChatPromptTemplate.from_messages([
        ("system", system_text),
        ("user", user_text),
    ])

    # 元信息先抛给前端
    yield {
        "type": "sources",
        "sources": [],
        "meta": {
            "char_count": len(text),
            "truncated": truncated,
            "source_lang": source_lang or "auto",
            "target_lang": target_lang,
            "domain": domain,
            "glossary_count": len(glossary) if glossary else 0,
        },
    }

    llm = get_llm()
    chain = full_prompt | llm

    logger.info(
        "🌐 翻译调用: %s→%s domain=%s chars=%d glossary=%d",
        source_lang or "auto", target_lang, domain, len(text), len(glossary or {}),
    )

    try:
        async for chunk in chain.astream({}):
            if chunk.content:
                yield {"type": "token", "content": chunk.content}
        yield {"type": "done"}
    except Exception as e:
        logger.exception("翻译失败")
        yield {"type": "error", "message": f"翻译失败: {e}"}