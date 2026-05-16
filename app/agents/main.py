# app/agents/main.py — LangGraph 第一步：画一个 2 节点的流程图

from typing import TypedDict

import asyncio
from langgraph.graph import StateGraph, START, END

from app.core.llm import client


# 1. 定义（State）
class MyState(TypedDict):
    message: str

# 2. 定义节点1
def say_hello(state: MyState) -> dict:
    old = state["message"]
    new = old + "嗨"
    print(f"--- 执行 say_hello, 当前长度: {len(new)} ---")
    return {"message": new}
# 3. 定义节点2
def say_bye(state: MyState) -> dict:
    print("--- 执行节点2: say_bye ---")
    old_msg = state["message"]
    return {"message": old_msg + " ——再见！"}

# 试试调用大模型
async def chat(state:MyState)-> dict:
    old_msg = state["message"]
    response = await client.chat.completions.create(
        model="qwen-plus",
        messages=[{"role": "user", "content": f"请用正式的语言总结这句话：{old_msg}"}]
    )
    reply = response.choices[0].message.content
    print(f"--- LLM 总结: {reply} ---")
    return {"message": reply}

# 3.5 条件判断函数
def should_repeat(state: MyState) -> str:
    """如果消息太短就再重复一次"""
    if len(state["message"]) < 10:
        return "repeat"   # 回到 hello
    else:
        return "enough"   # 去 bye

# 4. 画流程图 & 执行
builder = StateGraph(MyState)
builder.add_node("hello", say_hello)
builder.add_node("bye", say_bye)
builder.add_node("chat",chat)
builder.add_edge(START, "hello")
builder.add_conditional_edges(
    "hello",
    should_repeat,
    {
        "repeat": "hello",
        "enough": "bye"
    }
)
builder.add_edge("bye", "chat")
builder.add_edge("chat", END)

graph = builder.compile()

result = asyncio.run(graph.ainvoke({"message": ""}))
print("\n最终黑板上的内容:", result["message"])