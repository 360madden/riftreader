# Version: riftreader-drive-bootstrap-local-v0.1.0
# Total-Character-Count: 6778
# Purpose: Create/verify the local Google Drive-synced RiftReader folder tree and optionally create harmless test ZIP/manifest artifacts. Setup only: no patch apply, no Git mutation, no movement/input.

[CmdletBinding()]
param(
    [string]$DriveRoot,
    [string]$OutputRoot,
    [switch]$CreateTestArtifact,
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

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path $RepoRoot "scripts\captures\drive-bootstrap"
}
$OutputRoot = [System.IO.Path]::GetFullPath($OutputRoot)
New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null

$ResolvedDriveRoot = Resolve-Dir -Candidates @(
    $DriveRoot,
    "$env:USERPROFILE\Google Drive",
    "$env:USERPROFILE\Google Drive\My Drive",
    "$env:USERPROFILE\My Drive",
    "$env:USERPROFILE\OneDrive\Google Drive",
    "G:\My Drive",
    "G:\Google Drive"
)

$Warnings = [System.Collections.Generic.List[string]]::new()
$Created = [System.Collections.Generic.List[string]]::new()
$Existing = [System.Collections.Generic.List[string]]::new()
$TestArtifacts = [System.Collections.Generic.List[object]]::new()

if ([string]::IsNullOrWhiteSpace($ResolvedDriveRoot)) {
    $Warnings.Add("No local Google Drive folder found. Pass -DriveRoot explicitly.") | Out-Null
} else {
    $RiftRoot = Join-Path $ResolvedDriveRoot "RiftReader"
    $Folders = @(
        "", "inbox", "inbox\patches", "inbox\manifests", "inbox\handoffs",
        "outbox", "outbox\run-summaries", "outbox\logs", "outbox\screenshots",
        "archive", "archive\patches", "archive\runs", "status"
    )

    foreach ($rel in $Folders) {
        $folder = if ([string]::IsNullOrWhiteSpace($rel)) { $RiftRoot } else { Join-Path $RiftRoot $rel }
        if (Test-Path -LiteralPath $folder -PathType Container) {
            $Existing.Add($folder) | Out-Null
        } else {
            New-Item -ItemType Directory -Path $folder -Force | Out-Null
            $Created.Add($folder) | Out-Null
        }
    }

    if ($CreateTestArtifact.IsPresent) {
        $stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
        $patchDir = Join-Path $RiftRoot "inbox\patches"
        $manifestDir = Join-Path $RiftRoot "inbox\manifests"
        $tempDir = Join-Path $OutputRoot "test-artifact-$stamp"
        New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

        $readme = Join-Path $tempDir "README.txt"
        "Harmless RiftReader Drive inbox test artifact. CreatedUtc=$stamp. No repo mutation." | Set-Content -LiteralPath $readme -Encoding UTF8

        $zipName = "RiftReader_DriveInboxTestPatch_v0.0.0_$stamp.zip"
        $zipPath = Join-Path $patchDir $zipName
        if (Test-Path -LiteralPath $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
        Compress-Archive -LiteralPath $readme -DestinationPath $zipPath -Force

        $zipSha = Get-Sha256Hex -Path $zipPath
        $manifestName = "RiftReader_DriveInboxTestPatch_v0.0.0_$stamp.manifest.json"
        $manifestPath = Join-Path $manifestDir $manifestName

        [ordered]@{
            schemaVersion = 1
            packageKind = "riftreader-drive-inbox-test"
            packageVersion = "v0.0.0"
            createdUtc = (Get-Date).ToUniversalTime().ToString("o")
            targetRepo = "360madden/riftreader"
            targetFiles = @()
            commitMessage = "Drive inbox test artifact only"
            packageFile = "..\patches\$zipName"
            packageSha256 = $zipSha
            movementSentByApplier = $false
            inputSentByApplier = $false
            reloaduiSentByApplier = $false
            screenshotKeySentByApplier = $false
            noCheatEngine = $true
            payloadSha256 = [ordered]@{}
        } | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $manifestPath -Encoding UTF8

        $TestArtifacts.Add([pscustomobject][ordered]@{
            zipPath = $zipPath
            zipSha256 = $zipSha
            manifestPath = $manifestPath
        }) | Out-Null

        Remove-Item -LiteralPath $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

$summaryPath = Join-Path $OutputRoot ("drive-bootstrap-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".json")
$summary = [ordered]@{
    schemaVersion = 1
    mode = "riftreader-drive-bootstrap-local"
    status = if ([string]::IsNullOrWhiteSpace($ResolvedDriveRoot)) { "blocked-no-local-drive-root" } else { "completed" }
    ok = -not [string]::IsNullOrWhiteSpace($ResolvedDriveRoot)
    generatedAtUtc = (Get-Date).ToUniversalTime().ToString("o")
    repoRoot = $RepoRoot
    driveRoot = $ResolvedDriveRoot
    riftReaderDriveRoot = if ([string]::IsNullOrWhiteSpace($ResolvedDriveRoot)) { $null } else { Join-Path $ResolvedDriveRoot "RiftReader" }
    createdDirectoryCount = $Created.Count
    existingDirectoryCount = $Existing.Count
    createdDirectories = @($Created.ToArray())
    existingDirectories = @($Existing.ToArray())
    testArtifacts = @($TestArtifacts.ToArray())
    warnings = @($Warnings.ToArray())
    artifacts = [ordered]@{ outputRoot = $OutputRoot; summaryJson = $summaryPath }
    safety = [ordered]@{
        movementSent = $false
        inputSent = $false
        reloaduiSent = $false
        screenshotKeySent = $false
        gitMutation = $false
        patchApplied = $false
        noCheatEngine = $true
        localDriveFolderMutation = -not [string]::IsNullOrWhiteSpace($ResolvedDriveRoot)
    }
}
$summary | ConvertTo-Json -Depth 80 | Set-Content -LiteralPath $summaryPath -Encoding UTF8

if ($Json.IsPresent) {
    Get-Content -LiteralPath $summaryPath -Raw
} else {
    Write-Host "RiftReader Drive local bootstrap"
    Write-Host "Status     : $($summary.status)"
    Write-Host "Drive root : $ResolvedDriveRoot"
    Write-Host "Created    : $($Created.Count)"
    Write-Host "Existing   : $($Existing.Count)"
    Write-Host "Summary    : $summaryPath"
    foreach ($warning in $Warnings) { Write-Host "Warning    : $warning" -ForegroundColor Yellow }
}

# END_OF_SCRIPT_MARKER
