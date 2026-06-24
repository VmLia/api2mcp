"""
智能API解析路由
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Any

from ..services.smart_parser_service import SmartApiParser, ParseResult

router = APIRouter(prefix="/serverapi", tags=["smart-parser"])


class ParseRequest(BaseModel):
    """解析请求体"""
    text: str


class ParseResponse(BaseModel):
    """解析响应体"""
    success: bool
    data: ParseResult
    message: str = ""


@router.post("/parse", response_model=ParseResponse)
async def parse_api_text(request: ParseRequest):
    """
    智能解析API文档
    
    支持多种输入格式：
    - 自然语言描述
    - Swagger/OpenAPI JSON
    - URL模式
    - API文档片段
    
    返回解析后的结构化API配置，可直接用于创建API2MCP工具。
    """
    try:
        parser = SmartApiParser()
        result = await parser.parse_api_text(request.text)
        return {"success": True, "data": result, "message": "Parse successful"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Parse failed: {str(e)}")
