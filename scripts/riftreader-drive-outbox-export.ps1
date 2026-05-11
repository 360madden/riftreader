# Version: riftreader-drive-outbox-export-v0.1.0
# Total-Character-Count: 6685
# Purpose: Copy selected RiftReader local run-summary/log artifacts into the local Google Drive-synced RiftReader outbox with SHA-256 verification. No patch apply, no Git mutation, no movement/input.

[CmdletBinding()]
param(
    [string[]]$SourcePath,
    [string]$DriveRoot,
    [string]$OutboxRoot,
    [ValidateSet("run-summaries", "logs", "screenshots", "status")]
    [string]$Category = "run-summaries",
    [int]$MaxFiles = 10,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-Dir {
    param([string[]]$Candidates)
    foreach ($candidate in $Candidates) {
        if (-not [string]::IsNullOrWhiteSpace($candidate)) {
            $expanded = [Environment]::ExpandEnvironmentVariables($candidate)
            if (Test-Path -LiteralPath $expanded -PathType Container) {
                return (Resolve-Path -LiteralPath $expanded).Path
            }
        }
    }
    return $null
}

function Get-Sha256Hex {
    param([Parameter(Mandatory = $true)][string]$Path)
    return [string](Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
}

function Resolve-SourceFile {
    param([Parameter(Mandatory = $true)][string]$PathText)

    $expanded = [Environment]::ExpandEnvironmentVariables($PathText)
    if ([System.IO.Path]::IsPathRooted($expanded)) {
        if (Test-Path -LiteralPath $expanded -PathType Leaf) {
            return (Resolve-Path -LiteralPath $expanded).Path
        }
    }

    $repoRelative = Join-Path $RepoRoot $expanded
    if (Test-Path -LiteralPath $repoRelative -PathType Leaf) {
        return (Resolve-Path -LiteralPath $repoRelative).Path
    }

    throw "Source file not found: $PathText"
}

if ($MaxFiles -lt 1) {
    throw "MaxFiles must be at least 1."
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

$ResolvedDriveRoot = Resolve-Dir -Candidates @(
    $DriveRoot,
    "$env:USERPROFILE\Google Drive",
    "$env:USERPROFILE\Google Drive\My Drive",
    "$env:USERPROFILE\My Drive",
    "$env:USERPROFILE\OneDrive\Google Drive",
    "G:\My Drive",
    "G:\Google Drive"
)

$ResolvedOutboxRoot = Resolve-Dir -Candidates @(
    $OutboxRoot,
    $(if (-not [string]::IsNullOrWhiteSpace($ResolvedDriveRoot)) { Join-Path $ResolvedDriveRoot "RiftReader\outbox" } else { $null })
)

$warnings = [System.Collections.Generic.List[string]]::new()
$copied = [System.Collections.Generic.List[object]]::new()

if ([string]::IsNullOrWhiteSpace($ResolvedOutboxRoot)) {
    $warnings.Add("No local RiftReader Drive outbox root was found. Pass -DriveRoot or -OutboxRoot explicitly.") | Out-Null
}

$sourceFiles = [System.Collections.Generic.List[string]]::new()
if ($SourcePath -and $SourcePath.Count -gt 0) {
    foreach ($source in $SourcePath) {
        $sourceFiles.Add((Resolve-SourceFile -PathText $source)) | Out-Null
    }
}

if ($sourceFiles.Count -eq 0) {
    $captureRoot = Join-Path $RepoRoot "scripts\captures"
    if (Test-Path -LiteralPath $captureRoot -PathType Container) {
        $latest = @(Get-ChildItem -LiteralPath $captureRoot -Recurse -File -Filter "*.json" -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -match "\\drive-" -or $_.Name -match "drive-" } |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First $MaxFiles)
        foreach ($file in $latest) {
            $sourceFiles.Add($file.FullName) | Out-Null
        }
    }
}

if ($sourceFiles.Count -eq 0) {
    $warnings.Add("No source files were supplied or auto-discovered.") | Out-Null
}

$sessionDir = $null
if (-not [string]::IsNullOrWhiteSpace($ResolvedOutboxRoot)) {
    $stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
    $sessionDir = Join-Path (Join-Path $ResolvedOutboxRoot $Category) $stamp
    New-Item -ItemType Directory -Path $sessionDir -Force | Out-Null

    foreach ($sourceFile in @($sourceFiles.ToArray())) {
        $sourceItem = Get-Item -LiteralPath $sourceFile
        $destPath = Join-Path $sessionDir $sourceItem.Name
        Copy-Item -LiteralPath $sourceItem.FullName -Destination $destPath -Force

        $sourceHash = Get-Sha256Hex -Path $sourceItem.FullName
        $destHash = Get-Sha256Hex -Path $destPath

        $copied.Add([pscustomobject][ordered]@{
            sourcePath = $sourceItem.FullName
            destinationPath = $destPath
            fileName = $sourceItem.Name
            lengthBytes = [int64]$sourceItem.Length
            sourceSha256 = $sourceHash
            destinationSha256 = $destHash
            hashMatch = [string]::Equals($sourceHash, $destHash, [System.StringComparison]::OrdinalIgnoreCase)
        }) | Out-Null
    }
}

$summaryRoot = Join-Path $RepoRoot "scripts\captures\drive-outbox-export"
New-Item -ItemType Directory -Path $summaryRoot -Force | Out-Null
$summaryPath = Join-Path $summaryRoot ("drive-outbox-export-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".json")

$failedCopies = @($copied.ToArray() | Where-Object { -not $_.hashMatch })
$summary = [ordered]@{
    schemaVersion = 1
    mode = "riftreader-drive-outbox-export"
    status = if ([string]::IsNullOrWhiteSpace($ResolvedOutboxRoot)) { "blocked-no-outbox-root" } elseif ($failedCopies.Count -gt 0) { "failed-hash-mismatch" } else { "completed" }
    ok = (-not [string]::IsNullOrWhiteSpace($ResolvedOutboxRoot) -and $failedCopies.Count -eq 0)
    generatedAtUtc = (Get-Date).ToUniversalTime().ToString("o")
    repoRoot = $RepoRoot
    driveRoot = $ResolvedDriveRoot
    outboxRoot = $ResolvedOutboxRoot
    category = $Category
    sessionDir = $sessionDir
    sourceCount = $sourceFiles.Count
    copiedCount = $copied.Count
    copied = @($copied.ToArray())
    warnings = @($warnings.ToArray())
    artifacts = [ordered]@{
        summaryJson = $summaryPath
        localSummaryRoot = $summaryRoot
        outboxSessionDir = $sessionDir
    }
    safety = [ordered]@{
        movementSent = $false
        inputSent = $false
        reloaduiSent = $false
        screenshotKeySent = $false
        gitMutation = $false
        patchApplied = $false
        noCheatEngine = $true
    }
}

$summary | ConvertTo-Json -Depth 80 | Set-Content -LiteralPath $summaryPath -Encoding UTF8

if ($Json.IsPresent) {
    Get-Content -LiteralPath $summaryPath -Raw
} else {
    Write-Host "RiftReader Drive outbox export"
    Write-Host "Status : $($summary.status)"
    Write-Host "Copied : $($summary.copiedCount)"
    Write-Host "Outbox : $sessionDir"
    Write-Host "Summary: $summaryPath"
    foreach ($warning in $warnings) { Write-Host "Warning: $warning" -ForegroundColor Yellow }
}

# END_OF_SCRIPT_MARKER
