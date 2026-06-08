"""
API2MCP Subsystem Configuration
"""
import os
from pathlib import Path
from urllib.parse import quote
from pydantic_settings import BaseSettings, SettingsConfigDict

# .env file is located in project root (parent directory of backend)
_env_file = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    # Project configuration
    PROJECT_NAME: str = "API2MCP Tool Management"
    PROJECT_VERSION: str = "1.0.0"

    # API configuration
    API_PREFIX: str = "/api/v1"
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 34085  # Default port, can be overridden by env var API2MCP_PORT_BACKEND

    # Frontend configuration
    FRONTEND_PORT: int = 34075  # Default port, can be overridden by env var API2MCP_PORT_FRONTEND

    # MCP public access URL (MCP clients connect to this address)
    # Can be overridden by env var MCP_PUBLIC_BASE_URL, defaults to auto-generated
    MCP_PUBLIC_BASE_URL: str = ""

    @property
    def mcp_public_base_url(self) -> str:
        """MCP public base URL, prioritizes env var, otherwise auto-generates"""
        if self.MCP_PUBLIC_BASE_URL:
            return self.MCP_PUBLIC_BASE_URL.rstrip("/")
        # Use 127.0.0.1 instead of localhost to avoid IPv6 compatibility issues with some clients
        return f"http://127.0.0.1:{self.BACKEND_PORT}/mcpapi"

    # Database configuration - auto-generated from segment params, or can be overridden by DATABASE_URL
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
        """Database connection URL, prioritizes DATABASE_URL, otherwise builds from segment params"""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        driver = self.DB_DRIVER
        password = quote(self.DB_PASSWORD, safe="")
        return f"{self.DB_TYPE}+{driver}://{self.DB_USER}:{password}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # Default user (no login required, uses admin by default)
    DEFAULT_USER_ID: str = "admin"
    DEFAULT_USER_NAME: str = "admin"

    # Log configuration
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(env_file=str(_env_file), extra='ignore')


settings = Settings()