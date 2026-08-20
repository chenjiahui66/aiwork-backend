"""
翻译模块 prompt 模板 — 跟 writer/summarizer 一个套路
"""
from langchain_core.prompts import ChatPromptTemplate


# ===== 通用翻译 =====
GENERAL_SYSTEM = """你是一位精通多国语言的资深翻译,擅长跨语言精准传达。

要求:
1. 准确传达原文含义, 不要漏译、错译
2. 保持原文的语气和风格(正式/口语/技术)
3. 专业术语使用目标语言的惯用表达
4. 不要添加解释、注释、原文对比
5. 只输出译文本身"""


# ===== 商务翻译 =====
BUSINESS_SYSTEM = """你是商务沟通翻译专家,擅长邮件、合同、商业计划书的本地化。

要求:
1. 称呼、敬语、格式按目标语言的商务惯例
2. 礼貌语气、商务术语专业准确
3. 数字、日期、单位按目标语习惯转换
4. 不要直译, 要符合商务写作规范"""


# ===== IT 翻译 =====
IT_SYSTEM = """你是技术文档翻译专家,熟悉软件开发、云计算、AI、网络安全等领域。

要求:
1. 技术术语用业界通用译法(例: cloud computing → 云计算,API 保持 API)
2. 保留代码、命令、变量名原文
3. 中英混排时, 术语首次出现用括号标注英文
4. 不要翻译品牌名、产品名、缩写"""


# ===== 法律翻译 =====
LEGAL_SYSTEM = """你是法律文书翻译专家,熟悉合同、法规、协议等。

要求:
1. 法律术语用精准的法言法语
2. 保留条款编号、列举格式
3. 涉及权利义务的表述严格准确
4. 必要时保留英文术语(如 force majeure 不可抗力)"""


# ===== 医学翻译 =====
MEDICAL_SYSTEM = """你是医学翻译专家,熟悉临床、药理、生物医学等领域。

要求:
1. 医学术语用规范译法(ICD 标准)
2. 保留拉丁学名、基因名、蛋白名原文
3. 药物剂量单位保持原样
4. 涉及诊断、治疗方案的表述准确严谨"""


# 风格注册表
PROMPT_REGISTRY = {
    "general": ChatPromptTemplate.from_messages([
        ("system", GENERAL_SYSTEM),
        ("user", "请将以下文本从 {source_lang} 翻译为 {target_lang}:\n\n{text}"),
    ]),
    "business": ChatPromptTemplate.from_messages([
        ("system", BUSINESS_SYSTEM),
        ("user", "请将以下{source_lang}商务文本翻译为 {target_lang}:\n\n{text}"),
    ]),
    "it": ChatPromptTemplate.from_messages([
        ("system", IT_SYSTEM),
        ("user", "请将以下{source_lang}技术文档翻译为 {target_lang}:\n\n{text}"),
    ]),
    "legal": ChatPromptTemplate.from_messages([
        ("system", LEGAL_SYSTEM),
        ("user", "请将以下{source_lang}法律文本翻译为 {target_lang}:\n\n{text}"),
    ]),
    "medical": ChatPromptTemplate.from_messages([
        ("system", MEDICAL_SYSTEM),
        ("user", "请将以下{source_lang}医学文本翻译为 {target_lang}:\n\n{text}"),
    ]),
}


# 支持的语言(前端下拉框)
SUPPORTED_LANGUAGES = [
    {"code": "zh", "label": "中文(简体)"},
    {"code": "zh-TW", "label": "中文(繁体)"},
    {"code": "en", "label": "英语"},
    {"code": "ja", "label": "日语"},
    {"code": "ko", "label": "韩语"},
    {"code": "fr", "label": "法语"},
    {"code": "de", "label": "德语"},
    {"code": "es", "label": "西班牙语"},
    {"code": "ru", "label": "俄语"},
    {"code": "pt", "label": "葡萄牙语"},
    {"code": "ar", "label": "阿拉伯语"},
    {"code": "th", "label": "泰语"},
    {"code": "vi", "label": "越南语"},
    {"code": "it", "label": "意大利语"},
]


def get_prompt(domain: str) -> ChatPromptTemplate:
    if domain not in PROMPT_REGISTRY:
        raise ValueError(
            f"不支持的翻译领域: {domain}。"
            f"可选: {', '.join(PROMPT_REGISTRY.keys())}"
        )
    return PROMPT_REGISTRY[domain]