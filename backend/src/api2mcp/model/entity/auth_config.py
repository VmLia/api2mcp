"""
API2MCP 鉴权配置实体 - 可复用的认证配置
"""
from datetime import datetime
from sqlalchemy import Column, String, DateTime, JSON
from sqlalchemy.orm import relationship

from ...database import Base


class Api2mcpAuthConfig(Base):
    """
    API2MCP 鉴权配置表 - 可复用的认证配置
    """
    __tablename__ = "api2mcp_auth_config"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    auth_type = Column(String, nullable=False)  # none, api_key, bearer_token, basic_auth, oauth2
    config = Column(JSON, default=lambda: {})

    # 审计字段
    created_by = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    tools = relationship("Api2mcpTool", back_populates="auth_config")
