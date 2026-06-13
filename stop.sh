#!/bin/bash
#
# API2MCP Subsystem Stop Script
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

# Load environment variables
if [ -f "${SCRIPT_DIR}/.env" ]; then
    source "${SCRIPT_DIR}/.env"
fi

# Default port configuration
API2MCP_PORT_FRONTEND="${API2MCP_PORT_FRONTEND:-34075}"
API2MCP_PORT_BACKEND="${API2MCP_PORT_BACKEND:-34085}"

# PID files
PID_DIR="${SCRIPT_DIR}/pids"
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

# Stop services
stop_services() {
    echo -e "${BLUE}==> Stopping API2MCP services...${NC}"

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

    # Clean up backend port
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

    # Clean up frontend port
    if ! check_port ${API2MCP_PORT_FRONTEND}; then
        kill_port ${API2MCP_PORT_FRONTEND}
    fi

    echo -e "${GREEN}✓ All API2MCP services have been stopped${NC}"
}

# Execute stop
stop_services
