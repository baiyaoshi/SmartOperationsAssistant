import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
import uvicorn
import json

from langchain.agents.middleware.todo import Todo
from pydantic import BaseModel
from starlette.staticfiles import StaticFiles

from pathlib import Path

from app.core.llm import client
from app.runtime.stream_sink import set_sink_queue, sink_generator, clear_sink_queue
from app.services import chat_memory
from app.tools.meta import tool_registry, get_all_tools
from app.tools.mcp_loader import discover_and_register_mcp_tools
from app.core.mcp_client import close_all
from fastapi.responses import StreamingResponse
from app.agents.graph import build_graph


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时发现 MCP 工具，关闭时断开 MCP 连接"""
    print("[启动] 发现 MCP 工具...")
    await discover_and_register_mcp_tools()
    print(f"[启动] MCP 工具加载完成，共 {len(get_all_tools())} 个工具")
    yield
    print("[关闭] 断开 MCP 连接...")
    await close_all()


app = FastAPI(title="Smart Operations Assistant", lifespan=lifespan)

agent_graph = build_graph()
# 挂载前端静态文件
# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent

# 在 agent_graph = build_graph() 后面
app.mount("/frontend", StaticFiles(directory=str(BASE_DIR / "frontend"), html=True), name="frontend")

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"

class ChatRequestWithSession(BaseModel):
    message: str
    session_id: str = "default"

@app.get("/api/v1/health")
async def health():
    return{"status":"ok","message":"服务运行中"}

@app.post("/api/v1/chat")
async def chat(request:ChatRequest):
    resp=await client.chat.completions.create(
        model="qwen3.5-plus",
        messages=[{"role": "user", "content": request.message}],
        tools=[info["definition"] for info in tool_registry.values()]
    )
    msg=resp.choices[0].message
    print(msg)
    #如果决定调用工具
    if msg.tool_calls:
        # 收集所有工具结果
        tool_results = []
        for tool_call in msg.tool_calls:
            tool_name = tool_call.function.name
            tool_info = tool_registry[tool_name]
            arguments = json.loads(tool_call.function.arguments)
            result = tool_info["function"](**arguments)
            tool_results.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result
            })

        # 组装消息：用户消息 + LLM回复（含所有tool_calls）+ 所有工具结果
        messages = [
            {"role": "user", "content": request.message},
            msg,
            *tool_results  # ← 把所有工具结果展开传进去
        ]

        second_resp = await client.chat.completions.create(
            model="qwen3.5-plus",
            messages=messages,
            tools=[info["definition"] for info in tool_registry.values()]
        )
        return {"reply": second_resp.choices[0].message.content}
    return msg.content


async def stream_response(message: str):
    stream = await client.chat.completions.create(
        model="qwen3.5-plus",
        messages=[{"role": "user", "content": message}],
        stream=True
    )

    async for chunk in stream:
        if not chunk.choices:
            continue
        if chunk.choices[0].delta.content:
            yield f"data: {chunk.choices[0].delta.content}\n\n"

    yield "data: [DONE]\n\n"

@app.post("/api/v1/chat/stream")
async def chat_stream(request:ChatRequest):
    return StreamingResponse(
        stream_response(request.message),
        media_type="text/event-stream"
    )

@app.post("/api/v1/agent/demo")
async def graph_demo(request:ChatRequest):
    result = await agent_graph.ainvoke({"input": request.message})
    return {"message": result["response"]}


async def graph_stream_response(message: str):
    """流式输出图的执行过程（使用 stream_sink 实时推送）"""
    queue: asyncio.Queue[str] = asyncio.Queue()


    set_sink_queue(queue)

    async def run_graph():
        """跑图，结束后取最终报告并推送"""
        try:
            result = await agent_graph.ainvoke({"input": message})
            final_report = result.get("response", "")
            # 推报告
            await queue.put(f"data: 📝 报告:\n\n")
            for line in final_report.split("\n"):
                await queue.put(f"data: {line}\n\n")
        except Exception as e:
            await queue.put(f"data: ❌ 错误: {str(e)}\n\n")
        finally:
            await queue.put("[DONE]")

    # 同时跑图和消费队列
    async def consume():
        async for event in sink_generator(queue):
            yield event

    # 用任务来跑图
    graph_task = asyncio.create_task(run_graph())

    try:
        async for event in consume():
            yield event
    finally:
        graph_task.cancel()
        clear_sink_queue()


@app.post("/api/v1/agent/demo/stream")
async def graph_demo_stream(request: ChatRequest):
    return StreamingResponse(
        graph_stream_response(request.message),
        media_type="text/event-stream"
    )

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

@app.post("/api/v1/agent/demo/memory/stream")
async def graph_demo_memory_stream(request: ChatRequest):
    return StreamingResponse(
        graph_memory_stream_response(request.message, request.session_id),
        media_type="text/event-stream"
    )

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=9900)