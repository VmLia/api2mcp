#!/usr/bin/env python3
"""
API2MCP 数据库数据初始化脚本

功能:
  - 初始化基础配置数据（认证配置、环境变量）
  - 初始化示例工具数据
  - 更新已有数据

用法:
  python init_db_data.py              # 初始化基础配置数据（默认）
  python init_db_data.py --sample     # 初始化基础配置 + 示例工具数据
  python init_db_data.py --reset      # 清空所有数据并重新初始化
  python init_db_data.py --check      # 仅检查数据状态，不初始化

注意:
  运行此脚本前，请确保数据库表已创建（运行 python init/init_db.py）
"""
import asyncio
import sys
import os
import uuid
from pathlib import Path

# 添加 backend/src 到 Python 路径
_backend_src = Path(__file__).resolve().parent.parent / "backend" / "src"
if str(_backend_src) not in sys.path:
    sys.path.insert(0, str(_backend_src))

from sqlalchemy import text
from api2mcp.database import async_session_maker
from api2mcp.api_registry.entities.tool import Api2mcpBaseinfo
from api2mcp.api_registry.entities.parameter import Api2mcpParameter
from api2mcp.api_registry.entities.auth_config import Api2mcpAuthConfig
from api2mcp.api_registry.entities.env_variable import Api2mcpEnvVariable
from api2mcp.config import settings


# ============================================
# 基础配置数据定义
# ============================================

DEFAULT_AUTH_CONFIGS = [
    {
        "name": "API Key Auth",
        "auth_type": "api_key",
        "config": {"header_name": "X-API-Key", "api_key": "{{API_KEY}}"},
        "description": "API Key 认证方式，通过 HTTP Header 传递",
    },
    {
        "name": "Bearer Token Auth",
        "auth_type": "bearer_token",
        "config": {"token": "{{BEARER_TOKEN}}"},
        "description": "Bearer Token 认证方式，通过 Authorization Header 传递",
    },
    {
        "name": "Basic Auth",
        "auth_type": "basic_auth",
        "config": {"username": "{{USERNAME}}", "password": "{{PASSWORD}}"},
        "description": "Basic 认证方式，通过用户名密码认证",
    },
]

DEFAULT_ENV_VARIABLES = [
    {
        "key": "API_KEY",
        "value": "your-api-key-here",
        "scope": "global",
        "description": "示例 API Key，请在生产环境中替换为实际值",
    },
    {
        "key": "BEARER_TOKEN",
        "value": "your-bearer-token-here",
        "scope": "global",
        "description": "示例 Bearer Token，请在生产环境中替换为实际值",
    },
    {
        "key": "BASE_URL",
        "value": "https://api.example.com",
        "scope": "global",
        "description": "示例 API 基础 URL，请在生产环境中替换为实际值",
    },
]


# ============================================
# 示例工具数据定义
# ============================================

SAMPLE_TOOLS = [
    {
        "mcp_name": "get_weather",
        "tool_description": "展示用例，不可用 - Get weather information for specified city",
        "category": "Other",
        "tags": ["weather", "query", "demo"],
        "method": "GET",
        "api_fullurl": "https://api.openweathermap.org/data/2.5/weather",
        "transport_modes": ["streamable_http"],
        "parameters": [
            {"param_name": "q", "param_location": "query", "param_type": "string",
             "required": True, "description": "City name"},
            {"param_name": "appid", "param_location": "query", "param_type": "string",
             "required": True, "description": "API key"},
        ],
    },
]


# ============================================
# 数据操作函数
# ============================================

async def get_data_summary():
    """获取数据摘要"""
    async with async_session_maker() as session:
        summary = {}
        
        for table, label in [
            ("api2mcp_baseinfo", "tools"),
            ("api2mcp_parameters", "parameters"),
            ("api2mcp_auth_config", "auth_configs"),
            ("api2mcp_env_variables", "env_variables"),
        ]:
            result = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
            summary[label] = result.scalar()
        
        return summary


async def clear_all_data():
    """清空所有数据"""
    print("\n[Clearing all data...]")
    
    async with async_session_maker() as session:
        # 按依赖顺序删除
        tables = [
            'api2mcp_parameters',
            'api2mcp_baseinfo',
            'api2mcp_auth_config',
            'api2mcp_env_variables',
        ]
        
        for table in tables:
            await session.execute(text(f"DELETE FROM {table}"))
        
        await session.commit()
        print("  ✓ All data cleared")


async def init_auth_configs():
    """初始化认证配置数据"""
    print("\n[Initializing auth configs...]")
    
    async with async_session_maker() as session:
        # 检查是否已存在
        result = await session.execute(text("SELECT COUNT(*) FROM api2mcp_auth_config"))
        count = result.scalar()
        
        if count > 0:
            print(f"  {count} auth configs already exist, skipping")
            return
        
        # 创建默认认证配置
        for config_data in DEFAULT_AUTH_CONFIGS:
            auth_config = Api2mcpAuthConfig(
                id=str(uuid.uuid4()),
                name=config_data["name"],
                auth_type=config_data["auth_type"],
                config=config_data["config"],
                description=config_data.get("description", ""),
                created_by="system",
            )
            session.add(auth_config)
        
        await session.commit()
        print(f"  ✓ {len(DEFAULT_AUTH_CONFIGS)} auth configs created")


async def init_env_variables():
    """初始化环境变量数据"""
    print("\n[Initializing environment variables...]")
    
    async with async_session_maker() as session:
        # 检查是否已存在
        result = await session.execute(text("SELECT COUNT(*) FROM api2mcp_env_variables"))
        count = result.scalar()
        
        if count > 0:
            print(f"  {count} env variables already exist, skipping")
            return
        
        # 创建默认环境变量
        for var_data in DEFAULT_ENV_VARIABLES:
            env_var = Api2mcpEnvVariable(
                id=str(uuid.uuid4()),
                key=var_data["key"],
                value=var_data["value"],
                scope=var_data["scope"],
                description=var_data.get("description", ""),
                created_by="system",
            )
            session.add(env_var)
        
        await session.commit()
        print(f"  ✓ {len(DEFAULT_ENV_VARIABLES)} env variables created")


async def init_sample_tools():
    """初始化示例工具数据"""
    print("\n[Initializing sample tools...]")
    
    async with async_session_maker() as session:
        # 检查是否已存在
        result = await session.execute(text("SELECT COUNT(*) FROM api2mcp_baseinfo"))
        count = result.scalar()
        
        if count > 0:
            print(f"  {count} tools already exist, skipping sample data import")
            return
        
        # 创建示例工具
        for tool_data in SAMPLE_TOOLS:
            parameters = tool_data.pop("parameters", [])
            baseinfo_id = str(uuid.uuid4())
            
            tool = Api2mcpBaseinfo(
                id=baseinfo_id,
                **tool_data,
                content_type="application/json",
                output_fields={},
                usage_examples={"examples": []},
                created_by="system",
                updated_by="system",
            )
            session.add(tool)
            
            # 创建参数
            for idx, param_data in enumerate(parameters):
                param = Api2mcpParameter(
                    id=str(uuid.uuid4()),
                    baseinfo_id=baseinfo_id,
                    sort_order=idx,
                    **param_data,
                )
                session.add(param)
        
        await session.commit()
        print(f"  ✓ {len(SAMPLE_TOOLS)} sample tools created")


async def show_data_summary():
    """显示数据摘要"""
    print("\n" + "=" * 50)
    print("Database Data Summary")
    print("=" * 50)
    
    summary = await get_data_summary()
    
    print(f"  Tools:          {summary['tools']}")
    print(f"  Parameters:     {summary['parameters']}")
    print(f"  Auth Configs:   {summary['auth_configs']}")
    print(f"  Env Variables:  {summary['env_variables']}")
    
    # 显示工具列表
    if summary['tools'] > 0:
        print("\n  Tool List:")
        async with async_session_maker() as session:
            result = await session.execute(text(
                "SELECT mcp_name, version, method, status FROM api2mcp_baseinfo ORDER BY created_at"
            ))
            tools = result.fetchall()
            for t in tools:
                print(f"    - {t[0]}@{t[1]} [{t[2]}] [{t[3]}]")
    
    print()


async def init_data(do_sample: bool = False, do_reset: bool = False, do_check: bool = False):
    """
    数据初始化核心函数
    
    Args:
        do_sample: 是否导入示例工具数据
        do_reset: 是否清空数据重新初始化
        do_check: 是否仅检查不初始化
    """
    print()
    print("=" * 50)
    print("  API2MCP Database Data Initialization")
    print(f"  Reset data: {do_reset}")
    print(f"  Include sample: {do_sample}")
    print("=" * 50)
    
    try:
        if do_check:
            await show_data_summary()
            print("✓ Check completed")
            return True
        
        # 清空数据（如果需要）
        if do_reset:
            await clear_all_data()
        
        # 初始化基础配置数据
        await init_auth_configs()
        await init_env_variables()
        
        # 初始化示例工具数据（如果需要）
        if do_sample:
            await init_sample_tools()
        
        # 显示摘要
        await show_data_summary()
        
        print("=" * 50)
        print("✓ Data initialization completed!")
        print("=" * 50)
        print()
        return True
        
    except Exception as e:
        print(f"\n✗ Data initialization failed: {e}")
        import traceback
        traceback.print_exc()
        raise


async def main():
    """命令行入口"""
    args = sys.argv[1:]
    do_sample = "--sample" in args
    do_reset = "--reset" in args
    do_check = "--check" in args
    
    await init_data(
        do_sample=do_sample,
        do_reset=do_reset,
        do_check=do_check
    )
    
    if not do_check:
        print("Next steps:")
        print("  Start service:  ./start-mac.sh")
        print(f"  Open browser:   http://localhost:{settings.FRONTEND_PORT}")
        print()


if __name__ == "__main__":
    asyncio.run(main())