#requires -Version 5.1
<#
Top-level build script for xiaohongshu-Loop.

Builds dist/xhs-saas-console.exe (onefile) and dist/xhs-saas-console/ payload,
then assembles the WiX-based MSI installer. After a successful build,
optionally pushes the GitHub Release, using the bilingual release notes
under installer/docs/RELEASE_NOTES/.

Usage:
    # build only
    PS> .\installer\build.ps1 -Version 0.6.1

    # build + publish release (requires gh CLI)
    PS> .\installer\build.ps1 -Version 0.6.1 -Publish

    # publish a release using an existing MSI in installer/output/
    PS> .\installer\build.ps1 -Version 0.6.1 -Publish -SkipBuild

Environment:
    GH_TOKEN or gh auth login must be configured before -Publish.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [string]$Version,

    [switch]$Publish,

    [switch]$SkipBuild,

    [switch]$SkipVerify
)

$ErrorActionPreference = "Stop"

$ScriptDir    = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot     = (Resolve-Path (Join-Path $ScriptDir "..")).Path
$OutputDir    = Join-Path $ScriptDir "output"
$MsiOut       = Join-Path $OutputDir ("xhs-saas-console-" + $Version + ".msi")
$ReleaseNotes = Join-Path $ScriptDir "docs\RELEASE_NOTES\v$Version.md"

if (-not $SkipBuild) {
    Write-Host "==> [1/2] Building MSI" -ForegroundColor Cyan
    & (Join-Path $ScriptDir "build_msi.ps1") -Version $Version -SkipVerify:$SkipVerify
    if ($LASTEXITCODE -ne 0) { throw "build_msi.ps1 failed ($LASTEXITCODE)" }
} else {
    Write-Host "==> [1/2] Skipping MSI build (using existing $MsiOut)" -ForegroundColor Yellow
}

if (-not (Test-Path $MsiOut)) {
    throw "MSI not found at $MsiOut. Run without -SkipBuild."
}

if ($Publish) {
    Write-Host "==> [2/2] Publishing GitHub Release" -ForegroundColor Cyan

    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
        throw "gh CLI not found. Install: winget install GitHub.cli"
    }

    $Title = "v$Version - <one-line summary>"
    if (Test-Path $ReleaseNotes) {
        Write-Host "    using notes from: $ReleaseNotes"
        $NotesArg = @("--notes-file", $ReleaseNotes)
    } else {
        Write-Host "    no release notes found at $ReleaseNotes, falling back to default text" -ForegroundColor Yellow
        $NotesArg = @("--notes", "See CHANGELOG.md for full release notes.")
    }

    Push-Location $RepoRoot
    try {
        & gh release create "v$Version" `
            --title $Title `
            @NotesArg `
            $MsiOut
        if ($LASTEXITCODE -ne 0) { throw "gh release create failed ($LASTEXITCODE)" }
    } finally {
        Pop-Location
    }
    Write-Host "    release published: https://github.com/zhenyu666-debug/xiaohongshu-Loop/releases/tag/v$Version"
} else {
    Write-Host "==> [2/2] Skipping GitHub Release (re-run with -Publish to push)" -ForegroundColor Yellow
}

Write-Host "==> Done" -ForegroundColor Green