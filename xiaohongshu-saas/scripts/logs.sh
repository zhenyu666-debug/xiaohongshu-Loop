#!/usr/bin/env bash
# Tail logs from xhs-saas pods

set -euo pipefail

NAMESPACE=${NAMESPACE:-"xhs-saas"}
COMPONENT=${1:-"backend"}
TAIL_LINES=${2:-100}

case $COMPONENT in
  backend|api)
    LABEL="app=xhs-backend"
    ;;
  frontend|web)
    LABEL="app=xhs-frontend"
    ;;
  worker)
    LABEL="app=xhs-worker"
    ;;
  celery)
    LABEL="app=xhs-celery-worker"
    ;;
  beat)
    LABEL="app=xhs-celery-beat"
    ;;
  *)
    echo "Usage: $0 [backend|frontend|worker|celery|beat] [lines]"
    exit 1
    ;;
esac

PODS=$(kubectl -n $NAMESPACE get pods -l "$LABEL" -o jsonpath='{.items[*].metadata.name}')

if [[ -z "$PODS" ]]; then
  echo "No pods found for $LABEL"
  exit 1
fi

echo "==> Tailing logs for $LABEL ($PODS)"
kubectl -n $NAMESPACE logs -f --tail="$TAIL_LINES" --max-log-requests=10 $PODS
