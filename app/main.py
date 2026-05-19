import asyncio

from fastapi import FastAPI
import uvicorn
import json
from pydantic import BaseModel
from starlette.staticfiles import StaticFiles

from pathlib import Path

from app.core.llm import client
from app.tools.meta import tool_registry
from fastapi.responses import StreamingResponse
from app.agents.graph import build_graph

app=FastAPI(title="Smart Operations Assistant")

agent_graph = build_graph()
# 挂载前端静态文件
# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent

# 在 agent_graph = build_graph() 后面
app.mount("/frontend", StaticFiles(directory=str(BASE_DIR / "frontend"), html=True), name="frontend")
class ChatRequest(BaseModel):
    message: str

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
    """流式输出图的执行过程"""
    final_response = None

    async for event in agent_graph.astream({"input": message}):
        for node_name, node_output in event.items():
            if node_name == "skill_router":
                yield f"data:选择技能: {node_output.get('selected_skill', '')}\n\n"
            elif node_name == "planner":
                steps = node_output.get("plan", [])
                yield f"data:计划: {json.dumps(steps, ensure_ascii=False)}\n\n"
            elif node_name == "executor":
                step = node_output.get("current_step", "")
                result = node_output.get("current_result", "")
                if step:
                    yield f"data:执行: {step}\n\n"
                if result:
                    yield f"data:结果: {result[:100]}...\n\n"
            elif node_name == "replanner":
                if node_output.get("is_finished"):
                    yield f"data:完成，生成报告...\n\n"
                    # 从 astream 结果中拿 response
                    final_response = node_output.get("response", "")
                else:
                    yield f"data:继续下一步...\n\n"

    if final_response:
        yield f"data: 📝 报告:\n\n"
        # 报告内容分行输出
        for line in final_response.split("\n"):
            yield f"data: {line}\n\n"
    yield "data: [DONE]\n\n"


@app.post("/api/v1/agent/demo/stream")
async def graph_demo_stream(request: ChatRequest):
    return StreamingResponse(
        graph_stream_response(request.message),
        media_type="text/event-stream"
    )


if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=9900)