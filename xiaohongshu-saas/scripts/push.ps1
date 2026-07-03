# Push all updates under .\xiaohongshu-saas to
# https://github.com/zhenyu666-debug/xiaohongshu-Loop.git
#
# Prereqs:
#   - Install Git for Windows: https://git-scm.com/download/win
#   - Have push access to the repo (HTTPS user/pass or SSH key)
#
# Usage (from repo root, i.e. c:\Users\Hasee\.qclaw\workspace\get_jobs):
#   powershell -ExecutionPolicy Bypass -File .\xiaohongshu-saas\scripts\push.ps1
#   powershell -ExecutionPolicy Bypass -File .\xiaohongshu-saas\scripts\push.ps1 -Message "feat: ..."
#   powershell -ExecutionPolicy Bypass -File .\xiaohongshu-saas\scripts\push.ps1 -RemoteUrl "git@github.com:zhenyu666-debug/xiaohongshu-Loop.git"

[CmdletBinding()]
param(
    [string]$Message = "chore: update xhs-saas middleware",
    [string]$RemoteUrl = "https://github.com/zhenyu666-debug/xiaohongshu-Loop.git",
    [string]$Branch = "main"
)

$ErrorActionPreference = "Stop"

# Locate git.exe (common Windows install paths)
$gitCandidates = @(
    "$env:LOCALAPPDATA\Programs\Git\bin\git.exe",
    "$env:ProgramFiles\Git\bin\git.exe",
    "${env:ProgramFiles(x86)}\Git\bin\git.exe",
    "C:\Program Files\Git\bin\git.exe",
    "C:\Program Files (x86)\Git\bin\git.exe"
)
$git = $null
foreach ($p in $gitCandidates) {
    if ($p -and (Test-Path $p)) { $git = $p; break }
}
if (-not $git) {
    $git = (Get-Command git -ErrorAction SilentlyContinue)?.Source
}
if (-not $git) {
    Write-Host "ERROR: git not found. Install Git for Windows first." -ForegroundColor Red
    Write-Host "Download: https://git-scm.com/download/win" -ForegroundColor Yellow
    exit 1
}

$repoRoot = Join-Path $PSScriptRoot ".."
Set-Location $repoRoot
Write-Host "Working dir: $repoRoot" -ForegroundColor Cyan

# Init repo if needed
if (-not (Test-Path ".git")) {
    Write-Host "Initializing git repo..." -ForegroundColor Yellow
    & $git init
    & $git checkout -B $Branch
}

& $git remote remove origin 2>$null
& $git remote add origin $RemoteUrl

& $git add -A
$status = & $git status --porcelain
if (-not $status) {
    Write-Host "Nothing to commit." -ForegroundColor Yellow
} else {
    & $git commit -m $Message
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Commit failed." -ForegroundColor Red
        exit 1
    }
}

Write-Host "Pushing to $RemoteUrl ($Branch) ..." -ForegroundColor Cyan
& $git push -u origin $Branch
if ($LASTEXITCODE -ne 0) {
    Write-Host "Push failed. If this is the first push, you may need:" -ForegroundColor Yellow
    Write-Host "   git push -u origin $Branch --force" -ForegroundColor Yellow
    Write-Host "Or set credentials: git config --global user.name / user.email" -ForegroundColor Yellow
    exit 1
}

Write-Host "Done." -ForegroundColor Green