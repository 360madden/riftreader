# Version: 1.0.0
# TotalCharacters: 9257
# Purpose: Capture and package a promising actor-orientation lead with before/after stimulus evidence plus a targeted discovery session.

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Key,
    [string]$Label,
    [string]$ProcessName = 'rift_x64',
    [int]$HoldMilliseconds = 700,
    [int]$WaitMilliseconds = 250,
    [int]$SampleCount = 40,
    [int]$IntervalMilliseconds = 250,
    [int]$TopSharedHubs = 4,
    [switch]$RefreshReaderBridge,
    [switch]$RefreshOwnerComponents,
    [switch]$RefreshDiscoveryChain,
    [switch]$RefreshProjectorTrace,
    [switch]$NoAhkFallback,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$captureScript = Join-Path $PSScriptRoot 'capture-actor-orientation.ps1'
$stimulusScript = Join-Path $PSScriptRoot 'test-actor-orientation-stimulus.ps1'
$recordSessionScript = Join-Path $PSScriptRoot 'record-discovery-session.ps1'
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

$effectiveLabel = if ([string]::IsNullOrWhiteSpace($Label)) {
    'lead-{0}' -f (New-SessionSlug -Value $Key)
}
else {
    $Label
}

$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$sessionId = '{0}-{1}' -f $timestamp, (New-SessionSlug -Value $effectiveLabel)
$sessionDirectory = Join-Path $sessionRoot $sessionId
$outputDirectory = Join-Path $sessionDirectory 'lead'
$summaryFile = Join-Path $outputDirectory 'promising-orientation-lead.json'
$refreshCaptureFile = Join-Path $outputDirectory 'owner-refresh-orientation.json'
$refreshPreviousFile = Join-Path $outputDirectory 'owner-refresh-orientation.previous.json'
$stimulusFile = Join-Path $outputDirectory 'orientation-stimulus.json'

New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null

$warnings = New-Object System.Collections.Generic.List[string]
$steps = New-Object System.Collections.Generic.List[object]

if ($RefreshOwnerComponents) {
    $refreshOwnerStep = Invoke-Step -Name 'refresh-owner-components' -Action {
        $arguments = @{
            Json = $true
            Label = ("owner-refresh-{0}" -f $effectiveLabel)
            OutputFile = $refreshCaptureFile
            PreviousFile = $refreshPreviousFile
            RefreshOwnerComponents = $true
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
    $steps.Add($refreshOwnerStep) | Out-Null
    if (-not $refreshOwnerStep.Success) {
        $warnings.Add("Owner-component refresh capture failed: $($refreshOwnerStep.Error)") | Out-Null
    }
}

$stimulusStep = Invoke-Step -Name 'test-actor-orientation-stimulus' -Action {
    $arguments = @{
        Key = $Key
        Json = $true
        Label = $effectiveLabel
        HoldMilliseconds = $HoldMilliseconds
        WaitMilliseconds = $WaitMilliseconds
    }

    if ($RefreshReaderBridge) {
        $arguments['RefreshReaderBridge'] = $true
    }

    if ($NoAhkFallback) {
        $arguments['NoAhkFallback'] = $true
    }

    $jsonText = & $stimulusScript @arguments
    $document = Convert-JsonTextToObject -JsonText $jsonText
    if ($null -ne $document) {
        [System.IO.File]::WriteAllText($stimulusFile, ($document | ConvertTo-Json -Depth 80))
    }

    return $document
}
$steps.Add($stimulusStep) | Out-Null
if (-not $stimulusStep.Success) {
    $warnings.Add("Orientation stimulus failed: $($stimulusStep.Error)") | Out-Null
}

$sessionLabel = '{0}-session' -f $effectiveLabel
$recordStep = Invoke-Step -Name 'record-discovery-session' -Action {
    $arguments = @{
        Json = $true
        Label = $sessionLabel
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
    $warnings.Add("Targeted discovery session failed: $($recordStep.Error)") | Out-Null
}

$classification = $null
if ($stimulusStep.Success -and $null -ne $stimulusStep.Value) {
    $comparison = $stimulusStep.Value.Comparison
    $coordDelta = if ($null -ne $comparison.CoordDeltaMagnitude) { [double]$comparison.CoordDeltaMagnitude } else { 0.0 }
    $yawDelta = if ($null -ne $comparison.YawDeltaDegrees) { [Math]::Abs([double]$comparison.YawDeltaDegrees) } else { 0.0 }
    $pitchDelta = if ($null -ne $comparison.PitchDeltaDegrees) { [Math]::Abs([double]$comparison.PitchDeltaDegrees) } else { 0.0 }

    if ($yawDelta -ge 15.0 -and $coordDelta -le 0.25) {
        $classification = 'actor-turn'
    }
    elseif ($pitchDelta -ge 5.0 -and $coordDelta -le 0.25) {
        $classification = 'actor-pitch'
    }
    elseif ($coordDelta -gt 0.25 -and $yawDelta -lt 10.0 -and $pitchDelta -lt 5.0) {
        $classification = 'movement'
    }
    elseif ($yawDelta -lt 10.0 -and $pitchDelta -lt 5.0 -and $coordDelta -le 0.25) {
        $classification = 'no-turn'
    }
    else {
        $classification = 'mixed'
    }
}

$summary = [pscustomobject]@{
    Mode = 'promising-orientation-lead'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
    Key = $Key
    Label = $effectiveLabel
    SessionId = $sessionId
    SessionDirectory = $sessionDirectory
    LeadDirectory = $outputDirectory
    Inputs = [pscustomobject]@{
        ProcessName = $ProcessName
        HoldMilliseconds = $HoldMilliseconds
        WaitMilliseconds = $WaitMilliseconds
        SampleCount = $SampleCount
        IntervalMilliseconds = $IntervalMilliseconds
        TopSharedHubs = $TopSharedHubs
        RefreshReaderBridge = [bool]$RefreshReaderBridge
        RefreshOwnerComponents = [bool]$RefreshOwnerComponents
        RefreshDiscoveryChain = [bool]$RefreshDiscoveryChain
        RefreshProjectorTrace = [bool]$RefreshProjectorTrace
        NoAhkFallback = [bool]$NoAhkFallback
    }
    Files = [pscustomobject]@{
        SummaryFile = $summaryFile
        RefreshCaptureFile = $(if (Test-Path -LiteralPath $refreshCaptureFile) { $refreshCaptureFile } else { $null })
        StimulusFile = $(if (Test-Path -LiteralPath $stimulusFile) { $stimulusFile } else { $null })
    }
    Stimulus = $stimulusStep.Value
    LeadClassification = $classification
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

Write-Host 'Promising lead capture complete.'
Write-Host ("Session directory:           {0}" -f $sessionDirectory)
Write-Host ("Lead directory:              {0}" -f $outputDirectory)
Write-Host ("Summary file:                {0}" -f $summaryFile)
Write-Host ("Stimulus classification:     {0}" -f $(if ($classification) { $classification } else { 'unknown' }))
Write-Host ("Stimulus captured:           {0}" -f $(if ($stimulusStep.Success) { 'yes' } else { 'no' }))
Write-Host ("Discovery session packaged:  {0}" -f $(if ($recordStep.Success) { 'yes' } else { 'no' }))

if ($warnings.Count -gt 0) {
    Write-Host ''
    Write-Host 'Warnings:' -ForegroundColor Yellow
    foreach ($warning in $warnings | Select-Object -Unique) {
        Write-Host ("- {0}" -f $warning)
    }
}

# End of script

