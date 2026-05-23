"""Reranker 封装 — DashScope gte-rerank-v2

向量检索是"粗排"（各自编码，算余弦距离），
Reranker 是"精排"（query 和 doc 一起送进模型打分），准确度更高。

任何异常都降级返回原始 docs 的前 top_n 项，不阻断业务。
"""

from typing import Any, Dict, List, Optional

import httpx

from app.config.config import settings

_RERANK_ENDPOINT = (
    "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
)


async def rerank_docs(
    query: str,
    docs: List[Dict[str, Any]],
    *,
    top_n: Optional[int] = None,
    model: Optional[str] = None,
    timeout: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """对候选文档做 Rerank，返回按相关性降序排列的 top_n 个

    调用 DashScope 的 gte-rerank-v2 模型，给每对 (query, doc) 打分。
    分数写入 doc["rerank_score"]。

    Args:
        query: 用户问题
        docs: 粗排候选（每项含 content source chapter 等字段）
        top_n: 最终返回多少条（None = settings.rag_top_k）
        model: rerank 模型名（None = settings.rag_rerank_model）

    Returns:
        重排后的 top_n 文档（每项附加 rerank_score 字段）
    """
    top_n = top_n or settings.rag_top_k
    model = model or settings.rag_rerank_model
    timeout = timeout or settings.rag_rerank_timeout_sec

    if not docs or top_n <= 0:
        return docs if docs else []

    api_key = settings.dashscope_api_key
    if not api_key:
        return docs[:top_n]

    doc_texts = [d.get("content", "") for d in docs]

    payload = {
        "model": model,
        "input": {"query": query, "documents": doc_texts},
        "parameters": {
            "top_n": min(top_n, len(docs)),
            "return_documents": False,
        },
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(_RERANK_ENDPOINT, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        print(f"[rerank] 调用失败(降级): {type(e).__name__}: {e}")
        return docs[:top_n]

    try:
        results = data.get("output", {}).get("results") or []
        if not results:
            return docs[:top_n]

        reranked: List[Dict[str, Any]] = []
        for item in results:
            idx = item.get("index")        # 原始列表中的位置
            score = item.get("relevance_score")  # 相关性分数 0~1
            if idx is None or not (0 <= idx < len(docs)):
                continue
            doc = dict(docs[idx])
            if score is not None:
                doc["rerank_score"] = float(score)
            reranked.append(doc)
            if len(reranked) >= top_n:
                break

        if not reranked:
            return docs[:top_n]
        return reranked
    except Exception as e:
        print(f"[rerank] 解析失败(降级): {e}")
        return docs[:top_n]