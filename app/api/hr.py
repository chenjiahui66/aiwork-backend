"""
HR 助手接口
"""
import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.models.schemas import HrRequest
from app.hr import chain

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/hr", tags=["hr"])


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/run")
async def run(req: HrRequest) -> StreamingResponse:
    """流式 HR 任务"""

    async def stream():
        try:
            async for event in chain.run(task=req.task, inputs=req.inputs):
                yield _sse(event)
        except Exception as e:
            logger.exception("HR 异常")
            yield _sse({"type": "error", "message": f"服务异常: {e}"})

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/options")
async def list_options() -> dict:
    """前端下拉框用"""
    from app.hr.prompts import (
        COMMON_LOCATIONS,
        EXPERIENCE_LEVELS,
        JOB_INDUSTRIES,
        PROMPT_REGISTRY,
        TASK_LABELS,
    )
    return {
        "tasks": [
            {"code": k, "label": v, "fields": _fields_for_task(k)}
            for k, v in TASK_LABELS.items()
        ],
        "industries": JOB_INDUSTRIES,
        "experience_levels": EXPERIENCE_LEVELS,
        "locations": COMMON_LOCATIONS,
    }


def _fields_for_task(task: str) -> list[dict]:
    """每个任务需要的字段定义(前端动态渲染表单)"""
    if task == "jd":
        return [
            {"key": "position", "label": "职位名称", "type": "input", "required": True, "placeholder": "例如:Python 后端开发工程师"},
            {"key": "industry", "label": "行业", "type": "select", "options": "industries", "required": True},
            {"key": "requirements", "label": "关键要求", "type": "textarea", "rows": 3, "required": True, "placeholder": "例:\n- 3 年 Python 后端经验\n- 熟悉 FastAPI/Django\n- 有大模型项目经历"},
            {"key": "location", "label": "工作地点", "type": "select", "options": "locations"},
            {"key": "experience", "label": "经验要求", "type": "select", "options": "experience_levels", "required": True},
        ]
    if task == "resume_screen":
        return [
            {"key": "jd_excerpt", "label": "JD 关键要求", "type": "textarea", "rows": 4, "required": True, "placeholder": "把 JD 关键要求复制进来"},
            {"key": "resume_text", "label": "候选人简历", "type": "textarea", "rows": 12, "required": True, "placeholder": "粘贴简历全文"},
        ]
    if task == "onboarding":
        return [
            {"key": "employee_name", "label": "新员工姓名", "type": "input", "required": True, "placeholder": "例如:张明远"},
            {"key": "start_date", "label": "入职日期", "type": "input", "required": True, "placeholder": "例如:2024-09-01"},
            {"key": "position", "label": "职位", "type": "input", "required": True},
            {"key": "department", "label": "部门", "type": "input", "required": True},
            {"key": "manager", "label": "直属领导", "type": "input", "required": True, "placeholder": "例如:李经理"},
            {"key": "company", "label": "公司名", "type": "input", "required": True, "placeholder": "例如:AiWork 科技"},
        ]
    return []