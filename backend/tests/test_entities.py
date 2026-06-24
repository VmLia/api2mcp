"""
实体单元测试
"""
import pytest
from uuid import uuid4
from datetime import datetime

from api2mcp.entities.tool import Api2mcpTool
from api2mcp.entities.parameter import Api2mcpParameter
from api2mcp.entities.auth_config import Api2mcpAuthConfig
from api2mcp.entities.env_variable import Api2mcpEnvVariable


class TestApi2mcpTool:
    """工具实体测试"""

    def test_tool_creation(self):
        """测试工具创建"""
        tool = Api2mcpTool(
            id=str(uuid4()),
            tool_name="test_tool",
            version="v1",
            method="GET",
            base_url="https://api.example.com",
            path="/users",
            tool_description="Test tool description",
            category="test",
            tags=["test", "example"],
            status="active",
        )

        assert tool.tool_name == "test_tool"
        assert tool.version == "v1"
        assert tool.method == "GET"
        assert tool.status == "active"

    def test_tool_default_values(self):
        """测试工具默认字段"""
        tool = Api2mcpTool(
            id=str(uuid4()),
            tool_name="test_tool",
            method="POST",
            base_url="https://api.example.com",
            path="/api/data",
        )

        assert tool.version == "v1"
        assert tool.content_type == "application/json"
        assert tool.cache_ttl == 0
        assert tool.timeout_ms == 30000
        assert tool.status == "active"

    def test_tool_timestamps(self):
        """测试时间戳字段"""
        now = datetime.utcnow()
        tool = Api2mcpTool(
            id=str(uuid4()),
            tool_name="test_tool",
            version="v1",
            method="GET",
            base_url="https://api.example.com",
            path="/test",
            created_at=now,
            updated_at=now,
        )

        assert tool.created_at == now
        assert tool.updated_at == now


class TestApi2mcpParameter:
    """参数实体测试"""

    def test_parameter_creation(self):
        """测试参数创建"""
        param = Api2mcpParameter(
            id=str(uuid4()),
            tool_id="test_tool_id",
            param_name="user_id",
            param_type="string",
            param_location="path",
            param_required=True,
            param_description="User ID parameter",
        )

        assert param.param_name == "user_id"
        assert param.param_type == "string"
        assert param.param_location == "path"
        assert param.param_required is True

    def test_parameter_defaults(self):
        """测试参数默认值"""
        param = Api2mcpParameter(
            id=str(uuid4()),
            tool_id="test_tool_id",
            param_name="optional_param",
            param_type="string",
        )

        assert param.param_required is False
        assert param.param_location == "query"


class TestApi2mcpAuthConfig:
    """鉴权配置实体测试"""

    def test_auth_config_creation(self):
        """测试鉴权配置创建"""
        auth = Api2mcpAuthConfig(
            id=str(uuid4()),
            name="test_auth",
            auth_type="bearer",
            auth_location="header",
            auth_key_name="Authorization",
            auth_value_template="Bearer {{token}}",
            description="Test auth config",
        )

        assert auth.name == "test_auth"
        assert auth.auth_type == "bearer"
        assert auth.auth_location == "header"


class TestApi2mcpEnvVariable:
    """环境变量实体测试"""

    def test_env_variable_creation(self):
        """测试环境变量创建"""
        env = Api2mcpEnvVariable(
            id=str(uuid4()),
            key="API_KEY",
            value="test_secret_key",
            scope="global",
            description="API key for external service",
        )

        assert env.key == "API_KEY"
        assert env.value == "test_secret_key"
        assert env.scope == "global"

    def test_env_variable_tool_scope(self):
        """测试工具级环境变量"""
        env = Api2mcpEnvVariable(
            id=str(uuid4()),
            key="TOOL_API_KEY",
            value="tool_specific_key",
            scope="tool",
            tool_id="specific_tool_id",
        )

        assert env.scope == "tool"
        assert env.tool_id == "specific_tool_id"
