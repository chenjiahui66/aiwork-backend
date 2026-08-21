"""
发邮件模块 — 走标准库 smtplib,零新增依赖。

使用:
    from app.email import send_email
    await send_email(
        to=["boss@company.com"],
        subject="Q4 W42 周报",
        content="...",
    )
"""
from app.email.smtp_client import send_email

__all__ = ["send_email"]