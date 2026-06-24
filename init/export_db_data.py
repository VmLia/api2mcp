#!/usr/bin/env python3
"""
API2MCP 数据导出脚本

功能:
  - 从数据库导出已有的工具数据
  - 生成可导入到 init_db_data.py 的 Python 代码

用法:
  python export_db_data.py              # 导出所有工具数据
  python export_db_data.py --tool name  # 导出指定工具
  python export_db_data.py --output file.py  # 输出到指定文件
"""
import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime

# 添加 backend/src 到 Python 路径
_backend_src = Path(__file__).resolve().parent.parent / "backend" / "src"
if str(_backend_src) not in sys.path:
    sys.path.insert(0, str(_backend_src))

from sqlalchemy import text
from api2mcp.database import async_session_maker
from api2mcp.config import settings


async def export_all_tools():
    """导出所有工具数据"""
    print("\n[Exporting tools from database...]")
    
    async with async_session_maker() as session:
        # 查询所有工具
        result = await session.execute(text("""
            SELECT 
                id, mcp_name, version, tool_description, category, tags,
                method, api_fullurl, content_type, mcp_fullurl,
                output_fields, output_template, usage_examples,
                cache_ttl, timeout_ms, status, auth_config_id,
                transport_modes, created_by, updated_by
            FROM api2mcp_baseinfo
            ORDER BY created_at
        """))
        tools = result.fetchall()
        
        if not tools:
            print("  No tools found in database")
            return []
        
        exported_data = []
        
        for tool in tools:
            tool_id = tool[0]
            
            # 查询参数
            param_result = await session.execute(text("""
                SELECT 
                    param_name, param_type, param_location, required,
                    description, item_type, default_value, example_value,
                    unit, semantic_tag, parent_id, sort_order
                FROM api2mcp_parameters
                WHERE baseinfo_id = :tool_id
                ORDER BY sort_order
            """), {"tool_id": tool_id})
            params = param_result.fetchall()
            
            # 构建工具数据结构
            tool_data = {
                "mcp_name": tool[1],
                "version": tool[2],
                "tool_description": tool[3],
                "category": tool[4] or "Other",
                "tags": tool[5] or [],
                "method": tool[6],
                "api_fullurl": tool[7],
                "content_type": tool[8] or "application/json",
                "mcp_fullurl": tool[9],
                "output_fields": tool[10] or {},
                "output_template": tool[11],
                "usage_examples": tool[12] or {},
                "cache_ttl": tool[13] or 0,
                "timeout_ms": tool[14] or settings.TOOL_DEFAULT_TIMEOUT_MS,
                "status": tool[15] or "active",
                "auth_config_id": tool[16],
                "transport_modes": tool[17] or ["streamable_http"],
                "parameters": [
                    {
                        "param_name": p[0],
                        "param_type": p[1] or "string",
                        "param_location": p[2] or "query",
                        "required": p[3] or False,
                        "description": p[4] or "",
                        "item_type": p[5],
                        "default_value": p[6] or "",
                        "example_value": p[7] or "",
                        "unit": p[8] or "",
                        "semantic_tag": p[9] or "",
                        "parent_id": p[10],
                        "sort_order": p[11] or 0,
                    }
                    for p in params
                ],
            }
            
            exported_data.append(tool_data)
            print(f"  ✓ Exported: {tool[1]}@{tool[2]} ({len(params)} parameters)")
        
        return exported_data


def generate_python_code(tools_data: list) -> str:
    """生成 Python 代码"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    code = f'''# ============================================
# 导出的工具数据 - {timestamp}
# 从数据库导出，可用于 init_db_data.py 的 SAMPLE_TOOLS
# ============================================

EXPORTED_TOOLS = [
'''
    
    for tool in tools_data:
        # 格式化参数
        params_str = ""
        if tool["parameters"]:
            params_str = ",\n            ".join([
                json.dumps(p, ensure_ascii=False, indent=12)
                for p in tool["parameters"]
            ])
            params_str = f'''[
            {params_str}
        ]'''
        else:
            params_str = "[]"
        
        # 格式化整个工具
        tool_json = json.dumps(tool, ensure_ascii=False, indent=4)
        # 替换 parameters 字段为格式化后的版本
        tool_dict = json.loads(tool_json)
        tool_dict["parameters"] = "PARAMS_PLACEHOLDER"
        tool_json = json.dumps(tool_dict, ensure_ascii=False, indent=4)
        tool_json = tool_json.replace('"PARAMS_PLACEHOLDER"', params_str)
        
        code += f"    {tool_json},\n"
    
    code += "]\n"
    
    return code


async def main():
    """命令行入口"""
    args = sys.argv[1:]
    output_file = None
    
    # 解析参数
    for i, arg in enumerate(args):
        if arg == "--output" and i + 1 < len(args):
            output_file = args[i + 1]
    
    print()
    print("=" * 50)
    print("  API2MCP Data Export Tool")
    print("=" * 50)
    
    # 导出数据
    tools_data = await export_all_tools()
    
    if not tools_data:
        print("\n  No data to export")
        return
    
    # 生成代码
    code = generate_python_code(tools_data)
    
    # 输出
    if output_file:
        output_path = Path(output_file)
        output_path.write_text(code)
        print(f"\n  ✓ Exported to: {output_path}")
    else:
        print("\n" + "=" * 50)
        print("  Generated Python Code")
        print("=" * 50)
        print(code)
        print("=" * 50)
        print("\n提示: 将上述 EXPORTED_TOOLS 内容复制到 init_db_data.py 的 SAMPLE_TOOLS 中")
        print("或者使用 --output 参数保存到文件")


if __name__ == "__main__":
    asyncio.run(main())