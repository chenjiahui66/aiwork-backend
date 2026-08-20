"""
数据洞察主流程: 自然语言 -> SQL -> 执行 -> 图表
"""
import logging
from typing import AsyncIterator

from app.insight import chart_picker, seed_db, sql_generator

logger = logging.getLogger(__name__)


async def query(question: str) -> AsyncIterator[dict]:
    """
    自然语言查询 (流式输出)

    yield 事件:
    - {"type": "sources", "sources": [], "meta": {"sql": ..., "row_count": ..., "chart": {...}}}
    - {"type": "token", "content": "..."}    - 阶段说明文本
    - {"type": "done"}
    """
    if not question.strip():
        yield {"type": "error", "message": "问题不能为空"}
        return

    # 0. 启动种子 DB
    try:
        seed_db._ensure_seed()
    except Exception as e:
        yield {"type": "error", "message": f"数据库初始化失败: {e}"}
        return

    # 1. 生成 SQL
    yield {"type": "token", "content": "🔍 分析问题,生成 SQL...\n\n"}
    try:
        sql = sql_generator.generate_sql(question)
    except Exception as e:
        logger.exception("SQL 生成失败")
        yield {"type": "error", "message": f"SQL 生成失败: {e}"}
        return

    yield {"type": "token", "content": f"```sql\n{sql}\n```\n\n"}

    # 2. 安全校验
    is_valid, validated = sql_generator.validate_sql(sql)
    if not is_valid:
        yield {"type": "error", "message": f"SQL 安全校验失败: {validated}"}
        return
    final_sql = validated if isinstance(validated, str) else sql

    # 3. 执行 SQL
    yield {"type": "token", "content": "⚡ 执行查询...\n\n"}
    try:
        conn = seed_db.get_connection()
        cur = conn.cursor()
        cur.execute(final_sql)
        columns = [desc[0] for desc in cur.description] if cur.description else []
        rows_raw = cur.fetchall()
        conn.close()
        # 转成纯 Python 类型(JSON 序列化友好)
        rows = [_normalize_row(r) for r in rows_raw]
    except Exception as e:
        logger.exception("SQL 执行失败: %s", final_sql)
        yield {"type": "error", "message": f"SQL 执行失败: {e}\n\nSQL: {final_sql}"}
        return

    yield {
        "type": "token",
        "content": f"✅ 返回 {len(rows)} 行结果\n\n"
    }

    # 4. 选图表
    chart = chart_picker.pick_chart(columns, rows)
    chart_summary = _describe_chart(chart)
    yield {
        "type": "token",
        "content": f"📊 图表类型: **{chart['chart_type']}** {chart_summary}\n\n"
    }

    # 5. 把元信息抛给前端(包含 SQL + 数据 + 图表配置)
    yield {
        "type": "sources",
        "sources": [],
        "meta": {
            "sql": final_sql,
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "chart": chart,
        },
    }

    yield {"type": "done"}


def _normalize_row(row: tuple) -> list:
    """把 sqlite 行转 JSON 友好"""
    out = []
    for v in row:
        if isinstance(v, (int, float, str, type(None))):
            out.append(v)
        elif isinstance(v, bytes):
            out.append(v.decode("utf-8", errors="replace"))
        else:
            out.append(str(v))
    return out


def _describe_chart(chart: dict) -> str:
    t = chart["chart_type"]
    if t == "table":
        return chart.get("message", "")
    return ""