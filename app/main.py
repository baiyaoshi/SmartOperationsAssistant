from fastapi import FastAPI
import uvicorn
from langchain_core.messages import HumanMessage
from pydantic import BaseModel
from app.core.llm import client


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
        messages=[{"role": "user", "content": request.message}]
    )
    return {"reply":resp.choices[0].message.content}

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=9900)