# AiWork Backend - AI 应用后端

基于 **FastAPI + LangChain + FAISS** 从零搭建的多模块 AI 应用后端。

> 配合前端 [aiwork](../aiwork) 一起使用，作为 AiWork 平台多个 AI 应用的底层服务。

## 功能模块

| 模块 | 路径前缀 | 说明 |
|------|----------|------|
| 🧠 智能问答 RAG | `/api/upload` `/api/chat` `/api/documents` | 文档入库 + 基于资料的流式问答（带引用） |
| ✍️ 智能写作 | `/api/writer/*` | 邮件 / 周报 / 营销文案 / 演讲稿流式生成 |
| 📄 文档摘要 | `/api/summarizer/*` | 长文/会议纪要 → 短摘要 / 要点 / TL;DR |
| 🌐 智能翻译 | `/api/translator/*` | 14 语言 + 5 领域 + 术语表 |
| 💻 AI 代码助手 | `/api/coder/*` | 解释 / 重构 / 注释 / 调试 / 翻译（17 语言） |
| 📊 数据洞察 | `/api/insight/*` | 自然语言 → SQL → ECharts 图表（演示 SQLite） |
| 👥 HR 助手 | `/api/hr/*` | JD 生成 / 简历筛选 / 入职材料 |
| 🎨 AI 设计助手 | `/api/designer/*` | 生成可粘贴到 MJ/即梦的英文 Prompt |
| 🎙️ 会议助手 | `/api/meeting/*` | 浏览器 STT + 会议纪要 / 待办 / 摘要 |
| 🔗 可视化工作流 | `/api/workflow/*` | LangGraph StateGraph 多步流水线（4 模板） |
| 📧 **SMTP 发邮件** | `/api/email/*` | 通用"发邮件"按钮（SMTP 协议，零新依赖） |
| 📊 **飞书多维表格** | `/api/feishu/*` | 一键导入会议任务到飞书 Bitable |

> 新增模块原则：**一个能力一个文件夹**，不混。

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

### 数据洞察能力

- 🧠 Text-to-SQL：自然语言问题 → 安全 SQL（SELECT-only + 正则黑名单 + SQLite 只读连接）
- 📈 自动图表选型：2 列 ≤6 行 → 饼图；3 列含日期 → 折线；其他 → 柱状/表格
- 🎁 自带演示库：products/sales/employees/user_activity 启动自动灌种子

### 可视化工作流能力

- 🧩 真正的 LangGraph StateGraph（不是用 asyncio 假装）
- 📝 4 预置模板：文档总结流水线 / 客户评论分析 / 竞品对比 / PRD 生成器
- 📊 节点产物累积展示 + 步骤进度条

### SMTP 发邮件能力

- 📧 走标准库 `smtplib`，零新增依赖
- 🔌 兼容 QQ / 163 / Gmail / 腾讯企业邮（同一个 SMTP 代码）
- 📋 适配 465 SSL / 587 STARTTLS / 25 明文（明文仅 mock 用）
- 🚨 4 类细分异常：401 认证 / 502 连接 / 400 拒收 / 503 未配置

### 飞书多维表格能力

- 📊 一键"导入会议任务"到飞书 Bitable
- 🧠 后端 LLM 二次解析会议文本 → 结构化待办 JSON
- ✏️ 前端可手动编辑后再推送
- 🔑 `tenant_access_token` 2 小时缓存 + 自动刷新

## 技术栈

| 组件 | 选型 | 理由 |
|------|------|------|
| Web 框架 | FastAPI | 异步、SSE 原生支持、自动 OpenAPI 文档 |
| LLM | MiniMax-M3（OpenAI 兼容协议） | 1M 上下文、强 Coding/Agent |
| Embedding | 本地 BAAI/bge-small-zh-v1.5 | 中文 SOTA、零 API 成本、~100MB |
| 向量库 | FAISS（faiss-cpu） | Chroma 在 Windows 需 MSVC，FAISS 有预编译包 |
| 文档解析 | pypdf / python-docx / markdown | 按格式分发 |
| 工作流 | LangGraph StateGraph | 真正的图状态机 |
| 邮件 | Python 标准库 smtplib | 零新增依赖 |
| 飞书 | httpx + 飞书 OpenAPI | 异步 HTTP，无 SDK 依赖 |

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

### 文档摘要 / 翻译 / 代码助手 / 数据洞察 / HR / 设计 / 会议

每个模块统一风格：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/<module>/options` | 前端下拉选项（字段 schema / 类型等） |
| POST | `/api/<module>/process` | 流式处理（SSE） |

具体路径：`/api/summarizer/*` `/api/translator/*` `/api/coder/*` `/api/insight/*` `/api/hr/*` `/api/designer/*` `/api/meeting/*`

### 可视化工作流

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/workflow/options` | 列出所有预置工作流模板 |
| POST | `/api/workflow/run` | 流式运行（SSE 事件：`workflow_meta` / `node_start` / `token` / `node_end` / `done`） |

### SMTP 发邮件

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/email/status` | 检查 SMTP 是否配好（前端灰显按钮用） |
| POST | `/api/email/send` | 发送邮件（to/cc/subject/content/is_html） |

### 飞书多维表格

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/feishu/status` | 检查飞书是否配好 + 目标表格 URL |
| GET  | `/api/feishu/tables` | 列出多维表格下所有数据表（调试用） |
| GET  | `/api/feishu/tables/{tid}/fields` | 列出表的字段定义（前端用） |
| POST | `/api/feishu/push-records` | 批量新增记录（最多 1000 条） |
| POST | `/api/feishu/parse-todos` | LLM 把会议文本解析成结构化待办 JSON（SSE） |

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
│   │   ├── writer.py              # /api/writer/*               (写作)
│   │   ├── summarizer.py          # /api/summarizer/*           (摘要)
│   │   ├── translator.py          # /api/translator/*           (翻译)
│   │   ├── coder.py               # /api/coder/*                (代码)
│   │   ├── insight.py             # /api/insight/*              (数据)
│   │   ├── hr.py                  # /api/hr/*                   (HR)
│   │   ├── designer.py            # /api/designer/*             (设计)
│   │   ├── meeting.py             # /api/meeting/*              (会议)
│   │   ├── workflow.py            # /api/workflow/*             (工作流)
│   │   ├── email.py               # /api/email/*                (SMTP)
│   │   └── feishu.py              # /api/feishu/*               (飞书 Bitable)
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
│   ├── summarizer/                # —— 模块 3：文档摘要 ——
│   ├── translator/                # —— 模块 4：智能翻译 ——
│   ├── coder/                     # —— 模块 5：AI 代码助手 ——
│   ├── insight/                   # —— 模块 6：数据洞察（带 seed_db + sql_generator + chart_picker） ——
│   ├── hr/                        # —— 模块 7：HR 助手 ——
│   ├── designer/                  # —— 模块 8：AI 设计助手 ——
│   ├── meeting/                   # —— 模块 9：会议助手 ——
│   ├── workflow/                  # —— 模块 10：可视化工作流（LangGraph） ——
│   ├── email/                     # —— SMTP 发邮件 ——
│   └── feishu/                    # —— 飞书多维表格 Bitable ——
│
│   └── models/
│       └── schemas.py             # Pydantic 模型（请求/响应）
│
├── data/
│   ├── uploads/                   # 上传的原始文件
│   ├── faiss_index/               # FAISS 持久化索引
│   └── insight_demo.db            # 数据洞察演示 SQLite（启动自动建表+灌种子）
├── tests/
│   └── test_basic.py
├── tmp/
│   ├── smoke_email.py             # 本地 mock SMTP 冒烟测试
│   └── smoke_feishu.py            # 本地 mock 飞书 OpenAPI 冒烟测试
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

- [x] 11 个 AI 应用模块 + 邮件 + 飞书集成
- [x] 前端 Vue 应用市场接入（10 个卡片 + 侧边栏）
- [ ] 多轮对话持久化（半天）
- [ ] OCR 图片转文字（半天）
- [ ] 企业邮共享账号（部署给客户时免授权码）

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

**Q: 怎么配 SMTP 让"📧 发邮件"按钮变可点？**
A: 在 `.env` 里填：
```ini
SMTP_HOST=smtp.qq.com            # QQ 邮箱
SMTP_PORT=465                     # 465 SSL 或 587 STARTTLS
SMTP_USER=你的QQ@qq.com
SMTP_PASSWORD=16位授权码          # 不是 QQ 密码!去邮箱后台开 SMTP 服务生成
SMTP_FROM_NAME=AiWork 助手
```
**重点**：`SMTP_PASSWORD` 是授权码（去邮箱后台生成），不是登录密码。改完重启后端。

**Q: 怎么配飞书多维表格让"📊 导入飞书任务"按钮变可点？**
A: 三步：
1. 去 https://open.feishu.cn/ 创建"企业自建应用"，开通 `bitable:app` 权限，拿到 App ID + App Secret
2. 去 https://feishu.cn/base 创建多维表格，从 URL 截取 `app_token` 和 `table_id`
3. 在 `.env` 里填：
```ini
FEISHU_APP_ID=cli_xxxxxxxx
FEISHU_APP_SECRET=xxxxxxxx
FEISHU_BITABLE_APP_TOKEN=xxxxxxxxxxxxx
FEISHU_BITABLE_TABLE_ID=tblxxxxxxxx
```
重启后端。注意：你的多维表格必须有"标题" "责任人" "截止日期" "优先级" 这 4 个字段（或类似名字），否则推送会 400。字段类型说明见 `app/api/feishu.py` 顶部注释。

**Q: LLM 提示 "Input to ChatPromptTemplate is missing variables"？**
A: prompt 里有 `{xxx}` 被 LangChain 当成了变量。**JSON 示例里的 `{` 必须转义成 `{{`**,比如 `{"title": "..."}` → `{{"title": "..."}}`。

**Q: 飞书 API 报 1254000/1254045 错误码？**
A: 字段类型不匹配。`Date` 字段要传毫秒时间戳（`{value: 1700000000000}`），不能传字符串；`SingleSelect` 要传 option 的 key；`Person` 要传 `[{id: "ou_xxx"}]`。先调 `/api/feishu/tables/{tid}/fields` 看字段 schema。