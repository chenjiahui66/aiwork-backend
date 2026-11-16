"""
HTML 解析器 - 从网页中提取结构化信息

功能:
  - 标题 / meta 描述 / 关键词
  - 所有层级标题 (h1~h6)
  - 正文纯文本（去标签）
  - 页内链接（a href）+ 图片（img src）
  - Open Graph / Twitter Card 元数据
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag


@dataclass
class ParsedPage:
    """单页解析结果"""
    url: str
    title: str = ""
    meta_description: str = ""
    meta_keywords: str = ""
    headings: dict[str, list[str]] = field(default_factory=dict)
    body_text: str = ""
    links: list[dict[str, str]] = field(default_factory=list)   # [{href, text}]
    images: list[dict[str, str]] = field(default_factory=list)  # [{src, alt}]
    og_tags: dict[str, str] = field(default_factory=dict)       # {og:title, og:image, ...}
    twitter_tags: dict[str, str] = field(default_factory=dict)
    word_count: int = 0

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "title": self.title,
            "meta_description": self.meta_description,
            "meta_keywords": self.meta_keywords,
            "headings": self.headings,
            "body_text": self.body_text[:2000],  # 截断，避免 JSON 过大
            "links_count": len(self.links),
            "links": self.links[:50],            # 最多保留 50 条链接
            "images_count": len(self.images),
            "images": self.images[:30],
            "og_tags": self.og_tags,
            "twitter_tags": self.twitter_tags,
            "word_count": self.word_count,
        }


def _normalize_whitespace(text: str) -> str:
    """把连续空白压缩成单个空格，strip 首尾"""
    return re.sub(r"\s+", " ", text).strip()


def parse_html(html: str, base_url: str) -> ParsedPage:
    """
    解析 HTML 文档，返回结构化 ParsedPage

    Args:
        html:    原始 HTML 字符串
        base_url: 页面 URL（用于把相对链接转成绝对链接）
    """
    soup = BeautifulSoup(html, "lxml")
    page = ParsedPage(url=base_url)

    # ---- 标题 ----
    if soup.title and soup.title.string:
        page.title = soup.title.string.strip()

    # ---- Meta ----
    for meta in soup.find_all("meta"):
        name = meta.get("name", "").lower()
        prop = meta.get("property", "").lower()
        content = meta.get("content", "")
        if not content:
            continue

        if name == "description":
            page.meta_description = content.strip()
        elif name == "keywords":
            page.meta_keywords = content.strip()
        elif prop.startswith("og:") or name.startswith("og:"):
            key = prop if prop.startswith("og:") else name
            page.og_tags[key] = content.strip()
        elif prop.startswith("twitter:") or name.startswith("twitter:"):
            key = prop if prop.startswith("twitter:") else name
            page.twitter_tags[key] = content.strip()

    # ---- Headings ----
    for level in range(1, 7):
        tag = f"h{level}"
        texts = []
        for h in soup.find_all(tag):
            t = _normalize_whitespace(h.get_text())
            if t:
                texts.append(t)
        if texts:
            page.headings[tag] = texts

    # ---- 正文 ----
    # 优先找 <main>/<article>，否则 fallback 到 <body>
    main_area = soup.find("main") or soup.find("article") or soup.body or soup
    # 只清 script/style 等非内容标签。
    # 注意：不能清 header/nav/footer —— 很多 SPA（如 Vite 构建）没有 <main>，
    # 内容全在 <div id="app"> 里，清掉这些标签会把正文和链接一起删光。
    for tag_name in ("script", "style", "noscript", "template"):
        for t in main_area.find_all(tag_name):
            t.decompose()
    page.body_text = _normalize_whitespace(main_area.get_text())
    page.word_count = len(page.body_text.split())

    # ---- 链接 ----
    # 从整个文档提取（main_area 可能已被清理，但链接不该因此丢失）
    for a in soup.find_all("a", href=True):
        href = str(a["href"])
        # 跳过锚点 / javascript:
        if href.startswith("#") or href.lower().startswith("javascript:"):
            continue
        abs_url = urljoin(base_url, href)
        text = _normalize_whitespace(a.get_text())[:100]
        page.links.append({"href": abs_url, "text": text})

    # ---- 图片 ----
    for img in soup.find_all("img", src=True):
        src = str(img["src"])
        abs_src = urljoin(base_url, src)
        alt = img.get("alt", "")
        page.images.append({"src": abs_src, "alt": alt})

    return page


def extract_internal_links(page: ParsedPage, root_domain: str) -> list[str]:
    """
    从 ParsedPage 中提取同域内链（去重、去 anchor）

    Args:
        root_domain: 目标域名，如 "www.example.com"
    """
    parsed_root = urlparse(f"https://{root_domain}")
    seen: set[str] = set()
    internal: list[str] = []

    for link in page.links:
        url = link["href"]
        parsed = urlparse(url)
        # 同域名 + http(s)
        if parsed.scheme in ("http", "https") and parsed.netloc == parsed_root.netloc:
            # 去掉 fragment，去重
            clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if parsed.query:
                clean += f"?{parsed.query}"
            if clean not in seen:
                seen.add(clean)
                internal.append(clean)

    return internal
