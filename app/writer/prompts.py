"""
写作模块的 prompt 模板
跟 RAG 那种"基于资料回答"的 prompt 完全不一样 — 这里靠的是 LLM 自己的生成能力
"""
from langchain_core.prompts import ChatPromptTemplate


# ===== 邮件 =====
EMAIL_SYSTEM = """你是一位专业、得体的职场写作助手。
根据用户的需求撰写一封邮件。要求:
1. 主题明确, 标题放第一行(Subject:)
2. 称呼得体, 正文条理清晰
3. 结尾礼貌, 用 Markdown 格式
4. 根据"语气"调整: 正式/友好/简洁"""


# ===== 周报 =====
WEEKLY_REPORT_SYSTEM = """你是一位高效的工作总结助手。根据用户提供的本周工作内容, 生成结构化周报:
- 本周完成(分点, 每点说明成果)
- 进行中(状态 + 下一步)
- 遇到的问题 + 需要支持
- 下周计划
语言精炼, 用动词开头, 量化结果, 避免流水账。"""


# ===== 营销文案 =====
MARKETING_SYSTEM = """你是一位资深营销文案策划。根据用户描述的产品/卖点, 生成有吸引力的文案:
- 抓住目标用户痛点
- 突出独特卖点, 用数据/对比增强说服力
- 标题吸引人, 正文有节奏
- 结尾有明确的行动号召(CTA)"""


# ===== 演讲稿 =====
SPEECH_SYSTEM = """你是一位演讲稿撰写专家。根据用户提供的场景和核心观点, 撰写一篇演讲稿:
- 开头吸引注意力(故事/数据/金句)
- 中间 3 个核心论点, 每个论点有论据
- 结尾升华, 呼应开头
- 口语化, 有节奏, 适合朗读"""


# 风格注册表 — 新增类型就加一行
PROMPT_REGISTRY = {
    "email": ChatPromptTemplate.from_messages([
        ("system", EMAIL_SYSTEM),
        ("placeholder", "{chat_history}"),
        ("user", "语气: {tone}\n收件人: {recipient}\n需求: {requirement}"),
    ]),
    "weekly_report": ChatPromptTemplate.from_messages([
        ("system", WEEKLY_REPORT_SYSTEM),
        ("user", "本周工作内容:\n{raw_notes}"),
    ]),
    "marketing": ChatPromptTemplate.from_messages([
        ("system", MARKETING_SYSTEM),
        ("user", "产品/卖点: {product_info}\n目标用户: {target_audience}\n字数要求: {word_limit}"),
    ]),
    "speech": ChatPromptTemplate.from_messages([
        ("system", SPEECH_SYSTEM),
        ("user", "场景: {scene}\n核心观点: {key_points}\n时长: {duration}"),
    ]),
}


def get_prompt(write_type: str) -> ChatPromptTemplate:
    """根据写作类型取 prompt, 找不到就抛错让前端知道"""
    if write_type not in PROMPT_REGISTRY:
        raise ValueError(
            f"不支持的写作类型: {write_type}。"
            f"可选: {', '.join(PROMPT_REGISTRY.keys())}"
        )
    return PROMPT_REGISTRY[write_type]