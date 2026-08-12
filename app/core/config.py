"""
全局配置: 从 .env 读取,所有模块从这里取
"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置(自动从 .env 加载,支持类型校验)"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # 忽略 .env 里多余的字段
    )

    # ===== 硅基流动 =====
    siliconflow_api_key: str = ""

    # ===== LLM =====
    llm_model: str = "Qwen/Qwen2.5-72B-Instruct"
    llm_temperature: float = 0.3
    llm_max_tokens: int = 2048

    # ===== Embedding =====
    embedding_model: str = "BAAI/bge-m3"
    embedding_base_url: str = "https://api.siliconflow.cn/v1"

    # ===== 切片 =====
    chunk_size: int = 500
    chunk_overlap: int = 80

    # ===== 检索 =====
    retrieval_top_k: int = 4

    # ===== 服务 =====
    app_host: str = "0.0.0.0"
    app_port: int = 8001

    # ===== 路径 =====
    data_dir: str = "./data"
    upload_dir: str = "./data/uploads"
    chroma_dir: str = "./data/chroma"

    # ===== 派生路径(解析为绝对路径)=====
    @property
    def project_root(self) -> Path:
        """项目根目录 (aiwork-backend/)"""
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


# 单例
settings = Settings()