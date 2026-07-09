# Build script for xhs-saas images
# Usage: ./scripts/build.sh [version]
# Example: ./scripts/build.sh v0.6.3

set -euo pipefail

VERSION=${1:-"latest"}
REGISTRY=${REGISTRY:-"ghcr.io/your-org"}
IMAGE_BACKEND=${REGISTRY}/xhs-saas-backend
IMAGE_FRONTEND=${REGISTRY}/xhs-saas-frontend

echo "==> Building backend image: ${IMAGE_BACKEND}:${VERSION}"
docker build \
  -f docker/Dockerfile.backend \
  -t ${IMAGE_BACKEND}:${VERSION} \
  -t ${IMAGE_BACKEND}:latest \
  .

echo "==> Building frontend image: ${IMAGE_FRONTEND}:${VERSION}"
docker build \
  -f docker/Dockerfile.frontend \
  -t ${IMAGE_FRONTEND}:${VERSION} \
  -t ${IMAGE_FRONTEND}:latest \
  .

echo "==> Build complete"
echo ""
echo "To push:"
echo "  docker push ${IMAGE_BACKEND}:${VERSION}"
echo "  docker push ${IMAGE_FRONTEND}:${VERSION}"
