"""
工作流接口
"""
import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.models.schemas import WorkflowRunRequest
from app.workflow import chain

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/workflow", tags=["workflow"])


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/list")
async def list_workflows() -> dict:
    """列出所有预置工作流"""
    from app.workflow.flows import WORKFLOWS
    return {
        "workflows": [
            {
                "code": k,
                "name": v["name"],
                "description": v["description"],
                "icon": v["icon"],
                "input_label": v["input_label"],
                "input_placeholder": v["input_placeholder"],
                "input_min_length": v["input_min_length"],
                "steps": v["steps"],
            }
            for k, v in WORKFLOWS.items()
        ]
    }


@router.post("/run")
async def run(req: WorkflowRunRequest) -> StreamingResponse:
    """运行工作流(流式 SSE)"""

    async def stream():
        try:
            async for event in chain.run_workflow(req.workflow_code, req.input):
                yield _sse(event)
        except Exception as e:
            logger.exception("工作流运行异常")
            yield _sse({"type": "error", "message": f"服务异常: {e}"})

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )