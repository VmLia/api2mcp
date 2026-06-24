"""
环境变量服务 - 处理环境变量相关的业务逻辑
"""
import uuid
import logging
from typing import List, Optional, Dict, Any

from ...database import async_session_maker
from ..entities.env_variable import Api2mcpEnvVariable
from ..repositories.env_variable_repository import EnvVariableRepository
from ...config import settings

logger = logging.getLogger(__name__)


class EnvVariableService:
    """环境变量服务"""

    async def create_env_variable(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建环境变量"""
        async with async_session_maker() as session:
            repo = EnvVariableRepository(session)

            # 检查键名唯一性
            if await repo.exists_by_key(data['key']):
                raise ValueError("Variable name already exists")

            var_id = str(uuid.uuid4())
            var = await repo.create_env_variable(
                id=var_id,
                key=data['key'],
                value=data['value'],
                scope=data.get('scope', 'global'),
                tool_id=data.get('tool_id'),
                description=data.get('description'),
                created_by=settings.DEFAULT_USER_ID,
            )

            return {"status": "ok", "variable_id": var.id}

    async def list_env_variables(
        self,
        scope: Optional[str] = None,
        tool_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """获取环境变量列表"""
        async with async_session_maker() as session:
            repo = EnvVariableRepository(session)
            vars = await repo.get_all_variables(scope, tool_id)
            return [self._var_to_dict(v) for v in vars]

    async def delete_env_variable(self, var_id: str) -> Dict[str, Any]:
        """删除环境变量"""
        async with async_session_maker() as session:
            repo = EnvVariableRepository(session)

            var = await repo.get_by_id(var_id)
            if not var:
                raise ValueError("Variable not found")

            await repo.delete(var_id)
            return {"status": "ok"}

    def _var_to_dict(self, var: Api2mcpEnvVariable) -> Dict[str, Any]:
        """将环境变量实体转换为字典"""
        return {
            "id": var.id,
            "key": var.key,
            "value": "***" if var.value else "",  # 隐藏敏感值
            "scope": var.scope,
            "baseinfo_id": var.baseinfo_id,
            "description": var.description,
            "created_at": var.created_at.isoformat() if var.created_at else None,
        }
