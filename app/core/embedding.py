"""Embedding 服务 — 封装 DashScope text-embedding-v3 的向量化能力"""

from functools import lru_cache
from typing import List

from openai import AsyncOpenAI

from app.config.config import settings


@lru_cache(maxsize=1)
def get_embedding_client() -> AsyncOpenAI:
    """获取 Embedding 客户端（单例）"""
    if not settings.dashscope_api_key:
        raise ValueError("DASHSCOPE_API_KEY 未配置, 无法创建 Embedding 客户端")
    return AsyncOpenAI(
        api_key=settings.dashscope_api_key,
        base_url=settings.dashscope_base_url,
    )


async def embed_texts(texts: List[str]) -> List[List[float]]:
    """将文本列表向量化"""
    client = get_embedding_client()
    resp = await client.embeddings.create(
        model=settings.dashscope_embedding_model,
        input=texts,
        dimensions=settings.dashscope_embedding_dim,
    )
    ordered = sorted(resp.data, key=lambda x: x.index)
    return [item.embedding for item in ordered]


async def embed_query(text: str) -> List[float]:
    """将单个查询文本向量化"""
    result = await embed_texts([text])
    return result[0]