"""
Core 模块 - 核心功能组件
"""
from .redis import get_redis_client, close_redis_client, cache, distributed_lock
from .http_client import http_client_pool, get_http_client, close_http_client
from .circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerManager,
    CircuitBreakerConfig,
    CircuitOpenError,
    circuit_breaker_manager
)
from .rate_limiter import (
    RateLimiter,
    RateLimitConfig,
    rate_limiter
)
from .metrics import (
    metrics_collector,
    get_metrics_registry,
    get_metrics_text
)
from .logging import LoggingMiddleware
from .logging_structlog import (
    configure_logging,
    get_logger,
    trace, debug, info, warning, error, critical, exception
)

__all__ = [
    # Redis
    "get_redis_client",
    "close_redis_client",
    "cache",
    "distributed_lock",
    # HTTP Client
    "http_client_pool",
    "get_http_client",
    "close_http_client",
    # Circuit Breaker
    "CircuitBreaker",
    "CircuitBreakerManager",
    "CircuitBreakerConfig",
    "CircuitOpenError",
    "circuit_breaker_manager",
    # Rate Limiter
    "RateLimiter",
    "RateLimitConfig",
    "rate_limiter",
    # Metrics
    "metrics_collector",
    "get_metrics_registry",
    "get_metrics_text",
    # Logging
    "LoggingMiddleware",
    "configure_logging",
    "get_logger",
    "trace",
    "debug",
    "info",
    "warning",
    "error",
    "critical",
    "exception",
]