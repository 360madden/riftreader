# Version: 1.0.0
# TotalCharacters: 9766
# Purpose: Run the evidence-first RiftReader session workflow without letting one failed step abort the entire session.

[CmdletBinding()]
param(
    [string]$Label = 'evidence-first',
    [string[]]$Keys = @('Left', 'Right', 'A', 'D', 'Q', 'E', 'Up', 'Down', 'Space'),
    [string]$ProcessName = 'rift_x64',
    [int]$SampleCount = 20,
    [int]$IntervalMilliseconds = 500,
    [int]$TopSharedHubs = 4,
    [int]$HoldMilliseconds = 700,
    [int]$WaitMilliseconds = 250,
    [switch]$RefreshDiscoveryChain,
    [switch]$RefreshProjectorTrace,
    [switch]$RefreshReaderBridge,
    [switch]$RefreshOwnerComponents,
    [switch]$NoAhkFallback,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$captureScript = Join-Path $PSScriptRoot 'capture-actor-orientation.ps1'
$profileScript = Join-Path $PSScriptRoot 'profile-actor-orientation-keys.ps1'
$recordSessionScript = Join-Path $PSScriptRoot 'record-discovery-session.ps1'
$refreshReaderBridgeScript = Join-Path $PSScriptRoot 'refresh-readerbridge-export.ps1'
$sessionRoot = Join-Path $PSScriptRoot 'sessions'

function New-SessionSlug {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    $slug = ($Value.Trim().ToLowerInvariant() -replace '[^a-z0-9]+', '-').Trim('-')
    if ([string]::IsNullOrWhiteSpace($slug)) {
        return 'session'
    }

    return $slug
}

function Invoke-Step {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [scriptblock]$Action
    )

    try {
        $value = & $Action
        return [pscustomobject]@{
            Name = $Name
            Success = $true
            Value = $value
            Error = $null
        }
    }
    catch {
        return [pscustomobject]@{
            Name = $Name
            Success = $false
            Value = $null
            Error = $_.Exception.Message
        }
    }
}

function Convert-JsonTextToObject {
    param(
        [AllowNull()]
        [string]$JsonText
    )

    if ([string]::IsNullOrWhiteSpace($JsonText)) {
        return $null
    }

    if ($PSVersionTable.PSVersion.Major -ge 6) {
        return $JsonText | ConvertFrom-Json -Depth 80
    }

    return $JsonText | ConvertFrom-Json
}

function Get-ClassificationCounts {
    param(
        [AllowNull()]
        $ProfileDocument
    )

    $counts = [ordered]@{}
    if ($null -eq $ProfileDocument -or $null -eq $ProfileDocument.Results) {
        return $counts
    }

    foreach ($entry in @($ProfileDocument.Results)) {
        $classification = $null
        $errorText = $null

        if ($null -ne $entry -and $null -ne $entry.PSObject) {
            $classificationProperty = $entry.PSObject.Properties['Classification']
            if ($null -ne $classificationProperty) {
                $classification = [string]$classificationProperty.Value
            }

            $errorProperty = $entry.PSObject.Properties['Error']
            if ($null -ne $errorProperty) {
                $errorText = [string]$errorProperty.Value
            }
        }

        $name = if (-not [string]::IsNullOrWhiteSpace($classification)) {
            $classification
        }
        elseif (-not [string]::IsNullOrWhiteSpace($errorText)) {
            'error'
        }
        else {
            'unknown'
        }

        if (-not $counts.Contains($name)) {
            $counts[$name] = 0
        }

        $counts[$name]++
    }

    return $counts
}

$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$labelSlug = New-SessionSlug -Value $Label
$sessionId = '{0}-{1}' -f $timestamp, $labelSlug
$sessionDirectory = Join-Path $sessionRoot $sessionId
$outputDirectory = Join-Path $sessionDirectory 'evidence'
$summaryFile = Join-Path $outputDirectory 'evidence-first-summary.json'
$baselineCaptureFile = Join-Path $outputDirectory 'baseline-actor-orientation.json'
$baselinePreviousFile = Join-Path $outputDirectory 'baseline-actor-orientation.previous.json'
$keyProfileFile = Join-Path $outputDirectory 'actor-orientation-key-profile.json'

New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null

$warnings = New-Object System.Collections.Generic.List[string]
$steps = New-Object System.Collections.Generic.List[object]

if ($RefreshReaderBridge) {
    $refreshStep = Invoke-Step -Name 'refresh-readerbridge-export' -Action {
        $arguments = @{ NoReader = $true }
        if ($NoAhkFallback) {
            $arguments['NoAhkFallback'] = $true
        }

        & $refreshReaderBridgeScript @arguments | Out-Null
        return [pscustomobject]@{
            Refreshed = $true
        }
    }

    $steps.Add($refreshStep) | Out-Null
    if (-not $refreshStep.Success) {
        $warnings.Add("ReaderBridge refresh failed: $($refreshStep.Error)") | Out-Null
    }
}

$baselineStep = Invoke-Step -Name 'capture-baseline-actor-orientation' -Action {
    $arguments = @{
        Json = $true
        Label = ("baseline-{0}" -f $labelSlug)
        OutputFile = $baselineCaptureFile
        PreviousFile = $baselinePreviousFile
    }

    if ($RefreshOwnerComponents) {
        $arguments['RefreshOwnerComponents'] = $true
    }

    if ($RefreshReaderBridge) {
        $arguments['RefreshReaderBridge'] = $true
    }

    if ($NoAhkFallback) {
        $arguments['NoAhkFallback'] = $true
    }

    $jsonText = & $captureScript @arguments
    return (Convert-JsonTextToObject -JsonText $jsonText)
}
$steps.Add($baselineStep) | Out-Null
if (-not $baselineStep.Success) {
    $warnings.Add("Baseline actor-orientation capture failed: $($baselineStep.Error)") | Out-Null
}

$keyProfileStep = Invoke-Step -Name 'profile-actor-orientation-keys' -Action {
    $arguments = @{
        Json = $true
        Keys = $Keys
        HoldMilliseconds = $HoldMilliseconds
        WaitMilliseconds = $WaitMilliseconds
        OutputFile = $keyProfileFile
    }

    if ($RefreshReaderBridge) {
        $arguments['RefreshReaderBridge'] = $true
    }

    if ($NoAhkFallback) {
        $arguments['NoAhkFallback'] = $true
    }

    $jsonText = & $profileScript @arguments
    return (Convert-JsonTextToObject -JsonText $jsonText)
}
$steps.Add($keyProfileStep) | Out-Null
if (-not $keyProfileStep.Success) {
    $warnings.Add("Actor-orientation key profile failed: $($keyProfileStep.Error)") | Out-Null
}

$recordStep = Invoke-Step -Name 'record-discovery-session' -Action {
    $arguments = @{
        Json = $true
        Label = $Label
        ProcessName = $ProcessName
        SampleCount = $SampleCount
        IntervalMilliseconds = $IntervalMilliseconds
        TopSharedHubs = $TopSharedHubs
        SessionRoot = $sessionRoot
    }

    if ($RefreshDiscoveryChain) {
        $arguments['RefreshDiscoveryChain'] = $true
    }

    if ($RefreshProjectorTrace) {
        $arguments['RefreshProjectorTrace'] = $true
    }

    if ($RefreshReaderBridge) {
        $arguments['RefreshReaderBridge'] = $true
    }

    if ($NoAhkFallback) {
        $arguments['NoAhkFallback'] = $true
    }

    $jsonText = & $recordSessionScript @arguments
    return (Convert-JsonTextToObject -JsonText $jsonText)
}
$steps.Add($recordStep) | Out-Null
if (-not $recordStep.Success) {
    $warnings.Add("Discovery session packaging failed: $($recordStep.Error)") | Out-Null
}

$classificationCounts = Get-ClassificationCounts -ProfileDocument $keyProfileStep.Value

$summary = [pscustomobject]@{
    Mode = 'evidence-first-session'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
    Label = $Label
    SessionId = $sessionId
    SessionDirectory = $sessionDirectory
    EvidenceDirectory = $outputDirectory
    Inputs = [pscustomobject]@{
        Keys = $Keys
        ProcessName = $ProcessName
        SampleCount = $SampleCount
        IntervalMilliseconds = $IntervalMilliseconds
        TopSharedHubs = $TopSharedHubs
        HoldMilliseconds = $HoldMilliseconds
        WaitMilliseconds = $WaitMilliseconds
        RefreshDiscoveryChain = [bool]$RefreshDiscoveryChain
        RefreshProjectorTrace = [bool]$RefreshProjectorTrace
        RefreshReaderBridge = [bool]$RefreshReaderBridge
        RefreshOwnerComponents = [bool]$RefreshOwnerComponents
        NoAhkFallback = [bool]$NoAhkFallback
    }
    Files = [pscustomobject]@{
        SummaryFile = $summaryFile
        BaselineCaptureFile = $(if (Test-Path -LiteralPath $baselineCaptureFile) { $baselineCaptureFile } else { $null })
        KeyProfileFile = $(if (Test-Path -LiteralPath $keyProfileFile) { $keyProfileFile } else { $null })
    }
    BaselineCapture = $baselineStep.Value
    KeyProfile = $keyProfileStep.Value
    ClassificationCounts = $classificationCounts
    DiscoverySession = $recordStep.Value
    Steps = @(
        foreach ($step in $steps) {
            [pscustomobject]@{
                Name = $step.Name
                Success = [bool]$step.Success
                Error = $step.Error
            }
        }
    )
    Warnings = @($warnings | Select-Object -Unique)
}

$summaryJson = $summary | ConvertTo-Json -Depth 80
[System.IO.File]::WriteAllText($summaryFile, $summaryJson)

if ($Json) {
    Write-Output $summaryJson
    exit 0
}

Write-Host 'Evidence-first session complete.'
Write-Host ("Session directory:           {0}" -f $sessionDirectory)
Write-Host ("Evidence directory:          {0}" -f $outputDirectory)
Write-Host ("Summary file:                {0}" -f $summaryFile)
Write-Host ("Baseline capture:            {0}" -f $(if (Test-Path -LiteralPath $baselineCaptureFile) { $baselineCaptureFile } else { 'not written' }))
Write-Host ("Key profile:                 {0}" -f $(if (Test-Path -LiteralPath $keyProfileFile) { $keyProfileFile } else { 'not written' }))
Write-Host ("Discovery session packaged:  {0}" -f $(if ($recordStep.Success) { 'yes' } else { 'no' }))

if ($classificationCounts.Count -gt 0) {
    Write-Host ''
    Write-Host 'Key classifications:'
    foreach ($entry in $classificationCounts.GetEnumerator()) {
        Write-Host ("- {0}: {1}" -f $entry.Key, $entry.Value)
    }
}

if ($warnings.Count -gt 0) {
    Write-Host ''
    Write-Host 'Warnings:' -ForegroundColor Yellow
    foreach ($warning in $warnings | Select-Object -Unique) {
        Write-Host ("- {0}" -f $warning)
    }
}

# End of script


