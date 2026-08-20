"""
代码助手主流程 — 5 个任务: explain / refactor / comment / debug / translate
"""
import logging
from typing import AsyncIterator

from app.core.llm import get_llm
from app.coder import prompts as coder_prompts

logger = logging.getLogger(__name__)


async def analyze(
    task: str,
    code: str,
    language: str,
    target_language: str | None = None,
) -> AsyncIterator[dict]:
    """
    代码分析 (流式)

    yield 事件:
    - {"type": "sources", "sources": [], "meta": {...}}
    - {"type": "token", "content": "..."}
    - {"type": "done"}
    """
    if not code.strip():
        yield {"type": "error", "message": "代码为空"}
        return

    try:
        prompt_template = coder_prompts.get_prompt(task)
    except ValueError as e:
        yield {"type": "error", "message": str(e)}
        return

    # 构造 prompt 输入
    prompt_input: dict = {"code": code, "language": language}
    if task == "translate":
        if not target_language:
            yield {"type": "error", "message": "翻译任务必须传 target_language"}
            return
        prompt_input["source_language"] = language
        prompt_input["target_language"] = target_language

    # 文本过长保护
    MAX_CHARS = 20000
    truncated = False
    if len(code) > MAX_CHARS:
        code = code[:MAX_CHARS]
        prompt_input["code"] = code
        truncated = True

    # 元信息
    yield {
        "type": "sources",
        "sources": [],
        "meta": {
            "task": task,
            "language": language,
            "target_language": target_language,
            "code_lines": code.count("\n") + 1,
            "code_chars": len(code),
            "truncated": truncated,
        },
    }

    llm = get_llm()
    chain = prompt_template | llm

    logger.info(
        "💻 代码助手: task=%s lang=%s→%s chars=%d",
        task, language, target_language or "N/A", len(code),
    )

    try:
        async for chunk in chain.astream(prompt_input):
            if chunk.content:
                yield {"type": "token", "content": chunk.content}
        yield {"type": "done"}
    except Exception as e:
        logger.exception("代码分析失败")
        yield {"type": "error", "message": f"生成失败: {e}"}