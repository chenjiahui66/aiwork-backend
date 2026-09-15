"""测试用例生成器接口。

前端路径:
    POST /api/testcase/generate   解析 + 生成 pytest
    GET  /api/testcase/sample     内置示例文本
"""
import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.testcase_generator.generator import render_pytest
from app.testcase_generator.parser import parse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/testcase", tags=["testcase"])


class GenerateRequest(BaseModel):
    text: str = Field(..., description="自然语言测试用例文本")
    base_url: str = Field(default="http://localhost:8000", description="API 基础地址")


class StepOut(BaseModel):
    raw: str
    method: str
    path: str
    body: dict | None = None
    expect_status: int | None = None
    expect_json: str = ""
    note: str = ""


class CaseOut(BaseModel):
    title: str
    fn_name: str
    base_url: str
    steps: list[StepOut]


class GenerateResponse(BaseModel):
    code: str
    cases: list[CaseOut]
    pytest_source: str


class ParseRequest(BaseModel):
    text: str
    base_url: str = "http://localhost:8000"


class ParseResponse(BaseModel):
    cases: list[CaseOut]


def _case_to_dict(c) -> dict:
    return {
        "title": c.title,
        "fn_name": c.fn_name,
        "base_url": c.base_url,
        "steps": [
            {
                "raw": s.raw,
                "method": s.method,
                "path": s.path,
                "body": s.body,
                "expect_status": s.expect_status,
                "expect_json": s.expect_json,
                "note": s.note,
            }
            for s in c.steps
        ],
    }


@router.post("/parse", response_model=ParseResponse)
def api_parse(req: ParseRequest):
    cases = parse(req.text, base_url=req.base_url)
    return {"cases": [_case_to_dict(c) for c in cases]}


@router.post("/generate", response_model=GenerateResponse)
def api_generate(req: GenerateRequest):
    cases = parse(req.text, base_url=req.base_url)
    source = render_pytest(cases)
    return {
        "code": "ok",
        "cases": [_case_to_dict(c) for c in cases],
        "pytest_source": source,
    }


SAMPLE_TEXT = """\
用例 1: 用户登录成功
步骤:
  1. POST /api/login  body={"user":"alice","pwd":"123456"}
  2. 断言 status_code == 200
  3. 断言 resp.json().token 非空

用例 2: 登录失败-密码错误
步骤:
  1. POST /api/login  body={"user":"alice","pwd":"wrong"}
  2. 断言 status_code == 401

用例 3: 获取用户列表
步骤:
  1. GET /api/users
  2. 断言 status_code == 200
  3. 断言 resp.json().code == 0
"""


@router.get("/sample")
def api_sample():
    return {"text": SAMPLE_TEXT}
