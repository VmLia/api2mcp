"""
工具仓储 - 处理工具数据的数据库操作
"""
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import select, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..model.entity.tool import Api2mcpTool
from .base_repository import BaseRepository


class ToolRepository(BaseRepository[Api2mcpTool]):
    """工具仓储"""

    def __init__(self, session: AsyncSession):
        super().__init__(Api2mcpTool, session)

    async def create_tool(self, **kwargs) -> Api2mcpTool:
        """创建工具"""
        if 'id' not in kwargs:
            kwargs['id'] = str(uuid4())
        return await self.create(**kwargs)

    async def get_by_name_and_version(
        self, tool_name: str, version: str
    ) -> Optional[Api2mcpTool]:
        """根据工具名和版本获取工具"""
        result = await self.session.execute(
            select(Api2mcpTool).where(
                and_(
                    Api2mcpTool.tool_name == tool_name,
                    Api2mcpTool.version == version
                )
            )
        )
        return result.scalar_one_or_none()

    async def exists_by_name_and_version(
        self, tool_name: str, version: str
    ) -> bool:
        """检查工具名和版本组合是否存在"""
        result = await self.session.execute(
            select(Api2mcpTool).where(
                and_(
                    Api2mcpTool.tool_name == tool_name,
                    Api2mcpTool.version == version
                )
            )
        )
        return result.scalar_one_or_none() is not None

    async def get_active_tools(self) -> List[Api2mcpTool]:
        """获取所有活跃的工具"""
        result = await self.session.execute(
            select(Api2mcpTool)
            .where(Api2mcpTool.status == "active")
            .order_by(Api2mcpTool.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_tools_filtered(
        self,
        category: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[Api2mcpTool]:
        """根据条件过滤获取工具列表"""
        query = select(Api2mcpTool)

        if category:
            query = query.where(Api2mcpTool.category == category)
        if status:
            query = query.where(Api2mcpTool.status == status)
        if search:
            query = query.where(Api2mcpTool.tool_name.ilike(f"%{search}%"))

        query = query.order_by(Api2mcpTool.created_at.desc())
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_name(
        self,
        tool_name: str,
        version: Optional[str] = None
    ) -> Optional[Api2mcpTool]:
        """根据工具名获取工具，支持指定版本"""
        query = select(Api2mcpTool).where(
            Api2mcpTool.tool_name == tool_name,
            Api2mcpTool.status == "active"
        )
        if version:
            query = query.where(Api2mcpTool.version == version)
        else:
            # 如果没有指定版本，优先返回 v1 版本
            query = query.order_by(Api2mcpTool.version)

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def delete_tool_and_parameters(self, tool_id: str) -> bool:
        """删除工具及其所有参数"""
        # 先删除参数
        await self.session.execute(
            delete(Api2mcpTool).where(Api2mcpTool.id == tool_id)
        )
        await self.session.execute(
            delete(Api2mcpTool).where(Api2mcpTool.id == tool_id)
        )
        # 注意：参数通过外键级联删除，这里需要显式删除参数表
        from ..model.entity.parameter import Api2mcpParameter
        await self.session.execute(
            delete(Api2mcpParameter).where(Api2mcpParameter.tool_id == tool_id)
        )
        await self.session.commit()
        return True
