"""
数据洞察接口 — 跟之前模块一个套路,SSE 输出。
"""
import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.models.schemas import InsightQueryRequest
from app.insight import chain

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/insight", tags=["insight"])


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/query")
async def query(req: InsightQueryRequest) -> StreamingResponse:
    """
    自然语言查询 (SSE 流式)

    事件:
    - token: 流式输出阶段说明 + SQL
    - sources: 一次性,meta 里塞 SQL/columns/rows/chart(完整 ECharts option)
    - done: 完成
    - error: 出错
    """

    async def stream():
        try:
            async for event in chain.query(req.question):
                yield _sse(event)
        except Exception as e:
            logger.exception("数据洞察异常")
            yield _sse({"type": "error", "message": f"服务异常: {e}"})

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/schema")
async def get_schema() -> dict:
    """前端展示 schema 帮助用户提问"""
    from app.insight.seed_db import get_schema_description
    return {
        "schema": get_schema_description(),
        "examples": [
            "每个产品的总销售额是多少?",
            "华东和华北两个区域哪个卖得更好?",
            "近 3 个月销售趋势如何?",
            "按部门统计员工人数",
            "哪个产品的销售员最多?",
            "用户最常触发的事件类型是什么?",
        ],
    }


@router.post("/init")
async def init_db() -> dict:
    """手动触发演示数据库初始化(开发用)"""
    from app.insight import seed_db
    seed_db._ensure_seed()
    return {"status": "ok", "db_path": str(seed_db.DB_PATH)}