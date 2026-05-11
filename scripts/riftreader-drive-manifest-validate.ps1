# Version: riftreader-drive-manifest-validate-v0.1.0
# Total-Character-Count: 9528
# Purpose: Validate RiftReader Drive inbox manifest files and related package hashes. Discovery/validation only: no patch apply, no Git mutation, no movement/input.

[CmdletBinding()]
param(
    [string]$InboxRoot,
    [string[]]$ManifestPath,
    [string]$OutputRoot,
    [string]$ExpectedTargetRepo = "360madden/riftreader",
    [int]$MaxDepth = 4,
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

function Get-Prop {
    param($Object, [string]$Name)
    if ($null -eq $Object) { return $null }
    foreach ($p in @($Object.PSObject.Properties)) {
        if ([string]::Equals($p.Name, $Name, [System.StringComparison]::OrdinalIgnoreCase)) { return $p.Value }
    }
    return $null
}

function Resolve-RelativeFile {
    param([string]$BaseDirectory, [string]$PathText)
    if ([string]::IsNullOrWhiteSpace($PathText)) { return $null }
    $expanded = [Environment]::ExpandEnvironmentVariables($PathText)
    if ([System.IO.Path]::IsPathRooted($expanded)) { return [System.IO.Path]::GetFullPath($expanded) }
    return [System.IO.Path]::GetFullPath((Join-Path $BaseDirectory $expanded))
}

if ($MaxDepth -lt 0) { throw "MaxDepth must be zero or greater." }

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path $RepoRoot "scripts\captures\drive-manifest-validate"
}
$OutputRoot = [System.IO.Path]::GetFullPath($OutputRoot)
New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null

$ResolvedInboxRoot = Resolve-Dir -Candidates @(
    $InboxRoot,
    "$env:USERPROFILE\Google Drive\RiftReader\inbox",
    "$env:USERPROFILE\Google Drive\My Drive\RiftReader\inbox",
    "$env:USERPROFILE\My Drive\RiftReader\inbox",
    "G:\My Drive\RiftReader\inbox",
    "G:\Google Drive\RiftReader\inbox"
)

$Warnings = [System.Collections.Generic.List[string]]::new()
$ManifestFiles = [System.Collections.Generic.List[string]]::new()

if ($ManifestPath -and $ManifestPath.Count -gt 0) {
    foreach ($path in $ManifestPath) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "ManifestPath was not found: $path" }
        $ManifestFiles.Add((Resolve-Path -LiteralPath $path).Path) | Out-Null
    }
} elseif (-not [string]::IsNullOrWhiteSpace($ResolvedInboxRoot)) {
    $files = @(Get-ChildItem -LiteralPath $ResolvedInboxRoot -File -Recurse -ErrorAction SilentlyContinue |
        Where-Object {
            $relative = [System.IO.Path]::GetRelativePath($ResolvedInboxRoot, $_.FullName)
            $depth = (($relative -split '[\\/]').Count - 1)
            $lower = $_.Name.ToLowerInvariant()
            $depth -le $MaxDepth -and ($lower.EndsWith(".manifest.json") -or ($lower.EndsWith(".json") -and $lower.Contains("manifest")))
        })
    foreach ($file in $files) { $ManifestFiles.Add($file.FullName) | Out-Null }
} else {
    $Warnings.Add("No InboxRoot found and no ManifestPath supplied.") | Out-Null
}

$Results = [System.Collections.Generic.List[object]]::new()
foreach ($manifestFile in $ManifestFiles) {
    $errors = [System.Collections.Generic.List[string]]::new()
    $warn = [System.Collections.Generic.List[string]]::new()
    $packagePath = $null
    $packageSha = $null
    $expectedSha = $null
    $packageStatus = "not-checked"

    try { $doc = Get-Content -LiteralPath $manifestFile -Raw | ConvertFrom-Json -Depth 80 }
    catch {
        $Results.Add([pscustomobject][ordered]@{
            manifestPath = $manifestFile
            status = "invalid-json"
            ok = $false
            errors = @("json_parse_failed:$($_.Exception.Message)")
            warnings = @()
        }) | Out-Null
        continue
    }

    $schemaVersion = Get-Prop $doc "schemaVersion"
    $packageKind = [string](Get-Prop $doc "packageKind")
    $packageVersion = [string](Get-Prop $doc "packageVersion")
    $targetRepo = [string](Get-Prop $doc "targetRepo")
    $commitMessage = [string](Get-Prop $doc "commitMessage")

    if ($null -eq $schemaVersion -or [int]$schemaVersion -ne 1) { $errors.Add("schemaVersion_must_equal_1") | Out-Null }
    if ([string]::IsNullOrWhiteSpace($packageKind)) { $errors.Add("packageKind_missing") | Out-Null }
    if ([string]::IsNullOrWhiteSpace($packageVersion)) { $errors.Add("packageVersion_missing") | Out-Null }
    if ([string]::IsNullOrWhiteSpace($targetRepo)) { $errors.Add("targetRepo_missing") | Out-Null }
    elseif (-not [string]::Equals($targetRepo, $ExpectedTargetRepo, [System.StringComparison]::OrdinalIgnoreCase)) { $errors.Add("targetRepo_mismatch:$targetRepo") | Out-Null }
    if ([string]::IsNullOrWhiteSpace($commitMessage)) { $warn.Add("commitMessage_missing_or_empty") | Out-Null }

    foreach ($field in @("movementSentByApplier", "inputSentByApplier", "reloaduiSentByApplier", "screenshotKeySentByApplier")) {
        $value = Get-Prop $doc $field
        if ($null -eq $value) { $errors.Add("${field}_missing") | Out-Null }
        elseif ([bool]$value) { $errors.Add("${field}_must_be_false") | Out-Null }
    }

    $noCe = Get-Prop $doc "noCheatEngine"
    if ($null -eq $noCe) { $errors.Add("noCheatEngine_missing") | Out-Null }
    elseif (-not [bool]$noCe) { $errors.Add("noCheatEngine_must_be_true") | Out-Null }

    $manifestDir = Split-Path -Parent $manifestFile
    $packageFileValue = [string](Get-Prop $doc "packageFile")
    $expectedSha = [string](Get-Prop $doc "packageSha256")

    if (-not [string]::IsNullOrWhiteSpace($packageFileValue)) {
        $packagePath = Resolve-RelativeFile -BaseDirectory $manifestDir -PathText $packageFileValue
        if (-not (Test-Path -LiteralPath $packagePath -PathType Leaf)) {
            $errors.Add("packageFile_missing:$packagePath") | Out-Null
            $packageStatus = "missing"
        } else {
            $packageSha = Get-Sha256Hex -Path $packagePath
            if ([string]::IsNullOrWhiteSpace($expectedSha)) {
                $warn.Add("packageSha256_missing") | Out-Null
                $packageStatus = "hash-computed-no-expected"
            } elseif ([string]::Equals($packageSha, $expectedSha, [System.StringComparison]::OrdinalIgnoreCase)) {
                $packageStatus = "hash-match"
            } else {
                $errors.Add("packageSha256_mismatch") | Out-Null
                $packageStatus = "hash-mismatch"
            }
        }
    } else {
        $warn.Add("packageFile_missing") | Out-Null
    }

    $Results.Add([pscustomobject][ordered]@{
        manifestPath = $manifestFile
        status = if ($errors.Count -eq 0) { "valid" } else { "invalid" }
        ok = ($errors.Count -eq 0)
        schemaVersion = $schemaVersion
        packageKind = $packageKind
        packageVersion = $packageVersion
        targetRepo = $targetRepo
        packagePath = $packagePath
        packageStatus = $packageStatus
        packageSha256 = $packageSha
        expectedPackageSha256 = $expectedSha
        errors = @($errors.ToArray())
        warnings = @($warn.ToArray())
    }) | Out-Null
}

$validCount = @($Results.ToArray() | Where-Object { $_.ok }).Count
$invalidCount = @($Results.ToArray() | Where-Object { -not $_.ok }).Count
$summaryPath = Join-Path $OutputRoot ("drive-manifest-validate-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".json")

$summary = [ordered]@{
    schemaVersion = 1
    mode = "riftreader-drive-manifest-validate"
    status = if ($Warnings.Count -gt 0 -and $ManifestFiles.Count -eq 0) { "blocked-no-manifests" } elseif ($invalidCount -eq 0) { "completed-valid" } else { "completed-invalid-found" }
    ok = ($ManifestFiles.Count -gt 0 -and $invalidCount -eq 0)
    generatedAtUtc = (Get-Date).ToUniversalTime().ToString("o")
    repoRoot = $RepoRoot
    inboxRoot = $ResolvedInboxRoot
    expectedTargetRepo = $ExpectedTargetRepo
    manifestCount = $ManifestFiles.Count
    validCount = $validCount
    invalidCount = $invalidCount
    results = @($Results.ToArray())
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
    }
}
$summary | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $summaryPath -Encoding UTF8

if ($Json.IsPresent) {
    Get-Content -LiteralPath $summaryPath -Raw
} else {
    Write-Host "RiftReader Drive manifest validation"
    Write-Host "Status    : $($summary.status)"
    Write-Host "Manifests : $($summary.manifestCount)"
    Write-Host "Valid     : $validCount"
    Write-Host "Invalid   : $invalidCount"
    Write-Host "Summary   : $summaryPath"
    foreach ($warning in $Warnings) { Write-Host "Warning   : $warning" -ForegroundColor Yellow }
}

# END_OF_SCRIPT_MARKER
