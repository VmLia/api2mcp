"""
API 注册管理 - HTTP 路由
"""
from .tool_router import router as tool_router
from .smart_parser_router import router as smart_parser_router

__all__ = ["tool_router", "smart_parser_router"]
