"""
Prompt 加载器 — 从 .md 文件读 prompt 内容

为什么不直接用 ChatPromptTemplate.from_messages?
- 这些 prompt 文件含完整中文指令 + JSON 模板, 双重转义 {{ }} 太多容易出 bug
- 直接作为 system message 传给 LLM 更灵活, LLM 自己按格式输出 JSON
- 后续迭代只需要改 .md 文件, 不动 Python 代码
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent / "prompts"


def load_prompt(name: str) -> str:
    """加载指定 prompt 文件的完整内容"""
    path = _PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    content = path.read_text(encoding="utf-8")
    logger.debug("Loaded prompt: %s (%d chars)", name, len(content))
    return content


def _split_sections(content: str) -> tuple[str, str]:
    """
    把 .md 文件拆成 (system, user_template)
    分隔符: '## System' 开头到 '## User' 开头之间是 system
    """
    system_marker = "## System"
    user_marker = "## User"

    sys_start = content.find(system_marker)
    user_start = content.find(user_marker)

    if sys_start < 0 or user_start < 0:
        raise ValueError(f"Prompt must contain '## System' and '## User' markers")

    system_body = content[sys_start + len(system_marker):user_start].strip()
    user_body = content[user_start + len(user_marker):].strip()
    return system_body, user_body


def get_system_and_user(name: str) -> tuple[str, str]:
    """加载 prompt 并拆分成 (system_body, user_template)"""
    content = load_prompt(name)
    return _split_sections(content)


# 预注册所有 prompt 名（启动时校验文件存在）
PROMPT_FILES = [
    "research",
    "outline",
    "article",
    "wechat",
    "xiaohongshu",
    "douyin",
    "image_prompt",
    "geo_score",
]


def validate_all() -> None:
    """启动时校验所有 prompt 文件存在且格式正确"""
    for name in PROMPT_FILES:
        try:
            system, user = get_system_and_user(name)
            assert system, f"{name}: empty system"
            assert user, f"{name}: empty user"
        except Exception as e:
            raise RuntimeError(f"Prompt validation failed for {name}: {e}") from e
    logger.info("✅ All %d GEO prompt files validated", len(PROMPT_FILES))