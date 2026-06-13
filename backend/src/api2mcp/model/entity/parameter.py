"""
API2MCP 参数实体 - 支持树形嵌套存储
"""
from sqlalchemy import Column, String, ForeignKey, Integer, Boolean, Text
from sqlalchemy.orm import relationship

from ...database import Base


class Api2mcpParameter(Base):
    """
    API2MCP 参数表 - 支持树形嵌套存储
    """
    __tablename__ = "api2mcp_parameters"

    id = Column(String, primary_key=True)
    tool_id = Column(String, ForeignKey("api2mcp_tools.id"), nullable=False)
    parent_id = Column(String, ForeignKey("api2mcp_parameters.id"))

    # 参数基本信息
    param_name = Column(String, nullable=False)
    param_location = Column(String, nullable=False)  # query, path, body, header
    param_type = Column(String, nullable=False)  # string, integer, number, boolean, array, object
    item_type = Column(String)  # 数组项类型

    # 参数约束
    required = Column(Boolean, default=False)
    description = Column(Text)
    default_value = Column(String)
    example_value = Column(String)
    unit = Column(String)
    semantic_tag = Column(String)

    # 排序
    sort_order = Column(Integer, default=0)

    # 关系
    tool = relationship("Api2mcpTool", back_populates="parameters")
