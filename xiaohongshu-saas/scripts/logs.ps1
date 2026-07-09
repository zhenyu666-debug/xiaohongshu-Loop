# Tail logs from xhs-saas pods
# Usage: .\scripts\logs.ps1 [component] [lines]

param(
    [string]$Component = "backend",
    [int]$Lines = 100
)

$ErrorActionPreference = "Stop"
$Namespace = "xhs-saas"

switch ($Component) {
    { @("backend", "api") -contains $_ } { $Label = "app=xhs-backend" }
    { @("frontend", "web") -contains $_ } { $Label = "app=xhs-frontend" }
    "worker" { $Label = "app=xhs-worker" }
    "celery" { $Label = "app=xhs-celery-worker" }
    "beat" { $Label = "app=xhs-celery-beat" }
    default {
        Write-Host "Usage: .\logs.ps1 [backend|frontend|worker|celery|beat] [lines]" -ForegroundColor Red
        exit 1
    }
}

$Pods = kubectl -n $Namespace get pods -l $Label -o jsonpath='{.items[*].metadata.name}'

if (-not $Pods) {
    Write-Host "No pods found for $Label" -ForegroundColor Red
    exit 1
}

Write-Host "==> Tailing logs for $Label ($Pods)" -ForegroundColor Cyan
kubectl -n $Namespace logs -f --tail=$Lines --max-log-requests=10 $Pods.Split(" ")
