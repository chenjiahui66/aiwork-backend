"""
Playwright JS 渲染器 - 对 SPA 页面执行 JavaScript 后再解析

用途:
  - 对 Vite/React/Nuxt 等 CSR 站，httpx 只拿到空壳 <div id="app"></div>
  - Playwright 启动 headless Chromium，等 JS 渲染完再取 HTML
  - 作为 crawler.py 的可选渲染后端

浏览器优先级:
  1. Playwright 自带 Chromium（需 playwright install chromium）
  2. 系统安装的 Chrome（channel="chrome"）
  3. 系统安装的 Edge（channel="msedge"）
  后两者免下载，公司网环境下推荐用。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RendererConfig:
    """渲染器配置"""
    headless: bool = True
    wait_seconds: float = 2.0        # 等待 JS 渲染的时间（秒）
    timeout: float = 15.0            # 页面加载超时
    user_agent: str = "AiWorkCrawler/1.0 (practice bot)"
    browser: str = "auto"            # auto | chromium | chrome | msedge
    auto_scroll: bool = True         # 是否自动滚动触发懒加载


# 系统浏览器可执行文件路径（Windows）
_SYSTEM_BROWSER_PATHS = {
    "chrome": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ],
    "msedge": [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ],
}


def _find_system_browser(kind: str) -> str | None:
    """在常见安装路径里找系统浏览器 exe"""
    import os
    for path in _SYSTEM_BROWSER_PATHS.get(kind, []):
        if os.path.exists(path):
            return path
    return None


class PlaywrightRenderer:
    """
    Playwright headless 浏览器渲染器

    用法:
        renderer = PlaywrightRenderer(RendererConfig())
        with renderer:
            html = renderer.render("https://www.example.com")
    """

    def __init__(self, config: RendererConfig):
        self.cfg = config
        self._playwright = None
        self._browser = None
        self._browser_kind = ""

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()

    def start(self) -> None:
        """启动 Playwright + 浏览器（优先自带 Chromium，失败则回退系统 Chrome/Edge）"""
        try:
            from playwright.sync_api import sync_playwright
            self._playwright = sync_playwright().start()
        except ImportError:
            raise RuntimeError(
                "playwright 未安装。请运行: pip install playwright"
            )

        # 候选顺序：自带 Chromium → 系统 Chrome → 系统 Edge
        candidates: list[tuple[str, str | None]] = []
        if self.cfg.browser in ("auto", "chromium"):
            candidates.append(("chromium", None))
        if self.cfg.browser in ("auto", "chrome"):
            candidates.append(("chrome", None))
        if self.cfg.browser in ("auto", "msedge"):
            candidates.append(("msedge", None))

        last_error: Exception | None = None
        for kind, executable in candidates:
            try:
                kwargs = {"headless": self.cfg.headless}
                if executable:
                    kwargs["executable_path"] = executable
                else:
                    kwargs["channel"] = kind if kind != "chromium" else None
                    if kind == "chromium":
                        kwargs.pop("channel")

                self._browser = self._playwright.chromium.launch(**kwargs)
                self._browser_kind = kind
                logger.info("浏览器已启动: %s", kind)
                return
            except Exception as e:
                last_error = e
                logger.debug("启动 %s 失败: %s", kind, e)

        # 全部候选失败 → 尝试直接指定系统浏览器 exe 路径
        for kind in ("chrome", "msedge"):
            exe = _find_system_browser(kind)
            if not exe:
                continue
            try:
                self._browser = self._playwright.chromium.launch(
                    headless=self.cfg.headless,
                    executable_path=exe,
                )
                self._browser_kind = f"{kind} (系统安装: {exe})"
                logger.info("浏览器已启动: %s", self._browser_kind)
                return
            except Exception as e:
                last_error = e
                logger.debug("启动系统 %s 失败: %s", kind, e)

        self._playwright.stop()
        self._playwright = None
        raise RuntimeError(
            f"浏览器启动失败: {last_error}\n"
            "解决方式:\n"
            "  1) 运行 `playwright install chromium` 下载自带浏览器（需外网）\n"
            "  2) 装系统版 Chrome 或 Edge（Windows 自带 Edge），代码会自动探测"
        )

    def stop(self) -> None:
        """关闭浏览器 + Playwright"""
        if self._browser:
            try:
                self._browser.close()
            except Exception:
                pass
            self._browser = None
        if self._playwright:
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._playwright = None
        logger.info("浏览器已关闭")

    def render(self, url: str) -> str | None:
        """
        渲染单个 URL，返回完整 HTML

        Args:
            url: 页面 URL

        Returns:
            渲染后的 HTML 字符串，失败返回 None
        """
        if not self._browser:
            logger.error("浏览器未启动，请先调用 start() 或用 with 语句")
            return None

        try:
            page = self._browser.new_page(
                user_agent=self.cfg.user_agent,
            )
            page.goto(url, timeout=self.cfg.timeout * 1000, wait_until="domcontentloaded")

            # 等 JS 渲染
            page.wait_for_timeout(self.cfg.wait_seconds * 1000)

            # 尝试等网络空闲（异步接口返回后才渲染完整）
            try:
                page.wait_for_load_state("networkidle", timeout=self.cfg.timeout * 1000)
            except Exception:
                logger.debug("networkidle 超时, 继续用当前 DOM: %s", url)

            # 自动滚动到底，触发懒加载 / IntersectionObserver 渲染
            if self.cfg.auto_scroll:
                self._auto_scroll(page)

            # 取渲染后 HTML
            html = page.content()
            page.close()

            logger.debug("渲染成功: %s (%d chars)", url, len(html))
            return html

        except Exception as e:
            logger.warning("渲染失败 %s: %s", url, e)
            return None

    def _auto_scroll(self, page) -> None:
        """滚动到底再回到顶部，触发懒加载内容渲染"""
        try:
            page.evaluate("""
                async () => {
                    const step = window.innerHeight;
                    const max = document.body.scrollHeight;
                    for (let y = 0; y < max; y += step) {
                        window.scrollTo(0, y);
                        await new Promise(r => setTimeout(r, 200));
                    }
                    window.scrollTo(0, 0);
                }
            """)
            # 滚完再等一下，让最后一次渲染落地
            page.wait_for_timeout(500)
        except Exception as e:
            logger.debug("自动滚动失败(忽略): %s", e)
