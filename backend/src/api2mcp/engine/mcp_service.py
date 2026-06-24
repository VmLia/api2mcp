"""
MCP 服务 - 处理 MCP 协议相关的业务逻辑
"""
import json
import logging
import base64
from typing import Dict, Any, List, Optional

import httpx
from sqlalchemy import select

from ..database import async_session_maker
from ..api_registry.entities.tool import Api2mcpBaseinfo
from ..api_registry.entities.parameter import Api2mcpParameter
from ..api_registry.entities.auth_config import Api2mcpAuthConfig
from ..api_registry.entities.env_variable import Api2mcpEnvVariable
from ..config import settings

logger = logging.getLogger(__name__)


class MCPService:
    """MCP 协议服务"""

    def __init__(self):
        self.http_client = httpx.AsyncClient(timeout=httpx.Timeout(settings.HTTP_CLIENT_TIMEOUT))

    async def resolve_env_variables(
        self, value: str, tool_id: Optional[str] = None
    ) -> str:
        """解析环境变量引用，例如 {{API_KEY}}"""
        if not value or "{{" not in value:
            return value

        async with async_session_maker() as session:
            query = select(Api2mcpEnvVariable)
            if tool_id:
                query = query.where(
                    (Api2mcpEnvVariable.scope == "global") |
                    (Api2mcpEnvVariable.baseinfo_id == tool_id)
                )
            else:
                query = query.where(Api2mcpEnvVariable.scope == "global")

            result = await session.execute(query)
            variables = result.scalars().all()
            var_dict = {var.key: var.value for var in variables}

        # 替换所有环境变量引用
        result = value
        for key, val in var_dict.items():
            result = result.replace(f"{{{{{key}}}}}", val)

        return result

    async def build_request_url(
        self, tool: Api2mcpBaseinfo, arguments: Dict[str, Any]
    ) -> str:
        """构建请求 URL（处理路径参数）"""
        if not tool.api_fullurl or not tool.api_fullurl.strip():
            raise ValueError(
                f"Tool '{tool.mcp_name}@{tool.version}' api_fullurl is not configured. "
                "Please configure the API full URL in the management page first"
            )

        # 确保 api_fullurl 以 http:// 或 https:// 开头
        url = tool.api_fullurl.strip()
        if not url.startswith(('http://', 'https://')):
            url = f"http://{url}"

        # 替换路径参数，例如 /api/v1/projects/{id}
        for key, value in arguments.items():
            url = url.replace(f"{{{key}}}", str(value))

        return url

    async def build_request_headers(
        self, tool: Api2mcpBaseinfo
    ) -> Dict[str, str]:
        """构建请求头"""
        headers = {
            "Content-Type": tool.content_type,
            "Accept": "application/json",
        }

        # 如果有鉴权配置，添加认证头
        if tool.auth_config_id:
            async with async_session_maker() as session:
                result = await session.execute(
                    select(Api2mcpAuthConfig).where(
                        Api2mcpAuthConfig.id == tool.auth_config_id
                    )
                )
                auth_config = result.scalar_one_or_none()

                if auth_config:
                    auth_type = auth_config.auth_type
                    config = auth_config.config

                    if auth_type == "api_key":
                        header_name = config.get("header_name", "X-API-Key")
                        api_key = await self.resolve_env_variables(
                            config.get("api_key", ""), tool.id
                        )
                        headers[header_name] = api_key

                    elif auth_type == "bearer_token":
                        token = await self.resolve_env_variables(
                            config.get("token", ""), tool.id
                        )
                        headers["Authorization"] = f"Bearer {token}"

                    elif auth_type == "basic_auth":
                        username = await self.resolve_env_variables(
                            config.get("username", ""), tool.id
                        )
                        password = await self.resolve_env_variables(
                            config.get("password", ""), tool.id
                        )
                        auth = base64.b64encode(
                            f"{username}:{password}".encode()
                        ).decode()
                        headers["Authorization"] = f"Basic {auth}"

        return headers

    async def extract_params_by_location(
        self,
        parameters: List[Api2mcpParameter],
        arguments: Dict[str, Any],
        location: str
    ) -> Dict[str, Any]:
        """根据位置提取参数"""
        result = {}
        for param in parameters:
            if param.param_location == location and param.param_name in arguments:
                value = arguments[param.param_name]
                # 类型转换
                if param.param_type == "integer":
                    value = int(value)
                elif param.param_type == "number":
                    value = float(value)
                elif param.param_type == "boolean":
                    value = bool(value)
                result[param.param_name] = value
        return result

    async def execute_api_call(
        self, tool: Api2mcpBaseinfo, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行实际 API 调用"""
        async with async_session_maker() as session:
            result = await session.execute(
                select(Api2mcpParameter).where(Api2mcpParameter.baseinfo_id == tool.id)
            )
            parameters = result.scalars().all()

        # 构建 URL
        url = await self.build_request_url(tool, arguments)

        # 构建请求头
        headers = await self.build_request_headers(tool)

        # 按位置提取参数
        query_params = await self.extract_params_by_location(
            parameters, arguments, "query"
        )
        path_params = await self.extract_params_by_location(
            parameters, arguments, "path"
        )
        body_params = await self.extract_params_by_location(
            parameters, arguments, "body"
        )
        header_params = await self.extract_params_by_location(
            parameters, arguments, "header"
        )

        # 将 header 参数添加到请求头
        headers.update(header_params)

        try:
            timeout = tool.timeout_ms / 1000 if tool.timeout_ms else 30

            if tool.method.upper() == "GET":
                response = await self.http_client.get(
                    url,
                    params={**query_params, **path_params},
                    headers=headers,
                    timeout=timeout
                )

            elif tool.method.upper() == "POST":
                response = await self.http_client.post(
                    url,
                    params=query_params,
                    json=body_params if body_params else arguments,
                    headers=headers,
                    timeout=timeout
                )

            elif tool.method.upper() == "PUT":
                response = await self.http_client.put(
                    url,
                    params=query_params,
                    json=body_params if body_params else arguments,
                    headers=headers,
                    timeout=timeout
                )

            elif tool.method.upper() == "DELETE":
                response = await self.http_client.delete(
                    url,
                    params=query_params,
                    headers=headers,
                    timeout=timeout
                )

            else:
                raise ValueError(f"Unsupported HTTP method: {tool.method}")

            response.raise_for_status()
            return response.json()

        except httpx.HTTPError as e:
            raise ValueError(f"API call failed: {str(e)}")
        except Exception as e:
            raise ValueError(f"Request processing failed: {str(e)}")

    def apply_output_template(
        self, data: Dict[str, Any], template: Optional[str]
    ) -> Any:
        """应用 JMESPath 输出模板"""
        if not template:
            return data

        try:
            import jmespath
            return jmespath.search(template, data)
        except ImportError:
            return data
        except Exception as e:
            return {"error": f"JMESPath parsing failed: {str(e)}", "original_data": data}

    async def get_tools(
        self, tool_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """获取所有活跃的工具定义"""
        async with async_session_maker() as session:
            query = select(Api2mcpBaseinfo).where(Api2mcpBaseinfo.status == "active")
            if tool_id:
                query = query.where(Api2mcpBaseinfo.id == tool_id)
            result = await session.execute(query)
            tools_from_db = result.scalars().all()

            tools = []
            for tool in tools_from_db:
                param_result = await session.execute(
                    select(Api2mcpParameter).where(
                        Api2mcpParameter.baseinfo_id == tool.id
                    )
                )
                parameters = param_result.scalars().all()

                properties = {}
                required = []
                for param in parameters:
                    prop = {"type": param.param_type}
                    if param.description:
                        prop["description"] = param.description
                    if param.example_value:
                        prop["example"] = param.example_value
                    if param.default_value:
                        prop["default"] = param.default_value
                    if param.param_type == "array" and param.item_type:
                        prop["items"] = {"type": param.item_type}
                    properties[param.param_name] = prop
                    if param.required:
                        required.append(param.param_name)

                input_schema = {"type": "object", "properties": properties}
                if required:
                    input_schema["required"] = required

                # 构建完整的工具名：mcp_name@version
                full_tool_name = f"{tool.mcp_name}@{tool.version}"

                tools.append({
                    "name": full_tool_name,
                    "description": tool.tool_description or f"Call {tool.method} {tool.api_fullurl}",
                    "inputSchema": input_schema,
                })

            return tools

    async def invoke_tool(
        self, mcp_name: str, arguments: Dict[str, Any], tool_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """调用工具"""
        # 解析工具名格式：mcp_name@version 或 mcp_name
        version = None
        if "@" in mcp_name:
            parts = mcp_name.rsplit("@", 1)
            mcp_name = parts[0]
            version = parts[1]

        async with async_session_maker() as session:
            query = select(Api2mcpBaseinfo).where(
                Api2mcpBaseinfo.mcp_name == mcp_name,
                Api2mcpBaseinfo.status == "active"
            )
            if version:
                query = query.where(Api2mcpBaseinfo.version == version)
            if tool_id:
                query = query.where(Api2mcpBaseinfo.id == tool_id)

            result = await session.execute(query)
            tool = result.scalar_one_or_none()

            if not tool:
                return {
                    "content": [{"type": "text", "text": f"Tool not found or not enabled: {mcp_name}"}],
                    "isError": True,
                }

            try:
                raw_response = await self.execute_api_call(tool, arguments)

                if tool.output_template:
                    processed = self.apply_output_template(
                        raw_response, tool.output_template
                    )
                else:
                    processed = raw_response

                if tool.output_fields:
                    filtered = {}
                    for field_name, field_config in tool.output_fields.items():
                        if field_name in processed:
                            filtered[field_name] = processed[field_name]
                    processed = filtered

                return {
                    "content": [
                        {"type": "text", "text": json.dumps(processed, ensure_ascii=False, indent=2)}
                    ],
                    "isError": False,
                }

            except Exception as e:
                return {
                    "content": [{"type": "text", "text": f"Tool call failed: {str(e)}"}],
                    "isError": True,
                }
