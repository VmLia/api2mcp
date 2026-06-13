# API2MCP
[English Documentation](./README.md)

**企业痛点：**
- 企业做智能体开发时，面临已建项目和智能体的高效集成问题，尤其是智能体需要调用已有系统的数据服务接口，通常这些接口是 RESTful API 为主，而对于智能体来说，比较友好的数据获取方式是 MCP 协议。

**REST API 到 MCP 的桥接工具**
- 企业需要一个简单、安全、可扩展的解决方案，能够快速集成新的 API 到智能体中。
- 将任意 REST API 转换为 MCP（Model Context Protocol）工具，让 AI 智能体能够发现并调用你的 API。

## 已实现功能特性

- **可视化管理界面** - 通过分步向导配置 API
- **传输协议支持** - Streamable HTTP（当前支持），stdio（计划中）
- **动态工具发现** - MCP 客户端可自动发现所有已注册工具
- **工具隔离** - 通过根端点暴露所有工具，或按工具名/版本隔离
- **参数树** - 支持嵌套参数结构
- **鉴权配置** - 可复用的鉴权配置（API Key、Bearer Token、Basic Auth）
- **环境变量** - 安全的凭证管理，支持变量替换
- **输出映射** - 使用 JMESPath 模板转换响应数据

## Roadmap
<img width="1536" height="1024" alt="ed8897c34d2cef04700f16e6173a47e4" src="https://github.com/user-attachments/assets/f1106853-fa26-44d5-9bda-60d7982f2e88" />


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
```

#### 方式一：Macbook 一键安装（推荐）

```bash
# 一键安装所有依赖（后端 + 前端）
./start-mac.sh setup
```

#### 方式二：手动安装（适用于 Linux/Windows 或需要自定义配置）

```bash
# 1. 安装后端 Python 依赖
cd backend

# 使用 uv（推荐）
uv venv .venv
uv sync

# 或使用 pip（备选方案）
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. 安装前端依赖
cd ../frontend
npm install
```

### 2. 安装数据库（可选）

> 如已有 PostgreSQL 数据库，可直接跳到第 3 步配置连接信息。

#### 方式一：使用 Docker Compose（推荐）

```bash
# 使用 Docker Compose 一键启动 PostgreSQL
cd docker-compose-api2mcp
docker compose -f docker-compose-middleware.yaml up -d
```

> **说明**：使用此方式需要先安装 Docker 和 Docker Compose。

#### 方式二：使用已有 PostgreSQL 数据库

如果系统已安装 PostgreSQL，需要创建对应的数据库和用户：

```sql
-- 创建数据库
CREATE DATABASE api2mcp;

-- 创建用户
CREATE USER api2mcp WITH PASSWORD 'api2mcp@123';

-- 授予权限
GRANT ALL PRIVILEGES ON DATABASE api2mcp TO api2mcp;
```

> **注意**：确保 `.env` 文件中的数据库连接配置与你的 PostgreSQL 配置一致。

### 3. 配置初始化

复制示例配置文件并修改数据库连接：

```bash
cp .env.example .env
```

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

#### 方式二：手动启动（适用于 Linux/Windows 或需要自定义配置）
```bash
# 开发模式（后端日志实时显示，在 backend 目录下执行即可）
cd backend
source .venv/bin/activate  
uv run uvicorn main:app --host 0.0.0.0 --port 34085 --reload

# 前端开发模式（在 frontend 目录下执行）
cd ../frontend
npm run dev
```

> **说明**：端口配置从 `.env` 文件读取（API2MCP_PORT_FRONTEND=34075），无需额外参数。如需临时指定端口，可使用环境变量：
> ```bash
> API2MCP_PORT_FRONTEND=34075 npm run dev
> ```

在浏览器中打开 http://localhost:34075

## 容器化部署

### Docker Compose 文件

项目提供了三个 Docker Compose 文件，用于不同的部署场景：

| 文件 | 说明 | 命令 |
|------|------|------|
| `docker-compose-all.yaml` | 启动所有服务（应用 + 数据库） | `docker compose -f docker-compose-all.yaml up -d` |
| `docker-compose-api2mcp.yaml` | 只启动应用（需要预先配置数据库） | `docker compose -f docker-compose-api2mcp.yaml up -d` |
| `docker-compose-middleware.yaml` | 只启动数据库中间件 | `docker compose -f docker-compose-middleware.yaml up -d` |

### 使用 Docker Compose 构建和运行

```bash
# 进入 docker-compose 目录
cd docker-compose-api2mcp

# 启动所有服务（应用 + 数据库）
docker compose -f docker-compose-all.yaml up -d

# 查看服务状态
docker compose -f docker-compose-all.yaml ps

# 查看日志
docker compose -f docker-compose-all.yaml logs -f api2mcp

# 停止服务
docker compose -f docker-compose-all.yaml down
```

### Docker 环境变量配置

你可以通过环境变量自定义数据库配置：

```bash
export DB_HOST=localhost
export DB_PORT=5432
export DB_USER=myuser
export DB_PASSWORD=mypassword
export DB_NAME=mydatabase

docker compose -f docker-compose-api2mcp.yaml up -d
```

### 多架构构建

要构建同时兼容 x86-64 和 ARM64 架构的镜像（例如从 M4 Mac 构建部署到 Intel 服务器）：

```bash
# 设置你的镜像仓库（可选）
export REGISTRY="docker.io/your-username/"
export IMAGE_TAG="v1.0.0"

# 运行多架构构建
./build-multiarch.sh
```

该脚本将为 `linux/amd64` 和 `linux/arm64` 两个平台构建并推送镜像。

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
│   ├── src/              # 源代码目录
│   │   └── api2mcp/      # 包目录
│   │       ├── controller/   # REST API 控制器
│   │       ├── service/      # 业务逻辑层
│   │       ├── repository/   # 数据访问层
│   │       ├── model/        # 数据库模型
│   │       ├── database/     # 数据库配置
│   │       ├── config/       # 应用配置
│   │       ├── middleware/   # 自定义中间件
│   │       └── main.py       # 应用入口
│   ├── pyproject.toml    # Python 项目配置（uv）
│   ├── uv.lock           # uv 依赖锁文件
│   └── requirements.txt  # Python 依赖（pip 兼容）
├── frontend/             # Vue 3 + TypeScript 前端
│   ├── src/
│   │   ├── views/        # 页面组件
│   │   ├── stores/       # Pinia 状态管理
│   │   ├── router/       # 路由配置
│   │   ├── main.ts       # 入口文件
│   │   └── App.vue       # 根组件
│   ├── index.html        # HTML 模板
│   ├── package.json      # Node.js 依赖配置
│   ├── package-lock.json # Node.js 依赖锁文件
│   ├── vite.config.ts    # Vite 构建配置
│   ├── tsconfig.json     # TypeScript 配置
│   └── tsconfig.node.json # TypeScript Node 配置
├── docker-compose-api2mcp/  # Docker Compose 配置文件
│   ├── docker-compose-all.yaml        # 所有服务（应用 + 数据库）
│   ├── docker-compose-api2mcp.yaml    # 仅应用
│   └── docker-compose-middleware.yaml # 仅数据库
├── .env                  # 配置文件（前后端共用）
├── .env.example          # 配置文件示例
├── Dockerfile            # 一体化部署的 Docker 镜像
├── build-multiarch.sh    # 多架构构建脚本
├── start-mac.sh          # 跨平台启动脚本（macOS/Linux）
├── stop-mac.sh           # 跨平台停止脚本（macOS/Linux）
├── entrypoint.sh         # Docker 入口脚本
├── init_db.py            # 数据库初始化脚本
└── README.md             # 英文文档
```

## API 接口

### 管理 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/serverapi/apimng/tools` | 获取工具列表 |
| POST | `/serverapi/apimng/tools` | 创建工具 |
| GET | `/serverapi/apimng/tools/{id}` | 获取工具详情 |
| PUT | `/serverapi/apimng/tools/{id}` | 更新工具 |
| DELETE | `/serverapi/apimng/tools/{id}` | 删除工具 |
| GET | `/serverapi/apimng/tools/{id}/parameters` | 获取工具参数 |
| POST | `/serverapi/apimng/tools/{id}/parameters` | 创建参数 |
| PUT | `/serverapi/apimng/tools/{id}/parameters/{param_id}` | 更新参数 |
| DELETE | `/serverapi/apimng/tools/{id}/parameters/{param_id}` | 删除参数 |
| GET | `/serverapi/apimng/auth-configs` | 获取鉴权配置列表 |
| POST | `/serverapi/apimng/auth-configs` | 创建鉴权配置 |
| DELETE | `/serverapi/apimng/auth-configs/{id}` | 删除鉴权配置 |
| GET | `/serverapi/apimng/env-variables` | 获取环境变量列表 |
| POST | `/serverapi/apimng/env-variables` | 创建环境变量 |
| DELETE | `/serverapi/apimng/env-variables/{id}` | 删除环境变量 |
| GET | `/serverapi/apimng/semantic-tags` | 获取语义标签列表 |
| GET | `/serverapi/apimng/server-info` | 获取服务器信息 |

### MCP Server 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST | `/mcpapi` | MCP JSON-RPC 根端点 |
| GET/POST | `/mcpapi/{identifier}` | 按标识符隔离的端点 |
| GET/POST | `/mcpapi/{tool_name}/{version}` | 按工具名+版本隔离的端点 |

## 常见问题

### 1. 端口被占用

**问题**：启动服务时提示端口已被占用

**解决方案**：
```bash
# 查看哪个进程占用了端口
lsof -i :34075  # 前端端口
lsof -i :34085  # 后端端口

# 杀死占用端口的进程
kill -9 <PID>

# 或修改 .env 文件使用其他端口
API2MCP_PORT_FRONTEND=34076
API2MCP_PORT_BACKEND=34086
```

### 2. 数据库连接失败

**问题**：初始化数据库或启动服务时提示无法连接数据库

**可能原因及解决方案**：
- **PostgreSQL 未启动**：确保 PostgreSQL 服务正在运行
- **连接配置错误**：检查 `.env` 文件中的数据库连接参数
- **权限不足**：确保数据库用户有权限访问数据库

### 3. 工具名称和版本重复

**问题**：创建工具时提示 "Tool name and version combination already exists"

**解决方案**：
- 使用不同的工具名称或版本号
- 或先删除已存在的同名工具

### 4. 前端无法访问后端 API

**问题**：前端页面无法正常加载数据

**解决方案**：
- 确保后端服务已启动
- 检查浏览器控制台是否有网络错误
- 确保 `.env` 文件中的端口配置正确

### 5. uv 命令未找到

**问题**：执行 `uv run` 时提示命令未找到

**解决方案**：
```bash
# 安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 或使用 pip 替代
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python ../init_db.py
```

### 6. 容器镜像兼容性

**问题**：在 M4 Mac（ARM64）上构建的镜像无法在 x86-64 Linux 服务器上运行

**解决方案**：
```bash
# 使用多架构构建脚本
./build-multiarch.sh
```

这将为 `linux/amd64` 和 `linux/arm64` 两个平台构建镜像。

## 许可证

MIT
