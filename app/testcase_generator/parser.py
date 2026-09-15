"""文本测试用例解析器。

支持的输入格式(每个用例之间用空行分隔):
    用例 1: 用户登录成功
    步骤:
      1. POST /api/login  body={"user":"alice","pwd":"123456"}
      2. 断言 status_code == 200
      3. 断言 resp.json().token 非空

    用例 2: 登录失败-密码错误
    步骤:
      1. POST /api/login  body={"user":"alice","pwd":"wrong"}
      2. 断言 status_code == 401
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Step:
    raw: str
    method: str = ""           # GET / POST / PUT / DELETE
    path: str = ""
    body: dict | None = None
    expect_status: int | None = None
    expect_json: str = ""      # 形如 "token 非空" / "code == 0"
    note: str = ""             # 不能解析时填进 note


@dataclass
class Case:
    title: str
    fn_name: str
    steps: list[Step] = field(default_factory=list)
    base_url: str = "http://localhost:8000"


_STEP_RE = re.compile(r"^\s*(\d+)\s*[.)、]\s*(.+)$")
_METHOD_RE = re.compile(
    r"^\s*(GET|POST|PUT|DELETE|PATCH)\s+(\S+)(?:\s+body\s*=\s*(\{.*\}))?\s*$",
    re.IGNORECASE,
)
_ASSERT_STATUS_RE = re.compile(r"status_code\s*==\s*(\d+)")
_ASSERT_JSON_RE = re.compile(r"json\(\)\.([\w.]+)\s*(==|!=|非空|为空)\s*(.*)?")


def _slugify(title: str, index: int) -> str:
    """生成 Python 函数名:test_<index>_<slug>"""
    s = re.sub(r"[\s/\\,\.\-:;!?\"']+", "_", title)
    s = re.sub(r"[^a-zA-Z0-9_]", "", s).strip("_").lower()
    s = re.sub(r"_+", "_", s)
    if not s:
        s = "case"
    return f"test_{index:02d}_{s[:40]}"


def _parse_body(body_str: str) -> dict | None:
    body_str = body_str.strip()
    # 仅支持简单 JSON 字面量,复杂场景可后端替换为 LLM
    try:
        import json
        return json.loads(body_str)
    except Exception:
        return None


def _parse_step(line: str) -> Step:
    line = line.strip()
    s = Step(raw=line)

    m = _METHOD_RE.match(line)
    if m:
        s.method = m.group(1).upper()
        s.path = m.group(2)
        if m.group(3):
            s.body = _parse_body(m.group(3))
        return s

    m = _ASSERT_STATUS_RE.search(line)
    if m:
        s.expect_status = int(m.group(1))
        return s

    m = _ASSERT_JSON_RE.search(line)
    if m:
        s.expect_json = m.group(0).strip()
        return s

    s.note = line  # 兜底:留给生成器当注释
    return s


def parse(text: str, base_url: str = "http://localhost:8000") -> list[Case]:
    """把整段文本切成多个 Case。"""
    cases: list[Case] = []
    cur: Case | None = None

    title_re = re.compile(r"^\s*用例\s*(\d+)\s*[:：]\s*(.+?)\s*$")

    for line in text.splitlines():
        line = line.rstrip()
        if not line.strip():
            continue
        m = title_re.match(line)
        if m:
            if cur is not None:
                cases.append(cur)
            idx = int(m.group(1))
            cur = Case(
                title=m.group(2),
                fn_name=_slugify(m.group(2), idx),
                base_url=base_url,
            )
            continue
        if cur is None:
            # 没有标题行,自动建一个
            cur = Case(title="未命名用例", fn_name="test_01_unnamed", base_url=base_url)
        # 步骤行
        m = _STEP_RE.match(line)
        if m:
            cur.steps.append(_parse_step(m.group(2)))
        elif line.strip().startswith("断言") or "断言" in line:
            cur.steps.append(_parse_step(line))

    if cur is not None:
        cases.append(cur)
    return cases
