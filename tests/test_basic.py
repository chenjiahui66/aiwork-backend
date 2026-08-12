"""
最小验证脚本 - 跑通"启动 + 上传 + 检索"三个核心动作

用法:
    python tests/test_basic.py
"""
import sys
import time
from pathlib import Path

# 让 import 找到 app 包
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def check_env() -> bool:
    """检查环境变量"""
    from app.core.config import settings
    if not settings.siliconflow_api_key:
        print("❌ SILICONFLOW_API_KEY 未配置")
        print("   请复制 .env.example 为 .env 并填入 API Key")
        return False
    print(f"✅ API Key 已配置 (前 8 位: {settings.siliconflow_api_key[:8]}...)")
    print(f"   LLM Model: {settings.llm_model}")
    print(f"   Embedding Model: {settings.embedding_model}")
    print(f"   Chroma Dir: {settings.chroma_path}")
    return True


def check_embedding() -> bool:
    """测试 Embedding 是否能联通"""
    from app.core.llm import get_embeddings
    print("\n[1/3] 测试 Embedding 联通...")
    try:
        emb = get_embeddings()
        vec = emb.embed_query("你好")
        print(f"   ✅ Embedding 正常 (维度: {len(vec)})")
        return True
    except Exception as e:
        print(f"   ❌ Embedding 失败: {e}")
        return False


def check_llm() -> bool:
    """测试 LLM 是否能联通"""
    from app.core.llm import get_llm
    print("\n[2/3] 测试 LLM 联通...")
    try:
        llm = get_llm()
        resp = llm.invoke("用一句话介绍自己")
        print(f"   ✅ LLM 正常")
        print(f"   回答: {resp.content[:80]}")
        return True
    except Exception as e:
        print(f"   ❌ LLM 失败: {e}")
        return False


def check_chroma() -> bool:
    """测试 Chroma 初始化"""
    from app.rag import vector_store
    print("\n[3/3] 测试 Chroma 初始化...")
    try:
        store = vector_store.get_vector_store()
        count = store._collection.count()
        print(f"   ✅ Chroma 正常 (当前已有 {count} 个 chunk)")
        return True
    except Exception as e:
        print(f"   ❌ Chroma 失败: {e}")
        return False


if __name__ == "__main__":
    print("=" * 50)
    print(" AiWork Backend 验证脚本")
    print("=" * 50)

    start = time.time()

    if not check_env():
        sys.exit(1)
    if not check_embedding():
        sys.exit(1)
    if not check_llm():
        sys.exit(1)
    if not check_chroma():
        sys.exit(1)

    elapsed = time.time() - start
    print("\n" + "=" * 50)
    print(f" ✅ 全部通过 ({elapsed:.1f}s)")
    print("=" * 50)
    print("可以启动服务: python -m app.main")