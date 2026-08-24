"""
Image Prompt — Step 10-11: 配图 prompt + 封面 prompt

MiniMax 无图像模型 — 只生成可复制的 prompt, 留给 Midjourney/Stable Diffusion
"""
import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.llm import get_llm
from app.geo.outline import _entities_to_text
from app.geo.prompts_loader import get_system_and_user

logger = logging.getLogger(__name__)


async def generate_image_prompts(
    title: str,
    platform: str,
    outline: dict,
    research: dict,
) -> dict:
    """
    生成配图 prompt

    Returns:
        {
          "cover_prompt": "...",
          "illustration_prompts": [
            {"section": "...", "info": "...", "prompt": "..."},
            ...
          ]
        }
    """
    system_body, user_template = get_system_and_user("image_prompt")

    outline_json = json.dumps(outline, ensure_ascii=False, indent=2)
    entities_text = _entities_to_text(research.get("entities", {}))

    user_body = user_template.format(
        title=title,
        platform=platform,
        outline_json=outline_json,
        entities_text=entities_text,
    )

    llm = get_llm()
    messages = [
        SystemMessage(content=system_body),
        HumanMessage(content=user_body),
    ]

    logger.info("🎨 Generating image prompts: %s", title)
    response = await llm.ainvoke(messages)
    raw = response.content if hasattr(response, "content") else str(response)

    parsed = _safe_parse(raw)
    if parsed is None:
        logger.warning("Image prompt parse failed, raw: %s", raw[:200])
        return _fallback(title)

    logger.info("✅ Image prompts: cover + %d illustrations",
                len(parsed.get("illustration_prompts", [])))
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


def _fallback(title: str) -> dict:
    return {
        "cover_prompt": f"Minimalist cover illustration for '{title}', modern flat design, --ar 16:9 --style raw",
        "illustration_prompts": [
            {
                "section": "第1章",
                "info": "核心概念可视化",
                "prompt": f"Concept illustration for '{title}' chapter 1, flat design, --ar 16:9 --style raw",
            },
        ],
    }