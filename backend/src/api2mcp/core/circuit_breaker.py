"""
熔断器模块

提供：
- 熔断状态管理（关闭/打开/半开）
- 失败计数
- 自动恢复
"""
import asyncio
import logging
import time
from enum import Enum
from typing import Callable, Any, Optional, Dict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """熔断器状态"""
    CLOSED = "closed"       # 正常：允许请求通过
    OPEN = "open"           # 熔断：拒绝请求
    HALF_OPEN = "half_open" # 半开：尝试恢复


@dataclass
class CircuitBreakerConfig:
    """熔断器配置"""
    failure_threshold: int = 5          # 连续失败次数达到此值则熔断
    success_threshold: int = 3          # 半开状态下连续成功次数达到此值则恢复
    recovery_timeout: int = 30          # 熔断后等待多少秒尝试恢复
    half_open_max_calls: int = 3        # 半开状态下允许的最大尝试次数
    timeout: float = 30.0               # 单次请求超时时间


@dataclass
class CircuitBreakerStats:
    """熔断器统计"""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    state_changes: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0


class CircuitOpenError(Exception):
    """熔断器打开异常"""
    pass


class CircuitBreaker:
    """
    熔断器实现
    
    状态转换:
    - CLOSED -> OPEN: 连续失败达到阈值
    - OPEN -> HALF_OPEN: 超过恢复超时
    - HALF_OPEN -> CLOSED: 连续成功达到阈值
    - HALF_OPEN -> OPEN: 半开状态下再次失败
    """
    
    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        
        self._state = CircuitState.CLOSED
        self._stats = CircuitBreakerStats()
        
        self._last_state_change_time = time.time()
        self._half_open_calls = 0
        
        self._lock = asyncio.Lock()
        
        logger.info(f"CircuitBreaker '{name}' initialized with config: {self.config}")
    
    @property
    def state(self) -> CircuitState:
        return self._state
    
    @property
    def stats(self) -> CircuitBreakerStats:
        return self._stats
    
    def _should_attempt_recovery(self) -> bool:
        """检查是否应该尝试恢复"""
        elapsed = time.time() - self._last_state_change_time
        return elapsed >= self.config.recovery_timeout
    
    async def _try_transition_to_half_open(self):
        """尝试转换到半开状态"""
        if self._state == CircuitState.OPEN and self._should_attempt_recovery():
            self._state = CircuitState.HALF_OPEN
            self._half_open_calls = 0
            self._last_state_change_time = time.time()
            self._stats.state_changes += 1
            logger.warning(f"CircuitBreaker '{self.name}' transitioned to HALF_OPEN")
    
    async def _try_transition_to_closed(self):
        """尝试转换到关闭状态"""
        if self._state == CircuitState.HALF_OPEN:
            if self._stats.consecutive_successes >= self.config.success_threshold:
                self._state = CircuitState.CLOSED
                self._stats.consecutive_failures = 0
                self._last_state_change_time = time.time()
                self._stats.state_changes += 1
                logger.info(f"CircuitBreaker '{self.name}' transitioned to CLOSED")
    
    async def _try_transition_to_open(self):
        """转换到打开状态"""
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
            self._last_state_change_time = time.time()
            self._stats.state_changes += 1
            logger.error(f"CircuitBreaker '{self.name}' transitioned to OPEN")
    
    async def call(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        执行函数，带熔断保护
        
        Args:
            func: 要执行的异步函数
            *args, **kwargs: 函数参数
        
        Returns:
            函数返回值
        
        Raises:
            CircuitOpenError: 熔断器打开时抛出
            Exception: 函数执行过程中的其他异常
        """
        async with self._lock:
            self._stats.total_calls += 1
            
            # 检查状态
            if self._state == CircuitState.OPEN:
                # 尝试转换到半开
                await self._try_transition_to_half_open()
                
                if self._state == CircuitState.OPEN:
                    self._stats.rejected_calls += 1
                    raise CircuitOpenError(
                        f"CircuitBreaker '{self.name}' is OPEN, call rejected"
                    )
            
            # 半开状态下的限制
            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.config.half_open_max_calls:
                    self._stats.rejected_calls += 1
                    raise CircuitOpenError(
                        f"CircuitBreaker '{self.name}' HALF_OPEN max calls reached"
                    )
                self._half_open_calls += 1
        
        # 执行函数
        try:
            # 添加超时
            result = await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=self.config.timeout
            )
            
            # 成功处理
            async with self._lock:
                self._stats.successful_calls += 1
                self._stats.consecutive_successes += 1
                self._stats.consecutive_failures = 0
                self._stats.last_success_time = time.time()
            
            await self._try_transition_to_closed()
            return result
            
        except asyncio.TimeoutError:
            async with self._lock:
                self._stats.failed_calls += 1
                self._stats.consecutive_failures += 1
                self._stats.last_failure_time = time.time()
            
            await self._try_transition_to_open()
            raise
            
        except Exception as e:
            async with self._lock:
                self._stats.failed_calls += 1
                self._stats.consecutive_failures += 1
                self._stats.last_failure_time = time.time()
            
            # 检查是否需要熔断
            async with self._lock:
                if self._stats.consecutive_failures >= self.config.failure_threshold:
                    await self._try_transition_to_open()
            
            raise
    
    async def reset(self):
        """重置熔断器"""
        async with self._lock:
            self._state = CircuitState.CLOSED
            self._stats = CircuitBreakerStats()
            self._last_state_change_time = time.time()
            self._half_open_calls = 0
        logger.info(f"CircuitBreaker '{self.name}' reset")
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "name": self.name,
            "state": self._state.value,
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "success_threshold": self.config.success_threshold,
                "recovery_timeout": self.config.recovery_timeout,
                "half_open_max_calls": self.config.half_open_max_calls,
                "timeout": self.config.timeout
            },
            "stats": {
                "total_calls": self._stats.total_calls,
                "successful_calls": self._stats.successful_calls,
                "failed_calls": self._stats.failed_calls,
                "rejected_calls": self._stats.rejected_calls,
                "state_changes": self._stats.state_changes,
                "consecutive_failures": self._stats.consecutive_failures,
                "consecutive_successes": self._stats.consecutive_successes
            }
        }


class CircuitBreakerManager:
    """熔断器管理器 - 按工具维度管理熔断器"""
    
    _instance: Optional['CircuitBreakerManager'] = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()
        self._default_config = CircuitBreakerConfig()
        
        self._initialized = True
        logger.info("CircuitBreakerManager initialized")
    
    async def get_breaker(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ) -> CircuitBreaker:
        """获取或创建熔断器"""
        async with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(
                    name,
                    config or self._default_config
                )
            return self._breakers[name]
    
    async def call(
        self,
        tool_name: str,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """带熔断保护的调用"""
        breaker = await self.get_breaker(tool_name)
        return await breaker.call(func, *args, **kwargs)
    
    async def get_all_stats(self) -> Dict[str, dict]:
        """获取所有熔断器状态"""
        async with self._lock:
            return {
                name: breaker.to_dict()
                for name, breaker in self._breakers.items()
            }
    
    async def reset_all(self):
        """重置所有熔断器"""
        async with self._lock:
            for breaker in self._breakers.values():
                await breaker.reset()
        logger.info("All circuit breakers reset")


# 全局实例
circuit_breaker_manager = CircuitBreakerManager()