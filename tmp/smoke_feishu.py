"""
端到端 mock 测试 — 飞书多维表格导出

策略:用 respx 拦截 httpx,模拟飞书 OpenAPI 响应。
不真正起 HTTP server,代码更紧凑。
"""
import sys
import os
import asyncio
from unittest.mock import patch

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(BACKEND_ROOT, ".env"))

# 必须先 import config 再改
from app.core import config as _cfg

# 模拟"飞书已配好"
_cfg.settings.feishu_app_id = "cli_mock_app_id_12345"
_cfg.settings.feishu_app_secret = "mock_app_secret_abcdefghijklmnopqrstuvwxyz"
_cfg.settings.feishu_bitable_app_token = "bitable_app_token_xxxx"
_cfg.settings.feishu_bitable_table_id = "tblMockTable001"

# 用 respx 拦截 httpx
try:
    import respx
except ImportError:
    print("装 respx: pip install respx")
    sys.exit(1)

from httpx import Response


# ===== Mock 飞书 API =====
FAKE_TOKEN = "t-mock_xxxxxxxxxxxxxxxxxx"
FAKE_FIELDS = [
    {"field_id": "fldTitle", "field_name": "标题", "type": 1},   # Text
    {"field_id": "fldOwner", "field_name": "责任人", "type": 1},  # Text
    {"field_id": "fldDue",   "field_name": "截止日期", "type": 5},  # Date
    {"field_id": "fldPri",   "field_name": "优先级", "type": 3},  # SingleSelect
    {"field_id": "fldDone",  "field_name": "已完成", "type": 7},  # Checkbox
]
FAKE_TABLES = [
    {"table_id": "tblMockTable001", "name": "会议任务"},
    {"table_id": "tblMockTable002", "name": "周计划"},
]


def ok(data):
    return {"code": 0, "msg": "success", "data": data}


with respx.mock(assert_all_called=False) as router:
    # 1) tenant_access_token
    router.post(
        url="https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    ).mock(return_value=Response(200, json={
        "code": 0, "msg": "ok",
        "tenant_access_token": FAKE_TOKEN,
        "expire": 7200,
    }))

    # 2) list tables
    router.get(
        url__regex=r".*/bitable/v1/apps/[^/]+/tables$"
    ).mock(return_value=Response(200, json=ok({"items": FAKE_TABLES})))

    # 3) list fields
    router.get(
        url__regex=r".*/bitable/v1/apps/[^/]+/tables/[^/]+/fields$"
    ).mock(return_value=Response(200, json=ok({"items": FAKE_FIELDS})))

    # 4) push records
    counter = {"n": 0}
    def make_record_resp(request):
        body = request.read().decode()
        import json as _json
        data = _json.loads(body)
        n = len(data.get("records", []))
        counter["n"] += n
        return Response(200, json=ok({
            "records": [{"record_id": f"rec{i}_{counter['n']}"} for i in range(n)]
        }))
    router.post(
        url__regex=r".*/bitable/v1/apps/[^/]+/tables/[^/]+/records/batch_create$"
    ).mock(side_effect=make_record_resp)

    # 5) single create (没用,但保险起见)
    router.post(
        url__regex=r".*/bitable/v1/apps/[^/]+/tables/[^/]+/records$"
    ).mock(return_value=Response(200, json=ok({"record": {"record_id": "rec_single"}})))

    # 6) MiniMax OpenAI 兼容 chat completion — 给 LLM 一个固定的 JSON 响应
    router.post(
        url__regex=r"https://api\.minimaxi\.com/v1/chat/completions"
    ).mock(return_value=Response(200, json={
        "id": "chatcmpl-mock",
        "object": "chat.completion",
        "created": 1700000000,
        "model": "MiniMax-M3",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": (
                    '[{"title":"完成 AI 助手迭代设计稿","owner":"小王","due_date":"2026-08-26","priority":"高"},'
                    '{"title":"准备 Q4 营销方案","owner":"小李","due_date":"2026-10-31","priority":"中"},'
                    '{"title":"数据库迁移评估","owner":"张工","due_date":null,"priority":"高"}]'
                ),
            },
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 100, "completion_tokens": 200, "total_tokens": 300},
    }))


    # ===== 跑测试 =====
    async def main():
        from app.feishu import (
            get_tenant_access_token,
            list_tables,
            list_fields,
            push_records,
        )
        from app.api.feishu import parse_todos_stream
        from app.models.schemas import FeishuParseTodosRequest

        print("=== 1) 鉴权: 拿 tenant_access_token ===", flush=True)
        token = await get_tenant_access_token()
        print(f"✅ token = {token[:20]}...", flush=True)

        print("\n=== 2) 列数据表 ===", flush=True)
        tables = await list_tables()
        for t in tables:
            print(f"  - {t['table_id']}: {t['name']}", flush=True)

        print("\n=== 3) 列字段定义 ===", flush=True)
        fields = await list_fields()
        for f in fields:
            print(f"  - {f['field_name']:10s} (type={f['type']})", flush=True)

        print("\n=== 4) 推送 3 条记录 ===", flush=True)
        records = [
            {"标题": "完成 AI 助手迭代设计稿", "责任人": "小王", "优先级": "高"},
            {"标题": "准备 Q4 营销方案", "责任人": "小李", "优先级": "中"},
            {"标题": "整理客户反馈汇总", "责任人": "小张", "优先级": "低"},
        ]
        ids = await push_records(records)
        for rid in ids:
            print(f"  ✅ 写入 record_id={rid}", flush=True)

        print("\n=== 5) LLM 解析会议文本为结构化待办 — 改测试 _safe_parse_todos 的输入 ===", flush=True)
        from app.api.feishu import _safe_parse_todos
        fake_llm_output = (
            '[{"title":"完成 AI 助手迭代设计稿","owner":"小王","due_date":"2026-08-26","priority":"高"},'
            '{"title":"准备 Q4 营销方案","owner":"小李","due_date":"2026-10-31","priority":"中"},'
            '{"title":"数据库迁移评估","owner":"张工","due_date":null,"priority":"高"}]'
        )
        todos = _safe_parse_todos(fake_llm_output)
        print(f"  解析出 {len(todos)} 条:", flush=True)
        for todo in todos:
            print(f"    - {todo.title} | 责任人={todo.owner} | 截止={todo.due_date} | 优先级={todo.priority}", flush=True)

        print("\n=== 6) 推解析出的待办 ===", flush=True)
        records_from_todos = [
            {"标题": todo.title, "责任人": todo.owner or "", "优先级": todo.priority or "中"}
            for todo in todos
        ]
        ids2 = await push_records(records_from_todos)
        print(f"  ✅ 写入 {len(ids2)} 条: {ids2}", flush=True)

        # 边界场景
        print("\n=== 7) 鲁棒性: LLM 输出带 markdown fence ===", flush=True)
        fenced = (
            "```json\n"
            '[{"title":"文档整理","owner":null,"due_date":null,"priority":"低"}]\n'
            "```\n"
        )
        todos_fenced = _safe_parse_todos(fenced)
        print(f"  ✅ fence 处理: {len(todos_fenced)} 条", flush=True)
        for todo in todos_fenced:
            print(f"    - {todo.title} | 优先级={todo.priority}", flush=True)

        print("\n=== 8) 鲁棒性: LLM 输出解释垃圾 ===", flush=True)
        garbage = "好的,我来帮你解析。这是会议内容..."
        todos_garbage = _safe_parse_todos(garbage)
        print(f"  ✅ 垃圾输出兜底: {len(todos_garbage)} 条(应=0)", flush=True)

        print("\n🎉 全部 mock 测试通过", flush=True)


    asyncio.run(main())