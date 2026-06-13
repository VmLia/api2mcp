"""
基础仓储类 - 提供通用的 CRUD 操作
"""
from typing import TypeVar, Generic, Type, Optional, List, Any
from uuid import uuid4

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import Base

# 泛型类型变量
T = TypeVar('T', bound=Base)


class BaseRepository(Generic[T]):
    """
    基础仓储类 - 提供通用的数据库操作

    使用方式:
    ```python
    class UserRepository(BaseRepository[User]):
        def __init__(self, session: AsyncSession):
            super().__init__(User, session)
    ```
    """

    def __init__(self, model: Type[T], session: AsyncSession):
        """
        初始化仓储

        Args:
            model: SQLAlchemy 模型类
            session: 异步数据库会话
        """
        self.model = model
        self.session = session

    async def create(self, **kwargs) -> T:
        """创建新记录"""
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.commit()
        await self.session.refresh(instance)
        return instance

    async def get_by_id(self, id: str) -> Optional[T]:
        """根据 ID 获取记录"""
        result = await self.session.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def get_all(self) -> List[T]:
        """获取所有记录"""
        result = await self.session.execute(select(self.model))
        return list(result.scalars().all())

    async def update(self, id: str, **kwargs) -> Optional[T]:
        """更新记录"""
        instance = await self.get_by_id(id)
        if instance:
            for key, value in kwargs.items():
                if value is not None and hasattr(instance, key):
                    setattr(instance, key, value)
            await self.session.commit()
            await self.session.refresh(instance)
        return instance

    async def delete(self, id: str) -> bool:
        """删除记录"""
        instance = await self.get_by_id(id)
        if instance:
            await self.session.delete(instance)
            await self.session.commit()
            return True
        return False

    async def count(self) -> int:
        """统计记录数"""
        result = await self.session.execute(
            select(func.count()).select_from(self.model)
        )
        return result.scalar()

    async def exists(self, id: str) -> bool:
        """检查记录是否存在"""
        result = await self.session.execute(
            select(func.count()).select_from(self.model).where(self.model.id == id)
        )
        return result.scalar() > 0
