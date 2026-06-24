# ============================================
# API2MCP Application Container Image
# Frontend + Backend Only (Database is external)
# Database must be provided separately (PostgreSQL)
#
# Build Context: Project Root Directory
# Build Command: docker build -f docker/docker-build/Dockerfile -t api2mcp:v1.0.0 .
# ============================================

# ------------------------------
# Stage 1: Frontend Builder
# ------------------------------
FROM node:20-alpine AS frontend-builder

WORKDIR /app

# Copy and build frontend
COPY frontend/ ./frontend/
RUN cd frontend && npm ci && npm run build

# ------------------------------
# Stage 2: Backend Builder
# ------------------------------
FROM python:3.12-slim AS backend-builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Copy and build backend
COPY backend/ ./backend/
RUN cd backend && /root/.local/bin/uv sync --no-dev

# ------------------------------
# Stage 3: Runtime
# ------------------------------
FROM python:3.12-slim AS runtime

WORKDIR /app

# Install runtime system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy uv from builder
COPY --from=backend-builder /root/.local/bin/uv /usr/local/bin/

# Copy backend
COPY --from=backend-builder /app/backend /app/backend

# Copy frontend build output
COPY --from=frontend-builder /app/frontend/dist /app/backend/frontend/dist

# Copy entrypoint and init script
COPY init_db.py /app/init_db.py
COPY docker/docker-build/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Set environment variables
ENV PYTHONPATH=/app/backend/src
ENV PATH="/app/backend/.venv/bin:$PATH"
# Port configurations are read from .env file at runtime, not hardcoded here

# Expose default ports (can be overridden at runtime)
EXPOSE 34075
EXPOSE 34085

# Health check (uses BACKEND_PORT environment variable)
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:${API2MCP_PORT_BACKEND:-34085}/health || exit 1

# Entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]
