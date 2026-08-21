"""
HR 助手主流程 — 跟前面模块一致套路
"""
import logging
from typing import AsyncIterator

from app.core.llm import get_llm
from app.hr import prompts as hr_prompts

logger = logging.getLogger(__name__)


async def run(task: str, inputs: dict) -> AsyncIterator[dict]:
    """
    HR 任务(流式)

    yield:
    - {"type": "sources", "sources": [], "meta": {...}}
    - {"type": "token", "content": "..."}
    - {"type": "done"}
    """
    try:
        prompt_template = hr_prompts.get_prompt(task)
    except ValueError as e:
        yield {"type": "error", "message": str(e)}
        return

    # 元信息
    yield {
        "type": "sources",
        "sources": [],
        "meta": {
            "task": task,
            "task_label": hr_prompts.TASK_LABELS.get(task, task),
            "input_keys": list(inputs.keys()),
        },
    }

    llm = get_llm()
    chain = prompt_template | llm

    logger.info("👥 HR 任务: task=%s inputs=%s", task, list(inputs.keys()))

    try:
        async for chunk in chain.astream(inputs):
            if chunk.content:
                yield {"type": "token", "content": chunk.content}
        yield {"type": "done"}
    except Exception as e:
        logger.exception("HR 任务失败")
        yield {"type": "error", "message": f"生成失败: {e}"}