"""
Global configuration loaded from .env
"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ===== MiniMax =====
    minimax_api_key: str = ""
    minimax_base_url: str = "https://api.minimaxi.com/v1"

    # ===== LLM =====
    llm_model: str = "MiniMax-M3"
    llm_temperature: float = 0.3
    llm_max_tokens: int = 2048

    # ===== Embedding (local HF model) =====
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    embedding_device: str = "cpu"           # cpu / cuda / mps
    embedding_normalize: bool = True

    # ===== Splitter =====
    chunk_size: int = 500
    chunk_overlap: int = 80

    # ===== Retrieval =====
    retrieval_top_k: int = 4

    # ===== Server =====
    app_host: str = "0.0.0.0"
    app_port: int = 8001

    # ===== Paths =====
    data_dir: str = "./data"
    upload_dir: str = "./data/uploads"
    chroma_dir: str = "./data/chroma"

    # ===== SMTP(发邮件,可选 — 留空则 /api/email/send 不可用) =====
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_name: str = "AiWork 助手"
    smtp_timeout: int = 15

    @property
    def smtp_configured(self) -> bool:
        """SMTP 是否配置完整 — 用在前端灰显按钮 + 后端 503 提示"""
        return bool(self.smtp_host and self.smtp_user and self.smtp_password)

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parent.parent.parent

    @property
    def upload_path(self) -> Path:
        p = Path(self.upload_dir)
        if not p.is_absolute():
            p = self.project_root / p
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def chroma_path(self) -> Path:
        p = Path(self.chroma_dir)
        if not p.is_absolute():
            p = self.project_root / p
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def data_path(self) -> Path:
        p = Path(self.data_dir)
        if not p.is_absolute():
            p = self.project_root / p
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()