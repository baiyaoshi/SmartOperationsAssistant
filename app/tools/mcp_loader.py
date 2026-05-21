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