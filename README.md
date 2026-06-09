# API2MCP
[中文文档](./readme-cn.md)

**Enterprise Pain Points:**
- When enterprises develop agents, they face challenges in efficiently integrating existing systems with agents. Particularly when agents need to call data service APIs from existing systems, these APIs are typically RESTful. However, MCP protocol is more agent-friendly for data retrieval.

**REST API to MCP Bridge**
- Enterprises need a simple, secure, and extensible solution to quickly integrate new APIs into agents.
- Convert any REST API to MCP (Model Context Protocol) tools, enabling AI agents to discover and call your APIs.

## Features

- **Visual Management Interface** - Configure APIs through a step-by-step wizard
- **Transport Protocol Support** - Streamable HTTP (current), stdio (planned)
- **Dynamic Tool Discovery** - MCP clients can automatically discover all registered tools
- **Tool Isolation** - Expose all tools via root endpoint, or isolate by tool name/version
- **Parameter Tree** - Supports nested parameter structures
- **Auth Configuration** - Reusable auth configurations (API Key, Bearer Token, Basic Auth)
- **Environment Variables** - Secure credential management with variable substitution
- **Output Mapping** - Transform response data using JMESPath templates

<img width="1612" height="824" alt="image" src="https://github.com/user-attachments/assets/6dcc0c2f-278c-4653-aee2-0797d8326ca1" />
<img width="1612" height="824" alt="image" src="https://github.com/user-attachments/assets/a3c03519-a7f8-4664-9ea0-4b2fd46183e3" />
<img width="1612" height="824" alt="image" src="https://github.com/user-attachments/assets/71c31f31-d27a-42b5-9975-005be8c8085f" />


## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+

### Steps

```
1. Clone the project locally
2. Install database (skip if you already have one)
3. Configure initialization
4. Initialize database
5. Start services
```

### 1. Clone and Install

```bash
git clone https://github.com/VmLia/api2mcp.git
cd api2mcp
```

#### Option 1: One-click Install on Mac (Recommended)

```bash
# Install all dependencies (backend + frontend)
./start-mac.sh setup
```

#### Option 2: Manual Installation (for Linux/Windows or custom configuration)

```bash
# 1. Install backend Python dependencies
cd backend

# Using uv (recommended)
uv venv .venv
uv sync

# Or using pip (alternative)
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Install frontend dependencies
cd ../frontend
npm install
```

### 2. Install Database (Optional)

> If you already have a PostgreSQL database, skip to step 3 to configure the connection.

#### Option 1: Using Docker Compose (Recommended)

```bash
# Start PostgreSQL using Docker Compose
cd docker-compose-api2mcp
docker compose -f docker-compose-api2mcp.yaml up -d
```

> **Note**: Docker and Docker Compose must be installed first.

#### Option 2: Using Existing PostgreSQL Database

If PostgreSQL is already installed on your system, create the database and user:

```sql
-- Create database
CREATE DATABASE api2mcp;

-- Create user
CREATE USER api2mcp WITH PASSWORD 'api2mcp@123';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE api2mcp TO api2mcp;
```

> **Note**: Ensure the database connection configuration in `.env` matches your PostgreSQL setup.

### 3. Configure Initialization

Copy the example config file and modify database connection:

```bash
cp .env.example .env
```

Edit the `.env` file to configure database connection:

```bash
# Database (required)
DB_TYPE=postgresql
DB_HOST=127.0.0.1
DB_PORT=5432
DB_USER=api2mcp
DB_PASSWORD=api2mcp@123
DB_NAME=api2mcp
DB_DRIVER=asyncpg

# Ports (optional, defaults below)
API2MCP_PORT_BACKEND=34085
API2MCP_PORT_FRONTEND=34075

# MCP Public URL (optional, set for production)
# Leave empty to use default: http://127.0.0.1:34085/mcpapi
MCP_PUBLIC_BASE_URL=
```

### 4. Initialize Database

```bash
cd backend
source .venv/bin/activate  # Or use: uv run

# Create tables only
python ../init_db.py

# Or create tables + import sample data
python ../init_db.py --seed
```

### 5. Start the Service

#### Option 1: One-click Start on Mac
```bash
# Development mode (starts both frontend and backend, backend logs displayed in real-time)
./start-mac.sh
```

#### Option 2: Manual Start (for Linux/Windows or custom configuration)
```bash
# Backend (run in backend directory, backend logs displayed in real-time)
cd backend
source .venv/bin/activate
uv run uvicorn main:app --host 0.0.0.0 --port 34085 --reload

# Frontend (run in frontend directory)
cd ../frontend
npm run dev
```

> **Note**: The port is read from the `.env` file (API2MCP_PORT_FRONTEND=34075). To specify a different port temporarily, use environment variable:
> ```bash
> API2MCP_PORT_FRONTEND=34075 npm run dev
> ```

Open http://localhost:34075 in your browser

## MCP Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET/POST /mcpapi` | Root endpoint - exposes all active tools |
| `GET/POST /mcpapi/{identifier}` | Isolated endpoint by identifier (supports UUID or tool name) |
| `GET/POST /mcpapi/{tool_name}/{version}` | Isolated endpoint by tool name + version |

## MCP Client Configuration

**Recommended Clients: CherryStudio / MCP Inspector**

- Transport Mode: `streamable-http`
- URL: Use the MCP Server URL generated in the management page (format: `http://localhost:34085/mcpapi/{tool_name}/{version}`)

## Project Structure

```
api2mcp/
├── backend/              # Python FastAPI backend
│   ├── main.py           # Application entry
│   ├── api.py            # Management API routes
│   ├── mcp_server.py     # MCP protocol implementation
│   ├── api_info.py       # Database models
│   ├── config.py         # Configuration
│   ├── database.py       # Database connection
│   ├── pyproject.toml    # Python project configuration (uv)
│   ├── uv.lock           # uv dependency lock file
│   └── requirements.txt  # Python dependencies (pip compatible)
├── frontend/             # Vue 3 + TypeScript frontend
│   ├── src/
│   │   ├── views/        # Page components
│   │   ├── stores/       # Pinia state management
│   │   ├── router/       # Routing configuration
│   │   ├── main.ts       # Entry file
│   │   └── App.vue       # Root component
│   ├── index.html        # HTML template
│   ├── package.json      # Node.js dependency configuration
│   ├── package-lock.json # Node.js dependency lock file
│   ├── vite.config.ts    # Vite build configuration
│   ├── tsconfig.json     # TypeScript configuration
│   └── tsconfig.node.json # TypeScript Node configuration
├── docker-compose-api2mcp/  # Docker database deployment
│   └── docker-compose-api2mcp.yaml
├── .env                  # Configuration file (shared by frontend and backend)
├── .env.example          # Configuration file example
├── start-mac.sh          # Mac start script
├── stop-mac.sh           # Mac stop script
├── init_db.py            # Database initialization script
└── README.md             # English documentation
```

## API Reference

### Management API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/serverapi/apimng/tools` | Get tool list |
| POST | `/serverapi/apimng/tools` | Create tool |
| GET | `/serverapi/apimng/tools/{id}` | Get tool details |
| PUT | `/serverapi/apimng/tools/{id}` | Update tool |
| DELETE | `/serverapi/apimng/tools/{id}` | Delete tool |
| GET | `/serverapi/apimng/tools/{id}/parameters` | Get tool parameters |
| POST | `/serverapi/apimng/tools/{id}/parameters` | Create parameter |
| PUT | `/serverapi/apimng/tools/{id}/parameters/{param_id}` | Update parameter |
| DELETE | `/serverapi/apimng/tools/{id}/parameters/{param_id}` | Delete parameter |
| GET | `/serverapi/apimng/auth-configs` | Get auth config list |
| POST | `/serverapi/apimng/auth-configs` | Create auth config |
| DELETE | `/serverapi/apimng/auth-configs/{id}` | Delete auth config |
| GET | `/serverapi/apimng/env-variables` | Get environment variable list |
| POST | `/serverapi/apimng/env-variables` | Create environment variable |
| DELETE | `/serverapi/apimng/env-variables/{id}` | Delete environment variable |
| GET | `/serverapi/apimng/semantic-tags` | Get semantic tag list |
| GET | `/serverapi/apimng/server-info` | Get server info |

### MCP Server Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET/POST | `/mcpapi` | MCP JSON-RPC root endpoint |
| GET/POST | `/mcpapi/{identifier}` | Isolated endpoint by identifier |
| GET/POST | `/mcpapi/{tool_name}/{version}` | Isolated endpoint by tool name + version |

## FAQ

### 1. Port Already in Use

**Problem**: Service fails to start with "port already in use" error

**Solution**:
```bash
# Check which process is using the port
lsof -i :34075  # Frontend port
lsof -i :34085  # Backend port

# Kill the process
kill -9 <PID>

# Or change ports in .env file
API2MCP_PORT_FRONTEND=34076
API2MCP_PORT_BACKEND=34086
```

### 2. Database Connection Failed

**Problem**: Cannot connect to database during initialization or service startup

**Possible Causes and Solutions**:
- **PostgreSQL not running**: Ensure PostgreSQL service is running
- **Incorrect connection config**: Check database connection parameters in `.env` file
- **Insufficient permissions**: Ensure the database user has access permissions

### 3. Tool Name and Version Conflict

**Problem**: "Tool name and version combination already exists" when creating a tool

**Solution**:
- Use a different tool name or version number
- Or delete the existing tool with the same name and version first

### 4. Frontend Cannot Access Backend API

**Problem**: Frontend page cannot load data properly

**Solution**:
- Ensure backend service is running
- Check browser console for network errors
- Verify port configuration in `.env` file

### 5. uv Command Not Found

**Problem**: "uv command not found" when executing `uv run`

**Solution**:
```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or use pip instead
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python ../init_db.py
```

## License

MIT
