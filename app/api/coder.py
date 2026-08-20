"""
代码助手接口
"""
import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.models.schemas import CodeRequest
from app.coder import chain

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/coder", tags=["coder"])


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/analyze")
async def analyze(req: CodeRequest) -> StreamingResponse:
    """代码分析(流式 SSE)"""

    async def stream():
        try:
            async for event in chain.analyze(
                task=req.task,
                code=req.code,
                language=req.language,
                target_language=req.target_language,
            ):
                yield _sse(event)
        except Exception as e:
            logger.exception("代码助手异常")
            yield _sse({"type": "error", "message": f"服务异常: {e}"})

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/options")
async def list_options() -> dict:
    """前端下拉框用 — 返回任务和语言列表"""
    from app.coder.prompts import (
        PROMPT_REGISTRY,
        SUPPORTED_LANGUAGES,
        TASK_LABELS,
    )
    return {
        "tasks": [
            {"code": k, "label": v}
            for k, v in TASK_LABELS.items()
        ],
        "languages": SUPPORTED_LANGUAGES,
    }