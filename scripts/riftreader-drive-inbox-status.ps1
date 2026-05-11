# Version: riftreader-drive-inbox-status-v0.1.0
# Total-Character-Count: 6991
# Purpose: Inspect a local Google Drive-synced RiftReader artifact inbox, identify patch packages/manifests, compute SHA-256 hashes, and write a JSON status report. Discovery only: no patch apply, no Git mutation, no movement/input.

[CmdletBinding()]
param(
    [string]$DriveRoot,
    [string]$InboxRoot,
    [string]$OutputRoot,
    [int]$MaxDepth = 4,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-Sha256Hex {
    param([Parameter(Mandatory = $true)][string]$Path)
    return [string](Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
}

function Resolve-ExistingDirectory {
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

function Get-RelativePathSafe {
    param(
        [Parameter(Mandatory = $true)][string]$BasePath,
        [Parameter(Mandatory = $true)][string]$Path
    )

    try {
        return [System.IO.Path]::GetRelativePath($BasePath, $Path)
    }
    catch {
        return $Path
    }
}

if ($MaxDepth -lt 0) {
    throw "MaxDepth must be zero or greater."
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path $RepoRoot "scripts\captures\drive-inbox-status"
}

$OutputRoot = [System.IO.Path]::GetFullPath($OutputRoot)
New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null

$resolvedDriveRoot = Resolve-ExistingDirectory -Candidates @(
    $DriveRoot,
    "$env:USERPROFILE\Google Drive",
    "$env:USERPROFILE\My Drive",
    "$env:USERPROFILE\Google Drive\My Drive",
    "$env:USERPROFILE\OneDrive\Google Drive"
)

$inboxCandidates = @()
if (-not [string]::IsNullOrWhiteSpace($InboxRoot)) {
    $inboxCandidates += $InboxRoot
}

if (-not [string]::IsNullOrWhiteSpace($resolvedDriveRoot)) {
    $inboxCandidates += (Join-Path $resolvedDriveRoot "RiftReader\inbox")
    $inboxCandidates += (Join-Path $resolvedDriveRoot "RiftReader")
}

$resolvedInboxRoot = Resolve-ExistingDirectory -Candidates $inboxCandidates

$scanRoot = if (-not [string]::IsNullOrWhiteSpace($resolvedInboxRoot)) {
    $resolvedInboxRoot
}
else {
    $resolvedDriveRoot
}

$warnings = [System.Collections.Generic.List[string]]::new()
$packages = [System.Collections.Generic.List[object]]::new()
$manifests = [System.Collections.Generic.List[object]]::new()

if ([string]::IsNullOrWhiteSpace($scanRoot)) {
    $warnings.Add("No local Google Drive folder was found. Pass -DriveRoot or -InboxRoot explicitly.") | Out-Null
}
else {
    $allFiles = @(Get-ChildItem -LiteralPath $scanRoot -File -Recurse -ErrorAction SilentlyContinue |
        Where-Object {
            $relative = Get-RelativePathSafe -BasePath $scanRoot -Path $_.FullName
            (($relative -split '[\\/]').Count - 1) -le $MaxDepth
        })

    foreach ($file in $allFiles) {
        $lower = $file.Name.ToLowerInvariant()
        if ($lower.EndsWith(".zip") -and $lower.Contains("riftreader")) {
            $packages.Add([pscustomobject][ordered]@{
                name = $file.Name
                path = $file.FullName
                relativePath = Get-RelativePathSafe -BasePath $scanRoot -Path $file.FullName
                lengthBytes = [int64]$file.Length
                createdTime = $file.CreationTimeUtc.ToString("o")
                modifiedTime = $file.LastWriteTimeUtc.ToString("o")
                sha256 = Get-Sha256Hex -Path $file.FullName
            }) | Out-Null
        }
        elseif (($lower.EndsWith(".json") -or $lower.EndsWith(".manifest")) -and ($lower.Contains("riftreader") -or $lower.Contains("manifest"))) {
            $manifestInfo = [ordered]@{
                name = $file.Name
                path = $file.FullName
                relativePath = Get-RelativePathSafe -BasePath $scanRoot -Path $file.FullName
                lengthBytes = [int64]$file.Length
                createdTime = $file.CreationTimeUtc.ToString("o")
                modifiedTime = $file.LastWriteTimeUtc.ToString("o")
                sha256 = Get-Sha256Hex -Path $file.FullName
                parsed = $false
                schemaVersion = $null
                packageKind = $null
                packageVersion = $null
                targetRepo = $null
                parseError = $null
            }

            try {
                $doc = Get-Content -LiteralPath $file.FullName -Raw | ConvertFrom-Json -Depth 80
                $manifestInfo.parsed = $true
                $manifestInfo.schemaVersion = $doc.schemaVersion
                $manifestInfo.packageKind = $doc.packageKind
                $manifestInfo.packageVersion = $doc.packageVersion
                $manifestInfo.targetRepo = $doc.targetRepo
            }
            catch {
                $manifestInfo.parseError = $_.Exception.Message
            }

            $manifests.Add([pscustomobject]$manifestInfo) | Out-Null
        }
    }
}

$summaryPath = Join-Path $OutputRoot ("drive-inbox-status-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".json")

$summary = [ordered]@{
    schemaVersion = 1
    mode = "riftreader-drive-inbox-status"
    status = if ([string]::IsNullOrWhiteSpace($scanRoot)) { "blocked-no-local-drive-root" } else { "completed" }
    ok = -not [string]::IsNullOrWhiteSpace($scanRoot)
    generatedAtUtc = (Get-Date).ToUniversalTime().ToString("o")
    repoRoot = $RepoRoot
    driveRoot = $resolvedDriveRoot
    inboxRoot = $resolvedInboxRoot
    scanRoot = $scanRoot
    maxDepth = $MaxDepth
    packageCount = $packages.Count
    manifestCount = $manifests.Count
    packages = @($packages.ToArray())
    manifests = @($manifests.ToArray())
    warnings = @($warnings.ToArray())
    artifacts = [ordered]@{
        outputRoot = $OutputRoot
        summaryJson = $summaryPath
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

$summary | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $summaryPath -Encoding UTF8

if ($Json.IsPresent) {
    Get-Content -LiteralPath $summaryPath -Raw
}
else {
    Write-Host "RiftReader Drive inbox status"
    Write-Host "Status    : $($summary.status)"
    Write-Host "Scan root : $scanRoot"
    Write-Host "Packages  : $($packages.Count)"
    Write-Host "Manifests : $($manifests.Count)"
    Write-Host "Summary   : $summaryPath"
    foreach ($warning in $warnings) {
        Write-Host "Warning   : $warning" -ForegroundColor Yellow
    }
}

# END_OF_SCRIPT_MARKER
