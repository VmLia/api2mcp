#!/bin/bash
#
# API2MCP Multi-Architecture Build Script
# 构建前后端合一的单一镜像
# 支持 amd64 (x86-64) 和 arm64 (Apple Silicon / AWS Graviton)
#
# Usage:
#   cd /path/to/api2mcp
#   ./docker/docker-build/build-multiarch.sh
#
# Environment Variables:
#   IMAGE_NAME  - 镜像名称 (default: api2mcp)
#   IMAGE_TAG   - 镜像标签 (default: latest)
#   REGISTRY    - 镜像仓库地址 (default: empty, local build)
#

set -e

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# 镜像名称
IMAGE_NAME="${IMAGE_NAME:-api2mcp}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
REGISTRY="${REGISTRY:-}"  # 设置为你自己的镜像仓库，如 docker.io/username/

# 完整镜像名
FULL_IMAGE="${REGISTRY}${IMAGE_NAME}:${IMAGE_TAG}"

# Dockerfile 路径
DOCKERFILE_PATH="${SCRIPT_DIR}/Dockerfile"

echo "============================================"
echo "  API2MCP All-in-One Multi-Arch Build"
echo "============================================"
echo "Project Root: ${PROJECT_ROOT}"
echo "Dockerfile:   ${DOCKERFILE_PATH}"
echo "Image:        ${FULL_IMAGE}"
echo "Platforms:    linux/amd64, linux/arm64"
echo ""

# 切换到项目根目录
cd "${PROJECT_ROOT}"

# 清理旧的 builder
echo "[1/4] Setting up docker buildx..."
docker buildx rm api2mcp-builder 2>/dev/null || true
docker buildx create --name api2mcp-builder --driver docker-container --bootstrap
docker buildx use api2mcp-builder

# 检查 builder 状态
docker buildx inspect --bootstrap

# 构建镜像
echo ""
echo "[2/4] Building image (linux/amd64, linux/arm64)..."
docker buildx build \
    --platform linux/amd64,linux/arm64 \
    -f "${DOCKERFILE_PATH}" \
    -t "${FULL_IMAGE}" \
    --push \
    .

# 输出结果
echo ""
echo "[3/4] Build completed!"
echo "============================================"
echo "  Image Manifest:"
echo "============================================"
docker buildx imagetools inspect "${FULL_IMAGE}"

# 清理 builder
echo ""
echo "[4/4] Cleaning up builder..."
docker buildx rm api2mcp-builder 2>/dev/null || true

echo ""
echo "============================================"
echo "  Deployment Commands:"
echo "============================================"
echo ""
echo "  # AMD64 (x86-64) - Intel/AMD 服务器"
echo "  docker pull --platform linux/amd64 ${FULL_IMAGE}"
echo ""
echo "  # ARM64 - Apple Silicon / AWS Graviton / 树莓派"
echo "  docker pull --platform linux/arm64 ${FULL_IMAGE}"
echo ""
echo "  # 自动选择架构（生产环境推荐）"
echo "  docker run -d -p 34075:34075 -p 34085:34085 ${FULL_IMAGE}"
echo ""
echo "  # Docker Compose (启动所有服务)"
echo "  cd docker/docker-compose-api2mcp"
echo "  docker compose -f docker-compose-all.yaml up -d"
echo ""
echo "  # Docker Compose (只启动应用)"
echo "  cd docker/docker-compose-api2mcp"
echo "  docker compose -f docker-compose-api2mcp.yaml up -d"
echo ""
echo "============================================"
