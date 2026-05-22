import asyncio

from fastapi import APIRouter
from pydantic import BaseModel
import uvicorn
from fastapi.responses import StreamingResponse


from app.agents.graph import build_graph

agent_graph = build_graph()

from app.runtime.stream_sink import set_sink_queue, clear_sink_queue, sink_generator
from app.services import chat_memory

router = APIRouter(tags=["aiops"])

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"

class ChatRequestWithSession(BaseModel):
    message: str
    session_id: str = "default"

async def graph_memory_stream_response(message: str, session_id: str):
    """带记忆的流式诊断（使用 stream_sink 实时推送）"""
    # 1. 存用户消息
    await chat_memory.append_message(session_id, role="user", content=message)
    # 2. 读取历史消息，构造上下文
    history = await chat_memory.get_messages(session_id)

    if len(history) > 1:
        recent = history[:-1]
        recent = recent[-6:]
    else:
        recent = []

    context = ""
    if recent:
        lines = []
        for msg in recent:
            if msg["role"] == "user":
                role = "用户"
            else:
                role = "助手"
            content = msg["content"]
            lines.append(f"{role}: {content}")
        context = "以下是对话历史：\n" + "\n".join(lines) + "\n\n"

    if context:
        augmented_input = context + message
    else:
        augmented_input = message

    # 3. 使用 stream_sink 跑图
    queue: asyncio.Queue[str] = asyncio.Queue()


    set_sink_queue(queue)

    async def run_graph():
        try:
            result = await agent_graph.ainvoke({"input": augmented_input})
            final_report = result.get("response", "")
            # 存助手回复和报告
            if final_report:
                await chat_memory.append_message(session_id, role="assistant", content=final_report)
                await chat_memory.append_diagnosis_report(final_report, session_id=session_id)
            # 推报告
            await queue.put(f"data: 📝 报告:\n\n")
            for line in final_report.split("\n"):
                await queue.put(f"data: {line}\n\n")
        except Exception as e:
            await queue.put(f"data: ❌ 错误: {str(e)}\n\n")
        finally:
            await queue.put("[DONE]")

    graph_task = asyncio.create_task(run_graph())

    try:
        async for event in sink_generator(queue):
            yield event
    finally:
        graph_task.cancel()
        clear_sink_queue()


@router.post("/api/v1/agent/demo/memory/stream")
async def graph_demo_memory_stream(request: ChatRequest):
    return StreamingResponse(
        graph_memory_stream_response(request.message, request.session_id),
        media_type="text/event-stream"
    )