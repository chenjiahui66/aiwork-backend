"""
FastAPI 入口
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, coder, designer, email, feishu, hr, insight, meeting, summarizer, translator, upload, workflow, writer
from app.core.config import settings
from app.models.schemas import HealthResponse

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AiWork Backend - 智能问答 RAG",
    version="0.1.0",
    description="基于 LangChain + Chroma 的企业知识库问答服务",
)

# CORS - 允许前端(Vue dev server 5175/生产域名)访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发阶段全开, 部署时收紧
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由
app.include_router(upload.router)
app.include_router(chat.router)
app.include_router(writer.router)
app.include_router(summarizer.router)
app.include_router(translator.router)
app.include_router(coder.router)
app.include_router(insight.router)
app.include_router(hr.router)
app.include_router(designer.router)
app.include_router(meeting.router)
app.include_router(workflow.router)
app.include_router(email.router)
app.include_router(feishu.router)


@app.get("/")
async def root() -> dict:
    return {
        "name": "AiWork RAG Backend",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        llm_model=settings.llm_model,
        embedding_model=settings.embedding_model,
        chroma_dir=str(settings.chroma_path),
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=True,  # 开发模式: 代码改动自动 reload
        log_level="info",
    )