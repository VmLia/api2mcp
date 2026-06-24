"""
Redis 连接工具 - 用于状态管理、缓存、分布式锁
"""
import asyncio
import json
import logging
from typing import Any, Optional, Dict

import redis.asyncio as redis
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff

from ..config import settings

logger = logging.getLogger(__name__)

# Redis 连接池
_redis_client: Optional[redis.Redis] = None
_redis_lock = asyncio.Lock()
_redis_retry = Retry(ExponentialBackoff(), retries=3)


async def get_redis_client() -> redis.Redis:
    """获取 Redis 客户端实例（单例，支持自动重连）"""
    global _redis_client

    if _redis_client is None:
        async with _redis_lock:
            if _redis_client is None:
                _redis_client = redis.from_url(
                    settings.redis_url,
                    decode_responses=True,
                    socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
                    socket_connect_timeout=settings.REDIS_CONNECT_TIMEOUT,
                    retry=_redis_retry,
                    retry_on_timeout=True,
                    retry_on_error=[ConnectionError, TimeoutError, redis.ConnectionError],
                )
                # 测试连接
                try:
                    await _redis_client.ping()
                except Exception as e:
                    _redis_client = None
                    if settings.REDIS_OPTIONAL:
                        logger.warning(f"Redis connection failed (optional): {e}")
                        return None
                    raise ConnectionError(f"Failed to connect to Redis: {e}")

    # 健康检查：如果连接已断开，尝试重连
    try:
        await _redis_client.ping()
    except Exception as e:
        logger.warning(f"Redis connection lost, attempting to reconnect: {e}")
        async with _redis_lock:
            try:
                await _redis_client.close()
            except Exception:
                pass
            _redis_client = None

            try:
                _redis_client = redis.from_url(
                    settings.redis_url,
                    decode_responses=True,
                    socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
                    socket_connect_timeout=settings.REDIS_CONNECT_TIMEOUT,
                    retry=_redis_retry,
                    retry_on_timeout=True,
                    retry_on_error=[ConnectionError, TimeoutError, redis.ConnectionError],
                )
                await _redis_client.ping()
                logger.info("Redis reconnection successful")
            except Exception as reconnect_err:
                _redis_client = None
                if settings.REDIS_OPTIONAL:
                    logger.warning(f"Redis reconnection failed (optional): {reconnect_err}")
                    return None
                raise ConnectionError(f"Failed to reconnect to Redis: {reconnect_err}")

    return _redis_client


async def close_redis_client():
    """关闭 Redis 客户端连接"""
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None


class RedisCache:
    """Redis 缓存工具类"""

    def __init__(self, client: redis.Redis = None):
        self._client = client

    async def client(self) -> redis.Redis:
        """获取 Redis 客户端"""
        return self._client or await get_redis_client()

    async def get(self, key: str) -> Optional[str]:
        """获取缓存值"""
        return await (await self.client()).get(key)

    async def get_json(self, key: str) -> Optional[Dict]:
        """获取 JSON 格式的缓存值"""
        value = await self.get(key)
        if value:
            return json.loads(value)
        return None

    async def set(self, key: str, value: str, ttl: int = None):
        """设置缓存值"""
        ttl = ttl or settings.STATE_CACHE_TTL
        await (await self.client()).set(key, value, ex=ttl)

    async def set_json(self, key: str, value: Dict, ttl: int = None):
        """设置 JSON 格式的缓存值"""
        await self.set(key, json.dumps(value), ttl)

    async def delete(self, key: str):
        """删除缓存"""
        await (await self.client()).delete(key)

    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        return await (await self.client()).exists(key) > 0

    async def increment(self, key: str, amount: int = 1) -> int:
        """原子性递增"""
        return await (await self.client()).incr(key, amount)

    async def decrement(self, key: str, amount: int = 1) -> int:
        """原子性递减"""
        return await (await self.client()).decr(key, amount)


class RedisLock:
    """Redis 分布式锁"""

    def __init__(self, client: redis.Redis = None):
        self._client = client

    async def client(self) -> redis.Redis:
        """获取 Redis 客户端"""
        return self._client or await get_redis_client()

    async def acquire(
        self,
        key: str,
        timeout: int = 30,
        blocking_timeout: int = 10
    ) -> bool:
        """
        获取分布式锁
        :param key: 锁的键名
        :param timeout: 锁过期时间（秒）
        :param blocking_timeout: 等待获取锁的超时时间（秒）
        :return: 是否成功获取锁
        """
        lock_key = f"lock:{key}"
        end_time = asyncio.get_event_loop().time() + blocking_timeout

        while asyncio.get_event_loop().time() < end_time:
            # 使用 SET NX（仅在键不存在时设置）
            result = await (await self.client()).set(
                lock_key,
                "1",
                ex=timeout,
                nx=True
            )
            if result:
                return True
            await asyncio.sleep(0.1)

        return False

    async def release(self, key: str):
        """释放分布式锁"""
        lock_key = f"lock:{key}"
        await (await self.client()).delete(lock_key)


# 全局缓存实例
cache = RedisCache()

# 全局锁实例
distributed_lock = RedisLock()
