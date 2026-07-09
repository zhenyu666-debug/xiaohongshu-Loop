#!/usr/bin/env bash
# Deploy xhs-saas to Kubernetes
# Usage: ./scripts/deploy.sh [env] [version]
#   env: dev|prod (default: dev)
#   version: image tag (default: latest)
#
# Requires: kubectl configured, kustomize installed, GHCR login for prod

set -euo pipefail

ENV=${1:-"dev"}
VERSION=${2:-"latest"}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
KUSTOMIZE_DIR="${ROOT_DIR}/k8s/overlays/${ENV}"

if [[ ! -d "$KUSTOMIZE_DIR" ]]; then
  echo "ERROR: kustomize directory not found: $KUSTOMIZE_DIR"
  exit 1
fi

echo "==> Deploying xhs-saas to ${ENV} with version ${VERSION}"

# 1. Verify kubectl context
CONTEXT=$(kubectl config current-context)
echo "Current context: $CONTEXT"
read -p "Continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Aborted."
  exit 0
fi

# 2. Create namespace if not exists
kubectl apply -f "${ROOT_DIR}/k8s/base/00-namespace.yaml"

# 3. Update image tags via kustomize
echo "==> Updating image tags to ${VERSION}"
cd "$KUSTOMIZE_DIR"
kustomize edit set image \
  "xhs-saas/backend=${REGISTRY:-xhs-saas}/backend:${VERSION}" \
  "xhs-saas/frontend=${REGISTRY:-xhs-saas}/frontend:${VERSION}" 2>/dev/null || true

# 4. Apply manifests
echo "==> Applying manifests"
kustomize build "$KUSTOMIZE_DIR" | kubectl apply -f -

# 5. Wait for rollout
echo "==> Waiting for rollout"
kubectl -n xhs-saas rollout status deployment/xhs-backend --timeout=5m
kubectl -n xhs-saas rollout status deployment/xhs-frontend --timeout=5m

echo ""
echo "==> Deployment complete"
echo ""
echo "Status:"
kubectl -n xhs-saas get pods,svc,ing
