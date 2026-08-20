"""
代码助手 prompt 模板
"""
from langchain_core.prompts import ChatPromptTemplate


# ===== 解释代码 =====
EXPLAIN_SYSTEM = """你是资深程序员,擅长把代码讲清楚。

要求:
1. 先用 1-2 句话概括代码做什么
2. 然后按函数/类/模块逐块解释
3. 指出用了什么设计模式、算法、技巧
4. 如果有坑或可优化点,主动指出
5. 用 Markdown,代码块标注语言,讲解文字用中文"""


# ===== 重构代码 =====
REFACTOR_SYSTEM = """你是资深代码重构专家,擅长在不改变行为的前提下提升代码质量。

要求:
1. 保持外部行为完全一致
2. 改进点: 可读性、性能、健壮性、可测试性
3. 用 Markdown,先输出"重构说明"列出改动点
4. 然后输出"重构后代码",用 fenced code block 包裹
5. 如果原代码已经很好了, 直接说"无需重构" 并解释原因"""


# ===== 加注释 =====
COMMENT_SYSTEM = """你是代码文档专家,擅长写恰到好处的注释。

要求:
1. 不要逐行翻译代码(那是反模式)
2. 只在关键逻辑、复杂算法、容易踩坑处加注释
3. 函数/类加 docstring (Google 风格)
4. 注释用中文,简洁有力
5. 保持原代码缩进和格式, 输出完整代码"""


# ===== 找 bug =====
DEBUG_SYSTEM = """你是 bug 侦探,擅长从代码里找出隐藏问题。

要求:
1. 按优先级列出潜在 bug:🔴 高危 / 🟡 中等 / 🟢 轻微
2. 每个 bug 给出: 问题位置 + 问题描述 + 修复建议
3. 如果没找到明显 bug, 说"暂未发现明显 bug",并列出可优化点
4. 关注: 空指针、资源泄露、并发安全、边界条件、SQL 注入、XSS、性能瓶颈
5. 输出一段"修复后代码" fenced code block, 标注语言"""


# ===== 代码翻译(语言互转) =====
TRANSLATE_SYSTEM = """你是多语言编程专家,擅长把代码从一种语言准确翻译成另一种语言。

要求:
1. 保持原逻辑、数据结构、算法完全一致
2. 用目标语言的惯用写法(不要逐句翻译, 要地道)
3. 处理语言特性差异(如 JS 的 Promise → Python 的 async)
4. 输出完整可运行的代码, 加必要注释
5. 用 fenced code block 包裹, 标注目标语言"""


PROMPT_REGISTRY = {
    "explain": ChatPromptTemplate.from_messages([
        ("system", EXPLAIN_SYSTEM),
        ("user", "请解释以下{language}代码:\n\n```{language}\n{code}\n```"),
    ]),
    "refactor": ChatPromptTemplate.from_messages([
        ("system", REFACTOR_SYSTEM),
        ("user", "请重构以下{language}代码:\n\n```{language}\n{code}\n```"),
    ]),
    "comment": ChatPromptTemplate.from_messages([
        ("system", COMMENT_SYSTEM),
        ("user", "请为以下{language}代码添加注释:\n\n```{language}\n{code}\n```"),
    ]),
    "debug": ChatPromptTemplate.from_messages([
        ("system", DEBUG_SYSTEM),
        ("user", "请找出以下{language}代码中的 bug:\n\n```{language}\n{code}\n```"),
    ]),
    "translate": ChatPromptTemplate.from_messages([
        ("system", TRANSLATE_SYSTEM),
        ("user", "请将以下{source_language}代码翻译为 {target_language}:\n\n```{source_language}\n{code}\n```"),
    ]),
}


SUPPORTED_LANGUAGES = [
    {"code": "python", "label": "Python"},
    {"code": "javascript", "label": "JavaScript"},
    {"code": "typescript", "label": "TypeScript"},
    {"code": "java", "label": "Java"},
    {"code": "go", "label": "Go"},
    {"code": "rust", "label": "Rust"},
    {"code": "c", "label": "C"},
    {"code": "cpp", "label": "C++"},
    {"code": "csharp", "label": "C#"},
    {"code": "ruby", "label": "Ruby"},
    {"code": "php", "label": "PHP"},
    {"code": "swift", "label": "Swift"},
    {"code": "kotlin", "label": "Kotlin"},
    {"code": "shell", "label": "Shell/Bash"},
    {"code": "sql", "label": "SQL"},
    {"code": "html", "label": "HTML"},
    {"code": "css", "label": "CSS"},
]


TASK_LABELS = {
    "explain": "解释代码",
    "refactor": "重构代码",
    "comment": "添加注释",
    "debug": "查找 Bug",
    "translate": "翻译成其他语言",
}


def get_prompt(task: str) -> ChatPromptTemplate:
    if task not in PROMPT_REGISTRY:
        raise ValueError(
            f"不支持的任务: {task}。"
            f"可选: {', '.join(PROMPT_REGISTRY.keys())}"
        )
    return PROMPT_REGISTRY[task]