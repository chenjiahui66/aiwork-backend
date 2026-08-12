"""
LLM + Embedding 客户端封装

硅基流动走 OpenAI 兼容协议, 直接用 langchain_openai.ChatOpenAI / OpenAIEmbeddings
只需把 base_url 改成 https://api.siliconflow.cn/v1 即可
"""
from functools import lru_cache

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.core.config import settings


@lru_cache(maxsize=1)
def get_llm() -> ChatOpenAI:
    """获取 LLM 客户端(单例)"""
    if not settings.siliconflow_api_key:
        raise RuntimeError(
            "SILICONFLOW_API_KEY 未配置。请复制 .env.example 为 .env 并填入 API Key。"
        )
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.siliconflow_api_key,
        base_url="https://api.siliconflow.cn/v1",
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
    )


@lru_cache(maxsize=1)
def get_embeddings() -> OpenAIEmbeddings:
    """获取 Embedding 客户端(单例)"""
    if not settings.siliconflow_api_key:
        raise RuntimeError(
            "SILICONFLOW_API_KEY 未配置。请复制 .env.example 为 .env 并填入 API Key。"
        )
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=settings.siliconflow_api_key,
        base_url=settings.embedding_base_url,
        # bge-m3 推荐设置: 编码时 normalize, 检索时用余弦相似度
        check_embedding_ctx_length=False,
    )