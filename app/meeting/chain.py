"""
会议助手主流程 — 输入是会议转写文本,输出是结构化产物
"""
import logging
from typing import AsyncIterator

from app.core.llm import get_llm
from app.meeting import prompts as meeting_prompts

logger = logging.getLogger(__name__)


async def process(task: str, transcript: str) -> AsyncIterator[dict]:
    """
    处理会议内容(流式)

    yield:
    - {"type": "sources", "sources": [], "meta": {...}}
    - {"type": "token", "content": "..."}
    - {"type": "done"}
    """
    if not transcript.strip():
        yield {"type": "error", "message": "会议内容为空"}
        return

    try:
        prompt_template = meeting_prompts.get_prompt(task)
    except ValueError as e:
        yield {"type": "error", "message": str(e)}
        return

    # 文本过长保护
    MAX_CHARS = 25000
    truncated = False
    if len(transcript) > MAX_CHARS:
        transcript = transcript[:MAX_CHARS]
        truncated = True
        logger.warning("会议内容过长, 已截断到 %d 字符", MAX_CHARS)

    yield {
        "type": "sources",
        "sources": [],
        "meta": {
            "task": task,
            "task_label": meeting_prompts.TASK_LABELS.get(task, task),
            "char_count": len(transcript),
            "truncated": truncated,
        },
    }

    llm = get_llm()
    chain = prompt_template | llm

    logger.info(
        "🎙️ 会议助手: task=%s chars=%d", task, len(transcript),
    )

    try:
        async for chunk in chain.astream({"transcript": transcript}):
            if chunk.content:
                yield {"type": "token", "content": chunk.content}
        yield {"type": "done"}
    except Exception as e:
        logger.exception("会议处理失败")
        yield {"type": "error", "message": f"生成失败: {e}"}