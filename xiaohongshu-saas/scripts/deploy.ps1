# Deploy xhs-saas to Kubernetes
# Usage: .\scripts\deploy.ps1 [env] [version]
#   env: dev|prod (default: dev)
#   version: image tag (default: latest)

param(
    [string]$Env = "dev",
    [string]$Version = "latest",
    [string]$Registry = "xhs-saas"
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir
$KustomizeDir = Join-Path $RootDir "k8s\overlays\$Env"

if (-not (Test-Path $KustomizeDir)) {
    Write-Error "Kustomize directory not found: $KustomizeDir"
    exit 1
}

Write-Host "==> Deploying xhs-saas to $Env with version $Version" -ForegroundColor Cyan

# Verify kubectl context
$context = kubectl config current-context
Write-Host "Current context: $context" -ForegroundColor Yellow
$confirm = Read-Host "Continue? (y/N)"
if ($confirm -ne "y") {
    Write-Host "Aborted." -ForegroundColor Red
    exit 0
}

# Create namespace
kubectl apply -f (Join-Path $RootDir "k8s\base\00-namespace.yaml")

# Apply manifests
Write-Host "==> Applying manifests" -ForegroundColor Cyan
Set-Location $KustomizeDir
$kustomizeOutput = kustomize build $KustomizeDir | kubectl apply -f -

Write-Host $kustomizeOutput

# Wait for rollout
Write-Host "==> Waiting for rollout" -ForegroundColor Cyan
kubectl -n xhs-saas rollout status deployment/xhs-backend --timeout=5m
kubectl -n xhs-saas rollout status deployment/xhs-frontend --timeout=5m

Write-Host ""
Write-Host "==> Deployment complete" -ForegroundColor Green
Write-Host ""
kubectl -n xhs-saas get pods,svc,ing
