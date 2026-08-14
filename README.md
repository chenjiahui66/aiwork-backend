# AiWork Backend - 智能问答 RAG 服务

基于 **FastAPI + LangChain + Chroma** 从零搭建的企业知识库问答服务。

> 配合前端 [aiwork](../aiwork) 一起使用，作为 AiWork 平台的"智能问答"应用后端。

## 功能

- 📄 **多格式文档入库**：PDF / Word / Markdown / TXT
- ✂️ **中文友好切片**：按段落→句子→逗号→字符的优先级切分
- 🔍 **语义检索**：基于 bge-m3 Embedding + Chroma 向量库
- 💬 **流式问答**：SSE 流式返回，支持引用来源展示
- 🚫 **拒答能力**：知识库没资料时不会瞎编

## 技术栈

| 组件 | 选型 | 理由 |
|------|------|------|
| Web 框架 | FastAPI | 异步、SSE 原生支持、自动 OpenAPI 文档 |
| LLM | MiniMax-M3（OpenAI 兼容协议） | 1M 上下文、强 Coding/Agent |
| Embedding | 本地 bge-small-zh-v1.5 | 中文 SOTA、零 API 成本、~100MB |
| 向量库 | Chroma（本地持久化） | 零部署成本 |
| 文档解析 | pypdf / python-docx / unstructured | 按格式分发 |

## 快速开始

### 1. 安装依赖

建议 Python 3.10+：

```bash
cd D:\project\MVPdemo\aiwork-backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

> **Windows 用户注意**：pip 在中文 Windows 默认用 GBK 读 requirements.txt，文件含中文注释会报 `UnicodeDecodeError`。本项目已全部改成英文注释；如未来你自己扩展了中文内容，请用下面命令强制 UTF-8 安装：
>
> ```powershell
> $env:PYTHONIOENCODING="utf-8"; pip install -r requirements.txt
> ```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并填入 API Key：

```bash
copy .env.example .env     # Windows
```

编辑 `.env`：

```env
MINIMAX_API_KEY=sk-xxxxxxxxxxxxxx
```

申请地址：[https://platform.minimaxi.com](https://platform.minimaxi.com)
（首次使用注册送额度，足够跑大量测试）

### 3. 启动

```bash
python -m app.main

.\.venv\Scripts\python.exe run.py
```

启动后访问：
- 接口文档：http://localhost:8001/docs
- 健康检查：http://localhost:8001/health

> **首次启动会自动下载 embedding 模型**（BAAI/bge-small-zh-v1.5，约 100MB），需要联网，之后会缓存到本地。

### 3. 启动

```bash
python -m app.main
```

或：

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

启动成功后访问：
- 接口文档：http://localhost:8001/docs
- 健康检查：http://localhost:8001/health

## API 列表

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/upload` | 上传文档（multipart/form-data, 字段名 `file`） |
| GET  | `/api/documents` | 列出知识库里所有文档 |
| DELETE | `/api/documents/{doc_id}` | 删除某个文档 |
| POST | `/api/chat` | RAG 流式问答（SSE） |

### 示例：上传文档

```bash
curl -X POST http://localhost:8001/api/upload \
  -F "file=@D:/docs/产品手册.pdf"
```

返回：

```json
{
  "doc_id": "a1b2c3d4e5f6g7h8",
  "filename": "产品手册.pdf",
  "file_size": 245678,
  "chunk_count": 42,
  "status": "success"
}
```

### 示例：流式问答

```bash
curl -N -X POST http://localhost:8001/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "产品保修期是多久？"}'
```

SSE 事件流：

```
data: {"type": "sources", "sources": [...]}

data: {"type": "token", "content": "根据"}

data: {"type": "token", "content": "产品手册"}

data: {"type": "token", "content": "[1]，保修期"}

...

data: {"type": "done"}
```

## 项目结构

```
aiwork-backend/
├── app/
│   ├── main.py            # FastAPI 入口
│   ├── api/
│   │   ├── upload.py      # /api/upload 系列
│   │   └── chat.py        # /api/chat
│   ├── core/
│   │   ├── config.py      # 配置（pydantic-settings）
│   │   └── llm.py         # LLM / Embedding 客户端
│   ├── rag/
│   │   ├── loader.py      # 文档加载
│   │   ├── splitter.py    # 切片
│   │   ├── vector_store.py# Chroma 封装
│   │   └── chain.py       # RAG 核心链（检索+prompt+LLM）
│   └── models/
│       └── schemas.py     # Pydantic 模型
├── data/
│   ├── uploads/           # 上传的原始文件
│   └── chroma/            # Chroma 持久化数据
├── tests/
├── .env.example
├── requirements.txt
└── README.md
```

## 路线图

- [x] D1 后端骨架（当前）
- [ ] D2 前端接入 - 把 AiWork 应用市场"智能问答"卡片接上
- [ ] D4 体验打磨 - 对话历史、引用高亮、多文档管理
- [ ] D5 评测 + 部署

## 常见问题

**Q: Chroma 报错 "sqlite3 version too old"？**
A: Python 3.7 自带的 sqlite 太老，需要 Python 3.10+ 或手动升级 sqlite。

**Q: 硅基流动调用失败 "invalid api key"？**
A: 检查 `.env` 里 `SILICONFLOW_API_KEY` 是否正确，键名注意区分大小写。

**Q: bge-m3 embedding 很慢？**
A: 第一次调用会下载模型（硅基流动是云端 API 不需要本地下载）。如果用本地 embedding 模型请参考 langchain_huggingface。