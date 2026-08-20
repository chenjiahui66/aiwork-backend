"""
智能写作主流程 — 跟 rag/chain.py 对比着看:

rag/chain.py:     检索 → 拼 context → 调 LLM
writer/chain.py: 接收用户输入字段 → 拼 prompt → 调 LLM   (不查向量库!)

设计要点:
- 同样流式输出(SSE), 前端 ChatQAView.vue 的打字效果代码直接复用
- 每个写作类型有不同的输入字段, 用 **kwargs 透传
- 不查向量库, 所以 prompt 里不带 {context}
"""
import logging
from typing import AsyncIterator

from langchain_core.messages import AIMessage, HumanMessage

from app.core.llm import get_llm
from app.writer import prompts

logger = logging.getLogger(__name__)


def _convert_history(history: list[dict]) -> list:
    """跟 RAG 里那份一模一样, 抄过来用就行"""
    out = []
    for h in history:
        role = h.get("role")
        content = h.get("content", "")
        if role == "user":
            out.append(HumanMessage(content=content))
        elif role == "assistant":
            out.append(AIMessage(content=content))
    return out


async def generate(
    write_type: str,
    inputs: dict,
    history: list[dict] | None = None,
) -> AsyncIterator[dict]:
    """
    流式生成写作内容

    yield 事件:
    - {"type": "token", "content": "..."}   - LLM 增量输出
    - {"type": "done"}                       - 完成
    - (写作不检索, 所以没有 sources 事件 — 前端记得适配)
    """
    try:
        prompt_template = prompts.get_prompt(write_type)
    except ValueError as e:
        yield {"type": "error", "message": str(e)}
        return

    history_messages = _convert_history(history or [])
    llm = get_llm()

    # 把 history 注入到 prompt 的 placeholder 里
    # 注意: 不同类型的 prompt, placeholder 名字可能不一样 (这里 email 类型里有)
    prompt_input = {**inputs, "chat_history": history_messages}

    chain = prompt_template | llm

    logger.info(
        "✍️ 写作调用: type=%s keys=%s history=%d",
        write_type, list(inputs.keys()), len(history_messages),
    )

    try:
        async for chunk in chain.astream(prompt_input):
            if chunk.content:
                yield {"type": "token", "content": chunk.content}
        yield {"type": "done"}
    except Exception as e:
        logger.exception("写作生成失败")
        yield {"type": "error", "message": f"生成失败: {e}"}