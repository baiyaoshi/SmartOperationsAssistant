"""联网搜索 Provider + 结果格式化

支持:
  - open_websearch: 本地 open-webSearch daemon（默认）
  - mock: 零配置占位数据
"""

from typing import Any, Dict, List, Optional

from app.config.config import settings

import httpx
def get_provider() -> str:
    """获取当前联网搜索 provider 名"""
    return (settings.web_search_provider or "open_websearch").lower().strip()


def search_open_websearch(query: str, max_results: int) -> List[Dict[str, Any]]:
    """open-webSearch local daemon"""


    base_url = (settings.open_websearch_base_url or "http://127.0.0.1:3210").rstrip("/")
    payload: dict = {"query": query, "limit": max_results}
    if settings.open_websearch_engine:
        payload["engines"] = [settings.open_websearch_engine]
    if settings.open_websearch_search_mode and settings.open_websearch_search_mode != "auto":
        payload["searchMode"] = settings.open_websearch_search_mode

    resp = httpx.post(
        f"{base_url}/search",
        json=payload,
        timeout=settings.open_websearch_timeout_sec,
    )
    resp.raise_for_status()
    envelope = resp.json()
    if envelope.get("status") != "ok":
        raise RuntimeError(envelope.get("error", "open-webSearch error"))

    data = envelope.get("data") or {}
    return [
        {
            "title": r.get("title", "(无标题)"),
            "url": r.get("url", ""),
            "snippet": r.get("description") or r.get("snippet") or r.get("content", ""),
        }
        for r in data.get("results", [])
        if isinstance(r, dict)
    ]


def search_mock(query: str, max_results: int) -> List[Dict[str, Any]]:
    """Mock provider"""
    return [
        {
            "title": f"[MOCK] 关于 '{query}' 的搜索结果",
            "url": "https://example.com/mock-search-result",
            "snippet": f"Mock 占位返回。原始查询: {query!r}。",
        }
    ]


def search(query: str, max_results: int, provider: Optional[str] = None) -> List[Dict[str, Any]]:
    """按 provider 调度"""
    p = (provider or get_provider()).lower().strip()
    if p in ("open_websearch", "open-websearch", "openwebsearch"):
        return search_open_websearch(query, max_results)
    if p == "mock":
        return search_mock(query, max_results)
    raise ValueError(f"未知 provider: {p!r}")


def format_results(results: List[Dict[str, Any]], *, provider: str) -> str:
    """格式化为 Markdown"""
    header = ""
    if provider == "mock":
        header = "> **[WARN] Mock 数据** 仅供演示。\n\n"
    lines = []
    for i, r in enumerate(results, 1):
        title = r.get("title", "(无标题)")
        url = r.get("url", "(无 URL)")
        snippet = (r.get("snippet") or "").strip()
        lines.append(f"### {i}. {title}\n来源: {url}\n\n{snippet}")
    return header + "\n\n---\n\n".join(lines)