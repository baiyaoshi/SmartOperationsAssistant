"""Hybrid Retriever: BM25 (关键词匹配) + Vector (语义匹配) + RRF 融合

为什么加 Hybrid:
  纯向量检索在语义上强，但会漏精确关键词（如"ERR_CONN_REFUSED"、"redis.exception.TimeoutError"）。
  BM25 按词频匹配正好互补。

BM25 索引存在进程内存里，启动后从 Milvus 拉全量 chunks 构建。
"""

from __future__ import annotations

import re
import threading
from typing import Any, Dict, List, Optional, Tuple

from app.config.config import settings
from app.core.milvus import milvus_manager

try:
    from rank_bm25 import BM25Okapi
except ImportError:
    BM25Okapi = None
    print("[hybrid] rank_bm25 未安装, Hybrid Search 将降级到纯向量")


# 分词器: 英文按单词切，中文按单字切
_TOKEN_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_\-\.]*|[\u4e00-\u9fff]")


def _tokenize(text: str) -> List[str]:
    """轻量分词"""
    if not text:
        return []
    tokens = _TOKEN_RE.findall(text.lower())
    return [t for t in tokens if t]


class _BM25Index:
    """BM25 索引（线程安全，惰性构建）

    第一次检索时从 Milvus 拉全量数据建索引。
    文档上传/删除后调 refresh_bm25_index() 主动刷新。
    """

    def __init__(self):
        self._bm25: Optional[BM25Okapi] = None
        self._docs: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._built = False

    def build(self, docs: List[Dict[str, Any]]) -> None:
        """用文档列表构建 BM25 索引"""
        if BM25Okapi is None:
            self._built = True
            return
        if not docs:
            with self._lock:
                self._bm25 = None
                self._docs = []
                self._built = True
            return

        tokenized = [_tokenize(d.get("content", "")) for d in docs]
        try:
            bm25 = BM25Okapi(tokenized)
        except Exception as e:
            print(f"[hybrid] BM25 构建失败(降级): {e}")
            with self._lock:
                self._bm25 = None
                self._docs = []
                self._built = True
            return

        with self._lock:
            self._bm25 = bm25
            self._docs = docs
            self._built = True
        print(f"[hybrid] BM25 索引构建完成: {len(docs)} 文档")

    def search(self, query: str, k: int) -> List[Tuple[Dict[str, Any], float]]:
        """BM25 检索，返回 (文档, 分数) 列表"""
        if not self._built or self._bm25 is None or not self._docs:
            return []
        tokens = _tokenize(query)
        if not tokens:
            return []
        try:
            scores = self._bm25.get_scores(tokens)
        except Exception:
            return []
        indexed = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:k]
        return [(self._docs[i], float(s)) for i, s in indexed if s > 0]

    @property
    def is_ready(self) -> bool:
        return self._built and self._bm25 is not None


_bm25_index = _BM25Index()


def refresh_bm25_index() -> None:
    """重建 BM25 索引（从 Milvus 拉全量文档）"""
    if BM25Okapi is None:
        return
    if not milvus_manager.has_collection():
        return
    try:
        rows = milvus_manager.get_all_chunks()
    except Exception as e:
        print(f"[hybrid] 拉全量失败(降级): {e}")
        return
    _bm25_index.build(rows)


def hybrid_search(
    query: str,
    vector_docs: List[Dict[str, Any]],
    *,
    k: int,
    bm25_weight: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """将向量结果和 BM25 结果用 RRF 融合，返回 top-k

    RRF 公式: score = 权重 / (60 + 排名)
    只用排名不看绝对分数，解决向量和 BM25 量纲不同的问题。
    """
    bm25_weight = bm25_weight if bm25_weight is not None else settings.rag_hybrid_bm25_weight
    vec_weight = 1.0 - bm25_weight

    retrieve_k = max(k, settings.rag_retrieve_k)
    bm25_results = _bm25_index.search(query, retrieve_k) if _bm25_index.is_ready else []

    if not bm25_results:
        return vector_docs[:k]

    # RRF 融合
    rrf_k = 60
    scores: Dict[str, float] = {}
    doc_map: Dict[str, Dict[str, Any]] = {}

    def _key(doc: Dict[str, Any]) -> str:
        """用 source + chapter + content 做唯一键去重"""
        return f"{doc.get('source', '')}|{doc.get('chapter', '')}|{hash(doc.get('content', ''))}"

    for rank, doc in enumerate(vector_docs):
        kk = _key(doc)
        scores[kk] = scores.get(kk, 0.0) + vec_weight / (rrf_k + rank + 1)
        doc_map.setdefault(kk, doc)

    for rank, (doc, _) in enumerate(bm25_results):
        kk = _key(doc)
        scores[kk] = scores.get(kk, 0.0) + bm25_weight / (rrf_k + rank + 1)
        doc_map.setdefault(kk, doc)

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top = [doc_map[kk] for kk, _ in ranked[:k]]
    return top