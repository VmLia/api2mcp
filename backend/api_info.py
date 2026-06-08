"""
API2MCP Data Models
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship

from database import Base


class Api2mcpProject(Base):
    """
    API2MCP API Main Table - Stores overall API configuration and MCP generation information
    """
    __tablename__ = "api2mcp_projects"

    id = Column(String, primary_key=True)
    tool_name = Column(String, nullable=False, index=True)
    version = Column(String, default="v1", nullable=False)  # Version number, e.g., v1, v2, v3
    tool_description = Column(Text)
    category = Column(String)
    tags = Column(ARRAY(String), default=[])

    # Request definition
    method = Column(String, nullable=False)
    base_url = Column(String, nullable=False)
    path = Column(String, nullable=False)
    content_type = Column(String, default="application/json")

    # Output configuration
    output_fields = Column(JSON, default=lambda: {})
    output_template = Column(String)

    # Usage examples (few-shot)
    usage_examples = Column(JSON, default=lambda: {})

    # Runtime configuration
    cache_ttl = Column(Integer, default=0)
    timeout_ms = Column(Integer, default=30000)
    status = Column(String, default="active")
    auth_config_id = Column(String, ForeignKey("api2mcp_auth_config.id"))

    # Transport protocol configuration - supports multi-protocol extension (current: streamable_http, future: stdio)
    transport_modes = Column(JSON, default=lambda: ["streamable_http"])

    # Audit
    created_by = Column(String)
    updated_by = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    auth_config = relationship("Api2mcpAuthConfig", back_populates="projects")
    parameters = relationship("Api2mcpParameter", back_populates="project", cascade="all, delete-orphan")


class Api2mcpParameter(Base):
    """
    API2MCP Parameter Table - Supports tree nested storage
    """
    __tablename__ = "api2mcp_parameters"

    id = Column(String, primary_key=True)
    project_id = Column(String, ForeignKey("api2mcp_projects.id"), nullable=False)
    parent_id = Column(String, ForeignKey("api2mcp_parameters.id"))

    # Parameter basic info
    param_name = Column(String, nullable=False)
    param_location = Column(String, nullable=False)  # query, path, body, header
    param_type = Column(String, nullable=False)  # string, integer, number, boolean, array, object
    item_type = Column(String)  # Array item type

    # Parameter constraints
    required = Column(Boolean, default=False)
    description = Column(Text)
    default_value = Column(String)
    example_value = Column(String)
    unit = Column(String)
    semantic_tag = Column(String)

    # Sorting
    sort_order = Column(Integer, default=0)

    # Relationships
    project = relationship("Api2mcpProject", back_populates="parameters")


class Api2mcpAuthConfig(Base):
    """
    API2MCP Auth Config Table - Reusable authentication configurations
    """
    __tablename__ = "api2mcp_auth_config"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    auth_type = Column(String, nullable=False)  # none, api_key, bearer_token, basic_auth, oauth2
    config = Column(JSON, default=lambda: {})

    # Audit
    created_by = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    projects = relationship("Api2mcpProject", back_populates="auth_config")


class Api2mcpEnvVariable(Base):
    """
    API2MCP Environment Variable Table
    """
    __tablename__ = "api2mcp_env_variables"

    id = Column(String, primary_key=True)
    key = Column(String, nullable=False, unique=True, index=True)
    value = Column(String, nullable=False)
    scope = Column(String, default="global")  # global, project
    project_id = Column(String)
    description = Column(String)

    # Audit
    created_by = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
