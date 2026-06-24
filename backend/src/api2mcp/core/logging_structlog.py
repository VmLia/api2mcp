"""
结构化日志模块

使用 structlog 提供 JSON 格式的结构化日志
"""
import logging
import sys
import json
from datetime import datetime
from typing import Any, Dict, Optional
from enum import Enum

import structlog
from structlog.types import EventDict, Processor
from structlog.processors import JSONRenderer, TimeStamper, add_log_level


class LogLevel(str, Enum):
    """日志级别"""
    TRACE = "trace"
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


def add_timestamp(logger, method_name: str, event_dict: EventDict) -> EventDict:
    """添加 ISO 格式时间戳"""
    event_dict["timestamp"] = datetime.utcnow().isoformat() + "Z"
    return event_dict


def add_hostname(logger, method_name: str, event_dict: EventDict) -> EventDict:
    """添加主机名"""
    import socket
    event_dict["hostname"] = socket.gethostname()
    return event_dict


def add_pid(logger, method_name: str, event_dict: EventDict) -> EventDict:
    """添加进程 ID"""
    import os
    event_dict["pid"] = os.getpid()
    return event_dict


def sanitize_value(val: Any) -> Any:
    """清理值，确保可 JSON 序列化"""
    if val is None:
        return None
    if isinstance(val, (str, int, float, bool)):
        return val
    if isinstance(val, bytes):
        return val.decode('utf-8', errors='replace')
    if isinstance(val, Exception):
        return {
            "type": type(val).__name__,
            "message": str(val),
        }
    if hasattr(val, '__dict__'):
        return sanitize_value(val.__dict__)
    if isinstance(val, (list, tuple)):
        return [sanitize_value(v) for v in val]
    if isinstance(val, dict):
        return {k: sanitize_value(v) for k, v in val.items()}
    return str(val)


def sanitize_event_dict(logger, method_name: str, event_dict: EventDict) -> EventDict:
    """清理事件字典，确保所有值可序列化"""
    return {k: sanitize_value(v) for k, v in event_dict.items()}


def configure_logging(
    log_level: str = "INFO",
    json_format: bool = True,
    include_caller: bool = True
):
    """
    配置结构化日志
    
    Args:
        log_level: 日志级别
        json_format: 是否使用 JSON 格式
        include_caller: 是否包含调用者信息
    """
    processors = [
        structlog.contextvars.merge_contextvars,
        add_log_level,
        add_timestamp,
        add_hostname,
        add_pid,
    ]
    
    if include_caller:
        processors.append(structlog.processors.CallsiteParameterAdder({
            structlog.processors.CallsiteParameter.FILENAME: "filename",
            structlog.processors.CallsiteParameter.FUNC_NAME: "func_name",
            structlog.processors.CallsiteParameter.LINENO: "line_number",
        }))
    
    processors.append(sanitize_event_dict)
    
    if json_format:
        processors.append(JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: Optional[str] = None, **context) -> structlog.BoundLogger:
    """
    获取日志实例
    
    Usage:
        logger = get_logger("api2mcp")
        logger.info("request_received", request_id="123")
        
        # 带额外上下文
        logger = get_logger("api2mcp", user_id="456")
        logger.info("user_action", action="login")
    """
    logger = structlog.get_logger(name)
    if context:
        logger = logger.bind(**context)
    return logger


# 默认配置
configure_logging(log_level="INFO", json_format=True)


# 便捷函数
def trace(message: str, **kwargs):
    """记录 TRACE 级别日志"""
    get_logger().trace(message, **kwargs)


def debug(message: str, **kwargs):
    """记录 DEBUG 级别日志"""
    get_logger().debug(message, **kwargs)


def info(message: str, **kwargs):
    """记录 INFO 级别日志"""
    get_logger().info(message, **kwargs)


def warning(message: str, **kwargs):
    """记录 WARNING 级别日志"""
    get_logger().warning(message, **kwargs)


def error(message: str, **kwargs):
    """记录 ERROR 级别日志"""
    get_logger().error(message, **kwargs)


def critical(message: str, **kwargs):
    """记录 CRITICAL 级别日志"""
    get_logger().critical(message, **kwargs)


def exception(message: str, **kwargs):
    """记录异常（自动包含异常信息）"""
    get_logger().exception(message, **kwargs)