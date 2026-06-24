"""
基础信息仓储 - 处理基础信息数据的数据库操作
"""
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import select, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..entities.tool import Api2mcpBaseinfo
from .base_repository import BaseRepository


class BaseinfoRepository(BaseRepository[Api2mcpBaseinfo]):
    """基础信息仓储"""

    def __init__(self, session: AsyncSession):
        super().__init__(Api2mcpBaseinfo, session)

    async def create_baseinfo(self, **kwargs) -> Api2mcpBaseinfo:
        """创建基础信息"""
        if 'id' not in kwargs:
            kwargs['id'] = str(uuid4())
        return await self.create(**kwargs)

    async def get_by_name_and_version(
        self, mcp_name: str, version: str
    ) -> Optional[Api2mcpBaseinfo]:
        """根据 MCP 名称和版本获取基础信息"""
        result = await self.session.execute(
            select(Api2mcpBaseinfo).where(
                and_(
                    Api2mcpBaseinfo.mcp_name == mcp_name,
                    Api2mcpBaseinfo.version == version
                )
            )
        )
        return result.scalar_one_or_none()

    async def exists_by_name_and_version(
        self, mcp_name: str, version: str
    ) -> bool:
        """检查 MCP 名称和版本组合是否存在"""
        result = await self.session.execute(
            select(Api2mcpBaseinfo).where(
                and_(
                    Api2mcpBaseinfo.mcp_name == mcp_name,
                    Api2mcpBaseinfo.version == version
                )
            )
        )
        return result.scalar_one_or_none() is not None

    async def get_active_baseinfos(self) -> List[Api2mcpBaseinfo]:
        """获取所有活跃的基础信息"""
        result = await self.session.execute(
            select(Api2mcpBaseinfo)
            .where(Api2mcpBaseinfo.status == "active")
            .order_by(Api2mcpBaseinfo.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_baseinfos_filtered(
        self,
        category: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[Api2mcpBaseinfo]:
        """根据条件过滤获取基础信息列表"""
        query = select(Api2mcpBaseinfo)

        if category:
            query = query.where(Api2mcpBaseinfo.category == category)
        if status:
            query = query.where(Api2mcpBaseinfo.status == status)
        if search:
            query = query.where(Api2mcpBaseinfo.mcp_name.ilike(f"%{search}%"))

        query = query.order_by(Api2mcpBaseinfo.created_at.desc())
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_name(
        self,
        mcp_name: str,
        version: Optional[str] = None
    ) -> Optional[Api2mcpBaseinfo]:
        """根据 MCP 名称获取基础信息，支持指定版本"""
        query = select(Api2mcpBaseinfo).where(
            Api2mcpBaseinfo.mcp_name == mcp_name,
            Api2mcpBaseinfo.status == "active"
        )
        if version:
            query = query.where(Api2mcpBaseinfo.version == version)
        else:
            # 如果没有指定版本，优先返回 v1 版本
            query = query.order_by(Api2mcpBaseinfo.version)

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def delete_baseinfo_and_parameters(self, baseinfo_id: str) -> bool:
        """删除基础信息及其所有参数"""
        # 先删除参数
        from ..entities.parameter import Api2mcpParameter
        await self.session.execute(
            delete(Api2mcpParameter).where(Api2mcpParameter.baseinfo_id == baseinfo_id)
        )
        await self.session.execute(
            delete(Api2mcpBaseinfo).where(Api2mcpBaseinfo.id == baseinfo_id)
        )
        await self.session.commit()
        return True