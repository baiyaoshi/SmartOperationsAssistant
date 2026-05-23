"""RAG 工具函数: 消息格式化"""

from typing import Any, Dict, List


def content_to_text(content: Any) -> str:
    """统一把消息 content 转成纯文本"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            c.get("text", "") if isinstance(c, dict) else str(c) for c in content
        )
    return str(content)


def format_history(messages: List[Dict[str, Any]]) -> str:
    """把 [{role, content}, ...] 渲染成给 prompt 看的多行文本"""
    if not messages:
        return "(无)"
    lines = []
    for item in messages:
        role = "用户" if item.get("role") == "user" else "助手"
        content = str(item.get("content") or "").strip()
        if content:
            lines.append(f"{role}: {content[:1200]}")
    return "\n".join(lines) if lines else "(无)"