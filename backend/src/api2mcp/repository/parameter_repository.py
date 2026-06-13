"""
参数仓储 - 处理参数数据的数据库操作
"""
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..model.entity.parameter import Api2mcpParameter
from .base_repository import BaseRepository


class ParameterRepository(BaseRepository[Api2mcpParameter]):
    """参数仓储"""

    def __init__(self, session: AsyncSession):
        super().__init__(Api2mcpParameter, session)

    async def create_parameter(self, tool_id: str, **kwargs) -> Api2mcpParameter:
        """创建参数"""
        if 'id' not in kwargs:
            kwargs['id'] = str(uuid4())
        kwargs['tool_id'] = tool_id
        return await self.create(**kwargs)

    async def get_parameters_by_tool(self, tool_id: str) -> List[Api2mcpParameter]:
        """获取工具的所有参数"""
        result = await self.session.execute(
            select(Api2mcpParameter)
            .where(Api2mcpParameter.tool_id == tool_id)
            .order_by(Api2mcpParameter.sort_order)
        )
        return list(result.scalars().all())

    async def get_parameter_by_id(
        self, param_id: str, tool_id: str
    ) -> Optional[Api2mcpParameter]:
        """根据 ID 获取参数"""
        result = await self.session.execute(
            select(Api2mcpParameter)
            .where(Api2mcpParameter.id == param_id)
            .where(Api2mcpParameter.tool_id == tool_id)
        )
        return result.scalar_one_or_none()

    async def get_root_parameters(self, tool_id: str) -> List[Api2mcpParameter]:
        """获取顶级参数（无父参数的参数）"""
        result = await self.session.execute(
            select(Api2mcpParameter)
            .where(Api2mcpParameter.tool_id == tool_id)
            .where(Api2mcpParameter.parent_id == None)
            .order_by(Api2mcpParameter.sort_order)
        )
        return list(result.scalars().all())

    async def get_child_parameters(self, parent_id: str) -> List[Api2mcpParameter]:
        """获取子参数"""
        result = await self.session.execute(
            select(Api2mcpParameter)
            .where(Api2mcpParameter.parent_id == parent_id)
            .order_by(Api2mcpParameter.sort_order)
        )
        return list(result.scalars().all())

    async def delete_parameter_cascade(self, param_id: str) -> bool:
        """删除参数及其子参数（级联删除）"""
        # 先删除子参数
        await self.session.execute(
            delete(Api2mcpParameter).where(Api2mcpParameter.parent_id == param_id)
        )
        # 再删除参数本身
        await self.session.execute(
            delete(Api2mcpParameter).where(Api2mcpParameter.id == param_id)
        )
        await self.session.commit()
        return True

    async def delete_parameters_by_tool(self, tool_id: str) -> bool:
        """删除工具的所有参数"""
        await self.session.execute(
            delete(Api2mcpParameter).where(Api2mcpParameter.tool_id == tool_id)
        )
        await self.session.commit()
        return True
