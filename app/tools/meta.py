"""工具路由器"""
from app.tools.system_tool import get_cpu_usage, cpu_tool_definition, get_memory_usage, memory_tool_definition, \
    get_disk_usage, disk_tool_definition, get_top_processes, top_processes_tool_definition
from app.tools.time_tool import get_current_time, time_tool_definition
from app.tools.weather_tool import get_weather, weather_tool_definition

# 工具注册表：名字 → {函数, 定义}
tool_registry = {
    "get_current_time": {
        "function": get_current_time,
        "definition": time_tool_definition
    },
    "get_weather": {
        "function": get_weather,
        "definition": weather_tool_definition
    },
    "get_cpu_usage": {
        "function": get_cpu_usage,
        "definition": cpu_tool_definition
    },
    "get_memory_usage": {
        "function": get_memory_usage,
        "definition": memory_tool_definition
    },
    "get_disk_usage": {
        "function": get_disk_usage,
        "definition": disk_tool_definition
    },
    "get_top_processes": {
        "function": get_top_processes,
        "definition": top_processes_tool_definition
    },
}
