"""
API2MCP 工具实体
"""
from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship

from ...database import Base


class Api2mcpTool(Base):
    """
    API2MCP 工具主表 - 存储 API 工具的完整配置和 MCP 生成信息
    """
    __tablename__ = "api2mcp_tools"

    id = Column(String, primary_key=True)
    tool_name = Column(String, nullable=False, index=True)
    version = Column(String, default="v1", nullable=False)  # 版本号，如 v1, v2, v3
    tool_description = Column(Text)
    category = Column(String)
    tags = Column(ARRAY(String), default=[])

    # 请求定义
    method = Column(String, nullable=False)
    base_url = Column(String, nullable=False)
    path = Column(String, nullable=False)
    content_type = Column(String, default="application/json")

    # 输出配置
    output_fields = Column(JSON, default=lambda: {})
    output_template = Column(String)

    # 使用示例（few-shot）
    usage_examples = Column(JSON, default=lambda: {})

    # 运行时配置
    cache_ttl = Column(Integer, default=0)
    timeout_ms = Column(Integer, default=30000)
    status = Column(String, default="active")
    auth_config_id = Column(String, ForeignKey("api2mcp_auth_config.id"))

    # 传输协议配置 - 支持多协议扩展（当前：streamable_http，未来：stdio）
    transport_modes = Column(JSON, default=lambda: ["streamable_http"])

    # 审计字段
    created_by = Column(String)
    updated_by = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    auth_config = relationship("Api2mcpAuthConfig", back_populates="tools")
    parameters = relationship("Api2mcpParameter", back_populates="tool", cascade="all, delete-orphan")
