async await

```py
# 1. 定义异步函数：前面加 async
async def my_function():
    # 2. 调用另一个异步函数：前面加 await
    result = await some_other_async_function()
    return result

# 3. 调用异步函数不能用普通方式
# my_function()  ❌ 这样不行，返回的是一个 coroutine 对象

# 4. 要用 asyncio.run() 来运行
asyncio.run(my_function())
```

```py
import os

from openai import AsyncOpenAI
import asyncio
from dotenv import load_dotenv
load_dotenv()

client = AsyncOpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url=os.getenv("DASHSCOPE_BASE_URL")
)

async def main():
    resp = await client.chat.completions.create(
        model="qwen-plus",
        messages=[{"role": "user", "content": "你好"}]
    )
    print(resp.choices[0].message.content)

asyncio.run(main())
```



### fastapi

```py
from fastapi import FastAPI
import uvicorn

app=FastAPI(title="Smart Operations Assistant")

@app.get("/api/v1/helth")
async def health():
    return{"status":"ok","message":"服务运行中"}

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=9900)
```

```
你写 @RestController → 打包成 jar → java -jar app.jar 
                                               ↑
                                       内置了 Tomcat 服务器
你写 @app.get("/api/v1/health") → uvicorn.run(app) 
                                         ↑
                                  ASGI 服务器（相当于 Tomcat）                                      
```

```py
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
```



### 工具调用测试 无langchain

```py
from datetime import datetime

def get_current_time()->str:
    """获取系统当前日期和时间"""
    now=datetime.now()
    return now.strftime("%Y-%m-%d %H:%M:%S")

#Function Call工具描述
time_tool_definition = {
    "type": "function",
    "function": {
        "name": "get_current_time",
        "description": "获取当前日期和时间",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
}
```

```py
from fastapi import FastAPI
import uvicorn

from pydantic import BaseModel
from app.core.llm import client

from app.tools.time_tool import time_tool_definition, get_current_time

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
        tools=[time_tool_definition]
    )
    message=resp.choices[0].message
    #如果决定调用工具
    if message.tool_calls:
        for tool_call in message.tool_calls:
            if tool_call.function.name=="get_current_time":
                result=get_current_time()
        # 第二次调用 LLM，把工具结果传回去
        second_resp = await client.chat.completions.create(
            model="qwen3.5-plus",
            messages=[
                {"role": "user", "content": request.message},
                message,  # 第一次的回复（含 tool_calls）
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                }
            ],
            tools=[time_tool_definition]  # 还可以继续调工具
        )
        return {"reply": second_resp.choices[0].message.content}

    # 如果没有调工具，直接返回
    return {"reply": message.content}

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=9900)
```

### 带参工具

```py
def get_weather(city: str) -> str:
    """模拟获取指定城市的天气"""
    weather_data = {
        "北京": "晴，25°C，空气质量：良",
        "上海": "多云，28°C，空气质量：优",
        "广州": "雷阵雨，32°C，空气质量：良",
        "深圳": "阴天，30°C，空气质量：优",
        # 其他城市返回默认
    }
    info = weather_data.get(city, f"{city}，阴天，22°C，空气质量：良")
    return f"{city}当前天气：{info}"

weather_tool_definition = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "获取指定城市的当前天气信息",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "城市名称，例如：北京、上海、广州"
                }
            },
            "required": ["city"]  # city 是必需的
        }
    }
}
```



### 工具中心

meta.py

```py
# 工具注册表：名字 → {函数, 定义}
tool_registry = {
    "get_current_time": {
        "function": get_current_time,
        "definition": time_tool_definition
    },
    "get_weather": {
        "function": get_weather,
        "definition": weather_tool_definition
    }
}
```

```py
@app.post("/api/v1/chat")
async def chat(request:ChatRequest):
    resp=await client.chat.completions.create(
        model="qwen3.5-plus",
        messages=[{"role": "user", "content": request.message}],
        tools=[info["definition"] for info in tool_registry.values()]
    )
    msg=resp.choices[0].message
    #如果决定调用工具
    if msg.tool_calls:
        for tool_call in msg.tool_calls:
            tool_name = tool_call.function.name
            tool_info = tool_registry[tool_name]
            arguments = json.loads(tool_call.function.arguments)
            result = tool_info["function"](**arguments)

        # 第二次调用 LLM
        second_resp = await client.chat.completions.create(
            model="qwen3.5-plus",
            messages=[
                {"role": "user", "content": request.message},
                msg,
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                }
            ],
            tools=[info["definition"] for info in tool_registry.values()]
        )
        return {"reply": second_resp.choices[0].message.content}
```

```
ChatCompletionMessage(content='', refusal=None, role='assistant', annotations=None, audio=None, function_call=None, tool_calls=[ChatCompletionMessageFunctionToolCall(id='call_02301bd10aa046b280905e1b', function=Function(arguments='{"city": "北京"}', name='get_weather'), type='function', index=0)], reasoning_content='用户询问北京的天气情况，我需要使用 get_weather 工具来获取北京的当前天气信息。这个工具需要 city 参数，用户已经明确提到了"北京"，所以我可以直接使用这个参数。')
```

第一次调用 llm选择工具返回

```json
{
  "content": null,
  "tool_calls": [{
    "function": {
      "name": "get_weather",
      "arguments": "{\"city\": \"北京\"}"
    }
  }]
}
```

中间代码自己执行工具

```
result = get_weather(city="北京")
# → "北京当前天气：晴，25°C，空气质量：良"
```

第二次调用

```json
{
  messages: [
    {"role": "user", "content": "北京天气怎么样？"},   ← 原始问题
    {"role": "assistant", "content": null,              ← LLM 第一次的回复（含 tool_calls）
     "tool_calls": [...]},
    {"role": "tool", "content": "北京当前天气：晴，25°C，空气质量：良"}  ← 工具结果
  ]
}
```

但是很可惜上面只能获得一个工具结果

试着通过列表来存

```py
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
```

这样就可以实现调用多工具了



### SSE流式生成

```py
async def stream_response(message: str):
    stream = await client.chat.completions.create(
        model="qwen3.5-plus",
        messages=[{"role": "user", "content": message}],
        stream=True
    )

    async for chunk in stream:
        if chunk.choices[0].delta.content:
            yield f"data: {chunk.choices[0].delta.content}\n\n"

    yield "data: [DONE]\n\n"

@app.post("/api/v1/chat/stream")
async def chat_stream(request:ChatRequest):
    return StreamingResponse(
        stream_response(request.message),
        media_type="text/event-stream"
    )
```

```py
# 普通函数
def get_numbers():
    result = []
    for i in range(3):
        result.append(i)
    return result  # 一次性返回 [0, 1, 2]

# 生成器函数
def get_numbers():
    for i in range(3):
        yield i  # 一次返回一个：0 → 1 → 2

for num in get_numbers():
    print(num)  # 每次拿到一个值
```

| 代码             | 作用                                   |
| ---------------- | -------------------------------------- |
| yield            | 多次返回，每次推一段文字               |
| data: ... \n\n   | SSE 协议格式，告诉客户端"这是一条消息" |
| data: [DONE]\n\n | 结束信号，告诉客户端"没了"             |

---

## LangGraph

1. State（状态）— 流程图上的"共享黑板"

所有节点共用一块黑板，上面可以写东西（数据），后面的节点能看到前面写的内容。

比如：节点1 在黑板上写 `"姓名: 张三"`，节点2 就能读到并说 "你好张三"。

2. Node（节点）— 流程图上的每一个"方框"

每个方框里放一段 Python 代码。代码**读黑板上的内容**，处理一下，**再写回黑板**。

3. Edge（边）— 方框之间的箭头

箭头决定执行顺序。`NodeA → NodeB` 意思是先执行 A，再执行 B。



一个简单的例子

```py
# app/agents/main.py — LangGraph 第一步：画一个 2 节点的流程图

from typing import TypedDict
from langgraph.graph import StateGraph, START, END

# 1. 定义"黑板"（State）
class MyState(TypedDict):
    message: str

# 2. 定义"节点1"（一个 Python 函数）
def say_hello(state: MyState) -> dict:
    old = state["message"]
    new = old + "嗨"
    print(f"--- 执行 say_hello, 当前长度: {len(new)} ---")
    return {"message": new}
# 3. 定义"节点2"
def say_bye(state: MyState) -> dict:
    print("--- 执行节点2: say_bye ---")
    old_msg = state["message"]
    return {"message": old_msg + " ——再见！"}

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
builder.add_edge(START, "hello")
builder.add_conditional_edges(
    "hello",
    should_repeat,
    {
        "repeat": "hello",
        "enough": "bye"
    }
)
builder.add_edge("bye", END)

graph = builder.compile()

result = graph.invoke({"message": ""})
print("\n最终黑板上的内容:", result["message"])
```

| 概念             | 说明                                       |
| ---------------- | ------------------------------------------ |
| State            | TypedDict 定义的黑板，节点间共享数据       |
| Node             | 普通 Python 函数，读 state 写 state        |
| Edge             | add_edge() 固定的箭头                      |
| Conditional Edge | add_conditional_edges() 根据条件走不同路径 |
| 循环             | 节点通过条件边回到自己或前面的节点         |



结合大模型

```py
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
```

**遇到的一些问题**

刚才跑 LangGraph 的过程中你遇到了几个典型问题，总结一下：

问题 1：条件边死循环

**现象：** `say_hello` 无限执行直到报 `Recursion limit reached`

**原因：** 条件的终止条件设置不合理——`"你好，我是助手小明"` 只有 9 个字，但判断条件是 `< 10`，永远达不到 `>= 10`

**教训：** 写条件边时，一定要确保**存在一条能到达 END 的路径**，否则死循环。

问题 2：节点名 vs 函数引用

**现象：** `ValueError: Found edge ending at unknown node`

**原因：** `add_node("chat", chat)` 注册的名字是 `"chat"`（字符串），但 `add_edge(bye, chat)` 传的是函数对象本身

**教训：** LangGraph 里节点用**字符串名字**引用，不要传函数对象

| 正确                    | 错误                  |
| ----------------------- | --------------------- |
| add_edge("bye", "chat") | add_edge("bye", chat) |

问题 3：同步 vs 异步（Async vs Sync）

**现象：** `'coroutine' object has no attribute 'choices'`

**原因：** `app/core/llm.py` 用的是 `AsyncOpenAI`，调用要加 `await`，但 `chat` 函数忘了加

**教训：** `AsyncOpenAI` 的所有方法都要 `await`。如果节点是 `async def`，图调用时也要用 `ainvoke()` 而不是 `invoke()`

| 同步节点          | 异步节点                                                    |
| ----------------- | ----------------------------------------------------------- |
| def fn(state)     | async def fn(state)                                         |
| graph.invoke(...) | await graph.ainvoke(...) 或 asyncio.run(graph.ainvoke(...)) |

一句话记住

> 加节点用字符串名，调 LLM 要加 await，条件边一定要有终点。
