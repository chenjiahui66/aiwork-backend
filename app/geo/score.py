"""
GEO Score + AI 搜索模拟器 — Step 8.5 / 13

输入: 文章正文 + 研究报告 + 实体
输出: 总分 + 7 维度分 + 优势 + 劣势 + 优化建议 + AI 搜索模拟结果
"""
import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.llm import get_llm
from app.geo.outline import _entities_to_text
from app.geo.prompts_loader import get_system_and_user

logger = logging.getLogger(__name__)


async def score_article(
    title: str,
    platform: str,
    article_markdown: str,
    research: dict,
) -> dict:
    """
    GEO 评分 + AI 搜索模拟

    Returns:
        {
          "total_score": int,
          "dimensions": [{"name", "key", "score", "comment"}],
          "strengths": [...],
          "weaknesses": [...],
          "suggestions": [...],
          "ai_search_test": [{"question", "likelihood", "reason"}]
        }
    """
    system_body, user_template = get_system_and_user("geo_score")

    research_json = json.dumps(research, ensure_ascii=False, indent=2)
    entities_text = _entities_to_text(research.get("entities", {}))

    user_body = user_template.format(
        title=title,
        platform=platform,
        research_json=research_json,
        entities_text=entities_text,
        article_markdown=article_markdown,
    )

    llm = get_llm()
    messages = [
        SystemMessage(content=system_body),
        HumanMessage(content=user_body),
    ]

    logger.info("📊 Scoring article: %s", title)
    response = await llm.ainvoke(messages)
    raw = response.content if hasattr(response, "content") else str(response)

    parsed = _safe_parse(raw)
    if parsed is None:
        logger.warning("Score parse failed, raw: %s", raw[:200])
        return _fallback_score()

    logger.info("✅ GEO score: total=%d", parsed.get("total_score", 0))
    return parsed


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


def _fallback_score() -> dict:
    return {
        "total_score": 70,
        "dimensions": [
            {"name": "实体明确度", "key": "entity_clarity", "score": 70, "comment": "fallback"},
            {"name": "主题覆盖", "key": "topic_coverage", "score": 70, "comment": "fallback"},
            {"name": "问题覆盖", "key": "question_coverage", "score": 70, "comment": "fallback"},
            {"name": "数据支撑", "key": "data_support", "score": 70, "comment": "fallback"},
            {"name": "结构化", "key": "structure", "score": 70, "comment": "fallback"},
            {"name": "来源权威性", "key": "source_authority", "score": 70, "comment": "fallback"},
            {"name": "可验证性", "key": "verifiability", "score": 70, "comment": "fallback"},
        ],
        "strengths": ["文章已生成"],
        "weaknesses": ["评分解析失败,使用 fallback"],
        "suggestions": ["重试评分请求"],
        "ai_search_test": [
            {"question": "fallback 测试问题", "likelihood": "medium", "reason": "fallback"}
        ],
    }