"""
摘要模块的 prompt 模板
跟 writer/prompts.py 一个套路 —— 一个能力一个文件。
"""
from langchain_core.prompts import ChatPromptTemplate


# ===== 短摘要 =====
SHORT_SUMMARY_SYSTEM = """你是一位专业的文本摘要助手,擅长把长文压缩成简短的总结。

要求:
1. 用 1-3 句话概括全文核心内容
2. 用客观语气, 不要加主观评价
3. 输出纯文本, 不要加标题、列表、emoji
4. 如果原文是中文, 用中文输出"""


# ===== 要点列表 =====
KEY_POINTS_SYSTEM = """你是一位信息提取专家,擅长从长文中抽取关键要点。

要求:
1. 输出 3-7 条要点
2. 用 Markdown 无序列表(`- xxx`)
3. 每条要点独立成行, 控制在 30 字以内
4. 不要重复, 不要加引言或总结段落
5. 按重要性从高到低排序"""


# ===== TL;DR =====
TLDR_SYSTEM = """你是一位给忙碌的老板写"一分钟摘要"的助理。

要求:
1. 输出一段话, 不超过 100 字
2. 开头必须写 "TL;DR:"(英文, 表示"太长不看")
3. 直接说"这篇讲了什么"+"核心结论是什么"
4. 适合在手机上 5 秒读完
5. 用聊天口吻, 不用 Markdown"""


# 风格注册表
PROMPT_REGISTRY = {
    "short": ChatPromptTemplate.from_messages([
        ("system", SHORT_SUMMARY_SYSTEM),
        ("user", "请对以下文本生成简短摘要:\n\n{text}"),
    ]),
    "key_points": ChatPromptTemplate.from_messages([
        ("system", KEY_POINTS_SYSTEM),
        ("user", "请从以下文本中提取关键要点:\n\n{text}"),
    ]),
    "tldr": ChatPromptTemplate.from_messages([
        ("system", TLDR_SYSTEM),
        ("user", "{text}"),
    ]),
}


def get_prompt(summary_type: str) -> ChatPromptTemplate:
    """根据摘要类型取 prompt, 找不到就抛错"""
    if summary_type not in PROMPT_REGISTRY:
        raise ValueError(
            f"不支持的摘要类型: {summary_type}。"
            f"可选: {', '.join(PROMPT_REGISTRY.keys())}"
        )
    return PROMPT_REGISTRY[summary_type]