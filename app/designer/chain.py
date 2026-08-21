"""
设计助手主流程 — 纯 LLM 生成 prompt,用户拿 prompt 去别的工具
"""
import logging
from typing import AsyncIterator

from app.core.llm import get_llm
from app.designer import prompts as designer_prompts

logger = logging.getLogger(__name__)


async def generate(
    design_type: str,
    subject: str,
    style: str = "",
    color: str = "",
    scene: str = "",
    extra: str = "",
) -> AsyncIterator[dict]:
    """
    生成图像 prompt(流式)

    yield:
    - {"type": "sources", "sources": [], "meta": {...}}
    - {"type": "token", "content": "..."}
    - {"type": "done"}
    """
    if not subject.strip():
        yield {"type": "error", "message": "主题/产品描述不能为空"}
        return

    try:
        prompt_template = designer_prompts.get_prompt(design_type)
    except ValueError as e:
        yield {"type": "error", "message": str(e)}
        return

    # 元信息
    type_meta = designer_prompts.PROMPT_REGISTRY.get(design_type, {})
    yield {
        "type": "sources",
        "sources": [],
        "meta": {
            "design_type": design_type,
            "design_label": type_meta.get("label", design_type),
            "ratio": type_meta.get("ratio", "1:1"),
            "extra_hint": type_meta.get("extra_hint", ""),
        },
    }

    llm = get_llm()
    chain = prompt_template | llm

    logger.info(
        "🎨 设计 prompt: type=%s subject=%s",
        design_type, subject[:60],
    )

    try:
        async for chunk in chain.astream({
            "design_type": type_meta.get("label", design_type),
            "subject": subject,
            "style": style or "不限",
            "color": color or "由 AI 决定",
            "scene": scene or "通用",
            "extra": extra or "无",
        }):
            if chunk.content:
                yield {"type": "token", "content": chunk.content}
        yield {"type": "done"}
    except Exception as e:
        logger.exception("设计 prompt 生成失败")
        yield {"type": "error", "message": f"生成失败: {e}"}