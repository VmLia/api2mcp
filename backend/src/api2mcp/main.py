"""
API2MCP 后端服务主入口

优化版本：
- 添加 Prometheus 指标端点
- 优化生命周期管理
- 添加系统状态端点
"""
import logging
import uuid
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response, JSONResponse
from fastapi.routing import APIRoute

from .config import settings
from .api_registry.routers import tool_router, smart_parser_router
from .mcp_gateway.routers import mcp_router
from .mcp_gateway.state import server_state_manager
from .core import (
    LoggingMiddleware,
    get_redis_client,
    close_redis_client,
    http_client_pool,
    circuit_breaker_manager,
    rate_limiter,
    metrics_collector,
    get_metrics_text
)

# 添加项目根目录到 Python 路径，确保能导入 init 模块
_project_root = Path(__file__).resolve().parent.parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# 数据库表结构初始化模块
from init.init_db import init_tables


# 日志配置
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
)

# 服务实例 ID（使用主机名或随机生成）
SERVER_INSTANCE_ID = str(uuid.uuid4())[:8]
SERVICE_START_TIME = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化
    logging.info(f"API2MCP service starting on port: {settings.BACKEND_PORT}")
    logging.info(f"Server instance ID: {SERVER_INSTANCE_ID}")

    # 设置指标收集器启动时间
    metrics_collector.set_start_time()

    # 数据库表结构初始化（在服务启动时执行）
    try:
        logging.info(f"Database table initialization starting (drop_existing={settings.API2MCP_DB_DEL})")
        await init_tables(drop_existing=settings.API2MCP_DB_DEL)
        logging.info("Database table initialization completed")
    except Exception as e:
        logging.error(f"Database table initialization failed: {e}")
        raise

    # 初始化 Redis 连接（可选）
    try:
        redis_client = await get_redis_client()
        if redis_client:
            logging.info("Redis connection established")
        else:
            logging.warning("Redis connection failed (optional), service will continue without Redis")
    except Exception as e:
        if settings.REDIS_OPTIONAL:
            logging.warning(f"Redis connection failed (optional): {e}, service will continue without Redis")
        else:
            logging.error(f"Failed to connect to Redis: {e}")
            raise

    # 注册服务实例
    try:
        await server_state_manager.register_server(
            server_id=SERVER_INSTANCE_ID,
            name=f"api2mcp-{SERVER_INSTANCE_ID}"
        )
        logging.info("Server registered to state manager")
    except Exception as e:
        logging.warning(f"Failed to register server: {e}")

    yield

    # 关闭时清理
    logging.info("API2MCP service shutting down")

    # 注销服务实例
    try:
        await server_state_manager.unregister_server(SERVER_INSTANCE_ID)
        logging.info("Server unregistered from state manager")
    except Exception as e:
        logging.warning(f"Failed to unregister server: {e}")

    # 关闭 HTTP 连接池
    try:
        await http_client_pool.close()
        logging.info("HTTP client pool closed")
    except Exception as e:
        logging.warning(f"Failed to close HTTP client: {e}")

    # 关闭 Redis 连接
    try:
        await close_redis_client()
        logging.info("Redis connection closed")
    except Exception as e:
        logging.warning(f"Failed to close Redis connection: {e}")


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
app.include_router(smart_parser_router)  # smart_parser_router 已经包含 /serverapi prefix
app.include_router(mcp_router)  # mcp_router 已经包含 /mcpapi prefix


# ── 系统端点 ──

@app.get("/health", tags=["system"])
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "service": "api2mcp",
        "instance_id": SERVER_INSTANCE_ID,
        "uptime_seconds": int(time.time() - SERVICE_START_TIME)
    }


@app.get("/server/status", tags=["system"])
async def get_server_status():
    """获取服务状态信息"""
    servers = await server_state_manager.get_all_servers()
    return {
        "instance_id": SERVER_INSTANCE_ID,
        "uptime_seconds": int(time.time() - SERVICE_START_TIME),
        "servers": [server.to_dict() for server in servers]
    }


@app.get("/server/metrics", tags=["system"])
async def get_system_metrics():
    """获取系统指标（聚合信息）"""
    # HTTP 客户端统计
    http_stats = http_client_pool.stats
    
    # 熔断器统计
    circuit_breakers = await circuit_breaker_manager.get_all_stats()
    
    # 限流器统计
    rate_limit_stats = await rate_limiter.get_stats()
    
    return {
        "http_client": http_stats,
        "circuit_breakers": circuit_breakers,
        "rate_limiter": rate_limit_stats,
        "uptime_seconds": int(time.time() - SERVICE_START_TIME)
    }


@app.get("/metrics", tags=["system"])
async def prometheus_metrics():
    """Prometheus 指标端点"""
    return Response(
        content=get_metrics_text(),
        media_type="text/plain; version=0.0.4; charset=utf-8"
    )


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