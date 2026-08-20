"""
翻译接口
"""
import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.models.schemas import TranslateRequest
from app.translator import chain

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/translator", tags=["translator"])


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/translate")
async def translate(req: TranslateRequest) -> StreamingResponse:
    """
    流式翻译 (SSE)

    事件: sources(含meta) / token / done / error
    """

    async def stream():
        try:
            async for event in chain.translate(
                text=req.text,
                target_lang=req.target_lang,
                source_lang=req.source_lang,
                domain=req.domain,
                glossary=req.glossary,
            ):
                yield _sse(event)
        except Exception as e:
            logger.exception("翻译异常")
            yield _sse({"type": "error", "message": f"服务异常: {e}"})

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/options")
async def list_options() -> dict:
    """前端下拉框用 — 返回语言列表和领域列表"""
    from app.translator.prompts import (
        PROMPT_REGISTRY,
        SUPPORTED_LANGUAGES,
    )
    return {
        "languages": SUPPORTED_LANGUAGES,
        "domains": [
            {"code": "general", "label": "通用"},
            {"code": "business", "label": "商务邮件"},
            {"code": "it", "label": "IT 技术"},
            {"code": "legal", "label": "法律合同"},
            {"code": "medical", "label": "医学"},
        ],
    }