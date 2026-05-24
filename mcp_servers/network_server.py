"""网络诊断mcp工具"""
import subprocess
import time
import socket

import httpx
from fastmcp import FastMCP
from urllib.parse import urlparse
"""
第1层 DNS 解析  →  dns_lookup  (域名能不能解析出IP)
第2层 网络连通性 →  ping_host   (主机能不能通)
第3层 端口可达性 →  check_port  (端口有没有监听)
第4层 应用层     →  http_check  (HTTP 返回什么状态码)
"""


# 创建 MCP 服务器
mcp = FastMCP("network-server")


"""
如果 Agent 不限制内网扫描，攻击者可以通过输入这样的 prompt 来利用你的 Agent：
"帮我检查一下 10.0.0.1 到 10.0.0.255 的所有端口"
Agent 就会傻乎乎地去扫你们公司的内网，这相当于让 Agent 变成了一个攻击工具。如果不加限制，甚至可能被用来扫描 127.0.0.1:6379 探测 Redis 端口之类的内部服务。
"""

# 主机黑名单 (避免扫描内网)
_HOST_BLOCKLIST_PREFIXES = (
    "10.",       # 内网 A
    "192.168.",  # 内网 C
    "172.",      # 部分内网 B
    "127.",      # 本地回环
    "0.",
    "169.254.",  # 链路本地
)

def _is_blocked_ip(host: str) -> bool:
    """仅当 host 已经是 IP 格式时才拦"""
    parts = host.split(".")
    if len(parts) == 4 and all(p.isdigit() for p in parts):
        for prefix in _HOST_BLOCKLIST_PREFIXES:
            if host.startswith(prefix):
                return True
    return False

@mcp.tool()
def dns_lookup(domain: str) -> str:
    """解析域名为 IP 地址 (A 记录)，用于排查 DNS 故障"""
    # 1. 参数校验
    domain = (domain or "").strip()
    if not domain:
        return "[拒绝] domain 不能为空"

    # 2. DNS 解析
    try:
        start = time.time()
        #dns解析函数
        infos = socket.getaddrinfo(domain, None, family=socket.AF_INET)
        elapsed_ms = int((time.time() - start) * 1000)
        ips = sorted({info[4][0] for info in infos})
        return f"## DNS Lookup {domain}\n- IPs: {ips}\n- elapsed: {elapsed_ms} ms"
    except socket.gaierror as e:
        return f"[失败] {domain} DNS 解析失败: {e}"


@mcp.tool()
def ping_host(host: str, count: int = 4) -> str:
    """ping 一个公网主机, 检测连通性/丢包率/延迟. host 可以是域名或公网 IP. count 默认 4 次, 上限 10 次."""
    # 1.参数校验
    host = (host or "").strip()
    if not host:
        return "[拒绝] host 不能为空"
    count = max(1, min(int(count or 4), 10))
    if _is_blocked_ip(host):
        return f"[拒绝] {host} 是内网/回环地址, 不允许 ping_host"

    # 2.调用系统 ping
    try:
        process = subprocess.run(
            ["ping", "-n", str(count), "-w", "2000", host],
            capture_output=True,
            text=True,
            timeout=count * 3 + 5,
            encoding="gbk",
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        return f"[失败] ping {host} 超时 (> {count * 3 + 5}s)"
    except Exception as e:
        return f"[失败] ping 异常: {e}"

    # 3.返回结果
    output = (process.stdout or "") + (process.stderr or "")
    return f"## ping {host} (count={count})\n\n```\n{output.strip()[:2000]}\n```"


@mcp.tool()
def check_port(host: str, port: int, timeout_sec: float = 3.0) -> str:
    """检测指定 host 的 TCP 端口是否可达。用于排查'服务起来了吗/防火墙挡了吗'"""
    # 1. 参数校验
    host = (host or "").strip()
    if _is_blocked_ip(host):
        return f"[拒绝] {host} 是内网/回环地址, 不允许扫描"
    if not host or not port:
        return "[拒绝] host 和 port 都不能为空"
    port = int(port)
    if not (1 <= port <= 65535):
        return f"[拒绝] port 必须在 1-65535, 收到: {port}"
    timeout_sec = max(0.5, min(float(timeout_sec or 3.0), 10.0))

    # 2. 尝试 TCP 连接
    try:
        start = time.time()
        with socket.create_connection((host, port), timeout=timeout_sec):
            elapsed_ms = int((time.time() - start) * 1000)
            return f"## Port {host}:{port}\n- 可达 (TCP 连接成功)\n- elapsed: {elapsed_ms} ms"
    except socket.timeout:
        return f"## Port {host}:{port}\n- **不可达** (超时 {timeout_sec}s, 可能被防火墙挡)"
    except ConnectionRefusedError:
        return f"## Port {host}:{port}\n- **不可达** (连接被拒绝, 端口未监听)"
    except socket.gaierror as e:
        return f"[失败] {host} DNS 解析失败: {e}"
    except Exception as e:
        return f"[失败] 端口检测异常: {e}"


@mcp.tool()
def http_check(url: str, timeout_sec: float = 10.0) -> str:
    """对一个 HTTP/HTTPS URL 发起 GET 请求, 返回状态码/响应时间/响应头摘要。用于检查网站/接口可用性。"""
    # 1.参数校验
    url = (url or "").strip()
    if not url:
        return "[拒绝] url 不能为空"
    if not url.startswith(("http://", "https://")):
        url = "http://" + url

    parsed = urlparse(url)
    host = parsed.hostname or ""
    if _is_blocked_ip(host):
        return f"[拒绝] {host} 是内网/回环地址, 不允许 http_check"
    timeout_sec = max(1.0, min(float(timeout_sec or 10.0), 30.0))

    #2. 发起 HTTP 请求
    start = time.time()
    try:
        with httpx.Client(timeout=timeout_sec, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": "OnCall-Agent/1.0"})
        elapsed_ms = int((time.time() - start) * 1000)
    except httpx.TimeoutException:
        return f"[失败] {url} 请求超时 (>{timeout_sec}s)"
    except httpx.ConnectError as e:
        return f"[失败] {url} 连接失败: {e}"
    except Exception as e:
        return f"[失败] {url} 请求异常: {e}"

    # 3. 提取关键信息返回
    return (
        f"## HTTP Check {url}\n"
        f"- status: {resp.status_code}\n"
        f"- elapsed: {elapsed_ms} ms\n"
        f"- final_url: {resp.url}\n"
    )

if __name__ == "__main__":
    mcp.run("sse", port=9002)