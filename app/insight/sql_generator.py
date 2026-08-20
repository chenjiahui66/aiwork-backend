"""
Text-to-SQL: 用 LLM 把自然语言转成 SQLite 查询
"""
import logging
import re

from app.core.llm import get_llm
from app.insight.seed_db import get_schema_description

logger = logging.getLogger(__name__)


SQL_SYSTEM = """你是一位数据分析师,擅长把业务问题转成 SQL。

数据库是 SQLite。请严格根据下方 Schema 回答。

要求:
1. **只输出 SELECT 查询**,绝不输出 INSERT/UPDATE/DELETE/DROP/ALTER/PRAGMA
2. 输出**纯 SQL**(不要用 markdown 包裹, 不要加解释)
3. 必须加 LIMIT,最多 1000 行
4. 涉及的字段不存在时, 查 NULL 或报"无法回答"
5. 避免子查询嵌套过深
6. 涉及日期范围时用 date('now', '-N month') 或 BETWEEN,不要硬编码当前日期
7. 关联查询要写 JOIN 条件

【Schema】
{schema}
"""


def generate_sql(question: str) -> str:
    """
    调用 LLM 生成 SQL
    """
    from langchain_core.prompts import ChatPromptTemplate

    prompt = ChatPromptTemplate.from_messages([
        ("system", SQL_SYSTEM.format(schema=get_schema_description())),
        ("user", "{question}"),
    ])

    llm = get_llm()
    chain = prompt | llm

    # 调 LLM (非流式,因为我们要拿到完整 SQL 再执行)
    out = ""
    for chunk in chain.stream({"question": question}):
        if chunk.content:
            out += chunk.content

    sql = _clean_sql_output(out)
    logger.info("📊 SQL 生成: %s -> %s", question[:60], sql[:200])
    return sql


def _clean_sql_output(raw: str) -> str:
    """
    清理 LLM 输出,提取纯 SQL
    去掉 markdown fence、说明文字、多余空白
    """
    text = text.strip() if (text := raw) else raw  # noqa: E999

    # 去掉 markdown ```sql ... ```
    fence_match = re.search(r"```(?:sql)?\s*(.+?)```", raw, re.DOTALL | re.IGNORECASE)
    if fence_match:
        text = fence_match.group(1)
    else:
        text = raw

    text = text.strip()

    # 去掉头尾可能的解释文字
    # 找第一个 SELECT / WITH, 截到末尾
    sql_start = re.search(r"\b(SELECT|WITH)\b", text, re.IGNORECASE)
    if sql_start:
        text = text[sql_start.start():]

    # 去掉分号后的内容
    text = text.split(";")[0].strip()

    return text


def validate_sql(sql: str) -> tuple[bool, str]:
    """
    安全校验: 只允许 SELECT, 强制 LIMIT

    Returns: (is_valid, reason)
    """
    sql_clean = sql.strip().rstrip(";").strip()

    if not sql_clean:
        return False, "SQL 为空"

    # 必须以 SELECT 或 WITH 开头
    first_keyword = sql_clean.split()[0].upper() if sql_clean.split() else ""
    if first_keyword not in ("SELECT", "WITH"):
        return False, f"只允许 SELECT 查询, 不能以 {first_keyword} 开头"

    # 黑名单关键字
    dangerous = [
        "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
        "REPLACE", "TRUNCATE", "PRAGMA", "ATTACH", "DETACH",
        "VACUUM", "REINDEX", "GRANT", "REVOKE",
    ]
    upper_sql = sql_clean.upper()
    for kw in dangerous:
        # 词边界匹配,避免误判 (例如 "UPDATED_AT" 字段名)
        if re.search(rf"\b{kw}\b", upper_sql):
            return False, f"SQL 包含禁止关键字 {kw}"

    # 必须有 LIMIT (防止误操作大表)
    if not re.search(r"\bLIMIT\b", upper_sql):
        # 自动加 LIMIT 1000
        sql_clean += " LIMIT 1000"
        logger.warning("SQL 未带 LIMIT,自动追加 LIMIT 1000")

    return True, sql_clean