"""
HTTP 客户端连接池管理器

提供：
- 连接池管理
- 并发限制
- 自动健康检测
- 连接回收
"""
import asyncio
import logging
import time
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

import httpx
from httpx import AsyncClient, Timeout, Limits

from ..config import settings

logger = logging.getLogger(__name__)


class HTTPClientPool:
    """HTTP 连接池管理器"""
    
    _instance: Optional['HTTPClientPool'] = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # 连接池配置
        self._max_connections = 100
        self._max_keepalive = 20
        self._keepalive_expiry = 30.0
        
        # 并发限制
        self._semaphore = asyncio.Semaphore(self._max_connections)
        
        # 客户端实例
        self._client: Optional[AsyncClient] = None
        self._client_lock = asyncio.Lock()
        
        # 健康检测
        self._health_check_interval = 60  # 秒
        self._last_health_check = 0
        self._is_healthy = True
        
        # 统计
        self._total_requests = 0
        self._active_requests = 0
        self._failed_requests = 0
        
        self._initialized = True
        logger.info(
            f"HTTPClientPool initialized: max_connections={self._max_connections}, "
            f"max_keepalive={self._max_keepalive}"
        )
    
    async def _create_client(self) -> AsyncClient:
        """创建 HTTP 客户端"""
        return AsyncClient(
            timeout=Timeout(
                connect=settings.REDIS_CONNECT_TIMEOUT,
                read=settings.HTTP_CLIENT_TIMEOUT,
                write=settings.HTTP_CLIENT_TIMEOUT,
                pool=settings.HTTP_CLIENT_TIMEOUT
            ),
            limits=Limits(
                max_keepalive_connections=self._max_keepalive,
                max_connections=self._max_connections,
                keepalive_expiry=self._keepalive_expiry
            ),
            http2=True,  # 启用 HTTP/2
            follow_redirects=True,
            max_redirects=5
        )
    
    async def get_client(self) -> AsyncClient:
        """获取 HTTP 客户端（懒加载）"""
        if self._client is None:
            async with self._client_lock:
                if self._client is None:
                    self._client = await self._create_client()
                    logger.info("HTTP client created")
        return self._client
    
    @asynccontextmanager
    async def acquire(self, timeout: float = 30.0):
        """
        获取带并发限制的 HTTP 客户端
        
        Usage:
            async with http_pool.acquire() as client:
                response = await client.get(url)
        """
        # 尝试获取信号量
        try:
            await asyncio.wait_for(self._semaphore.acquire(), timeout=timeout)
        except asyncio.TimeoutError:
            self._failed_requests += 1
            raise TimeoutError(f"Failed to acquire HTTP connection within {timeout}s")
        
        self._active_requests += 1
        self._total_requests += 1
        
        try:
            client = await self.get_client()
            yield client
        except Exception as e:
            self._failed_requests += 1
            raise
        finally:
            self._active_requests -= 1
            self._semaphore.release()
    
    async def health_check(self) -> bool:
        """健康检测"""
        now = time.time()
        if now - self._last_health_check < self._health_check_interval:
            return self._is_healthy
        
        self._last_health_check = now
        
        try:
            async with self.acquire(timeout=5.0) as client:
                # 尝试一个简单的 HEAD 请求
                await client.head("https://httpbin.org/status/200", timeout=5.0)
            self._is_healthy = True
            logger.debug("HTTP pool health check passed")
            return True
        except Exception as e:
            self._is_healthy = False
            logger.warning(f"HTTP pool health check failed: {e}")
            return False
    
    async def close(self):
        """关闭连接池"""
        async with self._client_lock:
            if self._client:
                await self._client.aclose()
                self._client = None
                logger.info("HTTP client closed")
    
    async def reset(self):
        """重置连接池（强制重建）"""
        await self.close()
        async with self._client_lock:
            self._client = await self._create_client()
        logger.info("HTTP client reset")
    
    @property
    def stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_requests": self._total_requests,
            "active_requests": self._active_requests,
            "failed_requests": self._failed_requests,
            "is_healthy": self._is_healthy,
            "max_connections": self._max_connections,
            "available_slots": self._semaphore._value
        }


# 全局实例
http_client_pool = HTTPClientPool()


# 兼容旧接口
async def get_http_client() -> AsyncClient:
    """获取 HTTP 客户端（兼容旧接口）"""
    return await http_client_pool.get_client()


async def close_http_client():
    """关闭 HTTP 客户端（兼容旧接口）"""
    await http_client_pool.close()