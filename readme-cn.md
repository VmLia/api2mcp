# API2MCP
[English Documentation](./README.md)

**企业痛点：**
- 企业做智能体开发时，面临已建项目和智能体的高效集成问题，尤其是智能体需要调用已有系统的数据服务接口，通常这些接口是 RESTful API 为主，而对于智能体来说，比较友好的数据获取方式是 MCP 协议。

**REST API 到 MCP 的桥接工具**
- 企业需要一个简单、安全、可扩展的解决方案，能够快速集成新的 API 到智能体中。
- 将任意 REST API 转换为 MCP（Model Context Protocol）工具，让 AI 智能体能够发现并调用你的 API。

## 功能特性

- **可视化管理界面** - 通过分步向导配置 API
- **传输协议支持** - Streamable HTTP（当前支持），stdio（计划中）
- **动态工具发现** - MCP 客户端可自动发现所有已注册工具
- **工具隔离** - 通过根端点暴露所有工具，或按工具名/版本隔离
- **参数树** - 支持嵌套参数结构
- **鉴权配置** - 可复用的鉴权配置（API Key、Bearer Token、Basic Auth）
- **环境变量** - 安全的凭证管理，支持变量替换
- **输出映射** - 使用 JMESPath 模板转换响应数据

## 快速开始

### 前置要求

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+

### 操作步骤

```
1. 克隆项目到本地
2. 安装数据库（如有已有数据库可直接配置，跳过此步）
3. 配置初始化
4. 初始化数据库
5. 启动服务
```

### 1. 克隆与安装

```bash
git clone https://github.com/VmLia/api2mcp.git
cd api2mcp

# 一键安装所有依赖（后端 + 前端）
./start.sh setup
```

### 2. 安装数据库（可选）

> 如已有 PostgreSQL 数据库，可直接跳到第 3 步配置连接信息。

```bash
# 使用 Docker Compose 一键启动 PostgreSQL
cd docker-compose-api2mcp
docker compose -f docker-compose-api2mcp.yaml up -d
```

### 3. 配置初始化

编辑 `.env` 文件，配置数据库连接：

```bash
# 数据库（必需）
DB_TYPE=postgresql
DB_HOST=127.0.0.1
DB_PORT=5432
DB_USER=api2mcp
DB_PASSWORD=api2mcp@123
DB_NAME=api2mcp
DB_DRIVER=asyncpg

# 端口（可选，以下为默认值）
API2MCP_PORT_BACKEND=34085
API2MCP_PORT_FRONTEND=34075

# MCP 公开访问地址（可选，生产环境部署时设置）
# 留空则默认使用 http://127.0.0.1:34085/mcpapi
MCP_PUBLIC_BASE_URL=
```

### 4. 初始化数据库

```bash
cd backend
source .venv/bin/activate  # 或使用: uv run

# 仅创建表结构
python ../init_db.py

# 或创建表结构 + 导入示例数据
python ../init_db.py --seed
```

### 5. 启动服务

#### 方式一：Macbook 一键启动服务
```bash
# 开发模式（同时启动前后端应用，后端日志实时显示）
./start-mac.sh
```
#### 方式二：命令启动
```bash
# 开发模式（后端日志实时显示，在 backend 目录下执行即可）
cd api2mcp/backend
source .venv/bin/activate  
uv run main.py --reload

# 前端开发模式（在 frontend 目录下执行）
cd api2mcp/frontend
npm run dev --port 34075 --host 0.0.0.0
```

在浏览器中打开 http://localhost:34075

## MCP 端点

| 端点 | 说明 |
|------|------|
| `GET/POST /mcpapi` | 根端点 - 暴露所有活跃工具 |
| `GET/POST /mcpapi/{identifier}` | 按标识符隔离的端点（支持 UUID 或工具名称） |
| `GET/POST /mcpapi/{tool_name}/{version}` | 按工具名+版本隔离的端点 |

## MCP 客户端配置

**推荐客户端：CherryStudio / MCP Inspector**

- 传输模式：`streamable-http`
- URL：使用管理页面中生成的 MCP Server URL（格式：`http://localhost:34085/mcpapi/{tool_name}/{version}`）

## 项目结构

```
api2mcp/
├── backend/              # Python FastAPI 后端
│   ├── main.py           # 应用入口
│   ├── api.py            # 管理 API 路由
│   ├── mcp_server.py     # MCP 协议实现
│   ├── api_info.py       # 数据库模型
│   ├── config.py         # 配置
│   ├── database.py       # 数据库连接
│   └── requirements.txt  # Python 依赖
├── frontend/             # Vue 3 + TypeScript 前端
│   ├── src/
│   │   ├── views/        # 页面组件
│   │   ├── stores/       # Pinia 状态管理
│   │   ├── router/       # 路由配置
│   │   └── App.vue       # 根组件
│   └── package.json
├── docker-compose-api2mcp/  # Docker 数据库部署
├── .env                  # 配置文件（前后端共用）
├── start.sh              # 启动脚本
├── stop.sh               # 停止脚本
└── init_db.py            # 数据库初始化
```

## API 接口

### 管理 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/serverapi/apimng/projects` | 获取项目列表 |
| POST | `/serverapi/apimng/projects` | 创建项目 |
| GET | `/serverapi/apimng/projects/{id}` | 获取项目详情 |
| PUT | `/serverapi/apimng/projects/{id}` | 更新项目 |
| DELETE | `/serverapi/apimng/projects/{id}` | 删除项目 |
| GET | `/serverapi/apimng/projects/{id}/parameters` | 获取项目参数 |
| POST | `/serverapi/apimng/projects/{id}/parameters` | 创建参数 |
| PUT | `/serverapi/apimng/projects/{id}/parameters/{param_id}` | 更新参数 |
| DELETE | `/serverapi/apimng/projects/{id}/parameters/{param_id}` | 删除参数 |
| GET | `/serverapi/apimng/auth-configs` | 获取鉴权配置列表 |
| POST | `/serverapi/apimng/auth-configs` | 创建鉴权配置 |
| DELETE | `/serverapi/apimng/auth-configs/{id}` | 删除鉴权配置 |
| GET | `/serverapi/apimng/server-info` | 获取服务器信息 |

### MCP Server 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST | `/mcpapi` | MCP JSON-RPC 根端点 |
| GET/POST | `/mcpapi/{identifier}` | 按标识符隔离的端点 |
| GET/POST | `/mcpapi/{tool_name}/{version}` | 按工具名+版本隔离的端点 |

## 许可证

MIT