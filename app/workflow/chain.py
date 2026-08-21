"""
工作流主流程 — LangGraph 驱动

每个工作流是预编译的 StateGraph,这里负责:
1. 校验 workflow_code + 输入长度
2. emit workflow_meta 给前端
3. 调用 graph.astream(initial_state, stream_mode=["updates","custom"])
4. 把 LangGraph 的 stream 输出转换为前端 SSE 事件协议
"""
import logging
from typing import AsyncIterator

from app.workflow.flows import WORKFLOWS

logger = logging.getLogger(__name__)


async def run_workflow(workflow_code: str, input_text: str) -> AsyncIterator[dict]:
    """
    跑一个工作流(由 LangGraph StateGraph 驱动,流式输出每个节点的进度)。

    yield 事件(与前端协议保持不变):
    - {"type": "workflow_meta", "name", "description", "steps", "total_steps"}
    - {"type": "node_start", "node_id", "node_label"}
    - {"type": "token", "content"}
    - {"type": "node_end", "node_id", "node_label", "output", "output_key"}
    - {"type": "done", "state": {}}
    - {"type": "error", "message"}
    """
    if workflow_code not in WORKFLOWS:
        yield {"type": "error", "message": f"未知工作流: {workflow_code}"}
        return

    wf = WORKFLOWS[workflow_code]

    if not input_text.strip():
        yield {"type": "error", "message": "输入不能为空"}
        return

    if len(input_text) < wf["input_min_length"]:
        yield {
            "type": "error",
            "message": f"输入太短(至少 {wf['input_min_length']} 字符)",
        }
        return

    # 1) 元信息 — 前端先收到这个,知道有几个步骤
    yield {
        "type": "workflow_meta",
        "name": wf["name"],
        "description": wf["description"],
        "steps": wf["steps"],
        "total_steps": len(wf["steps"]),
    }

    logger.info(
        "🔧 工作流(LangGraph): %s, input_chars=%d", workflow_code, len(input_text)
    )

    # 2) 编译图(如果还没编译过,可以缓存 — 这里简单起见每次都重新编译)
    try:
        graph = wf["build_graph"]()
    except Exception as e:
        logger.exception("工作流图编译失败")
        yield {"type": "error", "message": f"工作流初始化失败: {e}"}
        return

    # 3) 初始 state — 每个工作流有自己的 state schema,都至少包含 "input"
    initial_state = {"input": input_text}

    # 4) 跑图,同时监听 state 更新 (mode="updates") 和自定义事件 (mode="custom")
    final_state = {}
    try:
        async for stream_type, payload in graph.astream(
            initial_state,
            stream_mode=["updates", "custom"],
        ):
            if stream_type == "custom":
                # 自定义事件 — node_start / token / node_end
                yield payload
            elif stream_type == "updates":
                # state 更新 — 每跑完一个节点,LangGraph 给一份 {node_name: {field: value}}
                # 我们只在结束时用 final_state 兜底
                if isinstance(payload, dict):
                    for node_updates in payload.values():
                        if isinstance(node_updates, dict):
                            final_state.update(node_updates)
    except Exception as e:
        logger.exception("工作流运行失败")
        yield {"type": "error", "message": f"运行失败: {e}"}
        return

    # 5) 完成
    yield {"type": "done", "state": final_state}