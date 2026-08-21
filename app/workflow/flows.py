"""
预置工作流 — 用 LangGraph StateGraph 实现真正的图状态机

每个工作流:
1. 定义自己的 State TypedDict(各步骤产物作为字段)
2. 定义每个节点的 async 函数(state) -> state_updates,函数内部 yield "events" 用于前端流式展示
3. 用 StateGraph 组装: add_node + add_edge(START -> n1 -> n2 -> ... -> END)
4. graph.compile() 后返回 WORKFLOWS 字典供 chain.py 调度

事件协议(与原 async generator 兼容):
- workflow_meta
- node_start
- token
- node_end
- done
- error
"""
import logging
from typing import AsyncIterator, TypedDict

from langgraph.graph import END, START, StateGraph

from app.workflow.node import make_llm_node

logger = logging.getLogger(__name__)


# ============================================================
# 工作流 1: 文档总结流水线
# 输入: 长文 → 摘要 → 英文翻译 → 待办提取
# ============================================================
class DocSummaryState(TypedDict, total=False):
    input: str
    summary: str
    english: str
    todos: str


def build_doc_summary_graph():
    """文档总结流水线 — 3 个节点串行"""
    builder = StateGraph(DocSummaryState)

    # 节点 1: 摘要
    async def summarize_node(state: DocSummaryState):
        return await make_llm_node(
            node_id="summarize",
            node_label="📝 步骤 1/3: 生成摘要",
            system_prompt="你是摘要助手,用 3 句话概括下面这段文字的核心内容。中文输出。",
            user_prompt=f"文本: {state['input']}",
            output_key="summary",
        )

    # 节点 2: 翻译
    async def translate_en_node(state: DocSummaryState):
        return await make_llm_node(
            node_id="translate_en",
            node_label="🌐 步骤 2/3: 翻译成英文",
            system_prompt="你是翻译助手,把下面这段中文翻译成专业的英文,适合发给海外同事。",
            user_prompt=f"原文:\n{state['summary']}",
            output_key="english",
        )

    # 节点 3: 待办
    async def extract_todo_node(state: DocSummaryState):
        return await make_llm_node(
            node_id="extract_todo",
            node_label="✅ 步骤 3/3: 提取待办事项",
            system_prompt=(
                "你是任务管理助手,从这段会议/文本中提取所有待办事项,"
                "按 Markdown 列表输出,每条标注责任人(如有)和截止日期(如有)。"
                "如果没有待办,直接说\"无\"。"
            ),
            user_prompt=f"文本:\n{state['input']}",
            output_key="todos",
        )

    builder.add_node("summarize", summarize_node)
    builder.add_node("translate_en", translate_en_node)
    builder.add_node("extract_todo", extract_todo_node)

    # 边: START → summarize → translate_en → extract_todo → END
    builder.add_edge(START, "summarize")
    builder.add_edge("summarize", "translate_en")
    builder.add_edge("translate_en", "extract_todo")
    builder.add_edge("extract_todo", END)

    return builder.compile()


# ============================================================
# 工作流 2: 客户评论分析
# 输入: 多条评论 → 情感 → 关键词 → 建议
# ============================================================
class ReviewAnalysisState(TypedDict, total=False):
    input: str
    sentiment: str
    keywords: str
    suggestions: str


def build_review_analysis_graph():
    builder = StateGraph(ReviewAnalysisState)

    async def sentiment_node(state: ReviewAnalysisState):
        return await make_llm_node(
            node_id="sentiment",
            node_label="😊 步骤 1/3: 情感分析",
            system_prompt=(
                "你是评论分析专家。\n"
                "对每条评论判断: 正面 😊 / 中性 😐 / 负面 😞,并打分 (-1 到 1)。\n"
                "输出格式:\n"
                "- 评论1: 正面 (0.8) - 简述原因\n"
                "- 评论2: 负面 (-0.6) - 简述原因\n"
                "最后给一行总计: \"正面 X 条, 中性 Y 条, 负面 Z 条, 平均分 X.X\"。"
            ),
            user_prompt=f"评论内容:\n{state['input']}",
            output_key="sentiment",
        )

    async def keywords_node(state: ReviewAnalysisState):
        return await make_llm_node(
            node_id="keywords",
            node_label="🔑 步骤 2/3: 关键词提取",
            system_prompt=(
                "你是关键词分析专家。\n"
                "从下面评论中提取 5-10 个高频关键词/短语,按出现频率从高到低排列,"
                "每条简短解释它在评论中的语境。\n输出 Markdown 列表。"
            ),
            user_prompt=f"评论:\n{state['input']}",
            output_key="keywords",
        )

    async def suggestions_node(state: ReviewAnalysisState):
        return await make_llm_node(
            node_id="suggestions",
            node_label="💡 步骤 3/3: 改进建议",
            system_prompt=(
                "你是产品改进顾问。\n"
                "基于上面的情感分析和关键词,输出 5 条具体可行的产品/服务改进建议。\n"
                "每条建议: 标题 + 简短理由 + 优先级(高/中/低)。\n中文输出。"
            ),
            user_prompt=(
                f"评论原文:\n{state['input']}\n\n"
                f"情感分析:\n{state['sentiment']}\n\n关键词:\n{state['keywords']}"
            ),
            output_key="suggestions",
        )

    builder.add_node("sentiment", sentiment_node)
    builder.add_node("keywords", keywords_node)
    builder.add_node("suggestions", suggestions_node)

    builder.add_edge(START, "sentiment")
    builder.add_edge("sentiment", "keywords")
    builder.add_edge("keywords", "suggestions")
    builder.add_edge("suggestions", END)

    return builder.compile()


# ============================================================
# 工作流 3: 竞品对比
# 输入: 产品列表 → 各自特点 → 对比矩阵 → SWOT
# ============================================================
class CompetitorCompareState(TypedDict, total=False):
    input: str
    features: str
    matrix: str
    swot: str


def build_competitor_compare_graph():
    builder = StateGraph(CompetitorCompareState)

    async def features_node(state: CompetitorCompareState):
        return await make_llm_node(
            node_id="features",
            node_label="📦 步骤 1/3: 列出各产品特点",
            system_prompt=(
                "你是产品分析师。\n"
                "对下面列出的每个产品/服务,逐一列出:\n"
                "- 核心定位 (一句话)\n- 主要功能 (3-5 条)\n"
                "- 目标用户\n- 商业模式\n\n"
                "输出格式:\n## 产品A\n- 核心定位: ...\n- 主要功能: ..."
            ),
            user_prompt=f"产品列表: {state['input']}",
            output_key="features",
        )

    async def matrix_node(state: CompetitorCompareState):
        return await make_llm_node(
            node_id="matrix",
            node_label="📊 步骤 2/3: 对比矩阵",
            system_prompt=(
                "你是竞品分析师。\n"
                "基于上面各产品的特点,生成一个 Markdown 对比表,维度包括:\n"
                "功能完整度 / 易用性 / 价格 / 性能 / 用户口碑 / 创新能力\n\n"
                "每项打 1-5 星,文末给一行\"综合推荐\"小结。"
            ),
            user_prompt=f"产品信息:\n{state['features']}",
            output_key="matrix",
        )

    async def swot_node(state: CompetitorCompareState):
        return await make_llm_node(
            node_id="swot",
            node_label="🎯 步骤 3/3: SWOT 分析",
            system_prompt=(
                "你是战略分析师。\n"
                "针对产品列表中的\"第一个产品\",做一份 SWOT 分析:\n"
                "- S(优势): 相比对手的差异化能力\n- W(劣势): 明显短板\n"
                "- O(机会): 市场增长点\n- T(威胁): 来自对手/市场的风险\n\n"
                "每点 2-3 条,简洁有力。中文输出。"
            ),
            user_prompt=f"对比信息:\n{state['matrix']}",
            output_key="swot",
        )

    builder.add_node("features", features_node)
    builder.add_node("matrix", matrix_node)
    builder.add_node("swot", swot_node)

    builder.add_edge(START, "features")
    builder.add_edge("features", "matrix")
    builder.add_edge("matrix", "swot")
    builder.add_edge("swot", END)

    return builder.compile()


# ============================================================
# 工作流 4: PRD 生成器
# 输入: 一句话需求 → 用户故事 → 验收标准 → 技术方案
# ============================================================
class PrdGeneratorState(TypedDict, total=False):
    input: str
    user_story: str
    acceptance: str
    tech_plan: str


def build_prd_generator_graph():
    builder = StateGraph(PrdGeneratorState)

    async def user_story_node(state: PrdGeneratorState):
        return await make_llm_node(
            node_id="user_story",
            node_label="👤 步骤 1/3: 用户故事",
            system_prompt=(
                "你是产品经理。\n"
                "把下面这句话扩展成 5-8 条用户故事,每条格式:\n"
                "\"作为 [角色], 我希望 [功能], 以便 [价值]。\"\n\n"
                "按优先级(P0/P1/P2)分组列出。"
            ),
            user_prompt=f"需求: {state['input']}",
            output_key="user_story",
        )

    async def acceptance_node(state: PrdGeneratorState):
        return await make_llm_node(
            node_id="acceptance",
            node_label="✅ 步骤 2/3: 验收标准",
            system_prompt=(
                "你是 QA 工程师。\n"
                "针对上面的用户故事,生成验收标准(Acceptance Criteria),"
                "每条用户故事对应 3-5 条 Gherkin 风格的验收点:\n"
                "- Given [前置条件]\n- When [动作]\n- Then [预期结果]\n\n中文输出。"
            ),
            user_prompt=f"用户故事:\n{state['user_story']}",
            output_key="acceptance",
        )

    async def tech_plan_node(state: PrdGeneratorState):
        return await make_llm_node(
            node_id="tech_plan",
            node_label="🏗️ 步骤 3/3: 技术方案",
            system_prompt=(
                "你是技术架构师。\n"
                "基于上面的需求 + 用户故事 + 验收标准,输出技术方案:\n"
                "1. 系统架构图(文字描述)\n2. 数据模型(核心表/字段)\n"
                "3. API 列表(端点 + 方法 + 用途)\n"
                "4. 关键技术选型(前端/后端/数据库, 给出推荐 + 理由)\n"
                "5. 风险点与应对\n\n每节简洁, 共 500 字以内。"
            ),
            user_prompt=(
                f"需求: {state['input']}\n\n用户故事:\n{state['user_story']}\n\n"
                f"验收标准:\n{state['acceptance']}"
            ),
            output_key="tech_plan",
        )

    builder.add_node("user_story", user_story_node)
    builder.add_node("acceptance", acceptance_node)
    builder.add_node("tech_plan", tech_plan_node)

    builder.add_edge(START, "user_story")
    builder.add_edge("user_story", "acceptance")
    builder.add_edge("acceptance", "tech_plan")
    builder.add_edge("tech_plan", END)

    return builder.compile()


# ============================================================
# 注册表 — 前端用元信息 + chain.py 用 compiled graph
# ============================================================
WORKFLOWS = {
    "doc_summary": {
        "code": "doc_summary",
        "name": "文档总结流水线",
        "description": "长文 → 摘要 → 英文翻译 → 待办提取",
        "icon": "📝",
        "input_label": "长文 / 会议记录",
        "input_placeholder": "把长文、会议记录、聊天记录粘到这里...",
        "input_min_length": 50,
        "steps": ["📝 生成摘要", "🌐 翻译成英文", "✅ 提取待办"],
        "build_graph": build_doc_summary_graph,
    },
    "review_analysis": {
        "code": "review_analysis",
        "name": "客户评论分析",
        "description": "评论 → 情感分析 → 关键词 → 改进建议",
        "icon": "😊",
        "input_label": "客户评论",
        "input_placeholder": (
            "多条评论,一行一条(每条不少于 10 字)...\n\n"
            "例如:\n这个产品真的太好用了!\n客服态度很差,等了 3 天\n功能强大但学习成本高"
        ),
        "input_min_length": 20,
        "steps": ["😊 情感分析", "🔑 关键词提取", "💡 改进建议"],
        "build_graph": build_review_analysis_graph,
    },
    "competitor_compare": {
        "code": "competitor_compare",
        "name": "竞品对比分析",
        "description": "产品列表 → 各自特点 → 对比矩阵 → SWOT",
        "icon": "📊",
        "input_label": "竞品列表(逗号分隔)",
        "input_placeholder": "例如:ChatGPT, Claude, 文心一言",
        "input_min_length": 3,
        "steps": ["📦 列出特点", "📊 对比矩阵", "🎯 SWOT"],
        "build_graph": build_competitor_compare_graph,
    },
    "prd_generator": {
        "code": "prd_generator",
        "name": "产品 PRD 生成器",
        "description": "一句话需求 → 用户故事 → 验收标准 → 技术方案",
        "icon": "💡",
        "input_label": "需求描述(一句话)",
        "input_placeholder": "例如:做一个员工请假系统,支持多级审批",
        "input_min_length": 5,
        "steps": ["👤 用户故事", "✅ 验收标准", "🏗️ 技术方案"],
        "build_graph": build_prd_generator_graph,
    },
}