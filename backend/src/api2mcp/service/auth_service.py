"""
鉴权服务 - 处理鉴权配置相关的业务逻辑
"""
import uuid
import logging
from typing import List, Dict, Any

from ..database import async_session_maker
from ..model.entity.auth_config import Api2mcpAuthConfig
from ..repository.auth_config_repository import AuthConfigRepository
from ..config import settings

logger = logging.getLogger(__name__)


class AuthService:
    """鉴权服务"""

    async def create_auth_config(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建鉴权配置"""
        async with async_session_maker() as session:
            repo = AuthConfigRepository(session)

            config_id = str(uuid.uuid4())
            config = await repo.create_auth_config(
                id=config_id,
                name=data['name'],
                auth_type=data.get('auth_type', 'none'),
                config=data.get('config', {}),
                created_by=settings.DEFAULT_USER_ID,
            )

            return {"status": "ok", "auth_config_id": config.id}

    async def list_auth_configs(self) -> List[Dict[str, Any]]:
        """获取所有鉴权配置"""
        async with async_session_maker() as session:
            repo = AuthConfigRepository(session)
            configs = await repo.get_all_configs()
            return [self._config_to_dict(c) for c in configs]

    async def delete_auth_config(self, config_id: str) -> Dict[str, Any]:
        """删除鉴权配置"""
        async with async_session_maker() as session:
            repo = AuthConfigRepository(session)

            config = await repo.get_by_id(config_id)
            if not config:
                raise ValueError("Auth config not found")

            # 检查是否被工具使用
            if await repo.is_using_by_tools(config_id):
                raise ValueError(
                    "This configuration is being used by tools and cannot be deleted"
                )

            await repo.delete(config_id)
            return {"status": "ok"}

    def _config_to_dict(self, config: Api2mcpAuthConfig) -> Dict[str, Any]:
        """将鉴权配置实体转换为字典"""
        return {
            "id": config.id,
            "name": config.name,
            "auth_type": config.auth_type,
            "config": config.config,
            "created_at": config.created_at.isoformat() if config.created_at else None,
        }
