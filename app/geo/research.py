"""
Research Agent — Step 1-2: 选题研究报告

输出: hotspots / faqs / gaps / opportunities / entities
基于 LLM 知识（当前版本不接实时 Web 搜索）
"""
import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.llm import get_llm
from app.geo.prompts_loader import get_system_and_user

logger = logging.getLogger(__name__)


async def run_research(title: str, platform: str, style: str) -> dict:
    """
    跑选题研究, 返回结构化报告 dict

    Args:
        title: 选题标题
        platform: 目标平台 (wechat/xiaohongshu/douyin/zhihu/toutiao)
        style: 内容风格 (professional/personal_ip/viral_analysis/story/opinion/tutorial)

    Returns:
        {
          "hotspots": [...],
          "faqs": [...],
          "gaps": [...],
          "opportunities": [...],
          "entities": {"entity": [], "company": [], "category": [], "related": []}
        }
    """
    system_body, user_template = get_system_and_user("research")

    user_body = user_template.format(title=title, platform=platform, style=style)

    llm = get_llm()
    messages = [
        SystemMessage(content=system_body),
        HumanMessage(content=user_body),
    ]

    logger.info("🔍 Research: title=%s, platform=%s, style=%s", title, platform, style)
    response = await llm.ainvoke(messages)
    raw = response.content if hasattr(response, "content") else str(response)

    # 鲁棒解析（参考 feishu bitable 的 _safe_parse_todos 思路）
    parsed = _safe_parse_research(raw)
    if parsed is None:
        logger.warning("Research parse failed, using fallback. Raw: %s", raw[:200])
        return _fallback_research(title)

    logger.info("✅ Research done: hotspots=%d, faqs=%d, entities=%d",
                len(parsed.get("hotspots", [])),
                len(parsed.get("faqs", [])),
                len(parsed.get("entities", {}).get("entity", [])))
    return parsed


def _safe_parse_research(raw: str) -> dict | None:
    """从 LLM 输出鲁棒提取 JSON"""
    text = raw.strip()

    # 去掉 ```json 包装
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline > 0:
            text = text[first_newline + 1:]
        if text.endswith("```"):
            text = text[:-3].strip()

    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试提取第一个 { 到最后一个 }
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return None
    return None


def _fallback_research(title: str) -> dict:
    """兜底研究输出（LLM 解析失败时）"""
    return {
        "hotspots": [f"基于标题「{title}」的热门方向分析（fallback）"],
        "faqs": [f"{title}的核心问题是什么？"],
        "gaps": ["现有内容同质化严重", "缺少真实案例", "缺少数据支撑"],
        "opportunities": ["加入真实案例对比", "加入成本分析", "加入操作步骤"],
        "entities": {
            "entity": [],
            "company": [],
            "category": [],
            "related": [],
        },
    }