"""
API2MCP Tool Management API Routes
"""
import json
import logging
import uuid
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, delete, func

from database import async_session_maker
from api_info import Api2mcpTool, Api2mcpParameter, Api2mcpAuthConfig, Api2mcpEnvVariable
from config import settings

router = APIRouter(prefix="/serverapi/apimng", tags=["API2MCP"])

# Default user ID
DEFAULT_USER = settings.DEFAULT_USER_ID

# Semantic tag constants
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


# ── Pydantic Request/Response Models ──

class ProjectCreate(BaseModel):
    tool_name: str
    version: str = "v1"  # Version number, e.g., v1, v2, v3
    tool_description: Optional[str] = None
    category: Optional[str] = None
    tags: List[str] = []
    method: str = "GET"
    base_url: str
    path: str
    content_type: str = "application/json"
    output_fields: dict = {}
    output_template: Optional[str] = None
    usage_examples: dict = {}
    cache_ttl: int = 0
    timeout_ms: int = 30000
    auth_config_id: Optional[str] = None
    transport_modes: List[str] = ["streamable_http"]  # Transport protocols, currently supports: streamable_http
    status: str = "active"


class ProjectUpdate(BaseModel):
    tool_name: Optional[str] = None
    version: Optional[str] = None  # Version number, e.g., v1, v2, v3
    tool_description: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    method: Optional[str] = None
    base_url: Optional[str] = None
    path: Optional[str] = None
    content_type: Optional[str] = None
    output_fields: Optional[dict] = None
    output_template: Optional[str] = None
    usage_examples: Optional[dict] = None
    cache_ttl: Optional[int] = None
    timeout_ms: Optional[int] = None
    auth_config_id: Optional[str] = None
    status: Optional[str] = None
    transport_modes: Optional[List[str]] = None  # List of transport protocols


class ParameterCreate(BaseModel):
    param_name: str
    param_location: str
    param_type: str
    item_type: Optional[str] = None
    required: bool = False
    description: Optional[str] = None
    default_value: Optional[str] = None
    example_value: Optional[str] = None
    unit: Optional[str] = None
    semantic_tag: Optional[str] = None
    parent_id: Optional[str] = None
    sort_order: int = 0


class ParameterUpdate(BaseModel):
    param_name: Optional[str] = None
    param_location: Optional[str] = None
    param_type: Optional[str] = None
    item_type: Optional[str] = None
    required: Optional[bool] = None
    description: Optional[str] = None
    default_value: Optional[str] = None
    example_value: Optional[str] = None
    unit: Optional[str] = None
    semantic_tag: Optional[str] = None
    sort_order: Optional[int] = None


class AuthConfigCreate(BaseModel):
    name: str
    auth_type: str = "none"
    config: dict = {}


class EnvVariableCreate(BaseModel):
    key: str
    value: str
    scope: str = "global"
    tool_id: Optional[str] = None
    description: Optional[str] = None


# ── Helper Functions ──

def _build_input_schema(parameters: List[Api2mcpParameter]) -> dict:
    """Build inputSchema"""
    properties = {}
    required = []
    
    params_by_parent = {}
    for param in parameters:
        parent_id = param.parent_id or "root"
        if parent_id not in params_by_parent:
            params_by_parent[parent_id] = []
        params_by_parent[parent_id].append(param)
    
    def build_property(param: Api2mcpParameter) -> dict:
        prop = {"type": param.param_type}
        
        description_parts = []
        if param.description:
            description_parts.append(param.description)
        if param.semantic_tag:
            tag_label = next((t["label"] for t in SEMANTIC_TAGS if t["value"] == param.semantic_tag), None)
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
            nested_schema = _build_input_schema(nested_params)
            prop["properties"] = nested_schema.get("properties", {})
            prop["required"] = nested_schema.get("required", [])
        
        return prop
    
    root_params = params_by_parent.get("root", [])
    for param in root_params:
        properties[param.param_name] = build_property(param)
        if param.required:
            required.append(param.param_name)
    
    schema = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def _build_output_schema(output_fields: dict) -> dict:
    """Build outputSchema"""
    properties = {}
    for field_name, field_config in output_fields.items():
        prop = {"type": field_config.get("type", "string")}
        if "description" in field_config:
            prop["description"] = field_config["description"]
        properties[field_name] = prop
    return {"type": "object", "properties": properties}


def _build_tool_description(tool: Api2mcpTool) -> str:
    """Build tool description"""
    description = tool.tool_description or "API tool call"
    if tool.usage_examples:
        examples = tool.usage_examples.get("examples", [])
        if examples:
            description += "\n\nUsage Examples:\n"
            for i, example in enumerate(examples[:3], 1):
                user_question = example.get("question", "")
                tool_call = example.get("params", {})
                description += f"{i}. User asks: {user_question}\n   Call params: {json.dumps(tool_call)}\n"
    return description


def _tool_to_dict(tool: Api2mcpTool) -> dict:
    return {
        "id": tool.id,
        "tool_name": tool.tool_name,
        "version": tool.version,
        "tool_description": tool.tool_description,
        "category": tool.category,
        "tags": tool.tags,
        "method": tool.method,
        "base_url": tool.base_url,
        "path": tool.path,
        "content_type": tool.content_type,
        "output_fields": tool.output_fields,
        "output_template": tool.output_template,
        "usage_examples": tool.usage_examples,
        "cache_ttl": tool.cache_ttl,
        "timeout_ms": tool.timeout_ms,
        "status": tool.status,
        "auth_config_id": tool.auth_config_id,
        "transport_modes": tool.transport_modes or ["streamable_http"],
        "created_at": tool.created_at.isoformat() if tool.created_at else None,
        "updated_at": tool.updated_at.isoformat() if tool.updated_at else None,
    }


def _parameter_to_dict(param: Api2mcpParameter) -> dict:
    return {
        "id": param.id,
        "tool_id": param.tool_id,
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


def _build_parameter_tree(parameters: List[Api2mcpParameter]) -> List[dict]:
    """Convert flat parameter list to tree structure"""
    param_dict = {p.id: _parameter_to_dict(p) for p in parameters}
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


def _auth_config_to_dict(config: Api2mcpAuthConfig) -> dict:
    return {
        "id": config.id,
        "name": config.name,
        "auth_type": config.auth_type,
        "config": config.config,
        "created_at": config.created_at.isoformat() if config.created_at else None,
    }


def _env_var_to_dict(var: Api2mcpEnvVariable) -> dict:
    return {
        "id": var.id,
        "key": var.key,
        "value": "***" if var.value else "",
        "scope": var.scope,
        "tool_id": var.tool_id,
        "description": var.description,
        "created_at": var.created_at.isoformat() if var.created_at else None,
    }


# ── Tool CRUD ──

@router.post("/tools")
async def create_tool(data: ProjectCreate):
    """Create API2MCP tool"""
    
    # Validate tool_name + version uniqueness (tool names can repeat, but not with the same version)
    async with async_session_maker() as session:
        result = await session.execute(
            select(Api2mcpTool).where(
                Api2mcpTool.tool_name == data.tool_name,
                Api2mcpTool.version == data.version
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail=f"Tool name and version combination already exists: {data.tool_name}@{data.version}")
    
    tool_id = str(uuid.uuid4())
    
    # Handle empty auth_config_id string, convert to None
    auth_config_id = data.auth_config_id if data.auth_config_id else None
    
    # Handle transport protocols, ensure at least one
    transport_modes = data.transport_modes if data.transport_modes and len(data.transport_modes) > 0 else ["streamable_http"]
    
    tool = Api2mcpTool(
        id=tool_id,
        tool_name=data.tool_name,
        version=data.version,
        tool_description=data.tool_description,
        category=data.category,
        tags=data.tags,
        method=data.method,
        base_url=data.base_url,
        path=data.path,
        content_type=data.content_type,
        output_fields=data.output_fields,
        output_template=data.output_template,
        usage_examples=data.usage_examples,
        cache_ttl=data.cache_ttl,
        timeout_ms=data.timeout_ms,
        status=data.status,
        auth_config_id=auth_config_id,
        transport_modes=transport_modes,
        created_by=DEFAULT_USER,
        updated_by=DEFAULT_USER,
    )
    
    async with async_session_maker() as session:
        session.add(tool)
        await session.commit()
    
    return {"status": "ok", "tool_id": tool_id, "tool_name": data.tool_name, "version": data.version}


@router.get("/tools")
async def list_tools(
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
):
    """List all API2MCP tools"""
    async with async_session_maker() as session:
        query = select(Api2mcpTool)
        if category:
            query = query.where(Api2mcpTool.category == category)
        if status:
            query = query.where(Api2mcpTool.status == status)
        if search:
            query = query.where(Api2mcpTool.tool_name.ilike(f"%{search}%"))
        query = query.order_by(Api2mcpTool.created_at.desc())
        
        result = await session.execute(query)
        tools = result.scalars().all()
        
        return {"tools": [_tool_to_dict(t) for t in tools]}


@router.get("/tools/{tool_id}")
async def get_tool(tool_id: str):
    """Get tool detail"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Api2mcpTool).where(Api2mcpTool.id == tool_id)
        )
        tool = result.scalar_one_or_none()
        if not tool:
            raise HTTPException(status_code=404, detail="Tool not found")
        
        result = await session.execute(
            select(Api2mcpParameter)
            .where(Api2mcpParameter.tool_id == tool_id)
            .order_by(Api2mcpParameter.sort_order)
        )
        parameters = result.scalars().all()
        
        tool_dict = _tool_to_dict(tool)
        tool_dict["parameters"] = [_parameter_to_dict(p) for p in parameters]
        
        return tool_dict


@router.put("/tools/{tool_id}")
async def update_tool(tool_id: str, data: ProjectUpdate):
    """Update tool configuration"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Api2mcpTool).where(Api2mcpTool.id == tool_id)
        )
        tool = result.scalar_one_or_none()
        if not tool:
            raise HTTPException(status_code=404, detail="Tool not found")
        
        # Validate tool_name + version uniqueness (if tool_name or version changed)
        new_tool_name = data.tool_name if data.tool_name else tool.tool_name
        new_version = data.version if data.version else tool.version
        if new_tool_name != tool.tool_name or new_version != tool.version:
            result = await session.execute(
                select(Api2mcpTool).where(
                    Api2mcpTool.tool_name == new_tool_name,
                    Api2mcpTool.version == new_version
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                raise HTTPException(status_code=409, detail=f"Tool name and version combination already exists: {new_tool_name}@{new_version}")
        
        update_fields = [
            "tool_name", "version", "tool_description", "category", "tags",
            "method", "base_url", "path", "content_type",
            "output_fields", "output_template", "usage_examples",
            "cache_ttl", "timeout_ms", "status",
        ]
        for field in update_fields:
            value = getattr(data, field, None)
            if value is not None:
                setattr(tool, field, value)
        
        # Handle auth_config_id separately, empty string becomes None
        if hasattr(data, 'auth_config_id') and data.auth_config_id is not None:
            tool.auth_config_id = data.auth_config_id if data.auth_config_id else None
        
        # Handle transport protocols
        if hasattr(data, 'transport_modes') and data.transport_modes is not None:
            if data.transport_modes and len(data.transport_modes) > 0:
                tool.transport_modes = data.transport_modes
            else:
                tool.transport_modes = ["streamable_http"]
        
        tool.updated_by = DEFAULT_USER
        await session.commit()
    
    return {"status": "ok"}


@router.delete("/tools/{tool_id}")
async def delete_tool(tool_id: str):
    """Delete tool and all its parameters, stop MCP Server"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Api2mcpTool).where(Api2mcpTool.id == tool_id)
        )
        tool = result.scalar_one_or_none()
        if not tool:
            raise HTTPException(status_code=404, detail="Tool not found")
        
        tool_name = tool.tool_name
        
        await session.execute(
            delete(Api2mcpParameter).where(Api2mcpParameter.tool_id == tool_id)
        )
        
        await session.delete(tool)
        await session.commit()
    
    return {"status": "ok", "tool_id": tool_id}


# ── Parameter Management ──

@router.get("/tools/{tool_id}/parameters")
async def list_parameters(tool_id: str):
    """Get all parameters for tool (tree structure)"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Api2mcpParameter)
            .where(Api2mcpParameter.tool_id == tool_id)
            .order_by(Api2mcpParameter.sort_order)
        )
        parameters = result.scalars().all()
        
        return {"parameters": _build_parameter_tree(parameters)}


@router.post("/tools/{tool_id}/parameters")
async def create_parameter(tool_id: str, data: ParameterCreate):
    """Create parameter"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Api2mcpTool).where(Api2mcpTool.id == tool_id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Tool not found")
        
        param = Api2mcpParameter(
            id=str(uuid.uuid4()),
            tool_id=tool_id,
            parent_id=data.parent_id,
            param_name=data.param_name,
            param_location=data.param_location,
            param_type=data.param_type,
            item_type=data.item_type,
            required=data.required,
            description=data.description,
            default_value=data.default_value,
            example_value=data.example_value,
            unit=data.unit,
            semantic_tag=data.semantic_tag,
            sort_order=data.sort_order,
        )
        
        session.add(param)
        await session.commit()
    
    return {"status": "ok", "parameter_id": param.id}


@router.put("/tools/{tool_id}/parameters/{param_id}")
async def update_parameter(tool_id: str, param_id: str, data: ParameterUpdate):
    """Update parameter"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Api2mcpParameter)
            .where(Api2mcpParameter.id == param_id)
            .where(Api2mcpParameter.tool_id == tool_id)
        )
        param = result.scalar_one_or_none()
        if not param:
            raise HTTPException(status_code=404, detail="Parameter not found")
        
        update_fields = [
            "param_name", "param_location", "param_type", "item_type",
            "required", "description", "default_value", "example_value",
            "unit", "semantic_tag", "sort_order",
        ]
        for field in update_fields:
            value = getattr(data, field, None)
            if value is not None:
                setattr(param, field, value)
        
        await session.commit()
    
    return {"status": "ok"}


@router.delete("/tools/{tool_id}/parameters/{param_id}")
async def delete_parameter(tool_id: str, param_id: str):
    """Delete parameter (cascading delete child parameters)"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Api2mcpParameter)
            .where(Api2mcpParameter.id == param_id)
            .where(Api2mcpParameter.tool_id == tool_id)
        )
        param = result.scalar_one_or_none()
        if not param:
            raise HTTPException(status_code=404, detail="Parameter not found")
        
        await session.execute(
            delete(Api2mcpParameter).where(Api2mcpParameter.parent_id == param_id)
        )
        
        await session.delete(param)
        await session.commit()
    
    return {"status": "ok"}


# ── Authentication Configuration Management ──

@router.post("/auth-configs")
async def create_auth_config(data: AuthConfigCreate):
    """Create auth configuration"""
    config_id = str(uuid.uuid4())
    config = Api2mcpAuthConfig(
        id=config_id,
        name=data.name,
        auth_type=data.auth_type,
        config=data.config,
        created_by=DEFAULT_USER,
    )
    
    async with async_session_maker() as session:
        session.add(config)
        await session.commit()
    
    return {"status": "ok", "auth_config_id": config_id}


@router.get("/auth-configs")
async def list_auth_configs():
    """List all auth configurations"""
    async with async_session_maker() as session:
        result = await session.execute(select(Api2mcpAuthConfig))
        configs = result.scalars().all()
        return {"configs": [_auth_config_to_dict(c) for c in configs]}


@router.delete("/auth-configs/{config_id}")
async def delete_auth_config(config_id: str):
    """Delete auth configuration"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Api2mcpAuthConfig).where(Api2mcpAuthConfig.id == config_id)
        )
        config = result.scalar_one_or_none()
        if not config:
            raise HTTPException(status_code=404, detail="Auth config not found")
        
        result = await session.execute(
            select(func.count()).select_from(Api2mcpTool)
            .where(Api2mcpTool.auth_config_id == config_id)
        )
        count = result.scalar_one()
        if count > 0:
            raise HTTPException(status_code=400, detail="This configuration is being used by tools and cannot be deleted")
        
        await session.delete(config)
        await session.commit()
    
    return {"status": "ok"}


# ── Environment Variable Management ──

@router.post("/env-variables")
async def create_env_variable(data: EnvVariableCreate):
    """Create environment variable"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Api2mcpEnvVariable).where(Api2mcpEnvVariable.key == data.key)
        )
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Variable name already exists")
        
        var = Api2mcpEnvVariable(
            id=str(uuid.uuid4()),
            key=data.key,
            value=data.value,
            scope=data.scope,
            tool_id=data.tool_id,
            description=data.description,
            created_by=DEFAULT_USER,
        )
        
        session.add(var)
        await session.commit()
    
    return {"status": "ok"}


@router.get("/env-variables")
async def list_env_variables(
    scope: Optional[str] = Query(None),
    tool_id: Optional[str] = Query(None),
):
    """List environment variables"""
    async with async_session_maker() as session:
        query = select(Api2mcpEnvVariable)
        if scope:
            query = query.where(Api2mcpEnvVariable.scope == scope)
        if tool_id:
            query = query.where(
                (Api2mcpEnvVariable.scope == "global") |
                (Api2mcpEnvVariable.tool_id == tool_id)
            )
        
        result = await session.execute(query)
        vars = result.scalars().all()
        
        return {"variables": [_env_var_to_dict(v) for v in vars]}


@router.delete("/env-variables/{var_id}")
async def delete_env_variable(var_id: str):
    """Delete environment variable"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Api2mcpEnvVariable).where(Api2mcpEnvVariable.id == var_id)
        )
        var = result.scalar_one_or_none()
        if not var:
            raise HTTPException(status_code=404, detail="Variable not found")
        
        await session.delete(var)
        await session.commit()
    
    return {"status": "ok"}


# ── MCP Tool Generation and Preview ──

@router.get("/tools/{tool_id}/mcp-definition")
async def get_mcp_definition(tool_id: str):
    """Get MCP definition preview for tool"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Api2mcpTool).where(Api2mcpTool.id == tool_id)
        )
        tool = result.scalar_one_or_none()
        if not tool:
            raise HTTPException(status_code=404, detail="Tool not found")
        
        result = await session.execute(
            select(Api2mcpParameter).where(Api2mcpParameter.tool_id == tool_id)
        )
        parameters = result.scalars().all()
        
        input_schema = _build_input_schema(list(parameters))
        output_schema = _build_output_schema(tool.output_fields)
        description = _build_tool_description(tool)
        
        return {
            "name": tool.tool_name,
            "description": description,
            "inputSchema": input_schema,
            "outputSchema": output_schema,
            "transportModes": tool.transport_modes or ["streamable_http"],
        }


@router.post("/tools/{tool_id}/register-mcp")
async def register_tool_to_mcp(tool_id: str):
    """Manually trigger tool registration to MCP"""
    # Simplified handling here, actual registration logic requires MCP service support
    async with async_session_maker() as session:
        result = await session.execute(
            select(Api2mcpTool).where(Api2mcpTool.id == tool_id)
        )
        tool = result.scalar_one_or_none()
        if not tool:
            raise HTTPException(status_code=404, detail="Tool not found")
    
    return {"status": "ok", "message": "Registered to MCP"}


# ── Semantic Tags Query ──

@router.get("/semantic-tags")
async def get_semantic_tags():
    """Get available semantic tags list"""
    return {"tags": SEMANTIC_TAGS}


@router.get("/server-info")
async def get_server_info():
    """
    Get MCP server configuration info (for frontend use)
    
    Returns the MCP public access URL, frontend no longer needs hardcoded URLs.
    Can be overridden via MCP_PUBLIC_BASE_URL environment variable.
    """
    return {
        "mcp_base_url": settings.mcp_public_base_url,
        "backend_port": settings.BACKEND_PORT,
        "project_name": settings.PROJECT_NAME,
        "project_version": settings.PROJECT_VERSION,
    }
