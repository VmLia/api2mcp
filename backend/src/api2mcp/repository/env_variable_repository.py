"""
环境变量仓储 - 处理环境变量数据的数据库操作
"""
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..model.entity.env_variable import Api2mcpEnvVariable
from .base_repository import BaseRepository


class EnvVariableRepository(BaseRepository[Api2mcpEnvVariable]):
    """环境变量仓储"""

    def __init__(self, session: AsyncSession):
        super().__init__(Api2mcpEnvVariable, session)

    async def create_env_variable(self, **kwargs) -> Api2mcpEnvVariable:
        """创建环境变量"""
        if 'id' not in kwargs:
            kwargs['id'] = str(uuid4())
        return await self.create(**kwargs)

    async def get_by_key(self, key: str) -> Optional[Api2mcpEnvVariable]:
        """根据键名获取环境变量"""
        result = await self.session.execute(
            select(Api2mcpEnvVariable).where(Api2mcpEnvVariable.key == key)
        )
        return result.scalar_one_or_none()

    async def exists_by_key(self, key: str) -> bool:
        """检查键名是否存在"""
        result = await self.session.execute(
            select(Api2mcpEnvVariable).where(Api2mcpEnvVariable.key == key)
        )
        return result.scalar_one_or_none() is not None

    async def get_global_variables(self) -> List[Api2mcpEnvVariable]:
        """获取所有全局环境变量"""
        result = await self.session.execute(
            select(Api2mcpEnvVariable)
            .where(Api2mcpEnvVariable.scope == "global")
        )
        return list(result.scalars().all())

    async def get_variables_for_tool(
        self, tool_id: Optional[str] = None
    ) -> List[Api2mcpEnvVariable]:
        """获取工具的环境变量（包括全局变量和工具级别的变量）"""
        if tool_id:
            query = select(Api2mcpEnvVariable).where(
                or_(
                    Api2mcpEnvVariable.scope == "global",
                    Api2mcpEnvVariable.tool_id == tool_id
                )
            )
        else:
            query = select(Api2mcpEnvVariable).where(
                Api2mcpEnvVariable.scope == "global"
            )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_all_variables(
        self,
        scope: Optional[str] = None,
        tool_id: Optional[str] = None
    ) -> List[Api2mcpEnvVariable]:
        """获取所有环境变量，支持过滤"""
        query = select(Api2mcpEnvVariable)

        if scope:
            query = query.where(Api2mcpEnvVariable.scope == scope)
        if tool_id:
            query = query.where(
                or_(
                    Api2mcpEnvVariable.scope == "global",
                    Api2mcpEnvVariable.tool_id == tool_id
                )
            )

        result = await self.session.execute(query)
        return list(result.scalars().all())
