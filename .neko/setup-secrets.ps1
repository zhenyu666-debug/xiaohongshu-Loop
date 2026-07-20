# Re-rolls the admin and friend passwords, writes them to
# .neko/passwords/{admin,user}_password (one password per line).
# Then re-starts the neko container so the env files are re-read.

$ErrorActionPreference = 'Stop'

$here   = Split-Path -Parent $MyInvocation.MyCommand.Path
$root   = Split-Path -Parent $here
$passDir = Join-Path $root 'passwords'
New-Item -Path $passDir -ItemType Directory -Force | Out-Null

function New-Pw([int]$len = 18) {
    -join ((1..$len) | ForEach-Object {
        Get-Random -InputObject ([char[]]'abcdefghjkmnpqrstuvwxyz23456789')
    })
}

[IO.File]::WriteAllText((Join-Path $passDir 'admin_password'), (New-Pw 20) + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
[IO.File]::WriteAllText((Join-Path $passDir 'user_password' ), (New-Pw 16) + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))

$compose = Join-Path $root 'docker-compose.yml'
$running = docker compose -f $compose ps --services 2>$null | Where-Object { $_ -eq 'neko-chromium' }
if ($running) {
    Write-Host 'restarting neko-chromium to pick up new passwords'
    docker compose -f $compose restart neko-chromium
}

Write-Host ''
Write-Host 'admin:' (Get-Content (Join-Path $passDir 'admin_password') -Raw).Trim()
Write-Host 'user :' (Get-Content (Join-Path $passDir 'user_password') -Raw).Trim()
