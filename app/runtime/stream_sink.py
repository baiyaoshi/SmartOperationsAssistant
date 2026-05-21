"""SSE 事件流旁路

executor 内部的工具调用结果实时推送到一个队列，
API 层从队列消费并推送给前端。
"""

import asyncio
import contextvars
from typing import Optional, AsyncGenerator

# 当前请求的 SSE 队列（每个请求独立）
_current_queue: contextvars.ContextVar[Optional["asyncio.Queue[str]"]] = contextvars.ContextVar(
    "_current_queue", default=None
)


def set_sink_queue(queue: asyncio.Queue[str]) -> None:
    """设置当前请求的 SSE 队列（API 层调用）"""
    _current_queue.set(queue)


def clear_sink_queue() -> None:
    """清除当前请求的 SSE 队列"""
    _current_queue.set(None)


async def push_event(event: str) -> None:
    """向当前请求推送一个 SSE 事件（节点内部调用）"""
    queue = _current_queue.get()
    if queue is not None:
        await queue.put(event)


async def sink_generator(queue: asyncio.Queue[str]) -> AsyncGenerator[str, None]:
    """从队列消费事件，生成 SSE 格式的字符串"""
    try:
        while True:
            event = await asyncio.wait_for(queue.get(), timeout=30.0)
            if event == "[DONE]":
                break
            yield event
    except asyncio.TimeoutError:
        yield "data: [TIMEOUT]\n\n"