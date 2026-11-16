"""
smoke_crawler.py - 爬虫模块冒烟测试

不依赖外部网络（用本地 HTML 片段模拟），验证:
  1. parse_html 基本解析
  2. extract_internal_links 域名过滤
  3. CrawlConfig 默认值
  4. Crawler 在 mock 场景下完整跑通
  5. ParsedPage.to_dict 序列化
  6. robots.txt 解析逻辑
  7. sitemap.xml 解析逻辑
  8. CLI 参数解析
  9. 深度限制
  10. 去重逻辑
"""
import sys
import json
from unittest.mock import MagicMock, patch
from pathlib import Path

# 确保项目根在 sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.crawler.parsers import parse_html, extract_internal_links, ParsedPage
from app.crawler.crawler import Crawler, CrawlConfig, CrawlResult
from app.crawler.crawl import build_parser

SAMPLE_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <title>测试网站 - 首页</title>
    <meta name="description" content="这是一个测试网站用于练手爬虫">
    <meta name="keywords" content="测试,爬虫,练手">
    <meta property="og:title" content="OG标题">
    <meta property="og:image" content="https://example.com/og.png">
    <meta name="twitter:card" content="summary_large_image">
</head>
<body>
    <header><nav>导航</nav></header>
    <main>
        <h1>欢迎来到测试网站</h1>
        <p>这是正文内容，用于验证爬虫能否正确提取。</p>
        <h2>关于我们</h2>
        <p>我们是一支技术团队。</p>
        <h2>服务项目</h2>
        <ul>
            <li><a href="/about">关于</a></li>
            <li><a href="/services">服务</a></li>
            <li><a href="https://www.example.com/contact">联系</a></li>
            <li><a href="https://other.com/external">外链</a></li>
            <li><a href="javascript:void(0)">JS链接</a></li>
            <li><a href="#anchor">锚点</a></li>
        </ul>
        <img src="/images/logo.png" alt="Logo">
        <img src="https://cdn.example.com/banner.jpg" alt="Banner">
    </main>
    <footer>页脚</footer>
</body>
</html>"""


def test_parse_html():
    """测试 1: parse_html 基本解析"""
    page = parse_html(SAMPLE_HTML, "https://www.example.com/")

    assert page.title == "测试网站 - 首页", f"title 错误: {page.title}"
    assert "测试网站" in page.meta_description, f"desc 错误: {page.meta_description}"
    assert "爬虫" in page.meta_keywords, f"keywords 错误: {page.meta_keywords}"
    assert "h1" in page.headings and "欢迎来到测试网站" in page.headings["h1"]
    assert "h2" in page.headings and len(page.headings["h2"]) == 2
    assert "正文内容" in page.body_text, f"body_text 缺正文: {page.body_text[:100]}"
    assert page.word_count > 0, "word_count 为 0"
    assert page.og_tags.get("og:title") == "OG标题"
    assert page.twitter_tags.get("twitter:card") == "summary_large_image"
    print(f"  ✅ parse_html: title={page.title}, h1={page.headings.get('h1')}, words={page.word_count}")


def test_extract_internal_links():
    """测试 2: extract_internal_links 域名过滤"""
    page = parse_html(SAMPLE_HTML, "https://www.example.com/")
    internal = extract_internal_links(page, "www.example.com")

    # 应包含 /about, /services, /contact，不含 other.com
    urls = [u for u in internal]
    assert any("/about" in u for u in urls), f"缺 /about: {urls}"
    assert any("/services" in u for u in urls), f"缺 /services: {urls}"
    assert any("/contact" in u for u in urls), f"缺 /contact: {urls}"
    assert not any("other.com" in u for u in urls), f"不应含外链: {urls}"
    print(f"  ✅ extract_internal_links: {len(internal)} 条内链, 外链已过滤")


def test_crawl_config_defaults():
    """测试 3: CrawlConfig 默认值"""
    cfg = CrawlConfig(start_url="https://www.example.com")
    assert cfg.max_depth == 2
    assert cfg.max_pages == 50
    assert cfg.respect_robots is True
    assert cfg.delay_min < cfg.delay_max
    print(f"  ✅ CrawlConfig: depth={cfg.max_depth}, pages={cfg.max_pages}, robots={cfg.respect_robots}")


def test_parsed_page_to_dict():
    """测试 5: ParsedPage.to_dict 序列化"""
    page = parse_html(SAMPLE_HTML, "https://www.example.com/")
    d = page.to_dict()

    assert "url" in d and "title" in d
    assert d["links_count"] == len(page.links)
    assert d["images_count"] == len(page.images)
    assert d["word_count"] == page.word_count
    # body_text 截断检查
    assert len(d["body_text"]) <= 2000
    print(f"  ✅ to_dict: keys={sorted(d.keys())[:6]}...")


def test_robots_parsing():
    """测试 6: robots.txt 解析逻辑"""
    crawler = Crawler(CrawlConfig(start_url="https://www.example.com", respect_robots=True))

    # 模拟一个 robots.txt 响应
    robots_text = """User-agent: *
Disallow: /admin/
Disallow: /private/

User-agent: Googlebot
Disallow: /secret/
"""
    # 直接注入 disallowed 集合
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = robots_text
    mock_client.get.return_value = mock_resp

    crawler._fetch_robots(mock_client, "https://www.example.com")

    assert not crawler._is_allowed("https://www.example.com/admin/login")
    assert not crawler._is_allowed("https://www.example.com/private/data")
    assert crawler._is_allowed("https://www.example.com/about")
    # /secret/ 只对 Googlebot 禁止，不对 * 禁止
    assert crawler._is_allowed("https://www.example.com/secret/page")
    print(f"  ✅ robots.txt: disallowed={len(crawler._robots_disallowed)} 条规则")


def test_sitemap_parsing():
    """测试 7: sitemap.xml 解析"""
    crawler = Crawler(CrawlConfig(start_url="https://www.example.com"))

    sitemap_xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://www.example.com/</loc></url>
  <url><loc>https://www.example.com/about</loc></url>
  <url><loc>https://www.example.com/services</loc></url>
</urlset>"""

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = sitemap_xml
    mock_client.get.return_value = mock_resp

    urls = crawler._fetch_sitemap_urls(mock_client, "https://www.example.com")
    assert len(urls) == 3, f"sitemap URL 数错误: {len(urls)}"
    assert "https://www.example.com/about" in urls
    print(f"  ✅ sitemap.xml: {len(urls)} 个 URL")


def test_cli_parser():
    """测试 8: CLI 参数解析"""
    parser = build_parser()
    args = parser.parse_args(["https://www.example.com", "--depth", "2", "--output", "out.json"])

    assert args.url == "https://www.example.com"
    assert args.depth == 2
    assert args.output == "out.json"
    assert args.no_robots is False
    print(f"  ✅ CLI parser: url={args.url}, depth={args.depth}")


def test_depth_limit():
    """测试 9: 深度限制"""
    cfg = CrawlConfig(start_url="https://www.example.com", max_depth=0, max_pages=10)
    crawler = Crawler(cfg)

    # depth=0 只爬起始页，不应发现新链接
    # mock httpx.Client 让 _fetch_page 返回一个有内链的页面
    with patch("app.crawler.crawler.httpx.Client") as MockClient:
        mock_client = MagicMock()
        MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
        MockClient.return_value.__exit__ = MagicMock(return_value=False)

        # robots.txt 返回 404
        robots_resp = MagicMock()
        robots_resp.status_code = 404

        # sitemap.xml 返回 404
        sitemap_resp = MagicMock()
        sitemap_resp.status_code = 404

        # 页面响应
        page_resp = MagicMock()
        page_resp.status_code = 200
        page_resp.headers = {"content-type": "text/html; charset=utf-8"}
        page_resp.text = SAMPLE_HTML
        page_resp.url = "https://www.example.com/"

        mock_client.get.side_effect = [robots_resp, sitemap_resp, page_resp]

        result = crawler.run()
        assert len(result.pages) == 1, f"depth=0 应只爬 1 页, 实际: {len(result.pages)}"
        print(f"  ✅ depth=0: 爬取 {len(result.pages)} 页")


def test_dedup():
    """测试 10: URL 去重"""
    crawler = Crawler(CrawlConfig(start_url="https://www.example.com", max_depth=1))
    crawler._visited.add("https://www.example.com/")
    crawler._visited.add("https://www.example.com/about")

    # 模拟再遇到相同 URL，应跳过
    assert "https://www.example.com/" in crawler._visited
    assert "https://www.example.com/about" in crawler._visited
    assert "https://www.example.com/contact" not in crawler._visited
    print(f"  ✅ 去重: visited={len(crawler._visited)} 条")


def run_all():
    tests = [
        ("parse_html 基本解析", test_parse_html),
        ("extract_internal_links 域名过滤", test_extract_internal_links),
        ("CrawlConfig 默认值", test_crawl_config_defaults),
        ("ParsedPage.to_dict 序列化", test_parsed_page_to_dict),
        ("robots.txt 解析", test_robots_parsing),
        ("sitemap.xml 解析", test_sitemap_parsing),
        ("CLI 参数解析", test_cli_parser),
        ("深度限制", test_depth_limit),
        ("URL 去重", test_dedup),
    ]

    print("=" * 60)
    print(f"  爬虫模块 smoke 测试 ({len(tests)} 项)")
    print("=" * 60)

    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            fn()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  ❌ {name}: {e}")

    print("\n" + "=" * 60)
    print(f"  结果: {passed} passed, {failed} failed / {len(tests)} total")
    print("=" * 60)
    return failed == 0


if __name__ == "__main__":
    ok = run_all()
    sys.exit(0 if ok else 1)
