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


settings = Settings()