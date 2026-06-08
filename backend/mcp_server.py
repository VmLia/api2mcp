"""
MCP Server Implementation
Supports Streamable HTTP transport protocol

Core Features:
1. Streamable HTTP: Stateless design, each request is handled independently, returns pure JSON
2. Supports tool isolation by tool_name/version
3. Tool configurations are dynamically loaded from database
"""
import json
import httpx
from typing import Any, Dict, List, Optional, Union
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select

from database import async_session_maker
from api_info import Api2mcpProject, Api2mcpParameter, Api2mcpAuthConfig, Api2mcpEnvVariable
from config import settings

router = APIRouter(prefix="/mcpapi", tags=["MCP Server"])

# Global HTTP client
http_client = httpx.AsyncClient(timeout=httpx.Timeout(60.0))


# ── MCP Protocol Models ──

class ToolCallRequest(BaseModel):
    """Tool call request"""
    tool_name: str
    arguments: Dict[str, Any]


class ToolCallResponse(BaseModel):
    """Tool call response - MCP standard format"""
    type: str = "text"
    text: Optional[str] = None
    data: Optional[str] = None
    mimeType: Optional[str] = None


class ToolInfo(BaseModel):
    """Tool information"""
    name: str
    description: str
    input_schema: Dict[str, Any]
    transport_modes: List[str] = ["streamable_http"]


class InvokeToolResponse(BaseModel):
    """Invoke tool response"""
    content: List[ToolCallResponse]
    isError: bool = False
    is_error: bool = False
    error_message: Optional[str] = None


class ListToolsResponse(BaseModel):
    """List tools response"""
    tools: List[ToolInfo]


# ── JSON-RPC 2.0 Models ──

class JSONRPCRequest(BaseModel):
    """JSON-RPC 2.0 request"""
    jsonrpc: str = "2.0"
    method: str
    params: Optional[Dict[str, Any]] = None
    id: Optional[Union[int, str]] = None


class JSONRPCError(BaseModel):
    """JSON-RPC 2.0 error"""
    code: int
    message: str
    data: Optional[Any] = None


class JSONRPCResponse(BaseModel):
    """JSON-RPC 2.0 response"""
    jsonrpc: str = "2.0"
    id: Optional[Union[int, str]] = None
    result: Optional[Any] = None
    error: Optional[JSONRPCError] = None


# ── AgentInfoResponse ──

class AgentInfoResponse(BaseModel):
    """Agent info response"""
    name: str = settings.PROJECT_NAME
    version: str = settings.PROJECT_VERSION
    protocol: str = "mcp"
    transport_modes: List[str] = ["streamable_http"]


# ── Helper Functions ──

async def _resolve_env_variables(value: str, project_id: Optional[str] = None) -> str:
    """Resolve environment variable references, e.g., {{API_KEY}}"""
    if not value or "{{" not in value:
        return value
    
    async with async_session_maker() as session:
        query = select(Api2mcpEnvVariable)
        if project_id:
            query = query.where(
                (Api2mcpEnvVariable.scope == "global") |
                (Api2mcpEnvVariable.project_id == project_id)
            )
        else:
            query = query.where(Api2mcpEnvVariable.scope == "global")
        
        result = await session.execute(query)
        variables = result.scalars().all()
        var_dict = {var.key: var.value for var in variables}
    
    # Replace all environment variable references
    result = value
    for key, val in var_dict.items():
        result = result.replace(f"{{{{{key}}}}}", val)
    
    return result


async def _build_request_url(project: Api2mcpProject, arguments: Dict[str, Any]) -> str:
    """Build request URL (handle path parameters)"""
    # Check if base_url is configured
    if not project.base_url or not project.base_url.strip():
        raise ValueError(f"Tool '{project.tool_name}@{project.version}' base_url is not configured. Please configure the API base URL in the management page first")
    
    # Ensure base_url starts with http:// or https://
    base_url = project.base_url.strip()
    if not base_url.startswith(('http://', 'https://')):
        base_url = f"http://{base_url}"
    
    # Ensure path starts with /
    path = project.path if project.path.startswith('/') else f"/{project.path}"
    
    url = f"{base_url}{path}"
    
    # Replace path parameters, e.g., /api/v1/projects/{id}
    for key, value in arguments.items():
        url = url.replace(f"{{{key}}}", str(value))
    
    return url


async def _build_request_headers(project: Api2mcpProject) -> Dict[str, str]:
    """Build request headers"""
    headers = {
        "Content-Type": project.content_type,
        "Accept": "application/json",
    }
    
    # If auth config exists, add authentication headers
    if project.auth_config_id:
        async with async_session_maker() as session:
            result = await session.execute(
                select(Api2mcpAuthConfig).where(Api2mcpAuthConfig.id == project.auth_config_id)
            )
            auth_config = result.scalar_one_or_none()
            
            if auth_config:
                auth_type = auth_config.auth_type
                config = auth_config.config
                
                if auth_type == "api_key":
                    header_name = config.get("header_name", "X-API-Key")
                    api_key = await _resolve_env_variables(config.get("api_key", ""), project.id)
                    headers[header_name] = api_key
                
                elif auth_type == "bearer_token":
                    token = await _resolve_env_variables(config.get("token", ""), project.id)
                    headers["Authorization"] = f"Bearer {token}"
                
                elif auth_type == "basic_auth":
                    username = await _resolve_env_variables(config.get("username", ""), project.id)
                    password = await _resolve_env_variables(config.get("password", ""), project.id)
                    import base64
                    auth = base64.b64encode(f"{username}:{password}".encode()).decode()
                    headers["Authorization"] = f"Basic {auth}"
    
    return headers


async def _extract_params_by_location(
    parameters: List[Api2mcpParameter],
    arguments: Dict[str, Any],
    location: str
) -> Dict[str, Any]:
    """Extract parameters by location"""
    result = {}
    for param in parameters:
        if param.param_location == location and param.param_name in arguments:
            value = arguments[param.param_name]
            # Type conversion
            if param.param_type == "integer":
                value = int(value)
            elif param.param_type == "number":
                value = float(value)
            elif param.param_type == "boolean":
                value = bool(value)
            result[param.param_name] = value
    return result


async def _execute_api_call(project: Api2mcpProject, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute actual API call"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Api2mcpParameter).where(Api2mcpParameter.project_id == project.id)
        )
        parameters = result.scalars().all()
    
    # Build URL
    url = await _build_request_url(project, arguments)
    
    # Build request headers
    headers = await _build_request_headers(project)
    
    # Extract parameters by location
    query_params = await _extract_params_by_location(parameters, arguments, "query")
    path_params = await _extract_params_by_location(parameters, arguments, "path")
    body_params = await _extract_params_by_location(parameters, arguments, "body")
    header_params = await _extract_params_by_location(parameters, arguments, "header")
    
    # Add header parameters to request headers
    headers.update(header_params)
    
    try:
        timeout = project.timeout_ms / 1000 if project.timeout_ms else 30
        
        if project.method.upper() == "GET":
            response = await http_client.get(
                url,
                params={**query_params, **path_params},
                headers=headers,
                timeout=timeout
            )
        
        elif project.method.upper() == "POST":
            response = await http_client.post(
                url,
                params=query_params,
                json=body_params if body_params else arguments,
                headers=headers,
                timeout=timeout
            )
        
        elif project.method.upper() == "PUT":
            response = await http_client.put(
                url,
                params=query_params,
                json=body_params if body_params else arguments,
                headers=headers,
                timeout=timeout
            )
        
        elif project.method.upper() == "DELETE":
            response = await http_client.delete(
                url,
                params=query_params,
                headers=headers,
                timeout=timeout
            )
        
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported HTTP method: {project.method}")
        
        response.raise_for_status()
        return response.json()
    
    except httpx.HTTPError as e:
        raise HTTPException(status_code=500, detail=f"API call failed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Request processing failed: {str(e)}")


def _apply_output_template(data: Dict[str, Any], template: Optional[str]) -> Any:
    """Apply JMESPath output template"""
    if not template:
        return data
    
    try:
        import jmespath
        return jmespath.search(template, data)
    except ImportError:
        return data
    except Exception as e:
        return {"error": f"JMESPath parsing failed: {str(e)}", "original_data": data}


async def _get_project_tools(project_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get all active tool definitions for project (JSON-RPC format)"""
    async with async_session_maker() as session:
        query = select(Api2mcpProject).where(Api2mcpProject.status == "active")
        if project_id:
            query = query.where(Api2mcpProject.id == project_id)
        result = await session.execute(query)
        projects = result.scalars().all()
        
        tools = []
        for project in projects:
            param_result = await session.execute(
                select(Api2mcpParameter).where(Api2mcpParameter.project_id == project.id)
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
            
            # Build full tool name: tool_name@version
            full_tool_name = f"{project.tool_name}@{project.version}"
            
            tools.append({
                "name": full_tool_name,
                "description": project.tool_description or f"Call {project.method} {project.path}",
                "inputSchema": input_schema,
            })
        
        return tools


def _make_jsonrpc_success(id: Any, result: Any) -> Dict[str, Any]:
    """Build JSON-RPC success response"""
    return {"jsonrpc": "2.0", "id": id, "result": result}


def _make_jsonrpc_error(id: Any, code: int, message: str, data: Any = None) -> Dict[str, Any]:
    """Build JSON-RPC error response"""
    resp = {"jsonrpc": "2.0", "id": id, "error": {"code": code, "message": message}}
    if data is not None:
        resp["error"]["data"] = data
    return resp


async def _handle_jsonrpc_method(
    method: str,
    params: Optional[Dict[str, Any]],
    project_id: Optional[str] = None
) -> Dict[str, Any]:
    """Handle JSON-RPC method call"""
    
    if method == "initialize":
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {},
            },
            "serverInfo": {
                "name": settings.PROJECT_NAME,
                "version": settings.PROJECT_VERSION,
            },
        }
    
    elif method == "notifications/initialized":
        return {}
    
    elif method == "tools/list":
        tools = await _get_project_tools(project_id)
        return {"tools": tools}
    
    elif method == "tools/call":
        if not params or "name" not in params:
            return _make_jsonrpc_error(request_id, -32602, "Missing tool name parameter")
        
        full_tool_name = params["name"]
        arguments = params.get("arguments", {})
        
        # Parse tool name format: tool_name@version or tool_name
        tool_name = full_tool_name
        version = None
        if "@" in full_tool_name:
            parts = full_tool_name.rsplit("@", 1)
            tool_name = parts[0]
            version = parts[1]
        
        async with async_session_maker() as session:
            query = select(Api2mcpProject).where(
                Api2mcpProject.tool_name == tool_name,
                Api2mcpProject.status == "active"
            )
            if version:
                query = query.where(Api2mcpProject.version == version)
            if project_id:
                query = query.where(Api2mcpProject.id == project_id)
            
            result = await session.execute(query)
            project = result.scalar_one_or_none()
            
            if not project:
                return {
                    "content": [{"type": "text", "text": f"Tool not found or not enabled: {full_tool_name}"}],
                    "isError": True,
                }
            
            try:
                raw_response = await _execute_api_call(project, arguments)
                
                if project.output_template:
                    processed = _apply_output_template(raw_response, project.output_template)
                else:
                    processed = raw_response
                
                if project.output_fields:
                    filtered = {}
                    for field_name, field_config in project.output_fields.items():
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
    
    elif method == "ping":
        return {}
    
    else:
        raise ValueError(f"Unknown MCP method: {method}")


async def _process_jsonrpc_request(
    body: Dict[str, Any],
    project_id: Optional[str] = None
) -> Dict[str, Any]:
    """Process single JSON-RPC request"""
    request_id = body.get("id")
    method = body.get("method", "")
    params = body.get("params")
    
    try:
        result = await _handle_jsonrpc_method(method, params, project_id)
        # notifications don't require response
        if method.startswith("notifications/"):
            return None
        return _make_jsonrpc_success(request_id, result)
    except ValueError as e:
        return _make_jsonrpc_error(request_id, -32601, str(e))
    except Exception as e:
        return _make_jsonrpc_error(request_id, -32603, f"Internal error: {str(e)}")


# ── Core MCP Server Endpoints (referenced anythingmcp architecture) ──

async def _resolve_project(identifier: str) -> Api2mcpProject:
    """Resolve project by UUID or tool_name, priority to UUID"""
    async with async_session_maker() as session:
        # First try by UUID
        result = await session.execute(
            select(Api2mcpProject).where(Api2mcpProject.id == identifier)
        )
        project = result.scalar_one_or_none()
        if project:
            return project
        
        # Then try by tool_name (compatible with older versions, default to v1)
        result = await session.execute(
            select(Api2mcpProject).where(
                Api2mcpProject.tool_name == identifier,
                Api2mcpProject.version == "v1",
                Api2mcpProject.status == "active"
            )
        )
        project = result.scalar_one_or_none()
        if project:
            return project
        
        # If v1 not found, try to find the first matching tool_name
        result = await session.execute(
            select(Api2mcpProject).where(
                Api2mcpProject.tool_name == identifier,
                Api2mcpProject.status == "active"
            ).order_by(Api2mcpProject.version)
        )
        project = result.scalar_one_or_none()
        if project:
            return project
        
        raise HTTPException(status_code=404, detail=f"Project not found: {identifier}")


async def _resolve_project_with_version(tool_name: str, version: str) -> Api2mcpProject:
    """Resolve project by tool_name + version"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Api2mcpProject).where(
                Api2mcpProject.tool_name == tool_name,
                Api2mcpProject.version == version,
                Api2mcpProject.status == "active"
            )
        )
        project = result.scalar_one_or_none()
        if project:
            return project
        
        raise HTTPException(status_code=404, detail=f"Project not found: {tool_name}@{version}")


@router.api_route("", methods=["POST", "GET"])
async def mcp_root_jsonrpc(request: Request):
    """
    MCP JSON-RPC 2.0 Root Endpoint (Streamable HTTP transport)

    MCP client access address:
    http://localhost:34085/mcpapi

    Lists all active tools from all projects without project isolation.

    Supported JSON-RPC methods:
    - initialize: Initialize MCP session
    - notifications/initialized: Client initialization complete notification
    - tools/list: List all active tools
    - tools/call: Call specified tool
    - ping: Heartbeat check
    """
    # GET request: Return server info
    if request.method == "GET":
        return {
            "name": settings.PROJECT_NAME,
            "version": settings.PROJECT_VERSION,
            "description": "API2MCP MCP Server - Converts REST APIs to MCP tools",
            "protocol": "mcp",
            "transport": "streamable-http",
            "endpoint": "/mcpapi",
        }
    
    # POST request: Handle JSON-RPC 2.0 protocol
    try:
        body = await request.json()
    except Exception:
        return Response(
            content=json.dumps(_make_jsonrpc_error(None, -32700, "Parse error: Invalid JSON")),
            media_type="application/json",
            status_code=400,
        )
    
    is_batch = isinstance(body, list)
    requests_list = body if is_batch else [body]
    
    responses = []
    for req_body in requests_list:
        if not isinstance(req_body, dict):
            continue
        
        if req_body.get("jsonrpc", "") != "2.0":
            responses.append(_make_jsonrpc_error(req_body.get("id"), -32600, "Invalid Request"))
            continue
        
        resp = await _process_jsonrpc_request(req_body)  # Don't pass project_id, query all projects
        if resp is not None:
            responses.append(resp)
    
    if not responses:
        return Response(status_code=202)
    
    response_data = responses if is_batch else responses[0]
    return Response(
        content=json.dumps(response_data, ensure_ascii=False),
        media_type="application/json",
    )


@router.api_route("/{identifier}", methods=["POST", "GET"])
async def mcp_project_jsonrpc(request: Request, identifier: str):
    """
    MCP JSON-RPC 2.0 Endpoint Isolated by Tool Name/ID
    
    URL: http://localhost:34085/mcpapi/{identifier}
    
    Supports two types of identifiers: UUID or tool_name
    
    Supported JSON-RPC methods:
    - initialize: Initialize MCP session
    - notifications/initialized: Client initialization complete notification
    - tools/list: List tools for this project
    - tools/call: Call tools for this project
    - ping: Heartbeat check
    """
    # Resolve project
    project = await _resolve_project(identifier)
    
    # GET request: Return server info
    if request.method == "GET":
        return {
            "name": f"{settings.PROJECT_NAME} - {project.tool_name}",
            "version": settings.PROJECT_VERSION,
            "description": project.tool_description or f"MCP tool for {project.tool_name}",
            "protocol": "mcp",
            "transport": "streamable-http",
            "endpoint": f"/mcpapi/{identifier}",
        }
    
    # POST request: Handle JSON-RPC 2.0 protocol
    try:
        body = await request.json()
    except Exception:
        return Response(
            content=json.dumps(_make_jsonrpc_error(None, -32700, "Parse error: Invalid JSON")),
            media_type="application/json",
            status_code=400,
        )
    
    is_batch = isinstance(body, list)
    requests_list = body if is_batch else [body]
    
    responses = []
    for req_body in requests_list:
        if not isinstance(req_body, dict):
            continue
        
        if req_body.get("jsonrpc", "") != "2.0":
            responses.append(_make_jsonrpc_error(req_body.get("id"), -32600, "Invalid Request"))
            continue
        
        resp = await _process_jsonrpc_request(req_body, project.id)
        if resp is not None:
            responses.append(resp)
    
    if not responses:
        return Response(status_code=202)
    
    response_data = responses if is_batch else responses[0]
    return Response(
        content=json.dumps(response_data, ensure_ascii=False),
        media_type="application/json",
    )


@router.api_route("/{tool_name}/{version}", methods=["POST", "GET"])
async def mcp_project_jsonrpc_with_version(request: Request, tool_name: str, version: str):
    """
    MCP JSON-RPC 2.0 Endpoint Isolated by Tool Name + Version
    
    URL: http://localhost:34085/mcpapi/{tool_name}/{version}
    
    Supported JSON-RPC methods:
    - initialize: Initialize MCP session
    - notifications/initialized: Client initialization complete notification
    - tools/list: List tools for this project
    - tools/call: Call tools for this project
    - ping: Heartbeat check
    """
    # Resolve project (by tool_name + version)
    project = await _resolve_project_with_version(tool_name, version)
    
    # GET request: Return server info
    if request.method == "GET":
        return {
            "name": f"{settings.PROJECT_NAME} - {project.tool_name}@{project.version}",
            "version": settings.PROJECT_VERSION,
            "description": project.tool_description or f"MCP tool for {project.tool_name}",
            "protocol": "mcp",
            "transport": "streamable-http",
            "endpoint": f"/mcpapi/{tool_name}/{version}",
        }
    
    # POST request: Handle JSON-RPC 2.0 protocol
    try:
        body = await request.json()
    except Exception:
        return Response(
            content=json.dumps(_make_jsonrpc_error(None, -32700, "Parse error: Invalid JSON")),
            media_type="application/json",
            status_code=400,
        )
    
    is_batch = isinstance(body, list)
    requests_list = body if is_batch else [body]
    
    responses = []
    for req_body in requests_list:
        if not isinstance(req_body, dict):
            continue
        
        if req_body.get("jsonrpc", "") != "2.0":
            responses.append(_make_jsonrpc_error(req_body.get("id"), -32600, "Invalid Request"))
            continue
        
        resp = await _process_jsonrpc_request(req_body, project.id)
        if resp is not None:
            responses.append(resp)
    
    if not responses:
        return Response(status_code=202)
    
    response_data = responses if is_batch else responses[0]
    return Response(
        content=json.dumps(response_data, ensure_ascii=False),
        media_type="application/json",
    )


# ── MCP Protocol Compatibility Endpoints (for legacy clients) ──

@router.get("/agent_info")
async def agent_info():
    """MCP Protocol: Get agent info"""
    return AgentInfoResponse()


@router.post("/list_tools")
async def list_tools():
    """MCP Protocol: List all available tools"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Api2mcpProject).where(Api2mcpProject.status == "active")
        )
        projects = result.scalars().all()
        
        tools = []
        for project in projects:
            result = await session.execute(
                select(Api2mcpParameter).where(Api2mcpParameter.project_id == project.id)
            )
            parameters = result.scalars().all()
            
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
            
            tools.append(ToolInfo(
                name=project.tool_name,
                description=project.tool_description or "API tool call",
                input_schema=input_schema,
                transport_modes=project.transport_modes or ["streamable_http"],
            ))
        
        return ListToolsResponse(tools=tools)


@router.post("/tools")
async def tools():
    """List all available tools"""
    return await list_tools()


@router.get("/tools")
async def tools_get():
    """List all available tools via GET"""
    return await list_tools()


@router.post("/mcplist:tools")
async def mcplist_tools():
    """mcplist:tools endpoint"""
    return await list_tools()


@router.get("/mcplist:tools")
async def mcplist_tools_get():
    """mcplist:tools endpoint via GET"""
    return await list_tools()


@router.post("/invoke_tool")
async def invoke_tool(request: ToolCallRequest):
    """MCP Protocol: Invoke specified tool"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Api2mcpProject).where(
                Api2mcpProject.tool_name == request.tool_name,
                Api2mcpProject.status == "active"
            )
        )
        project = result.scalar_one_or_none()
        
        if not project:
            return InvokeToolResponse(
                content=[ToolCallResponse(type="text", text=f"Tool not found or not enabled: {request.tool_name}")],
                is_error=True,
                error_message=f"Tool not found or not enabled: {request.tool_name}"
            )
        
        try:
            raw_response = await _execute_api_call(project, request.arguments)
            
            if project.output_template:
                processed_response = _apply_output_template(raw_response, project.output_template)
            else:
                processed_response = raw_response
            
            if project.output_fields:
                filtered = {}
                for field_name, field_config in project.output_fields.items():
                    if field_name in processed_response:
                        filtered[field_name] = processed_response[field_name]
                processed_response = filtered
            
            return InvokeToolResponse(
                content=[ToolCallResponse(type="text", text=json.dumps(processed_response, ensure_ascii=False, indent=2))],
                is_error=False
            )
        
        except Exception as e:
            return InvokeToolResponse(
                content=[ToolCallResponse(type="text", text=str(e))],
                is_error=True,
                error_message=str(e)
            )


# ── Extended Endpoints ──

@router.get("/tools/{tool_name}")
async def get_tool_info(tool_name: str):
    """Get detailed information for a single tool"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Api2mcpProject).where(Api2mcpProject.tool_name == tool_name)
        )
        project = result.scalar_one_or_none()
        
        if not project:
            raise HTTPException(status_code=404, detail=f"Tool not found: {tool_name}")
        
        result = await session.execute(
            select(Api2mcpParameter).where(Api2mcpParameter.project_id == project.id)
        )
        parameters = result.scalars().all()
        
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
        
        return {
            "name": project.tool_name,
            "description": project.tool_description,
            "category": project.category,
            "input_schema": input_schema,
            "output_fields": project.output_fields,
            "method": project.method,
            "endpoint": f"{project.base_url}{project.path}",
            "status": project.status,
            "created_at": project.created_at.isoformat() if project.created_at else None,
        }


@router.post("/tools/{tool_name}/test")
async def test_tool(tool_name: str, arguments: Dict[str, Any]):
    """Test tool invocation (with detailed debug info)"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Api2mcpProject).where(Api2mcpProject.tool_name == tool_name)
        )
        project = result.scalar_one_or_none()
        
        if not project:
            raise HTTPException(status_code=404, detail=f"Tool not found: {tool_name}")
        
        start_time = datetime.now()
        
        try:
            raw_response = await _execute_api_call(project, arguments)
            
            if project.output_template:
                processed_response = _apply_output_template(raw_response, project.output_template)
            else:
                processed_response = raw_response
            
            duration = (datetime.now() - start_time).total_seconds() * 1000
            
            return {
                "success": True,
                "tool_name": tool_name,
                "arguments": arguments,
                "raw_response": raw_response,
                "processed_response": processed_response,
                "duration_ms": round(duration, 2),
                "timestamp": datetime.now().isoformat()
            }
        
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds() * 1000
            return {
                "success": False,
                "tool_name": tool_name,
                "arguments": arguments,
                "error": str(e),
                "duration_ms": round(duration, 2),
                "timestamp": datetime.now().isoformat()
            }
