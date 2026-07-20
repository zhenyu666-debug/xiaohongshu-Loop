# share-neko-supervisor.ps1
#
# Single-shot supervisor that:
#   1. docker compose up the neko container (idempotent)
#   2. start the backend uvicorn (with bogus TG_HOST so the /api/health
#      ping fails fast instead of blocking 14s waiting for the unreachable
#      TigerGraph RESTPP)
#   3. start the vite dev server (with the allowedHosts fix baked in
#      so the chromium container's host.docker.internal request is not
#      rejected)
#   4. open a serveo SSH tunnel forwarding localhost:8080 (neko) outward,
#      capture the share URL from the PTY banner, and write it to
#      $env:TEMP\neko_url.txt AND $root\.neko\current_url.txt so any
#      future run can pick it up
#   5. watch all four children every 10s and restart any that died, while
#      the supervisor itself is alive
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File .neko/share-neko-supervisor.ps1
#
# Stop:
#   stop the supervisor with Ctrl-C; or kill its PID. The four children
#   stay alive (this script intentionally does NOT bring them down on
#   exit — see 'Bring down' in README.md).

$ErrorActionPreference = 'Stop'

$root         = 'C:\Users\Hasee\.qclaw\workspace\get_jobs'
$fraudEngine  = Join-Path $root 'fraud-risk-engine'
$frontend     = Join-Path $fraudEngine 'frontend'
$nekoDir      = Join-Path $root '.neko'
$compose      = Join-Path $nekoDir 'docker-compose.yml'

$serveoOut    = Join-Path $env:TEMP 'neko_serveo_out.txt'
$serveoErr    = Join-Path $env:TEMP 'neko_serveo_err.txt'
$urlTmpFile   = Join-Path $env:TEMP 'neko_url.txt'
$urlFile      = Join-Path $nekoDir  'current_url.txt'
$stateFile    = Join-Path $nekoDir  'supervisor_state.json'

$logDir       = Join-Path $nekoDir 'logs'
New-Item -Path $logDir -ItemType Directory -Force | Out-Null
$supLog       = Join-Path $logDir 'supervisor.log'

function Log([string]$msg) {
    $ts = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
    Write-Host "[$ts] $msg"
    Add-Content -Path $supLog -Value "[$ts] $msg" -Encoding UTF8
}

function Save-State([hashtable]$s) {
    $s | ConvertTo-Json -Depth 4 | Set-Content -Path $stateFile -Encoding UTF8
}

function Test-NeokAlive() {
    $svc = (& docker compose -f $compose ps --services 2>$null) -join ''
    $svcOnline = (& docker compose -f $compose ps neko-chromium 2>$null) | Select-String 'Up|healthy'
    return [bool]$svcOnline
}

function Test-Listening([int]$port) {
    $c = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
    return [bool]$c
}

function Test-Health([int]$port, [string]$path, [int]$timeoutSec = 15) {
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:$port$path" -TimeoutSec $timeoutSec -UseBasicParsing -ErrorAction Stop
        return $r.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Capture-Existing-Url() {
    if (Test-Path $urlFile) {
        $existing = (Get-Content $urlFile -Raw -ErrorAction SilentlyContinue).Trim()
        if ($existing -and $existing -match '^https://') { return $existing }
    }
    return $null
}

function Start-Neko() {
    if (Test-NeokAlive) {
        Log 'neko already up — skipping'
        return
    }
    Log 'starting neko via docker compose...'
    Push-Location $nekoDir
    try {
        & docker compose -f $compose up -d 2>&1 | ForEach-Object { Log "compose: $_" }
    } finally {
        Pop-Location
    }
    $deadline = (Get-Date).AddSeconds(90)
    while ((Get-Date) -lt $deadline) {
        if (Test-NeokAlive) { Log 'neko healthy'; return }
        Start-Sleep -Seconds 2
    }
    Log 'neko failed to come up within 90s'
}

function Start-Backend() {
    if (Test-Listening 8888) {
        # Verify it's actually serving (not a wedged uvicorn from a previous boot)
        if (Test-Health 8888 '/api/health' 18) {
            Log 'backend already healthy — skipping'
            return
        }
        Log 'backend listening but not responding — killing stale process'
        Get-NetTCPConnection -State Listen -LocalPort 8888 -ErrorAction SilentlyContinue |
            ForEach-Object {
                try { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } catch {}
            }
        Start-Sleep -Seconds 1
    }
    Log 'starting uvicorn on :8888 (TG_HOST=127.0.0.1 TG_RESTPP_PORT=19999 so healthcheck fails fast)...'
    $env:TG_HOST = '127.0.0.1'
    $env:TG_RESTPP_PORT = '19999'
    $outLog = Join-Path $logDir 'backend.out.log'
    $errLog = Join-Path $logDir 'backend.err.log'
    $proc = Start-Process -FilePath 'python' `
        -ArgumentList @('-m','uvicorn','app:app','--host','0.0.0.0','--port','8888') `
        -WorkingDirectory $fraudEngine `
        -RedirectStandardOutput $outLog `
        -RedirectStandardError  $errLog `
        -PassThru `
        -WindowStyle Hidden
    $backendPid = [int]$proc.Id
    Log "backend PID $backendPid"
    # wait for /api/health to return 200 (may take ~15s because of TG ping retries)
    $deadline = (Get-Date).AddSeconds(45)
    while ((Get-Date) -lt $deadline) {
        if (Test-Health 8888 '/api/health' 20) { Log 'backend healthy'; return }
        Start-Sleep -Seconds 2
    }
    Log 'backend failed to become healthy within 45s — see backend.out.log / backend.err.log'
}

function Start-Vite() {
    if (Test-Listening 5173) {
        if (Test-Health 5173 '/' 5) {
            Log 'vite already healthy — skipping'
            return
        }
        Log 'vite listening but not responding — killing stale process'
        Get-NetTCPConnection -State Listen -LocalPort 5173 -ErrorAction SilentlyContinue |
            ForEach-Object {
                try { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } catch {}
            }
        Start-Sleep -Seconds 1
    }
    Log 'starting vite on :5173...'
    $outLog = Join-Path $logDir 'vite.out.log'
    $errLog = Join-Path $logDir 'vite.err.log'
    $viteBin = Join-Path $frontend 'node_modules\.bin\vite.cmd'
    $proc = Start-Process -FilePath $viteBin `
        -ArgumentList @('--host','0.0.0.0','--port','5173') `
        -WorkingDirectory $frontend `
        -RedirectStandardOutput $outLog `
        -RedirectStandardError  $errLog `
        -PassThru `
        -WindowStyle Hidden
    $vitePid = [int]$proc.Id
    Log "vite PID $vitePid"
    $deadline = (Get-Date).AddSeconds(30)
    while ((Get-Date) -lt $deadline) {
        if (Test-Health 5173 '/' 5) { Log 'vite healthy'; return }
        Start-Sleep -Seconds 2
    }
    Log 'vite failed to come up within 30s — see vite.out.log / vite.err.log'
}

function Start-Serveo() {
    # If we already captured a URL and the tunnel is still alive, reuse it
    $existing = Capture-Existing-Url
    if ($existing) {
        $c = Get-NetTCPConnection -State Established -RemotePort 22 -ErrorAction SilentlyContinue |
                Where-Object { $_.OwningProcess -in @(Get-Process -Name ssh -ErrorAction SilentlyContinue | ForEach-Object Id) }
        if ($c) {
            Log "serveo tunnel still alive, reusing $existing"
            return $existing
        }
    }
    # else kill any stale ssh and start fresh
    Get-Process -Name ssh -ErrorAction SilentlyContinue | ForEach-Object {
        try { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue } catch {}
    }
    Start-Sleep -Seconds 1

    Log 'starting serveo SSH tunnel...'
    Remove-Item $serveoOut,$serveoErr -ErrorAction SilentlyContinue
    $proc = Start-Process -FilePath 'ssh' `
        -ArgumentList @('-tt','-o','ServerAliveInterval=30','-o','ServerAliveCountMax=3',
                         '-R','80:localhost:8080','serveo.net') `
        -RedirectStandardOutput $serveoOut `
        -RedirectStandardError  $serveoErr `
        -PassThru
    Log "serveo ssh PID $($proc.Id)"

    # Wait up to 120s for the URL to appear in the PTY capture
    $url = $null
    $deadline = (Get-Date).AddSeconds(120)
    while ((Get-Date) -lt $deadline -and -not $url) {
        if (Test-Path $serveoOut) {
            $txt = Get-Content $serveoOut -Raw -ErrorAction SilentlyContinue
            $m = [regex]::Match($txt, 'https://([a-z0-9-]+)\.serveousercontent\.com')
            if ($m.Success) { $url = $m.Value }
        }
        Start-Sleep -Seconds 2
    }
    if ($url) {
        Set-Content -Path $urlTmpFile -Value $url -Encoding UTF8
        Set-Content -Path $urlFile    -Value $url -Encoding UTF8
        Log "SHARE URL: $url"
    } else {
        Log "no serveo URL captured within 120s — check $serveoOut / $serveoErr"
    }
    return $url
}

# --- bring everything up ---
Log "=== supervisor start (PID $PID) ==="
Start-Neko
Start-Backend
Start-Vite
Start-Serveo

$state = @{
    started_at   = (Get-Date).ToString('o')
    share_url    = Capture-Existing-Url
    supervisor   = $PID
}
Save-State $state

Log "=== stack up ==="
Log "share URL: $($state.share_url)"
Log "admin pw : $((Get-Content (Join-Path $nekoDir 'passwords/admin_password') -Raw).Trim())"
Log "user  pw : $((Get-Content (Join-Path $nekoDir 'passwords/user_password')  -Raw).Trim())"
Log "supervisor is now in WATCH mode. Ctrl-C to stop; children stay up."

# --- watch loop: every 10s, restart anything that died ---
try {
    while ($true) {
        Start-Sleep -Seconds 10
        if (-not (Test-NeokAlive)) {
            Log 'WATCH: neko died — restarting'
            Start-Neko
        }
        if (-not (Test-Listening 8888) -or -not (Test-Health 8888 '/api/health' 18)) {
            Log 'WATCH: backend unhealthy — restarting'
            Start-Backend
        }
        if (-not (Test-Listening 5173) -or -not (Test-Health 5173 '/' 5)) {
            Log 'WATCH: vite unhealthy — restarting'
            Start-Vite
        }
        # SSH tunnel health: must have a TCP connection to serveo.net:22
        $sshAlive = $false
        Get-Process -Name ssh -ErrorAction SilentlyContinue | ForEach-Object {
            $c = Get-NetTCPConnection -State Established -RemotePort 22 -OwningProcess $_.Id -ErrorAction SilentlyContinue
            if ($c) { $sshAlive = $true }
        }
        if (-not $sshAlive) {
            Log 'WATCH: serveo tunnel died — re-opening'
            Start-Serveo
            $state.share_url = Capture-Existing-Url
            Save-State $state
            Log "WATCH: new share URL: $($state.share_url)"
        }
    }
} finally {
    Log '=== supervisor exiting (children left running) ==='
}
