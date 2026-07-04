# data-lakehouse startup script
param(
    [int]$MaxDockerWait = 300,
    [int]$Speedup = 86400
)

$ErrorActionPreference = "Continue"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

function Write-Step {
    param([string]$Msg, [string]$Color = "Cyan")
    Write-Host ""
    Write-Host ("=" * 60) -ForegroundColor DarkGray
    Write-Host "  $Msg" -ForegroundColor $Color
    Write-Host ("=" * 60) -ForegroundColor DarkGray
}

function Write-Success {
    param([string]$Msg)
    Write-Host "[OK] $Msg" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Msg)
    Write-Host "[WARN] $Msg" -ForegroundColor Yellow
}

function Test-Command {
    param([string]$Cmd)
    try {
        Get-Command $Cmd -ErrorAction Stop | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Wait-ForService {
    param(
        [string]$Name,
        [scriptblock]$Check,
        [int]$TimeoutSec = 120,
        [int]$IntervalSec = 5
    )
    $elapsed = 0
    Write-Host "  Waiting for $Name... (timeout ${TimeoutSec}s)" -ForegroundColor Gray
    while ($elapsed -lt $TimeoutSec) {
        try {
            $result = & $Check
            if ($result) {
                Write-Success "$Name is ready"
                return $true
            }
        } catch {
            # ignore
        }
        Start-Sleep $IntervalSec
        $elapsed += $IntervalSec
        Write-Host "    ${elapsed}s..." -ForegroundColor Gray
    }
    Write-Warn "$Name timeout, continuing"
    return $false
}

# Step 1: Docker Desktop
Write-Step "Step 1/7 -- Docker Desktop"

$dockerRunning = $false
try {
    docker info 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        $dockerRunning = $true
        Write-Success "Docker is already running"
    }
} catch {
    # not running
}

if (-not $dockerRunning) {
    Write-Host "  Starting Docker Desktop..."
    Start-Process "Docker Desktop"
    $elapsed = 0
    while ($elapsed -lt $MaxDockerWait) {
        Start-Sleep 5
        $elapsed += 5
        try {
            docker info 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) {
                $dockerRunning = $true
                break
            }
        } catch { }
        Write-Host "    Docker starting... ${elapsed}s" -ForegroundColor Gray
    }
}

if (-not $dockerRunning) {
    Write-Host ""
    Write-Host "[ERROR] Docker Desktop failed to start. Please start it manually." -ForegroundColor Red
    exit 1
}
Write-Success "Docker Desktop is ready"

# Step 2: docker-compose up
Write-Step "Step 2/7 -- Start infrastructure"

$composeFile = Join-Path $ProjectRoot "docker-compose.yml"
if (-not (Test-Path $composeFile)) {
    Write-Host "[ERROR] docker-compose.yml not found: $composeFile" -ForegroundColor Red
    exit 1
}

Push-Location $ProjectRoot
try {
    docker compose down --remove-orphans 2>$null | Out-Null
    Write-Host "  Running docker compose up -d ..."
    docker compose up -d
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] docker compose up failed (exit $LASTEXITCODE)" -ForegroundColor Red
        exit 1
    }
    Write-Success "docker compose up -d done"
} finally {
    Pop-Location
}

Write-Host "  Waiting for service health checks..."
$null = Wait-ForService "postgres" {
    (docker inspect postgres --format "{{.State.Health.Status}}" 2>$null) -eq "healthy"
} -TimeoutSec 60

$null = Wait-ForService "minio" {
    (docker inspect minio --format "{{.State.Health.Status}}" 2>$null) -eq "healthy"
} -TimeoutSec 60

$null = Wait-ForService "iceberg-rest" {
    (docker inspect iceberg-rest --format "{{.State.Health.Status}}" 2>$null) -eq "healthy"
} -TimeoutSec 90

Write-Success "Infrastructure started"

# Step 3: Flink Iceberg Connector JAR
Write-Step "Step 3/7 -- Download Flink Iceberg Connector JAR"

$libDir = Join-Path $ProjectRoot "flink\lib"
$jarName = "iceberg-flink-runtime-1.18-1.5.2.jar"
$jarPath = Join-Path $libDir $jarName

if (-not (Test-Path $libDir)) {
    New-Item -ItemType Directory -Force -Path $libDir | Out-Null
}

if (Test-Path $jarPath) {
    $size = [math]::Round((Get-Item $jarPath).Length / 1MB, 1)
    Write-Success "JAR already exists: $jarName (${size} MB), skipping download"
} else {
    Write-Host "  Downloading $jarName ..."
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $url = "https://repo1.maven.org/maven2/org/apache/iceberg/iceberg-flink-runtime/1.18/1.5.2/$jarName"
        Invoke-WebRequest -Uri $url -OutFile $jarPath -TimeoutSec 300
        $size = [math]::Round((Get-Item $jarPath).Length / 1MB, 1)
        Write-Success "Downloaded: ${size} MB"
    } catch {
        Write-Warn "JAR download failed. Manual download required: https://repo1.maven.org/maven2/org/apache/iceberg/iceberg-flink-runtime/1.18/1.5.2/$jarName"
    }
}

Write-Host "  Restarting Flink TaskManager to load JAR..."
Push-Location $ProjectRoot
docker compose restart flink-taskmanager 2>$null | Out-Null
Pop-Location
Write-Success "Flink TaskManager restarted"

# Step 4: Kafka Topic
Write-Step "Step 4/7 -- Create Kafka Topic"

$null = Wait-ForService "Kafka" {
    try {
        docker exec kafka kafka-topics.sh --bootstrap-server localhost:9092 --list 2>$null | Out-Null
        $LASTEXITCODE -eq 0
    } catch { $false }
} -TimeoutSec 60

$existing = docker exec kafka kafka-topics.sh --bootstrap-server localhost:9092 --list 2>$null | Out-String
if ($existing -match "user-behavior") {
    Write-Success "Topic 'user-behavior' already exists"
} else {
    Write-Host "  Creating topic: user-behavior (6 partitions)..."
    $result = docker exec kafka kafka-topics.sh `
        --bootstrap-server localhost:9092 `
        --create --topic user-behavior `
        --partitions 6 --replication-factor 1 `
        --if-not-exists 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Topic 'user-behavior' created"
    } else {
        Write-Warn "Topic creation failed: $result"
    }
}

# Step 5: Python dependencies
Write-Step "Step 5/7 -- Install Python dependencies"

$pythonExe = $null
foreach ($cmd in @("python", "python3", "py")) {
    if (Test-Command $cmd) {
        $pythonExe = $cmd
        break
    }
}

if ($pythonExe -eq $null) {
    Write-Warn "Python not found, skipping dependency install"
} else {
    Write-Host "  Installing kafka-python, pandas, psutil..."
    $pipOut = & $pythonExe -m pip install kafka-python pandas psutil -q 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Python dependencies installed"
    } else {
        Write-Warn "Some packages failed to install. Run manually: pip install kafka-python pandas psutil"
    }
}

# Step 6: Data Replay Producer
Write-Step "Step 6/7 -- Run Data Replay Producer"

$csvPath = Join-Path $ProjectRoot "data\raw\UserBehavior.csv"
if (-not (Test-Path $csvPath)) {
    Write-Host "[ERROR] Data file not found: $csvPath" -ForegroundColor Red
    Write-Host "  Run first: python data\generate_test_data.py" -ForegroundColor Yellow
    exit 1
}

$producerScript = Join-Path $ProjectRoot "replay\kafka_replay_producer.py"
if (-not (Test-Path $producerScript)) {
    Write-Host "[ERROR] Producer script not found: $producerScript" -ForegroundColor Red
    exit 1
}

$csvSize = [math]::Round((Get-Item $csvPath).Length / 1MB, 1)
$playbackSec = [int](86400 / $Speedup)
Write-Host "  Data file: $csvPath"
Write-Host "  File size: ${csvSize} MB"
Write-Host "  Speedup: ${Speedup}x (1 second = ${playbackSec} seconds of original data)"
Write-Host ""
Write-Host "  Starting Replay Producer..."
Write-Host "  (Ctrl+C to interrupt safely - script supports resume)" -ForegroundColor Gray
Write-Host ""

$replayCmd = "$pythonExe `"$producerScript`" --input `"$csvPath`" --kafka localhost:9092 --topic user-behavior --speedup $Speedup --batch-size 5000"
Write-Host "  Command: $replayCmd" -ForegroundColor Gray
Write-Host ""

try {
    Invoke-Expression $replayCmd
    Write-Success "Data Replay completed"
} catch {
    Write-Warn "Data Replay error: $_"
}

# Step 7: Done
Write-Step "Step 7/7 -- All done!" "Green"

Write-Host ""
Write-Host "  Real-time Lakehouse Project Started!" -ForegroundColor Green
Write-Host ""
Write-Host "  Service URLs:" -ForegroundColor White
Write-Host "  - Flink Dashboard: http://localhost:8081" -ForegroundColor Cyan
Write-Host "  - Kafka UI:        http://localhost:8083" -ForegroundColor Cyan
Write-Host "  - MinIO Console:   http://localhost:9001  (admin / password)" -ForegroundColor Cyan
Write-Host "  - Trino:          http://localhost:8080" -ForegroundColor Cyan
Write-Host "  - Iceberg REST:   http://localhost:8181" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Container status:" -ForegroundColor White
Push-Location $ProjectRoot
docker compose ps --format "  {{.Name}}: {{.State}}" | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
Pop-Location
Write-Host ""
Write-Host "  Next steps:" -ForegroundColor White
Write-Host "  1. Open Flink Dashboard (localhost:8081) and submit SQL jobs" -ForegroundColor Gray
Write-Host "  2. Execute flink/jobs/01-04 SQL files in order" -ForegroundColor Gray
Write-Host "  3. Query with Trino (localhost:8080) using trino/queries/*.sql" -ForegroundColor Gray
Write-Host ""
