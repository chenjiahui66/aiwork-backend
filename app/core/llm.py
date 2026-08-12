"""
LLM + Embedding client wrappers.

- LLM:  MiniMax-M3 via OpenAI-compatible endpoint (api.minimaxi.com)
- Embedding: local HuggingFace model (BAAI/bge-small-zh-v1.5)
"""
import logging
from functools import lru_cache

from langchain_openai import ChatOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_llm() -> ChatOpenAI:
    """LLM client (singleton) - MiniMax-M3 via OpenAI protocol."""
    if not settings.minimax_api_key:
        raise RuntimeError(
            "MINIMAX_API_KEY not set. Copy .env.example to .env and fill the key."
        )
    logger.info("LLM client: %s @ %s", settings.llm_model, settings.minimax_base_url)
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.minimax_api_key,
        base_url=settings.minimax_base_url,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
    )


# ----- Embedding (lazy load) -----
_embeddings_instance = None


def get_embeddings():
    """
    Local HuggingFace embedding (BAAI/bge-small-zh-v1.5).

    First call will download the model (~100MB) to HF cache.
    Subsequent calls reuse the in-memory instance.
    """
    global _embeddings_instance
    if _embeddings_instance is not None:
        return _embeddings_instance

    if not settings.embedding_model:
        raise RuntimeError("EMBEDDING_MODEL not set")

    try:
        from langchain_huggingface import HuggingFaceEmbeddings
    except ImportError as e:
        raise RuntimeError(
            "Please install langchain-huggingface: pip install langchain-huggingface sentence-transformers"
        ) from e

    logger.info(
        "Loading embedding model: %s (device=%s, normalize=%s)",
        settings.embedding_model,
        settings.embedding_device,
        settings.embedding_normalize,
    )
    _embeddings_instance = HuggingFaceEmbeddings(
        model_name=settings.embedding_model,
        model_kwargs={"device": settings.embedding_device},
        encode_kwargs={"normalize_embeddings": settings.embedding_normalize},
    )
    return _embeddings_instance