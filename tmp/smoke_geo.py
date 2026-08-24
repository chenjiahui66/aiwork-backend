"""
端到端 mock 测试 — GEO 内容智能体

策略: 用 unittest.mock 拦截 get_llm, 返回固定响应。
不真正调 LLM, 代码更紧凑 + 跑得快。

覆盖:
1. prompt 加载器 — 8 个 prompt 文件
2. research 模块 — JSON 解析 + fallback
3. orchestrator — 12 步全流程串联 (mock LLM)
4. /api/geo/health — 健康检查
5. /api/geo/generate — SSE 流式输出
"""
import sys
import os
import asyncio
import json
from unittest.mock import patch, MagicMock

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_ROOT)
from dotenv import load_dotenv

load_dotenv(os.path.join(BACKEND_ROOT, ".env"))

# === 配置 fake .env ===
from app.core import config as _cfg

_cfg.settings.minimax_api_key = "mock-api-key-for-smoke"


# ===== Mock LLM 响应数据 =====

MOCK_RESEARCH_JSON = {
    "hotspots": [
        "AI Agent — 2024-2025 最热赛道, 大厂纷纷布局",
        "AI 视频 — Sora/可灵引爆",
        "AI 编程 — Cursor/Claude Code",
    ],
    "faqs": [
        "AI 副业到底怎么赚钱？",
        "需要会编程吗？",
        "普通人能不能做？",
    ],
    "gaps": ["同质化严重", "缺真实案例", "缺数据"],
    "opportunities": ["加案例", "加成本分析", "加操作步骤"],
    "entities": {
        "entity": ["Claude Code", "Cursor"],
        "company": ["Anthropic", "OpenAI"],
        "category": ["AI 编程工具"],
        "related": ["Codex", "Windsurf"],
    },
}

MOCK_OUTLINE_JSON = {
    "title": "普通人如何用 AI 做副业（2026 实操指南）",
    "sections": [
        {
            "heading": "为什么 AI 副业现在是机会",
            "key_points": ["门槛低", "工具成熟"],
            "questions_to_answer": ["为什么是现在？"],
            "evidence_needed": ["数据"],
        },
        {
            "heading": "5 个真实可执行的 AI 副业",
            "key_points": ["案例1", "案例2"],
            "questions_to_answer": ["具体做什么？"],
            "evidence_needed": ["真实案例"],
        },
    ],
    "faq": [
        {"question": "需要会编程吗？", "answer_hint": "不需要"},
    ],
    "conclusion": "总结 + 3 条行动建议",
}

MOCK_ARTICLE = """# 普通人如何用 AI 做副业

## 为什么 AI 副业现在是机会

AI 工具已经成熟, 普通人也能上手。

## 5 个真实可执行的 AI 副业

案例 1: AI 写作
案例 2: AI 设计

## FAQ

### 需要会编程吗？
不需要。

## 行动建议

1. 立即开始
2. 选一个细分
3. 持续迭代
"""

MOCK_WECHAT_JSON = {
    "title": "普通人 AI 副业：2026 实操指南",
    "summary": "AI 副业门槛低、机会多, 5 个真实案例 + 操作步骤。",
    "geo_description": "AI 副业 2026 最新指南, 含 Claude Code、Cursor 等工具实操案例。",
    "content": MOCK_ARTICLE,
    "cover_suggestion": "简约封面, AI 元素",
}

MOCK_XHS_JSON = {
    "titles": ["2026 AI 副业 5 个真实案例", "AI 副业 0 基础入门", "..."],
    "content": "AI 副业怎么做？🌟 5 个真实案例分享 ✨\n\n1. AI 写作...",
    "tags": ["#AI副业", "#自媒体"],
    "cover_suggestion": "小红书风格封面",
}

MOCK_DOUYIN_JSON = {
    "title": "AI 副业 5 个真实案例",
    "cover_text": "AI 副业月入过万",
    "grid_copies": [{"index": i, "role": f"图{i}", "text": f"内容{i}"} for i in range(1, 10)],
    "caption": "AI 副业真实案例分享...",
    "tags": ["#AI"],
    "cover_suggestion": "抖音封面",
}

MOCK_IMAGE_JSON = {
    "cover_prompt": "Cover for AI 副业 article, minimalist, --ar 16:9 --style raw",
    "illustration_prompts": [
        {"section": "第1章", "info": "概念", "prompt": "Illustration 1, --ar 16:9 --style raw"},
        {"section": "第2章", "info": "案例", "prompt": "Illustration 2, --ar 16:9 --style raw"},
    ],
}

MOCK_SCORE_JSON = {
    "total_score": 82,
    "dimensions": [
        {"name": "实体明确度", "key": "entity_clarity", "score": 85, "comment": "好"},
        {"name": "主题覆盖", "key": "topic_coverage", "score": 80, "comment": "好"},
    ],
    "strengths": ["实体清晰", "FAQ 完整"],
    "weaknesses": ["案例可补充"],
    "suggestions": ["加 2 个真实案例"],
    "ai_search_test": [
        {"question": "AI 副业怎么做？", "likelihood": "high", "reason": "直接回答"},
    ],
}


def make_mock_llm():
    """返回一个 mock ChatOpenAI — 根据 prompt 关键词返回不同 JSON"""
    mock = MagicMock()

    async def mock_ainvoke(messages):
        # 把 system + user 合并成一段文本, 用关键词识别调用哪个 prompt
        if isinstance(messages, list) and len(messages) > 0:
            full_content = " ".join(
                (m.content if hasattr(m, "content") else str(m))
                for m in messages
            )
        else:
            full_content = str(messages)

        # 解析: system 含哪类关键词 → 返回对应 JSON
        # 用每条 prompt 独特的关键词识别, 避免误判
        if "Generative Engine Optimization" in full_content:
            data = MOCK_RESEARCH_JSON
        elif "构建文章的知识结构" in full_content:
            data = MOCK_OUTLINE_JSON
        elif "GEO 写作铁律" in full_content:
            data = MOCK_ARTICLE  # Markdown 文本
        elif "公众号爆款编辑" in full_content:
            data = MOCK_WECHAT_JSON
        elif "小红书爆款编辑" in full_content:
            data = MOCK_XHS_JSON
        elif "抖音图文爆款编辑" in full_content:
            data = MOCK_DOUYIN_JSON
        elif "AI 绘画 prompt 工程师" in full_content:
            data = MOCK_IMAGE_JSON
        elif "GEO 内容质量评估员" in full_content:
            data = MOCK_SCORE_JSON
        else:
            data = {"fallback": True, "matched_first_100": full_content[:100]}

        # 包装成 LangChain AIMessage-like 对象
        resp = MagicMock()
        resp.content = json.dumps(data, ensure_ascii=False) if isinstance(data, dict) else str(data)
        return resp

    mock.ainvoke = mock_ainvoke
    return mock


# ===== 测试 =====
def test_prompts_loaded():
    """测试 1: 8 个 prompt 文件能正常加载"""
    print("\n=== [测试 1] 加载 8 个 prompt 文件 ===")
    from app.geo.prompts_loader import validate_all, PROMPT_FILES
    validate_all()
    assert len(PROMPT_FILES) == 8, f"应 8 个, 实际 {len(PROMPT_FILES)}"
    print(f"  ✅ 通过 — {len(PROMPT_FILES)} 个 prompt 文件全加载")


def test_research_module():
    """测试 2: research 模块"""
    print("\n=== [测试 2] research.run_research ===")
    with patch("app.geo.research.get_llm", return_value=make_mock_llm()):
        from app.geo import research as r
        result = asyncio.run(r.run_research(
            title="普通人如何用 AI 做副业",
            platform="wechat",
            style="personal_ip",
        ))
    assert "hotspots" in result
    assert "faqs" in result
    assert "entities" in result
    assert len(result["hotspots"]) >= 1
    print(f"  ✅ 通过 — hotspots={len(result['hotspots'])}, faqs={len(result['faqs'])}, entities={len(result['entities'].get('entity', []))}")


def test_outline_module():
    """测试 3: outline 模块"""
    print("\n=== [测试 3] outline.build_outline ===")
    with patch("app.geo.outline.get_llm", return_value=make_mock_llm()):
        from app.geo import outline as o
        result = asyncio.run(o.build_outline(
            title="测试",
            platform="wechat",
            style="personal_ip",
            research=MOCK_RESEARCH_JSON,
        ))
    assert "title" in result
    assert "sections" in result
    assert "faq" in result
    print(f"  ✅ 通过 — title={result['title']}, sections={len(result['sections'])}")


def test_writer_module():
    """测试 4: writer 模块"""
    print("\n=== [测试 4] writer.write_article ===")
    with patch("app.geo.writer.get_llm", return_value=make_mock_llm()):
        from app.geo import writer as w
        result = asyncio.run(w.write_article(
            title="测试",
            platform="wechat",
            style="personal_ip",
            outline=MOCK_OUTLINE_JSON,
            research=MOCK_RESEARCH_JSON,
        ))
    assert isinstance(result, str)
    assert len(result) > 100
    print(f"  ✅ 通过 — 文章长度 {len(result)} 字符")


def test_image_prompt_module():
    """测试 5: image_prompt 模块"""
    print("\n=== [测试 5] image_prompt.generate_image_prompts ===")
    with patch("app.geo.image_prompt.get_llm", return_value=make_mock_llm()):
        from app.geo import image_prompt as ip
        result = asyncio.run(ip.generate_image_prompts(
            title="测试",
            platform="xiaohongshu",
            outline=MOCK_OUTLINE_JSON,
            research=MOCK_RESEARCH_JSON,
        ))
    assert "cover_prompt" in result
    assert "illustration_prompts" in result
    print(f"  ✅ 通过 — cover + {len(result['illustration_prompts'])} 配图")


def test_score_module():
    """测试 6: score 模块"""
    print("\n=== [测试 6] score.score_article ===")
    with patch("app.geo.score.get_llm", return_value=make_mock_llm()):
        from app.geo import score as s
        result = asyncio.run(s.score_article(
            title="测试",
            platform="wechat",
            article_markdown=MOCK_ARTICLE,
            research=MOCK_RESEARCH_JSON,
        ))
    assert "total_score" in result
    assert "dimensions" in result
    assert "ai_search_test" in result
    print(f"  ✅ 通过 — total_score={result['total_score']}, dimensions={len(result['dimensions'])}")


def test_platform_module():
    """测试 7: platform 模块三平台"""
    print("\n=== [测试 7] platform.rewrite_for_platform (3 平台) ===")
    with patch("app.geo.platform.get_llm", return_value=make_mock_llm()):
        from app.geo import platform as pl
        for p in ["wechat", "xiaohongshu", "douyin"]:
            result = asyncio.run(pl.rewrite_for_platform(
                platform=p,
                title="测试",
                article_markdown=MOCK_ARTICLE,
                research=MOCK_RESEARCH_JSON,
            ))
            assert result is not None
            print(f"  ✅ {p}: keys={list(result.keys())}")


def test_orchestrator_full_flow():
    """测试 8: orchestrator 12 步全流程"""
    print("\n=== [测试 8] orchestrator.generate_geo_content 全流程 ===")
    with patch("app.geo.orchestrator.research.get_llm", return_value=make_mock_llm()), \
         patch("app.geo.orchestrator.outline.get_llm", return_value=make_mock_llm()), \
         patch("app.geo.orchestrator.writer.get_llm", return_value=make_mock_llm()), \
         patch("app.geo.orchestrator.image_prompt.get_llm", return_value=make_mock_llm()), \
         patch("app.geo.orchestrator.score.get_llm", return_value=make_mock_llm()), \
         patch("app.geo.orchestrator.platform.get_llm", return_value=make_mock_llm()):
        from app.geo import orchestrator as o
        events = []

        async def collect():
            async for ev in o.generate_geo_content(
                title="普通人如何用 AI 做副业",
                platform_name="wechat",
                style="personal_ip",
            ):
                events.append(ev)

        asyncio.run(collect())

    step_events = [e for e in events if e.get("type") == "step"]
    final_events = [e for e in events if e.get("type") == "final"]
    done_events = [e for e in events if e.get("type") == "done"]
    error_events = [e for e in events if e.get("type") == "error"]

    print(f"  step 事件: {len(step_events)}")
    print(f"  final 事件: {len(final_events)}")
    print(f"  done 事件: {len(done_events)}")
    print(f"  error 事件: {len(error_events)}")

    assert len(step_events) >= 12, f"应至少 12 步, 实际 {len(step_events)}"
    assert len(final_events) == 1
    assert len(error_events) == 0

    final_data = final_events[0]["data"]
    assert "research" in final_data
    assert "article" in final_data
    assert "geo_score" in final_data
    assert "images" in final_data
    assert "platform_pack" in final_data
    assert final_data["article"]["word_count"] > 0
    assert final_data["platform_pack"]["wechat"]
    assert final_data["platform_pack"]["xiaohongshu"]
    assert final_data["platform_pack"]["douyin"]

    print(f"  ✅ 通过 — 文章 {final_data['article']['word_count']} 字, GEO 评分 {final_data['geo_score']['total_score']}")


def test_api_health():
    """测试 9: /api/geo/health 接口"""
    print("\n=== [测试 9] /api/geo/health 接口 ===")
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    resp = client.get("/api/geo/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["prompts_loaded"] == 8
    print(f"  ✅ 通过 — {data}")


def test_api_generate_sse():
    """测试 10: /api/geo/generate SSE 接口"""
    print("\n=== [测试 10] /api/geo/generate SSE 接口 ===")
    from fastapi.testclient import TestClient

    # mock 掉所有 LLM 调用
    mock_llm = make_mock_llm()
    with patch("app.geo.research.get_llm", return_value=mock_llm), \
         patch("app.geo.outline.get_llm", return_value=mock_llm), \
         patch("app.geo.writer.get_llm", return_value=mock_llm), \
         patch("app.geo.image_prompt.get_llm", return_value=mock_llm), \
         patch("app.geo.score.get_llm", return_value=mock_llm), \
         patch("app.geo.platform.get_llm", return_value=mock_llm):
        from app.main import app
        client = TestClient(app)

        with client.stream(
            "POST",
            "/api/geo/generate",
            json={
                "title": "普通人如何用 AI 做副业",
                "platform": "wechat",
                "style": "personal_ip",
            },
        ) as resp:
            assert resp.status_code == 200
            event_count = 0
            has_final = False
            for line in resp.iter_lines():
                if line.startswith("data: "):
                    event_count += 1
                    data = json.loads(line[6:])
                    if data.get("type") == "final":
                        has_final = True

    print(f"  SSE 事件数: {event_count}, 含 final: {has_final}")
    assert event_count >= 12
    assert has_final
    print(f"  ✅ 通过 — {event_count} 个 SSE 事件, 含 final 数据")


def main():
    print("=" * 60)
    print("GEO 模块 smoke 测试")
    print("=" * 60)
    tests = [
        test_prompts_loaded,
        test_research_module,
        test_outline_module,
        test_writer_module,
        test_image_prompt_module,
        test_score_module,
        test_platform_module,
        test_orchestrator_full_flow,
        test_api_health,
        test_api_generate_sse,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  ❌ 失败: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"结果: {passed} 通过 / {failed} 失败 / 共 {len(tests)} 项")
    print("=" * 60)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())