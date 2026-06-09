"""
API2MCP Standalone Subsystem - Main Entry
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from config import settings
from api import router as api2mcp_router
from mcp_server import router as mcp_server_router


# Log configuration
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management"""
    # Startup initialization
    logging.info(f"API2MCP service starting on port: {settings.BACKEND_PORT}")
    
    yield
    
    # Shutdown cleanup
    logging.info("API2MCP service shutting down")


# Create FastAPI application
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description="""
API2MCP - REST API to MCP Bridge

## Features

Convert traditional REST APIs into MCP (Model Context Protocol) tools, enabling AI agents to call these APIs.

### Frontend Routes (frontrouter)

- `/frontrouter/` - Home/Project List
- `/frontrouter/create` - Create New Project
- `/frontrouter/:id` - Edit/View Project Detail

### Server API (serverapi/apimng)

- `GET  /serverapi/apimng/server-info` - Server Info
- `GET  /serverapi/apimng/projects` - Project List
- `POST /serverapi/apimng/projects` - Create Project
- `GET  /serverapi/apimng/projects/{id}` - Project Detail
- `PUT  /serverapi/apimng/projects/{id}` - Update Project
- `DELETE /serverapi/apimng/projects/{id}` - Delete Project
- `GET  /serverapi/apimng/projects/{id}/parameters` - Parameter List
- `GET  /serverapi/apimng/projects/{id}/mcp-definition` - MCP Definition Preview

### MCP Server Endpoints (mcpapi) - For AI Agent Calls

- `GET/POST /mcpapi` - MCP JSON-RPC 2.0 Root Endpoint (Streamable HTTP)
- `GET/POST /mcpapi/{identifier}` - Isolated Endpoint by Project Identifier

### Other

- `GET /health` - Health Check
- `GET /apidocs` - Swagger Documentation
- `GET /redoc` - ReDoc Documentation
""",
    lifespan=lifespan,
    docs_url="/apidocs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes (API routes must come before static files)
app.include_router(api2mcp_router, prefix="")  # api.py already includes /serverapi prefix
app.include_router(mcp_server_router, prefix="")  # mcp_server.py already includes /mcpapi prefix

# Health check
@app.get("/health", tags=["system"])
async def health_check():
    return {"status": "healthy", "service": "api2mcp-standalone"}


# ── Frontend Static File Service and Route Support ──

# Frontend build directory
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"

# Mount frontend static files only if dist directory exists
if (frontend_dist / "assets").exists():
    app.mount("/frontrouter/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

# ── Vue Router History Mode Support ──

# Note: catch_all must be registered after all other routes, otherwise it intercepts API requests
from fastapi.routing import APIRoute

async def catch_all(full_path: str):
    """
    Handle all unmatched routes, return frontend index.html
    Supports Vue Router history mode
    """
    # Handle static asset requests
    if full_path.startswith("frontrouter/assets/"):
        asset_path = frontend_dist / full_path.replace("frontrouter/", "")
        if asset_path.exists():
            return FileResponse(asset_path)
        return {"error": "Not found"}, 404
    
    # Return index.html for frontend routing
    index_html = frontend_dist / "index.html"
    if index_html.exists():
        return FileResponse(index_html)
    
    return {"error": "Not found"}, 404

# Register catch_all route only if frontend dist exists
if frontend_dist.exists():
    app.router.routes.append(APIRoute("/{full_path:path}", endpoint=catch_all, methods=["GET"]))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=True
    )