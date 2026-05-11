# Version: riftreader-drive-intake-report-v0.1.0
# Total-Character-Count: 11379
# Purpose: Produce a non-mutating readiness report for RiftReader Drive inbox patch ZIP/manifest pairs. Discovery/report only: no patch apply, no Git mutation, no movement/input.

[CmdletBinding()]
param(
    [string]$DriveRoot,
    [string]$InboxRoot,
    [string]$OutputRoot,
    [string]$ExpectedTargetRepo = "360madden/riftreader",
    [int]$MaxDepth = 5,
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
    $OutputRoot = Join-Path $RepoRoot "scripts\captures\drive-intake-report"
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

$ResolvedInboxRoot = Resolve-Dir -Candidates @(
    $InboxRoot,
    $(if (-not [string]::IsNullOrWhiteSpace($ResolvedDriveRoot)) { Join-Path $ResolvedDriveRoot "RiftReader\inbox" } else { $null })
)

$warnings = [System.Collections.Generic.List[string]]::new()
$manifestReports = [System.Collections.Generic.List[object]]::new()
$packageFiles = [System.Collections.Generic.List[object]]::new()
$referencedPackages = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)

if ([string]::IsNullOrWhiteSpace($ResolvedInboxRoot)) {
    $warnings.Add("No local RiftReader Drive inbox root was found. Pass -DriveRoot or -InboxRoot explicitly.") | Out-Null
}

if (-not [string]::IsNullOrWhiteSpace($ResolvedInboxRoot)) {
    $allFiles = @(Get-ChildItem -LiteralPath $ResolvedInboxRoot -File -Recurse -ErrorAction SilentlyContinue |
        Where-Object {
            $relative = [System.IO.Path]::GetRelativePath($ResolvedInboxRoot, $_.FullName)
            (($relative -split '[\\/]').Count - 1) -le $MaxDepth
        })

    foreach ($zip in @($allFiles | Where-Object { $_.Name.ToLowerInvariant().EndsWith(".zip") })) {
        $packageFiles.Add([pscustomobject][ordered]@{
            name = $zip.Name
            path = $zip.FullName
            lengthBytes = [int64]$zip.Length
            sha256 = Get-Sha256Hex -Path $zip.FullName
            modifiedTimeUtc = $zip.LastWriteTimeUtc.ToString("o")
        }) | Out-Null
    }

    $manifestFiles = @($allFiles | Where-Object {
        $lower = $_.Name.ToLowerInvariant()
        $lower.EndsWith(".manifest.json") -or ($lower.EndsWith(".json") -and $lower.Contains("manifest"))
    })

    foreach ($manifest in $manifestFiles) {
        $errors = [System.Collections.Generic.List[string]]::new()
        $manifestWarnings = [System.Collections.Generic.List[string]]::new()
        $packagePath = $null
        $packageSha = $null
        $expectedSha = $null
        $packageStatus = "not-referenced"

        try {
            $doc = Get-Content -LiteralPath $manifest.FullName -Raw | ConvertFrom-Json -Depth 80
        } catch {
            $manifestReports.Add([pscustomobject][ordered]@{
                manifestPath = $manifest.FullName
                status = "invalid-json"
                ready = $false
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
        if (-not [string]::IsNullOrWhiteSpace($targetRepo) -and -not [string]::Equals($targetRepo, $ExpectedTargetRepo, [System.StringComparison]::OrdinalIgnoreCase)) { $errors.Add("targetRepo_mismatch:$targetRepo") | Out-Null }
        if ([string]::IsNullOrWhiteSpace($commitMessage)) { $manifestWarnings.Add("commitMessage_missing_or_empty") | Out-Null }

        foreach ($field in @("movementSentByApplier", "inputSentByApplier", "reloaduiSentByApplier", "screenshotKeySentByApplier")) {
            $value = Get-Prop $doc $field
            if ($null -eq $value) { $errors.Add("${field}_missing") | Out-Null }
            if ($null -ne $value -and [bool]$value) { $errors.Add("${field}_must_be_false") | Out-Null }
        }

        $noCe = Get-Prop $doc "noCheatEngine"
        if ($null -eq $noCe) { $errors.Add("noCheatEngine_missing") | Out-Null }
        if ($null -ne $noCe -and -not [bool]$noCe) { $errors.Add("noCheatEngine_must_be_true") | Out-Null }

        $packageFileValue = [string](Get-Prop $doc "packageFile")
        $expectedSha = [string](Get-Prop $doc "packageSha256")
        if (-not [string]::IsNullOrWhiteSpace($packageFileValue)) {
            $packagePath = Resolve-RelativeFile -BaseDirectory $manifest.DirectoryName -PathText $packageFileValue
            if (-not (Test-Path -LiteralPath $packagePath -PathType Leaf)) {
                $errors.Add("packageFile_missing:$packagePath") | Out-Null
                $packageStatus = "missing"
            } else {
                [void]$referencedPackages.Add($packagePath)
                $packageSha = Get-Sha256Hex -Path $packagePath
                if ([string]::IsNullOrWhiteSpace($expectedSha)) {
                    $manifestWarnings.Add("packageSha256_missing") | Out-Null
                    $packageStatus = "hash-computed-no-expected"
                }
                if (-not [string]::IsNullOrWhiteSpace($expectedSha) -and [string]::Equals($packageSha, $expectedSha, [System.StringComparison]::OrdinalIgnoreCase)) {
                    $packageStatus = "hash-match"
                }
                if (-not [string]::IsNullOrWhiteSpace($expectedSha) -and -not [string]::Equals($packageSha, $expectedSha, [System.StringComparison]::OrdinalIgnoreCase)) {
                    $errors.Add("packageSha256_mismatch") | Out-Null
                    $packageStatus = "hash-mismatch"
                }
            }
        } else {
            $manifestWarnings.Add("packageFile_missing") | Out-Null
        }

        $manifestReports.Add([pscustomobject][ordered]@{
            manifestPath = $manifest.FullName
            status = if ($errors.Count -eq 0) { "ready" } else { "not-ready" }
            ready = ($errors.Count -eq 0)
            schemaVersion = $schemaVersion
            packageKind = $packageKind
            packageVersion = $packageVersion
            targetRepo = $targetRepo
            commitMessage = $commitMessage
            packagePath = $packagePath
            packageStatus = $packageStatus
            packageSha256 = $packageSha
            expectedPackageSha256 = $expectedSha
            errors = @($errors.ToArray())
            warnings = @($manifestWarnings.ToArray())
        }) | Out-Null
    }
}

$orphanPackages = [System.Collections.Generic.List[object]]::new()
foreach ($pkg in @($packageFiles.ToArray())) {
    if (-not $referencedPackages.Contains([string]$pkg.path)) {
        $orphanPackages.Add($pkg) | Out-Null
    }
}

$readyCount = @($manifestReports.ToArray() | Where-Object { $_.ready }).Count
$notReadyCount = @($manifestReports.ToArray() | Where-Object { -not $_.ready }).Count
$summaryPath = Join-Path $OutputRoot ("drive-intake-report-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".json")

$summary = [ordered]@{
    schemaVersion = 1
    mode = "riftreader-drive-intake-report"
    status = if ([string]::IsNullOrWhiteSpace($ResolvedInboxRoot)) { "blocked-no-inbox-root" } elseif ($notReadyCount -gt 0) { "completed-not-ready-found" } else { "completed" }
    ok = (-not [string]::IsNullOrWhiteSpace($ResolvedInboxRoot))
    generatedAtUtc = (Get-Date).ToUniversalTime().ToString("o")
    repoRoot = $RepoRoot
    driveRoot = $ResolvedDriveRoot
    inboxRoot = $ResolvedInboxRoot
    expectedTargetRepo = $ExpectedTargetRepo
    packageCount = $packageFiles.Count
    manifestCount = $manifestReports.Count
    readyManifestCount = $readyCount
    notReadyManifestCount = $notReadyCount
    orphanPackageCount = $orphanPackages.Count
    manifests = @($manifestReports.ToArray())
    packages = @($packageFiles.ToArray())
    orphanPackages = @($orphanPackages.ToArray())
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
} else {
    Write-Host "RiftReader Drive intake report"
    Write-Host "Status     : $($summary.status)"
    Write-Host "Packages   : $($summary.packageCount)"
    Write-Host "Manifests  : $($summary.manifestCount)"
    Write-Host "Ready      : $readyCount"
    Write-Host "Not ready  : $notReadyCount"
    Write-Host "Orphans    : $($summary.orphanPackageCount)"
    Write-Host "Summary    : $summaryPath"
    foreach ($warning in $warnings) { Write-Host "Warning    : $warning" -ForegroundColor Yellow }
}

# END_OF_SCRIPT_MARKER
