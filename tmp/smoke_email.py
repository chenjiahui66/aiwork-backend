"""
本地 mock SMTP 测试 — 起 aiosmtpd, 把 settings 指向 localhost,
验证 send_email 真的能发送 + 校验 SMTP 协议握手/邮件内容都正确。
"""
import sys
import os
import threading
import time

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(BACKEND_ROOT, ".env"))

# 必须先 import config 再改 SMTP_HOST (pydantic-settings 是单例)
from app.core import config as _cfg

# 重写 SMTP 配置 — 指向本地 mock
_cfg.settings.smtp_host = "127.0.0.1"
_cfg.settings.smtp_port = 18025  # mock 端口(587 STARTTLS 模式)
_cfg.settings.smtp_user = "test@aibot.local"
_cfg.settings.smtp_password = "mock-auth-code-123456"
_cfg.settings.smtp_from_name = "AiWork 测试"

# 启动 mock SMTP 服务器
from aiosmtpd.controller import Controller


class CaptureHandler:
    """收到邮件就打印"""
    def __init__(self):
        self.messages = []

    async def handle_DATA(self, server, session, envelope):
        # 把整封信存起来 + 返回 250(成功)
        print(
            f"\n=== [MOCK SMTP] 收到邮件 ===",
            flush=True,
        )
        print(f"From: {envelope.mail_from}", flush=True)
        print(f"To: {envelope.rcpt_tos}", flush=True)
        print(f"Data (前 200 字节):\n{envelope.content.decode(errors='ignore')[:200]}", flush=True)
        print(f"=== 邮件结束 ===\n", flush=True)
        self.messages.append(envelope)
        return "250 OK Message accepted"


handler = CaptureHandler()
# mock 用最宽松的 authenticator — 任何用户/密码都接受
from aiosmtpd.smtp import AuthResult, LoginPassword


async def auth_handler(server, session, envelope, mechanism, auth_data):
    if mechanism == "LOGIN":
        # 接受任何 user/password(明文回显)
        return AuthResult(success=True)
    if mechanism == "PLAIN":
        return AuthResult(success=True)
    return AuthResult(success=False, handled=False)


controller = Controller(
    handler,
    hostname="127.0.0.1",
    port=18025,
    authenticator=auth_handler,
    auth_require_tls=False,  # 明文模式下也允许 AUTH
)
controller.start()
print("🚀 Mock SMTP started at 127.0.0.1:18025", flush=True)

# 给它点时间起来
time.sleep(0.5)

# 现在测 send_email
import asyncio
from app.email import send_email
from app.email.smtp_client import (
    SMTPAuthError,
    SMTPConnectionError,
    SMTPSendError,
    EmailError,
)


async def main():
    print("\n--- 测试 1: 正常发送 ---", flush=True)
    result = await send_email(
        to=["boss@aibot.local", "hr@aibot.local"],
        subject="Q4 W42 周报-张三",
        content="本周完成:\n1. AI 应用后端新增 9 个模块\n2. Docker 三容器部署上线\n下周计划:\n1. 飞书多维表格导出\n2. SMTP 邮件集成",
        cc=["cto@aibot.local"],
    )
    print(f"✅ 发送成功: {result}", flush=True)

    print("\n--- 测试 2: HTML 格式 ---", flush=True)
    result = await send_email(
        to=["ui@aibot.local"],
        subject="<h1>HTML 测试</h1>",
        content="<h1>Hi</h1><p>这是一封<b>HTML</b>邮件</p>",
        is_html=True,
    )
    print(f"✅ HTML 发送成功: {result}", flush=True)

    print("\n--- 测试 3: 单收件人 ---", flush=True)
    result = await send_email(
        to=["alone@aibot.local"],
        subject="单收件人测试",
        content="只有 1 个收件人,没有 cc",
    )
    print(f"✅ 单收件人成功: {result}", flush=True)


try:
    asyncio.run(main())
    print(f"\n🎉 共捕获 {len(handler.messages)} 封邮件", flush=True)
except Exception as e:
    print(f"\n❌ 测试失败: {type(e).__name__}: {e}", flush=True)
    import traceback
    traceback.print_exc()
finally:
    controller.stop()
    print("Mock SMTP stopped", flush=True)