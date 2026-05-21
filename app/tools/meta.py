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