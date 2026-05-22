from contextlib import asynccontextmanager
from fastapi import FastAPI
import uvicorn
from starlette.staticfiles import StaticFiles
from pathlib import Path

from app.tools.meta import get_all_tools
from app.tools.mcp_loader import discover_and_register_mcp_tools
from app.core.mcp_client import close_all
from app.api.v1 import health, aiops  # 引入路由


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[启动] 发现 MCP 工具...")
    await discover_and_register_mcp_tools()
    print(f"[启动] MCP 工具加载完成，共 {len(get_all_tools())} 个工具")
    yield
    print("[关闭] 断开 MCP 连接...")
    await close_all()

app = FastAPI(title="Smart Operations Assistant", lifespan=lifespan)


# 注册路由
app.include_router(health.router)
app.include_router(aiops.router)

# 挂载前端
BASE_DIR = Path(__file__).resolve().parent.parent
app.mount("/frontend", StaticFiles(directory=str(BASE_DIR / "frontend"), html=True), name="frontend")


if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=9900)