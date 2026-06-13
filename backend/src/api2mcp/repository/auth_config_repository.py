"""
鉴权配置仓储 - 处理鉴权配置数据的数据库操作
"""
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..model.entity.auth_config import Api2mcpAuthConfig
from .base_repository import BaseRepository


class AuthConfigRepository(BaseRepository[Api2mcpAuthConfig]):
    """鉴权配置仓储"""

    def __init__(self, session: AsyncSession):
        super().__init__(Api2mcpAuthConfig, session)

    async def create_auth_config(self, **kwargs) -> Api2mcpAuthConfig:
        """创建鉴权配置"""
        if 'id' not in kwargs:
            kwargs['id'] = str(uuid4())
        return await self.create(**kwargs)

    async def get_by_name(self, name: str) -> Optional[Api2mcpAuthConfig]:
        """根据名称获取鉴权配置"""
        result = await self.session.execute(
            select(Api2mcpAuthConfig).where(Api2mcpAuthConfig.name == name)
        )
        return result.scalar_one_or_none()

    async def get_all_configs(self) -> List[Api2mcpAuthConfig]:
        """获取所有鉴权配置"""
        result = await self.session.execute(select(Api2mcpAuthConfig))
        return list(result.scalars().all())

    async def count_tools_using_config(self, config_id: str) -> int:
        """统计使用该配置的工具数量"""
        from ..model.entity.tool import Api2mcpTool
        result = await self.session.execute(
            select(func.count()).select_from(Api2mcpTool)
            .where(Api2mcpTool.auth_config_id == config_id)
        )
        return result.scalar()

    async def is_using_by_tools(self, config_id: str) -> bool:
        """检查配置是否被工具使用"""
        return await self.count_tools_using_config(config_id) > 0
