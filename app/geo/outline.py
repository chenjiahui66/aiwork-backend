"""
Outline Builder — Step 7: 构建文章知识结构

输入: 研究报告
输出: 文章大纲 (sections + faq + conclusion)
"""
import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.llm import get_llm
from app.geo.prompts_loader import get_system_and_user

logger = logging.getLogger(__name__)


async def build_outline(
    title: str,
    platform: str,
    style: str,
    research: dict,
) -> dict:
    """
    构建文章大纲

    Returns:
        {
          "title": "优化后的标题",
          "sections": [{"heading": ..., "key_points": [...], ...}],
          "faq": [{"question": ..., "answer_hint": ...}],
          "conclusion": "..."
        }
    """
    system_body, user_template = get_system_and_user("outline")

    research_json = json.dumps(research, ensure_ascii=False, indent=2)
    entities_text = _entities_to_text(research.get("entities", {}))

    user_body = user_template.format(
        title=title,
        platform=platform,
        style=style,
        research_json=research_json,
        entities_text=entities_text,
    )

    llm = get_llm()
    messages = [
        SystemMessage(content=system_body),
        HumanMessage(content=user_body),
    ]

    logger.info("📐 Building outline for: %s", title)
    response = await llm.ainvoke(messages)
    raw = response.content if hasattr(response, "content") else str(response)

    parsed = _safe_parse_outline(raw)
    if parsed is None:
        logger.warning("Outline parse failed, raw: %s", raw[:200])
        return _fallback_outline(title)

    logger.info("✅ Outline: %d sections, %d faqs",
                len(parsed.get("sections", [])),
                len(parsed.get("faq", [])))
    return parsed


def _entities_to_text(entities: dict) -> str:
    """把 entities dict 渲染成可读的纯文本, 喂给后续模块做指代统一"""
    if not entities:
        return "（无明确实体）"
    lines = []
    for cat in ["entity", "company", "category", "related"]:
        items = entities.get(cat, [])
        if items:
            lines.append(f"- {cat.upper()}: {', '.join(items)}")
    return "\n".join(lines) if lines else "（无明确实体）"


def _safe_parse_outline(raw: str) -> dict | None:
    """鲁棒 JSON 解析"""
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


def _fallback_outline(title: str) -> dict:
    return {
        "title": title,
        "sections": [
            {
                "heading": "什么是核心问题",
                "key_points": ["问题定义", "为什么重要"],
                "questions_to_answer": [f"{title}的核心问题是什么？"],
                "evidence_needed": ["数据支撑"],
            },
            {
                "heading": "现状分析",
                "key_points": ["已有内容", "用户痛点"],
                "questions_to_answer": ["现状如何？"],
                "evidence_needed": ["案例"],
            },
        ],
        "faq": [
            {"question": f"{title}常见问题", "answer_hint": "简要回答"}
        ],
        "conclusion": "总结 + 3 条行动建议（fallback）",
    }