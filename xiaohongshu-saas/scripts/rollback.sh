#!/usr/bin/env bash
# Rollback xhs-saas deployment
# Usage: ./scripts/rollback.sh [component]
#   component: backend|frontend|all (default: all)

set -euo pipefail

COMPONENT=${1:-"all"}

echo "==> Rolling back xhs-saas"

if [[ "$COMPONENT" == "backend" || "$COMPONENT" == "all" ]]; then
  echo "Rolling back backend..."
  kubectl -n xhs-saas rollout undo deployment/xhs-backend
  kubectl -n xhs-saas rollout status deployment/xhs-backend --timeout=5m
fi

if [[ "$COMPONENT" == "frontend" || "$COMPONENT" == "all" ]]; then
  echo "Rolling back frontend..."
  kubectl -n xhs-saas rollout undo deployment/xhs-frontend
  kubectl -n xhs-saas rollout status deployment/xhs-frontend --timeout=5m
fi

if [[ "$COMPONENT" == "worker" || "$COMPONENT" == "all" ]]; then
  echo "Rolling back workers..."
  kubectl -n xhs-saas rollout undo deployment/xhs-worker
  kubectl -n xhs-saas rollout undo deployment/xhs-celery-worker
  kubectl -n xhs-saas rollout status deployment/xhs-worker --timeout=5m
  kubectl -n xhs-saas rollout status deployment/xhs-celery-worker --timeout=5m
fi

echo "==> Rollback complete"
kubectl -n xhs-saas get pods
