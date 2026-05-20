"""会话记忆存储 (Redis)

功能:
  - 存/取 对话消息 (按 session_id)
  - 存/取 诊断报告 (跨 session 共享)
"""

import json
from datetime import datetime, timezone
from typing import Any, Optional

from app.config.config import settings
from redis.asyncio import Redis

_redis: Optional[Any] = None
_redis_import_failed = False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _get_redis():
    global _redis, _redis_import_failed
    if not settings.chat_memory_enabled: # 配置里关闭了记忆 → 返回 None
        return None
    if _redis is not None: # 已经连接成功了 → 复用
        return _redis


    try:
        client = Redis.from_url(settings.redis_url, decode_responses=True)
        await client.ping() # 测试连接
        _redis = client
        print(f"[chat-memory] Redis 已连接: {settings.redis_url}")
        return _redis
    except Exception as e:
        _redis_import_failed = True
        print(f"[chat-memory] Redis 连接失败: {e}")
        return None


# 消息操作

#aiops:chat:
def _messages_key(session_id: str) -> str:
    return f"aiops:chat:{session_id}:messages"


async def get_messages(session_id: str) -> list[dict]:
    """获取 session 的所有消息"""
    client = await _get_redis()
    if client is None:
        return []
    try:
        rows = await client.lrange(_messages_key(session_id), 0, -1) # Redis LIST 命令：取全部元素
        result = []
        for row in rows:
            if row:  # 跳过空行
                data = json.loads(row)
                result.append(data)
        return result
    except Exception as e:
        print(f"[chat-memory] 读取消息失败: {e}")
        return []


async def append_message(session_id: str, *, role: str, content: str):
    """追加一条消息"""
    client = await _get_redis()
    if client is None:
        return
    if role not in ("user", "assistant"):
        return
    payload = {"role": role, "content": content[:4000], "ts": _now_iso()} # 截断，防止消息太长 # 时间戳
    try:
        key = _messages_key(session_id)
        await client.rpush(key, json.dumps(payload, ensure_ascii=False))
        await client.ltrim(key, -settings.chat_max_messages, -1)
        await client.expire(key, settings.chat_memory_ttl_sec)
    except Exception as e:
        print(f"[chat-memory] 写入消息失败: {e}")


async def clear_session(session_id: str):
    """清空 session"""
    client = await _get_redis()
    if client is None:
        return
    try:
        await client.delete(_messages_key(session_id))
    except Exception as e:
        print(f"[chat-memory] 清空失败: {e}")


# ─── 诊断报告操作 ────────────────────────────────────

_DIAGNOSIS_REPORTS_KEY = "aiops:diagnosis:reports"
_DIAGNOSIS_REPORTS_MAX = 5


async def append_diagnosis_report(report: str, *, session_id: str = ""):
    """诊断报告写 Redis (跨 session 共享)"""
    if not report.strip():
        return
    client = await _get_redis()
    if client is None:
        return
    payload = {
        "ts": _now_iso(),
        "session_id": session_id,
        "report": report[:4000],
    }
    try:
        await client.lpush(_DIAGNOSIS_REPORTS_KEY, json.dumps(payload, ensure_ascii=False)) #	往 LIST 左边推入（头部插入）
        await client.ltrim(_DIAGNOSIS_REPORTS_KEY, 0, _DIAGNOSIS_REPORTS_MAX - 1) #消减记录，保留最新的几份
        await client.expire(_DIAGNOSIS_REPORTS_KEY, settings.chat_memory_ttl_sec) #过期
    except Exception as e:
        print(f"[chat-memory] 诊断报告写入失败: {e}")


async def get_recent_diagnosis_reports(limit: int = 3) -> list[dict]:
    """获取最近 N 份诊断报告"""
    client = await _get_redis()
    if client is None:
        return []
    try:
        rows = await client.lrange(_DIAGNOSIS_REPORTS_KEY, 0, limit - 1)
        out = []
        for row in rows:
            try:
                item = json.loads(row)
                if isinstance(item, dict) and item.get("report"):
                    out.append(item)
            except Exception:
                continue
        return out
    except Exception as e:
        print(f"[chat-memory] 诊断报告读取失败: {e}")
        return []
