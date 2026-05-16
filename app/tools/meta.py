"""工具路由器"""


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
    }
}
