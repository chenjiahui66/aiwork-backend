"""
文档加载器: 根据文件扩展名选择不同的 loader

支持格式:
- .pdf  → PyPDFLoader
- .docx → Docx2txtLoader
- .md   → UnstructuredMarkdownLoader
- .txt  → TextLoader
- 其他  → 报错
"""
import logging
from pathlib import Path

from langchain_community.document_loaders import (
    Docx2txtLoader,
    PyPDFLoader,
    TextLoader,
    UnstructuredMarkdownLoader,
)
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".md", ".txt"}


def load_document(file_path: str | Path) -> list[Document]:
    """
    加载单个文件, 返回 langchain Document 列表

    Document.page_content: 文本内容
    Document.metadata: {source, page(可选), ...}
    """
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"文件不存在: {p}")

    ext = p.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"不支持的文件格式: {ext}。支持: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    logger.info("加载文档: %s (ext=%s)", p.name, ext)

    if ext == ".pdf":
        loader = PyPDFLoader(str(p))
    elif ext == ".docx":
        loader = Docx2txtLoader(str(p))
    elif ext == ".md":
        loader = UnstructuredMarkdownLoader(str(p), mode="single")
    elif ext == ".txt":
        loader = TextLoader(str(p), encoding="utf-8")

    docs = loader.load()

    # 统一在 metadata 里塞 filename(后续引用展示用)
    for d in docs:
        d.metadata["filename"] = p.name

    logger.info("✅ 加载完成: %s -> %d 页/段", p.name, len(docs))
    return docs