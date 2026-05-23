"""知识库 API — 上传文档 + 检索测试"""

import asyncio
from typing import List

from fastapi import APIRouter, UploadFile, File, HTTPException
from app.schemas.knowledge import SearchRequest, SearchResponse, SearchResult

from app.core.milvus import milvus_manager
from app.core.embedding import embed_texts
from app.core.vector_store import safe_similarity_search
from app.services.rag.document_processor import chunk_text

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """上传文档文件，自动分块并存入知识库

    支持 .txt / .md 格式
    """
    if not file.filename:
        raise HTTPException(400, "文件名不能为空")

    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(400, "仅支持 UTF-8 编码的文本文件")

    if not text.strip():
        raise HTTPException(400, "文件内容为空")

    # 分块
    chapters = chunk_text(text, source=file.filename)
    if not chapters:
        raise HTTPException(400, "文件内容过短，无法分块")

    print(f"[knowledge] {file.filename}: 分 {len(chapters)} 块")

    # 向量化
    texts = [c["content"] for c in chapters]
    vectors = await embed_texts(texts)

    # 存入 Milvus
    milvus_manager.connect()
    milvus_manager.create_collection()
    milvus_manager.insert(
        texts=[c["content"] for c in chapters],
        vectors=vectors,
        sources=[c["source"] for c in chapters],
        chapters=[c["chapter"] for c in chapters],
    )

    return {
        "filename": file.filename,
        "chunks": len(chapters),
        "status": "ok",
    }


@router.post("/search", response_model=SearchResponse)
async def search_knowledge(request: SearchRequest):
    """检索知识库测试"""
    milvus_manager.connect()

    docs = await safe_similarity_search(request.query, k=request.top_k)

    results = []
    for d in docs:
        results.append(SearchResult(
            content=d.get("content", ""),
            source=d.get("source", "未知"),
            chapter=d.get("chapter", ""),
            distance=round(float(d.get("distance", 0)), 4),
        ))

    return SearchResponse(
        query=request.query,
        results=results,
        total=len(results),
    )


@router.get("/collections")
async def list_collections():
    """查看 Milvus 中的 collection 和文档数"""
    milvus_manager.connect()
    cols = milvus_manager.list_collections()
    stats = []
    for col in cols:
        try:
            info = milvus_manager._client.describe_collection(col)
            stats.append({
                "name": col,
                "fields": len(info.get("fields", [])),
            })
        except Exception:
            stats.append({"name": col, "fields": 0})
    return {"collections": stats}