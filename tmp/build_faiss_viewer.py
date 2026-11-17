"""
build_faiss_viewer.py — 生成 FAISS 向量库可视化页面

用法:
    cd D:\\project\\MVPdemo\\aiwork-backend
    .\\.venv\\Scripts\\python.exe tmp\\build_faiss_viewer.py

产出:
    tmp\\faiss_viewer.html      ← 双击用浏览器打开
    tmp\\faiss_viz_data.json    ← 中间数据（可删）

数据来源:
    data\\chroma\\aiwork_kb.faiss  (向量)
    data\\chroma\\aiwork_kb.pkl    (原文 + metadata)

上传新文档后重跑一次即可刷新页面。
"""
import json
import pickle
from pathlib import Path

import faiss
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
VEC_DIR = ROOT / "data" / "chroma"
TPL = ROOT / "tmp" / "faiss_viewer.template.html"
DATA_OUT = ROOT / "tmp" / "faiss_viz_data.json"
HTML_OUT = ROOT / "tmp" / "faiss_viewer.html"
INDEX_NAME = "aiwork_kb"

DOC_COLORS = ["#3b82f6", "#f59e0b", "#10b981", "#f43f5e"]


def export_data() -> dict:
    """读 FAISS + pkl, 算相似度矩阵和 PCA 2D 投影"""
    index = faiss.read_index(str(VEC_DIR / f"{INDEX_NAME}.faiss"))
    n, d = index.ntotal, index.d
    matrix = index.reconstruct_n(0, n).astype(np.float64)

    with open(VEC_DIR / f"{INDEX_NAME}.pkl", "rb") as f:
        docstore, index_to_id = pickle.load(f)

    # 按 FAISS 索引顺序对齐（保证 id ↔ 向量一一对应）
    chunks = []
    for i in range(n):
        key = index_to_id[i]
        doc = docstore._dict[key]
        m = doc.metadata
        chunks.append({
            "id": i,
            "key": key,
            "text": doc.page_content,
            "filename": m.get("filename", "?"),
            "doc_id": m.get("doc_id", "?"),
            "chunk_index": m.get("chunk_index", 0),
            "page": m.get("page", 0),
            "total_pages": m.get("total_pages", 0),
            "words": len(doc.page_content),
        })

    # 余弦相似度矩阵（bge 已归一化 → 点积即余弦）
    normed = matrix / np.clip(np.linalg.norm(matrix, axis=1, keepdims=True), 1e-9, None)
    sim = normed @ normed.T
    np.fill_diagonal(sim, 1.0)
    off = sim[~np.eye(n, dtype=bool)]

    # PCA → 2D
    centered = matrix - matrix.mean(axis=0)
    u, s, vt = np.linalg.svd(centered, full_matrices=False)
    coords = centered @ vt[:2].T
    var_explained = (s[:2] ** 2 / (s ** 2).sum()).tolist()
    for axis in range(2):
        c = coords[:, axis]
        coords[:, axis] = (c - c.min()) / max(c.max() - c.min(), 1e-9)

    # 文档分组
    docs = {}
    for c in chunks:
        docs.setdefault(c["doc_id"], {"filename": c["filename"], "chunks": 0})
        docs[c["doc_id"]]["chunks"] += 1
    doc_list = []
    for i, (k, v) in enumerate(docs.items()):
        doc_list.append({"doc_id": k, **v, "color": DOC_COLORS[i % len(DOC_COLORS)], "idx": i})

    return {
        "meta": {
            "ntotal": n,
            "dim": d,
            "index_type": type(index).__name__,
            "metric": "L2 (余弦等价，bge 已归一化)",
            "var_explained": var_explained,
            "sim_offdiag_min": float(off.min()),
            "sim_offdiag_max": float(off.max()),
            "sim_mean_offdiag": float(off.mean()),
        },
        "docs": doc_list,
        "chunks": chunks,
        "sim": [[round(float(v), 3) for v in row] for row in sim],
        "coords": [[round(float(v), 4) for v in row] for row in coords],
    }


def main():
    print("读取向量库...")
    payload = export_data()
    DATA_OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"  chunks={len(payload['chunks'])}, 文档={len(payload['docs'])}, "
          f"相似度非对角范围 [{payload['meta']['sim_offdiag_min']:.3f}, {payload['meta']['sim_offdiag_max']:.3f}]")

    print("注入 HTML...")
    html = TPL.read_text(encoding="utf-8")
    assert "/*__DATA__*/" in html, f"模板占位符缺失: {TPL}"
    data_json = DATA_OUT.read_text(encoding="utf-8").replace("</", "<\\/")
    html = html.replace("/*__DATA__*/", data_json)
    HTML_OUT.write_text(html, encoding="utf-8")

    print(f"\n✅ 完成: {HTML_OUT}  ({HTML_OUT.stat().st_size / 1024:.1f} KB)")
    print(f"   双击用浏览器打开即可（自包含单文件，无需服务器）")


if __name__ == "__main__":
    main()
