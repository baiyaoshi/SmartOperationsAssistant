"""文档分块处理"""

from typing import List

from app.config.config import settings


def chunk_text(text: str, source: str, chapter: str = "") -> List[dict]:
    """将文本按指定大小分块

    Args:
        text: 原始文本
        source: 来源（文件名）
        chapter: 章节

    Returns:
        [{"content", "source", "chapter"}, ...]
    """
    chunk_size = settings.rag_chunk_size
    overlap = settings.rag_chunk_overlap
    step = chunk_size - overlap

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append({
                "content": chunk_text,
                "source": source,
                "chapter": chapter,
            })
        if end >= len(text):
            break
        start += step

    return chunks