"""
基础信息服务 - 处理基础信息相关的业务逻辑
"""
import logging
import uuid
from typing import List, Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from ...database import async_session_maker
from ..entities.tool import Api2mcpBaseinfo
from ..entities.parameter import Api2mcpParameter
from ..repositories.tool_repository import BaseinfoRepository
from ..repositories.parameter_repository import ParameterRepository
from ...config import settings

logger = logging.getLogger(__name__)

# 语义标签常量
SEMANTIC_TAGS = [
    {"value": "like", "label": "Multi-field fuzzy match"},
    {"value": "min", "label": "Minimum value comparison"},
    {"value": "max", "label": "Maximum value comparison"},
    {"value": "date_range_start", "label": "Date range start"},
    {"value": "date_range_end", "label": "Date range end"},
    {"value": "exact", "label": "Exact match"},
    {"value": "in", "label": "In list"},
    {"value": "between", "label": "Range between"},
]


class BaseinfoService:
    """基础信息服务"""

    def __init__(self, session: Optional[AsyncSession] = None):
        self.session = session  # 如果为 None，方法内部会使用 async_session_maker()

    async def create_baseinfo(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建基础信息"""
        async with async_session_maker() as session:
            repo = BaseinfoRepository(session)

            # 验证 MCP 名称+版本唯一性
            if await repo.exists_by_name_and_version(data['mcp_name'], data['version']):
                raise ValueError(
                    f"MCP name and version combination already exists: "
                    f"{data['mcp_name']}@{data['version']}"
                )

            baseinfo_id = str(uuid.uuid4())

            # 处理空的 auth_config_id
            auth_config_id = data.get('auth_config_id') or None

            # 处理传输协议，确保至少有一个
            transport_modes = data.get('transport_modes') or ["streamable_http"]

            baseinfo = await repo.create_baseinfo(
                id=baseinfo_id,
                mcp_name=data['mcp_name'],
                version=data.get('version', 'v1'),
                tool_description=data.get('tool_description'),
                category=data.get('category'),
                tags=data.get('tags', []),
                method=data['method'],
                api_fullurl=data['api_fullurl'],
                content_type=data.get('content_type', 'application/json'),
                mcp_fullurl=data.get('mcp_fullurl'),
                output_fields=data.get('output_fields', {}),
                output_template=data.get('output_template'),
                usage_examples=data.get('usage_examples', {}),
                cache_ttl=data.get('cache_ttl', 0),
                timeout_ms=data.get('timeout_ms', settings.TOOL_DEFAULT_TIMEOUT_MS),
                status=data.get('status', 'active'),
                auth_config_id=auth_config_id,
                transport_modes=transport_modes,
                created_by=settings.DEFAULT_USER_ID,
                updated_by=settings.DEFAULT_USER_ID,
            )

            return {
                "status": "ok",
                "baseinfo_id": baseinfo.id,
                "mcp_name": baseinfo.mcp_name,
                "version": baseinfo.version
            }

    async def list_baseinfos(
        self,
        category: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """获取基础信息列表"""
        async with async_session_maker() as session:
            repo = BaseinfoRepository(session)
            baseinfos = await repo.get_baseinfos_filtered(category, status, search)
            return [self._baseinfo_to_dict(t) for t in baseinfos]

    async def get_baseinfo(self, baseinfo_id: str) -> Optional[Dict[str, Any]]:
        """获取基础信息详情"""
        async with async_session_maker() as session:
            repo = BaseinfoRepository(session)
            param_repo = ParameterRepository(session)

            baseinfo = await repo.get_by_id(baseinfo_id)
            if not baseinfo:
                return None

            parameters = await param_repo.get_parameters_by_baseinfo(baseinfo_id)

            result = self._baseinfo_to_dict(baseinfo)
            result["parameters"] = [self._parameter_to_dict(p) for p in parameters]
            return result

    async def update_baseinfo(
        self, baseinfo_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """更新基础信息配置"""
        async with async_session_maker() as session:
            repo = BaseinfoRepository(session)
            baseinfo = await repo.get_by_id(baseinfo_id)
            if not baseinfo:
                raise ValueError("Baseinfo not found")

            # 验证 MCP 名称+版本唯一性（如果更改）
            new_mcp_name = data.get('mcp_name', baseinfo.mcp_name)
            new_version = data.get('version', baseinfo.version)
            if new_mcp_name != baseinfo.mcp_name or new_version != baseinfo.version:
                if await repo.exists_by_name_and_version(new_mcp_name, new_version):
                    raise ValueError(
                        f"MCP name and version combination already exists: "
                        f"{new_mcp_name}@{new_version}"
                    )

            # 构建更新数据
            update_data = {}
            for field in [
                "mcp_name", "version", "tool_description", "category", "tags",
                "method", "api_fullurl", "content_type", "mcp_fullurl",
                "output_fields", "output_template", "usage_examples",
                "cache_ttl", "timeout_ms", "status",
            ]:
                if field in data and data[field] is not None:
                    update_data[field] = data[field]

            # 处理 auth_config_id
            if 'auth_config_id' in data:
                update_data['auth_config_id'] = data['auth_config_id'] if data['auth_config_id'] else None

            # 处理传输协议
            if 'transport_modes' in data:
                if data['transport_modes'] and len(data['transport_modes']) > 0:
                    update_data['transport_modes'] = data['transport_modes']
                else:
                    update_data['transport_modes'] = ["streamable_http"]

            update_data['updated_by'] = settings.DEFAULT_USER_ID

            await repo.update(baseinfo_id, **update_data)
            return {"status": "ok"}

    async def delete_baseinfo(self, baseinfo_id: str) -> Dict[str, Any]:
        """删除基础信息及其所有参数"""
        async with async_session_maker() as session:
            repo = BaseinfoRepository(session)
            param_repo = ParameterRepository(session)

            baseinfo = await repo.get_by_id(baseinfo_id)
            if not baseinfo:
                raise ValueError("Baseinfo not found")

            # 删除参数
            await param_repo.delete_parameters_by_baseinfo(baseinfo_id)

            # 删除基础信息
            await repo.delete(baseinfo_id)

            return {"status": "ok", "baseinfo_id": baseinfo_id}

    async def get_mcp_definition(self, baseinfo_id: str) -> Optional[Dict[str, Any]]:
        """获取 MCP 定义预览"""
        async with async_session_maker() as session:
            repo = BaseinfoRepository(session)
            param_repo = ParameterRepository(session)

            baseinfo = await repo.get_by_id(baseinfo_id)
            if not baseinfo:
                return None

            parameters = await param_repo.get_parameters_by_baseinfo(baseinfo_id)

            input_schema = self._build_input_schema(parameters)
            output_schema = self._build_output_schema(baseinfo.output_fields or {})
            description = self._build_baseinfo_description(baseinfo)

            return {
                "name": baseinfo.mcp_name,
                "description": description,
                "inputSchema": input_schema,
                "outputSchema": output_schema,
                "transportModes": baseinfo.transport_modes or ["streamable_http"],
            }

    def _baseinfo_to_dict(self, baseinfo: Api2mcpBaseinfo) -> Dict[str, Any]:
        """将基础信息实体转换为字典"""
        return {
            "id": baseinfo.id,
            "mcp_name": baseinfo.mcp_name,
            "version": baseinfo.version,
            "tool_description": baseinfo.tool_description,
            "category": baseinfo.category,
            "tags": baseinfo.tags or [],
            "method": baseinfo.method,
            "api_fullurl": baseinfo.api_fullurl,
            "content_type": baseinfo.content_type,
            "mcp_fullurl": baseinfo.mcp_fullurl,
            "output_fields": baseinfo.output_fields or {},
            "output_template": baseinfo.output_template,
            "usage_examples": baseinfo.usage_examples or {},
            "cache_ttl": baseinfo.cache_ttl,
            "timeout_ms": baseinfo.timeout_ms,
            "status": baseinfo.status,
            "auth_config_id": baseinfo.auth_config_id,
            "transport_modes": baseinfo.transport_modes or ["streamable_http"],
            "created_at": baseinfo.created_at.isoformat() if baseinfo.created_at else None,
            "updated_at": baseinfo.updated_at.isoformat() if baseinfo.updated_at else None,
        }

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

    def _build_input_schema(self, parameters: List[Api2mcpParameter]) -> Dict[str, Any]:
        """构建输入 Schema"""
        properties = {}
        required = []

        params_by_parent: Dict[str, List[Api2mcpParameter]] = {}
        for param in parameters:
            parent_id = param.parent_id or "root"
            if parent_id not in params_by_parent:
                params_by_parent[parent_id] = []
            params_by_parent[parent_id].append(param)

        def build_property(param: Api2mcpParameter) -> Dict[str, Any]:
            prop = {"type": param.param_type}

            description_parts = []
            if param.description:
                description_parts.append(param.description)
            if param.semantic_tag:
                tag_label = next(
                    (t["label"] for t in SEMANTIC_TAGS if t["value"] == param.semantic_tag),
                    None
                )
                if tag_label:
                    description_parts.append(f"Semantic: {tag_label}")
            if param.unit:
                description_parts.append(f"Unit: {param.unit}")
            if param.example_value:
                description_parts.append(f"Example: {param.example_value}")

            if description_parts:
                prop["description"] = " ".join(description_parts)

            if param.example_value:
                prop["example"] = param.example_value
            if param.default_value:
                prop["default"] = param.default_value
            if param.param_type == "array" and param.item_type:
                prop["items"] = {"type": param.item_type}
            if param.param_type == "object" and str(param.id) in params_by_parent:
                nested_params = params_by_parent[str(param.id)]
                nested_schema = _build_nested_schema(nested_params, params_by_parent)
                prop["properties"] = nested_schema.get("properties", {})
                prop["required"] = nested_schema.get("required", [])

            return prop

        def _build_nested_schema(
            params: List[Api2mcpParameter],
            all_params: Dict[str, List[Api2mcpParameter]]
        ) -> Dict[str, Any]:
            schema = {"type": "object", "properties": {}}
            required_fields = []

            for param in params:
                schema["properties"][param.param_name] = build_property(param)
                if param.required:
                    required_fields.append(param.param_name)
                if param.param_type == "object" and str(param.id) in all_params:
                    nested = _build_nested_schema(all_params[str(param.id)], all_params)
                    schema["properties"][param.param_name]["properties"] = nested.get("properties", {})
                    schema["properties"][param.param_name]["required"] = nested.get("required", [])

            if required_fields:
                schema["required"] = required_fields
            return schema

        root_params = params_by_parent.get("root", [])
        for param in root_params:
            properties[param.param_name] = build_property(param)
            if param.required:
                required.append(param.param_name)

        schema = {"type": "object", "properties": properties}
        if required:
            schema["required"] = required
        return schema

    def _build_output_schema(self, output_fields: Dict[str, Any]) -> Dict[str, Any]:
        """构建输出 Schema"""
        properties = {}
        for field_name, field_config in output_fields.items():
            prop = {"type": field_config.get("type", "string")}
            if "description" in field_config:
                prop["description"] = field_config["description"]
            properties[field_name] = prop
        return {"type": "object", "properties": properties}

    def _build_baseinfo_description(self, baseinfo: Api2mcpBaseinfo) -> str:
        """构建基础信息描述"""
        import json
        description = baseinfo.tool_description or "API tool call"
        if baseinfo.usage_examples:
            examples = baseinfo.usage_examples.get("examples", [])
            if examples:
                description += "\n\nUsage Examples:\n"
                for i, example in enumerate(examples[:3], 1):
                    user_question = example.get("question", "")
                    tool_call = example.get("params", {})
                    description += f"{i}. User asks: {user_question}\n   Call params: {json.dumps(tool_call)}\n"
        return description

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