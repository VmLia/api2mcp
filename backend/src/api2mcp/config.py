"""
API2MCP 应用配置
"""
import os
from pathlib import Path
from urllib.parse import quote
from pydantic_settings import BaseSettings, SettingsConfigDict


# .env 文件位于项目根目录（backend 的上一级）
_env_file = Path(__file__).resolve().parent.parent.parent.parent / ".env"


class Settings(BaseSettings):
    """应用配置"""

    # 项目信息
    PROJECT_NAME: str = "API2MCP Tool Management"
    PROJECT_VERSION: str = "1.0.0"

    # API 服务配置
    API_PREFIX: str = "/api/v1"
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 34085  # 可通过环境变量 API2MCP_PORT_BACKEND 覆盖

    # 前端配置
    FRONTEND_PORT: int = 34075  # 可通过环境变量 API2MCP_PORT_FRONTEND 覆盖

    # MCP 公开访问地址（供 MCP 客户端连接）
    # 可通过环境变量 MCP_PUBLIC_BASE_URL 覆盖，默认为自动生成
    MCP_PUBLIC_BASE_URL: str = ""

    @property
    def mcp_public_base_url(self) -> str:
        """MCP 公开基础 URL，优先使用环境变量，否则自动生成"""
        if self.MCP_PUBLIC_BASE_URL:
            return self.MCP_PUBLIC_BASE_URL.rstrip("/")
        # 使用 127.0.0.1 而非 localhost，避免部分客户端的 IPv6 兼容性问题
        return f"http://127.0.0.1:{self.BACKEND_PORT}/mcpapi"

    # 数据库配置 - 从配置参数自动生成，或通过 DATABASE_URL 覆盖
    DB_TYPE: str = "postgresql"
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 5432
    DB_USER: str = ""
    DB_PASSWORD: str = ""
    DB_NAME: str = ""
    DB_DRIVER: str = "asyncpg"
    DATABASE_URL: str = ""

    @property
    def database_url(self) -> str:
        """数据库连接 URL，优先使用 DATABASE_URL，否则从参数构建"""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        password = quote(self.DB_PASSWORD, safe="")
        return f"{self.DB_TYPE}+{self.DB_DRIVER}://{self.DB_USER}:{password}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # 默认用户（无登录需求，默认使用 admin）
    DEFAULT_USER_ID: str = "admin"
    DEFAULT_USER_NAME: str = "admin"

    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_REQUEST_ENABLED: bool = True  # 是否启用请求日志，可通过环境变量 LOG_REQUEST_ENABLED 覆盖
    UVICORN_ACCESS_LOG: bool = True  # 是否启用 uvicorn 访问日志，可通过环境变量 UVICORN_ACCESS_LOG 覆盖

    # FastAPI 配置
    TITLE: str = "API2MCP"
    DESCRIPTION: str = """
API2MCP - REST API to MCP Bridge

## 功能特性

将传统 REST API 转换为 MCP (Model Context Protocol) 工具，使 AI Agent 能够调用这些 API。

### MCP Server 端点 (mcpapi) - AI Agent 调用

- `GET/POST /mcpapi` - MCP JSON-RPC 2.0 根端点 (Streamable HTTP)
- `GET/POST /mcpapi/{identifier}` - 按项目标识符隔离的端点
- `GET/POST /mcpapi/{tool_name}/{version}` - 按工具名+版本隔离的端点

### 其他

- `GET /health` - 健康检查
- `GET /apidocs` - Swagger 文档
- `GET /redoc` - ReDoc 文档
"""

    model_config = SettingsConfigDict(
        env_file=str(_env_file),
        extra='ignore',
        case_sensitive=True
    )


# 全局配置实例
settings = Settings()
