"""
Platform Rewrite — Step 12: 多平台改写

公众号 / 小红书 / 抖音图文 三份专属发布包
"""
import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.llm import get_llm
from app.geo.outline import _entities_to_text
from app.geo.prompts_loader import get_system_and_user

logger = logging.getLogger(__name__)


async def rewrite_for_platform(
    platform: str,
    title: str,
    article_markdown: str,
    research: dict,
) -> dict:
    """
    按目标平台生成发布包

    Args:
        platform: "wechat" | "xiaohongshu" | "douyin"
        title: 原文标题
        article_markdown: 文章正文 Markdown
        research: 研究报告 (用于实体)

    Returns:
        平台专属 dict (结构因平台而异, 见各 prompt)
    """
    if platform == "wechat":
        return await _rewrite_wechat(title, article_markdown, research)
    elif platform == "xiaohongshu":
        return await _rewrite_xiaohongshu(title, article_markdown, research)
    elif platform == "douyin":
        return await _rewrite_douyin(title, article_markdown, research)
    else:
        # 其他平台 (知乎/今日头条) 暂时用通用 fallback
        return {
            "title": title,
            "content": article_markdown,
            "cover_suggestion": f"适用于 {platform} 的封面",
            "note": f"平台 {platform} 当前使用原文, 后续补充专属 prompt",
        }


async def _rewrite_wechat(title: str, article: str, research: dict) -> dict:
    system_body, user_template = get_system_and_user("wechat")
    entities_text = _entities_to_text(research.get("entities", {}))
    user_body = user_template.format(
        title=title,
        article_markdown=article,
        entities_text=entities_text,
    )
    raw = await _invoke(system_body, user_body)
    parsed = _safe_parse(raw)
    return parsed or _fallback("wechat", title, article)


async def _rewrite_xiaohongshu(title: str, article: str, research: dict) -> dict:
    system_body, user_template = get_system_and_user("xiaohongshu")
    entities_text = _entities_to_text(research.get("entities", {}))
    user_body = user_template.format(
        title=title,
        article_markdown=article,
        entities_text=entities_text,
    )
    raw = await _invoke(system_body, user_body)
    parsed = _safe_parse(raw)
    return parsed or _fallback("xiaohongshu", title, article)


async def _rewrite_douyin(title: str, article: str, research: dict) -> dict:
    system_body, user_template = get_system_and_user("douyin")
    entities_text = _entities_to_text(research.get("entities", {}))
    user_body = user_template.format(
        title=title,
        article_markdown=article,
        entities_text=entities_text,
    )
    raw = await _invoke(system_body, user_body)
    parsed = _safe_parse(raw)
    return parsed or _fallback("douyin", title, article)


async def _invoke(system_body: str, user_body: str) -> str:
    llm = get_llm()
    messages = [
        SystemMessage(content=system_body),
        HumanMessage(content=user_body),
    ]
    response = await llm.ainvoke(messages)
    return response.content if hasattr(response, "content") else str(response)


def _safe_parse(raw: str) -> dict | None:
    text = raw.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline > 0:
            text = text[first_newline + 1:]
        if text.endswith("```"):
            text = text[:-3].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return None
    return None


def _fallback(platform: str, title: str, article: str) -> dict:
    if platform == "wechat":
        return {
            "title": title,
            "summary": article[:100] + "...",
            "geo_description": article[:200],
            "content": article,
            "cover_suggestion": "微信封面建议（fallback）",
        }
    elif platform == "xiaohongshu":
        return {
            "titles": [title],
            "content": article[:1500],
            "tags": ["#AI", "#自媒体"],
            "cover_suggestion": "小红书封面建议（fallback）",
        }
    elif platform == "douyin":
        return {
            "title": title,
            "cover_text": title[:15],
            "grid_copies": [{"index": i, "role": f"图{i}", "text": "..."} for i in range(1, 10)],
            "caption": article[:400],
            "tags": ["#AI"],
            "cover_suggestion": "抖音封面（fallback）",
        }
    return {"title": title, "content": article}