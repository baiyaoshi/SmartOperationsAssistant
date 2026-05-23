"""向量存储操作 — 高级检索流水线: Vector → [Hybrid] → [Rerank] → 返回

safe_similarity_search: 纯向量检索，给工具/快速查询用
advanced_search: 完整流水线（向量+混合+重排），给 RAG 服务用
"""

from typing import Any, Dict, List, Optional

from app.config.config import settings
from app.core.embedding import embed_query
from app.core.milvus import milvus_manager

from app.core.hybrid_retriever import _bm25_index, hybrid_search, refresh_bm25_index
from app.core.reranker import rerank_docs

async def safe_similarity_search(
    query: str,
    k: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """纯向量检索（带异常兜底）

    Args:
        query: 查询文本
        k: 返回 top-k（None 用 settings.rag_top_k）

    Returns:
        [{"content", "source", "chapter", "distance"}, ...]
        失败时返回空列表，不抛异常
    """
    k = k or settings.rag_top_k
    if not milvus_manager.is_alive() or not milvus_manager.has_collection():
        return []

    try:
        vector = await embed_query(query)
    except Exception as e:
        print(f"[vector_store] embed_query 失败: {e}")
        return []

    try:
        rows = milvus_manager.search(vector, top_k=k)
        return rows
    except Exception as e:
        print(f"[vector_store] search 失败: {e}")
        return []


async def advanced_search(
    query: str,
    k: Optional[int] = None,
    *,
    use_hybrid: Optional[bool] = None,
    use_rerank: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """高级检索流水线: Vector → [Hybrid] → [Rerank] → 返回 top-k

    每一层可通过 settings 开关，任一环节失败自动降级到上一层结果。

    Args:
        query: 查询文本
        k: 最终返回 top-k（None 用 settings.rag_top_k）
        use_hybrid: 是否启用 BM25+Vector 融合（None 走 settings）
        use_rerank: 是否启用 Reranker 精排（None 走 settings）

    Returns:
        每项含 content / source / chapter / distance / (rerank_score) 等字段
    """


    final_k = k or settings.rag_top_k
    use_hybrid = settings.rag_hybrid_enabled if use_hybrid is None else use_hybrid
    use_rerank = settings.rag_rerank_enabled if use_rerank is None else use_rerank

    # 需要 hybrid/rerank 时，先多取一些候选，给后续环节留空间
    retrieve_k = settings.rag_retrieve_k if (use_hybrid or use_rerank) else final_k

    # Step 1: 向量粗排
    vector_docs = await safe_similarity_search(query, k=retrieve_k)
    if not vector_docs:
        return []

    # Step 2: Hybrid 融合（BM25 + Vector + RRF）
    candidates = vector_docs
    if use_hybrid:
        if not _bm25_index.is_ready:
            try:
                refresh_bm25_index()
            except Exception as e:
                print(f"[advanced_search] BM25 lazy build 失败: {e}")
        candidates = hybrid_search(query, vector_docs, k=retrieve_k)

    # Step 3: Rerank 精排
    if use_rerank and len(candidates) > final_k:
        try:
            candidates = await rerank_docs(query, candidates, top_n=final_k)
        except Exception as e:
            print(f"[advanced_search] rerank 降级: {e}")
            candidates = candidates[:final_k]
    else:
        candidates = candidates[:final_k]

    return candidates