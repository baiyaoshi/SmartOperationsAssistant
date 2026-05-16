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