我是一名agent初学者，希望通过一个项目来深入了解agent，参考项目F:\develop\agent\mutil-rag-agent 你可能丢失了一些记忆，请重新阅读我的项目和参考项目，阅读我的md文件，并且给出我接下来应该完成的事情，在你指导我的时候，最好不要给我直接生成代码，告诉我应该干什么



1. **新建 `network_server.py`**（网络诊断 MCP 服务器，ping/HTTP/DNS/端口）
2. **新建 `docker_server.py`**（Docker 管理 MCP 服务器）
3. **开始轻量 RAG 知识库**（chromadb）
4. **整理项目结构**（路由拆分到 `api/v1/`）



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



### 使用graph调用api

```py
from typing import TypedDict

import asyncio
from langgraph.graph import StateGraph, START, END
from app.core.llm import client

# 1. 定义（State）
class MyState(TypedDict):
    message: str
# 试试调用大模型
async def chat(state: MyState) -> dict:
    old_msg = state["message"]
    response = await client.chat.completions.create(
        model="qwen-plus",
        messages=[{"role": "user", "content": f"请用正式的语言总结这句话：{old_msg}"}]
    )
    reply = response.choices[0].message.content
    print(f"--- LLM 总结: {reply} ---")
    return {"message": reply}
# 4. 画流程图 & 执行
def build_graph():
    builder = StateGraph(MyState)
    builder.add_node("chat", chat)
    builder.add_edge(START,"chat")
    builder.add_edge("chat", END)
    graph = builder.compile()
    return graph

```

```py
agent_graph = build_graph()
@app.post("/api/v1/agent/demo")
async def graph_demo(request: ChatRequest):
    result = await agent_graph.ainvoke({"message": request.message})
    return {"message": result["message"]}
```

**`ainvoke()` 的参数就是state的初始状态。**



### 简单的langraph节点，包含skillrouter,executor,replanner等

```py
"""LangGraph Plan-Execute-Replan 演示"""

from typing import TypedDict, List
from langgraph.graph import StateGraph, START, END
from app.core.llm import client


class PlanExecuteState(TypedDict):
    input: str  # 用户原始问题
    selected_skill: str  # 选中的技能
    plan: List[str]  # 待执行的步骤列表
    past_steps: List[str]  # 已执行的步骤描述
    current_step: str  # 当前步骤
    current_result: str  # 当前步骤的结果
    response: str  # 最终报告
    step_index: int  # 当前步数
    is_finished: bool  # 是否完成


async def skill_router(state:PlanExecuteState)->dict:
    """判断用户提出问题属于哪一个诊断领域"""
    prompt = f"""用户问题: {state['input']}
    请判断这是哪类问题, 从以下选项中选择一个:
    - host_resource: CPU/内存/磁盘/本机卡顿
    - network: ping/HTTP/DNS/端口/网址打不开
    - generic: 其他无法归类的故障
    只返回选项名称, 不要其他文字。"""
    resp=await client.chat.completions.create(
        model="qwen-plus",
        messages=[{"role":"user","content":prompt}]
    )
    skill=resp.choices[0].message.content.strip()
    print(f"选择了Skill：{skill}")
    return {"selected_skill":skill}


#节点Planner（制定计划）
async def planner(state: PlanExecuteState) -> dict:
    """把用户问题拆成 2-3 个诊断步骤"""
    prompt = f"""用户问题: {state['input']}
                请把这个问题拆成 2-3 个诊断步骤，每步一句话。
                只返回步骤列表，每行一个，不要序号。"""

    resp = await client.chat.completions.create(
        model="qwen-plus",
        messages=[{"role": "user", "content": prompt}]
    )
    steps = resp.choices[0].message.content.strip().split("\n")
    print(f"计划: {steps}")
    return {"plan": steps, "step_index": 0, "is_finished": False}


#节点Executor（执行一步）
async def executor(state: PlanExecuteState) -> dict:
    """执行当前步骤"""
    idx = state["step_index"]
    step = state["plan"][idx]
    print(f"🔧 执行第 {idx + 1} 步: {step}")

    #简单模拟让LLM回答这一步
    resp = await client.chat.completions.create(
        model="qwen-plus",
        messages=[{"role": "user", "content": f"请回答这个问题（模拟诊断工具）: {step}"}]
    )
    result = resp.choices[0].message.content

    # 打开state 拼接过去完成步骤 拼接前50作为摘要后续我可能会进行修改
    new_past_steps = state.get("past_steps", []) + [f"{step} → {result[:50]}..."]
    return {
        "current_step": step,
        "current_result": result,
        "past_steps": new_past_steps,
        "step_index": idx + 1
    }


#节点Replanner（评估进度）
async def replanner(state: PlanExecuteState) -> dict:
    """判断是否完成"""
    idx = state["step_index"]
    total = len(state["plan"])

    if idx >= total:
        # 所有步骤执行完毕，生成报告
        prompt = f"""用户问题: {state['input']}
                诊断记录: {state['past_steps']}
                请生成一份完整的诊断报告。"""
        resp = await client.chat.completions.create(
            model="qwen-plus",
            messages=[{"role": "user", "content": prompt}]
        )
        report = resp.choices[0].message.content
        print(f" 报告生成完成")
        return {"response": report, "is_finished": True}
    else:
        print(f" 还有 {total - idx} 步未执行，继续")
        return {"is_finished": False}


#条件边: 判断是否继续
def should_continue(state: PlanExecuteState) -> str:
    if state["is_finished"]:
        return "end"
    else:
        return "continue"


#建图
def build_graph():
    builder = StateGraph(PlanExecuteState)
    builder.add_node("skill_router",skill_router)
    builder.add_node("planner", planner)
    builder.add_node("executor", executor)
    builder.add_node("replanner", replanner)

    builder.add_edge(START, "skill_router")
    builder.add_edge("skill_router","planner")
    builder.add_edge("planner", "executor")
    builder.add_edge("executor", "replanner")
    builder.add_conditional_edges(
        "replanner",
        should_continue,
        {
            "continue": "executor",  # 还有步骤 → 继续执行
            "end": END  # 完成 → 结束
        }
    )

    return builder.compile()
```

### 在节点中调用工具

```py
async def executor(state: PlanExecuteState) -> dict:
    """执行当前步骤"""
    idx = state["step_index"]
    step = state["plan"][idx]
    print(f" 执行第 {idx + 1} 步: {step}")

    #第一次调用，让llm决定是否要调用工具
    resp = await client.chat.completions.create(
        model="qwen-plus",
        messages=[{"role": "user", "content": step}],
        tools=[info["definition"] for info in tool_registry.values()]
    )
    msg=resp.choices[0].message
    #如果决定调用工具
    if msg.tool_calls:
        tool_results=[]
        for tool_call in msg.tool_calls:
            tool_name=tool_call.function.name
            tool_info=tool_registry[tool_name]
            arguments=json.loads(tool_call.function.arguments)
            result=tool_info["function"](**arguments)
            tool_results.append({
                "role":"tool",
                "tool_call_id":tool_call.id,
                "content":result
            })
        #第二次调用，工具调用结果交给LLM
        second_resp=await client.chat.completions.create(
            model="qwen-plus",
            messages=[
                {"role":"user","content":step},
                msg,
                *tool_results
            ]
        )
        result=second_resp.choices[0].message.content
    else:
        result=msg.content

    # 打开state 拼接过去完成步骤 拼接前50作为摘要后续我可能会进行修改
    new_past_steps = state.get("past_steps", []) + [f"{step} → {result[:50]}..."]
    return {
        "current_step": step,
        "current_result": result,
        "past_steps": new_past_steps,
        "step_index": idx + 1
    }
```



**工具是怎么调用的，arguments又是什么语法，我完全没看到工具调用的函数**？

A:

```python
for tool_call in msg.tool_calls:
    tool_name = tool_call.function.name        # 工具名（字符串）
    tool_info = tool_registry[tool_name]       # 从注册表取 {function, definition}
    arguments = json.loads(tool_call.function.arguments)  # ← 你问的这行
    result = tool_info["function"](**arguments)  # ← 真正调用工具的地方
```

拆开来看

1. `msg.tool_calls` 是什么？

当 LLM 决定调工具时，它返回的 `msg.tool_calls` 是一个列表，比如：

```python
[
    ToolCall(
        id="call_123",
        function=Function(
            name="get_current_time",           # 工具名
            arguments='{}'                      # 参数（JSON 字符串）
        )
    ),
    ToolCall(
        id="call_456",
        function=Function(
            name="get_weather",
            arguments='{"city": "北京"}'         # 参数
        )
    )
]
```

2. `json.loads(tool_call.function.arguments)`

LLM 返回的 `arguments` 是 **JSON 格式的字符串**，比如 `'{"city": "北京"}'`。

```
json.loads()` 把它解析成 Python 字典：`{"city": "北京"}
```

3. `tool_info["function"](**arguments)` ← **真正调用的地方**

`tool_info` 是从注册表里取出来的

```python
{
    "function": get_weather,        # ← 这是真正的 Python 函数
    "definition": weather_tool_definition  # ← 这是给 LLM 看的 JSON 描述
}
```

所以 `tool_info["function"]` 就是 `get_weather` 这个函数。

`**arguments` 是 Python 的**解包语法**，把字典展开成关键字参数：

```python
# 如果 arguments = {"city": "北京"}
# 那么：
tool_info["function"](**arguments)
# 等价于：
get_weather(city="北京")
```

总结

| 代码                               | 含义                                      |
| ---------------------------------- | ----------------------------------------- |
| tool_call.function.name            | LLM 说"我要调 get_weather"                |
| tool_registry["get_weather"]       | 从注册表找到对应的函数和定义              |
| tool_call.function.arguments       | LLM 给的参数，是 JSON 字符串              |
| json.loads(...)                    | 把 '{"city":"北京"}' 变成 {"city":"北京"} |
| tool_info["function"](**arguments) | 真正执行 get_weather(city="北京")         |

所以整条链路是：

```
LLM 说"调 get_weather，参数 city=北京"
  → 解析出函数名和参数
  → 从注册表找到 get_weather 这个 Python 函数
  → 用 **arguments 把参数传进去
  → 函数执行，返回结果
```

### 让llm返回固定的json

structured.py

```py
"""结构化输出兼容层 — 让 LLM 返回 JSON，解析成 Pydantic 对象"""

import json
import re
from typing import Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def _schema_hint(schema_cls: Type[BaseModel]) -> str:
    """把 Pydantic 模型转换成 JSON 字段说明文本，塞给 LLM"""
    schema = schema_cls.model_json_schema()
    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    lines = []
    for name, meta in props.items():
        type_name = meta.get("type") or "any"
        req = "必填" if name in required else "可选"
        desc = meta.get("description", "")
        lines.append(f'  - "{name}" ({req}, {type_name}): {desc}')
    return "\n".join(lines)


def _extract_json(text: str) -> dict:
    """从 LLM 回复中提取 JSON 对象（兼容 ```json 代码块）"""
    raw = text.strip()
    # 去掉 markdown 代码块标记
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # 如果整段不是 JSON，尝试从中提取 {...}
        match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if not match:
            raise ValueError(f"无法从 LLM 回复中提取 JSON: {text[:200]}")
        return json.loads(match.group(0))
```

你的 `skill_router` 节点目前是这样拿 LLM 结果的：

```python
resp = await client.chat.completions.create(
    model=harness.router_model,
    messages=[{"role": "user", "content": prompt}]
)
skill = resp.choices[0].message.content.strip()
```

问题：**你完全信任 LLM 会"乖乖返回选项名称，不要其他文字"**。

但 LLM 经常不听话：

- ✅ `"host_resource"`
- ❌ `"这个问题属于 host_resource 类型"`
- ❌ `"host_resource（CPU/内存/磁盘）"`
- ❌ `"根据你的描述，我判断是 host_resource 问题"`
- ❌ 甚至可能返回空字符串或一堆废话

你的后续代码直接拿 `skill` 去做逻辑判断，一旦格式不对就崩了。

解决方案的思路

不让 LLM 返回**自由文本**，而是要求它返回**固定结构的 JSON**：

```
用户问："我的电脑很卡"
LLM 返回 JSON → {"skill_name": "host_resource", "confidence": 0.95}
```

然后用代码**解析 + 校验**这个 JSON：

```python
# 如果 JSON 里缺了 skill_name 字段 → 报错，走默认值
# 如果 confidence 不在 0~1 之间 → 报错，走默认值
```

```
LLM 返回文本
    ↓
_extract_json()      → 把文本里的 JSON 扒出来（兼容各种 messy 格式）
    ↓
schema_cls.model_validate()  → 用 Pydantic 校验字段类型/必填
    ↓
返回 Pydantic 对象  → 后面代码直接 .field_name 取值，安全可靠
```

三个函数的职责

| 函数                 | 职责                                                         | 为什么需要                                                   |
| -------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| _schema_hint()       | 把 Pydantic 模型转成文字说明，告诉 LLM "按这个结构返回 JSON" | LLM 要知道 JSON 长什么样才能按格式输出                       |
| _extract_json()      | 从 LLM 回复的文本里提取 JSON 对象                            | LLM 可能返回 json\n{...}\n，也可能直接返回 {...}，也可能在废话中间夹一个 {...} |
| ainvoke_structured() | 调 LLM → 解析 → 校验 → 重试 的完整流程                       | 把"调 LLM"和"拿结构化数据"两步打包成一个函数，所有节点通用   |

使用例

```py
class SkillChoice(BaseModel):
    skill_name: str = Field(..., description="选中的技能名称: host_resource / network / generic")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="置信度 0~1")
    reason: str = Field(default="", description="选择原因")

async def skill_router(state:PlanExecuteState)->dict:
    """判断用户提出问题属于哪一个诊断领域"""
    #注入prompt
    prompt = harness.skill_router_prompt.format(input=state["input"])
    try:
        choice = await ainvoke_structured(
            llm=client,
            schema_cls=SkillChoice,
            messages=[{"role": "user", "content": prompt}],
            model_name=harness.router_model,
        )
        skill = choice.skill_name.strip().lower()
        print(f"选择了 Skill：{skill} (置信度: {choice.confidence}, 原因: {choice.reason})")
    except Exception as e:
        print(f"  skill_router LLM 调用失败，走默认值: {e}")
        skill = "generic"

    return {"selected_skill": skill}
```

### Skill

先写好skill数据模型

```py
"""Skill 数据模型 — 每个 Skill 由一个 SKILL.md 文件描述"""

from typing import List, Optional
from pydantic import BaseModel, Field


class Skill(BaseModel):
    """单个 Skill 的运行时表示"""

    name: str = Field(..., description="Skill 唯一标识, snake_case, 例如 host_resource_diagnosis")
    display_name: str = Field(..., description="人类可读名称")
    description: str = Field(..., description="适用场景一句话描述")
    triggers: List[str] = Field(default_factory=list, description="触发关键字")
    allowed_tools: List[str] = Field(default_factory=list, description="允许的工具白名单，空=全部允许")
    risk_level: str = Field(default="low", description="风险等级: low/medium/high")

    # Markdown body
    playbook: str = Field(default="", description="完整 Markdown 正文")
    source_path: Optional[str] = Field(default=None, description="源 SKILL.md 文件路径")

    def to_router_card(self) -> str:
        """生成给 Router LLM 看的菜单条目"""
        triggers = ", ".join(self.triggers) if self.triggers else "(无)"
        return (
            f"- **{self.name}** — {self.display_name}\n"
            f"  适用场景: {self.description}\n"
            f"  触发关键字: {triggers}"
        )
```

再写loader skill解析器

```py
"""SKILL.md 解析器 — YAML frontmatter + Markdown body"""
"""读取skill.md转成skill对象"""
"""
SKILL.md 文件内容
    │
    ▼
---                          ← 文件以 --- 开头
name: host_resource...       ← 中间是 YAML 格式的元信息
display_name: 主机资源诊断
triggers: [cpu 高, 内存高]
---
                             ← 第二个 --- 之后是正文
# 主机资源诊断 Playbook      ← Markdown 格式的步骤模板
1. 检查 CPU 使用率...
    │
    │  loader.py 解析
    ▼
Skill 对象：
  name = "host_resource_diagnosis"
  display_name = "主机资源诊断"
  triggers = ["cpu 高", "内存高"]
  playbook = "# 主机资源诊断 Playbook1. 检查 CPU...
  """


import re
from pathlib import Path
from typing import Any, Dict, Tuple

import yaml

from app.skills.models import Skill


class SkillLoadError(Exception):
    """SKILL.md 解析失败"""


# 匹配: ---\n<yaml>\n---\n<body>
_FRONTMATTER_RE = re.compile(
    r"^---\s*\n(.*?)\n---\s*\n(.*)$",
    re.DOTALL,
)


def _split_frontmatter(text: str) -> Tuple[Dict[str, Any], str]:
    """把 SKILL.md 文本拆成 (frontmatter dict, body str)"""
    cleaned = text.lstrip("\ufeff")  # 去掉 Windows BOM
    match = _FRONTMATTER_RE.match(cleaned)
    if not match:
        raise SkillLoadError("SKILL.md 必须以 --- 开头，包含 YAML frontmatter")
    fm_text, body = match.group(1), match.group(2)
    try:
        fm = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError as e:
        raise SkillLoadError(f"YAML 语法错误: {e}") from e
    if not isinstance(fm, dict):
        raise SkillLoadError(f"frontmatter 必须是字典，实际是 {type(fm).__name__}")
    return fm, body.strip()


def load_skill_from_file(path: Path) -> Skill:
    """从 SKILL.md 文件加载单个 Skill"""
    text = path.read_text(encoding="utf-8")
    fm, body = _split_frontmatter(text)

    try:
        skill = Skill(
            **fm,
            playbook=body,
            source_path=str(path),
        )
    except Exception as e:
        raise SkillLoadError(f"Skill 字段校验失败 ({path}): {e}") from e

    print(f"  [Skill] 已加载: {skill.name} <- {path}")
    return skill
```

```python
class SkillLoadError(Exception):
    """SKILL.md 解析失败"""
```

自定义异常

使用例

```py
try:
    skill = load_skill_from_file(skill_md)
except SkillLoadError as e:
    print(f"跳过文件 {skill_md}: {e}")
    continue    # 跳过这个坏文件，继续加载下一个
```

`_FRONTMATTER_RE` 正则

匹配 SKILL.md 的格式：

```
---                          ← 开头
name: host_resource_diagnosis
display_name: 主机资源诊断    ← 中间是 YAML
---
# Playbook                   ← 两个 --- 之后是正文
1. 检查 CPU...
```

`_split_frontmatter`

| 步骤 | 代码                    | 作用                                                         |
| ---- | ----------------------- | ------------------------------------------------------------ |
| 1    | \ufeff 处理             | Windows 记事本存 UTF-8 时会在文件头加个看不见的字符，去掉它  |
| 2    | _FRONTMATTER_RE.match() | 用正则把文件拆成 YAML 头和 Markdown 正文                     |
| 3    | yaml.safe_load(fm_text) | 把 YAML 字符串解析成 Python 字典，比如 {"name": "host_resource", "triggers": ["cpu"]} |

返回结果是一个元组：`({"name": "host_resource", ...}, "# Playbook\n1. 检查...")`

`load_skill_from_file`

| 步骤 | 代码                       | 作用                                                         |
| ---- | -------------------------- | ------------------------------------------------------------ |
| 1    | path.read_text()           | 把 SKILL.md 文件的全部内容读到内存                           |
| 2    | _split_frontmatter()       | 拆成 (YAML 字典, 正文)                                       |
| 3    | Skill(**fm, playbook=body) | 把字典展开传给 Skill 构造函数，**fm 就是把 {"name": "xxx", "display_name": "yyy"} 变成 Skill(name="xxx", display_name="yyy", ...) |
| 4    | try/except                 | 如果某个字段类型不对（比如 name 不是字符串），Pydantic 会抛异常，统一包成 SkillLoadError |

总结

|                      |                                                  |
| -------------------- | ------------------------------------------------ |
| SkillLoadError       | 解析 SKILL.md 出错时抛的异常，让调用方能捕获跳过 |
| _FRONTMATTER_RE      | 正则，把 ---\nYAML\n---\n正文 拆成两段           |
| _split_frontmatter   | 用正则拆文件，把 YAML 字符串转成 Python 字典     |
| load_skill_from_file | 读文件 → 拆 frontmatter → 变成 Skill 对象        |

registry

```py
"""SkillRegistry — 扫描 definitions/ 目录加载所有 SKILL.md，全局单例"""

from pathlib import Path
from typing import Dict, List, Optional

from app.skills.loader import SkillLoadError, load_skill_from_file
from app.skills.models import Skill

# Skill 定义目录
_DEFINITIONS_DIR = Path(__file__).parent / "definitions"

# 兜底 Skill 名
GENERIC_SKILL_NAME = "generic_oncall"


class SkillRegistry:
    """加载和管理所有 Skill"""

    def __init__(self, skills: Dict[str, Skill]) -> None:
        self._skills = skills

    def all(self) -> List[Skill]:
        return list(self._skills.values())

    def names(self) -> List[str]:
        return list(self._skills.keys())

    def get(self, name: str) -> Optional[Skill]:
        return self._skills.get(name)

    def get_or_generic(self, name: Optional[str]) -> Skill:
        """取指定 Skill，不存在时回退到 generic_oncall"""
        if name and name in self._skills:
            return self._skills[name]
        generic = self._skills.get(GENERIC_SKILL_NAME)
        if generic is None:
            raise RuntimeError(f"兜底 Skill {GENERIC_SKILL_NAME!r} 缺失")
        return generic

    def to_router_menu(self) -> str:
        """生成给 Router LLM 看的全部 Skill 菜单"""
        cards = [s.to_router_card() for s in self._skills.values()]
        return "\n\n".join(cards)


def _scan_definitions(root: Path) -> Dict[str, Skill]:
    """扫描 definitions/ 目录加载所有 SKILL.md"""
    skills: Dict[str, Skill] = {}
    if not root.exists():
        print(f"[Skill] 定义目录不存在: {root}")
        return skills

    for skill_md in sorted(root.glob("*/SKILL.md")):
        try:
            skill = load_skill_from_file(skill_md)
        except SkillLoadError as e:
            print(f"[Skill] 跳过 {skill_md}: {e}")
            continue

        if skill.name in skills:
            print(f"[Skill] 重名 {skill.name!r}，后者覆盖前者: {skill_md}")
        skills[skill.name] = skill

    return skills


# 全局单例（启动时加载一次）
_registry: Optional[SkillRegistry] = None


def get_skill_registry() -> SkillRegistry:
    """获取全局 SkillRegistry 单例"""
    global _registry
    if _registry is None:
        skills = _scan_definitions(_DEFINITIONS_DIR)
        print(f"[Skill] 已加载 {len(skills)} 个 Skill: {list(skills.keys())}")
        _registry = SkillRegistry(skills)
    return _registry
```

| 方法                  | 作用                                        | 例子                                          |
| --------------------- | ------------------------------------------- | --------------------------------------------- |
| all()                 | 返回所有 Skill 列表                         | [Skill(...), Skill(...)]                      |
| names()               | 返回所有 Skill 名字                         | ["host_resource_diagnosis", "generic_oncall"] |
| get("xxx")            | 按名字取一个 Skill                          | registry.get("host_resource")                 |
| get_or_generic("xxx") | 取 Skill，找不到就返回兜底的 generic_oncall | 防止 planner/executor 拿到 None 报错          |
| to_router_menu()      | 生成给 LLM 看的菜单文字                     | 拼装所有 Skill 的 to_router_card()            |

`_scan_definitions`

**扫描 `definitions/` 目录下所有 `\*/SKILL.md` 文件，逐个加载。**



get_skill_registry` 全局单例

和 `agent_harness.py` 里的 `get_agent_harness()` 完全一样的模式。

| 特性                  | 说明                           |
| --------------------- | ------------------------------ |
| 全局变量 _registry    | 第一次调用时加载，后续直接返回 |
| 只加载一次            | 启动时扫描文件，后续只从内存取 |
| 改 Skill 文件需要重启 | 不像热加载那么复杂，目前够用   |



回顾一下整个技能树的工作流：

```
Skill 注册表 (启动时加载)
  │
  ├── host_resource_diagnosis/SKILL.md
  │     ├── name, display_name, description, triggers
  │     ├── allowed_tools
  │     └── playbook (Markdown 正文)
  │
  └── generic_oncall/SKILL.md
        └── ...

skill_router 调 registry.to_router_menu() 动态生成菜单
  │
  LLM 从菜单中选 skill_name → "host_resource_diagnosis"
```

现在加新 Skill 只需要：

1. 在 `app/skills/definitions/` 下建一个 `新skill名/SKILL.md`
2. 重启服务





### Redis记忆存储

`app/services/chat_memory.py` — 记忆存储层

提供 4 个核心函数：

| 函数                                        | 功能                          |
| ------------------------------------------- | ----------------------------- |
| append_message(session_id, role, content)   | 追加一条消息到 session        |
| get_messages(session_id)                    | 获取 session 所有消息         |
| append_diagnosis_report(report, session_id) | 存诊断报告（跨 session 共享） |
| get_recent_diagnosis_reports(limit)         | 取最近 N 份诊断报告           |

每个消息存 JSON：`{"role": "user/assistant", "content": "...", "ts": "..."}`

Redis 键格式：

- `aiops:chat:{session_id}:messages` — 对话消息（List）
- `aiops:diagnosis:reports` — 诊断报告（List，跨 session 共享）

 `frontend/index.html` — 前端传 session_id

- 页面加载时从 URL 参数读 `session_id`
- 没有则自动生成：`session_时间戳_随机数`
- 写入 URL（`?session_id=xxx`），刷新可见
- 每次请求带上 `session_id` 字段



redis中数据

```
[
  {"role": "user", "content": "我的名字是白曜石"},
  {"role": "assistant", "content": "已确认：白曜石"},
  {"role": "user", "content": "我喜欢编程"},
  {"role": "assistant", "content": "很好！"}
]
```



```py
async def graph_memory_stream_response(message: str, session_id: str):
    """带记忆的流式诊断"""
    # 1. 存用户消息
    await chat_memory.append_message(session_id, role="user", content=message)
    # 2. 读取历史消息，构造上下文
    history = await chat_memory.get_messages(session_id)

    # 历史消息：去掉当前这条，取最近6条
    if len(history) > 1:
        recent = history[:-1]          # 去掉当前消息
        recent = recent[-6:]           # 最多留6条
    else:
        recent = []
    # 把历史拼成文本
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

    # 历史 + 当前问题，传给图
    if context:
        augmented_input = context + message
    else:
        augmented_input = message

    # 3. 跑图（带上历史上下文）
    final_response = None
    async for event in agent_graph.astream({"input": augmented_input}):
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
                    final_response = node_output.get("response", "")
                else:
                    yield f"data:继续下一步...\n\n"

```



### MCP

```py
"""MCP 客户端管理 — 连接 MCP 服务器，发现工具、调用工具"""

import json
import httpx
from typing import Any

# MCP 服务器配置
MCP_SERVERS = {
    "system": {
        "url": "http://127.0.0.1:9001",
        "description": "系统诊断 (CPU/内存/磁盘/进程)"
    }
}


class MCPClient:
    """单个 MCP 服务器的客户端"""

    def __init__(self, name: str, base_url: str):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=30.0)

    async def list_tools(self) -> list[dict]:
        """获取该服务器上的所有工具列表"""
        resp = await self._client.post(f"{self.base_url}/list_tools")
        resp.raise_for_status()
        data = resp.json()
        return data.get("tools", [])

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """调用该服务器上的一个工具"""
        resp = await self._client.post(
            f"{self.base_url}/call_tool",
            json={"name": tool_name, "arguments": arguments}
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("content", "")

    async def close(self):
        await self._client.aclose()


# 全局缓存：server_name → MCPClient 实例
_clients: dict[str, MCPClient] = {}


async def get_client(server_name: str) -> MCPClient:
    """获取（或创建）指定服务器的客户端"""
    if server_name not in _clients:
        config = MCP_SERVERS.get(server_name)
        if not config:
            raise ValueError(f"未知的 MCP 服务器: {server_name}")
        _clients[server_name] = MCPClient(server_name, config["url"])
    return _clients[server_name]


async def discover_all_tools() -> list[dict]:
    """发现所有 MCP 服务器上的工具，返回 OpenAI 格式的 tool definition 列表"""
    all_tools = []
    for server_name in MCP_SERVERS:
        try:
            client = await get_client(server_name)
            tools = await client.list_tools()
            for tool in tools:
                # 转成 OpenAI function call 格式
                definition = {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get("inputSchema", {"type": "object", "properties": {}})
                    }
                }
                all_tools.append({
                    "server": server_name,
                    "name": tool["name"],
                    "definition": definition,
                    "function": None  # MCP 工具没有本地函数
                })
        except Exception as e:
            print(f"  [MCP] 发现工具失败 ({server_name}): {e}")
    return all_tools


async def call_mcp_tool(server_name: str, tool_name: str, arguments: dict) -> str:
    """调用 MCP 工具"""
    client = await get_client(server_name)
    try:
        result = await client.call_tool(tool_name, arguments)
        return result
    except Exception as e:
        return f"工具 {tool_name} 调用失败: {e}"


async def close_all():
    """关闭所有 MCP 连接"""
    for client in _clients.values():
        await client.close()
    _clients.clear()
```

整体：为什么需要 MCP 客户端？

你现在的 executor 调工具是这样的：

```
executor → tool_registry["get_cpu_usage"]["function"](参数)
         → system_tool.py 里的那个 Python 函数
```

MCP 之后变成：

```
executor → tool_registry → 发现是 MCP 工具
         → mcp_client.call_mcp_tool("system", "get_cpu_usage", 参数)
         → HTTP 请求 → system_server.py（另一个进程）
         → psutil → 返回结果
```

所以 `mcp_client.py` 就是负责**发 HTTP 请求**的那一层。



修改meta.py

```py
"""工具路由器 — 支持本地工具 + MCP 工具"""

from typing import Optional

from app.tools.system_tool import get_cpu_usage, cpu_tool_definition, get_memory_usage, memory_tool_definition, \
    get_disk_usage, disk_tool_definition, get_top_processes, top_processes_tool_definition
from app.tools.time_tool import get_current_time, time_tool_definition
from app.tools.weather_tool import get_weather, weather_tool_definition

# ── 工具条目结构 ──
# 每个工具可以是以下两种类型之一：
#   1. 本地工具: {"type": "local", "function": <Python函数>, "definition": <OpenAI格式>}
#   2. MCP 工具: {"type": "mcp", "server": "system", "definition": <OpenAI格式>}

_tool_registry: dict = {}

def register_local_tool(name: str, func, definition: dict):
    """注册一个本地工具（直接在进程内调用）"""
    _tool_registry[name] = {
        "type": "local",
        "function": func,
        "definition": definition,
        "description": definition.get("function", {}).get("description", "")
    }

def register_mcp_tool(name: str, server: str, definition: dict):
    """注册一个 MCP 工具（通过 MCP 协议调用）"""
    _tool_registry[name] = {
        "type": "mcp",
        "server": server,
        "definition": definition,
        "description": definition.get("function", {}).get("description", "")
    }

def get_tool(name: str) -> Optional[dict]:
    """获取工具信息"""
    return _tool_registry.get(name)

def get_all_tools() -> list[dict]:
    """获取所有工具的 definition（用于传给 LLM）"""
    return [info["definition"] for info in _tool_registry.values()]

def get_tool_names() -> list[str]:
    """获取所有工具名"""
    return list(_tool_registry.keys())

# ── 注册本地工具 ──
register_local_tool("get_current_time", get_current_time, time_tool_definition)
register_local_tool("get_weather", get_weather, weather_tool_definition)
register_local_tool("get_cpu_usage", get_cpu_usage, cpu_tool_definition)
register_local_tool("get_memory_usage", get_memory_usage, memory_tool_definition)
register_local_tool("get_disk_usage", get_disk_usage, disk_tool_definition)
register_local_tool("get_top_processes", get_top_processes, top_processes_tool_definition)


# ── 以下工具会通过 MCP 发现后注册 ──
# 注册 MCP 工具的代码在 mcp_loader.py 中

# 为了方便外部引用，保持兼容
tool_registry = _tool_registry  # 别名，旧的 import 还能用
```

mcp_loader.py

```py
"""MCP 工具加载器 — 连接 MCP 服务器发现工具，注册到工具注册表"""

from app.tools.meta import register_mcp_tool
from app.core.mcp_client import MCP_SERVERS, get_client


async def discover_and_register_mcp_tools():
    """连接所有 MCP 服务器，发现工具并注册到全局注册表

    在应用启动时调用一次。
    """
    for server_name in MCP_SERVERS:
        try:
            client = await get_client(server_name)
            tools = await client.list_tools()
            for tool in tools:
                # 转成 OpenAI function call 格式
                definition = {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get("inputSchema", {
                            "type": "object",
                            "properties": {}
                        })
                    }
                }
                register_mcp_tool(tool["name"], server_name, definition)
                print(f"  [MCP] 注册工具: {tool['name']} <- {server_name}")
        except Exception as e:
            print(f"  [MCP] 连接失败 ({server_name}): {e}")
```
