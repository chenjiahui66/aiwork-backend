"""
SMTP 客户端 — 兼容 QQ / 163 / Gmail / 企业邮(腾讯/阿里)

设计要点:
- 用 asyncio.to_thread 把同步 smtplib 跑在线程池,不阻塞 FastAPI event loop
- 支持纯文本 / HTML 两种格式
- 异常分类: AuthError(密码错) / ConnectionError(连不上) / SendError(收件人拒收)
"""
import asyncio
import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailError(Exception):
    """发邮件基础异常"""


class SMTPAuthError(EmailError):
    """认证失败 — 授权码错 / SMTP 没开"""


class SMTPConnectionError(EmailError):
    """连不上 — host 错 / 端口错 / 网络问题"""


class SMTPSendError(EmailError):
    """发送失败 — 收件人拒收 / 内容被反垃圾"""


def _compose_message(
    to: list[str],
    subject: str,
    content: str,
    *,
    cc: list[str] | None = None,
    is_html: bool = False,
) -> MIMEMultipart:
    """拼装邮件(MIME)"""
    msg = MIMEMultipart("alternative")
    # 发件人显示名
    msg["From"] = formataddr((settings.smtp_from_name, settings.smtp_user))
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg["Subject"] = subject

    # 正文 — plain 或 html
    subtype = "html" if is_html else "plain"
    msg.attach(MIMEText(content, subtype, "utf-8"))
    return msg


def _send_sync(
    to: list[str],
    subject: str,
    content: str,
    cc: list[str] | None = None,
    is_html: bool = False,
) -> dict:
    """同步发送 — 跑在线程池里"""
    msg = _compose_message(to, subject, content, cc=cc, is_html=is_html)

    # 所有收件人(to + cc)— SMTP RCPT TO 命令需要完整列表
    all_recipients = to + (cc or [])

    # 是否走 TLS — 配置 host 在 127.0.0.1/localhost 时默认 False(便于 mock 测试)
    # 生产 SMTP 永远是 True(465 SSL 或 587 STARTTLS)
    use_tls = settings.smtp_host not in ("127.0.0.1", "localhost")

    context = ssl.create_default_context()
    if not use_tls:
        # 测试场景 — 关掉证书校验
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

    try:
        # 端口 465 → SMTP_SSL(隐式 TLS)
        # 端口 587 / 25 → SMTP + STARTTLS(显式 TLS, 标准做法)
        # 端口非 465 且 use_tls=False → 明文(只用于本地 mock 测试)
        if use_tls and settings.smtp_port == 465:
            smtp_class = smtplib.SMTP_SSL
            smtp_args = (settings.smtp_host, settings.smtp_port)
            smtp_kwargs = {"timeout": settings.smtp_timeout, "context": context}
        else:
            smtp_class = smtplib.SMTP
            smtp_args = (settings.smtp_host, settings.smtp_port)
            smtp_kwargs = {"timeout": settings.smtp_timeout}

        with smtp_class(*smtp_args, **smtp_kwargs) as server:
            # 587/25 走 STARTTLS 升级(use_tls=True 才升级)
            if use_tls and settings.smtp_port != 465:
                server.starttls(context=context)
            server.login(settings.smtp_user, settings.smtp_password)
            refused = server.sendmail(
                settings.smtp_user, all_recipients, msg.as_string()
            )
    except smtplib.SMTPAuthenticationError as e:
        raise SMTPAuthError(
            f"SMTP 认证失败: {e.smtp_code} {e.smtp_error.decode(errors='ignore') if isinstance(e.smtp_error, bytes) else e.smtp_error}"
            f" — 请检查授权码是否正确,QQ/163 需要在邮箱后台开 SMTP 服务"
        ) from e
    except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected, OSError) as e:
        raise SMTPConnectionError(
            f"连不上 SMTP 服务器 {settings.smtp_host}:{settings.smtp_port} — {e}"
        ) from e
    except smtplib.SMTPRecipientsRefused as e:
        raise SMTPSendError(f"收件人被拒绝: {e.recipients}") from e
    except smtplib.SMTPException as e:
        raise EmailError(f"SMTP 错误: {e}") from e

    # sendmail 返回的 dict 是被服务器拒收的 {addr: (code, msg)}
    if refused:
        raise SMTPSendError(f"部分收件人被拒收: {refused}")

    return {
        "to": to,
        "cc": cc or [],
        "subject": subject,
        "sent_at": msg["Date"] if msg["Date"] else None,
    }


async def send_email(
    to: list[str],
    subject: str,
    content: str,
    cc: list[str] | None = None,
    is_html: bool = False,
) -> dict:
    """
    异步发邮件入口 — 把同步 smtplib 跑在线程池里,不阻塞 event loop。

    Args:
        to: 收件人列表(必填,至少 1 个)
        subject: 邮件主题
        content: 正文(纯文本或 HTML)
        cc: 抄送列表(可选)
        is_html: True=HTML 格式, False=纯文本

    Returns:
        {"to": [...], "cc": [...], "subject": "...", "sent_at": "..."}

    Raises:
        EmailError / SMTPAuthError / SMTPConnectionError / SMTPSendError
    """
    if not settings.smtp_configured:
        raise EmailError(
            "SMTP 未配置 — 请在 .env 里填 SMTP_HOST / SMTP_USER / SMTP_PASSWORD,"
            "QQ/163 邮箱需后台开 SMTP 服务并生成授权码"
        )

    if not to:
        raise EmailError("收件人不能为空")

    logger.info(
        "📧 发邮件: to=%s cc=%s subject=%s is_html=%s",
        to, cc or [], subject[:30], is_html,
    )

    # 跑在线程池里 — 不阻塞 event loop
    result = await asyncio.to_thread(
        _send_sync, to, subject, content, cc, is_html
    )
    logger.info("✅ 邮件发送成功: to=%s", to)
    return result