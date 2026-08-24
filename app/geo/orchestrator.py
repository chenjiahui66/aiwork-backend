"""
GEO Orchestrator — 12 步主控

串起所有 skill, 一次返回全量 GEO 内容包

调用顺序:
1. Research        (research.py)       — Step ①②
2. Outline         (outline.py)        — Step ⑦
3. Writer          (writer.py)         — Step ⑧⑨
4. Image Prompts   (image_prompt.py)   — Step ⑩⑪
5. Score           (score.py)          — 评分 + AI 搜索模拟
6. Platform Rewrite (platform.py)       — Step ⑫

中间步骤（④ 提取用户问题, ⑤ 分析缺口, ⑥ 实体分析）都内嵌在 Research + Outline 的 prompt 里
"""
import logging
from typing import AsyncIterator

from app.geo import (
    image_prompt,
    outline,
    platform,
    research,
    score,
    writer,
)

logger = logging.getLogger(__name__)


async def generate_geo_content(
    title: str,
    platform_name: str,
    style: str,
) -> AsyncIterator[dict]:
    """
    跑完整 GEO 流程, 流式 yield 进度事件

    事件类型:
    - {"type": "step", "step": 1, "name": "选题研究", "status": "start"}
    - {"type": "step", "step": 1, "name": "选题研究", "status": "done", "data": {...}}
    - {"type": "article", "content": "..."}     — 文章正文 (一次性完整输出)
    - {"type": "final", "data": {...完整结果...}}
    - {"type": "error", "message": "..."}
    """
    try:
        # ===== Step 1-2: Research =====
        yield {"type": "step", "step": 1, "name": "选题研究", "status": "start"}
        research_data = await research.run_research(title, platform_name, style)
        yield {"type": "step", "step": 1, "name": "选题研究", "status": "done"}

        # ===== Step 7: Outline =====
        yield {"type": "step", "step": 2, "name": "构建知识结构", "status": "start"}
        outline_data = await outline.build_outline(
            title=title,
            platform=platform_name,
            style=style,
            research=research_data,
        )
        yield {"type": "step", "step": 2, "name": "构建知识结构", "status": "done"}

        # ===== Step 8-9: Writer =====
        yield {"type": "step", "step": 3, "name": "AI 生成文章", "status": "start"}
        article_markdown = await writer.write_article(
            title=title,
            platform=platform_name,
            style=style,
            outline=outline_data,
            research=research_data,
        )
        yield {"type": "step", "step": 3, "name": "AI 生成文章", "status": "done"}

        # ===== Step 10-11: Image Prompts =====
        yield {"type": "step", "step": 4, "name": "生成配图 prompt", "status": "start"}
        image_data = await image_prompt.generate_image_prompts(
            title=title,
            platform=platform_name,
            outline=outline_data,
            research=research_data,
        )
        yield {"type": "step", "step": 4, "name": "生成配图 prompt", "status": "done"}

        # ===== Score: GEO 评分 + AI 搜索模拟 =====
        yield {"type": "step", "step": 5, "name": "GEO 质量评分", "status": "start"}
        score_data = await score.score_article(
            title=title,
            platform=platform_name,
            article_markdown=article_markdown,
            research=research_data,
        )
        yield {"type": "step", "step": 5, "name": "GEO 质量评分", "status": "done"}

        # ===== Step 12: 多平台改写 =====
        yield {"type": "step", "step": 6, "name": "多平台改写", "status": "start"}
        wechat_pack = await platform.rewrite_for_platform(
            platform="wechat",
            title=title,
            article_markdown=article_markdown,
            research=research_data,
        )
        xhs_pack = await platform.rewrite_for_platform(
            platform="xiaohongshu",
            title=title,
            article_markdown=article_markdown,
            research=research_data,
        )
        douyin_pack = await platform.rewrite_for_platform(
            platform="douyin",
            title=title,
            article_markdown=article_markdown,
            research=research_data,
        )
        yield {"type": "step", "step": 6, "name": "多平台改写", "status": "done"}

        # ===== Final: 组装全量结果 =====
        final_data = {
            "research": research_data,
            "outline": outline_data,
            "article": {
                "title": outline_data.get("title", title),
                "content": article_markdown,
                "word_count": len(article_markdown),
            },
            "geo_score": score_data,
            "images": image_data,
            "platform_pack": {
                "wechat": wechat_pack,
                "xiaohongshu": xhs_pack,
                "douyin": douyin_pack,
            },
        }

        yield {"type": "final", "data": final_data}
        yield {"type": "done"}

    except Exception as e:
        logger.exception("GEO orchestrator failed")
        yield {"type": "error", "message": f"流程异常: {e}"}