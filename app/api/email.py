"""
发邮件 API — 写作助手/会议助手/数据洞察的通用"发送"按钮

端点:
- GET /api/email/status     检查 SMTP 是否配置(前端用)
- POST /api/email/send      发邮件
"""
import logging

from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.email import send_email
from app.email.smtp_client import (
    EmailError,
    SMTPAuthError,
    SMTPConnectionError,
    SMTPSendError,
)
from app.models.schemas import EmailSendRequest, EmailSendResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/email", tags=["email"])


@router.get("/status")
async def email_status() -> dict:
    """前端用 — 检查 SMTP 是否配好(决定按钮是否可点)"""
    return {
        "configured": settings.smtp_configured,
        "from_name": settings.smtp_from_name if settings.smtp_configured else "",
        "from_addr": settings.smtp_user if settings.smtp_configured else "",
    }


@router.post("/send", response_model=EmailSendResponse)
async def send(req: EmailSendRequest) -> EmailSendResponse:
    """
    发邮件 — 通用接口。

    适用场景:
    - 写作助手:周报 / 邮件 / 公文 生成完,一键发给老板/同事
    - 会议助手:会议纪要发给所有参会人
    - 数据洞察:报表邮件订阅

    错误码:
    - 503 SMTP 未配置
    - 502 SMTP 连接失败
    - 401 SMTP 认证失败(授权码错)
    - 400 参数错(收件人为空 / 主题空)
    """
    try:
        result = await send_email(
            to=req.to,
            subject=req.subject,
            content=req.content,
            cc=req.cc or None,
            is_html=req.is_html,
        )
    except SMTPAuthError as e:
        logger.warning("SMTP 认证失败: %s", e)
        raise HTTPException(
            status_code=401,
            detail=f"SMTP 认证失败: {e}",
        )
    except SMTPConnectionError as e:
        logger.warning("SMTP 连接失败: %s", e)
        raise HTTPException(
            status_code=502,
            detail=f"SMTP 服务器连不上: {e}",
        )
    except SMTPSendError as e:
        logger.warning("SMTP 发送失败: %s", e)
        raise HTTPException(
            status_code=400,
            detail=f"邮件发送失败: {e}",
        )
    except EmailError as e:
        # 未配置 / 收件人为空等
        if "未配置" in str(e):
            raise HTTPException(
                status_code=503,
                detail=str(e),
            )
        raise HTTPException(status_code=400, detail=str(e))

    return EmailSendResponse(
        success=True,
        message="邮件已发送",
        to=result["to"],
        cc=result["cc"],
        subject=result["subject"],
    )