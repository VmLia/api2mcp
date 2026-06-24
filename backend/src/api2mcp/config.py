"""
API2MCP 应用配置
"""
from pathlib import Path
from urllib.parse import quote
from pydantic_settings import BaseSettings, SettingsConfigDict


# .env 文件位于项目根目录（backend 的上一级）
_env_file = Path(__file__).resolve().parent.parent.parent.parent / ".env"


class Settings(BaseSettings):
    """应用配置"""

    # ── 项目信息（代码默认值）──
    PROJECT_NAME: str = "API2MCP Tool Management"
    PROJECT_VERSION: str = "1.0.0"
    API_PREFIX: str = "/api/v1"
    DB_TYPE: str = "postgresql"
    DB_DRIVER: str = "asyncpg"

    # ── 服务配置（.env）──
    API2MCP_HOST: str = "0.0.0.0"
    API2MCP_PORT_FRONTEND: int = 34075
    API2MCP_PORT_BACKEND: int = 34085
    API2MCP_DB_DEL: bool = False

    @property
    def BACKEND_HOST(self) -> str:
        return self.API2MCP_HOST

    @property
    def BACKEND_PORT(self) -> int:
        return self.API2MCP_PORT_BACKEND

    @property
    def FRONTEND_PORT(self) -> int:
        return self.API2MCP_PORT_FRONTEND

    # ── 前端 & MCP（.env）──
    VITE_API_URL: str = ""
    MCP_PUBLIC_BASE_URL: str = ""

    @property
    def mcp_public_base_url(self) -> str:
        """MCP 公开基础 URL"""
        if self.MCP_PUBLIC_BASE_URL:
            return self.MCP_PUBLIC_BASE_URL.rstrip("/")
        return f"http://127.0.0.1:{self.BACKEND_PORT}/mcpapi"

    # ── 数据库配置（.env）──
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "api2mcp"
    DB_PASSWORD: str = "api2mcp@123"
    DB_NAME: str = "api2mcp"
    DATABASE_URL: str = ""

    @property
    def database_url(self) -> str:
        """数据库连接 URL"""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        password = quote(self.DB_PASSWORD, safe="")
        return f"{self.DB_TYPE}+{self.DB_DRIVER}://{self.DB_USER}:{password}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # ── Redis 配置（.env）──
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = "api2mcp@123"
    REDIS_DB: int = 0
    REDIS_OPTIONAL: bool = True
    REDIS_SOCKET_TIMEOUT: int = 5
    REDIS_CONNECT_TIMEOUT: int = 5
    STATE_CACHE_TTL: int = 3600

    @property
    def redis_url(self) -> str:
        """Redis 连接 URL"""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # ── HTTP 客户端配置（.env）──
    HTTP_CLIENT_TIMEOUT: int = 60
    TOOL_DEFAULT_TIMEOUT_MS: int = 30000

    # ── 默认用户配置（.env）──
    DEFAULT_USER_ID: str = "admin"

    # ── LLM 配置（.env）──
    LLM_API_KEY: str = ""
    LLM_API_URL: str = "https://api.deepseek.com"
    LLM_MODEL_NAME: str = "deepseek-v4-flash"

    # ── 日志配置（.env）──
    LOG_LEVEL: str = "INFO"
    LOG_REQUEST_ENABLED: bool = False
    UVICORN_ACCESS_LOG: bool = False

    # ── FastAPI 元信息（代码默认值）──
    TITLE: str = "API2MCP"
    DESCRIPTION: str = """
API2MCP - REST API to MCP Bridge

将传统 REST API 转换为 MCP (Model Context Protocol) 工具，使 AI Agent 能够调用这些 API。

### MCP Server 端点

- `GET/POST /mcpapi` - MCP JSON-RPC 2.0 根端点
- `GET/POST /mcpapi/{identifier}` - 按项目标识符隔离的端点
- `GET/POST /mcpapi/{tool_name}/{version}` - 按工具名+版本隔离的端点

### 其他

- `GET /health` - 健康检查
- `GET /apidocs` - Swagger 文档
"""

    model_config = SettingsConfigDict(
        env_file=str(_env_file),
        extra='ignore',
        case_sensitive=True
    )


# 全局配置实例
settings = Settings()
