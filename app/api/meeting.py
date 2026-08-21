"""
会议助手接口
"""
import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.models.schemas import MeetingRequest
from app.meeting import chain

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/meeting", tags=["meeting"])


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/process")
async def process(req: MeetingRequest) -> StreamingResponse:
    """处理会议内容(流式 SSE)"""

    async def stream():
        try:
            async for event in chain.process(
                task=req.task,
                transcript=req.transcript,
            ):
                yield _sse(event)
        except Exception as e:
            logger.exception("会议处理异常")
            yield _sse({"type": "error", "message": f"服务异常: {e}"})

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/options")
async def list_options() -> dict:
    """前端下拉框用"""
    from app.meeting.prompts import PROMPT_REGISTRY, TASK_LABELS
    return {
        "tasks": [
            {"code": k, "label": v}
            for k, v in TASK_LABELS.items()
        ],
    }