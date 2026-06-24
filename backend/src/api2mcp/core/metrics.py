"""
Prometheus 指标模块
"""
import logging
from typing import Optional

from prometheus_client import Counter, Histogram, Gauge, Info, CollectorRegistry

logger = logging.getLogger(__name__)

# 创建独立的 registry（避免与默认 registry 冲突）
registry = CollectorRegistry()

# ── HTTP 客户端指标 ──
HTTP_CLIENT_REQUESTS_TOTAL = Counter(
    'http_client_requests_total',
    'Total HTTP requests',
    ['method', 'status'],
    registry=registry
)

HTTP_CLIENT_REQUEST_DURATION = Histogram(
    'http_client_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method'],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    registry=registry
)

HTTP_CLIENT_CONNECTIONS = Gauge(
    'http_client_connections',
    'HTTP client connection pool status',
    ['state'],
    registry=registry
)

# ── MCP 服务指标 ──
MCP_REQUESTS_TOTAL = Counter(
    'mcp_requests_total',
    'Total MCP requests',
    ['tool', 'status'],
    registry=registry
)

MCP_REQUEST_DURATION = Histogram(
    'mcp_request_duration_seconds',
    'MCP request duration in seconds',
    ['tool'],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    registry=registry
)

MCP_ACTIVE_REQUESTS = Gauge(
    'mcp_active_requests',
    'Number of active MCP requests',
    registry=registry
)

# ── 熔断器指标 ──
CIRCUIT_BREAKER_STATE = Gauge(
    'circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=open, 2=half_open)',
    ['tool'],
    registry=registry
)

CIRCUIT_BREAKER_CALLS_TOTAL = Counter(
    'circuit_breaker_calls_total',
    'Total circuit breaker calls',
    ['tool', 'result'],
    registry=registry
)

# ── 限流器指标 ──
RATE_LIMIT_REQUESTS_TOTAL = Counter(
    'rate_limit_requests_total',
    'Total rate limit check results',
    ['result'],
    registry=registry
)

RATE_LIMIT_CURRENT_QPS = Gauge(
    'rate_limit_current_qps',
    'Current QPS',
    registry=registry
)

# ── 数据库指标 ──
DB_CONNECTIONS_ACTIVE = Gauge(
    'db_connections_active',
    'Number of active database connections',
    registry=registry
)

DB_QUERY_DURATION = Histogram(
    'db_query_duration_seconds',
    'Database query duration in seconds',
    ['operation'],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
    registry=registry
)

# ── Redis 指标 ──
REDIS_CONNECTIONS_ACTIVE = Gauge(
    'redis_connections_active',
    'Number of active Redis connections',
    registry=registry
)

REDIS_COMMAND_DURATION = Histogram(
    'redis_command_duration_seconds',
    'Redis command duration in seconds',
    ['command'],
    buckets=[0.0001, 0.0005, 0.001, 0.005, 0.01, 0.025, 0.05],
    registry=registry
)

# ── 服务指标 ──
SERVICE_INFO = Info('api2mcp', 'API2MCP service information', registry=registry)

SERVICE_UPTIME = Gauge(
    'service_uptime_seconds',
    'Service uptime in seconds',
    registry=registry
)

SERVICE_REQUESTS_TOTAL = Counter(
    'service_requests_total',
    'Total service requests',
    ['endpoint', 'method', 'status'],
    registry=registry
)


class MetricsCollector:
    """指标收集器"""
    
    def __init__(self):
        self._start_time = None
    
    def set_start_time(self):
        """设置服务启动时间"""
        import time
        self._start_time = time.time()
    
    def record_http_request(self, method: str, status: str):
        """记录 HTTP 请求"""
        HTTP_CLIENT_REQUESTS_TOTAL.labels(method=method, status=status).inc()
    
    def record_http_duration(self, method: str, duration: float):
        """记录 HTTP 请求耗时"""
        HTTP_CLIENT_REQUEST_DURATION.labels(method=method).observe(duration)
    
    def record_mcp_request(self, tool: str, status: str):
        """记录 MCP 请求"""
        MCP_REQUESTS_TOTAL.labels(tool=tool, status=status).inc()
    
    def record_mcp_duration(self, tool: str, duration: float):
        """记录 MCP 请求耗时"""
        MCP_REQUEST_DURATION.labels(tool=tool).observe(duration)
    
    def set_mcp_active_requests(self, count: int):
        """设置活跃 MCP 请求数"""
        MCP_ACTIVE_REQUESTS.set(count)
    
    def record_circuit_breaker(self, tool: str, state: str):
        """记录熔断器状态"""
        state_map = {"closed": 0, "open": 1, "half_open": 2}
        CIRCUIT_BREAKER_STATE.labels(tool=tool).set(state_map.get(state, 0))
    
    def record_circuit_breaker_call(self, tool: str, result: str):
        """记录熔断器调用"""
        CIRCUIT_BREAKER_CALLS_TOTAL.labels(tool=tool, result=result).inc()
    
    def record_rate_limit(self, result: str):
        """记录限流结果"""
        RATE_LIMIT_REQUESTS_TOTAL.labels(result=result).inc()
    
    def set_current_qps(self, qps: float):
        """设置当前 QPS"""
        RATE_LIMIT_CURRENT_QPS.set(qps)
    
    def record_db_query(self, operation: str, duration: float):
        """记录数据库查询"""
        DB_QUERY_DURATION.labels(operation=operation).observe(duration)
    
    def set_db_connections(self, count: int):
        """设置活跃数据库连接"""
        DB_CONNECTIONS_ACTIVE.set(count)
    
    def record_redis_command(self, command: str, duration: float):
        """记录 Redis 命令"""
        REDIS_COMMAND_DURATION.labels(command=command).observe(duration)
    
    def set_redis_connections(self, count: int):
        """设置活跃 Redis 连接"""
        REDIS_CONNECTIONS_ACTIVE.set(count)
    
    def record_service_request(self, endpoint: str, method: str, status: str):
        """记录服务请求"""
        SERVICE_REQUESTS_TOTAL.labels(endpoint=endpoint, method=method, status=status).inc()
    
    def update_uptime(self):
        """更新服务运行时间"""
        if self._start_time:
            import time
            SERVICE_UPTIME.set(time.time() - self._start_time)


# 全局实例
metrics_collector = MetricsCollector()


def get_metrics_registry() -> CollectorRegistry:
    """获取指标注册表"""
    return registry


def get_metrics_text() -> str:
    """获取 Prometheus 格式的指标文本"""
    from prometheus_client import generate_latest
    return generate_latest(registry).decode('utf-8')