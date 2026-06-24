"""
参数服务 - 处理参数相关的业务逻辑
"""
import uuid
import logging
from typing import List, Optional, Dict, Any

from ...database import async_session_maker
from ..entities.parameter import Api2mcpParameter
from ..repositories.parameter_repository import ParameterRepository
from ..repositories.tool_repository import BaseinfoRepository

logger = logging.getLogger(__name__)


class ParameterService:
    """参数服务"""

    async def create_parameter(
        self, baseinfo_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """创建参数"""
        async with async_session_maker() as session:
            baseinfo_repo = BaseinfoRepository(session)
            param_repo = ParameterRepository(session)

            # 验证基础信息存在
            baseinfo = await baseinfo_repo.get_by_id(baseinfo_id)
            if not baseinfo:
                raise ValueError("Baseinfo not found")

            param_id = str(uuid.uuid4())
            param = await param_repo.create_parameter(
                id=param_id,
                baseinfo_id=baseinfo_id,
                parent_id=data.get('parent_id'),
                param_name=data['param_name'],
                param_location=data['param_location'],
                param_type=data['param_type'],
                item_type=data.get('item_type'),
                required=data.get('required', False),
                description=data.get('description'),
                default_value=data.get('default_value'),
                example_value=data.get('example_value'),
                unit=data.get('unit'),
                semantic_tag=data.get('semantic_tag'),
                sort_order=data.get('sort_order', 0),
            )

            return {"status": "ok", "parameter_id": param.id}

    async def list_parameters(self, baseinfo_id: str) -> List[Dict[str, Any]]:
        """获取基础信息的参数列表（树结构）"""
        async with async_session_maker() as session:
            param_repo = ParameterRepository(session)
            parameters = await param_repo.get_parameters_by_baseinfo(baseinfo_id)
            return self._build_parameter_tree(parameters)

    async def update_parameter(
        self, baseinfo_id: str, param_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """更新参数"""
        async with async_session_maker() as session:
            param_repo = ParameterRepository(session)

            param = await param_repo.get_parameter_by_id(param_id, baseinfo_id)
            if not param:
                raise ValueError("Parameter not found")

            # 构建更新数据
            update_data = {}
            for field in [
                "param_name", "param_location", "param_type", "item_type",
                "required", "description", "default_value", "example_value",
                "unit", "semantic_tag", "sort_order",
            ]:
                if field in data and data[field] is not None:
                    update_data[field] = data[field]

            await param_repo.update(param_id, **update_data)
            return {"status": "ok"}

    async def delete_parameter(
        self, baseinfo_id: str, param_id: str
    ) -> Dict[str, Any]:
        """删除参数（级联删除子参数）"""
        async with async_session_maker() as session:
            param_repo = ParameterRepository(session)

            param = await param_repo.get_parameter_by_id(param_id, baseinfo_id)
            if not param:
                raise ValueError("Parameter not found")

            await param_repo.delete_parameter_cascade(param_id)
            return {"status": "ok"}

    def _parameter_to_dict(self, param: Api2mcpParameter) -> Dict[str, Any]:
        """将参数实体转换为字典"""
        return {
            "id": param.id,
            "baseinfo_id": param.baseinfo_id,
            "parent_id": param.parent_id,
            "param_name": param.param_name,
            "param_location": param.param_location,
            "param_type": param.param_type,
            "item_type": param.item_type,
            "required": param.required,
            "description": param.description,
            "default_value": param.default_value,
            "example_value": param.example_value,
            "unit": param.unit,
            "semantic_tag": param.semantic_tag,
            "sort_order": param.sort_order,
        }

    def _build_parameter_tree(
        self, parameters: List[Api2mcpParameter]
    ) -> List[Dict[str, Any]]:
        """将平铺的参数列表转换为树结构"""
        param_dict = {p.id: self._parameter_to_dict(p) for p in parameters}
        root_params = []

        for param in parameters:
            if param.parent_id:
                parent = param_dict.get(param.parent_id)
                if parent:
                    if "children" not in parent:
                        parent["children"] = []
                    parent["children"].append(param_dict[param.id])
            else:
                root_params.append(param_dict[param.id])

        def sort_children(params):
            params.sort(key=lambda x: x["sort_order"])
            for p in params:
                if "children" in p:
                    sort_children(p["children"])
            return params

        return sort_children(root_params)