"""
MCP 协议控制器 - 处理 MCP JSON-RPC 2.0 协议请求
"""
import json
import logging
from typing import Any, Dict, Optional, Union
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select

from ...database import async_session_maker
from ...api_registry.entities.tool import Api2mcpBaseinfo
from ...api_registry.entities.parameter import Api2mcpParameter
from ...engine.mcp_service import MCPService
from ...config import settings
from ..state import (
    request_state_manager,
    call_statistics_manager,
    RequestStatus
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mcpapi", tags=["MCP Server"])

# 初始化 MCP 服务
mcp_service = MCPService()


# ── JSON-RPC 辅助函数 ──

def _make_jsonrpc_success(id: Any, result: Any) -> Dict[str, Any]:
    """构建 JSON-RPC 成功响应"""
    return {"jsonrpc": "2.0", "id": id, "result": result}


def _make_jsonrpc_error(
    id: Any, code: int, message: str, data: Any = None
) -> Dict[str, Any]:
    """构建 JSON-RPC 错误响应"""
    resp = {"jsonrpc": "2.0", "id": id, "error": {"code": code, "message": message}}
    if data is not None:
        resp["error"]["data"] = data
    return resp


async def _handle_jsonrpc_method(
    method: str,
    params: Optional[Dict[str, Any]],
    tool_id: Optional[str] = None
) -> Dict[str, Any]:
    """处理 JSON-RPC 方法调用"""

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
        tools = await mcp_service.get_tools(tool_id)
        return {"tools": tools}

    elif method == "tools/call":
        if not params or "name" not in params:
            return _make_jsonrpc_error(None, -32602, "Missing tool name parameter")

        full_tool_name = params["name"]
        arguments = params.get("arguments", {})

        # 解析工具名和版本
        tool_name = full_tool_name
        tool_version = "v1"
        if "@" in full_tool_name:
            tool_name, tool_version = full_tool_name.rsplit("@", 1)

        # 记录请求开始
        request_id = await request_state_manager.start_request(
            tool_name=tool_name,
            tool_version=tool_version,
            input_params=arguments
        )

        start_time = datetime.now()

        try:
            # 更新状态为处理中
            await request_state_manager.update_request_status(
                request_id, RequestStatus.PROCESSING
            )

            # 执行工具调用
            result = await mcp_service.invoke_tool(full_tool_name, arguments, tool_id)

            # 更新状态为完成
            await request_state_manager.update_request_status(
                request_id, RequestStatus.COMPLETED, output_result=result
            )

            # 记录调用统计
            latency_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            await call_statistics_manager.record_call(
                tool_name=tool_name,
                tool_version=tool_version,
                success=True,
                latency_ms=latency_ms
            )

            return result

        except Exception as e:
            # 更新状态为失败
            await request_state_manager.update_request_status(
                request_id, RequestStatus.FAILED, error_message=str(e)
            )

            # 记录调用统计
            latency_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            await call_statistics_manager.record_call(
                tool_name=tool_name,
                tool_version=tool_version,
                success=False,
                latency_ms=latency_ms
            )

            raise

    elif method == "ping":
        return {}

    else:
        raise ValueError(f"Unknown MCP method: {method}")


async def _process_jsonrpc_request(
    body: Dict[str, Any],
    tool_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """处理单个 JSON-RPC 请求"""
    request_id = body.get("id")
    method = body.get("method", "")
    params = body.get("params")

    try:
        result = await _handle_jsonrpc_method(method, params, tool_id)
        # notifications 不需要响应
        if method.startswith("notifications/"):
            return None
        return _make_jsonrpc_success(request_id, result)
    except ValueError as e:
        return _make_jsonrpc_error(request_id, -32601, str(e))
    except Exception as e:
        return _make_jsonrpc_error(request_id, -32603, f"Internal error: {str(e)}")


async def _resolve_project(identifier: str) -> Api2mcpBaseinfo:
    """根据 UUID 或工具名解析项目"""
    async with async_session_maker() as session:
        # 先尝试 UUID
        result = await session.execute(
            select(Api2mcpBaseinfo).where(Api2mcpBaseinfo.id == identifier)
        )
        project = result.scalar_one_or_none()
        if project:
            return project

        # 再尝试工具名（兼容旧版本，默认 v1）
        result = await session.execute(
            select(Api2mcpBaseinfo).where(
                Api2mcpBaseinfo.mcp_name == identifier,
                Api2mcpBaseinfo.version == "v1",
                Api2mcpBaseinfo.status == "active"
            )
        )
        project = result.scalar_one_or_none()
        if project:
            return project

        # 如果 v1 没找到，尝试找第一个匹配的
        result = await session.execute(
            select(Api2mcpBaseinfo).where(
                Api2mcpBaseinfo.mcp_name == identifier,
                Api2mcpBaseinfo.status == "active"
            ).order_by(Api2mcpBaseinfo.version)
        )
        project = result.scalar_one_or_none()
        if project:
            return project

        raise HTTPException(status_code=404, detail=f"Project not found: {identifier}")


async def _resolve_project_with_version(
    mcp_name: str, version: str
) -> Api2mcpBaseinfo:
    """根据工具名+版本解析项目"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Api2mcpBaseinfo).where(
                Api2mcpBaseinfo.mcp_name == mcp_name,
                Api2mcpBaseinfo.version == version,
                Api2mcpBaseinfo.status == "active"
            )
        )
        project = result.scalar_one_or_none()
        if project:
            return project

        raise HTTPException(
            status_code=404,
            detail=f"Project not found: {mcp_name}@{version}"
        )


# ── MCP JSON-RPC 端点 ──

@router.api_route("", methods=["POST", "GET"])
async def mcp_root_jsonrpc(request: Request):
    """
    MCP JSON-RPC 2.0 根端点 (Streamable HTTP 传输)

    MCP 客户端访问地址：
    http://localhost:{backend_port}/mcpapi

    列出所有活跃工具，不进行项目隔离。

    支持的 JSON-RPC 方法：
    - initialize: 初始化 MCP 会话
    - notifications/initialized: 客户端初始化完成通知
    - tools/list: 列出所有活跃工具
    - tools/call: 调用指定工具
    - ping: 心跳检查
    """
    # GET 请求：返回服务器信息
    if request.method == "GET":
        return {
            "name": settings.PROJECT_NAME,
            "version": settings.PROJECT_VERSION,
            "description": "API2MCP MCP Server - Converts REST APIs to MCP tools",
            "protocol": "mcp",
            "transport": "streamable-http",
            "endpoint": "/mcpapi",
        }

    # POST 请求：处理 JSON-RPC 2.0 协议
    try:
        body = await request.json()
    except Exception:
        return Response(
            content=json.dumps(
                _make_jsonrpc_error(None, -32700, "Parse error: Invalid JSON")
            ),
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
            responses.append(
                _make_jsonrpc_error(req_body.get("id"), -32600, "Invalid Request")
            )
            continue

        resp = await _process_jsonrpc_request(req_body)  # 不传 tool_id，查询所有工具
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
    MCP JSON-RPC 2.0 端点 - 按工具名称/ID 隔离

    URL: http://localhost:{backend_port}/mcpapi/{identifier}

    支持两种标识符类型：UUID 或 tool_name

    支持的 JSON-RPC 方法：
    - initialize: 初始化 MCP 会话
    - notifications/initialized: 客户端初始化完成通知
    - tools/list: 列出此项目的工具
    - tools/call: 调用此项目的工具
    - ping: 心跳检查
    """
    # 解析项目
    project = await _resolve_project(identifier)

    # GET 请求：返回服务器信息
    if request.method == "GET":
        return {
            "name": f"{settings.PROJECT_NAME} - {project.mcp_name}",
            "version": settings.PROJECT_VERSION,
            "description": project.tool_description or f"MCP tool for {project.mcp_name}",
            "protocol": "mcp",
            "transport": "streamable-http",
            "endpoint": f"/mcpapi/{identifier}",
        }

    # POST 请求：处理 JSON-RPC 2.0 协议
    try:
        body = await request.json()
    except Exception:
        return Response(
            content=json.dumps(
                _make_jsonrpc_error(None, -32700, "Parse error: Invalid JSON")
            ),
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
            responses.append(
                _make_jsonrpc_error(req_body.get("id"), -32600, "Invalid Request")
            )
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


@router.api_route("/{mcp_name}/{version}", methods=["POST", "GET"])
async def mcp_project_jsonrpc_with_version(
    request: Request, mcp_name: str, version: str
):
    """
    MCP JSON-RPC 2.0 端点 - 按工具名+版本隔离

    URL: http://localhost:{backend_port}/mcpapi/{mcp_name}/{version}

    支持的 JSON-RPC 方法：
    - initialize: 初始化 MCP 会话
    - notifications/initialized: 客户端初始化完成通知
    - tools/list: 列出此项目的工具
    - tools/call: 调用此项目的工具
    - ping: 心跳检查
    """
    # 解析项目（按工具名+版本）
    project = await _resolve_project_with_version(mcp_name, version)

    # GET 请求：返回服务器信息
    if request.method == "GET":
        return {
            "name": f"{settings.PROJECT_NAME} - {project.mcp_name}@{project.version}",
            "version": settings.PROJECT_VERSION,
            "description": project.tool_description or f"MCP tool for {project.mcp_name}",
            "protocol": "mcp",
            "transport": "streamable-http",
            "endpoint": f"/mcpapi/{mcp_name}/{version}",
        }

    # POST 请求：处理 JSON-RPC 2.0 协议
    try:
        body = await request.json()
    except Exception:
        return Response(
            content=json.dumps(
                _make_jsonrpc_error(None, -32700, "Parse error: Invalid JSON")
            ),
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
            responses.append(
                _make_jsonrpc_error(req_body.get("id"), -32600, "Invalid Request")
            )
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


# ── MCP 协议兼容性端点（兼容旧版客户端） ──

@router.get("/agent_info")
async def agent_info():
    """MCP 协议：获取 Agent 信息"""
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.PROJECT_VERSION,
        "protocol": "mcp",
        "transport_modes": ["streamable_http"],
    }


@router.post("/list_tools")
async def list_tools():
    """MCP 协议：列出所有可用工具"""
    tools = await mcp_service.get_tools()
    return {"tools": tools}


@router.post("/tools")
async def tools():
    """列出所有可用工具"""
    return await list_tools()


@router.get("/tools")
async def tools_get():
    """通过 GET 列出所有可用工具"""
    return await list_tools()


@router.post("/mcplist:tools")
async def mcplist_tools():
    """mcplist:tools 端点"""
    return await list_tools()


@router.get("/mcplist:tools")
async def mcplist_tools_get():
    """通过 GET 访问 mcplist:tools 端点"""
    return await list_tools()


@router.post("/invoke_tool")
async def invoke_tool(request: dict):
    """MCP 协议：调用指定工具"""
    tool_name = request.get("tool_name")
    arguments = request.get("arguments", {})

    # 解析工具名和版本
    parsed_tool_name = tool_name
    tool_version = "v1"
    if "@" in tool_name:
        parsed_tool_name, tool_version = tool_name.rsplit("@", 1)

    # 记录请求开始
    request_id = await request_state_manager.start_request(
        tool_name=parsed_tool_name,
        tool_version=tool_version,
        input_params=arguments
    )

    start_time = datetime.now()

    try:
        # 更新状态为处理中
        await request_state_manager.update_request_status(
            request_id, RequestStatus.PROCESSING
        )

        # 执行工具调用
        result = await mcp_service.invoke_tool(tool_name, arguments)

        # 更新状态为完成
        await request_state_manager.update_request_status(
            request_id, RequestStatus.COMPLETED, output_result=result
        )

        # 记录调用统计
        latency_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        await call_statistics_manager.record_call(
            tool_name=parsed_tool_name,
            tool_version=tool_version,
            success=True,
            latency_ms=latency_ms
        )

        return {
            "content": result.get("content", []),
            "isError": result.get("isError", False),
            "is_error": result.get("isError", False),
            "error_message": result.get("content", [{}])[0].get("text") if result.get("isError") else None,
            "request_id": request_id,
        }

    except Exception as e:
        # 更新状态为失败
        await request_state_manager.update_request_status(
            request_id, RequestStatus.FAILED, error_message=str(e)
        )

        # 记录调用统计
        latency_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        await call_statistics_manager.record_call(
            tool_name=parsed_tool_name,
            tool_version=tool_version,
            success=False,
            latency_ms=latency_ms
        )

        return {
            "content": [],
            "isError": True,
            "is_error": True,
            "error_message": str(e),
            "request_id": request_id,
        }


# ── 状态管理端点 ──

@router.get("/stats")
async def get_mcp_stats():
    """获取 MCP Server 整体统计信息"""
    return {"message": "Use /server/status for server status information"}


@router.get("/stats/{tool_name}")
async def get_tool_stats(tool_name: str, version: str = "v1"):
    """获取指定工具的调用统计"""
    stats = await call_statistics_manager.get_stats(tool_name, version)
    return {
        "tool_name": tool_name,
        "version": version,
        **stats
    }


@router.get("/stats/{tool_name}/history")
async def get_tool_stats_history(tool_name: str, version: str = "v1", hours: int = 24):
    """获取指定工具的历史调用统计（按小时）"""
    history = await call_statistics_manager.get_hourly_stats(tool_name, version, hours)
    return {
        "tool_name": tool_name,
        "version": version,
        "hours": hours,
        "history": history
    }


@router.get("/requests/{request_id}")
async def get_request_status(request_id: str):
    """获取指定请求的状态信息"""
    request_info = await request_state_manager.get_request_info(request_id)
    if not request_info:
        raise HTTPException(status_code=404, detail=f"Request not found: {request_id}")
    return request_info.to_dict()


@router.get("/requests/{tool_name}/{version}")
async def get_tool_requests(tool_name: str, version: str = "v1", limit: int = 100):
    """获取指定工具的最近请求列表"""
    requests = await request_state_manager.get_recent_requests(tool_name, version, limit)
    return {
        "tool_name": tool_name,
        "version": version,
        "requests": [req.to_dict() for req in requests]
    }


# ── 扩展端点 ──

@router.get("/tools/{mcp_name}")
async def get_tool_info(mcp_name: str):
    """获取单个工具的详细信息"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Api2mcpBaseinfo).where(Api2mcpBaseinfo.mcp_name == mcp_name)
        )
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail=f"Tool not found: {mcp_name}")

        result = await session.execute(
            select(Api2mcpParameter).where(Api2mcpParameter.baseinfo_id == project.id)
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
            "name": project.mcp_name,
            "description": project.tool_description,
            "category": project.category,
            "input_schema": input_schema,
            "output_fields": project.output_fields,
            "method": project.method,
            "endpoint": project.api_fullurl,
            "mcp_fullurl": project.mcp_fullurl,
            "status": project.status,
            "created_at": project.created_at.isoformat() if project.created_at else None,
        }


@router.post("/tools/{mcp_name}/test")
async def test_tool(mcp_name: str, arguments: dict):
    """测试工具调用（带详细调试信息）"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Api2mcpBaseinfo).where(Api2mcpBaseinfo.mcp_name == mcp_name)
        )
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail=f"Tool not found: {mcp_name}")

        start_time = datetime.now()

        try:
            raw_response = await mcp_service.execute_api_call(project, arguments)

            if project.output_template:
                processed_response = mcp_service.apply_output_template(
                    raw_response, project.output_template
                )
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
