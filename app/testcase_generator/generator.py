"""把 Case 列表渲染成 pytest 代码。

策略:Python 直写,不打 diff。每条用例一个 def test_xxx()。
"""
from __future__ import annotations

import json

from .parser import Case, Step


HEADER = '''\
"""本文件由 aiwork 测试用例生成器自动生成,请勿手工编辑。
如需修改,请回到 AiWork -> 测试用例生成器调整用例后重新生成。
"""
from __future__ import annotations

import pytest
import requests


def _request(method: str, path: str, base_url: str, body=None):
    url = f"{base_url.rstrip('/')}{path}"
    method = method.upper()
    if method == "GET":
        return requests.get(url, timeout=10)
    if method == "DELETE":
        return requests.delete(url, timeout=10)
    if body is None:
        return requests.request(method, url, timeout=10)
    return requests.request(method, url, json=body, timeout=10)


def _assert(resp, expect_status=None, expect_json=""):
    if expect_status is not None:
        assert resp.status_code == expect_status, (
            f"期望状态码 {expect_status}, 实际 {resp.status_code}, body={resp.text[:200]}"
        )
    if expect_json:
        expr = expect_json
        try:
            data = resp.json()
            if "非空" in expr:
                # 形如:resp.json().token 非空
                key = expr.split("json().", 1)[-1].split(" ")[0].split("==")[0].split("!=")[0].strip(".")
                assert data.get(key), f"{key} 应非空, 实际 {data.get(key)!r}"
            elif "为空" in expr:
                key = expr.split("json().", 1)[-1].split(" ")[0].strip(".")
                assert not data.get(key), f"{key} 应为空, 实际 {data.get(key)!r}"
            elif "==" in expr:
                lhs, rhs = [x.strip() for x in expr.split("==", 1)]
                key = lhs.split("json().", 1)[-1].strip(".")
                actual = data.get(key)
                # 简单字面量
                if rhs.startswith('"') or rhs.startswith("'"):
                    expected = rhs[1:-1] if rhs[0] == rhs[-1] else rhs
                else:
                    try:
                        expected = json.loads(rhs)
                    except Exception:
                        expected = rhs
                assert actual == expected, f"{key} 期望 {expected!r}, 实际 {actual!r}"
        except ValueError:
            pytest.fail(f"响应不是 JSON: {resp.text[:200]}")


'''


def _render_step(step: Step) -> str:
    """把一条 Step 翻译成 1~3 行 Python 代码。"""
    if not step.method and step.expect_status is None and not step.expect_json and not step.note:
        return ""

    lines: list[str] = []
    if step.method:
        if step.body is not None:
            body = json.dumps(step.body, ensure_ascii=False)
            lines.append(f"resp = _request({step.method!r}, {step.path!r}, BASE_URL, {body})")
        else:
            lines.append(f"resp = _request({step.method!r}, {step.path!r}, BASE_URL)")
    if step.expect_status is not None:
        lines.append(f"_assert(resp, expect_status={step.expect_status})")
    if step.expect_json:
        lines.append(f"_assert(resp, expect_json={step.expect_json!r})")
    if step.note and not lines:
        lines.append(f"# TODO: 无法解析 - {step.note}")
    return "\n    ".join(lines)


def _render_case(case: Case) -> str:
    step_lines: list[str] = []
    for st in case.steps:
        rendered = _render_step(st)
        if rendered:
            step_lines.append(rendered)
    if not step_lines:
        step_lines = ["pytest.skip('空用例')"]
    body = "\n    ".join(step_lines)
    return (
        f"def {case.fn_name}():\n"
        f"    \"\"\"{case.title}\"\"\"\n"
        f"    BASE_URL = {case.base_url!r}\n"
        f"    {body}\n"
    )


def render_pytest(cases: list[Case]) -> str:
    if not cases:
        return HEADER + "\n# 未解析到任何用例,请检查输入格式\n"
    body = "\n\n".join(_render_case(c) for c in cases)
    return HEADER + "\n\n" + body + "\n"
