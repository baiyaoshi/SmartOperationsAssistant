"""知识库相关 Schema"""
from pydantic import BaseModel
from typing import List


class SearchRequest(BaseModel):
    """检索测试请求"""
    query: str
    top_k: int = 3


class SearchResult(BaseModel):
    """单条检索结果"""
    content: str
    source: str
    chapter: str
    distance: float = 0
    rerank_score: float = 0


class SearchResponse(BaseModel):
    """检索测试响应"""
    query: str
    results: List[SearchResult]
    total: int