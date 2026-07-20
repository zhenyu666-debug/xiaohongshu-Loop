# healthcheck.ps1 — emit a JSON snapshot of the neko + vite + backend + serveo stack.
#
# Output: prints JSON to stdout and writes it to .neko/supervisor_state.json so
# other tools (status pages, alert webhooks) can read the latest snapshot without
# re-running the probes.
#
# Usage:
#   powershell -NoProfile -File .neko/healthcheck.ps1

$ErrorActionPreference = 'Stop'

$root       = 'C:\Users\Hasee\.qclaw\workspace\get_jobs'
$nekoDir    = Join-Path $root '.neko'
$compose    = Join-Path $nekoDir 'docker-compose.yml'
$stateFile  = Join-Path $nekoDir 'supervisor_state.json'
$urlFile    = Join-Path $nekoDir 'current_url.txt'

function Probe([int]$port, [string]$path, [int]$timeoutSec = 15) {
    $started = Get-Date
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:$port$path" -TimeoutSec $timeoutSec -UseBasicParsing -ErrorAction Stop
        return @{
            ok       = ($r.StatusCode -eq 200)
            status   = $r.StatusCode
            latency_ms = [int]((Get-Date) - $started).TotalMilliseconds
            bytes    = $r.RawContentLength
        }
    } catch {
        return @{
            ok        = $false
            error     = $_.Exception.Message
            latency_ms = [int]((Get-Date) - $started).TotalMilliseconds
        }
    }
}

$nekoContainer = & docker compose -f $compose ps neko-chromium 2>$null
$nekoUp = ($nekoContainer | Select-String 'Up|healthy') -ne $null

$backend = Probe 8888 '/api/health' 25
$frontend = Probe 5173 '/' 5

# serveo: must have at least one SSH process with an Established TCP conn to :22
$sshTunnels = Get-Process -Name ssh -ErrorAction SilentlyContinue | ForEach-Object {
    $conn = Get-NetTCPConnection -State Established -RemotePort 22 -OwningProcess $_.Id -ErrorAction SilentlyContinue
    if ($conn) {
        return @{
            pid            = $_.Id
            started        = $_.StartTime.ToString('o')
            remote         = "$($conn.RemoteAddress):$($conn.RemotePort)"
            local          = "$($conn.LocalAddress):$($conn.LocalPort)"
        }
    }
    return $null
} | Where-Object { $_ }

$shareUrl = $null
if (Test-Path $urlFile) {
    $shareUrl = (Get-Content $urlFile -Raw -ErrorAction SilentlyContinue).Trim()
    if ($shareUrl -notmatch '^https://') { $shareUrl = $null }
}

$report = [ordered]@{
    checked_at = (Get-Date).ToString('o')
    neko       = @{
        running   = $nekoUp
        compose_ps = ($nekoContainer -join "`n").Trim()
    }
    backend    = $backend
    frontend   = $frontend
    serveo     = @{
        tunnels  = @($sshTunnels)
        share_url = $shareUrl
    }
    ok         = ($nekoUp -and $backend.ok -and $frontend.ok -and $sshTunnels.Count -gt 0 -and $shareUrl)
}

$json = $report | ConvertTo-Json -Depth 5
Set-Content -Path $stateFile -Value $json -Encoding UTF8
Write-Output $json

if (-not $report.ok) {
    exit 1
}
