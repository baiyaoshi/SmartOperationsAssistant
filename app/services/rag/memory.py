"""RAG Chat 的会话记忆操作: query 改写 + 历史压缩"""
#TODO



from typing import Any, Dict, List

from app.core.llm import client
from app.services.rag.utils import format_history


async def rewrite_question(
    question: str,
    *,
    summary: str = "",
    recent_messages: List[Dict[str, Any]] = None,
) -> str:
    """用历史改写当前问题为独立检索 query"""
    if not recent_messages:
        return question

    # 把最近几条消息拼成一段历史
    history_text = format_history(recent_messages[-4:])

    # 调 LLM 改写（用最小模型，省钱）
    resp = await client.chat.completions.create(
        model="qwen-plus",
        messages=[
            {"role": "system", "content": "你是一个查询改写助手。根据对话历史，把用户最新问题改写成独立的自包含查询。"},
            {"role": "user", "content": f"对话历史：\n{history_text}\n\n用户最新问题：{question}\n\n改写后的查询："}
        ],
    )
    rewritten = resp.choices[0].message.content.strip()
    return rewritten if rewritten else question

async def compact_if_needed(session_id: str) -> None:
    """压缩历史（简化版暂不实现）"""
    pass