"""
Pydantic 数据模型 - API 层与 rag 层之间共享
"""
from typing import Literal

from pydantic import BaseModel, Field


# ===== 上传相关 =====

class UploadResponse(BaseModel):
    """上传文档后的响应"""
    doc_id: str = Field(..., description="文档唯一 ID(后续管理用)")
    filename: str = Field(..., description="原始文件名")
    file_size: int = Field(..., description="文件大小(字节)")
    chunk_count: int = Field(..., description="切片数量")
    status: Literal["success", "failed"] = "success"
    message: str = ""


class DocumentInfo(BaseModel):
    """知识库中文档列表项"""
    doc_id: str
    filename: str
    file_size: int
    upload_time: str  # ISO 格式
    chunk_count: int


class DocumentListResponse(BaseModel):
    """文档列表响应"""
    total: int
    documents: list[DocumentInfo]


# ===== 对话相关 =====

class ChatSource(BaseModel):
    """引用来源(检索到的文档片段)"""
    chunk_id: str = Field(..., description="chunk ID")
    doc_id: str
    filename: str
    content: str = Field(..., description="片段内容")
    score: float = Field(..., description="相似度分数(越低越相似)")


class ChatRequest(BaseModel):
    """对话请求"""
    question: str = Field(..., min_length=1, max_length=2000)
    top_k: int | None = Field(None, description="覆盖默认 top_k")
    history: list[dict] = Field(
        default_factory=list,
        description="对话历史, 格式 [{role: 'user'|'assistant', content: '...'}]",
    )


class ChatResponse(BaseModel):
    """对话响应(非流式)"""
    answer: str
    sources: list[ChatSource]


# ===== 通用 =====

class HealthResponse(BaseModel):
    """健康检查"""
    status: Literal["ok", "degraded"] = "ok"
    llm_model: str
    embedding_model: str
    chroma_dir: str


# ===== 写作相关 =====

class WriterRequest(BaseModel):
    """智能写作请求

    inputs 字段根据 write_type 不同而不同:
    - email:        {tone, recipient, requirement}
    - weekly_report: {raw_notes}
    - marketing:    {product_info, target_audience, word_limit}
    - speech:       {scene, key_points, duration}
    """
    write_type: str = Field(..., description="写作类型: email/weekly_report/marketing/speech")
    inputs: dict = Field(..., description="写作参数(按类型不同)")
    history: list[dict] = Field(default_factory=list, description="多轮对话历史")


# ===== 摘要相关 =====

class TextSummaryRequest(BaseModel):
    """纯文本摘要请求"""
    text: str = Field(..., min_length=10, description="要摘要的文本")
    summary_type: Literal["short", "key_points", "tldr"] = Field(
        "short", description="摘要类型"
    )


class DocSummaryRequest(BaseModel):
    """基于已入库文档的摘要请求"""
    doc_id: str = Field(..., description="知识库中的文档 ID")
    summary_type: Literal["short", "key_points", "tldr"] = Field(
        "short", description="摘要类型"
    )


# ===== 翻译相关 =====

class TranslateRequest(BaseModel):
    """翻译请求"""
    text: str = Field(..., min_length=1, max_length=20000, description="原文")
    target_lang: str = Field(..., description="目标语言 code, 如 en/zh/ja")
    source_lang: str | None = Field(None, description="源语言 code, 不传则自动检测")
    domain: Literal["general", "business", "it", "legal", "medical"] = Field(
        "general", description="翻译领域"
    )
    glossary: dict[str, str] = Field(
        default_factory=dict,
        description="术语表, 如 {RAG: 检索增强生成}",
    )


# ===== 代码助手相关 =====

class CodeRequest(BaseModel):
    """代码分析请求"""
    task: Literal["explain", "refactor", "comment", "debug", "translate"] = Field(
        ..., description="任务类型"
    )
    code: str = Field(..., min_length=1, description="源码")
    language: str = Field(..., description="源码语言, 如 python/javascript")
    target_language: str | None = Field(None, description="翻译任务的目标语言")


# ===== 数据洞察相关 =====

class InsightQueryRequest(BaseModel):
    """自然语言查询请求"""
    question: str = Field(..., min_length=2, max_length=500, description="业务问题")


# ===== HR 助手相关 =====

class HrRequest(BaseModel):
    """HR 助手请求

    inputs 字段根据 task 不同:
    - jd:           {position, industry, requirements, location, experience}
    - resume_screen: {jd_excerpt, resume_text}
    - onboarding:   {employee_name, start_date, position, department, manager, company}
    """
    task: Literal["jd", "resume_screen", "onboarding"] = Field(..., description="任务")
    inputs: dict = Field(..., description="任务参数")


# ===== 设计助手相关 =====

class DesignRequest(BaseModel):
    """设计助手请求 — 生成可粘贴到 Midjourney/DALL-E 等工具的 prompt"""
    design_type: Literal["poster", "banner", "logo", "illustration", "social", "ppt"] = Field(
        ..., description="设计类型"
    )
    subject: str = Field(..., min_length=1, max_length=500, description="主题/产品")
    style: str | None = Field(None, description="风格偏好")
    color: str | None = Field(None, description="主色调")
    scene: str | None = Field(None, description="使用场景")
    extra: str | None = Field(None, description="额外要求")


# ===== 会议助手相关 =====

class MeetingRequest(BaseModel):
    """会议内容处理请求

    task: minutes(纪要) / todo(待办) / summary(摘要)
    transcript: 会议转写文本(浏览器 ASR 实时输出 或用户粘贴/上传)
    """
    task: Literal["minutes", "todo", "summary"] = Field(..., description="任务")
    transcript: str = Field(..., min_length=10, description="会议转写文本")