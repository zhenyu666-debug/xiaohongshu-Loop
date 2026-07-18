$ErrorActionPreference = "SilentlyContinue"
$attempt = 0
$maxAttempts = 20
$retryDelay = 5
$startTime = Get-Date

Write-Host "Starting TigerGraph pull with retry loop..."
Write-Host "Start time: $startTime"

while ($attempt -lt $maxAttempts) {
    $attempt++
    $elapsed = [math]::Round(((Get-Date) - $startTime).TotalMinutes, 1)
    Write-Host "=== Attempt $attempt (elapsed: ${elapsed}m) ==="

    $output = docker pull docker.1ms.run/tigergraph/tigergraph:latest 2>&1
    $exitCode = $LASTEXITCODE

    $output | ForEach-Object { Write-Host $_ }

    if ($exitCode -eq 0) {
        Write-Host "SUCCESS on attempt $attempt!"
        exit 0
    }

    # Check if we made progress (last layer downloaded)
    if ($output -match "eb7a111519fc.*Download complete") {
        Write-Host "Layer eb7a downloaded but extraction failed - retrying immediately..."
    } else {
        Write-Host "Attempt $attempt failed - retrying in $retryDelay seconds..."
        Start-Sleep -Seconds $retryDelay
    }
}

Write-Host "Failed after $maxAttempts attempts"
exit 1
