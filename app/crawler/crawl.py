"""
爬虫 CLI 入口 - 独立脚本，可直接运行

用法:
    # 基本用法（爬 1 层深度）
    python -m app.crawler.crawl https://www.example.com

    # 指定深度 + 输出文件
    python -m app.crawler.crawl https://www.example.com --depth 2 --output results.json

    # 不遵守 robots.txt（自己的站可以）
    python -m app.crawler.crawl https://www.example.com --depth 3 --no-robots

    # 限制最大页面数 + 调慢延迟
    python -m app.crawler.crawl https://www.example.com --depth 2 --max-pages 30 --delay 1.0 3.0

    # 也可以直接当脚本跑
    python app/crawler/crawl.py https://www.example.com --depth 1
"""
from __future__ import annotations

import argparse
import logging
import sys

from app.crawler.crawler import Crawler, CrawlConfig


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="crawl",
        description="AiWork 爬虫 - 广度优先 + 深度控制 + robots.txt",
    )
    p.add_argument("url", help="起始 URL，如 https://www.example.com")
    p.add_argument("--depth", type=int, default=1, help="爬取深度（0=只爬起始页，默认1）")
    p.add_argument("--max-pages", type=int, default=50, help="最多爬取页数（默认50）")
    p.add_argument("--delay", type=float, nargs=2, metavar=("MIN", "MAX"),
                    default=[0.5, 1.5], help="请求间隔秒数范围（默认 0.5 1.5）")
    p.add_argument("--timeout", type=float, default=15.0, help="单次请求超时秒数（默认15）")
    p.add_argument("--no-robots", action="store_true", help="不遵守 robots.txt")
    p.add_argument("--output", "-o", default="", help="JSON 结果输出路径")
    p.add_argument("--verbose", "-v", action="store_true", help="显示 DEBUG 日志")
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)

    # 日志
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # 校验 URL
    url = args.url
    if not url.startswith("http"):
        url = f"https://{url}"

    config = CrawlConfig(
        start_url=url,
        max_depth=args.depth,
        max_pages=args.max_pages,
        delay_min=args.delay[0],
        delay_max=args.delay[1],
        timeout=args.timeout,
        respect_robots=not args.no_robots,
        output_path=args.output,
    )

    crawler = Crawler(config)
    result = crawler.run()

    # 打印摘要
    print("\n" + "=" * 60)
    print(f"  爬取完成: {result.config.start_url}")
    print(f"  页面数:   {len(result.pages)}")
    print(f"  跳过数:   {len(result.skipped)}")
    print(f"  错误数:   {len(result.errors)}")
    print(f"  耗时:     {result.total_time:.1f}s")
    print("=" * 60)

    # 打印每个页面概览
    for i, page in enumerate(result.pages, 1):
        print(f"\n--- 第 {i} 页 ---")
        print(f"  URL:    {page.url}")
        print(f"  标题:   {page.title or '(无)'}")
        print(f"  描述:   {page.meta_description[:80] or '(无)'}")
        print(f"  字数:   {page.word_count}")
        print(f"  内链:   {len(page.links)} 条")
        print(f"  图片:   {len(page.images)} 张")
        if page.og_tags:
            print(f"  OG:     {', '.join(page.og_tags.keys())}")

    if result.errors:
        print("\n⚠ 错误详情:")
        for err in result.errors:
            print(f"  {err['url']}: {err['error']}")

    if config.output_path:
        print(f"\n✅ 结果已保存: {config.output_path}")


if __name__ == "__main__":
    main()
