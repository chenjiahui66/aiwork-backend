"""
工作流节点辅助函数 — LangGraph 节点包装层

关键设计:
- LangGraph 节点签名: async def (state) -> dict(state updates)
- 但前端需要流式 token,所以用 LangGraph 的 get_stream_writer() push 自定义事件
- chain.py 用 graph.astream(state, stream_mode=["updates", "custom"]) 同时拿 state 变更和自定义事件

事件协议(前端不变):
- node_start
- token
- node_end
"""
import logging

from langchain_core.prompts import ChatPromptTemplate
from langgraph.config import get_stream_writer

from app.core.llm import get_llm

logger = logging.getLogger(__name__)


async def make_llm_node(
    node_id: str,
    node_label: str,
    system_prompt: str,
    user_prompt: str,
    output_key: str,
) -> dict:
    """
    LangGraph 节点函数 — 跑一次 LLM 调用,把结果写进 state 的 output_key。

    同时通过 LangGraph 的 stream writer 向前端 emit:
    - node_start
    - token (每个 chunk)
    - node_end (含完整输出)

    返回:
        dict {output_key: "完整 LLM 输出"} — LangGraph 用来更新 state
    """
    writer = get_stream_writer()

    # 1) 节点开始事件
    writer({"type": "node_start", "node_id": node_id, "node_label": node_label})

    # 2) LLM 流式调用
    llm = get_llm()
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", user_prompt),
    ])
    chain = prompt | llm

    full = ""
    async for chunk in chain.astream({}):
        if chunk.content:
            full += chunk.content
            writer({"type": "token", "content": chunk.content})

    # 3) 节点结束事件(含完整产物)
    writer({
        "type": "node_end",
        "node_id": node_id,
        "node_label": node_label,
        "output": full,
        "output_key": output_key,
    })

    # 4) 返回 state 更新
    return {output_key: full}