# GEO 内容智能体模块 — 产品分析 & 技术规划

> 对齐 ChatGPT 给的方案 + 现有 aiwork-backend 的能力复用清单。
> 第一版只做一个闭环：**标题 → GEO检索 → 文章 → 配图 → 发布**

---

## 1. 产品定位（一句话）

**AI 自媒体研究员 + GEO 内容编辑 + 视觉设计师**

用户输入一个选题 → 系统自动完成检索 → GEO 分析 → 文章 → 配图 → 多平台发布素材。

不是"AI 写作工具"，是"内容生产 Agent"。

---

## 2. MVP 范围（第一版只做这些）

✅ **要做**：
- 选题输入（标题 + 平台 + 风格）
- 12 步 Agent 流程（一个端到端大接口返回全量结果，不做中间步骤交互）
- 文章正文 + GEO 评分
- 配图 prompt（4 张配图 + 1 张封面）—— **图像生成走第三方 API 或前端占位**
- 多平台发布包：公众号 / 小红书 / 抖音图文（各一份专属内容）
- 内容质量检查（GEO 评分 + 缺口提示）

❌ **第一版不做**：
- Agent 编排可视化（Dify 式）
- 视频生成
- 自动发布
- 用户系统 / 付费 / 多租户
- 品牌知识库
- 历史文章管理
- 协作 / 评论 / 多人

---

## 3. 模块边界（在 aiwork-backend 里的位置）

新增文件夹：`app/geo/`，平级于 `app/rag/`、`app/writer/`、`app/email/`、`app/feishu/`。

```
app/
├── geo/
│   ├── __init__.py
│   ├── orchestrator.py       # 12 步主控
│   ├── research.py           # ① 搜索互联网 + ② 搜集资料（web_search）
│   ├── analysis.py           # ③⑤⑥ 竞品分析 + 内容缺口 + GEO 关键词/实体
│   ├── outline.py            # ⑦ 构建文章知识结构
│   ├── writer.py             # ⑧⑨ 文章生成 + GEO 优化
│   ├── image_prompt.py       # ⑩⑪ 配图 prompt + 封面 prompt
│   ├── platform.py           # ⑫ 多平台改写（公众号/小红书/抖音图文）
│   ├── score.py              # GEO 评分 + AI 搜索模拟器
│   └── prompts/              # 所有 prompt 模板
│       ├── research.md
│       ├── outline.md
│       ├── article.md
│       ├── wechat.md
│       ├── xiaohongshu.md
│       ├── douyin.md
│       └── geo_score.md
```

**12 个 skill 映射到 8 个 Python 模块**（不是 1:1，合并同质的）：
| Step | Skill 名 | 模块 |
|---|---|---|
| ① 搜索互联网 | `web-research` | `research.py` |
| ② 搜集资料 | `web-research` | `research.py` |
| ③ 分析搜索结果 | `topic-research` | `analysis.py` |
| ④ 提取用户真实问题 | `topic-research` | `analysis.py` |
| ⑤ 分析内容缺口 | `topic-research` | `analysis.py` |
| ⑥ GEO 关键词/实体分析 | `geo-analysis` | `analysis.py` |
| ⑦ 构建文章知识结构 | `content-outline` | `outline.py` |
| ⑧ AI 生成文章 | `article-writer` | `writer.py` |
| ⑨ GEO 优化 | `article-writer` | `writer.py` |
| ⑩ 生成图文 | `image-prompt` | `image_prompt.py` |
| ⑪ 生成封面 | `cover-generator` | `image_prompt.py` |
| ⑫ 输出发布素材 | `wechat/xiaohongshu/douyin-writer` | `platform.py` |

---

## 4. 关键差异化功能（必须做出来）

### 4.1 GEO Research Agent
- 输入：标题
- 输出：
  - 当前热门方向（5-8 条）
  - 用户高频问题（5-10 条）
  - 已有内容普遍问题（5 条）
  - 内容机会（5 条）
- 实现：WebSearch（MiniMax 工具调用 or SerpAPI）+ LLM 二次结构化

### 4.2 实体清晰（Entity Graph）
- 系统识别主题内的核心实体：
  - Entity（产品名 / 概念）
  - Company（公司）
  - Category（品类）
  - Related（竞品 / 关联项）
- 写文章时**强制统一指代**，避免混叫

### 4.3 Q-A 结构
- 文章自动生成 FAQ 模块
- 每条问题独立可被 AI 搜索引擎抓取

### 4.4 事实可验证（Claim → Source）
- 每条事实声明带 URL 来源
- 没有来源的事实标 `unverified`
- 数据幻觉风险降低

### 4.5 GEO 评分（0-100）
- 维度：实体明确 / 主题覆盖 / 问题覆盖 / 数据支撑 / 案例 / 来源权威 / FAQ
- 每维度打分 + 改进建议
- **一键优化**（重跑 GEO Skill）

### 4.6 AI 搜索模拟器
- 系统模拟 3-5 个相关问题
- 评估文章被引用的可能性（高/中/低）
- 说明理由（"缺少 X 实体"、"未回答 Y 问题"）

### 4.7 文章结构驱动配图
- 文章章节 → 每章核心信息 → 视觉表达方式 → Image Prompt → 出图
- **MiniMax 无图像模型**，第一版只生成 prompt，UI 提供"复制 prompt 去 Midjourney/Stable Diffusion"
- 配图数量：正文配图 4 张 + 封面 1 张

### 4.8 多平台发布包
- 公众号：标题 + 正文 + 封面 + GEO 描述
- 小红书：标题 ×10 + 正文 + 9 张图 + 标签
- 抖音图文：标题 + 9 宫格文案 + 文案

---

## 5. API 设计

```
POST /api/geo/generate
  body: {
    title: str,
    platform: "wechat" | "xiaohongshu" | "douyin" | "zhihu" | "toutiao",
    style: "professional" | "personal_ip" | "viral_analysis" | "story" | "opinion" | "tutorial",
    enable_image: bool = false   # 第一版默认 false
  }
  response: {
    research: { hotspots, faqs, gaps, opportunities, entities },
    article: { title, outline, content, faqs, facts },
    geo_score: { total, dimensions[], suggestions[] },
    ai_search_test: [{ question, likelihood, reason }],
    images: { cover_prompt, illustration_prompts[] },
    platform_pack: {
      wechat: { title, content, geo_description },
      xiaohongshu: { titles[], content, tags[] },
      douyin: { title, grid_copies[] }
    }
  }

GET /api/geo/health
POST /api/geo/score-only   # 只跑 GEO 评分，不重写文章
```

---

## 6. 前端页面（`src/views/GEOView.vue`）

参考 ChatGPT 建议的三块布局：

```
┌──────────────────────────────────────┐
│  AI脑洞工场 · GEO 内容智能体           │
├──────────────────────────────────────┤
│  [ 输入你的选题 ]                     │
│  平台：[微信▼] 风格：[个人IP▼]       │
│  [ ✨ 一键生成 ]                     │
├──────────────────────────────────────┤
│  生成进度（步骤 1/12...）             │
├──────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐         │
│  │  文章正文 │  │ GEO 评分 │         │
│  │          │  │   82     │         │
│  │          │  │ ✓ ✓ ✓ ⚠   │         │
│  └──────────┘  └──────────┘         │
│  配图 prompts（可复制去出图）         │
├──────────────────────────────────────┤
│  发布包：                             │
│  [ 公众号 ] [ 小红书 ] [ 抖音图文 ]   │
└──────────────────────────────────────┘
```

前端路由：`/geo`，侧边栏卡片名「GEO 智能体」。

---

## 7. 技术栈（最大化复用现有）

| 层 | 复用 | 新增 |
|---|---|---|
| LLM | `app/core/llm.py` 单例 | — |
| Prompt 管理 | — | `app/geo/prompts/*.md`（文件级，方便迭代） |
| Web 搜索 | — | MiniMax 工具调用 or SerpAPI key |
| 实体识别 | — | LLM 二次结构化（不强求 NER 模型） |
| GEO 评分 | — | 启发式规则 + LLM 评估 |
| 出图 | — | 不接，生成 prompt 即可 |
| 路由 | `app/api/geo.py` + `app/main.py` 注册 | — |
| Schema | `app/models/schemas.py` 加 `GEORequest/Response` | — |
| 前端 | `src/views/GEOView.vue` + `src/router/router.ts` + `src/data/mock.ts` | — |

**关键约束**：
- MiniMax 无图像模型 → 配图生成 = 生成可复制的 prompt，**不做后端调出图 API**
- Web 搜索需要 API key（SerpAPI / Tavily），第一版可以用 LLM 自带的搜索能力 if available，否则走"无 web 搜索 + 仅凭 LLM 知识"的 fallback 模式

---

## 8. 第一版里程碑

1. **后端骨架**（半天）
   - `app/geo/` 8 个模块
   - 12 步主流程跑通（Web 搜索 fallback 到 LLM-only）
   - GEO 评分 + AI 搜索模拟器
   - 多平台改写

2. **后端测试**（半天）
   - `tmp/smoke_geo.py` mock LLM 跑全流程
   - 验证输入 → 输出结构

3. **前端页面**（半天）
   - `GEOView.vue` 三块布局
   - 流式进度更新（复用 `parse-todos` 的 SSE 模式）
   - 侧边栏卡片接入

4. **README 更新**（半小时）
   - 第 13 个模块
   - 调参指南（Web 搜索 API key 怎么配）

---

## 9. 关键风险 & 兜底

| 风险 | 兜底 |
|---|---|
| MiniMax 无图像 | 只生成 prompt，前端给"复制到 Midjourney"按钮 |
| Web 搜索 API 没配 | fallback 到 LLM-only，UI 标"⚠ 当前未启用实时检索" |
| 12 步全跑一次太慢 | 拆可选项：先快速版（5 步），完整版（12 步） |
| GEO 评分不准 | 第一版用启发式规则 + LLM 评估，后续按用户反馈迭代 |
| 内容过长超出 token | 分章节生成，最后拼接 |

---

## 10. 不做的事（明确边界）

- ❌ 不承诺"AI 搜索排名保证"（文案上写"提高被引用的基础条件"）
- ❌ 不做 Agent 编排可视化
- ❌ 不做自动发布
- ❌ 不做用户系统（先用自己公众号做第一波内容）
- ❌ 不做付费 / SaaS（先免费 3 篇跑通闭环）
- ❌ 不做品牌知识库 / 自定义写作风格

---

**下一步**：用户确认范围 → 开始写代码。先做后端 12 步骨架 + 端到端 smoke test。