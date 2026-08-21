"""
飞书鉴权 — tenant_access_token

- 凭证有效期 2 小时
- 模块内缓存 + 自动刷新
- 失败时清缓存重试一次

文档: https://open.feishu.cn/document/server-docs/authentication-management/access-token/tenant_access_token_internal
"""
import asyncio
import logging
import time

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_BASE = "https://open.feishu.cn/open-apis"

# 模块级缓存 — 进程内所有调用复用同一个
_token: str | None = None
_expires_at: float = 0.0
_lock = asyncio.Lock()


def feishu_configured() -> bool:
    return settings.feishu_configured


async def get_tenant_access_token(force_refresh: bool = False) -> str:
    """
    拿 tenant_access_token,2 小时缓存。
    - force_refresh=True: 无视缓存,重新拿(用于 401 后重试)
    """
    global _token, _expires_at

    # 简单过期判定(留 60 秒 buffer)
    if not force_refresh and _token and time.time() < _expires_at - 60:
        return _token

    async with _lock:
        # 双检 — 别的协程可能已经刷新过了
        if not force_refresh and _token and time.time() < _expires_at - 60:
            return _token

        logger.info("🔑 飞书: 申请 tenant_access_token")
        try:
            async with httpx.AsyncClient(timeout=settings.feishu_timeout) as client:
                resp = await client.post(
                    f"{_BASE}/auth/v3/tenant_access_token/internal",
                    json={
                        "app_id": settings.feishu_app_id,
                        "app_secret": settings.feishu_app_secret,
                    },
                )
            data = resp.json()
        except httpx.HTTPError as e:
            logger.exception("飞书鉴权请求失败")
            raise RuntimeError(f"飞书鉴权请求失败: {e}") from e

        if data.get("code") != 0:
            raise RuntimeError(
                f"飞书鉴权失败: code={data.get('code')} msg={data.get('msg')}"
            )

        _token = data["tenant_access_token"]
        # expire 一般是 7200 秒 — 减 60 秒 buffer
        _expires_at = time.time() + int(data.get("expire", 7200)) - 60
        logger.info("✅ 飞书: 拿到新 token, 有效期 %ds", int(_expires_at - time.time()))
        return _token


def reset_token_cache() -> None:
    """清掉缓存 — 主要给测试用"""
    global _token, _expires_at
    _token = None
    _expires_at = 0