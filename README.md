# AiWork Backend - AI 应用后端

基于 **FastAPI + LangChain + FAISS** 从零搭建的多模块 AI 应用后端。

> 配合前端 [aiwork](../aiwork) 一起使用，作为 AiWork 平台多个 AI 应用的底层服务。

## 功能模块

| 模块 | 路径前缀 | 说明 |
|------|----------|------|
| 🧠 智能问答 RAG | `/api/upload` `/api/chat` `/api/documents` | 文档入库 + 基于资料的流式问答（带引用） |
| ✍️ 智能写作 | `/api/writer/*` | 邮件 / 周报 / 营销文案 / 演讲稿流式生成 |

> 新增模块原则：一个能力一个文件夹，不混。

### 智能问答 RAG 能力

- 📄 多格式文档入库：PDF / Word / Markdown / TXT
- ✂️ 中文友好切片：按段落→句子→逗号→字符的优先级切分
- 🔍 语义检索：基于 bge-small-zh Embedding + FAISS 向量库
- 💬 流式问答：SSE 流式返回，支持引用来源展示
- 🚫 拒答能力：知识库没资料时不会瞎编

### 智能写作能力

- 📧 邮件撰写（自定义语气 / 收件人）
- 📋 周报生成（基于本周工作内容生成结构化周报）
- 📢 营销文案（产品卖点 → 有吸引力文案）
- 🎤 演讲稿（场景 + 核心观点 → 完整演讲稿）

## 技术栈

| 组件 | 选型 | 理由 |
|------|------|------|
| Web 框架 | FastAPI | 异步、SSE 原生支持、自动 OpenAPI 文档 |
| LLM | MiniMax-M3（OpenAI 兼容协议） | 1M 上下文、强 Coding/Agent |
| Embedding | 本地 BAAI/bge-small-zh-v1.5 | 中文 SOTA、零 API 成本、~100MB |
| 向量库 | FAISS（faiss-cpu） | Chroma 在 Windows 需 MSVC，FAISS 有预编译包 |
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
# 方式 A：用项目自带的 run.py（开发推荐，自动 reload）
.\.venv\Scripts\python.exe run.py

# 方式 B：直接 uvicorn
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

启动后访问：
- 接口文档：http://localhost:8001/docs
- 健康检查：http://localhost:8001/health

> **首次启动会自动下载 embedding 模型**（BAAI/bge-small-zh-v1.5，约 100MB），需要联网，之后会缓存到本地。
> 
> **Windows PowerShell 用户**：永远带绝对路径 `.\.venv\Scripts\python.exe`，不要裸敲 `python`（PATH 默认指向系统 Python 3.13，不在 venv 里）。

## API 列表

### 智能问答

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/upload` | 上传文档（multipart/form-data, 字段名 `file`） |
| GET  | `/api/documents` | 列出知识库里所有文档 |
| DELETE | `/api/documents/{doc_id}` | 删除某个文档 |
| POST | `/api/chat` | RAG 流式问答（SSE） |

### 智能写作

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/writer/types` | 列出支持的写作类型 |
| POST | `/api/writer/generate` | 流式生成写作内容（SSE） |

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

### 示例：智能写作（邮件）

```bash
curl -N -X POST http://localhost:8001/api/writer/generate \
  -H "Content-Type: application/json" \
  -d '{"write_type":"email","inputs":{"tone":"正式","recipient":"王总","requirement":"请批一下年假申请"}}'
```

SSE 事件流（写作不检索，所以**没有 sources 事件**）：

```
data: {"type": "token", "content": "Subject:"}

data: {"type": "token", "content": " 年假申请"}

...

data: {"type": "done"}
```

支持的写作类型：`email` / `weekly_report` / `marketing` / `speech`

## 项目结构

> 模块化原则：**一个能力一个文件夹**。`rag/` 跟 `writer/` 平级，互不依赖。

```
aiwork-backend/
├── app/
│   ├── main.py                    # FastAPI 入口 + CORS + include_router
│   │
│   ├── api/                       # —— HTTP 边界层，每个模块一个文件 ——
│   │   ├── upload.py              # /api/upload, /api/documents  (问答)
│   │   ├── chat.py                # /api/chat (SSE)            (问答)
│   │   └── writer.py              # /api/writer/*               (写作)
│   │
│   ├── core/                      # —— 共享基础设施，谁都能用 ——
│   │   ├── config.py              # pydantic-settings 配置
│   │   └── llm.py                 # LLM / Embedding 单例
│   │
│   ├── rag/                       # —— 模块 1：智能问答 ——
│   │   ├── loader.py              # 文档加载（按格式分发）
│   │   ├── splitter.py            # 切片（中文友好）
│   │   ├── vector_store.py        # FAISS 增删查
│   │   └── chain.py               # RAG 链：检索 → prompt → LLM
│   │
│   ├── writer/                    # —— 模块 2：智能写作 ——
│   │   ├── prompts.py             # 写作 prompt 模板（邮件/周报/营销/演讲）
│   │   └── chain.py               # 写作链：输入字段 → prompt → LLM
│   │                              # （不查向量库，纯 LLM 生成）
│   │
│   └── models/
│       └── schemas.py             # Pydantic 模型（请求/响应）
│
├── data/
│   ├── uploads/                   # 上传的原始文件
│   └── faiss_index/               # FAISS 持久化索引
├── tests/
│   ├── test_basic.py              # 单元测试
│   └── test_rag_e2e.py            # 端到端 RAG 验证
├── tools/
│   └── dump_vector_db.py          # 调试：导出 FAISS 内容
├── .env.example
├── requirements.txt
└── README.md
```

### 模块切分判断口诀

| 这个新功能…… | 放哪 |
|---|---|
| **要查向量库**（问答 / 查资料 / 找相似） | `rag/` |
| **纯 LLM 生成**（写作 / 翻译 / 总结 / 改写） | `writer/` |
| **要操作数据库 / 文件**（用户 / 订单 / 上传） | 新开 `service/` 或 `db/` |
| **要调用外部 API**（天气 / 搜索 / 发邮件） | 新开 `tools/` 或 `integrations/` |
| **共用基础设施**（LLM / 配置 / 日志） | `core/` |

### 加新模块的标准 4 步

```
1. app/<new_module>/  建新文件夹(__init__.py + 你需要的逻辑文件)
2. app/models/schemas.py  加请求/响应 BaseModel
3. app/api/<new_module>.py  写 @router.post/get, 包成 HTTP 接口
4. app/main.py  app.include_router(your_router)  ← 漏了这步就 404
```

## 路线图

- [x] D1 后端骨架（当前）
- [ ] D2 前端接入 - 把 AiWork 应用市场"智能问答"卡片接上
- [ ] D4 体验打磨 - 对话历史、引用高亮、多文档管理
- [ ] D5 评测 + 部署

## 常见问题

**Q: PowerShell 敲 `python` 报 `No module named 'fastapi'`？**
A: Windows PowerShell 默认 `python` 解析到全局 Python（如 `C:\Users\10909\AppData\Local\Programs\Python\Python313\python.exe`），不是项目 venv。**永远带绝对路径**：`.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8001`，或用项目里的 `.\dev-shell.ps1` 重新定义 python。

**Q: Chroma 报错 "sqlite3 version too old" 或 Windows 上需要 MSVC 编译？**
A: 项目已改用 **FAISS**（`faiss-cpu` 有 Windows 预编译 wheel）。如果要用 Chroma，需要 Python 3.10+ 且装 Visual Studio Build Tools。

**Q: MiniMax 调用失败 "invalid api key"？**
A: 检查 `.env` 里 `MINIMAX_API_KEY` 是否正确。本项目用 MiniMax-M3（OpenAI 兼容协议），base URL 在 `app/core/config.py`。

**Q: 第一次启动很慢 / 报模型下载超时？**
A: 首次启动会自动从 HuggingFace 下载 `BAAI/bge-small-zh-v1.5`（约 100MB）。如果下载慢或失败，可设置环境变量 `HF_ENDPOINT=https://hf-mirror.com` 走国内镜像。

**Q: 换 embedding 模型后检索结果不对？**
A: 不同模型的向量维度不同，必须**删掉旧 FAISS 索引**重新入库：
```bash
rm -rf data/faiss_index/
```
然后重新上传文档。