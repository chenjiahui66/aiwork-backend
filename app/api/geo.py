"""
GEO 内容智能体 API — 跟 chat/writer 一个套路: SSE 流式输出 + 一次完整 JSON
"""
import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.geo import orchestrator
from app.geo.prompts_loader import validate_all
from app.models.schemas import GEOHealthResponse, GEORequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/geo", tags=["geo"])


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/generate")
async def generate(req: GEORequest) -> StreamingResponse:
    """
    流式生成 GEO 内容包
    事件:
    - {"type": "step", "step": N, "name": "...", "status": "start|done"}
    - {"type": "final", "data": {...完整 GEO 结果...}}
    - {"type": "done"}
    - {"type": "error", "message": "..."}
    """

    async def stream():
        try:
            async for event in orchestrator.generate_geo_content(
                title=req.title,
                platform_name=req.platform,
                style=req.style,
            ):
                yield _sse(event)
        except Exception as e:
            logger.exception("GEO 接口异常")
            yield _sse({"type": "error", "message": f"服务异常: {e}"})

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/health")
async def health() -> GEOHealthResponse:
    """健康检查 — 验证 prompt 文件加载"""
    try:
        validate_all()
        prompts_loaded = 8
    except Exception as e:
        logger.warning("Prompt validation failed: %s", e)
        prompts_loaded = 0

    llm_ok = True
    try:
        from app.core.llm import get_llm  # noqa
        get_llm()
    except Exception:
        llm_ok = False

    return GEOHealthResponse(
        prompts_loaded=prompts_loaded,
        llm_available=llm_ok,
    )