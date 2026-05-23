"""RAG Chat 的会话记忆操作: query 改写 + 历史压缩"""
#TODO



from typing import Any, Dict, List


async def rewrite_question(
    question: str,
    *,
    summary: str = "",
    recent_messages: List[Dict[str, Any]] = None,
) -> str:
    """用历史改写当前问题为独立检索 query（简化版，直接返回原文）"""
    return question


async def compact_if_needed(session_id: str) -> None:
    """压缩历史（简化版暂不实现）"""
    pass