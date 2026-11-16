"""
核心爬虫 - BFS 广度优先 + 深度控制 + 礼貌延迟 + robots.txt

设计要点:
  - 用 httpx 同步客户端（简单直接，练手不需要异步）
  - BFS 按深度层推进，每层可配置最大页面数
  - 自动尊重 robots.txt（可关闭）
  - 两次请求之间随机延迟，避免压垮目标站
  - 解析 sitemap.xml 发现更多 URL
"""
from __future__ import annotations

import json
import logging
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse, urljoin

import httpx
from bs4 import BeautifulSoup

from app.crawler.parsers import ParsedPage, parse_html, extract_internal_links

logger = logging.getLogger(__name__)


@dataclass
class CrawlConfig:
    """爬虫配置"""
    start_url: str = ""
    max_depth: int = 2               # 爬取深度（0 = 只爬起始页）
    max_pages: int = 50              # 最多爬多少页
    delay_min: float = 0.5           # 请求间隔下限（秒）
    delay_max: float = 1.5           # 请求间隔上限（秒）
    timeout: float = 15.0            # 单次请求超时（秒）
    respect_robots: bool = True       # 是否遵守 robots.txt
    user_agent: str = "AiWorkCrawler/1.0 (practice bot)"
    output_path: str = ""            # JSON 结果输出路径


@dataclass
class CrawlResult:
    """爬取结果汇总"""
    config: CrawlConfig
    pages: list[ParsedPage] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)      # 被跳过的 URL（robots/错误）
    errors: list[dict[str, str]] = field(default_factory=list)  # [{url, error}]
    total_time: float = 0.0

    def to_dict(self) -> dict:
        return {
            "start_url": self.config.start_url,
            "max_depth": self.config.max_depth,
            "max_pages": self.config.max_pages,
            "pages_crawled": len(self.pages),
            "pages_skipped": len(self.skipped),
            "errors": len(self.errors),
            "total_time_seconds": round(self.total_time, 2),
            "pages": [p.to_dict() for p in self.pages],
            "skipped": self.skipped,
            "error_details": self.errors,
        }


class Crawler:
    """
    礼貌型 BFS 爬虫

    用法:
        cfg = CrawlConfig(start_url="https://www.example.com", max_depth=2)
        crawler = Crawler(cfg)
        result = crawler.run()
    """

    def __init__(self, config: CrawlConfig):
        self.cfg = config
        self.result = CrawlResult(config=config)
        self._visited: set[str] = set()
        self._robots_disallowed: set[str] = set()

    # ---- robots.txt ----

    def _fetch_robots(self, client: httpx.Client, root_url: str) -> None:
        """
        简易 robots.txt 解析（只看 Disallow，不处理 Allow/爬取延迟等）
        练手足够，生产请用 robotparser 模块
        """
        parsed = urlparse(root_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        try:
            resp = client.get(robots_url, timeout=self.cfg.timeout)
            if resp.status_code != 200:
                logger.info("robots.txt 不存在或不可读 (%d), 跳过", resp.status_code)
                return

            lines = resp.text.splitlines()
            # 简单解析：只关心 User-agent: * 的 Disallow
            in_wildcard = False
            for line in lines:
                line = line.strip()
                if line.startswith("#") or not line:
                    continue
                if line.lower().startswith("user-agent:"):
                    agent = line.split(":", 1)[1].strip()
                    in_wildcard = (agent == "*")
                elif in_wildcard and line.lower().startswith("disallow:"):
                    path = line.split(":", 1)[1].strip()
                    if path:
                        disallow_url = f"{parsed.scheme}://{parsed.netloc}{path}"
                        self._robots_disallowed.add(disallow_url)

            logger.info("robots.txt: 解析到 %d 条 Disallow 规则", len(self._robots_disallowed))

        except Exception as e:
            logger.warning("读取 robots.txt 失败: %s", e)

    def _is_allowed(self, url: str) -> bool:
        """检查 URL 是否被 robots.txt 禁止"""
        if not self.cfg.respect_robots:
            return True
        for disallow in self._robots_disallowed:
            if url.startswith(disallow):
                return False
        return True

    # ---- sitemap.xml ----

    def _fetch_sitemap_urls(self, client: httpx.Client, root_url: str) -> list[str]:
        """
        从 sitemap.xml 提取所有 <loc> URL
        """
        parsed = urlparse(root_url)
        sitemap_url = f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"
        try:
            resp = client.get(sitemap_url, timeout=self.cfg.timeout)
            if resp.status_code != 200:
                logger.info("sitemap.xml 不存在 (%d), 跳过", resp.status_code)
                return []

            soup = BeautifulSoup(resp.text, "xml")
            urls = []
            for loc in soup.find_all("loc"):
                url = loc.get_text(strip=True)
                if url.startswith("http"):
                    urls.append(url)
            logger.info("sitemap.xml: 发现 %d 个 URL", len(urls))
            return urls

        except Exception as e:
            logger.warning("读取 sitemap.xml 失败: %s", e)
            return []

    # ---- 单页抓取 ----

    def _fetch_page(self, client: httpx.Client, url: str) -> ParsedPage | None:
        """抓取并解析单个页面"""
        try:
            resp = client.get(url, timeout=self.cfg.timeout, follow_redirects=True)
            resp.raise_for_status()

            # 只处理 HTML
            ct = resp.headers.get("content-type", "")
            if "text/html" not in ct and "application/xhtml" not in ct:
                logger.debug("跳过非 HTML 页面: %s (%s)", url, ct)
                return None

            return parse_html(resp.text, str(resp.url))

        except httpx.HTTPStatusError as e:
            err = f"HTTP {e.response.status_code}"
            logger.warning("抓取失败 %s: %s", url, err)
            self.result.errors.append({"url": url, "error": err})
            return None
        except Exception as e:
            err = str(e)[:200]
            logger.warning("抓取异常 %s: %s", url, err)
            self.result.errors.append({"url": url, "error": err})
            return None

    # ---- BFS 主循环 ----

    def run(self) -> CrawlResult:
        """
        执行爬取，返回 CrawlResult

        流程:
          1. 初始化 httpx 客户端
          2. 读取 robots.txt
          3. 读取 sitemap.xml 补 URL 池
          4. BFS 按深度推进，每层抓取后提取内链加入下一层
          5. 保存 JSON 结果
        """
        start = time.time()
        root_domain = urlparse(self.cfg.start_url).netloc
        logger.info("开始爬取 %s (depth=%d, max_pages=%d)",
                     self.cfg.start_url, self.cfg.max_depth, self.cfg.max_pages)

        with httpx.Client(
            headers={"User-Agent": self.cfg.user_agent},
            follow_redirects=True,
        ) as client:

            # robots.txt
            if self.cfg.respect_robots:
                self._fetch_robots(client, self.cfg.start_url)

            # sitemap 补 URL
            sitemap_urls = self._fetch_sitemap_urls(client, self.cfg.start_url)

            # BFS 队列: [(url, depth), ...]
            queue: list[tuple[str, int]] = [(self.cfg.start_url, 0)]
            for url in sitemap_urls:
                if urlparse(url).netloc == root_domain:
                    queue.append((url, 1))  # sitemap 里的算 depth=1

            while queue and len(self.result.pages) < self.cfg.max_pages:
                url, depth = queue.pop(0)

                # 去重
                if url in self._visited:
                    continue
                self._visited.add(url)

                # 深度限制
                if depth > self.cfg.max_depth:
                    continue

                # robots.txt 检查
                if not self._is_allowed(url):
                    self.result.skipped.append(url)
                    logger.debug("robots.txt 禁止: %s", url)
                    continue

                # 礼貌延迟
                if self.result.pages:  # 第一次不延迟
                    delay = random.uniform(self.cfg.delay_min, self.cfg.delay_max)
                    time.sleep(delay)

                # 抓取 + 解析
                logger.info("[%d/%d] depth=%d  %s",
                            len(self.result.pages) + 1, self.cfg.max_pages, depth, url)
                page = self._fetch_page(client, url)

                if page is None:
                    continue

                self.result.pages.append(page)

                # 提取内链，加入下一层队列
                if depth < self.cfg.max_depth:
                    internal = extract_internal_links(page, root_domain)
                    for link in internal:
                        if link not in self._visited:
                            queue.append((link, depth + 1))

        self.result.total_time = time.time() - start
        logger.info("爬取完成: %d 页, %d 跳过, %d 错误, 耗时 %.1fs",
                     len(self.result.pages), len(self.result.skipped),
                     len(self.result.errors), self.result.total_time)

        # 保存结果
        if self.cfg.output_path:
            self._save_json()

        return self.result

    # ---- 输出 ----

    def _save_json(self) -> None:
        path = Path(self.cfg.output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = self.result.to_dict()
        # 确保 JSON 序列化时中文不转义
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("结果已保存: %s (%d bytes)", path, path.stat().st_size)
