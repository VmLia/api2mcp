"""
API2MCP 环境变量实体
"""
from datetime import datetime
from sqlalchemy import Column, String, DateTime

from ...database import Base


class Api2mcpEnvVariable(Base):
    """
    API2MCP 环境变量表
    """
    __tablename__ = "api2mcp_env_variables"

    id = Column(String, primary_key=True)
    key = Column(String, nullable=False, unique=True, index=True)
    value = Column(String, nullable=False)
    scope = Column(String, default="global")  # global, project
    tool_id = Column(String)
    description = Column(String)

    # 审计字段
    created_by = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
