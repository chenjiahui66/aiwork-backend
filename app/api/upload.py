"""
上传接口 - 接收文件 -> 存到 upload_dir -> 加载 -> 切片 -> 入向量库
"""
import logging
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core.config import settings
from app.models.schemas import UploadResponse
from app.rag import loader, splitter, vector_store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["upload"])


@router.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)) -> UploadResponse:
    """
    上传文档并入库

    流程:
    1. 保存文件到 upload_dir(用 UUID 重命名, 避免冲突)
    2. 加载 -> 切片 -> 入库
    3. 返回 doc_id 和 chunk_count
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名为空")

    ext = Path(file.filename).suffix.lower()
    if ext not in loader.SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {ext}。支持: {', '.join(sorted(loader.SUPPORTED_EXTENSIONS))}",
        )

    # 1. 保存
    doc_id = uuid.uuid4().hex[:16]  # 短 UUID 够用
    safe_filename = f"{doc_id}_{file.filename}"
    save_path = settings.upload_path / safe_filename

    try:
        content = await file.read()
        save_path.write_bytes(content)
    except Exception as e:
        logger.exception("保存文件失败")
        raise HTTPException(status_code=500, detail=f"保存文件失败: {e}")

    logger.info(
        "📥 上传: %s -> %s (size=%d, doc_id=%s)",
        file.filename,
        save_path.name,
        len(content),
        doc_id,
    )

    # 2. 加载
    try:
        docs = loader.load_document(save_path)
    except Exception as e:
        # 回滚: 删除已保存的文件
        save_path.unlink(missing_ok=True)
        logger.exception("加载文档失败")
        raise HTTPException(status_code=400, detail=f"加载文档失败: {e}")

    # 3. 切片
    chunks = splitter.split_documents(docs)

    # 4. 入库
    try:
        chunk_count = vector_store.add_chunks(chunks, doc_id=doc_id)
    except Exception as e:
        save_path.unlink(missing_ok=True)
        logger.exception("入库失败")
        raise HTTPException(status_code=500, detail=f"入库失败: {e}")

    return UploadResponse(
        doc_id=doc_id,
        filename=file.filename,
        file_size=len(content),
        chunk_count=chunk_count,
        status="success",
        message=f"成功入库 {chunk_count} 个切片",
    )


@router.get("/documents")
async def list_documents() -> dict:
    """列出知识库里所有文档"""
    docs = vector_store.list_documents()
    return {"total": len(docs), "documents": docs}


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str) -> dict:
    """删除某个文档(同时清掉向量库里的 chunk)"""
    count = vector_store.delete_document(doc_id)
    # 同时删除 upload_dir 里的文件
    for f in settings.upload_path.iterdir():
        if f.name.startswith(f"{doc_id}_"):
            f.unlink(missing_ok=True)
            logger.info("🗑️ 删除上传文件: %s", f.name)
            break
    return {"deleted_chunks": count, "doc_id": doc_id}