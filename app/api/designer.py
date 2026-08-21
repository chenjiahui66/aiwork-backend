"""
设计助手接口
"""
import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.models.schemas import DesignRequest
from app.designer import chain

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/designer", tags=["designer"])


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/generate")
async def generate(req: DesignRequest) -> StreamingResponse:
    """生成设计 prompt(流式 SSE)"""

    async def stream():
        try:
            async for event in chain.generate(
                design_type=req.design_type,
                subject=req.subject,
                style=req.style,
                color=req.color,
                scene=req.scene,
                extra=req.extra,
            ):
                yield _sse(event)
        except Exception as e:
            logger.exception("设计助手异常")
            yield _sse({"type": "error", "message": f"服务异常: {e}"})

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/options")
async def list_options() -> dict:
    """前端下拉框用"""
    from app.designer.prompts import PROMPT_REGISTRY
    return {
        "design_types": [
            {
                "code": k,
                "label": v["label"],
                "ratio": v["ratio"],
                "extra_hint": v["extra_hint"],
            }
            for k, v in PROMPT_REGISTRY.items()
        ],
        "styles": [
            {"value": "", "label": "由 AI 决定"},
            {"value": "极简", "label": "极简 Minimalist"},
            {"value": "商务", "label": "商务 Professional"},
            {"value": "国风", "label": "国风 Chinese Ink"},
            {"value": "写实", "label": "写实 Photorealistic"},
            {"value": "卡通", "label": "卡通 Cartoon"},
            {"value": "抽象", "label": "抽象 Abstract"},
            {"value": "赛博朋", "label": "赛博朋克 Cyberpunk"},
        ],
        "color_palettes": [
            {"value": "", "label": "由 AI 决定"},
            {"value": "蓝白", "label": "蓝白(科技感)"},
            {"value": "暖橙黄", "label": "暖橙黄(活泼)"},
            {"value": "深绿", "label": "深绿(自然)"},
            {"value": "黑金", "label": "黑金(高端)"},
            {"value": "粉紫", "label": "粉紫(年轻女性)"},
            {"value": "黑白", "label": "黑白(经典)"},
        ],
    }