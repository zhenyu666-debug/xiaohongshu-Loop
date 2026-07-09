# Rollback xhs-saas deployment
# Usage: .\scripts\rollback.ps1 [component]
#   component: backend|frontend|worker|all (default: all)

param(
    [string]$Component = "all"
)

$ErrorActionPreference = "Stop"
$Namespace = "xhs-saas"

Write-Host "==> Rolling back xhs-saas ($Component)" -ForegroundColor Cyan

if ($Component -eq "backend" -or $Component -eq "all") {
    Write-Host "Rolling back backend..." -ForegroundColor Yellow
    kubectl -n $Namespace rollout undo deployment/xhs-backend
    kubectl -n $Namespace rollout status deployment/xhs-backend --timeout=5m
}

if ($Component -eq "frontend" -or $Component -eq "all") {
    Write-Host "Rolling back frontend..." -ForegroundColor Yellow
    kubectl -n $Namespace rollout undo deployment/xhs-frontend
    kubectl -n $Namespace rollout status deployment/xhs-frontend --timeout=5m
}

if ($Component -eq "worker" -or $Component -eq "all") {
    Write-Host "Rolling back workers..." -ForegroundColor Yellow
    kubectl -n $Namespace rollout undo deployment/xhs-worker
    kubectl -n $Namespace rollout undo deployment/xhs-celery-worker
    kubectl -n $Namespace rollout status deployment/xhs-worker --timeout=5m
    kubectl -n $Namespace rollout status deployment/xhs-celery-worker --timeout=5m
}

Write-Host "==> Rollback complete" -ForegroundColor Green
kubectl -n $Namespace get pods
