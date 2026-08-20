"""
摘要接口 —— 两个入口: 纯文本 / 已入库文档
"""
import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.models.schemas import DocSummaryRequest, TextSummaryRequest
from app.summarizer import chain

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/summarizer", tags=["summarizer"])


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/text")
async def summarize_text(req: TextSummaryRequest) -> StreamingResponse:
    """纯文本摘要 (用户粘贴一段文字进来)"""

    async def stream():
        try:
            async for event in chain.summarize(
                text=req.text, summary_type=req.summary_type
            ):
                yield _sse(event)
        except Exception as e:
            logger.exception("文本摘要异常")
            yield _sse({"type": "error", "message": f"服务异常: {e}"})

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/document")
async def summarize_document(req: DocSummaryRequest) -> StreamingResponse:
    """从知识库里挑一篇已入库的文档生成摘要"""

    async def stream():
        try:
            async for event in chain.summarize(
                doc_id=req.doc_id, summary_type=req.summary_type
            ):
                yield _sse(event)
        except Exception as e:
            logger.exception("文档摘要异常")
            yield _sse({"type": "error", "message": f"服务异常: {e}"})

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/types")
async def list_types() -> dict:
    """前端下拉框用 — 返回支持的摘要类型"""
    from app.summarizer.prompts import PROMPT_REGISTRY
    return {
        "types": list(PROMPT_REGISTRY.keys()),
        "descriptions": {
            "short": "短摘要(1-3 句)",
            "key_points": "要点列表(3-7 条)",
            "tldr": "TL;DR(≤100 字)",
        },
    }