#!/usr/bin/env python3
"""
API2MCP Database Initialization Script

Usage:
  python init_db.py          # Create table structure (first use)
  python init_db.py --seed   # Create table structure + import sample data
  python init_db.py --check  # Only check table structure, do not create
"""
import asyncio
import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from sqlalchemy import text

from database import engine, async_session_maker
from models import Base


# Expected table names list
EXPECTED_TABLES = [
    'api2mcp_projects',
    'api2mcp_parameters',
    'api2mcp_auth_config',
    'api2mcp_env_variables',
]


async def get_existing_tables():
    """Get existing api2mcp tables in database"""
    async with engine.connect() as conn:
        result = await conn.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name LIKE 'api2mcp_%'"
        ))
        return [row[0] for row in result]


async def get_table_columns(table_name: str) -> dict:
    """Get table column information"""
    async with engine.connect() as conn:
        result = await conn.execute(text(
            f"SELECT column_name, data_type FROM information_schema.columns "
            f"WHERE table_schema = 'public' AND table_name = '{table_name}'"
        ))
        return {row[0]: row[1] for row in result}


async def create_tables():
    """Create all missing tables"""
    existing = await get_existing_tables()
    missing = [t for t in EXPECTED_TABLES if t not in existing]

    if not missing:
        print("  ✓ All tables already exist")
        return True

    print(f"  Creating missing tables: {', '.join(missing)}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("  ✓ Tables created successfully")
    return True


async def check_table_health():
    """Check table structure health status"""
    print("\n[2/3] Checking table structure...")

    existing = await get_existing_tables()

    for table in EXPECTED_TABLES:
        if table not in existing:
            print(f"   {table} does not exist")
            continue

        columns = await get_table_columns(table)
        print(f"  ✓ {table} ({len(columns)} columns)")


async def seed_sample_data():
    """Import sample data (optional)"""
    print("\n[3/3] Importing sample data...")

    from models import Api2mcpProject, Api2mcpParameter, Api2mcpAuthConfig, Api2mcpEnvVariable
    import uuid

    async with async_session_maker() as session:
        # Check if data already exists
        result = await session.execute(text("SELECT COUNT(*) FROM api2mcp_projects"))
        project_count = result.scalar()

        if project_count > 0:
            print(f"  {project_count} projects already exist, skipping sample data import")
            print("  Tip: Use --reset parameter to clear and re-import")
            return

        # Create sample auth configurations
        auth_configs = [
            Api2mcpAuthConfig(
                id=str(uuid.uuid4()),
                name="API Key Auth",
                auth_type="api_key",
                config={"header_name": "X-API-Key", "api_key": "{{API_KEY}}"},
                created_by="admin",
            ),
            Api2mcpAuthConfig(
                id=str(uuid.uuid4()),
                name="Bearer Token Auth",
                auth_type="bearer_token",
                config={"token": "{{BEARER_TOKEN}}"},
                created_by="admin",
            ),
        ]
        for auth in auth_configs:
            session.add(auth)

        # Create sample environment variables
        env_vars = [
            Api2mcpEnvVariable(
                id=str(uuid.uuid4()),
                key="API_KEY",
                value="your-api-key-here",
                scope="global",
                description="Sample API key",
                created_by="admin",
            ),
            Api2mcpEnvVariable(
                id=str(uuid.uuid4()),
                key="BASE_URL",
                value="https://api.example.com",
                scope="global",
                description="Sample API base URL",
                created_by="admin",
            ),
        ]
        for var in env_vars:
            session.add(var)

        # Create sample projects
        sample_projects = [
            {
                "tool_name": "search_projects",
                "tool_description": "Search project list, supports filtering by keyword, status, budget range, etc.",
                "category": "Project Management",
                "tags": ["project", "search"],
                "method": "GET",
                "base_url": "{{BASE_URL}}",
                "path": "/api/v1/projects/search",
                "transport_modes": ["streamable_http"],
                "parameters": [
                    {"param_name": "keyword", "param_location": "query", "param_type": "string",
                     "required": False, "description": "Search keyword", "semantic_tag": "like"},
                    {"param_name": "status", "param_location": "query", "param_type": "string",
                     "required": False, "description": "Project status"},
                    {"param_name": "budget_min", "param_location": "query", "param_type": "number",
                     "required": False, "description": "Minimum budget (10k RMB)", "semantic_tag": "min"},
                ],
            },
            {
                "tool_name": "get_weather",
                "tool_description": "Get weather information for specified city",
                "category": "Other",
                "tags": ["weather", "query"],
                "method": "GET",
                "base_url": "https://api.openweathermap.org",
                "path": "/data/2.5/weather",
                "transport_modes": ["streamable_http"],
                "parameters": [
                    {"param_name": "q", "param_location": "query", "param_type": "string",
                     "required": True, "description": "City name"},
                    {"param_name": "appid", "param_location": "query", "param_type": "string",
                     "required": True, "description": "API key"},
                ],
            },
        ]

        for project_data in sample_projects:
            parameters = project_data.pop("parameters", [])
            project_id = str(uuid.uuid4())

            project = Api2mcpProject(
                id=project_id,
                **project_data,
                content_type="application/json",
                output_fields={},
                usage_examples={"examples": []},
                created_by="admin",
                updated_by="admin",
            )
            session.add(project)

            for idx, param_data in enumerate(parameters):
                param = Api2mcpParameter(
                    id=str(uuid.uuid4()),
                    project_id=project_id,
                    sort_order=idx,
                    **param_data,
                )
                session.add(param)

        await session.commit()
        print("  ✓ Sample data imported successfully")
        print("    - 2 auth configs")
        print("    - 2 environment variables")
        print("    - 2 sample projects (search_projects, get_weather)")


async def show_summary():
    """Show database summary"""
    print("\n" + "=" * 50)
    print("Database Summary")
    print("=" * 50)

    async with async_session_maker() as session:
        for table, label in [
            ("api2mcp_projects", "Projects"),
            ("api2mcp_parameters", "Parameters"),
            ("api2mcp_auth_config", "Auth Configs"),
            ("api2mcp_env_variables", "Env Variables"),
        ]:
            result = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
            count = result.scalar()
            print(f"  {label}: {count}")

        # Project list
        result = await session.execute(text(
            "SELECT tool_name, version, method, status FROM api2mcp_projects ORDER BY created_at"
        ))
        projects = result.fetchall()
        if projects:
            print(f"\n  Project List:")
            for p in projects:
                print(f"    - {p[0]}@{p[1]} [{p[2]}] [{p[3]}]")

    print()


async def main():
    """Main function"""
    args = sys.argv[1:]
    do_seed = "--seed" in args
    do_check = "--check" in args

    print()
    print("=" * 50)
    print("  API2MCP Database Initialization")
    print("=" * 50)

    try:
        # Step 1: Create tables
        print("\n[1/3] Creating table structure...")
        await create_tables()

        if do_check:
            await check_table_health()
            await show_summary()
            print("✓ Check completed")
            return

        # Step 2: Check table health
        await check_table_health()

        # Step 3: Optional - Import sample data
        if do_seed:
            await seed_sample_data()

        # Show summary
        await show_summary()

        print("=" * 50)
        print("✓ Initialization completed!")
        print("=" * 50)
        print()
        print("Next steps:")
        print("  Start service:  ./start.sh")
        print("  Open browser: http://localhost:34075")
        print()

    except Exception as e:
        print(f"\n✗ Initialization failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
