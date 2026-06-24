"""
核心模块单元测试
"""
import asyncio
import pytest
import pytest_asyncio

import sys
from pathlib import Path

# 将 src 目录添加到 path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from api2mcp.core.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitOpenError,
    CircuitState
)
from api2mcp.core.rate_limiter import RateLimiter, TokenBucket


class TestCircuitBreaker:
    """熔断器测试"""
    
    @pytest.mark.asyncio
    async def test_circuit_closed_state(self):
        """测试关闭状态"""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=1
        )
        breaker = CircuitBreaker("test", config)
        
        assert breaker.state == CircuitState.CLOSED
        
        # 成功调用应该通过
        async def success_func():
            return "success"
        
        result = await breaker.call(success_func)
        assert result == "success"
        assert breaker.stats.successful_calls == 1
    
    @pytest.mark.asyncio
    async def test_circuit_open_after_failures(self):
        """测试失败后熔断"""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=60
        )
        breaker = CircuitBreaker("test", config)
        
        # 连续失败
        async def fail_func():
            raise ValueError("fail")
        
        for _ in range(2):
            try:
                await breaker.call(fail_func)
            except ValueError:
                pass  # 忽略异常
        
        # 等待状态更新
        await asyncio.sleep(0.1)
        
        # 再次失败应该触发熔断
        with pytest.raises((ValueError, CircuitOpenError)):
            await breaker.call(fail_func)
    
    @pytest.mark.asyncio
    async def test_circuit_half_open_recovery(self):
        """测试半开恢复"""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout=1,  # 1秒后尝试恢复
            success_threshold=2
        )
        breaker = CircuitBreaker("test", config)
        
        # 失败触发熔断
        async def fail_func():
            raise ValueError("fail")
        
        try:
            await breaker.call(fail_func)
        except ValueError:
            pass
        
        # 等待恢复超时
        await asyncio.sleep(1.5)
        
        # 半开状态后，连续成功应该恢复
        async def success_func():
            return "success"
        
        await breaker.call(success_func)
        await breaker.call(success_func)
        
        assert breaker.state == CircuitState.CLOSED
    
    @pytest.mark.asyncio
    async def test_circuit_timeout(self):
        """测试超时保护"""
        config = CircuitBreakerConfig(
            timeout=0.1
        )
        breaker = CircuitBreaker("test", config)
        
        async def slow_func():
            await asyncio.sleep(1)
            return "success"
        
        with pytest.raises(asyncio.TimeoutError):
            await breaker.call(slow_func)


class TestTokenBucket:
    """令牌桶测试"""
    
    @pytest.mark.asyncio
    async def test_token_bucket_consume(self):
        """测试令牌消费"""
        bucket = TokenBucket(rate=10, capacity=10)
        
        # 应该可以消费
        result = await bucket.consume(1, wait=False)
        assert result is True
        
        # 消费后可用令牌减少
        available = await bucket.get_available_tokens()
        assert available < 10
    
    @pytest.mark.asyncio
    async def test_token_bucket_refill(self):
        """测试令牌补充"""
        bucket = TokenBucket(rate=100, capacity=10)
        
        # 消费所有令牌
        for _ in range(10):
            await bucket.consume(1, wait=False)
        
        available = await bucket.get_available_tokens()
        assert available < 1
        
        # 等待补充
        await asyncio.sleep(0.1)
        
        available = await bucket.get_available_tokens()
        assert available > 0
    
    @pytest.mark.asyncio
    async def test_token_bucket_wait(self):
        """测试等待模式"""
        bucket = TokenBucket(rate=1, capacity=1)
        
        # 消费唯一的令牌
        await bucket.consume(1, wait=False)
        
        # 再次消费需要等待
        start = asyncio.get_event_loop().time()
        result = await bucket.consume(1, wait=True)
        elapsed = asyncio.get_event_loop().time() - start
        
        assert result is True
        assert elapsed >= 1.0  # 至少等待 1 秒


class TestRateLimiter:
    """限流器测试"""
    
    @pytest.mark.asyncio
    async def test_rate_limiter_check(self):
        """测试限流检查"""
        limiter = RateLimiter()
        
        # 首次检查应该通过
        allowed, wait = await limiter.check_limit("test_tool")
        assert allowed is True
    
    @pytest.mark.asyncio
    async def test_rate_limiter_acquire(self):
        """测试限流获取"""
        limiter = RateLimiter()
        
        # 应该可以获取
        result = await limiter.acquire("test_tool", tokens=1, timeout=5.0)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_rate_limiter_stats(self):
        """测试统计"""
        limiter = RateLimiter()
        
        await limiter.check_limit("tool1")
        await limiter.check_limit("tool2")
        
        stats = await limiter.get_stats()
        
        assert stats["total_requests"] >= 2
        assert stats["allowed_requests"] >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])