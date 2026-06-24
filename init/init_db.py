#!/usr/bin/env python3
"""
API2MCP 数据库表结构管理脚本

功能:
  - 创建/重建数据库表结构
  - 检查数据库表是否存在

用法:
  python init_db.py              # 创建缺失的表（默认）
  python init_db.py --check      # 仅检查表结构，不创建
  python init_db.py --reset      # 删除所有表并重新创建

环境变量配置:
  API2MCP_DB_DEL: 是否在服务启动时删除已存在的表（true/false，默认 false）
"""
import asyncio
import sys
import os
from pathlib import Path

# 添加 backend/src 到 Python 路径
_backend_src = Path(__file__).resolve().parent.parent / "backend" / "src"
if str(_backend_src) not in sys.path:
    sys.path.insert(0, str(_backend_src))

from sqlalchemy import text
from api2mcp.database import engine, Base
from api2mcp.api_registry.entities.tool import Api2mcpBaseinfo
from api2mcp.api_registry.entities.parameter import Api2mcpParameter
from api2mcp.api_registry.entities.auth_config import Api2mcpAuthConfig
from api2mcp.api_registry.entities.env_variable import Api2mcpEnvVariable
from api2mcp.config import settings


EXPECTED_TABLES = [
    'api2mcp_baseinfo',
    'api2mcp_parameters',
    'api2mcp_auth_config',
    'api2mcp_env_variables',
]


async def get_existing_tables():
    """获取数据库中已存在的 api2mcp 表"""
    async with engine.connect() as conn:
        result = await conn.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name LIKE 'api2mcp_%'"
        ))
        return [row[0] for row in result]


async def get_table_columns(table_name: str) -> dict:
    """获取表的列信息"""
    async with engine.connect() as conn:
        result = await conn.execute(text(
            f"SELECT column_name, data_type FROM information_schema.columns "
            f"WHERE table_schema = 'public' AND table_name = '{table_name}'"
        ))
        return {row[0]: row[1] for row in result}


async def drop_all_tables():
    """删除所有 api2mcp 相关表"""
    existing = await get_existing_tables()
    if not existing:
        print("  ✓ No tables to drop")
        return

    print(f"  Dropping existing tables: {', '.join(existing)}")
    async with engine.connect() as conn:
        for table in existing:
            await conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
        await conn.commit()
    print("  ✓ All tables dropped")


async def create_tables(drop_existing: bool = False):
    """
    创建所有需要的表
    
    Args:
        drop_existing: 是否先删除已存在的表
    """
    if drop_existing:
        await drop_all_tables()

    existing = await get_existing_tables()
    missing = [t for t in EXPECTED_TABLES if t not in existing]

    if not missing:
        print("  ✓ All tables already exist")
        return True

    print(f"  Creating tables: {', '.join(missing)}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("  ✓ Tables created successfully")
    return True


async def check_table_health():
    """检查表结构健康状态"""
    print("\n[Checking table structure...]")

    existing = await get_existing_tables()
    all_ok = True

    for table in EXPECTED_TABLES:
        if table not in existing:
            print(f"  ✗ {table} does not exist")
            all_ok = False
            continue

        columns = await get_table_columns(table)
        print(f"  ✓ {table} ({len(columns)} columns)")

    return all_ok


async def show_summary():
    """显示数据库表结构摘要"""
    print("\n" + "=" * 50)
    print("Database Table Summary")
    print("=" * 50)

    existing = await get_existing_tables()
    
    for table in EXPECTED_TABLES:
        if table in existing:
            columns = await get_table_columns(table)
            print(f"  ✓ {table}: {len(columns)} columns")
        else:
            print(f"  ✗ {table}: not exist")

    print()


async def init_tables(drop_existing: bool = False, do_check: bool = False):
    """
    数据库表结构初始化核心函数（供服务启动时调用）
    
    Args:
        drop_existing: 是否先删除已存在的表（从 API2MCP_DB_DEL 配置读取）
        do_check: 是否仅检查不创建
    """
    print()
    print("=" * 50)
    print("  API2MCP Database Table Initialization")
    print(f"  Drop existing tables: {drop_existing}")
    print("=" * 50)

    try:
        if do_check:
            await check_table_health()
            await show_summary()
            print("✓ Check completed")
            return True

        print("\n[Creating table structure...]")
        await create_tables(drop_existing=drop_existing)
        await check_table_health()
        await show_summary()

        print("=" * 50)
        print("✓ Table initialization completed!")
        print("=" * 50)
        print()
        return True

    except Exception as e:
        print(f"\n✗ Table initialization failed: {e}")
        import traceback
        traceback.print_exc()
        raise


async def main():
    """命令行入口"""
    args = sys.argv[1:]
    do_check = "--check" in args
    do_reset = "--reset" in args

    drop_existing = do_reset or settings.API2MCP_DB_DEL

    await init_tables(
        drop_existing=drop_existing,
        do_check=do_check
    )

    if not do_check:
        print("Next steps:")
        print("  Start service:     ./start-mac.sh")
        print("  Initialize data:   python init/init_db_data.py")
        print(f"  Open browser:      http://localhost:{settings.FRONTEND_PORT}")
        print()


if __name__ == "__main__":
    asyncio.run(main())