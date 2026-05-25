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


# 临时存储：文件名 → {chunks, 上传时间}
# 因为 Milvus 只存向量和文本，不存元信息，用这个做演示
_kb_docs: dict = {}


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

    # 记录元信息
    _kb_docs[file.filename] = {
        "filename": file.filename,
        "chunks": len(chapters),
        "upload_time": __import__("datetime").datetime.now().isoformat(),
    }

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


@router.get("/documents")
async def list_documents():
    """查看知识库中已上传的文档列表"""
    # 从 Milvus 中按 source 字段去重列出文档
    milvus_manager.connect()
    if not milvus_manager.has_collection():
        return {"documents": [], "total": 0}

    try:
        rows = milvus_manager.get_all_chunks()
        sources = {}
        for row in rows:
            source = row.get("source", "未知")
            if source not in sources:
                sources[source] = {
                    "filename": source,
                    "chunks": 0,
                    "upload_time": _kb_docs.get(source, {}).get("upload_time", "未知"),
                }
            sources[source]["chunks"] += 1

        docs = sorted(sources.values(), key=lambda x: x["filename"])
        return {"documents": docs, "total": len(docs)}
    except Exception as e:
        raise HTTPException(500, f"获取文档列表失败: {e}")


@router.delete("/documents/{filename:path}")
async def delete_document(filename: str):
    """删除知识库中的某个文档"""
    milvus_manager.connect()
    if not milvus_manager.has_collection():
        raise HTTPException(404, "知识库为空")

    try:
        milvus_manager.delete_by_source(filename)
        _kb_docs.pop(filename, None)
        return {"filename": filename, "status": "deleted"}
    except Exception as e:
        raise HTTPException(500, f"删除失败: {e}")
