"""
限流器模块

提供：
- 令牌桶算法
- 多维度限流（全局 + 按工具 + 按用户）
- 滑动窗口统计
"""
import asyncio
import logging
import time
from typing import Dict, Optional
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """限流配置"""
    global_rate: int = 1000        # 全局 QPS
    global_capacity: int = 1000    # 全局容量
    tool_rate: int = 100           # 单工具 QPS
    tool_capacity: int = 100       # 单工具容量
    user_rate: int = 50            # 单用户 QPS
    user_capacity: int = 50        # 单用户容量
    window_size: float = 1.0       # 窗口大小（秒）


@dataclass
class RateLimitStats:
    """限流统计"""
    total_requests: int = 0
    allowed_requests: int = 0
    rejected_requests: int = 0
    wait_time_ms: float = 0.0


class TokenBucket:
    """
    令牌桶实现
    
    算法：
    - 每次请求消耗 1 个令牌
    - 令牌以固定速率补充
    - 桶满时新令牌被丢弃
    """
    
    def __init__(self, rate: float, capacity: int):
        self.rate = rate          # 每秒生成的令牌数
        self.capacity = capacity  # 桶容量
        self._tokens = float(capacity)
        self._last_update = time.time()
        self._lock = asyncio.Lock()
    
    async def _refill(self):
        """补充令牌"""
        now = time.time()
        elapsed = now - self._last_update
        
        # 计算应该补充的令牌数
        new_tokens = elapsed * self.rate
        self._tokens = min(self.capacity, self._tokens + new_tokens)
        self._last_update = now
    
    async def consume(self, tokens: int = 1, wait: bool = True) -> bool:
        """
        消费令牌
        
        Args:
            tokens: 要消费的令牌数
            wait: 是否等待（如果为 False，则立即返回）
        
        Returns:
            是否成功消费
        """
        async with self._lock:
            await self._refill()
            
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            
            if not wait:
                return False
            
            # 计算需要等待的时间
            needed = tokens - self._tokens
            wait_time = needed / self.rate
            
            # 等待令牌生成
            await asyncio.sleep(wait_time)
            
            self._tokens = 0
            return True
    
    async def get_available_tokens(self) -> float:
        """获取可用令牌数"""
        async with self._lock:
            await self._refill()
            return self._tokens


class SlidingWindowCounter:
    """
    滑动窗口计数器
    
    用于精确的 QPS 统计
    """
    
    def __init__(self, window_size: float = 1.0):
        self.window_size = window_size
        self._requests: Dict[str, list] = defaultdict(list)  # key -> [timestamp, ...]
        self._lock = asyncio.Lock()
    
    async def record(self, key: str) -> int:
        """记录请求，返回当前窗口内的请求数"""
        async with self._lock:
            now = time.time()
            cutoff = now - self.window_size
            
            # 清理过期的请求记录
            if key in self._requests:
                self._requests[key] = [
                    t for t in self._requests[key]
                    if t > cutoff
                ]
            
            # 记录新请求
            self._requests[key].append(now)
            
            return len(self._requests[key])
    
    async def get_count(self, key: str) -> int:
        """获取当前窗口内的请求数"""
        async with self._lock:
            now = time.time()
            cutoff = now - self.window_size
            
            if key not in self._requests:
                return 0
            
            return len([
                t for t in self._requests[key]
                if t > cutoff
            ])


class RateLimiter:
    """
    多维度限流器
    
    维度：
    - 全局限流
    - 按工具限流
    - 按用户/租户限流
    """
    
    _instance: Optional['RateLimiter'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.config = RateLimitConfig()
        
        # 全局限流器
        self._global_bucket = TokenBucket(
            self.config.global_rate,
            self.config.global_capacity
        )
        
        # 滑动窗口（用于精确统计）
        self._sliding_window = SlidingWindowCounter(self.config.window_size)
        
        # 按工具的限流器
        self._tool_buckets: Dict[str, TokenBucket] = {}
        self._tool_buckets_lock = asyncio.Lock()
        
        # 按用户的限流器
        self._user_buckets: Dict[str, TokenBucket] = {}
        self._user_buckets_lock = asyncio.Lock()
        
        # 统计
        self._stats = RateLimitStats()
        self._stats_lock = asyncio.Lock()
        
        self._initialized = True
        logger.info(f"RateLimiter initialized: global_rate={self.config.global_rate}")
    
    async def _get_tool_bucket(self, tool_name: str) -> TokenBucket:
        """获取工具限流器"""
        async with self._tool_buckets_lock:
            if tool_name not in self._tool_buckets:
                self._tool_buckets[tool_name] = TokenBucket(
                    self.config.tool_rate,
                    self.config.tool_capacity
                )
            return self._tool_buckets[tool_name]
    
    async def _get_user_bucket(self, user_id: str) -> TokenBucket:
        """获取用户限流器"""
        async with self._user_buckets_lock:
            if user_id not in self._user_buckets:
                self._user_buckets[user_id] = TokenBucket(
                    self.config.user_rate,
                    self.config.user_capacity
                )
            return self._user_buckets[user_id]
    
    async def check_limit(
        self,
        tool_name: Optional[str] = None,
        user_id: Optional[str] = None,
        tokens: int = 1
    ) -> tuple[bool, float]:
        """
        检查限流
        
        Args:
            tool_name: 工具名称
            user_id: 用户 ID
            tokens: 要消费的令牌数
        
        Returns:
            (是否允许, 预估等待时间 ms)
        """
        async with self._stats_lock:
            self._stats.total_requests += 1
        
        wait_time_ms = 0.0
        
        # 1. 全局限流
        if not await self._global_bucket.consume(tokens, wait=False):
            async with self._stats_lock:
                self._stats.rejected_requests += 1
            return False, 0.0
        
        # 2. 工具维度限流
        if tool_name:
            tool_bucket = await self._get_tool_bucket(tool_name)
            if not await tool_bucket.consume(tokens, wait=False):
                async with self._stats_lock:
                    self._stats.rejected_requests += 1
                return False, 0.0
        
        # 3. 用户维度限流
        if user_id:
            user_bucket = await self._get_user_bucket(user_id)
            if not await user_bucket.consume(tokens, wait=False):
                async with self._stats_lock:
                    self._stats.rejected_requests += 1
                return False, 0.0
        
        # 全部通过
        async with self._stats_lock:
            self._stats.allowed_requests += 1
        
        return True, wait_time_ms
    
    async def acquire(
        self,
        tool_name: Optional[str] = None,
        user_id: Optional[str] = None,
        tokens: int = 1,
        timeout: float = 30.0
    ) -> bool:
        """
        获取限流许可（阻塞等待）
        
        Args:
            tool_name: 工具名称
            user_id: 用户 ID
            tokens: 要消费的令牌数
            timeout: 超时时间
        
        Returns:
            是否成功获取
        """
        start_time = time.time()
        
        # 1. 全局限流（等待）
        if not await self._global_bucket.consume(tokens, wait=True):
            return False
        
        # 2. 工具维度限流
        if tool_name:
            tool_bucket = await self._get_tool_bucket(tool_name)
            if not await tool_bucket.consume(tokens, wait=True):
                return False
        
        # 3. 用户维度限流
        if user_id:
            user_bucket = await self._get_user_bucket(user_id)
            if not await user_bucket.consume(tokens, wait=True):
                return False
        
        elapsed = (time.time() - start_time) * 1000
        async with self._stats_lock:
            self._stats.wait_time_ms += elapsed
        
        return True
    
    async def get_stats(self) -> dict:
        """获取统计信息"""
        async with self._stats_lock:
            stats = {
                "total_requests": self._stats.total_requests,
                "allowed_requests": self._stats.allowed_requests,
                "rejected_requests": self._stats.rejected_requests,
                "rejection_rate": (
                    self._stats.rejected_requests / self._stats.total_requests
                    if self._stats.total_requests > 0 else 0
                ),
                "avg_wait_time_ms": (
                    self._stats.wait_time_ms / self._stats.allowed_requests
                    if self._stats.allowed_requests > 0 else 0
                )
            }
        
        # 添加滑动窗口统计
        global_count = await self._sliding_window.get_count("global")
        stats["current_qps"] = global_count
        
        return stats
    
    async def get_tool_stats(self, tool_name: str) -> dict:
        """获取工具限流统计"""
        bucket = await self._get_tool_bucket(tool_name)
        return {
            "tool_name": tool_name,
            "available_tokens": await bucket.get_available_tokens(),
            "rate": self.config.tool_rate,
            "capacity": self.config.tool_capacity
        }
    
    async def reset(self):
        """重置所有限流器"""
        self._global_bucket = TokenBucket(
            self.config.global_rate,
            self.config.global_capacity
        )
        
        async with self._tool_buckets_lock:
            self._tool_buckets.clear()
        
        async with self._user_buckets_lock:
            self._user_buckets.clear()
        
        async with self._stats_lock:
            self._stats = RateLimitStats()
        
        logger.info("RateLimiter reset")


# 全局实例
rate_limiter = RateLimiter()