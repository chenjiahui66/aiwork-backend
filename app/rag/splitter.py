"""
文本切片策略

中文场景默认用 RecursiveCharacterTextSplitter, 优先级分隔符:
["\n\n", "\n", "。", "！", "？", "；", " ", ""]
这样能尽量保持段落/句子的语义完整性
"""
import logging

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import settings

logger = logging.getLogger(__name__)

# 中文友好的分隔符(优先级从高到低)
CHINESE_SEPARATORS = [
    "\n\n",   # 段落
    "\n",     # 换行
    "。",     # 中文句号
    "！",     # 感叹号
    "？",     # 问号
    "；",     # 分号
    "，",     # 逗号
    "、",     # 顿号
    " ",      # 空格
    "",       # 字符(兜底)
]


def split_documents(docs: list[Document]) -> list[Document]:
    """
    把加载出来的 Document 切成更小的 chunk

    每片大小: settings.chunk_size(默认 500 字符)
    重叠:     settings.chunk_overlap(默认 80 字符)
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=CHINESE_SEPARATORS,
        length_function=len,
    )
    chunks = splitter.split_documents(docs)
    logger.info(
        "切片完成: %d 篇文档 -> %d 个 chunk (size=%d, overlap=%d)",
        len(docs),
        len(chunks),
        settings.chunk_size,
        settings.chunk_overlap,
    )
    return chunks