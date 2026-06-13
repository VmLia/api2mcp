#!/bin/bash
#
# API2MCP Application Entrypoint
# Frontend + Backend Only (Database is external)
# Database connection must be provided via environment variables
#

set -e

echo "============================================"
echo "  API2MCP Application Container"
echo "  Frontend + Backend Only (Database External)"
echo "============================================"

# Configuration
BACKEND_PORT="${API2MCP_PORT_BACKEND:-34085}"
FRONTEND_PORT="${API2MCP_PORT_FRONTEND:-34075}"
BACKEND_DIR="/app/backend"
FRONTEND_DIR="/app/backend/frontend"

# Build uvicorn command with access log control
if [ "${UVICORN_ACCESS_LOG}" = "true" ] || [ "${UVICORN_ACCESS_LOG}" = "1" ]; then
    UVICORN_ACCESS_LOG_FLAG="--access-log"
else
    UVICORN_ACCESS_LOG_FLAG="--no-access-log"
fi

# Initialize database
init_database() {
    echo "Initializing database..."
    
    # Check if database connection is configured
    if [ -z "${DB_HOST}" ]; then
        echo "WARNING: DB_HOST is not set. Skipping database initialization."
        echo "Please provide database connection via environment variables:"
        echo "  DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME"
        return 0
    fi
    
    cd /app
    python init_db.py
}

# Start backend service
start_backend() {
    echo "Starting backend service on port ${BACKEND_PORT}..."
    cd ${BACKEND_DIR}
    uvicorn api2mcp.main:app --host 0.0.0.0 --port ${BACKEND_PORT} --log-level info ${UVICORN_ACCESS_LOG_FLAG} &
    BACKEND_PID=$!
    echo "Backend started (PID: ${BACKEND_PID})"
}

# Start frontend service
start_frontend() {
    echo "Starting frontend service on port ${FRONTEND_PORT}..."
    cd ${FRONTEND_DIR}

    # Check if dist folder exists (production build)
    if [ -d "dist" ] && [ -f "dist/index.html" ]; then
        # Production mode: serve static files
        echo "Frontend: Production mode detected"
        cd dist
        python -m http.server ${FRONTEND_PORT} --bind 0.0.0.0 &
        FRONTEND_PID=$!
    else
        # Fallback: development mode
        echo "Frontend: Development mode (dist not found)"
        python -m http.server ${FRONTEND_PORT} --bind 0.0.0.0 &
        FRONTEND_PID=$!
    fi
    echo "Frontend started (PID: ${FRONTEND_PID})"
}

# Main function
main() {
    # Initialize database (if configured)
    init_database

    # Start backend (background)
    start_backend

    # Wait for backend to start
    sleep 3

    # Start frontend (background)
    start_frontend

    # Display status
    echo ""
    echo "============================================"
    echo "  API2MCP Services Started!"
    echo "  Frontend: http://localhost:${FRONTEND_PORT}"
    echo "  Backend:  http://localhost:${BACKEND_PORT}"
    echo "  API Docs: http://localhost:${BACKEND_PORT}/apidocs"
    echo ""
    echo "  Database Configuration:"
    echo "    Host: ${DB_HOST:-Not configured}"
    echo "    Port: ${DB_PORT:-5432}"
    echo "    Name: ${DB_NAME:-api2mcp}"
    echo "============================================"
    echo ""

    # Trap signals for graceful shutdown
    trap "echo 'Shutting down...'; kill ${BACKEND_PID} 2>/dev/null; kill ${FRONTEND_PID} 2>/dev/null; exit 0" SIGTERM SIGINT

    # Keep container running
    wait
}

# Execute
main "$@"
