"""
MCP Server 全流程状态管理模块

负责跟踪：
1. 请求状态（开始、处理中、完成、失败）
2. 服务健康状态
3. 调用统计信息
4. 分布式锁保护
"""
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List, Union
from enum import Enum
from dataclasses import dataclass, asdict

from ..core.redis import cache, distributed_lock, get_redis_client


class RequestStatus(Enum):
    """请求状态枚举"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ServerStatus(Enum):
    """服务状态枚举"""
    RUNNING = "running"
    STOPPED = "stopped"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass
class RequestInfo:
    """请求信息"""
    request_id: str
    tool_name: str
    tool_version: str
    status: str
    created_at: str
    updated_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    latency_ms: Optional[int] = None
    input_params: Optional[Dict] = None
    output_result: Optional[Dict] = None

    def to_dict(self) -> Dict:
        """转换为字典"""
        return asdict(self)


@dataclass
class ServerInfo:
    """服务信息"""
    server_id: str
    name: str
    status: str
    last_heartbeat: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_latency_ms: float = 0.0

    def to_dict(self) -> Dict:
        """转换为字典"""
        return asdict(self)


class RequestStateManager:
    """请求状态管理器"""

    # Redis 键前缀
    REQUEST_PREFIX = "mcp:request:"
    REQUEST_INDEX_PREFIX = "mcp:requests:"
    REQUEST_LOCK_PREFIX = "mcp:lock:request:"

    @staticmethod
    def generate_request_id() -> str:
        """生成唯一请求 ID"""
        return str(uuid.uuid4())

    @staticmethod
    def _get_request_key(request_id: str) -> str:
        """获取请求状态键"""
        return f"{RequestStateManager.REQUEST_PREFIX}{request_id}"

    @staticmethod
    def _get_request_index_key(tool_name: str, tool_version: str) -> str:
        """获取请求索引键"""
        return f"{RequestStateManager.REQUEST_INDEX_PREFIX}{tool_name}:{tool_version}"

    @staticmethod
    def _get_request_lock_key(request_id: str) -> str:
        """获取请求锁键"""
        return f"{RequestStateManager.REQUEST_LOCK_PREFIX}{request_id}"

    async def start_request(
        self,
        tool_name: str,
        tool_version: str,
        input_params: Optional[Dict] = None
    ) -> str:
        """
        记录请求开始
        :return: 请求 ID
        """
        request_id = self.generate_request_id()
        now = datetime.utcnow().isoformat()

        request_info = RequestInfo(
            request_id=request_id,
            tool_name=tool_name,
            tool_version=tool_version,
            status=RequestStatus.PENDING.value,
            created_at=now,
            updated_at=now,
            input_params=input_params
        )

        # 存储请求信息
        await cache.set_json(self._get_request_key(request_id), request_info.to_dict())

        # 添加到索引
        await (await cache.client()).zadd(
            self._get_request_index_key(tool_name, tool_version),
            {request_id: datetime.fromisoformat(now).timestamp()}
        )

        return request_id

    async def update_request_status(
        self,
        request_id: str,
        status: RequestStatus,
        error_message: Optional[str] = None,
        output_result: Optional[Dict] = None
    ):
        """
        更新请求状态
        """
        key = self._get_request_key(request_id)
        request_info = await cache.get_json(key)

        if not request_info:
            return

        now = datetime.utcnow().isoformat()
        request_info["status"] = status.value
        request_info["updated_at"] = now

        if status == RequestStatus.PROCESSING:
            request_info["started_at"] = now
        elif status == RequestStatus.COMPLETED:
            request_info["completed_at"] = now
            request_info["output_result"] = output_result
            # 计算延迟
            if request_info.get("started_at"):
                start_time = datetime.fromisoformat(request_info["started_at"])
                end_time = datetime.fromisoformat(now)
                request_info["latency_ms"] = int((end_time - start_time).total_seconds() * 1000)
        elif status == RequestStatus.FAILED:
            request_info["completed_at"] = now
            request_info["error_message"] = error_message

        await cache.set_json(key, request_info)

    async def get_request_info(self, request_id: str) -> Optional[RequestInfo]:
        """
        获取请求信息
        """
        data = await cache.get_json(self._get_request_key(request_id))
        if data:
            return RequestInfo(**data)
        return None

    async def get_recent_requests(
        self,
        tool_name: str,
        tool_version: str,
        limit: int = 100
    ) -> List[RequestInfo]:
        """
        获取最近的请求列表
        """
        key = self._get_request_index_key(tool_name, tool_version)
        request_ids = await (await cache.client()).zrevrange(key, 0, limit - 1)

        requests = []
        for request_id in request_ids:
            info = await self.get_request_info(request_id)
            if info:
                requests.append(info)

        return requests

    async def delete_request(self, request_id: str):
        """
        删除请求记录
        """
        key = self._get_request_key(request_id)
        await cache.delete(key)


class ServerStateManager:
    """服务状态管理器"""

    # Redis 键前缀
    SERVER_PREFIX = "mcp:server:"
    SERVER_INDEX = "mcp:servers"
    SERVER_HEARTBEAT_PREFIX = "mcp:heartbeat:"

    @staticmethod
    def _get_server_key(server_id: str) -> str:
        """获取服务状态键"""
        return f"{ServerStateManager.SERVER_PREFIX}{server_id}"

    @staticmethod
    def _get_heartbeat_key(server_id: str) -> str:
        """获取心跳键"""
        return f"{ServerStateManager.SERVER_HEARTBEAT_PREFIX}{server_id}"

    async def register_server(self, server_id: str, name: str):
        """
        注册服务实例
        """
        now = datetime.utcnow().isoformat()

        server_info = ServerInfo(
            server_id=server_id,
            name=name,
            status=ServerStatus.RUNNING.value,
            last_heartbeat=now
        )

        await cache.set_json(self._get_server_key(server_id), server_info.to_dict())
        await (await cache.client()).sadd(self.SERVER_INDEX, server_id)

    async def update_heartbeat(self, server_id: str):
        """
        更新服务心跳
        """
        now = datetime.utcnow().isoformat()
        key = self._get_server_key(server_id)

        server_info = await cache.get_json(key)
        if server_info:
            server_info["last_heartbeat"] = now
            server_info["status"] = ServerStatus.RUNNING.value
            await cache.set_json(key, server_info)

        # 设置心跳过期（30秒无心跳则视为离线）
        heartbeat_key = self._get_heartbeat_key(server_id)
        await cache.set(heartbeat_key, now, ttl=30)

    async def get_server_info(self, server_id: str) -> Optional[ServerInfo]:
        """
        获取服务信息
        """
        data = await cache.get_json(self._get_server_key(server_id))
        if data:
            return ServerInfo(**data)
        return None

    async def get_all_servers(self) -> List[ServerInfo]:
        """
        获取所有服务实例
        """
        server_ids = await (await cache.client()).smembers(self.SERVER_INDEX)
        servers = []

        for server_id in server_ids:
            info = await self.get_server_info(server_id)
            if info:
                # 检查心跳是否过期
                heartbeat_key = self._get_heartbeat_key(server_id)
                if not await cache.exists(heartbeat_key):
                    info.status = ServerStatus.STOPPED.value
                servers.append(info)

        return servers

    async def update_server_stats(
        self,
        server_id: str,
        success: bool,
        latency_ms: int
    ):
        """
        更新服务统计信息
        """
        key = self._get_server_key(server_id)
        server_info = await cache.get_json(key)

        if not server_info:
            return

        server_info["total_requests"] += 1

        if success:
            server_info["successful_requests"] += 1
        else:
            server_info["failed_requests"] += 1

        # 更新平均延迟（简单移动平均）
        current_avg = server_info.get("avg_latency_ms", 0.0)
        server_info["avg_latency_ms"] = (current_avg * (server_info["total_requests"] - 1) + latency_ms) / server_info["total_requests"]

        await cache.set_json(key, server_info)

    async def unregister_server(self, server_id: str):
        """
        注销服务实例
        """
        await cache.delete(self._get_server_key(server_id))
        await cache.delete(self._get_heartbeat_key(server_id))
        await (await cache.client()).srem(self.SERVER_INDEX, server_id)


class CallStatisticsManager:
    """调用统计管理器"""

    # Redis 键前缀
    STATS_PREFIX = "mcp:stats:"
    STATS_HOURLY_PREFIX = "mcp:stats:hourly:"
    STATS_DAILY_PREFIX = "mcp:stats:daily:"

    @staticmethod
    def _get_stats_key(tool_name: str, tool_version: str) -> str:
        """获取统计键"""
        return f"{CallStatisticsManager.STATS_PREFIX}{tool_name}:{tool_version}"

    @staticmethod
    def _get_hourly_key(tool_name: str, tool_version: str, hour: str) -> str:
        """获取小时统计键"""
        return f"{CallStatisticsManager.STATS_HOURLY_PREFIX}{tool_name}:{tool_version}:{hour}"

    @staticmethod
    def _get_daily_key(tool_name: str, tool_version: str, date: str) -> str:
        """获取日统计键"""
        return f"{CallStatisticsManager.STATS_DAILY_PREFIX}{tool_name}:{tool_version}:{date}"

    async def record_call(self, tool_name: str, tool_version: str, success: bool, latency_ms: int):
        """
        记录调用统计
        """
        now = datetime.utcnow()
        hour_key = now.strftime("%Y%m%d%H")
        date_key = now.strftime("%Y%m%d")

        # 更新总统计
        stats_key = self._get_stats_key(tool_name, tool_version)
        async with await get_redis_client() as client:
            async with client.pipeline(transaction=True) as pipe:
                pipe.hincrby(stats_key, "total_calls", 1)
                pipe.hincrby(stats_key, "success_calls" if success else "failed_calls", 1)
                pipe.hincrby(stats_key, "total_latency_ms", latency_ms)
                await pipe.execute()

        # 更新小时统计
        hourly_key = self._get_hourly_key(tool_name, tool_version, hour_key)
        async with await get_redis_client() as client:
            async with client.pipeline(transaction=True) as pipe:
                pipe.hincrby(hourly_key, "total_calls", 1)
                pipe.hincrby(hourly_key, "success_calls" if success else "failed_calls", 1)
                pipe.hincrby(hourly_key, "total_latency_ms", latency_ms)
                pipe.expire(hourly_key, 24 * 60 * 60)  # 保留24小时
                await pipe.execute()

        # 更新日统计
        daily_key = self._get_daily_key(tool_name, tool_version, date_key)
        async with await get_redis_client() as client:
            async with client.pipeline(transaction=True) as pipe:
                pipe.hincrby(daily_key, "total_calls", 1)
                pipe.hincrby(daily_key, "success_calls" if success else "failed_calls", 1)
                pipe.hincrby(daily_key, "total_latency_ms", latency_ms)
                pipe.expire(daily_key, 7 * 24 * 60 * 60)  # 保留7天
                await pipe.execute()

    async def get_stats(self, tool_name: str, tool_version: str) -> Dict[str, Any]:
        """
        获取工具调用统计
        """
        stats_key = self._get_stats_key(tool_name, tool_version)
        data = await (await cache.client()).hgetall(stats_key)

        if not data:
            return {
                "total_calls": 0,
                "success_calls": 0,
                "failed_calls": 0,
                "avg_latency_ms": 0.0,
                "success_rate": 0.0
            }

        total_calls = int(data.get("total_calls", 0))
        success_calls = int(data.get("success_calls", 0))
        failed_calls = int(data.get("failed_calls", 0))
        total_latency = int(data.get("total_latency_ms", 0))

        return {
            "total_calls": total_calls,
            "success_calls": success_calls,
            "failed_calls": failed_calls,
            "avg_latency_ms": total_latency / total_calls if total_calls > 0 else 0.0,
            "success_rate": (success_calls / total_calls * 100) if total_calls > 0 else 0.0
        }

    async def get_hourly_stats(self, tool_name: str, tool_version: str, hours: int = 24) -> List[Dict]:
        """
        获取最近N小时的统计
        """
        result = []
        now = datetime.utcnow()

        for i in range(hours):
            hour = (now - datetime.timedelta(hours=i)).strftime("%Y%m%d%H")
            key = self._get_hourly_key(tool_name, tool_version, hour)
            data = await (await cache.client()).hgetall(key)

            total_calls = int(data.get("total_calls", 0))
            success_calls = int(data.get("success_calls", 0))
            total_latency = int(data.get("total_latency_ms", 0))

            result.append({
                "hour": hour,
                "total_calls": total_calls,
                "success_calls": success_calls,
                "failed_calls": int(data.get("failed_calls", 0)),
                "avg_latency_ms": total_latency / total_calls if total_calls > 0 else 0.0
            })

        return result


# 全局状态管理器实例
request_state_manager = RequestStateManager()
server_state_manager = ServerStateManager()
call_statistics_manager = CallStatisticsManager()
