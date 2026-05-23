"""RAG Chat 的联网搜索上下文构造"""

from typing import Any, Dict, List, Tuple

from app.core.web_search import format_results, get_provider, search


async def build_web_context(
    rewritten_question: str,
    *,
    summary: str = "",
    recent_messages: List[Dict[str, Any]] = None,
    enabled: bool = False,
) -> Tuple[str, List[str], List[Dict[str, Any]], str]:
    """联网搜索 + 拼 context

    Returns:
        (web_context_text, sources, web_hits, skip_reason)
    """
    if not enabled:
        return "(本轮未启用联网搜索)", [], [], "本轮未启用联网搜索"

    provider = get_provider()
    max_results = max(1, min(3, 5))

    try:
        raw_hits = search(rewritten_question, max_results, provider)
    except Exception as e:
        return (
            f"(联网搜索失败: {type(e).__name__}: {e})",
            [],
            [],
            f"{type(e).__name__}: {e}",
        )

    if not raw_hits:
        return (
            f"(联网搜索未找到与 '{rewritten_question}' 相关的结果)",
            [],
            [],
            "未找到相关结果",
        )

    text = format_results(raw_hits, provider=provider)
    sources = [f"web:{rewritten_question[:20]}"]
    web_hits = [
        {
            "title": h.get("title", "")[:120],
            "url": h.get("url", "")[:300],
            "snippet": (h.get("snippet", "") or "")[:240],
        }
        for h in raw_hits
    ]
    return text, sources, web_hits, ""