"""
智能写作接口 — 跟 chat.py 一个套路, SSE 输出
"""
import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.models.schemas import WriterRequest
from app.writer import chain

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/writer", tags=["writer"])


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/generate")
async def generate(req: WriterRequest) -> StreamingResponse:
    """
    流式生成写作内容
    事件: token / done / error  (写作不检索, 没 sources 事件)
    """

    async def stream():
        try:
            async for event in chain.generate(
                write_type=req.write_type,
                inputs=req.inputs,
                history=req.history,
            ):
                yield _sse(event)
        except Exception as e:
            logger.exception("写作接口异常")
            yield _sse({"type": "error", "message": f"服务异常: {e}"})

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/types")
async def list_types() -> dict:
    """前端下拉框用 — 返回支持的写作类型"""
    from app.writer.prompts import PROMPT_REGISTRY
    return {
        "types": list(PROMPT_REGISTRY.keys()),
        "descriptions": {
            "email": "邮件撰写",
            "weekly_report": "周报生成",
            "marketing": "营销文案",
            "speech": "演讲稿",
        },
    }