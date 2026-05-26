"""MCP 客户端管理 — 连接 MCP 服务器，发现工具、调用工具"""

from typing import Any
from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client

# MCP 服务器配置
MCP_SERVERS = {
    "system": {
        "url": "http://127.0.0.1:9001",
        "description": "系统诊断 (CPU/内存/磁盘/进程)"
    },
    "network": {
            "url": "http://127.0.0.1:9002",
            "description": "网络诊断 (ping/HTTP/DNS/端口)"
        },
    "docker": {
        "url": "http://127.0.0.1:9003",
        "description": "Docker 容器诊断 (ps/stats/logs/inspect)"
    },
}


class MCPClient:
    """单个 MCP 服务器的客户端"""

    def __init__(self, name: str, base_url: str):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self._session: ClientSession | None = None
        self._ctx = None

    async def connect(self):
        """连接到 MCP 服务器（SSE 方式）"""
        sse_url = f"{self.base_url}/sse"
        self._ctx = sse_client(sse_url)
        transport = await self._ctx.__aenter__()
        read, write = transport
        self._session = await ClientSession(read, write).__aenter__()
        await self._session.initialize()

    async def list_tools(self) -> list[dict]:
        """获取该服务器上的所有工具列表"""
        if not self._session:
            await self.connect()
        tools = await self._session.list_tools()
        result = []
        for tool in tools.tools:
            result.append({
                "name": tool.name,
                "description": tool.description or "",
                "inputSchema": tool.inputSchema or {"type": "object", "properties": {}}
            })
        return result

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """调用该服务器上的一个工具"""
        if not self._session:
            await self.connect()
        result = await self._session.call_tool(tool_name, arguments)
        # 提取文本内容
        texts = []
        for content in result.content:
            if hasattr(content, "text"):
                texts.append(content.text)
        return "\n".join(texts)

    async def close(self):
        """关闭连接"""
        if self._session:
            await self._session.__aexit__(None, None, None)
        if self._ctx:
            await self._ctx.__aexit__(None, None, None)


# 全局缓存：server_name → MCPClient 实例
_clients: dict[str, MCPClient] = {}


async def get_client(server_name: str) -> MCPClient:
    """获取（或创建）指定服务器的客户端"""
    if server_name not in _clients:
        config = MCP_SERVERS.get(server_name)
        if not config:
            raise ValueError(f"未知的 MCP 服务器: {server_name}")
        client = MCPClient(server_name, config["url"])
        await client.connect()
        _clients[server_name] = client
    return _clients[server_name]


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