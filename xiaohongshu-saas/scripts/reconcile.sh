#!/usr/bin/env bash
# Continuous health check and auto-recovery
# Runs every 5 minutes (configurable) and reconciles state

set -euo pipefail

NAMESPACE=${NAMESPACE:-"xhs-saas"}
LOG_FILE=${LOG_FILE:-"/var/log/xhs-saas-reconciler.log"}
CHECK_INTERVAL=${CHECK_INTERVAL:-300}

log() {
  local ts=$(date -Iseconds)
  echo "[$ts] $*" | tee -a "$LOG_FILE"
}

reconcile_pods() {
  log "==> Checking pod health"

  # Restart pods in CrashLoopBackOff
  local crashing=$(kubectl -n $NAMESPACE get pods -o json | \
    jq -r '.items[] | select(.status.containerStatuses[]?.state.waiting.reason == "CrashLoopBackOff") | .metadata.name')

  for pod in $crashing; do
    log "Restarting CrashLoopBackOff pod: $pod"
    kubectl -n $NAMESPACE delete pod "$pod" --grace-period=0 --force
  done
}

reconcile_pvc() {
  log "==> Checking PVC status"
  local pending=$(kubectl -n $NAMESPACE get pvc -o json | \
    jq -r '.items[] | select(.status.phase == "Pending") | .metadata.name')

  if [[ -n "$pending" ]]; then
    log "WARNING: Pending PVCs: $pending"
  fi
}

reconcile_jobs() {
  log "==> Checking failed CronJobs"
  local failed=$(kubectl -n $NAMESPACE get pods -l job-name -o json | \
    jq -r '.items[] | select(.status.phase == "Failed") | .metadata.name')

  for pod in $failed; do
    log "Cleaning failed job pod: $pod"
    kubectl -n $NAMESPACE delete pod "$pod" --grace-period=0 --force
  done
}

check_api() {
  log "==> Checking API health"
  local url="http://xhs-backend.${NAMESPACE}.svc.cluster.local:8000/health"
  if ! curl -fsS --max-time 10 "$url" >/dev/null 2>&1; then
    log "ERROR: API health check failed at $url"
    # Could trigger alert here
  else
    log "API is healthy"
  fi
}

main() {
  log "==> Reconciler started (interval=${CHECK_INTERVAL}s)"

  while true; do
    reconcile_pods
    reconcile_pvc
    reconcile_jobs
    check_api

    log "Sleeping ${CHECK_INTERVAL}s..."
    sleep "$CHECK_INTERVAL"
  done
}

main
