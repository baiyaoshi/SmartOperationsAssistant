"""知识库检索工具 (RAG Tool)

Agent 调这个工具查询运维知识库，返回 top-k 相关片段。
"""

from app.config.config import settings
from app.core.vector_store import safe_similarity_search


async def search_knowledge_base(query: str) -> str:
    """搜索运维知识库 (SOP、On-Call 手册、故障处理流程等)

    在以下场景调用本工具:
    - 需要查询某种告警的标准处理流程
    - 需要参考已有的故障处理经验

    Args:
        query: 查询关键词或问题

    Returns:
        相关文档片段 (Markdown 格式)
    """
    docs = safe_similarity_search(query, k=settings.rag_top_k)

    if not docs:
        return (
            f"知识库中没有找到与 '{query}' 直接相关的文档。"
            f"请尝试换个关键词搜索。"
        )

    chunks = []
    for i, doc in enumerate(docs, 1):
        source = doc.get("source") or "未知来源"
        chapter = doc.get("chapter") or ""
        header = f"### 片段 {i} | 来源: {source}"
        if chapter:
            header += f" | 章节: {chapter}"
        chunks.append(f"{header}\n{doc.get('content', '').strip()}")

    return "\n\n---\n\n".join(chunks)