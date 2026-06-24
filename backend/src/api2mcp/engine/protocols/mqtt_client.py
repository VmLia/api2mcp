"""
MQTT 协议客户端

支持：
- 订阅主题
- 发布消息
- 自动重连
- QoS 级别
"""
import asyncio
import json
import logging
from typing import Callable, Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

import aiomqtt

from ..config import settings

logger = logging.getLogger(__name__)


class QoSLevel(Enum):
    """MQTT QoS 级别"""
    AT_MOST_ONCE = 0    # 最多一次
    AT_LEAST_ONCE = 1   # 至少一次
    EXACTLY_ONCE = 2    # 恰好一次


@dataclass
class MQTTConfig:
    """MQTT 配置"""
    broker_url: str = "mqtt://localhost:1883"
    username: Optional[str] = None
    password: Optional[str] = None
    client_id: str = "api2mcp"
    keepalive: int = 60
    clean_session: bool = True
    tls_enabled: bool = False


class MQTTClient:
    """
    MQTT 异步客户端
    
    Usage:
        client = MQTTClient()
        
        # 订阅主题
        async def on_message(topic, payload):
            print(f"Received: {topic} -> {payload}")
        
        await client.subscribe("sensors/#", on_message)
        
        # 发布消息
        await client.publish("sensors/temperature", {"value": 25.5})
        
        # 保持连接
        await asyncio.sleep(3600)
        
        # 关闭
        await client.close()
    """
    
    def __init__(self, config: Optional[MQTTConfig] = None):
        self.config = config or MQTTConfig()
        self._client: Optional[aiomqtt.Client] = None
        self._subscriptions: Dict[str, Callable] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
    
    async def connect(self):
        """连接到 MQTT broker"""
        if self._client is not None:
            return
        
        try:
            self._client = aiomqtt.Client(
                identifier=self.config.client_id,
                clean_session=self.config.clean_session,
                keepalive=self.config.keepalive,
            )
            
            # 设置认证
            if self.config.username and self.config.password:
                self._client.username_pw_set(
                    self.config.username,
                    self.config.password
                )
            
            # TLS 支持
            if self.config.tls_enabled:
                self._client.tls_set()
            
            await self._client.__aenter__()
            logger.info(f"MQTT connected to {self.config.broker_url}")
            
        except Exception as e:
            logger.error(f"MQTT connection failed: {e}")
            self._client = None
            raise
    
    async def close(self):
        """关闭连接"""
        async with self._lock:
            self._running = False
            
            if self._task:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
            
            if self._client:
                try:
                    await self._client.__aexit__(None, None, None)
                except Exception as e:
                    logger.warning(f"MQTT close error: {e}")
                self._client = None
            
            logger.info("MQTT connection closed")
    
    async def subscribe(
        self,
        topic: str,
        callback: Callable[[str, Any], Any],
        qos: QoSLevel = QoSLevel.AT_LEAST_ONCE
    ):
        """
        订阅主题
        
        Args:
            topic: 主题（支持通配符）
            callback: 回调函数，签名: callback(topic: str, payload: Any)
            qos: QoS 级别
        """
        if self._client is None:
            await self.connect()
        
        self._subscriptions[topic] = callback
        
        async with self._client.messages() as messages:
            await self._client.subscribe(topic, qos.value)
            logger.info(f"Subscribed to topic: {topic}")
            
            self._running = True
            
            # 创建消息处理任务
            async def message_loop():
                while self._running:
                    try:
                        async for message in messages:
                            try:
                                payload = json.loads(message.payload.decode())
                            except json.JSONDecodeError:
                                payload = message.payload.decode()
                            
                            # 调用回调
                            callback(message.topic, payload)
                            
                    except asyncio.CancelledError:
                        break
                    except Exception as e:
                        logger.error(f"MQTT message loop error: {e}")
                        await asyncio.sleep(1)
            
            self._task = asyncio.create_task(message_loop())
    
    async def unsubscribe(self, topic: str):
        """取消订阅"""
        if self._client and topic in self._subscriptions:
            await self._client.unsubscribe(topic)
            del self._subscriptions[topic]
            logger.info(f"Unsubscribed from topic: {topic}")
    
    async def publish(
        self,
        topic: str,
        payload: Any,
        qos: QoSLevel = QoSLevel.AT_MOST_ONCE,
        retain: bool = False
    ):
        """
        发布消息
        
        Args:
            topic: 主题
            payload: 消息内容（会自动 JSON 序列化）
            qos: QoS 级别
            retain: 是否保留消息
        """
        if self._client is None:
            await self.connect()
        
        # JSON 序列化
        if not isinstance(payload, str):
            payload = json.dumps(payload, ensure_ascii=False)
        
        await self._client.publish(topic, payload, qos.value, retain)
        logger.debug(f"Published to {topic}: {payload[:100]}...")
    
    async def get_client(self) -> Optional[aiomqtt.Client]:
        """获取客户端实例"""
        if self._client is None:
            await self.connect()
        return self._client


class MQTTProtocol:
    """
    MQTT 协议适配器 - 将 MQTT 消息转换为 MCP 工具调用
    
    使用场景：
    - 物联网传感器数据采集
    - 实时消息推送
    - 事件驱动架构
    """
    
    def __init__(self, config: Optional[MQTTConfig] = None):
        self._client = MQTTClient(config)
        self._tool_handlers: Dict[str, Callable] = {}
    
    async def register_tool_handler(
        self,
        tool_name: str,
        handler: Callable[[Dict], Any]
    ):
        """注册工具处理器"""
        self._tool_handlers[tool_name] = handler
    
    async def subscribe_tool_topic(
        self,
        tool_name: str,
        topic: str,
        qos: QoSLevel = QoSLevel.AT_LEAST_ONCE
    ):
        """订阅工具主题"""
        
        async def handle_message(topic_str: str, payload: Any):
            if tool_name in self._tool_handlers:
                try:
                    result = await self._tool_handlers[tool_name](payload)
                    logger.info(f"Tool {tool_name} executed: {result}")
                except Exception as e:
                    logger.error(f"Tool {tool_name} execution failed: {e}")
        
        await self._client.subscribe(topic, handle_message, qos)
        logger.info(f"Registered tool {tool_name} on topic {topic}")
    
    async def publish_tool_result(
        self,
        tool_name: str,
        result: Any,
        topic: Optional[str] = None
    ):
        """发布工具执行结果"""
        topic = topic or f"api2mcp/results/{tool_name}"
        await self._client.publish(topic, result)
    
    async def close(self):
        """关闭连接"""
        await self._client.close()


# 全局实例（按需创建）
_mqtt_clients: Dict[str, MQTTClient] = {}


async def get_mqtt_client(
    broker_url: str,
    username: Optional[str] = None,
    password: Optional[str] = None,
    client_id: str = "api2mcp"
) -> MQTTClient:
    """获取 MQTT 客户端实例"""
    key = f"{broker_url}:{client_id}"
    
    if key not in _mqtt_clients:
        config = MQTTConfig(
            broker_url=broker_url,
            username=username,
            password=password,
            client_id=client_id
        )
        _mqtt_clients[key] = MQTTClient(config)
    
    return _mqtt_clients[key]