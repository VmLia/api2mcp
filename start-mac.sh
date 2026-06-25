#!/bin/bash
#
# API2MCP Startup Script
# Supports uv or pip for Python environment management
# Cross-platform: macOS, CentOS, Ubuntu
#

set -e

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${SCRIPT_DIR}/backend"
FRONTEND_DIR="${SCRIPT_DIR}/frontend"
INIT_DIR="${SCRIPT_DIR}/init"
PID_DIR="${SCRIPT_DIR}/pids"
LOG_DIR="${SCRIPT_DIR}/logs"

# Load environment variables
if [ -f "${SCRIPT_DIR}/.env" ]; then
    source "${SCRIPT_DIR}/.env"
fi

# Default port configuration
API2MCP_PORT_FRONTEND="${API2MCP_PORT_FRONTEND:-34075}"
API2MCP_PORT_BACKEND="${API2MCP_PORT_BACKEND:-34085}"
UVICORN_ACCESS_LOG="${UVICORN_ACCESS_LOG:-true}"

# Database initialization config
API2MCP_DB_DEL="${API2MCP_DB_DEL:-false}"
API2MCP_INIT_DATA="${API2MCP_INIT_DATA:-true}"

# Build uvicorn command with access log control
if [ "${UVICORN_ACCESS_LOG}" = "true" ] || [ "${UVICORN_ACCESS_LOG}" = "1" ]; then
    UVICORN_ACCESS_LOG_FLAG="--access-log"
else
    UVICORN_ACCESS_LOG_FLAG="--no-access-log"
fi

# Create necessary directories
mkdir -p "${PID_DIR}"
mkdir -p "${LOG_DIR}"

# Log files
BACKEND_LOG="${LOG_DIR}/backend.log"
FRONTEND_LOG="${LOG_DIR}/frontend.log"
INIT_LOG="${LOG_DIR}/init.log"

# PID files
BACKEND_PID="${PID_DIR}/backend.pid"
FRONTEND_PID="${PID_DIR}/frontend.pid"
WATCHDOG_PID="${PID_DIR}/watchdog.pid"

# ============================================
# Utility Functions
# ============================================

# Check if port is occupied (cross-platform compatible)
check_port() {
    local port=$1
    if command -v ss &> /dev/null; then
        if ss -tlnp | grep -q ":${port} "; then
            return 1
        fi
    elif command -v lsof &> /dev/null; then
        if lsof -i ":${port}" > /dev/null 2>&1; then
            return 1
        fi
    elif command -v netstat &> /dev/null; then
        if netstat -tlnp 2>/dev/null | grep -q ":${port} " || netstat -an 2>/dev/null | grep -q ".${port} "; then
            return 1
        fi
    fi
    return 0
}

# Kill process occupying port
kill_port() {
    local port=$1
    echo -e "${YELLOW}Cleaning up process on port ${port}...${NC}"
    
    if command -v ss &> /dev/null; then
        local pids=$(ss -tlnp | grep ":${port} " | awk '{print $7}' | sed 's/,.*//; s/.*=//' | grep -v '^$')
        if [ -n "${pids}" ]; then
            kill -9 ${pids} 2>/dev/null || true
        fi
    elif command -v lsof &> /dev/null; then
        lsof -ti ":${port}" | xargs kill -9 2>/dev/null || true
    elif command -v fuser &> /dev/null; then
        fuser -k -n tcp "${port}" 2>/dev/null || true
    fi
    sleep 1
}

# Check if command exists
check_command() {
    local cmd=$1
    if ! command -v ${cmd} &> /dev/null; then
        echo -e "${RED}Error: ${cmd} not installed${NC}"
        case "${cmd}" in
            uv)
                echo -e "${YELLOW}Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh${NC}"
                ;;
            npm)
                echo -e "${YELLOW}Install Node.js: https://nodejs.org/en/download/package-manager/${NC}"
                ;;
        esac
        exit 1
    fi
}

# ============================================
# Environment & Dependencies
# ============================================

check_uv() {
    check_command uv
    echo -e "${GREEN}✓ uv installed${NC}"
}

init_python_env() {
    echo -e "${BLUE}==> Initializing Python environment...${NC}"

    cd "${BACKEND_DIR}"

    if command -v uv &> /dev/null; then
        echo -e "${GREEN}✓ uv detected, using uv for environment management${NC}"

        if [ -d ".venv" ]; then
            echo -e "${GREEN}✓ Python virtual environment already exists${NC}"
        else
            echo -e "${YELLOW}Creating Python virtual environment...${NC}"
            uv venv .venv
        fi

        echo -e "${YELLOW}Installing/updating Python dependencies...${NC}"
        uv sync
    else
        echo -e "${YELLOW}uv not detected, using pip...${NC}"

        if [ -d ".venv" ]; then
            echo -e "${GREEN}✓ Python virtual environment already exists${NC}"
        else
            echo -e "${YELLOW}Creating Python virtual environment...${NC}"
            python3 -m venv .venv || python -m venv .venv
        fi

        source .venv/bin/activate
        echo -e "${YELLOW}Installing Python dependencies...${NC}"
        pip install -r requirements.txt
    fi

    echo -e "${GREEN}✓ Python environment ready${NC}"
}

init_frontend_deps() {
    echo -e "${BLUE}==> Checking frontend dependencies...${NC}"
    
    check_command npm
    
    cd "${FRONTEND_DIR}"
    
    if [ ! -d "node_modules" ]; then
        echo -e "${YELLOW}Installing frontend dependencies...${NC}"
        npm install
    else
        echo -e "${GREEN}✓ Frontend dependencies already installed${NC}"
    fi
}

# ============================================
# Database Initialization
# ============================================

init_database() {
    echo -e "${BLUE}==> Initializing database...${NC}"
    echo -e "${YELLOW}  API2MCP_DB_DEL: ${API2MCP_DB_DEL}${NC}"
    
    cd "${BACKEND_DIR}"
    source .venv/bin/activate
    
    # Run database table initialization
    echo -e "${YELLOW}Creating database tables...${NC}"
    if python "${INIT_DIR}/init_db.py" 2>&1 | tee -a "${INIT_LOG}"; then
        echo -e "${GREEN}✓ Database tables initialized${NC}"
    else
        echo -e "${RED}✗ Database table initialization failed${NC}"
        return 1
    fi
    
    # Initialize default data if enabled
    if [ "${API2MCP_INIT_DATA}" = "true" ]; then
        echo -e "${YELLOW}Loading initial data...${NC}"
        if [ -f "${INIT_DIR}/init_db_data.py" ]; then
            if python "${INIT_DIR}/init_db_data.py" 2>&1 | tee -a "${INIT_LOG}"; then
                echo -e "${GREEN}✓ Initial data loaded${NC}"
            else
                echo -e "${YELLOW}⚠ Initial data loading failed (continuing)${NC}"
            fi
        else
            echo -e "${YELLOW}⚠ init_db_data.py not found, skipping${NC}"
        fi
    else
        echo -e "${YELLOW}⚠ Initial data loading disabled (API2MCP_INIT_DATA=false)${NC}"
    fi
    
    echo -e "${GREEN}✓ Database initialization completed${NC}"
}

# ============================================
# Service Management
# ============================================

start_backend() {
    echo -e "${BLUE}==> Starting backend service...${NC}"
    
    cd "${BACKEND_DIR}"
    source .venv/bin/activate
    
    if ! check_port ${API2MCP_PORT_BACKEND}; then
        echo -e "${YELLOW}Warning: Port ${API2MCP_PORT_BACKEND} is occupied, cleaning up...${NC}"
        kill_port ${API2MCP_PORT_BACKEND}
    fi
    
    echo -e "${YELLOW}Starting backend service (port: ${API2MCP_PORT_BACKEND})...${NC}"
    echo -e "${YELLOW}API Docs: http://localhost:${API2MCP_PORT_BACKEND}/apidocs${NC}"
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  Backend Service Log (Real-time)${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    
    uvicorn api2mcp.main:app --host 0.0.0.0 --port ${API2MCP_PORT_BACKEND} --log-level info --reload ${UVICORN_ACCESS_LOG_FLAG}
}

start_backend_bg() {
    echo -e "${BLUE}==> Starting backend service...${NC}"
    
    cd "${BACKEND_DIR}"
    source .venv/bin/activate
    
    if ! check_port ${API2MCP_PORT_BACKEND}; then
        echo -e "${YELLOW}Warning: Port ${API2MCP_PORT_BACKEND} is occupied, cleaning up...${NC}"
        kill_port ${API2MCP_PORT_BACKEND}
    fi
    
    echo -e "${YELLOW}Starting backend service (port: ${API2MCP_PORT_BACKEND})...${NC}"
    nohup uvicorn api2mcp.main:app --host 0.0.0.0 --port ${API2MCP_PORT_BACKEND} --log-level info --reload ${UVICORN_ACCESS_LOG_FLAG} > "${BACKEND_LOG}" 2>&1 &
    echo $! > "${BACKEND_PID}"
    
    sleep 3
    
    if curl -s http://localhost:${API2MCP_PORT_BACKEND}/apidocs > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Backend service started successfully (PID: $(cat ${BACKEND_PID}))${NC}"
        echo -e "${GREEN}  API Docs: http://localhost:${API2MCP_PORT_BACKEND}/apidocs${NC}"
    else
        echo -e "${RED}✗ Backend service failed to start, check logs: ${BACKEND_LOG}${NC}"
        return 1
    fi
}

start_frontend() {
    echo -e "${BLUE}==> Starting frontend service...${NC}"
    
    check_command npm
    
    cd "${FRONTEND_DIR}"
    
    if [ ! -d "node_modules" ]; then
        echo -e "${YELLOW}Installing frontend dependencies...${NC}"
        npm install
    fi
    
    if ! check_port ${API2MCP_PORT_FRONTEND}; then
        echo -e "${YELLOW}Warning: Port ${API2MCP_PORT_FRONTEND} is occupied, cleaning up...${NC}"
        kill_port ${API2MCP_PORT_FRONTEND}
    fi
    
    echo -e "${YELLOW}Starting frontend service (port: ${API2MCP_PORT_FRONTEND})...${NC}"
    nohup npm run dev > "${FRONTEND_LOG}" 2>&1 &
    echo $! > "${FRONTEND_PID}"
    
    sleep 5
    
    if ! check_port ${API2MCP_PORT_FRONTEND}; then
        echo -e "${GREEN}✓ Frontend service started successfully (PID: $(cat ${FRONTEND_PID}))${NC}"
        echo -e "${GREEN}  Frontend: http://localhost:${API2MCP_PORT_FRONTEND}${NC}"
    else
        echo -e "${RED}✗ Frontend service failed to start, check logs: ${FRONTEND_LOG}${NC}"
        return 1
    fi
}

stop_services() {
    echo -e "${BLUE}==> Stopping services...${NC}"
    
    # Stop backend
    if [ -f "${BACKEND_PID}" ]; then
        local backend_pid=$(cat "${BACKEND_PID}")
        if kill -0 ${backend_pid} 2>/dev/null; then
            echo -e "${YELLOW}Stopping backend service (PID: ${backend_pid})...${NC}"
            kill ${backend_pid}
            sleep 1
        fi
        rm -f "${BACKEND_PID}"
    fi
    
    if ! check_port ${API2MCP_PORT_BACKEND}; then
        kill_port ${API2MCP_PORT_BACKEND}
    fi
    
    # Stop frontend
    if [ -f "${FRONTEND_PID}" ]; then
        local frontend_pid=$(cat "${FRONTEND_PID}")
        if kill -0 ${frontend_pid} 2>/dev/null; then
            echo -e "${YELLOW}Stopping frontend service (PID: ${frontend_pid})...${NC}"
            kill ${frontend_pid}
            sleep 1
        fi
        rm -f "${FRONTEND_PID}"
    fi
    
    if ! check_port ${API2MCP_PORT_FRONTEND}; then
        kill_port ${API2MCP_PORT_FRONTEND}
    fi
    
    # Stop watchdog
    stop_watchdog
    
    echo -e "${GREEN}✓ All services stopped${NC}"
}

# ============================================
# Watchdog
# ============================================

start_watchdog() {
    if [ -f "${WATCHDOG_PID}" ]; then
        local old_pid=$(cat "${WATCHDOG_PID}")
        if kill -0 ${old_pid} 2>/dev/null; then
            kill ${old_pid} 2>/dev/null
        fi
        rm -f "${WATCHDOG_PID}"
    fi
    
    nohup "${SCRIPT_DIR}/start-mac.sh" --watchdog > "${LOG_DIR}/watchdog.log" 2>&1 &
    echo $! > "${WATCHDOG_PID}"
    echo -e "${GREEN}✓ Watchdog started (PID: $(cat ${WATCHDOG_PID}))${NC}"
}

stop_watchdog() {
    if [ -f "${WATCHDOG_PID}" ]; then
        local watchdog_pid=$(cat "${WATCHDOG_PID}")
        if kill -0 ${watchdog_pid} 2>/dev/null; then
            kill ${watchdog_pid} 2>/dev/null
        fi
        rm -f "${WATCHDOG_PID}"
    fi
}

run_watchdog() {
    set +e
    
    echo -e "$(date '+%Y-%m-%d %H:%M:%S') [Watchdog] Started, monitoring every 30s..." >> "${LOG_DIR}/watchdog.log"
    
    while true; do
        sleep 30
        
        # Check backend
        local backend_alive=false
        if [ -f "${BACKEND_PID}" ]; then
            local backend_pid=$(cat "${BACKEND_PID}")
            if kill -0 ${backend_pid} 2>/dev/null; then
                backend_alive=true
            fi
        fi
        if [ "${backend_alive}" = "false" ]; then
            if ! check_port ${API2MCP_PORT_BACKEND}; then
                backend_alive=true
            fi
        fi
        if [ "${backend_alive}" = "false" ]; then
            echo -e "$(date '+%Y-%m-%d %H:%M:%S') [Watchdog] Backend crashed, restarting..." >> "${LOG_DIR}/watchdog.log"
            rm -f "${BACKEND_PID}"
            (start_backend_bg 2>&1) >> "${LOG_DIR}/watchdog.log"
        fi
        
        # Check frontend
        local frontend_alive=false
        if [ -f "${FRONTEND_PID}" ]; then
            local frontend_pid=$(cat "${FRONTEND_PID}")
            if kill -0 ${frontend_pid} 2>/dev/null; then
                frontend_alive=true
            fi
        fi
        if [ "${frontend_alive}" = "false" ]; then
            if ! check_port ${API2MCP_PORT_FRONTEND}; then
                frontend_alive=true
            fi
        fi
        if [ "${frontend_alive}" = "false" ]; then
            echo -e "$(date '+%Y-%m-%d %H:%M:%S') [Watchdog] Frontend crashed, restarting..." >> "${LOG_DIR}/watchdog.log"
            rm -f "${FRONTEND_PID}"
            (start_frontend 2>&1) >> "${LOG_DIR}/watchdog.log"
        fi
    done
}

# ============================================
# Status & Logs
# ============================================

status() {
    echo -e "${BLUE}==> Service Status${NC}"
    
    # Backend status
    if [ -f "${BACKEND_PID}" ]; then
        local backend_pid=$(cat "${BACKEND_PID}")
        if kill -0 ${backend_pid} 2>/dev/null; then
            echo -e "${GREEN}✓ Backend running (PID: ${backend_pid}, Port: ${API2MCP_PORT_BACKEND})${NC}"
        else
            if ! check_port ${API2MCP_PORT_BACKEND}; then
                local actual_pid=$(lsof -ti ":${API2MCP_PORT_BACKEND}" 2>/dev/null)
                echo -e "${YELLOW}⚠ Backend running (PID: ${actual_pid:-unknown}, Port: ${API2MCP_PORT_BACKEND}, stale PID: ${backend_pid})${NC}"
            else
                echo -e "${RED}✗ Backend not running (stale PID file)${NC}"
            fi
        fi
    else
        if ! check_port ${API2MCP_PORT_BACKEND}; then
            local actual_pid=$(lsof -ti ":${API2MCP_PORT_BACKEND}" 2>/dev/null)
            echo -e "${YELLOW}⚠ Backend running (PID: ${actual_pid:-unknown}, Port: ${API2MCP_PORT_BACKEND})${NC}"
        else
            echo -e "${RED}✗ Backend not running${NC}"
        fi
    fi
    
    # Frontend status
    if [ -f "${FRONTEND_PID}" ]; then
        local frontend_pid=$(cat "${FRONTEND_PID}")
        if kill -0 ${frontend_pid} 2>/dev/null; then
            echo -e "${GREEN}✓ Frontend running (PID: ${frontend_pid}, Port: ${API2MCP_PORT_FRONTEND})${NC}"
        else
            if ! check_port ${API2MCP_PORT_FRONTEND}; then
                local actual_pid=$(lsof -ti ":${API2MCP_PORT_FRONTEND}" 2>/dev/null)
                echo -e "${YELLOW}⚠ Frontend running (PID: ${actual_pid:-unknown}, Port: ${API2MCP_PORT_FRONTEND}, stale PID: ${frontend_pid})${NC}"
            else
                echo -e "${RED}✗ Frontend not running (stale PID file)${NC}"
            fi
        fi
    else
        if ! check_port ${API2MCP_PORT_FRONTEND}; then
            local actual_pid=$(lsof -ti ":${API2MCP_PORT_FRONTEND}" 2>/dev/null)
            echo -e "${YELLOW}⚠ Frontend running (PID: ${actual_pid:-unknown}, Port: ${API2MCP_PORT_FRONTEND})${NC}"
        else
            echo -e "${RED}✗ Frontend not running${NC}"
        fi
    fi
    
    # Watchdog status
    if [ -f "${WATCHDOG_PID}" ]; then
        local watchdog_pid=$(cat "${WATCHDOG_PID}")
        if kill -0 ${watchdog_pid} 2>/dev/null; then
            echo -e "${GREEN}✓ Watchdog running (PID: ${watchdog_pid})${NC}"
        else
            echo -e "${RED}✗ Watchdog not running (stale PID file)${NC}"
        fi
    else
        echo -e "${YELLOW}⚠ Watchdog not running${NC}"
    fi
}

logs() {
    local service=$1
    
    case $service in
        backend)
            if [ -f "${BACKEND_LOG}" ]; then
                tail -100 "${BACKEND_LOG}"
            else
                echo -e "${RED}Backend log file does not exist${NC}"
            fi
            ;;
        frontend)
            if [ -f "${FRONTEND_LOG}" ]; then
                tail -100 "${FRONTEND_LOG}"
            else
                echo -e "${RED}Frontend log file does not exist${NC}"
            fi
            ;;
        init)
            if [ -f "${INIT_LOG}" ]; then
                tail -100 "${INIT_LOG}"
            else
                echo -e "${RED}Init log file does not exist${NC}"
            fi
            ;;
        *)
            echo -e "${YELLOW}Usage: $0 logs [backend|frontend|init]${NC}"
            ;;
    esac
}

# ============================================
# Help
# ============================================

show_help() {
    echo -e "${BLUE}API2MCP Startup Script${NC}"
    echo ""
    echo -e "${GREEN}Usage:${NC}"
    echo "  $0                      Start all services (backend foreground)"
    echo "  $0 start                Same as above"
    echo "  $0 start-bg             Start all services (background)"
    echo "  $0 start-bg --watchdog  Start with auto-restart watchdog"
    echo "  $0 stop                 Stop all services"
    echo "  $0 restart              Restart services"
    echo "  $0 restart-bg           Restart services (background)"
    echo "  $0 restart-bg --watchdog Restart with watchdog"
    echo "  $0 setup                Install dependencies only"
    echo "  $0 init                 Initialize database only"
    echo "  $0 status               Show service status"
    echo "  $0 logs [service]       View logs (backend/frontend/init)"
    echo "  $0 help                 Show this help"
    echo ""
    echo -e "${GREEN}Environment Variables (.env):${NC}"
    echo "  API2MCP_PORT_FRONTEND   Frontend port (default: 34075)"
    echo "  API2MCP_PORT_BACKEND    Backend port (default: 34085)"
    echo "  API2MCP_DB_DEL          Drop tables on startup (true/false, default: false)"
    echo "  API2MCP_INIT_DATA       Load initial data (true/false, default: true)"
    echo ""
    echo -e "${GREEN}Examples:${NC}"
    echo "  $0                              # Start all services"
    echo "  $0 start-bg --watchdog          # Background with watchdog"
    echo "  API2MCP_DB_DEL=true $0          # Reset database on start"
    echo "  $0 init                         # Initialize database only"
}

# ============================================
# Main Entry Points
# ============================================

start_all_foreground() {
    check_uv
    init_python_env
    init_frontend_deps
    init_database
    start_all_foreground_services
}

start_all_foreground_services() {
    # Start frontend first (background)
    echo -e "${BLUE}==> Starting frontend service...${NC}"
    
    check_command npm
    cd "${FRONTEND_DIR}"
    
    if [ ! -d "node_modules" ]; then
        echo -e "${YELLOW}Installing frontend dependencies...${NC}"
        npm install
    fi
    
    if ! check_port ${API2MCP_PORT_FRONTEND}; then
        echo -e "${YELLOW}Warning: Port ${API2MCP_PORT_FRONTEND} is occupied, cleaning up...${NC}"
        kill_port ${API2MCP_PORT_FRONTEND}
    fi
    
    echo -e "${YELLOW}Starting frontend service (port: ${API2MCP_PORT_FRONTEND})...${NC}"
    nohup npm run dev > "${FRONTEND_LOG}" 2>&1 &
    echo $! > "${FRONTEND_PID}"
    
    sleep 5
    
    if ! check_port ${API2MCP_PORT_FRONTEND}; then
        echo -e "${GREEN}✓ Frontend service started successfully${NC}"
        echo -e "${GREEN}  Frontend: http://localhost:${API2MCP_PORT_FRONTEND}${NC}"
    else
        echo -e "${RED}✗ Frontend service failed to start, check logs: ${FRONTEND_LOG}${NC}"
        exit 1
    fi
    
    # Start backend (foreground)
    start_backend
}

# Main logic
case "${1:-start}" in
    start)
        check_uv
        init_python_env
        init_frontend_deps
        init_database
        start_all_foreground_services
        ;;
    start-bg)
        check_uv
        init_python_env
        init_frontend_deps
        init_database
        start_backend_bg
        start_frontend
        if [ "${2}" = "--watchdog" ]; then
            start_watchdog
        fi
        echo ""
        echo -e "${GREEN}========================================${NC}"
        echo -e "${GREEN}  API2MCP Services Started!${NC}"
        echo -e "${GREEN}  Frontend: http://localhost:${API2MCP_PORT_FRONTEND}${NC}"
        echo -e "${GREEN}  API Docs:  http://localhost:${API2MCP_PORT_BACKEND}/apidocs${NC}"
        echo -e "${GREEN}========================================${NC}"
        ;;
    --watchdog)
        run_watchdog
        ;;
    stop)
        stop_services
        ;;
    restart)
        stop_services
        sleep 2
        check_uv
        init_python_env
        init_frontend_deps
        init_database
        start_all_foreground_services
        ;;
    restart-bg)
        stop_services
        sleep 2
        check_uv
        init_python_env
        init_frontend_deps
        init_database
        start_backend_bg
        start_frontend
        if [ "${2}" = "--watchdog" ]; then
            start_watchdog
        fi
        echo -e "${GREEN}✓ Services restarted${NC}"
        ;;
    setup)
        echo -e "${BLUE}==> Installing dependencies...${NC}"
        check_uv
        init_python_env
        init_frontend_deps
        echo -e "${GREEN}✓ Dependencies installed${NC}"
        ;;
    init)
        check_uv
        init_python_env
        init_database
        ;;
    status)
        status
        ;;
    logs)
        logs "${2:-backend}"
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        show_help
        exit 1
        ;;
esac