from fastapi import FastAPI
import uvicorn
import json
from pydantic import BaseModel
from app.core.llm import client
from app.tools.meta import tool_registry
from fastapi.responses import StreamingResponse

app=FastAPI(title="Smart Operations Assistant")



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

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=9900)