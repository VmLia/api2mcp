"""
API2MCP 后端服务主入口
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.routing import APIRoute

from .config import settings
from .controller import tool_router, mcp_router
from .middleware.logging_middleware import LoggingMiddleware


# 日志配置
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化
    logging.info(f"API2MCP service starting on port: {settings.BACKEND_PORT}")

    yield

    # 关闭时清理
    logging.info("API2MCP service shutting down")


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.TITLE,
    version=settings.PROJECT_VERSION,
    description=settings.DESCRIPTION,
    lifespan=lifespan,
    docs_url="/apidocs",
    redoc_url="/redoc"
)

# 添加日志中间件
app.add_middleware(LoggingMiddleware)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由（API 路由必须在静态文件之前）
app.include_router(tool_router)  # tool_router 已经包含 /serverapi prefix
app.include_router(mcp_router)  # mcp_router 已经包含 /mcpapi prefix


# 健康检查
@app.get("/health", tags=["system"])
async def health_check():
    """健康检查端点"""
    return {"status": "healthy", "service": "api2mcp"}


# ── 前端静态文件服务和路由支持 ──

# 前端构建目录
frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"


async def catch_all(full_path: str):
    """
    处理所有未匹配的路由，返回前端 index.html
    支持 Vue Router history 模式
    """
    # 处理静态资源请求
    if full_path.startswith("frontrouter/assets/"):
        asset_path = frontend_dist / full_path.replace("frontrouter/", "")
        if asset_path.exists():
            return FileResponse(asset_path)
        return {"error": "Not found"}, 404

    # 返回前端 index.html
    index_html = frontend_dist / "index.html"
    if index_html.exists():
        return FileResponse(index_html)

    return {"error": "Not found"}, 404


# 仅当前端 dist 存在时注册路由
if frontend_dist.exists():
    # 挂载前端静态资源
    if (frontend_dist / "assets").exists():
        app.mount(
            "/frontrouter/assets",
            StaticFiles(directory=frontend_dist / "assets"),
            name="assets"
        )

    # 注册 catch_all 路由（必须在其他路由之后）
    app.router.routes.append(
        APIRoute("/{full_path:path}", endpoint=catch_all, methods=["GET"])
    )


# ── 开发模式入口 ──

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api2mcp.main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=True,
        access_log=settings.UVICORN_ACCESS_LOG
    )
