"""
飞书多维表格 API

端点:
- GET  /api/feishu/status                   是否配好
- GET  /api/feishu/tables                  列出数据表
- GET  /api/feishu/tables/{tid}/fields     列出字段定义
- POST /api/feishu/push-records            批量新增记录
- POST /api/feishu/parse-todos             从文本用 LLM 拆出结构化待办
"""
import json
import logging
import re
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException
from langchain_core.prompts import ChatPromptTemplate

from app.core.config import settings
from app.core.llm import get_llm
from app.feishu import (
    list_tables,
    list_fields,
    push_records,
    FeishuAPIError,
)
from app.models.schemas import (
    FeishuField,
    FeishuFieldsResponse,
    FeishuParseTodosRequest,
    FeishuParseTodosResponse,
    FeishuParsedTodo,
    FeishuPushRequest,
    FeishuPushResponse,
    FeishuStatusResponse,
    FeishuTable,
    FeishuTablesResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/feishu", tags=["feishu"])


# ===== 类型名映射(飞书 type 字段是 int) =====
# 完整列表见 https://open.feishu.cn/document/server-docs/bitable/field-type
FEISHU_TYPE_NAMES = {
    1: "Text",
    2: "Number",
    3: "SingleSelect",
    4: "MultiSelect",
    5: "Date",
    7: "Checkbox",
    11: "Person",
    13: "Phone",
    15: "Url",
    17: "Attachment",
    18: "SingleLink",
    20: "Formula",
    21: "DuplexLink",
    22: "Location",
    23: "GroupChat",
    1001: "CreatedTime",
    1002: "ModifiedTime",
    1003: "CreatedUser",
    1004: "ModifiedUser",
    1005: "AutoNumber",
}


@router.get("/status", response_model=FeishuStatusResponse)
async def status() -> FeishuStatusResponse:
    """前端用 — 检查飞书是否配好"""
    configured = settings.feishu_configured
    app_token = settings.feishu_bitable_app_token if configured else ""
    table_id = settings.feishu_bitable_table_id if configured else ""
    # 飞书多维表格 URL 模板
    table_url = (
        f"https://feishu.cn/base/{app_token}?table={table_id}"
        if configured else ""
    )
    return FeishuStatusResponse(
        configured=configured,
        app_token=app_token,
        table_id=table_id,
        table_url=table_url,
    )


@router.get("/tables", response_model=FeishuTablesResponse)
async def tables() -> FeishuTablesResponse:
    """列出多维表格下所有数据表 — 调试用"""
    try:
        items = await list_tables()
    except FeishuAPIError as e:
        raise HTTPException(status_code=502, detail=f"飞书 API 错误: {e.msg}") from e
    except RuntimeError as e:
        # 未配置
        raise HTTPException(status_code=503, detail=str(e)) from e
    return FeishuTablesResponse(
        tables=[
            FeishuTable(table_id=t.get("table_id", ""), name=t.get("name", ""))
            for t in items
        ]
    )


@router.get("/tables/{table_id}/fields", response_model=FeishuFieldsResponse)
async def fields(table_id: str) -> FeishuFieldsResponse:
    """
    列出指定表的字段定义 — 前端用这个知道字段名/类型,
    然后才能正确构造 push_records 的数据
    """
    try:
        items = await list_fields(table_id=table_id)
    except FeishuAPIError as e:
        raise HTTPException(status_code=502, detail=f"飞书 API 错误: {e.msg}") from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return FeishuFieldsResponse(
        fields=[
            FeishuField(
                field_id=f.get("field_id", ""),
                field_name=f.get("field_name", ""),
                type=f.get("type", 1),
                type_name=FEISHU_TYPE_NAMES.get(f.get("type", 1), "Unknown"),
            )
            for f in items
        ]
    )


@router.post("/push-records", response_model=FeishuPushResponse)
async def push(req: FeishuPushRequest) -> FeishuPushResponse:
    """
    批量推送记录到飞书多维表格。

    请求体 records 每条可以是:
    - {"fields": {...}}  (飞书原生格式)
    - {key1: val1, key2: val2, ...}  (我们自动包成 fields)

    ⚠️ 字段 key 必须跟飞书表里的字段名一致,类型必须匹配
       (Text → string, Number → number, Date → ms 时间戳 等)。
       不对会 400 错误。先调 GET /api/feishu/tables/{tid}/fields 看 schema。
    """
    try:
        record_ids = await push_records(
            req.records,
            table_id=req.table_id,
        )
    except FeishuAPIError as e:
        # 飞书的字段类型不匹配会 1254000 系列错误
        logger.warning("飞书推送失败: %s", e)
        raise HTTPException(
            status_code=400,
            detail=f"飞书写入失败: code={e.code} {e.msg}",
        ) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    return FeishuPushResponse(
        success=True,
        message=f"已成功写入 {len(record_ids)} 条记录到飞书多维表格",
        record_count=len(record_ids),
        record_ids=record_ids,
    )


# ===== LLM 解析会议文本为结构化待办 =====

_PARSE_TODOS_SYSTEM = """你是会议待办解析助手,从给定的会议内容/纪要中,提取出所有明确的待办事项。

【严格 JSON 输出】— 不要任何其他文字/解释/代码块标记:
[
  {{"title": "任务标题(动词开头,简洁明确,10 字以内)", "owner": "责任人或 null", "due_date": "YYYY-MM-DD 或 null", "priority": "高/中/低"}}
]

【规则】
- title: 必填,具体可执行的动作,例如"完成 AI 助手迭代设计稿"
- owner: 能从文本推断出责任人(角色或人名),否则 null
- due_date: 能推断出截止日期(YYYY-MM-DD),否则 null
- priority: 高/中/低, 紧迫的 + 截止日期近的 = 高
- 只提取明确的, 排除"建议考虑""可能需要"等模糊表述
- 任务标题不要带方括号/破折号前缀,纯文字
"""


def _safe_parse_todos(raw: str) -> list[FeishuParsedTodo]:
    """LLM 输出可能带 markdown fence / 解释文字,要 robust 解析"""
    if not raw:
        return []

    # 去掉可能的 markdown code block
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    # 找第一个 [ 和最后一个 ] 的 JSON 数组
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        logger.warning("LLM 输出不含 JSON 数组: %s", text[:200])
        return []
    json_text = text[start:end + 1]

    try:
        data = json.loads(json_text)
    except json.JSONDecodeError:
        logger.warning("JSON 解析失败: %s", json_text[:200])
        return []

    todos: list[FeishuParsedTodo] = []
    if not isinstance(data, list):
        return []

    for item in data:
        if not isinstance(item, dict):
            continue
        title = item.get("title") or item.get("任务") or ""
        if not title:
            continue
        todos.append(
            FeishuParsedTodo(
                title=str(title).strip()[:200],
                owner=item.get("owner") or item.get("责任人"),
                due_date=item.get("due_date") or item.get("截止日期"),
                priority=item.get("priority") or item.get("优先级"),
            )
        )
    return todos


async def parse_todos_stream(req: FeishuParseTodosRequest) -> AsyncIterator[dict]:
    """
    流式解析 — SSE 协议跟其他模块一致

    yield 事件:
    - {"type": "token", "content": "..."}
    - {"type": "done", "todos": [...], "raw": "..."}
    - {"type": "error", "message": "..."}
    """
    user_msg = req.text
    if req.meeting_title:
        user_msg = f"会议主题: {req.meeting_title}\n\n{req.text}"

    prompt = ChatPromptTemplate.from_messages([
        ("system", _PARSE_TODOS_SYSTEM),
        ("user", user_msg),
    ])
    llm = get_llm()
    chain = prompt | llm

    full = ""
    try:
        async for chunk in chain.astream({}):
            if chunk.content:
                full += chunk.content
                yield {"type": "token", "content": chunk.content}
    except Exception as e:
        logger.exception("解析待办失败")
        yield {"type": "error", "message": f"LLM 调用失败: {e}"}
        return

    todos = _safe_parse_todos(full)
    yield {"type": "done", "todos": todos, "raw": full}


@router.post("/parse-todos")
async def parse_todos(req: FeishuParseTodosRequest):
    """
    流式解析会议文本为结构化待办 JSON 数组 — 配合前端"导入飞书任务"流程

    前端调用模式:
    1. POST /api/feishu/parse-todos  → 拿到 todos JSON 数组(可手动编辑)
    2. POST /api/feishu/push-records  → 把 todos 数组推给飞书
    """
    import json as _json
    from fastapi.responses import StreamingResponse

    async def stream():
        # 把异步生成器包成 SSE
        async for ev in parse_todos_stream(req):
            yield f"data: {_json.dumps(ev, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )