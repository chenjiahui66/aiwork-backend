"""
飞书多维表格 Bitable API 封装

API 文档:
- 列出数据表: GET /open-apis/bitable/v1/apps/{app_token}/tables
- 列出字段:   GET /open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields
- 新增记录:   POST /open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records
- 批量新增:   POST /open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create

关键字段类型(必须严格匹配,否则 400):
- Text:        {"text": "..."}
- Number:      {"value": 123}
- Date:        {"value": 1700000000000}   ← 毫秒时间戳
- SingleSelect: {"value": "option_key"}
- MultiSelect:  {"value": ["key1", "key2"]}
- Person:       {"value": [{"id": "ou_xxx"}]}
- Url:          {"link": "...", "text": "..."}
- Checkbox:     {"value": true / false}
"""
import logging
from typing import Any

import httpx

from app.core.config import settings
from app.feishu.auth import get_tenant_access_token

logger = logging.getLogger(__name__)

_BASE = "https://open.feishu.cn/open-apis"


class FeishuAPIError(Exception):
    """飞书 API 业务错误 — 4xx/5xx 但拿到 JSON 响应"""
    def __init__(self, code: int, msg: str, status_code: int = 0):
        self.code = code
        self.msg = msg
        self.status_code = status_code
        super().__init__(f"飞书 API 错误 [{code}]: {msg}")


async def _request(
    method: str,
    path: str,
    *,
    json_body: dict | None = None,
    params: dict | None = None,
) -> dict:
    """统一的飞书 API 请求封装 — 自动加 Authorization,统一错误处理"""
    if not settings.feishu_configured:
        raise RuntimeError(
            "飞书未配置 — 请在 .env 里填 FEISHU_APP_ID / FEISHU_APP_SECRET / "
            "FEISHU_BITABLE_APP_TOKEN / FEISHU_BITABLE_TABLE_ID"
        )

    token = await get_tenant_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
    }
    url = f"{_BASE}{path}"

    async with httpx.AsyncClient(timeout=settings.feishu_timeout) as client:
        resp = await client.request(
            method, url, headers=headers, json=json_body, params=params
        )

    # 飞书 200 不代表成功 — 必须看 JSON 里的 code 字段
    try:
        data = resp.json()
    except Exception:
        raise RuntimeError(f"飞书 API 返回非 JSON: {resp.status_code} {resp.text[:200]}")

    if data.get("code") != 0:
        raise FeishuAPIError(
            code=data.get("code", -1),
            msg=data.get("msg", ""),
            status_code=resp.status_code,
        )

    return data.get("data", {})


async def list_tables(app_token: str | None = None) -> list[dict]:
    """列出指定 app 下所有数据表 — 前端调试用"""
    at = app_token or settings.feishu_bitable_app_token
    data = await _request(
        "GET", f"/bitable/v1/apps/{at}/tables",
    )
    return data.get("items", [])


async def list_fields(
    table_id: str | None = None,
    app_token: str | None = None,
) -> list[dict]:
    """列出表的字段定义 — 前端调试用, 帮助用户知道字段名和类型"""
    at = app_token or settings.feishu_bitable_app_token
    tid = table_id or settings.feishu_bitable_table_id
    data = await _request(
        "GET", f"/bitable/v1/apps/{at}/tables/{tid}/fields",
    )
    return data.get("items", [])


async def create_record(
    fields: dict[str, Any],
    *,
    table_id: str | None = None,
    app_token: str | None = None,
    record_id: str | None = None,
) -> str:
    """
    新增单条记录。

    Args:
        fields: 字段 dict,key 必须是表的字段名,value 必须是飞书要求的格式
        table_id / app_token: 默认用 .env 的, 也可指定别的表

    Returns:
        新记录的 record_id
    """
    at = app_token or settings.feishu_bitable_app_token
    tid = table_id or settings.feishu_bitable_table_id
    body: dict[str, Any] = {"fields": fields}
    if record_id:
        body["record_id"] = record_id

    data = await _request(
        "POST", f"/bitable/v1/apps/{at}/tables/{tid}/records", json_body=body,
    )
    record = data.get("record", {})
    return record.get("record_id", "")


async def push_records(
    records: list[dict[str, Any]],
    *,
    table_id: str | None = None,
    app_token: str | None = None,
) -> list[str]:
    """
    批量新增记录 — 飞书一次最多 1000 条。

    Args:
        records: 每条是 {"fields": {...}}, 也可以直接是字段 dict(我们自动包装)
        table_id / app_token: 默认用 .env 的

    Returns:
        新记录 ID 列表(按提交顺序)
    """
    if not records:
        return []

    at = app_token or settings.feishu_bitable_app_token
    tid = table_id or settings.feishu_bitable_table_id

    # 自动包装:允许前端传 [{title:..., owner:..., ...}, ...] 也行
    formatted = []
    for r in records:
        if "fields" in r and isinstance(r["fields"], dict):
            formatted.append(r)
        else:
            formatted.append({"fields": r})

    data = await _request(
        "POST",
        f"/bitable/v1/apps/{at}/tables/{tid}/records/batch_create",
        json_body={"records": formatted},
    )
    items = data.get("records", [])
    return [item.get("record_id", "") for item in items]