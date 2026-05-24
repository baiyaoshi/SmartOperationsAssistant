"""RAG 聊天 API (SSE 流式)"""

import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.schemas.chat import ChatRequest
import app.services.rag_service as rag_service

router = APIRouter(prefix="/api/v1/rag", tags=["rag"])


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    async def event_generator():
        try:
            async for event in rag_service.stream_chat(
                req.message,
                session_id=req.session_id,
                web_search=False,
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
