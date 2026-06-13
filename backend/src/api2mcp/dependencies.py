"""
依赖注入 - 提供 FastAPI 依赖项
"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from .database import async_session_maker
from .repository.tool_repository import ToolRepository
from .repository.parameter_repository import ParameterRepository
from .repository.auth_config_repository import AuthConfigRepository
from .repository.env_variable_repository import EnvVariableRepository
from .service.tool_service import ToolService
from .service.parameter_service import ParameterService
from .service.auth_service import AuthService
from .service.env_variable_service import EnvVariableService
from .service.mcp_service import MCPService


# ── 数据库会话依赖 ──

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话的依赖项

    使用方式:
    ```python
    @app.get("/tools")
    async def get_tools(session: AsyncSession = Depends(get_db_session)):
        ...
    ```
    """
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


# ── 仓储依赖 ──

async def get_tool_repository(
    session: AsyncSession = Depends(get_db_session)
) -> ToolRepository:
    """获取工具仓储"""
    return ToolRepository(session)


async def get_parameter_repository(
    session: AsyncSession = Depends(get_db_session)
) -> ParameterRepository:
    """获取参数仓储"""
    return ParameterRepository(session)


async def get_auth_config_repository(
    session: AsyncSession = Depends(get_db_session)
) -> AuthConfigRepository:
    """获取鉴权配置仓储"""
    return AuthConfigRepository(session)


async def get_env_variable_repository(
    session: AsyncSession = Depends(get_db_session)
) -> EnvVariableRepository:
    """获取环境变量仓储"""
    return EnvVariableRepository(session)


# ── 服务依赖 ──

async def get_tool_service() -> ToolService:
    """获取工具服务"""
    return ToolService()


async def get_parameter_service() -> ParameterService:
    """获取参数服务"""
    return ParameterService()


async def get_auth_service() -> AuthService:
    """获取鉴权服务"""
    return AuthService()


async def get_env_variable_service() -> EnvVariableService:
    """获取环境变量服务"""
    return EnvVariableService()


async def get_mcp_service() -> MCPService:
    """获取 MCP 服务"""
    return MCPService()
