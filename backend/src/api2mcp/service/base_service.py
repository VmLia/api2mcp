"""
基础服务类 - 提供通用的业务逻辑基类
"""
from typing import Generic, TypeVar, Type
from sqlalchemy.ext.asyncio import AsyncSession

from ..repository.base_repository import BaseRepository

# 泛型类型变量
T = TypeVar('T')


class BaseService(Generic[T]):
    """
    基础服务类 - 提供通用的业务逻辑

    使用方式:
    ```python
    class UserService(BaseService[User]):
        def __init__(self, repository: UserRepository):
            super().__init__(UserRepository)
    ```
    """

    def __init__(self, repository_class: Type[BaseRepository]):
        """
        初始化服务

        Args:
            repository_class: 仓储类
        """
        self.repository_class = repository_class

    def get_repository(self, session: AsyncSession) -> BaseRepository:
        """获取仓储实例"""
        return self.repository_class(session)
