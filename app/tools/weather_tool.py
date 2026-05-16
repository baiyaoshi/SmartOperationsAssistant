def get_weather(city: str) -> str:
    """模拟获取指定城市的天气"""
    weather_data = {
        "北京": "晴，25°C，空气质量：良",
        "上海": "多云，28°C，空气质量：优",
        "广州": "雷阵雨，32°C，空气质量：良",
        "深圳": "阴天，30°C，空气质量：优",
        #其他城市返回默认
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
            "required": ["city"]  #city 是必需的
        }
    }
}