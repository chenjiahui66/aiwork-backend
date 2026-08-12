"""
对话接口 - RAG 流式输出(SSE)
"""
import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.models.schemas import ChatRequest
from app.rag import chain

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])


def _sse_format(data: dict) -> str:
    """SSE 协议格式: data: <json>\n\n"""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/chat")
async def chat(req: ChatRequest) -> StreamingResponse:
    """
    RAG 流式对话 - Server-Sent Events

    事件类型:
    - {"type": "sources", "sources": [...]}
    - {"type": "token", "content": "..."}
    - {"type": "done"}
    - {"type": "error", "message": "..."}
    """

    async def event_stream():
        try:
            async for event in chain.chat(
                question=req.question,
                top_k=req.top_k,
                history=req.history,
            ):
                yield _sse_format(event)
        except Exception as e:
            logger.exception("RAG 调用失败")
            yield _sse_format(
                {"type": "error", "message": f"服务异常: {str(e)}"}
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # 关闭 nginx 缓冲(部署时如果套 nginx)
        },
    )