"""
日志中间件 - 记录请求和响应日志
"""
import logging
import time
import uuid
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from api2mcp.config import settings

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件"""

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        # 生成请求 ID
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id

        # 检查是否启用请求日志
        if settings.LOG_REQUEST_ENABLED:
            # 记录请求开始
            start_time = time.time()
            logger.info(
                f"[{request_id}] {request.method} {request.url.path} - Started",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "client": request.client.host if request.client else None,
                }
            )
        else:
            start_time = None

        # 处理请求
        try:
            response = await call_next(request)

            # 检查是否启用请求日志
            if settings.LOG_REQUEST_ENABLED and start_time:
                # 计算处理时间
                duration_ms = (time.time() - start_time) * 1000

                # 记录请求完成
                logger.info(
                    f"[{request_id}] {request.method} {request.url.path} - "
                    f"{response.status_code} ({duration_ms:.2f}ms)",
                    extra={
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                        "duration_ms": duration_ms,
                    }
                )

            # 添加请求 ID 到响应头
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            # 检查是否启用请求日志
            if settings.LOG_REQUEST_ENABLED and start_time:
                # 计算处理时间
                duration_ms = (time.time() - start_time) * 1000

                # 记录错误
                logger.error(
                    f"[{request_id}] {request.method} {request.url.path} - "
                    f"Error: {str(e)} ({duration_ms:.2f}ms)",
                    extra={
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "error": str(e),
                        "duration_ms": duration_ms,
                    }
                )
            raise


# 导出中间件实例
logging_middleware = LoggingMiddleware
