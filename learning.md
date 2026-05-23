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



### RAG

embedding.py

```py
"""Embedding 服务 — 封装 DashScope text-embedding-v3 的向量化能力"""

from functools import lru_cache
from typing import List

from openai import AsyncOpenAI

from app.config.config import settings


@lru_cache(maxsize=1)
def get_embedding_client() -> AsyncOpenAI:
    """获取 Embedding 客户端（单例）"""
    if not settings.dashscope_api_key:
        raise ValueError("DASHSCOPE_API_KEY 未配置, 无法创建 Embedding 客户端")
    return AsyncOpenAI(
        api_key=settings.dashscope_api_key,
        base_url=settings.dashscope_base_url,
    )


async def embed_texts(texts: List[str]) -> List[List[float]]:
    """将文本列表向量化"""
    client = get_embedding_client()
    resp = await client.embeddings.create(
        model=settings.dashscope_embedding_model,
        input=texts,
        dimensions=settings.dashscope_embedding_dim,
    )
    ordered = sorted(resp.data, key=lambda x: x.index)
    return [item.embedding for item in ordered]


async def embed_query(text: str) -> List[float]:
    """将单个查询文本向量化"""
    result = await embed_texts([text])
    return result[0]
```

**`get_embedding_client()`** — 创建 Embedding API 客户端（进程内只创建一次）

**`embed_texts(texts)`** — 批量向量化，用于文档入库

**`embed_query(text)`** — 单条查询向量化，用于搜索

milvus.py

```py
from typing import Any, Dict, List, Optional

from pymilvus import MilvusClient, MilvusException, DataType

from app.config.config import settings


class MilvusManager:
    def __init__(self):
        self._client: Optional[MilvusClient] = None

    def connect(self) -> None:
        if self._client is not None:
            return
        uri = f"http://{settings.milvus_host}:{settings.milvus_port}"
        print(f"[Milvus] 连接: {uri}")
        try:
            self._client = MilvusClient(uri=uri, timeout=10)
            print(f"[Milvus] 连接成功 | collections: {self.list_collections()}")
        except MilvusException as e:
            self._client = None
            print(f"[Milvus] 连接失败: {e}")
            raise

    def close(self) -> None:
        if self._client is None:
            return
        self._client.close()
        self._client = None

    def is_alive(self) -> bool:
        if self._client is None:
            return False
        try:
            self._client.list_collections()
            return True
        except Exception:
            return False

    @property
    def is_connected(self) -> bool:
        return self._client is not None

    def list_collections(self) -> List[str]:
        if self._client is None:
            return []
        try:
            return self._client.list_collections()
        except Exception:
            return []

    def has_collection(self, name: Optional[str] = None) -> bool:
        if self._client is None:
            return False
        col = name or settings.milvus_collection
        try:
            return col in self._client.list_collections()
        except Exception:
            return False

    def create_collection(
        self,
        name: Optional[str] = None,
        dim: Optional[int] = None,
        drop_existing: bool = False,
    ) -> None:
        col = name or settings.milvus_collection
        dim = dim or settings.dashscope_embedding_dim

        if self.has_collection(col):
            if drop_existing:
                self.drop_collection(col)
            else:
                print(f"[Milvus] collection 已存在: {col}")
                return

        schema = MilvusClient.create_schema(
            auto_id=True,
            enable_dynamic_field=False,
        )
        schema.add_field(field_name="id", datatype=DataType.INT64, is_primary=True)
        schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=dim)
        schema.add_field(field_name="content", datatype=DataType.VARCHAR, max_length=65535)
        schema.add_field(field_name="source", datatype=DataType.VARCHAR, max_length=512)
        schema.add_field(field_name="chapter", datatype=DataType.VARCHAR, max_length=512)

        index_params = MilvusClient.prepare_index_params()
        index_params.add_index(
            field_name="vector",
            metric_type="COSINE",
            index_type="HNSW",
            params={"M": 8, "efConstruction": 64},
        )

        self._client.create_collection(
            collection_name=col,
            schema=schema,
            index_params=index_params,
        )
        print(f"[Milvus] collection 创建成功: {col} (dim={dim})")

    def drop_collection(self, name: Optional[str] = None) -> None:
        col = name or settings.milvus_collection
        self._client.drop_collection(col)
        print(f"[Milvus] 已删除 collection: {col}")

    def insert(
        self,
        texts: List[str],
        vectors: List[List[float]],
        sources: List[str],
        chapters: List[str],
    ) -> None:
        if self._client is None:
            raise RuntimeError("Milvus 未连接")
        data = []
        for i in range(len(texts)):
            data.append({
                "vector": vectors[i],
                "content": texts[i],
                "source": sources[i],
                "chapter": chapters[i],
            })
        self._client.insert(collection_name=settings.milvus_collection, data=data)

    def search(
        self,
        query_vector: List[float],
        top_k: int = 10,
        output_fields: Optional[List[str]] = None,
        expr: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if self._client is None:
            return []
        if output_fields is None:
            output_fields = ["content", "source", "chapter"]

        results = self._client.search(
            collection_name=settings.milvus_collection,
            data=[query_vector],
            anns_field="vector",
            limit=top_k,
            search_params={"metric_type": "COSINE", "params": {"ef": 64}},
            filter=expr,
            output_fields=output_fields,
        )

        rows = []
        for hits in results:
            for hit in hits:
                entity = hit.get("entity", {})
                row = {"id": hit["id"], "distance": hit["distance"]}
                for f in output_fields:
                    row[f] = entity.get(f)
                rows.append(row)
        return rows

    def get_all_chunks(self, limit: int = 16384) -> List[Dict[str, Any]]:
        if self._client is None or not self.has_collection():
            return []
        return self._client.query(
            collection_name=settings.milvus_collection,
            filter="id >= 0",
            output_fields=["content", "source", "chapter"],
            limit=limit,
        )

    def delete_by_source(self, source: str) -> None:
        if self._client is None:
            return
        self._client.delete(
            collection_name=settings.milvus_collection,
            filter=f'source == "{source}"',
        )


milvus_manager = MilvusManager()

```

connect()` / `disconnect()`

Milvus 是一个独立服务（跑在 Docker 里），你需要先建立 TCP 连接才能操作它。

参考项目也是这么做的：启动时调 `connect()`，关闭时调 `disconnect()`。

`is_alive()` / `has_collection()`

**判断性方法**。在调别的操作之前先问问"能连上吗？""这个表存在吗？"，避免直接报错。

参考项目的 `milvus.py` 也一样有 `is_alive()` 和 `has_collection()`，用于健康检查和防御性编程。

`create_collection()`

类比 MySQL 的 `CREATE TABLE`。你需要定义：

- 有哪些字段（content, vector, source, chapter...）
- 向量字段用什么距离算法（COSINE）
- 向量索引怎么建（HNSW）

这些字段名和参考项目完全一致（`pk`, `content`, `vector`, `source`, `chapter`），方便以后迁移数据。

`insert()` — 批量写入

文档入库时用。先把文本转成向量（调 embedding 服务），然后连同样本信息一起存进 Milvus。

参考项目用 `langchain_milvus.Milvus.from_documents()` 自动做，我这里拆开是因为你没用 LangChain，需要手动控制。

`search()` — 核心方法

**向量检索**。给一个查询向量，找余弦距离最近的 top_k 个文档。

这就是 RAG 的"检索"步骤。参考项目用 `milvus_manager.search()` 做底层搜索，然后用 `similarity_search` 包装成用户友好的接口。

`get_all_chunks()`

拉全量数据。用在 **BM25 混合检索**（后面 hybrid_retriever.py 里要用），因为 BM25 需要把所有文本加载到内存里建索引。

参考项目里的 `_load_all_chunks_from_milvus()` 做的是同一件事。

`delete_by_source()`

按来源删除文档。比如你想重新导入某个文件的知识，先删旧的。

vector_store.py

```py
"""向量存储操作 — 高级检索流水线: Vector → [Hybrid] → [Rerank] → 返回

safe_similarity_search: 纯向量检索，给工具/快速查询用
advanced_search: 完整流水线（向量+混合+重排），给 RAG 服务用
"""

from typing import Any, Dict, List, Optional

from app.config.config import settings
from app.core.embedding import embed_query
from app.core.milvus import milvus_manager

from app.core.hybrid_retriever import _bm25_index, hybrid_search, refresh_bm25_index
from app.core.reranker import rerank_docs

async def safe_similarity_search(
    query: str,
    k: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """纯向量检索（带异常兜底）

    Args:
        query: 查询文本
        k: 返回 top-k（None 用 settings.rag_top_k）

    Returns:
        [{"content", "source", "chapter", "distance"}, ...]
        失败时返回空列表，不抛异常
    """
    k = k or settings.rag_top_k
    if not milvus_manager.is_alive() or not milvus_manager.has_collection():
        return []

    try:
        vector = await embed_query(query)
    except Exception as e:
        print(f"[vector_store] embed_query 失败: {e}")
        return []

    try:
        rows = milvus_manager.search(vector, top_k=k)
        return rows
    except Exception as e:
        print(f"[vector_store] search 失败: {e}")
        return []


async def advanced_search(
    query: str,
    k: Optional[int] = None,
    *,
    use_hybrid: Optional[bool] = None,
    use_rerank: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """高级检索流水线: Vector → [Hybrid] → [Rerank] → 返回 top-k

    每一层可通过 settings 开关，任一环节失败自动降级到上一层结果。

    Args:
        query: 查询文本
        k: 最终返回 top-k（None 用 settings.rag_top_k）
        use_hybrid: 是否启用 BM25+Vector 融合（None 走 settings）
        use_rerank: 是否启用 Reranker 精排（None 走 settings）

    Returns:
        每项含 content / source / chapter / distance / (rerank_score) 等字段
    """


    final_k = k or settings.rag_top_k
    use_hybrid = settings.rag_hybrid_enabled if use_hybrid is None else use_hybrid
    use_rerank = settings.rag_rerank_enabled if use_rerank is None else use_rerank

    # 需要 hybrid/rerank 时，先多取一些候选，给后续环节留空间
    retrieve_k = settings.rag_retrieve_k if (use_hybrid or use_rerank) else final_k

    # Step 1: 向量粗排
    vector_docs = await safe_similarity_search(query, k=retrieve_k)
    if not vector_docs:
        return []

    # Step 2: Hybrid 融合（BM25 + Vector + RRF）
    candidates = vector_docs
    if use_hybrid:
        if not _bm25_index.is_ready:
            try:
                refresh_bm25_index()
            except Exception as e:
                print(f"[advanced_search] BM25 lazy build 失败: {e}")
        candidates = hybrid_search(query, vector_docs, k=retrieve_k)

    # Step 3: Rerank 精排
    if use_rerank and len(candidates) > final_k:
        try:
            candidates = await rerank_docs(query, candidates, top_n=final_k)
        except Exception as e:
            print(f"[advanced_search] rerank 降级: {e}")
            candidates = candidates[:final_k]
    else:
        candidates = candidates[:final_k]

    return candidates
```

**`safe_similarity_search`** — 简单版。给一句话，返回知识库里最像的 N 个文档。纯向量搜索，异常自动返回空。用在 `knowledge_tool.py` 里，Agent 调工具"查知识库"时走这个。

**`advanced_search`** — 完整版。同样给一句话，但走三条流水线：

1. 向量搜索先粗取 20 条
2. 再和 BM25（关键词匹配）结果混合排序
3. 最后用 Reranker 模型精排取前 3 条

每一层失败自动降级。用在 RAG 聊天服务里，追求最高准确率。

hybrid_retriever.py

```py
"""Hybrid Retriever: BM25 (关键词匹配) + Vector (语义匹配) + RRF 融合

为什么加 Hybrid:
  纯向量检索在语义上强，但会漏精确关键词（如"ERR_CONN_REFUSED"、"redis.exception.TimeoutError"）。
  BM25 按词频匹配正好互补。

BM25 索引存在进程内存里，启动后从 Milvus 拉全量 chunks 构建。
"""

from __future__ import annotations

import re
import threading
from typing import Any, Dict, List, Optional, Tuple

from app.config.config import settings
from app.core.milvus import milvus_manager

try:
    from rank_bm25 import BM25Okapi
except ImportError:
    BM25Okapi = None
    print("[hybrid] rank_bm25 未安装, Hybrid Search 将降级到纯向量")


# 分词器: 英文按单词切，中文按单字切
_TOKEN_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_\-\.]*|[\u4e00-\u9fff]")


def _tokenize(text: str) -> List[str]:
    """轻量分词"""
    if not text:
        return []
    tokens = _TOKEN_RE.findall(text.lower())
    return [t for t in tokens if t]


class _BM25Index:
    """BM25 索引（线程安全，惰性构建）

    第一次检索时从 Milvus 拉全量数据建索引。
    文档上传/删除后调 refresh_bm25_index() 主动刷新。
    """

    def __init__(self):
        self._bm25: Optional[BM25Okapi] = None
        self._docs: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._built = False

    def build(self, docs: List[Dict[str, Any]]) -> None:
        """用文档列表构建 BM25 索引"""
        if BM25Okapi is None:
            self._built = True
            return
        if not docs:
            with self._lock:
                self._bm25 = None
                self._docs = []
                self._built = True
            return

        tokenized = [_tokenize(d.get("content", "")) for d in docs]
        try:
            bm25 = BM25Okapi(tokenized)
        except Exception as e:
            print(f"[hybrid] BM25 构建失败(降级): {e}")
            with self._lock:
                self._bm25 = None
                self._docs = []
                self._built = True
            return

        with self._lock:
            self._bm25 = bm25
            self._docs = docs
            self._built = True
        print(f"[hybrid] BM25 索引构建完成: {len(docs)} 文档")

    def search(self, query: str, k: int) -> List[Tuple[Dict[str, Any], float]]:
        """BM25 检索，返回 (文档, 分数) 列表"""
        if not self._built or self._bm25 is None or not self._docs:
            return []
        tokens = _tokenize(query)
        if not tokens:
            return []
        try:
            scores = self._bm25.get_scores(tokens)
        except Exception:
            return []
        indexed = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:k]
        return [(self._docs[i], float(s)) for i, s in indexed if s > 0]

    @property
    def is_ready(self) -> bool:
        return self._built and self._bm25 is not None


_bm25_index = _BM25Index()


def refresh_bm25_index() -> None:
    """重建 BM25 索引（从 Milvus 拉全量文档）"""
    if BM25Okapi is None:
        return
    if not milvus_manager.has_collection():
        return
    try:
        rows = milvus_manager.get_all_chunks()
    except Exception as e:
        print(f"[hybrid] 拉全量失败(降级): {e}")
        return
    _bm25_index.build(rows)


def hybrid_search(
    query: str,
    vector_docs: List[Dict[str, Any]],
    *,
    k: int,
    bm25_weight: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """将向量结果和 BM25 结果用 RRF 融合，返回 top-k

    RRF 公式: score = 权重 / (60 + 排名)
    只用排名不看绝对分数，解决向量和 BM25 量纲不同的问题。
    """
    bm25_weight = bm25_weight if bm25_weight is not None else settings.rag_hybrid_bm25_weight
    vec_weight = 1.0 - bm25_weight

    retrieve_k = max(k, settings.rag_retrieve_k)
    bm25_results = _bm25_index.search(query, retrieve_k) if _bm25_index.is_ready else []

    if not bm25_results:
        return vector_docs[:k]

    # RRF 融合
    rrf_k = 60
    scores: Dict[str, float] = {}
    doc_map: Dict[str, Dict[str, Any]] = {}

    def _key(doc: Dict[str, Any]) -> str:
        """用 source + chapter + content 做唯一键去重"""
        return f"{doc.get('source', '')}|{doc.get('chapter', '')}|{hash(doc.get('content', ''))}"

    for rank, doc in enumerate(vector_docs):
        kk = _key(doc)
        scores[kk] = scores.get(kk, 0.0) + vec_weight / (rrf_k + rank + 1)
        doc_map.setdefault(kk, doc)

    for rank, (doc, _) in enumerate(bm25_results):
        kk = _key(doc)
        scores[kk] = scores.get(kk, 0.0) + bm25_weight / (rrf_k + rank + 1)
        doc_map.setdefault(kk, doc)

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top = [doc_map[kk] for kk, _ in ranked[:k]]
    return top
```

**这个文件解决一个实际问题：纯向量检索会漏掉精确关键词。**

举个例子：

- 用户搜 `"ERR_CONN_REFUSED"` — 向量会把这几个词"揉"成语义，找出来的可能是"连接失败"相关的泛泛内容
- 用户搜 `"redis.exceptions.TimeoutError"` — 向量不认识这个精确的异常类名

**BM25 就像传统搜索引擎的关键词匹配**，见字如面，看到 `ERR_CONN_REFUSED` 就找包含这几个字符的文档，不依赖语义理解。

**RRF 融合**就是把向量结果和 BM25 结果按排名混合排序，取两者的交集和排名优势，比单用其中一路准确率高 5-15%。

**你的项目里**：`vector_store.py` 的 `advanced_search` 会调这里的 `hybrid_search()`，当 `rag_hybrid_enabled=True` 时生效。	



web_search.py

```py
"""联网搜索 Provider + 结果格式化

支持:
  - open_websearch: 本地 open-webSearch daemon（默认）
  - mock: 零配置占位数据
"""

from typing import Any, Dict, List, Optional

from app.config.config import settings

import httpx
def get_provider() -> str:
    """获取当前联网搜索 provider 名"""
    return (settings.web_search_provider or "open_websearch").lower().strip()


def search_open_websearch(query: str, max_results: int) -> List[Dict[str, Any]]:
    """open-webSearch local daemon"""


    base_url = (settings.open_websearch_base_url or "http://127.0.0.1:3210").rstrip("/")
    payload: dict = {"query": query, "limit": max_results}
    if settings.open_websearch_engine:
        payload["engines"] = [settings.open_websearch_engine]
    if settings.open_websearch_search_mode and settings.open_websearch_search_mode != "auto":
        payload["searchMode"] = settings.open_websearch_search_mode

    resp = httpx.post(
        f"{base_url}/search",
        json=payload,
        timeout=settings.open_websearch_timeout_sec,
    )
    resp.raise_for_status()
    envelope = resp.json()
    if envelope.get("status") != "ok":
        raise RuntimeError(envelope.get("error", "open-webSearch error"))

    data = envelope.get("data") or {}
    return [
        {
            "title": r.get("title", "(无标题)"),
            "url": r.get("url", ""),
            "snippet": r.get("description") or r.get("snippet") or r.get("content", ""),
        }
        for r in data.get("results", [])
        if isinstance(r, dict)
    ]


def search_mock(query: str, max_results: int) -> List[Dict[str, Any]]:
    """Mock provider"""
    return [
        {
            "title": f"[MOCK] 关于 '{query}' 的搜索结果",
            "url": "https://example.com/mock-search-result",
            "snippet": f"Mock 占位返回。原始查询: {query!r}。",
        }
    ]


def search(query: str, max_results: int, provider: Optional[str] = None) -> List[Dict[str, Any]]:
    """按 provider 调度"""
    p = (provider or get_provider()).lower().strip()
    if p in ("open_websearch", "open-websearch", "openwebsearch"):
        return search_open_websearch(query, max_results)
    if p == "mock":
        return search_mock(query, max_results)
    raise ValueError(f"未知 provider: {p!r}")


def format_results(results: List[Dict[str, Any]], *, provider: str) -> str:
    """格式化为 Markdown"""
    header = ""
    if provider == "mock":
        header = "> **[WARN] Mock 数据** 仅供演示。\n\n"
    lines = []
    for i, r in enumerate(results, 1):
        title = r.get("title", "(无标题)")
        url = r.get("url", "(无 URL)")
        snippet = (r.get("snippet") or "").strip()
        lines.append(f"### {i}. {title}\n来源: {url}\n\n{snippet}")
    return header + "\n\n---\n\n".join(lines)
```

retrieval.py

```py
"""知识库检索: 走 advanced_search (Vector → [Hybrid] → [Rerank]) 拼成 LLM 上下文"""

from typing import Any, Dict, List, Tuple

from app.config.config import settings
from app.core.vector_store import advanced_search

CHUNK_CHAR_LIMIT = 800


async def build_context(
    question: str, top_k: int
) -> Tuple[str, int, List[str], List[Dict[str, Any]]]:
    """检索知识库，拼接成 context 字符串

    Returns:
        (context_text, hit_count, sources, hits_meta)
        hits_meta: [{"source", "chapter", "preview", "score"}, ...]
    """
    docs = await advanced_search(question, k=top_k)
    if not docs:
        return "(知识库未命中相关内容)", 0, [], []

    chunks: List[str] = []
    sources: List[str] = []
    hits_meta: List[Dict[str, Any]] = []
    for i, doc in enumerate(docs, 1):
        source = doc.get("source", "未知")
        sources.append(str(source))
        chapter = doc.get("chapter", "")
        header = f"## 来源 {i} | {source}"
        if chapter:
            header += f" | 章节: {chapter}"
        raw_text = doc.get("content", "").strip()
        truncated = raw_text[:CHUNK_CHAR_LIMIT]
        if len(raw_text) > CHUNK_CHAR_LIMIT:
            truncated += "... (已截断)"
        chunks.append(f"{header}\n{truncated}")
        score = doc.get("rerank_score") or doc.get("distance")
        score_val = round(float(score), 4) if score is not None else None
        preview = raw_text.replace("\n", " ")
        hits_meta.append({
            "source": str(source),
            "chapter": str(chapter) if chapter else "",
            "preview": preview[:240] + ("..." if len(preview) > 240 else ""),
            "score": score_val,
        })

    return "\n\n".join(chunks), len(docs), sources, hits_meta
```

memory.py

```py
"""RAG Chat 的会话记忆操作: query 改写 + 历史压缩"""

from typing import Any, Dict, List


async def rewrite_question(
    question: str,
    *,
    summary: str = "",
    recent_messages: List[Dict[str, Any]] = None,
) -> str:
    """用历史改写当前问题为独立检索 query（简化版，直接返回原文）"""
    return question


async def compact_if_needed(session_id: str) -> None:
    """压缩历史（简化版暂不实现）"""
    pass
```

utils.py

```py
"""RAG 工具函数: 消息格式化"""

from typing import Any, Dict, List


def content_to_text(content: Any) -> str:
    """统一把消息 content 转成纯文本"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            c.get("text", "") if isinstance(c, dict) else str(c) for c in content
        )
    return str(content)


def format_history(messages: List[Dict[str, Any]]) -> str:
    """把 [{role, content}, ...] 渲染成给 prompt 看的多行文本"""
    if not messages:
        return "(无)"
    lines = []
    for item in messages:
        role = "用户" if item.get("role") == "user" else "助手"
        content = str(item.get("content") or "").strip()
        if content:
            lines.append(f"{role}: {content[:1200]}")
    return "\n".join(lines) if lines else "(无)"
```

web_context.py

```py
"""RAG Chat 的联网搜索上下文构造"""

from typing import Any, Dict, List, Tuple

from app.core.web_search import format_results, get_provider, search


async def build_web_context(
    rewritten_question: str,
    *,
    summary: str = "",
    recent_messages: List[Dict[str, Any]] = None,
    enabled: bool = False,
) -> Tuple[str, List[str], List[Dict[str, Any]], str]:
    """联网搜索 + 拼 context

    Returns:
        (web_context_text, sources, web_hits, skip_reason)
    """
    if not enabled:
        return "(本轮未启用联网搜索)", [], [], "本轮未启用联网搜索"

    provider = get_provider()
    max_results = max(1, min(3, 5))

    try:
        raw_hits = search(rewritten_question, max_results, provider)
    except Exception as e:
        return (
            f"(联网搜索失败: {type(e).__name__}: {e})",
            [],
            [],
            f"{type(e).__name__}: {e}",
        )

    if not raw_hits:
        return (
            f"(联网搜索未找到与 '{rewritten_question}' 相关的结果)",
            [],
            [],
            "未找到相关结果",
        )

    text = format_results(raw_hits, provider=provider)
    sources = [f"web:{rewritten_question[:20]}"]
    web_hits = [
        {
            "title": h.get("title", "")[:120],
            "url": h.get("url", "")[:300],
            "snippet": (h.get("snippet", "") or "")[:240],
        }
        for h in raw_hits
    ]
    return text, sources, web_hits, ""
```

knowledge_tool.py

```py
"""知识库检索工具 (RAG Tool)

Agent 调这个工具查询运维知识库，返回 top-k 相关片段。
"""

from app.config.config import settings
from app.core.vector_store import safe_similarity_search


def search_knowledge_base(query: str) -> str:
    """搜索运维知识库 (SOP、On-Call 手册、故障处理流程等)

    在以下场景调用本工具:
    - 需要查询某种告警的标准处理流程
    - 需要参考已有的故障处理经验

    Args:
        query: 查询关键词或问题

    Returns:
        相关文档片段 (Markdown 格式)
    """
    docs = safe_similarity_search(query, k=settings.rag_top_k)

    if not docs:
        return (
            f"知识库中没有找到与 '{query}' 直接相关的文档。"
            f"请尝试换个关键词搜索。"
        )

    chunks = []
    for i, doc in enumerate(docs, 1):
        source = doc.get("source") or "未知来源"
        chapter = doc.get("chapter") or ""
        header = f"### 片段 {i} | 来源: {source}"
        if chapter:
            header += f" | 章节: {chapter}"
        chunks.append(f"{header}\n{doc.get('content', '').strip()}")

    return "\n\n---\n\n".join(chunks)
```



knowledge.py

document_processor.py

knowledge.py  -api



1. `app/config/config.py` — 配置

**位置：** `app/config/config.py`

**改动：** 在原文件基础上增加了 RAG 和联网搜索相关的配置字段。

**新加的字段：**

```python
    # RAG 相关
    rag_top_k: int = 3
    rag_retrieve_k: int = 20
    rag_hybrid_enabled: bool = True
    rag_rerank_enabled: bool = True
    rag_rerank_model: str = "gte-rerank-v2"
    rag_rerank_timeout_sec: int = 30
    rag_chunk_size: int = 800                     # 文档分块大小 (字符)
    rag_chunk_overlap: int = 100                  # 分块重叠大小 (字符)
    rag_hybrid_bm25_weight: float = 0.4           # Hybrid 中 BM25 的权重

    # 联网搜索
    web_search_provider: str = "mock"             # open_websearch / mock
    open_websearch_base_url: str = "http://127.0.0.1:3210"
    open_websearch_engine: str = "bing"
    open_websearch_search_mode: str = "auto"
    open_websearch_timeout_sec: float = 15.0
```

**每个字段什么意思：**

| 字段                       | 默认值                | 说明                                 |
| -------------------------- | --------------------- | ------------------------------------ |
| rag_top_k                  | 3                     | 最终给 LLM 看的文档数                |
| rag_retrieve_k             | 20                    | 先粗取 20 条，给后面重排留空间       |
| rag_hybrid_enabled         | True                  | 是否启用 BM25+向量混合搜索           |
| rag_hybrid_bm25_weight     | 0.4                   | 混合搜索里 BM25 的权重（向量是 0.6） |
| rag_rerank_enabled         | True                  | 是否启用 Reranker 精排               |
| rag_rerank_model           | gte-rerank-v2         | DashScope 的 Rerank 模型             |
| rag_rerank_timeout_sec     | 8                     | Rerank 超时秒数                      |
| rag_chunk_size             | 800                   | 文档分块大小（字符数）               |
| rag_chunk_overlap          | 100                   | 相邻块重叠字符数                     |
| web_search_provider        | mock                  | 联网搜索 provider                    |
| open_websearch_base_url    | http://127.0.0.1:3210 | open-webSearch 地址                  |
| open_websearch_engine      | bing                  | 搜索引擎                             |
| open_websearch_search_mode | auto                  | 搜索模式                             |
| open_websearch_timeout_sec | 15                    | 搜索超时秒数                         |

------

**为什么要分块？** 因为 LLM 有上下文限制，一篇文章几千字不能直接扔进去，切成 800 字的小块，只取最相关的几块。

**为什么 chunk 和 overlap 是 800/100？** 800 字一段够容纳一个运维场景的描述，100 字重叠保证切在句子中间时不会丢掉关键信息。

**`rag_rerank_model: str = "gte-rerank-v2"`** — DashScope 的交叉编码器模型，比向量搜索更精准。



2. `app/core/embedding.py` — 向量化服务

**作用：** 把文本转成向量（一串数字），让计算机能理解文本的"语义相似度"。

**三个函数：**

**`get_embedding_client()`** — 创建 Embedding API 客户端。

- `@lru_cache(maxsize=1)` 保证进程只创建一次，不重复建连
- 用配置里的 `dashscope_api_key` 和 `dashscope_base_url` 初始化
- 调的是 DashScope（阿里云）的兼容 OpenAI 接口

**`embed_texts(texts)`** — 批量转向量，传一个文本列表，返回向量列表。

- 文档入库时用，一次把几十个 chunk 全转完
- `dimensions=1024` 表示每个向量 1024 维

**`embed_query(text)`** — 单条文本转向量，搜问题时用。

- 实际上调的就是 `embed_texts([text])` 取第一个结果

  

3. `app/core/milvus.py` — Milvus 向量数据库操作

**作用：** 封装所有对 Milvus 的操作——连库、建表、存数据、搜数据。

**类 `MilvusManager`** 里的关键方法：

**`connect()`** — 连接 Milvus 服务

- Milvus 是独立跑的 Docker 容器，地址 `127.0.0.1:19530`
- 用新版 `MilvusClient` 连接，省掉了旧版的 deprecation 警告

**`create_collection()`** — 建表

- 相当于 MySQL 的 `CREATE TABLE`
- 字段有 5 个：
  - `id` — 主键，自动增长
  - `vector` — 1024 维的向量，存 Embedding 结果
  - `content` — 文档原文
  - `source` — 来源文件名
  - `chapter` — 章节名
- 用 HNSW 算法建向量索引，余弦距离衡量相似度

**`insert(texts, vectors, sources, chapters)`** — 批量存文档

- 把文本、向量、来源、章节打包成字典列表写进 Milvus

**`search(query_vector, top_k)`** — 核心方法：向量搜索

- 给一个查询向量，找余弦距离最近的 N 条文档
- 返回 `[{"id", "distance", "content", "source", "chapter"}, ...]`
- `distance` 是余弦距离，越小越相似（0.7 表示挺像，0.3 表示不太像）

**`get_all_chunks()`** — 拉全量文档，给 BM25 索引用

**`delete_by_source(source)`** — 按文件名删除，重新上传时先清旧数据

**`milvus_manager = MilvusManager()`** — 全局单例，整个项目共用这一个实例



4. `app/core/vector_store.py` — 检索流水线编排

**作用：** 把前面三个模块（Embedding + Milvus + Hybrid + Reranker）串成一条流水线。对外只提供两个函数，调用方不需要关心底层细节。

**两个函数：**

**`safe_similarity_search(query, k)`** — 简单版搜索

- 三步：向量化查询 → 搜 Milvus → 返回结果
- 任何一步失败都返回空列表，不报错
- 用于 `knowledge_tool.py`（Agent 调用的工具函数）和 `knowledge.py` API 的搜索接口

**`advanced_search(query, k)`** — 高级版搜索（三步流水线）

```
用户问题 → 向量化 → 纯向量搜20条 → BM25+向量混合排序 → Reranker精排取3条
```

流程：

1. **Step 1 — 向量粗排**：把用户问题转成向量，在 Milvus 里搜 20 条
2. **Step 2 — Hybrid 融合**：如果开启了 `rag_hybrid_enabled`，把 BM25（关键词）和向量结果混合排序
3. **Step 3 — Rerank 精排**：如果开启了 `rag_rerank_enabled`，用 DashScope 的 cross-encoder 模型精排到 3 条

**降级机制：** 第 2 步失败 → 用第 1 步结果。第 3 步失败 → 用第 2 步结果。用户总会得到结果。

------

**为什么分成两个函数？**

| 函数                   | 速度   | 准确度 | 用在哪         |
| ---------------------- | ------ | ------ | -------------- |
| safe_similarity_search | 快     | 一般   | 工具、测试 API |
| advanced_search        | 慢一些 | 高     | RAG 聊天服务   |

**为什么先取 20 条再精排？** 向量搜索快但粗，BM25 和 Reranker 慢但准。先快速筛到 20 条，再花时间精排这 20 条，比直接搜 3 条准确得多。



​	5. `app/core/hybrid_retriever.py` — 混合搜索（BM25 + RRF）

**解决什么问题：** 向量搜索靠"语义"，但搜精确关键词（如 `ERR_CONN_REFUSED`、`redis.exceptions.TimeoutError`）时效果很差。BM25 按词频匹配正好互补。

**核心概念：**

**BM25 是什么？** 传统搜索引擎的核心算法（Google 早期也在用）。数关键词在文档里出现了多少次，出现越多分越高。搜 `ERR_CONN_REFUSED` 就找包含这几个字符的文档。

**RRF 融合是什么？** 向量和 BM25 的分数单位不同（一个是余弦距离 0~1，一个是 BM25 分数 0~∞），不能直接相加。RRF 的方法

```
分数 = 权重 / (60 + 排名)
```

只看排名不管绝对分数，把两份结果按排名重新打分后合并。

**关键函数：**

**`_tokenize(text)`** — 分词器

- 英文单词（`ERR_CONN_REFUSED`）保留原样
- 中文按单字切（"内存不足"→ "内" "存" "不" "足"）

**`_BM25Index` 类** — BM25 索引

- 存内存里，第一次搜索时从 Milvus 拉全量文档构建
- 线程安全（`threading.Lock`）
- `rank_bm25` 库没装时自动降级，不影响功能

**`refresh_bm25_index()`** — 重建索引

- 上传新文档后调用，让 BM25 认出新文档

**`hybrid_search(query, vector_docs, k)`** — 融合搜索

- 向量和 BM25 各搜一批，RRF 公式混合排序后取前 k 条
- `bm25_weight=0.4` 表示 BM25 占 40%，向量占 60%

------

**为什么是 0.4 和 0.6？** 运维场景以语义理解为主（"内存不足" = 找内存相关的文档），关键词只作补充（搜特定错误码时有用）。0.4/0.6 是经验值，可以调。

**为什么装在内存里？** BM25 全量索引也就几千个文档，内存里放得下而且查询速度毫秒级。



6. `app/core/reranker.py` — Reranker 精排

**解决什么问题：** 向量搜索（余弦距离）认为"相似的"不一定是"相关的"。Reranker 把问题和文档一起送进模型看它们是不是真的相关，准确度比向量高一个档次。

**原理对比：**

| 方式     | 做法                     | 比喻                                 |
| -------- | ------------------------ | ------------------------------------ |
| 向量检索 | 各自转成向量，算距离     | 两个人各自填简历，看简历像不像       |
| Reranker | 把问题和文档一起送给模型 | 面试官同时看两个人，直接比较谁更合适 |

**函数 `rerank_docs(query, docs, top_n)`：**

1. 把 20 条候选文档发给 DashScope 的 `gte-rerank-v2` 模型
2. 模型给每对 `(query, doc)` 打一个 `relevance_score`（0~1）
3. 按分数降序排列，返回前 top_n 条
4. 每条结果追加 `rerank_score` 字段

**降级机制：** API 调用失败、超时、解析异常 → 直接返回原始 docs 的前 top_n 条，不报错。

------

**为什么在向量搜索之后再 Rerank？** Reranker 每评一对 `(query, doc)` 就要调用一次模型，20 条候选就是 20 次打分，耗时约 100-300ms。如果对全量文档跑 Reranker，时间不可接受。所以先用向量搜 20 条候选，再花 100ms 精排。

**`gte-rerank-v2` 是什么？** DashScope 提供的一个专门用来给 `(问题, 文档)` 打分的模型，和 `text-embedding-v3` 同一个家族的。



7. `app/core/web_search.py` — 联网搜索

**作用：** 当知识库里找不到答案时，去互联网上搜。

**两个 provider：**

**`search_open_websearch(query, max_results)`** — 真实搜索

- 调本地跑着的 `open-webSearch` 容器（`http://127.0.0.1:3210`）
- 这个容器里封装了 Bing 搜索引擎
- 返回 `[{"title", "url", "snippet"}, ...]`

**`search_mock(query, max_results)`** — 假数据

- 返回一条固定占位结果，标注 `[MOCK]`
- 用于开发和演示

**调度函数 `search(query, max_results, provider=None)`：**

- 按 `web_search_provider` 配置选择用哪个 provider
- 没配置或配了 `mock` → 假数据
- 配了 `open_websearch` → 真实搜索

**`format_results(results, provider)`：**

- 把搜索结果格式化成 Markdown 文本，方便塞进 LLM 的上下文

------

**为什么联网搜索和知识库搜索分开？** 知识库是公司内部文档，联网搜是互联网的公开信息，来源和可信度不同，分开处理更清晰。

**什么时候用它？** RAG 聊天时如果用户问题的关键词匹配了配置里的技术主题词（redis、nginx、kubernetes 等），可以触发联网搜最新的文档（官网、Stack Overflow 等）。



9. `app/services/rag/retrieval.py` — 检索结果拼成 LLM 上下文

**作用：** 搜索知识库，把结果拼成一段 LLM 能直接看的 Markdown 文本。

**核心函数 `build_context(question, top_k)`：**

1. 调 `advanced_search` 走完整流水线（向量→混合→重排）
2. 把命中的文档拼成这样的格式：

```
## 来源 1 | 运维手册.md | 章节: CPU 诊断
当 CPU 使用率持续超过 90% 时...

## 来源 2 | 数据库手册.md | 章节: MySQL 运维
MySQL 主从延迟排查：检查 slave 的 IO/SQL 线程状态...
```

1. 同时返回元数据（来源列表、每条的预览文字、分数等）

**返回值 4 个：**

| 位置 | 字段         | 说明                                                  |
| ---- | ------------ | ----------------------------------------------------- |
| [0]  | context_text | 拼好的 Markdown 字符串，直接塞进 LLM 的 system prompt |
| [1]  | hit_count    | 命中了几条                                            |
| [2]  | sources      | 来源文件名列表                                        |
| [3]  | hits_meta    | 每条详细元数据（source, chapter, preview, score）     |

**为什么截断到 800 字？** 每条文档块本身是 800 字分出来的，但 reranker 可能返回的字段更长，再截一次保险，防止 LLM 上下文被撑爆。

------

**`CHUNK_CHAR_LIMIT = 800` 没有错吧？** 没错，就是和 `rag_chunk_size = 800` 保持一致，一条 chunk 最多 800 字符。

10.MEMORY  //TODO



11. `app/services/rag/web_context.py` — 联网搜索上下文

**作用：** RAG 聊天需要联网搜时，用 web_search.py 搜结果拼成上下文。

**函数 `build_web_context(rewritten_question, enabled)`：**

流程：

1. 如果 `enabled=False` → 返回"未启用"
2. 调 `web_search.py` 的 `search()` 联网搜
3. 用 `format_results()` 拼成 Markdown
4. 同时返回元数据（来源、摘要等）

**返回值 4 个：**

| 位置                 | 说明                        |
| -------------------- | --------------------------- |
| [0] web_context_text | Markdown 格式的搜索结果文本 |
| [1] sources          | 来源列表                    |
| [2] web_hits         | 每条搜索结果的摘要元数据    |
| [3] skip_reason      | 如果跳过了，返回原因        |

12. `app/services/rag/utils.py` — 工具函数

**两个小函数：**

**`content_to_text(content)`** — 消息内容转纯文本

- LLM 的消息 content 可能是字符串、列表（多模态）或其他类型
- 统一转成纯文本字符串，避免下游处理时类型错误

**`format_history(messages)`** — 历史消息格式化

- 把 `[{"role": "user", "content": "你好"}, {"role": "assistant", "content": "我能帮你什么"}]`
- 渲染成：

```
用户: 你好
助手: 我能帮你什么
```

- 每条不超过 1200 字符，防止历史太长





13. `app/tools/knowledge_tool.py` — Agent 知识库工具

**作用：** AIOps Agent 在诊断故障时，可以调这个工具查知识库。

**函数 `search_knowledge_base(query)`：**

- 调 `safe_similarity_search`（纯向量搜索，不走 Hybrid/Reranker，因为 Agent 调用要快）
- 返回 Markdown 格式的文档片段
- 搜不到时返回友好提示

**这个工具怎么被 Agent 使用？**

Agent 遇到一个问题（比如"Redis 连接超时"），它会：

1. 先调系统工具查当前 Redis 状态
2. 如果看不出原因 → 调 `search_knowledge_base("Redis 连接超时")`
3. 知识库返回之前记录过的处理流程
4. Agent 参考这个流程继续诊断或出报告





15. `app/services/rag/document_processor.py` — 文档分块

**作用：** 上传文档时，把一整篇文章切成一段一段 800 字的块，每块是一个独立的"知识点"。

**`chunk_text(text, source, chapter)`：**

- 按 `rag_chunk_size=800` 切段
- 相邻段有 `rag_chunk_overlap=100` 字重叠，防止关键句子被切在边缘上
