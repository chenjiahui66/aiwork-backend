"""
RAG 端到端测试用例

不依赖外部服务启动 - 直接用 FastAPI TestClient 跑
用法:
    python tests/test_rag_e2e.py

流程:
    1. 生成临时 Markdown 文档(模拟企业员工手册)
    2. POST /api/upload       - 上传
    3. GET  /api/documents    - 验证入库
    4. POST /api/chat         - 问3个问题
    5. DELETE /api/documents/{id} - 清理

打印每个步骤结果,最后统计通过率
"""
import json
import sys
import tempfile
from pathlib import Path

# 让 import 找到 app 包
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# === 准备: 模拟一份企业文档 ===

SAMPLE_DOC = """# MiniMax 公司员工手册 (2026 版)

## 第一章 工作时间

公司实行弹性工作制。员工每天工作 8 小时,核心工作时间为 10:00 - 16:00。
员工可在 8:00 - 10:00 之间开始工作,相应地在 16:00 - 19:00 之间结束。
周末双休,如需加班需提前申请,加班费按国家规定执行。

## 第二章 薪酬福利

试用期 3 个月,试用期薪资为正式薪资的 80%。
转正后薪资由基本工资、绩效奖金、年终奖三部分构成。
公司为全体员工缴纳五险一金,按工资基数 12% 缴纳住房公积金。
每年 6 月和 12 月各发一次绩效奖金,根据部门和个人表现评定。

## 第三章 休假制度

员工每年享有 10 天年假,工作满 5 年增加至 15 天,满 10 年增加至 20 天。
病假需提供医院证明,3 天以内无需医院证明,超过 3 天需提供二级以上医院诊断证明。
婚假 10 天,产假 158 天,陪产假 15 天,丧假根据亲属关系 1-5 天不等。

## 第四章 报销流程

差旅报销需在返回公司后 5 个工作日内提交。
报销单据需包含发票原件、出差申请单、行程明细。
单次报销金额超过 5000 元需部门总监审批,超过 20000 元需 CFO 审批。
报销款一般在提交后 10 个工作日内到账。

## 第五章 技术栈

后端主语言为 Python 3.10+,使用 FastAPI 框架。
数据库主用 PostgreSQL,缓存使用 Redis。
前端主用 Vue 3 + TypeScript,UI 库使用 Element Plus。
AI 方向使用 LangChain + LangGraph,向量库使用 Chroma 或 Milvus。
"""


# === 测试用例 ===

TEST_CASES = [
    {
        "question": "公司试用期多久?",
        "expect_keywords": ["3 个月", "80%"],
        "expect_refuse": False,
        "description": "命中型 - 答案在文档里",
    },
    {
        "question": "公司年假最多能休多少天?",
        "expect_keywords": ["10 年", "20 天"],
        "expect_refuse": False,
        "description": "命中型 - 需要稍微推理",
    },
    {
        "question": "公司食堂有什么菜?",
        "expect_keywords": [],
        "expect_refuse": True,
        "description": "拒答型 - 文档里没有",
    },
]


def run_test():
    """主测试流程"""
    from fastapi.testclient import TestClient

    from app.main import app
    from app.rag import vector_store

    # === 0. 清空向量库(测试干净起点) ===
    print("=" * 60)
    print(" RAG 端到端测试")
    print("=" * 60)
    print("\n[0] 清空向量库...")
    vector_store.reset_vector_store()
    print("    ✅ 完成")

    client = TestClient(app)

    # === 1. 准备临时文档 ===
    print("\n[1] 准备测试文档...")
    tmp_path = Path(tempfile.gettempdir()) / "minimax_handbook.md"
    tmp_path.write_text(SAMPLE_DOC, encoding="utf-8")
    print(f"    📄 文件: {tmp_path}")
    print(f"    📊 大小: {tmp_path.stat().st_size} 字节")

    # === 2. 上传 ===
    print("\n[2] POST /api/upload")
    with open(tmp_path, "rb") as f:
        resp = client.post(
            "/api/upload",
            files={"file": ("minimax_handbook.md", f, "text/markdown")},
        )

    if resp.status_code != 200:
        print(f"    ❌ 上传失败: {resp.status_code}")
        print(f"    {resp.text}")
        return False

    upload_data = resp.json()
    doc_id = upload_data["doc_id"]
    chunk_count = upload_data["chunk_count"]
    print(f"    ✅ 上传成功")
    print(f"       doc_id     = {doc_id}")
    print(f"       chunk_count = {chunk_count}")

    if chunk_count < 3:
        print(f"    ⚠️ chunk 数偏少,预期至少 3 个")

    # === 3. 列文档 ===
    print("\n[3] GET /api/documents")
    resp = client.get("/api/documents")
    docs = resp.json()
    print(f"    ✅ 当前共 {docs['total']} 个文档")
    for d in docs["documents"]:
        print(f"       - {d['filename']} ({d['chunk_count']} chunks)")

    if docs["total"] != 1:
        print(f"    ❌ 预期 1 个文档,实际 {docs['total']} 个")
        return False

    # === 4. 问答测试 ===
    print("\n[4] POST /api/chat (问 3 个问题)")
    passed = 0
    failed = 0

    for i, tc in enumerate(TEST_CASES, 1):
        print(f"\n    --- 问题 {i}: {tc['question']} ---")
        print(f"        类型: {tc['description']}")

        # 用 stream 接口但不用 stream 模式,简化测试
        resp = client.post(
            "/api/chat",
            json={"question": tc["question"], "top_k": 3},
        )

        if resp.status_code != 200:
            print(f"        ❌ HTTP {resp.status_code}")
            failed += 1
            continue

        # 解析 SSE 事件流
        full_answer = ""
        sources = []

        for line in resp.text.split("\n"):
            if not line.startswith("data: "):
                continue
            try:
                event = json.loads(line[6:])
            except json.JSONDecodeError:
                continue

            if event.get("type") == "sources":
                sources = event.get("sources", [])
            elif event.get("type") == "token":
                full_answer += event.get("content", "")
            elif event.get("type") == "error":
                print(f"        ❌ 后端错误: {event.get('message')}")

        print(f"        检索到 {len(sources)} 个引用:")
        for j, src in enumerate(sources, 1):
            preview = src["content"][:60].replace("\n", " ")
            print(f"          [{j}] {src['filename']} (score={src['score']:.3f})")
            print(f"              {preview}...")

        print(f"        回答: {full_answer[:120]}...")

        # 校验
        is_refuse = "未在知识库中找到" in full_answer or "未找到" in full_answer

        if tc["expect_refuse"]:
            if is_refuse:
                print(f"        ✅ 正确拒答")
                passed += 1
            else:
                print(f"        ❌ 应该拒答但没拒")
                failed += 1
        else:
            if is_refuse:
                print(f"        ❌ 不应该拒答但拒了")
                failed += 1
                continue

            matched = [k for k in tc["expect_keywords"] if k in full_answer]
            if matched:
                print(f"        ✅ 命中关键词: {matched}")
                passed += 1
            else:
                print(f"        ❌ 未命中预期关键词: {tc['expect_keywords']}")
                failed += 1

    # === 5. 清理 ===
    print("\n[5] DELETE /api/documents/{doc_id}")
    resp = client.delete(f"/api/documents/{doc_id}")
    print(f"    ✅ 清理: {resp.json()}")

    # === 汇总 ===
    print("\n" + "=" * 60)
    print(f" 测试结果: {passed} 通过 / {failed} 失败 / 共 {len(TEST_CASES)}")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_test()
    sys.exit(0 if success else 1)