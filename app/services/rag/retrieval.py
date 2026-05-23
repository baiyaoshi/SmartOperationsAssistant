"""知识库检索: 走 advanced_search (Vector → [Hybrid] → [Rerank]) 拼成 LLM 上下文"""

from typing import Any, Dict, List, Tuple

from app.config.config import settings
from app.core.vector_store import advanced_search

CHUNK_CHAR_LIMIT = 800


async def build_context(
    question: str, top_k: int
) -> Tuple[str, int, List[str], List[Dict[str, Any]]]:
    """检索知识库，拼接成 context 字符串

    Returns:
        (context_text, hit_count, sources, hits_meta)
        hits_meta: [{"source", "chapter", "preview", "score"}, ...]
    """
    docs = await advanced_search(question, k=top_k)
    if not docs:
        return "(知识库未命中相关内容)", 0, [], []

    chunks: List[str] = []
    sources: List[str] = []
    hits_meta: List[Dict[str, Any]] = []
    for i, doc in enumerate(docs, 1):
        source = doc.get("source", "未知")
        sources.append(str(source))
        chapter = doc.get("chapter", "")
        header = f"## 来源 {i} | {source}"
        if chapter:
            header += f" | 章节: {chapter}"
        raw_text = doc.get("content", "").strip()
        truncated = raw_text[:CHUNK_CHAR_LIMIT]
        if len(raw_text) > CHUNK_CHAR_LIMIT:
            truncated += "... (已截断)"
        chunks.append(f"{header}\n{truncated}")
        score = doc.get("rerank_score") or doc.get("distance")
        score_val = round(float(score), 4) if score is not None else None
        preview = raw_text.replace("\n", " ")
        hits_meta.append({
            "source": str(source),
            "chapter": str(chapter) if chapter else "",
            "preview": preview[:240] + ("..." if len(preview) > 240 else ""),
            "score": score_val,
        })

    return "\n\n".join(chunks), len(docs), sources, hits_meta