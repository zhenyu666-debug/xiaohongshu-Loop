# Opens a serveo SSH tunnel that forwards 80:localhost:8080 (the neko web UI), and
# captures the randomly-assigned share URL from the PTY banner into $env:TEMP\neko_url.txt.
#
# Run this AFTER `docker compose up -d`. Reads the URL out of the capture file when
# it finally appears (serveo sometimes takes 3-30s to assign a hostname).

$ErrorActionPreference = 'Stop'
$root   = 'C:\Users\Hasee\.qclaw\workspace\get_jobs'
$out    = Join-Path $env:TEMP 'neko_serveo_out.txt'
$err    = Join-Path $env:TEMP 'neko_serveo_err.txt'
$banner = Join-Path $env:TEMP 'neko_url.txt'

Remove-Item $out,$err,$banner -ErrorAction SilentlyContinue

    $argList = @('-tt','-o','ServerAliveInterval=30','-o','ServerAliveCountMax=3',
                 '-R','80:localhost:8080','serveo.net')

    Write-Host 'launching ssh tunnel, capturing PTY to' $out
    $proc = Start-Process -FilePath 'ssh' -ArgumentList $argList `
        -RedirectStandardOutput $out `
        -RedirectStandardError  $err `
        -PassThru

Write-Host 'ssh started, PID' $proc.Id

# Poll the captured output for ~120 s looking for the share URL.
$end = (Get-Date).AddSeconds(120)
$url  = $null
while ((Get-Date) -lt $end -and -not $url) {
    if (Test-Path $out) {
        $txt = Get-Content $out -Raw -ErrorAction SilentlyContinue
        $m   = [regex]::Match($txt, 'https://([a-z0-9-]+)\.serveousercontent\.com')
        if ($m.Success) { $url = $m.Value }
    }
    Start-Sleep -Seconds 2
}

if ($url) {
    Set-Content -Path $banner -Value $url -Encoding UTF8
    Write-Host ''
    Write-Host 'SHARE URL:' $url
    Write-Host ''
    Write-Host '(also saved to' $banner ')'
} else {
    Write-Host 'no URL captured within 120s — check' $out 'and' $err
}
