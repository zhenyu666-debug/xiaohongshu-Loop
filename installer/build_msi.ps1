#requires -Version 5.1
<#
Build xhs-saas-console.msi from dist/ contents using WiX 3.14.

Usage:
    PS> .\installer\build_msi.ps1 -Version 0.6.0
#>
[CmdletBinding()]
param(
    [string]$Version = "0.6.0",
    [switch]$SkipVerify
)

$ErrorActionPreference = "Stop"

$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot   = (Resolve-Path (Join-Path $ScriptDir "..")).Path
$DistDir    = Join-Path $RepoRoot "dist\xhs-saas-console"
$WixDir     = "C:\wix\3.14"
$WixSrcDir  = Join-Path $ScriptDir "wix"
$BuildDir   = Join-Path $ScriptDir "build"
$OutputDir  = Join-Path $ScriptDir "output"
$StagingDir = Join-Path $BuildDir "staging"

$candle = Join-Path $WixDir "candle.exe"
$light  = Join-Path $WixDir "light.exe"
$heat   = Join-Path $WixDir "heat.exe"

if (-not (Test-Path $candle)) { throw "WiX not installed at $WixDir" }
if (-not (Test-Path $DistDir)) { throw "dist\xhs-saas-console not found at $DistDir" }

Write-Host "==> RepoRoot : $RepoRoot"
Write-Host "==> DistDir  : $DistDir"
Write-Host "==> Version  : $Version"

if (Test-Path $BuildDir) { Remove-Item $BuildDir -Recurse -Force }
New-Item -ItemType Directory -Path $BuildDir   -Force | Out-Null
New-Item -ItemType Directory -Path $StagingDir -Force | Out-Null

Write-Host "==> Staging"
Copy-Item -Path (Join-Path $DistDir "*") -Destination $StagingDir -Recurse -Force

$MainExeSource = Join-Path $RepoRoot "dist\xhs-saas-console.exe"
$MainExeTarget = Join-Path $StagingDir "xhs-saas-console.exe"
if (Test-Path $MainExeSource) {
    Copy-Item -Path $MainExeSource -Destination $MainExeTarget -Force
}

foreach ($f in @("LICENSE","README.md","FAQ.md")) {
    $src = Join-Path $RepoRoot $f
    if (Test-Path $src) {
        Copy-Item -Path $src -Destination $StagingDir -Force
    }
}

Write-Host "==> heat harvesting"
$filesWxs = Join-Path $BuildDir "Files.wxs"
& $heat dir $StagingDir -cg HarvestedFiles -dr INSTALLDIR -srd -sreg -gg -ke `
       -var var.StagingDir `
       -out $filesWxs
if ($LASTEXITCODE -ne 0) { throw "heat failed ($LASTEXITCODE)" }

Write-Host "==> candle compiling"
$productWxs = Join-Path $WixSrcDir "product.wxs"
Push-Location $BuildDir
try {
    & $candle -nologo -arch x64 -ext WixUtilExtension `
            "-dVersion=$Version" `
            "-dStagingDir=$StagingDir" `
            "-out." `
            $productWxs `
            $filesWxs
    if ($LASTEXITCODE -ne 0) { throw "candle failed ($LASTEXITCODE)" }
} finally {
    Pop-Location
}

Write-Host "==> light linking"
$MsiOut = Join-Path $OutputDir ("xhs-saas-console-" + $Version + ".msi")
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
Push-Location $BuildDir
try {
    & $light -nologo -sval -cultures:en-US -ext WixUIExtension -ext WixUtilExtension `
            -out $MsiOut `
            (Join-Path $BuildDir "product.wixobj") `
            (Join-Path $BuildDir "Files.wixobj")
    if ($LASTEXITCODE -ne 0) { throw "light failed ($LASTEXITCODE)" }
} finally {
    Pop-Location
}

$MsiSize = [math]::Round((Get-Item $MsiOut).Length / 1MB, 1)
Write-Host "==> MSI built: $MsiOut ($MsiSize MB)" -ForegroundColor Green

if (-not $SkipVerify) {
    $Sandbox = Join-Path $BuildDir "verify"
    if (Test-Path $Sandbox) { Remove-Item $Sandbox -Recurse -Force }
    New-Item -ItemType Directory -Path $Sandbox -Force | Out-Null

    Write-Host "==> msiexec /a verify"
    $p = Start-Process -FilePath "msiexec.exe" `
        -ArgumentList "/a `"$MsiOut`" /qn TARGETDIR=`"$Sandbox\installed`"" `
        -Wait -PassThru -NoNewWindow
    if ($p.ExitCode -ne 0) { throw "msiexec /a failed: $($p.ExitCode)" }

    $InstalledExe = Join-Path $Sandbox "installed\xhs-saas-console\xhs-saas-console.exe"
    if (-not (Test-Path $InstalledExe)) {
        Get-ChildItem (Join-Path $Sandbox "installed") -Recurse -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -eq "xhs-saas-console.exe" } | ForEach-Object { Write-Host "  found: $($_.FullName)" }
        throw "MSI did not install xhs-saas-console.exe"
    }
    Write-Host "==> MSI verified: $InstalledExe" -ForegroundColor Green
    Remove-Item $Sandbox -Recurse -Force
}

Write-Host "==> Done" -ForegroundColor Green