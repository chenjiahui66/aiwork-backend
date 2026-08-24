"""
Article Writer — Step 8-9: 文章生成 + GEO 优化

输入: 大纲 + 研究报告 + 实体
输出: Markdown 文章正文
"""
import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.llm import get_llm
from app.geo.outline import _entities_to_text
from app.geo.prompts_loader import get_system_and_user

logger = logging.getLogger(__name__)


async def write_article(
    title: str,
    platform: str,
    style: str,
    outline: dict,
    research: dict,
) -> str:
    """
    生成文章正文 (Markdown 格式)

    Returns:
        Markdown 文本
    """
    system_body, user_template = get_system_and_user("article")

    outline_json = json.dumps(outline, ensure_ascii=False, indent=2)
    entities_text = _entities_to_text(research.get("entities", {}))

    user_body = user_template.format(
        title=title,
        platform=platform,
        style=style,
        outline_json=outline_json,
        entities_text=entities_text,
    )

    llm = get_llm()
    messages = [
        SystemMessage(content=system_body),
        HumanMessage(content=user_body),
    ]

    logger.info("✍️ Writing article: %s, platform=%s, style=%s", title, platform, style)
    response = await llm.ainvoke(messages)
    raw = response.content if hasattr(response, "content") else str(response)

    article = raw.strip()
    # 去掉 ```markdown 包装
    if article.startswith("```markdown"):
        article = article[len("```markdown"):].lstrip()
    elif article.startswith("```"):
        # 通用 ```xxx 包装
        first_newline = article.find("\n")
        if first_newline > 0:
            article = article[first_newline + 1:]
    if article.endswith("```"):
        article = article[:-3].rstrip()

    logger.info("✅ Article written: %d chars", len(article))
    return article