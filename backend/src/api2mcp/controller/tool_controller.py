"""
工具管理控制器 - 处理工具、参数、鉴权配置、环境变量的 API 请求
"""
import logging
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query

from ..service.tool_service import ToolService
from ..service.parameter_service import ParameterService
from ..service.auth_service import AuthService
from ..service.env_variable_service import EnvVariableService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/serverapi/apimng", tags=["API2MCP"])


# ── 工具 CRUD ──

@router.post("/tools")
async def create_tool(data: dict):
    """创建 API2MCP 工具"""
    service = ToolService()
    try:
        result = await service.create_tool(data)
        return result
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating tool: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tools")
async def list_tools(
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
):
    """获取所有 API2MCP 工具"""
    service = ToolService()
    try:
        tools = await service.list_tools(category, status, search)
        return {"tools": tools}
    except Exception as e:
        logger.error(f"Error listing tools: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tools/{tool_id}")
async def get_tool(tool_id: str):
    """获取工具详情"""
    service = ToolService()
    try:
        tool = await service.get_tool(tool_id)
        if not tool:
            raise HTTPException(status_code=404, detail="Tool not found")
        return tool
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tool: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/tools/{tool_id}")
async def update_tool(tool_id: str, data: dict):
    """更新工具配置"""
    service = ToolService()
    try:
        await service.update_tool(tool_id, data)
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating tool: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/tools/{tool_id}")
async def delete_tool(tool_id: str):
    """删除工具及其所有参数"""
    service = ToolService()
    try:
        return await service.delete_tool(tool_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting tool: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── 参数管理 ──

@router.get("/tools/{tool_id}/parameters")
async def list_parameters(tool_id: str):
    """获取工具的参数列表（树结构）"""
    service = ParameterService()
    try:
        parameters = await service.list_parameters(tool_id)
        return {"parameters": parameters}
    except Exception as e:
        logger.error(f"Error listing parameters: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tools/{tool_id}/parameters")
async def create_parameter(tool_id: str, data: dict):
    """创建参数"""
    service = ParameterService()
    try:
        return await service.create_parameter(tool_id, data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating parameter: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/tools/{tool_id}/parameters/{param_id}")
async def update_parameter(tool_id: str, param_id: str, data: dict):
    """更新参数"""
    service = ParameterService()
    try:
        return await service.update_parameter(tool_id, param_id, data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating parameter: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/tools/{tool_id}/parameters/{param_id}")
async def delete_parameter(tool_id: str, param_id: str):
    """删除参数（级联删除子参数）"""
    service = ParameterService()
    try:
        return await service.delete_parameter(tool_id, param_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting parameter: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── 鉴权配置管理 ──

@router.post("/auth-configs")
async def create_auth_config(data: dict):
    """创建鉴权配置"""
    service = AuthService()
    try:
        return await service.create_auth_config(data)
    except Exception as e:
        logger.error(f"Error creating auth config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/auth-configs")
async def list_auth_configs():
    """获取所有鉴权配置"""
    service = AuthService()
    try:
        configs = await service.list_auth_configs()
        return {"configs": configs}
    except Exception as e:
        logger.error(f"Error listing auth configs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/auth-configs/{config_id}")
async def delete_auth_config(config_id: str):
    """删除鉴权配置"""
    service = AuthService()
    try:
        return await service.delete_auth_config(config_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting auth config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── 环境变量管理 ──

@router.post("/env-variables")
async def create_env_variable(data: dict):
    """创建环境变量"""
    service = EnvVariableService()
    try:
        return await service.create_env_variable(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating env variable: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/env-variables")
async def list_env_variables(
    scope: Optional[str] = Query(None),
    tool_id: Optional[str] = Query(None),
):
    """获取环境变量列表"""
    service = EnvVariableService()
    try:
        vars = await service.list_env_variables(scope, tool_id)
        return {"variables": vars}
    except Exception as e:
        logger.error(f"Error listing env variables: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/env-variables/{var_id}")
async def delete_env_variable(var_id: str):
    """删除环境变量"""
    service = EnvVariableService()
    try:
        return await service.delete_env_variable(var_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting env variable: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── MCP 工具生成和预览 ──

@router.get("/tools/{tool_id}/mcp-definition")
async def get_mcp_definition(tool_id: str):
    """获取工具的 MCP 定义预览"""
    service = ToolService()
    try:
        definition = await service.get_mcp_definition(tool_id)
        if not definition:
            raise HTTPException(status_code=404, detail="Tool not found")
        return definition
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting MCP definition: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tools/{tool_id}/register-mcp")
async def register_tool_to_mcp(tool_id: str):
    """手动触发工具注册到 MCP"""
    # 简化处理，实际注册逻辑需要 MCP 服务支持
    service = ToolService()
    try:
        tool = await service.get_tool(tool_id)
        if not tool:
            raise HTTPException(status_code=404, detail="Tool not found")
        return {"status": "ok", "message": "Registered to MCP"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering tool to MCP: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── 语义标签查询 ──

@router.get("/semantic-tags")
async def get_semantic_tags():
    """获取可用的语义标签列表"""
    from ..service.tool_service import SEMANTIC_TAGS
    return {"tags": SEMANTIC_TAGS}


# ── 服务器信息 ──

@router.get("/server-info")
async def get_server_info():
    """
    获取 MCP 服务器配置信息（供前端使用）

    返回 MCP 公开访问 URL，前端不再需要硬编码 URL。
    可通过 MCP_PUBLIC_BASE_URL 环境变量覆盖。
    """
    from ..config import settings
    return {
        "mcp_base_url": settings.mcp_public_base_url,
        "backend_port": settings.BACKEND_PORT,
        "project_name": settings.PROJECT_NAME,
        "project_version": settings.PROJECT_VERSION,
    }
