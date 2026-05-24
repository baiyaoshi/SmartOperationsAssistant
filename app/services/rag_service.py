"""RAG 聊天服务

把知识库检索 + 联网搜索 + LLM 生成串成 SSE 事件流。
调用方（api/v1/chat.py）消费这个流推给前端。
"""

from __future__ import annotations

import time
from typing import Any, AsyncIterator

from app.core.llm import client
from app.runtime.agent_harness import get_agent_harness
from app.services.rag.retrieval import build_context
from app.services.rag.web_context import build_web_context
from app.services.rag.memory import rewrite_question
from app.services.rag.utils import format_history
import app.services.chat_memory as chat_memory

harness = get_agent_harness()


async def stream_chat(
    question: str,
    *,
    session_id: str = "default",
    top_k: int = 3,
    web_search: bool = False,
) -> AsyncIterator[dict]:
    """流式 RAG 聊天, yield 事件字典

    事件类型:
      - {"type": "progress", "stage": ..., "label": ..., "detail": ...}
      - {"type": "token", "content": "..."}
      - {"type": "end"}
      - {"type": "error", "message": "..."}
    """
    total_t0 = time.perf_counter()

    def progress(stage: str, label: str, detail: str = "") -> dict:
        return {
            "type": "progress",
            "stage": stage,
            "label": label,
            "detail": detail,
        }

    # ── Stage 1: 读取历史记忆 ──
    history = await chat_memory.get_messages(session_id)
    if history:
        history_text = format_history(history[-6:])  # 取最近 6 条
    else:
        history_text = "(无)"

    # ── Stage 2: Query 改写 ──
    rewritten = await rewrite_question(question, recent_messages=history[-4:] if history else [])
    if rewritten != question:
        yield progress("rewrite", "查询改写", f"{question} → {rewritten}")

    # ── Stage 3: 知识库检索 ──
    yield progress("retrieve", "正在检索知识库", f"top_k={top_k}")
    context, hits, sources, hits_meta = await build_context(rewritten, top_k)
    if hits > 0:
        yield progress("retrieve_done", f"检索完成, 命中 {hits} 个片段", ", ".join(sources[:3]))
    else:
        yield progress("retrieve_done", "知识库未命中相关内容", "")

    # ── Stage 4: 联网搜索（可选）──
    web_context = ""
    web_sources = []
    if web_search:
        yield progress("web", "正在联网补充资料", "")
        try:
            web_context, web_sources, web_hits, skip_reason = await build_web_context(
                rewritten, enabled=True
            )
            if web_hits:
                yield progress("web_done", f"联网补充完成 ({len(web_hits)} 条)", "")
            else:
                yield progress("web_done", "联网搜索未找到相关结果", skip_reason)
        except Exception as e:
            yield progress("web_done", f"联网搜索失败: {type(e).__name__}", str(e))
            web_context = ""
            web_sources = []

    # ── Stage 5: 构造 Prompt ──
    system_prompt = harness.rag_system_prompt
    user_prompt = harness.rag_user_prompt.format(
        context=context,
        web_context=web_context or "(未启用联网搜索)",
        history=history_text,
        question=question,
    )

    yield progress("llm", "模型正在生成回答", "")

    # ── Stage 6: LLM 流式生成 ──
    full_answer = ""
    input_tokens = output_tokens = 0
    llm_t0 = time.perf_counter()

    try:
        resp = await client.chat.completions.create(
            model=harness.rag_chat_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            stream=True,
            stream_options={"include_usage": True},
        )

        async for chunk in resp:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                full_answer += delta.content
                yield {"type": "token", "content": delta.content}

            usage = chunk.usage
            if usage:
                input_tokens = usage.prompt_tokens or input_tokens
                output_tokens = usage.completion_tokens or output_tokens

    except Exception as e:
        yield {"type": "error", "message": f"LLM 调用失败: {type(e).__name__}: {e}"}
        return

    # ── 收尾: 写记忆 ──
    try:
        await chat_memory.append_message(session_id, role="user", content=question)
        await chat_memory.append_message(session_id, role="assistant", content=full_answer)
    except Exception as e:
        print(f"[rag_service] 记忆写入失败: {e}")

    llm_ms = int((time.perf_counter() - llm_t0) * 1000)
    total_ms = int((time.perf_counter() - total_t0) * 1000)

    yield {
        "type": "stats",
        "data": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "llm_ms": llm_ms,
            "total_ms": total_ms,
        },
    }
    yield {"type": "end"}
