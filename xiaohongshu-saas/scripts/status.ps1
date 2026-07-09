# Show xhs-saas deployment status

param()

$ErrorActionPreference = "Stop"
$Namespace = "xhs-saas"

Write-Host "==> Namespace: $Namespace" -ForegroundColor Cyan
Write-Host ""

Write-Host "==> Pods" -ForegroundColor Yellow
kubectl -n $Namespace get pods -o wide
Write-Host ""

Write-Host "==> Services" -ForegroundColor Yellow
kubectl -n $Namespace get svc
Write-Host ""

Write-Host "==> Ingress" -ForegroundColor Yellow
kubectl -n $Namespace get ing
Write-Host ""

Write-Host "==> HPA" -ForegroundColor Yellow
kubectl -n $Namespace get hpa
Write-Host ""

Write-Host "==> PDB" -ForegroundColor Yellow
kubectl -n $Namespace get pdb
Write-Host ""

Write-Host "==> PVC" -ForegroundColor Yellow
kubectl -n $Namespace get pvc
Write-Host ""

Write-Host "==> CronJobs" -ForegroundColor Yellow
kubectl -n $Namespace get cronjobs
Write-Host ""

Write-Host "==> Recent events" -ForegroundColor Yellow
kubectl -n $Namespace get events --sort-by='.lastTimestamp' | Select-Object -Last 20
