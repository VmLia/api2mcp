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
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${SCRIPT_DIR}/backend"
FRONTEND_DIR="${SCRIPT_DIR}/frontend"
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

# PID files
BACKEND_PID="${PID_DIR}/backend.pid"
FRONTEND_PID="${PID_DIR}/frontend.pid"

# Check if port is occupied (cross-platform compatible)
check_port() {
    local port=$1
    # Try ss first (available on most Linux systems)
    if command -v ss &> /dev/null; then
        if ss -tlnp | grep -q ":${port} "; then
            return 1  # Port is occupied
        fi
    elif command -v lsof &> /dev/null; then
        # Fallback to lsof (macOS)
        if lsof -i ":${port}" > /dev/null 2>&1; then
            return 1  # Port is occupied
        fi
    elif command -v netstat &> /dev/null; then
        # Fallback to netstat (older systems)
        if netstat -tlnp 2>/dev/null | grep -q ":${port} " || netstat -an 2>/dev/null | grep -q ".${port} "; then
            return 1  # Port is occupied
        fi
    fi
    return 0  # Port is available
}

# Kill process occupying port (cross-platform compatible)
kill_port() {
    local port=$1
    echo -e "${YELLOW}Cleaning up process on port ${port}...${NC}"
    
    # Try ss first (available on most Linux systems)
    if command -v ss &> /dev/null; then
        local pids=$(ss -tlnp | grep ":${port} " | awk '{print $7}' | sed 's/,.*//; s/.*=//' | grep -v '^$')
        if [ -n "${pids}" ]; then
            kill -9 ${pids} 2>/dev/null || true
        fi
    elif command -v lsof &> /dev/null; then
        # Fallback to lsof (macOS)
        lsof -ti ":${port}" | xargs kill -9 2>/dev/null || true
    elif command -v fuser &> /dev/null; then
        # Fallback to fuser (some Linux systems)
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

# Check if uv is installed
check_uv() {
    check_command uv
    echo -e "${GREEN}✓ uv installed${NC}"
}

# Initialize Python environment (prefer uv, fallback to pip)
init_python_env() {
    echo -e "${BLUE}==> Initializing Python environment...${NC}"

    cd "${BACKEND_DIR}"

    if command -v uv &> /dev/null; then
        echo -e "${GREEN}✓ uv detected, using uv for environment management${NC}"

        # Check if uv environment exists
        if [ -d ".venv" ]; then
            echo -e "${GREEN}✓ Python virtual environment already exists${NC}"
        else
            echo -e "${YELLOW}Creating Python virtual environment...${NC}"
            uv venv .venv
        fi

        # Install/update dependencies
        echo -e "${YELLOW}Installing Python dependencies...${NC}"
        uv sync
    else
        echo -e "${YELLOW}uv not detected, using pip to install dependencies...${NC}"
        echo -e "${YELLOW}Tip: Install uv for better dependency management: curl -LsSf https://astral.sh/uv/install.sh | sh${NC}"

        # Check if virtual environment exists
        if [ -d ".venv" ]; then
            echo -e "${GREEN}✓ Python virtual environment already exists${NC}"
        else
            echo -e "${YELLOW}Creating Python virtual environment...${NC}"
            python3 -m venv .venv || python -m venv .venv
        fi

        # Activate virtual environment and install dependencies
        source .venv/bin/activate
        echo -e "${YELLOW}Installing Python dependencies...${NC}"
        pip install -r requirements.txt
    fi

    echo -e "${GREEN}✓ Python environment ready${NC}"
}

# Database table initialization is now handled by main.py lifespan
# init_database_tables() {
#     echo -e "${BLUE}==> Initializing database tables...${NC}"
#     cd "${BACKEND_DIR}"
#     source .venv/bin/activate
#     echo -e "${YELLOW}Running database table initialization (API2MCP_DB_DEL=${API2MCP_DB_DEL:-false})...${NC}"
#     if python "${SCRIPT_DIR}/init/init_db.py"; then
#         echo -e "${GREEN}✓ Database table initialization completed${NC}"
#     else
#         echo -e "${RED}✗ Database table initialization failed${NC}"
#         exit 1
#     fi
# }

# Start backend service (foreground mode)
start_backend() {
    echo -e "${BLUE}==> Starting backend service...${NC}"
    
    cd "${BACKEND_DIR}"
    source .venv/bin/activate
    
    # Check port and clean up if needed
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
    
    # Run in foreground, output logs directly (--reload enables auto-restart on code changes)
    uvicorn api2mcp.main:app --host 0.0.0.0 --port ${API2MCP_PORT_BACKEND} --log-level info --reload ${UVICORN_ACCESS_LOG_FLAG}
}

# Start backend in background mode
start_backend_bg() {
    echo -e "${BLUE}==> Starting backend service...${NC}"
    
    cd "${BACKEND_DIR}"
    source .venv/bin/activate
    
    # Check port and clean up if needed
    if ! check_port ${API2MCP_PORT_BACKEND}; then
        echo -e "${YELLOW}Warning: Port ${API2MCP_PORT_BACKEND} is occupied, cleaning up...${NC}"
        kill_port ${API2MCP_PORT_BACKEND}
    fi
    
    # Start service (--reload enables auto-restart on code changes)
    echo -e "${YELLOW}Starting backend service (port: ${API2MCP_PORT_BACKEND})...${NC}"
    nohup uvicorn api2mcp.main:app --host 0.0.0.0 --port ${API2MCP_PORT_BACKEND} --log-level info --reload ${UVICORN_ACCESS_LOG_FLAG} > "${BACKEND_LOG}" 2>&1 &
    echo $! > "${BACKEND_PID}"
    
    # Wait for service to start
    sleep 3
    
    # Check if service started successfully
    if curl -s http://localhost:${API2MCP_PORT_BACKEND}/apidocs > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Backend service started successfully (PID: $(cat ${BACKEND_PID}))${NC}"
        echo -e "${GREEN}  API Docs: http://localhost:${API2MCP_PORT_BACKEND}/apidocs${NC}"
    else
        echo -e "${RED}✗ Backend service failed to start, check logs: ${BACKEND_LOG}${NC}"
        return 1
    fi
}

# Start frontend service
start_frontend() {
    echo -e "${BLUE}==> Starting frontend service...${NC}"
    
    # Check if npm is installed
    check_command npm
    
    cd "${FRONTEND_DIR}"
    
    # Check node_modules
    if [ ! -d "node_modules" ]; then
        echo -e "${YELLOW}Installing frontend dependencies...${NC}"
        npm install
    fi
    
    # Check port and clean up if needed
    if ! check_port ${API2MCP_PORT_FRONTEND}; then
        echo -e "${YELLOW}Warning: Port ${API2MCP_PORT_FRONTEND} is occupied, cleaning up...${NC}"
        kill_port ${API2MCP_PORT_FRONTEND}
    fi
    
    # Start service
    echo -e "${YELLOW}Starting frontend service (port: ${API2MCP_PORT_FRONTEND})...${NC}"
    nohup npm run dev > "${FRONTEND_LOG}" 2>&1 &
    echo $! > "${FRONTEND_PID}"
    
    # Wait for service to start
    sleep 5
    
    # Check if service started successfully (port occupied means service started)
    if ! check_port ${API2MCP_PORT_FRONTEND}; then
        echo -e "${GREEN}✓ Frontend service started successfully (PID: $(cat ${FRONTEND_PID}))${NC}"
        echo -e "${GREEN}  Frontend: http://localhost:${API2MCP_PORT_FRONTEND}${NC}"
    else
        echo -e "${RED}✗ Frontend service failed to start, check logs: ${FRONTEND_LOG}${NC}"
        return 1
    fi
}

# Stop services
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
    
    # Clean up port
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
    
    # Clean up port
    if ! check_port ${API2MCP_PORT_FRONTEND}; then
        kill_port ${API2MCP_PORT_FRONTEND}
    fi
    
    # Stop watchdog
    stop_watchdog
    
    echo -e "${GREEN}✓ All services stopped${NC}"
}

# Show status
status() {
    echo -e "${BLUE}==> Service Status${NC}"
    
    # Backend status
    if [ -f "${BACKEND_PID}" ]; then
        local backend_pid=$(cat "${BACKEND_PID}")
        if kill -0 ${backend_pid} 2>/dev/null; then
            echo -e "${GREEN}✓ Backend service running (PID: ${backend_pid}, Port: ${API2MCP_PORT_BACKEND})${NC}"
        else
            # PID file exists but process died - check if port is still occupied
            if ! check_port ${API2MCP_PORT_BACKEND}; then
                # Port is occupied but PID doesn't match - watchdog likely restarted
                local actual_pid=$(lsof -ti ":${API2MCP_PORT_BACKEND}" 2>/dev/null)
                if [ -n "${actual_pid}" ]; then
                    echo -e "${YELLOW}⚠ Backend service running (PID: ${actual_pid}, Port: ${API2MCP_PORT_BACKEND}, PID file stale: ${backend_pid})${NC}"
                else
                    echo -e "${RED}✗ Backend service not running (PID file exists but process exited)${NC}"
                fi
            else
                echo -e "${RED}✗ Backend service not running (PID file exists but process exited)${NC}"
            fi
        fi
    else
        if ! check_port ${API2MCP_PORT_BACKEND}; then
            local actual_pid=$(lsof -ti ":${API2MCP_PORT_BACKEND}" 2>/dev/null)
            echo -e "${YELLOW}⚠ Backend service running (PID: ${actual_pid:-unknown}, Port: ${API2MCP_PORT_BACKEND})${NC}"
        else
            echo -e "${RED}✗ Backend service not running${NC}"
        fi
    fi
    
    # Frontend status
    if [ -f "${FRONTEND_PID}" ]; then
        local frontend_pid=$(cat "${FRONTEND_PID}")
        if kill -0 ${frontend_pid} 2>/dev/null; then
            echo -e "${GREEN}✓ Frontend service running (PID: ${frontend_pid}, Port: ${API2MCP_PORT_FRONTEND})${NC}"
        else
            # PID file exists but process died - check if port is still occupied
            if ! check_port ${API2MCP_PORT_FRONTEND}; then
                local actual_pid=$(lsof -ti ":${API2MCP_PORT_FRONTEND}" 2>/dev/null)
                if [ -n "${actual_pid}" ]; then
                    echo -e "${YELLOW}⚠ Frontend service running (PID: ${actual_pid}, Port: ${API2MCP_PORT_FRONTEND}, PID file stale: ${frontend_pid})${NC}"
                else
                    echo -e "${RED}✗ Frontend service not running (PID file exists but process exited)${NC}"
                fi
            else
                echo -e "${RED}✗ Frontend service not running (PID file exists but process exited)${NC}"
            fi
        fi
    else
        if ! check_port ${API2MCP_PORT_FRONTEND}; then
            local actual_pid=$(lsof -ti ":${API2MCP_PORT_FRONTEND}" 2>/dev/null)
            echo -e "${YELLOW}⚠ Frontend service running (PID: ${actual_pid:-unknown}, Port: ${API2MCP_PORT_FRONTEND})${NC}"
        else
            echo -e "${RED}✗ Frontend service not running${NC}"
        fi
    fi
    
    # Watchdog status
    if [ -f "${WATCHDOG_PID}" ]; then
        local watchdog_pid=$(cat "${WATCHDOG_PID}")
        if kill -0 ${watchdog_pid} 2>/dev/null; then
            echo -e "${GREEN}✓ Watchdog running (PID: ${watchdog_pid})${NC}"
        else
            echo -e "${RED}✗ Watchdog not running (PID file exists but process exited)${NC}"
        fi
    else
        echo -e "${YELLOW}⚠ Watchdog not running${NC}"
    fi
}

# View logs
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
        *)
            echo -e "${YELLOW}Usage: $0 logs [backend|frontend]${NC}"
            ;;
    esac
}

# Watchdog PID file
WATCHDOG_PID="${PID_DIR}/watchdog.pid"

# Start watchdog: re-exec this script in background watchdog mode
start_watchdog() {
    # Stop existing watchdog if running
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

# Stop watchdog
stop_watchdog() {
    if [ -f "${WATCHDOG_PID}" ]; then
        local watchdog_pid=$(cat "${WATCHDOG_PID}")
        if kill -0 ${watchdog_pid} 2>/dev/null; then
            kill ${watchdog_pid} 2>/dev/null
        fi
        rm -f "${WATCHDOG_PID}"
    fi
}

# Watchdog mode: monitor and auto-restart crashed services
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

# Show help
show_help() {
    echo -e "${BLUE}API2MCP Startup Script${NC}"
    echo ""
    echo -e "${GREEN}Usage:${NC}"
    echo "  $0              Start backend and frontend (backend in foreground)"
    echo "  $0 start        Start backend and frontend (backend in foreground)"
    echo "  $0 start-bg     Start all services (background mode)"
    echo "  $0 start-bg --watchdog  Start all services with auto-restart watchdog"
    echo "  $0 stop         Stop all services"
    echo "  $0 restart      Restart services (backend in foreground)"
    echo "  $0 restart-bg   Restart all services (background mode)"
    echo "  $0 setup        Install dependencies only (first use or after updates)"
    echo "  $0 status       Show service status"
    echo "  $0 logs         View backend logs"
    echo "  $0 logs [backend|frontend]  View specified service logs"
    echo "  $0 help         Show this help message"
    echo ""
    echo -e "${GREEN}Mode Description:${NC}"
    echo "  Default/start (Foreground)  - Frontend in background, backend in foreground with real-time logs"
    echo "  start-bg (Background)       - All services run in background, suitable for production"
    echo ""
    echo -e "${GREEN}Environment Variables (.env):${NC}"
    echo "  API2MCP_PORT_FRONTEND  Frontend port (default: 34075)"
    echo "  API2MCP_PORT_BACKEND   Backend port (default: 34085)"
    echo "  API2MCP_DB_DEL         Drop existing tables on startup (true/false, default: false)"
    echo "  DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME  Database connection"
    echo "  REDIS_HOST/REDIS_PORT/REDIS_PASSWORD          Redis connection"
    echo "  DATABASE_URL           Database connection URL (overrides above)"
    echo "  VITE_API_URL           Frontend API proxy URL (empty uses current domain)"
    echo ""
    echo -e "${GREEN}Supported Platforms:${NC}"
    echo "  - macOS"
    echo "  - CentOS/RHEL"
    echo "  - Ubuntu/Debian"
    echo ""
    echo -e "${GREEN}Examples:${NC}"
    echo "  $0                         # Start frontend and backend with backend in foreground"
    echo "  $0 start-bg                # Start all services in background"
    echo "  $0 setup                   # Install dependencies only"
    echo "  API2MCP_PORT_BACKEND=8080 $0   # Use custom port"
}

# Start frontend in background and backend in foreground
start_all_foreground() {
    # Start frontend first (background)
    echo -e "${BLUE}==> Starting frontend service...${NC}"
    
    # Check if npm is installed
    check_command npm
    
    cd "${FRONTEND_DIR}"
    
    # Check node_modules
    if [ ! -d "node_modules" ]; then
        echo -e "${YELLOW}Installing frontend dependencies...${NC}"
        npm install
    fi
    
    # Check port and clean up if needed
    if ! check_port ${API2MCP_PORT_FRONTEND}; then
        echo -e "${YELLOW}Warning: Port ${API2MCP_PORT_FRONTEND} is occupied, cleaning up...${NC}"
        kill_port ${API2MCP_PORT_FRONTEND}
    fi
    
    # Start frontend service (background)
    echo -e "${YELLOW}Starting frontend service (port: ${API2MCP_PORT_FRONTEND})...${NC}"
    nohup npm run dev > "${FRONTEND_LOG}" 2>&1 &
    echo $! > "${FRONTEND_PID}"
    
    # Wait for frontend to start
    sleep 5
    
    # Check if frontend started successfully (port occupied means service started)
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
        start_all_foreground
        ;;
    start-bg)
        check_uv
        init_python_env
        start_backend_bg
        start_frontend
        # Start watchdog if --watchdog flag is passed
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
        # Internal: watchdog mode (called by start_watchdog)
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
        start_all_foreground
        ;;
    restart-bg)
        stop_services
        sleep 2
        check_uv
        init_python_env
        start_backend_bg
        start_frontend
        # Start watchdog if --watchdog flag is passed
        if [ "${2}" = "--watchdog" ]; then
            start_watchdog
        fi
        echo -e "${GREEN}✓ Services restarted${NC}"
        ;;
    setup)
        echo -e "${BLUE}==> Installing dependencies...${NC}"
        check_command npm
        init_python_env

        # Install frontend dependencies
        echo -e "${BLUE}==> Installing frontend dependencies...${NC}"
        cd "${FRONTEND_DIR}"
        if [ ! -d "node_modules" ]; then
            npm install
        else
            echo -e "${GREEN}✓ Frontend dependencies already installed${NC}"
        fi

        echo -e "${GREEN}========================================${NC}"
        echo -e "${GREEN}  Dependencies installed${NC}"
        echo -e "${GREEN}========================================${NC}"
        echo ""
        echo -e "${YELLOW}Next: Run $0 to start services${NC}"
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
