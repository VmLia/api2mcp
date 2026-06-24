"""
WebSocket 协议客户端

支持：
- 连接到 WebSocket 服务器
- 发送/接收消息
- 自动重连
- 心跳保活
"""
import asyncio
import json
import logging
from typing import Callable, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

import websockets
from websockets.client import WebSocketClientProtocol
from websockets.exceptions import ConnectionClosed

from ..config import settings

logger = logging.getLogger(__name__)


class WebSocketState(Enum):
    """WebSocket 连接状态"""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"


@dataclass
class WebSocketConfig:
    """WebSocket 配置"""
    uri: str = "ws://localhost:8080/ws"
    ping_interval: int = 30      # 心跳间隔（秒）
    ping_timeout: int = 10       # 心跳超时（秒）
    max_size: int = 10 * 1024 * 1024  # 最大消息大小 10MB
    reconnect_delay: int = 5     # 重连延迟（秒）
    max_reconnect_attempts: int = 5  # 最大重连次数


class WebSocketClient:
    """
    WebSocket 异步客户端
    
    Usage:
        client = WebSocketClient("ws://localhost:8080/ws")
        
        # 设置消息处理
        client.on_message(lambda msg: print(f"Received: {msg}"))
        
        # 连接
        await client.connect()
        
        # 发送消息
        await client.send({"type": "hello"})
        
        # 保持连接
        await asyncio.sleep(3600)
        
        # 关闭
        await client.close()
    """
    
    def __init__(self, config: Optional[WebSocketConfig] = None):
        self.config = config or WebSocketConfig()
        self._ws: Optional[WebSocketClientProtocol] = None
        self._state = WebSocketState.DISCONNECTED
        self._message_handler: Optional[Callable] = None
        self._error_handler: Optional[Callable] = None
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._reconnect_count = 0
        self._lock = asyncio.Lock()
    
    @property
    def state(self) -> WebSocketState:
        return self._state
    
    @property
    def is_connected(self) -> bool:
        return self._state == WebSocketState.CONNECTED
    
    def on_message(self, handler: Callable[[Any], Any]):
        """设置消息处理函数"""
        self._message_handler = handler
    
    def on_error(self, handler: Callable[[Exception], Any]):
        """设置错误处理函数"""
        self._error_handler = handler
    
    async def connect(self):
        """连接到 WebSocket 服务器"""
        async with self._lock:
            if self._state == WebSocketState.CONNECTED:
                return
            
            self._state = WebSocketState.CONNECTING
            logger.info(f"Connecting to {self.config.uri}")
            
            try:
                self._ws = await asyncio.wait_for(
                    websockets.connect(
                        self.config.uri,
                        ping_interval=self.config.ping_interval,
                        ping_timeout=self.config.ping_timeout,
                        max_size=self.config.max_size,
                    ),
                    timeout=10.0
                )
                
                self._state = WebSocketState.CONNECTED
                self._reconnect_count = 0
                logger.info(f"WebSocket connected to {self.config.uri}")
                
                # 启动消息接收循环
                self._running = True
                self._task = asyncio.create_task(self._receive_loop())
                
            except Exception as e:
                self._state = WebSocketState.DISCONNECTED
                logger.error(f"WebSocket connection failed: {e}")
                raise
    
    async def _receive_loop(self):
        """接收消息循环"""
        while self._running:
            try:
                message = await self._ws.recv()
                
                # 解析 JSON
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    data = message
                
                # 调用消息处理函数
                if self._message_handler:
                    try:
                        self._message_handler(data)
                    except Exception as e:
                        logger.error(f"Message handler error: {e}")
                        
            except asyncio.CancelledError:
                break
            except ConnectionClosed as e:
                logger.warning(f"WebSocket connection closed: {e}")
                await self._handle_disconnect()
                break
            except Exception as e:
                logger.error(f"WebSocket receive error: {e}")
                if self._error_handler:
                    self._error_handler(e)
                await asyncio.sleep(1)
    
    async def _handle_disconnect(self):
        """处理断开连接"""
        self._running = False
        self._state = WebSocketState.DISCONNECTED
        
        # 尝试重连
        if self._reconnect_count < self.config.max_reconnect_attempts:
            self._state = WebSocketState.RECONNECTING
            self._reconnect_count += 1
            
            delay = self.config.reconnect_delay * self._reconnect_count
            logger.info(f"Reconnecting in {delay}s (attempt {self._reconnect_count})")
            
            await asyncio.sleep(delay)
            
            try:
                await self.connect()
            except Exception as e:
                logger.error(f"Reconnection failed: {e}")
    
    async def send(self, data: Any):
        """发送消息"""
        if not self.is_connected:
            raise ConnectionError("WebSocket not connected")
        
        # JSON 序列化
        if not isinstance(data, str):
            message = json.dumps(data, ensure_ascii=False)
        else:
            message = data
        
        await self._ws.send(message)
        logger.debug(f"Sent: {message[:100]}...")
    
    async def send_text(self, text: str):
        """发送文本消息"""
        if not self.is_connected:
            raise ConnectionError("WebSocket not connected")
        await self._ws.send(text)
    
    async def send_binary(self, data: bytes):
        """发送二进制消息"""
        if not self.is_connected:
            raise ConnectionError("WebSocket not connected")
        await self._ws.send(data)
    
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
            
            if self._ws:
                try:
                    await self._ws.close()
                except Exception as e:
                    logger.warning(f"WebSocket close error: {e}")
                self._ws = None
            
            self._state = WebSocketState.DISCONNECTED
            logger.info("WebSocket connection closed")


class WebSocketProtocol:
    """
    WebSocket 协议适配器 - 将 WebSocket 消息转换为 MCP 工具调用
    
    使用场景：
    - 实时聊天应用
    - 实时数据推送
    - 协作编辑
    - 游戏同步
    """
    
    def __init__(self, config: Optional[WebSocketConfig] = None):
        self._client = WebSocketClient(config)
        self._tool_handlers: Dict[str, Callable] = {}
    
    async def connect(self):
        """连接到 WebSocket 服务器"""
        await self._client.connect()
        
        # 设置默认消息处理
        self._client.on_message(self._handle_message)
    
    async def _handle_message(self, data: Any):
        """处理接收到的消息"""
        if isinstance(data, dict):
            tool_name = data.get("tool")
            if tool_name and tool_name in self._tool_handlers:
                try:
                    result = await self._tool_handlers[tool_name](data.get("payload", {}))
                    logger.info(f"Tool {tool_name} executed: {result}")
                except Exception as e:
                    logger.error(f"Tool {tool_name} execution failed: {e}")
    
    def register_tool_handler(
        self,
        tool_name: str,
        handler: Callable[[Dict], Any]
    ):
        """注册工具处理器"""
        self._tool_handlers[tool_name] = handler
    
    async def call_tool(self, tool_name: str, payload: Dict) -> Any:
        """通过 WebSocket 调用工具"""
        message = {
            "tool": tool_name,
            "payload": payload
        }
        await self._client.send(message)
    
    async def close(self):
        """关闭连接"""
        await self._client.close()


# 全局实例（按需创建）
_ws_clients: Dict[str, WebSocketClient] = {}


async def get_websocket_client(
    uri: str,
    ping_interval: int = 30
) -> WebSocketClient:
    """获取 WebSocket 客户端实例"""
    if uri not in _ws_clients:
        config = WebSocketConfig(uri=uri, ping_interval=ping_interval)
        _ws_clients[uri] = WebSocketClient(config)
    
    return _ws_clients[uri]