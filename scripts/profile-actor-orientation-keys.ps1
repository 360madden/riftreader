[CmdletBinding()]
param(
    [string[]]$Keys = @('Left', 'Right', 'A', 'D', 'Q', 'E', 'Up', 'Down', 'Space'),
    [switch]$Json,
    [int]$HoldMilliseconds = 700,
    [int]$WaitMilliseconds = 250,
    [switch]$RefreshReaderBridge,
    [switch]$NoAhkFallback,
    [string]$ProcessName = 'rift_x64',
    [int]$ProcessId,
    [string]$TargetWindowHandle,
    [string]$OutputFile = (Join-Path $PSScriptRoot 'captures\actor-orientation-key-profile.json')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$stimulusScript = Join-Path $PSScriptRoot 'test-actor-orientation-stimulus.ps1'
$resolvedOutputFile = [System.IO.Path]::GetFullPath($OutputFile)

function Format-Nullable {
    param(
        $Value,
        [string]$Format = '0.000'
    )

    if ($null -eq $Value) {
        return 'n/a'
    }

    return ([double]$Value).ToString($Format, [System.Globalization.CultureInfo]::InvariantCulture)
}

function Classify-Response {
    param(
        [double]$YawDeltaDegrees,
        [double]$PitchDeltaDegrees,
        [double]$CoordDeltaMagnitude
    )

    $absYaw = [Math]::Abs($YawDeltaDegrees)
    $absPitch = [Math]::Abs($PitchDeltaDegrees)

    if ($absYaw -ge 15.0 -and $CoordDeltaMagnitude -le 0.25) {
        return 'actor-turn'
    }

    if ($absPitch -ge 5.0 -and $CoordDeltaMagnitude -le 0.25) {
        return 'actor-pitch'
    }

    if ($CoordDeltaMagnitude -gt 0.25 -and $absYaw -lt 10.0 -and $absPitch -lt 5.0) {
        return 'movement'
    }

    if ($absYaw -lt 10.0 -and $absPitch -lt 5.0 -and $CoordDeltaMagnitude -le 0.25) {
        return 'no-turn'
    }

    return 'mixed'
}

function Write-ProfileText {
    param($Document)

    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add('Actor orientation key profile')
    $lines.Add("Generated (UTC):             $($Document.GeneratedAtUtc)")
    $lines.Add("Output file:                 $($Document.OutputFile)")
    $lines.Add("Keys tested:                 $([string]::Join(', ', $Document.Keys))")
    $lines.Add("Refresh ReaderBridge:        $($Document.RefreshReaderBridge)")
    $lines.Add('Results:')

    foreach ($entry in $Document.Results) {
        if ($entry.Error) {
            $lines.Add("  - $($entry.Key): error | $($entry.Error)")
            continue
        }

        $lines.Add("  - $($entry.Key): $($entry.Classification) | yaw $(Format-Nullable $entry.YawDeltaDegrees '0.000') deg | pitch $(Format-Nullable $entry.PitchDeltaDegrees '0.000') deg | addon coord $(Format-Nullable $entry.AddonCoordDeltaMagnitude '0.000000') | live coord $(Format-Nullable $entry.PreferredLiveCoordDeltaMagnitude '0.000000') | addon confirmed $($entry.AddonCoordMovementConfirmed) | live confirmed $($entry.LiveCoordMovementConfirmed) | telemetry $($entry.TelemetryAlignmentStatus) | basis det $(Format-Nullable $entry.BasisDeterminantAfter '0.000000') | basis dup $(Format-Nullable $entry.BasisDuplicateMaxRowDeltaAfter '0.000000')")
    }

    return [string]::Join([Environment]::NewLine, $lines)
}

$results = New-Object System.Collections.Generic.List[object]

foreach ($key in $Keys) {
    try {
        $stimulusArguments = @{
            Key = $key
            HoldMilliseconds = $HoldMilliseconds
            WaitMilliseconds = $WaitMilliseconds
            Json = $true
            ProcessName = $ProcessName
        }
        if ($ProcessId -gt 0) {
            $stimulusArguments['ProcessId'] = $ProcessId
        }
        if (-not [string]::IsNullOrWhiteSpace($TargetWindowHandle)) {
            $stimulusArguments['TargetWindowHandle'] = $TargetWindowHandle
        }
        if ($RefreshReaderBridge) {
            $stimulusArguments['RefreshReaderBridge'] = $true
        }
        if ($NoAhkFallback) {
            $stimulusArguments['NoAhkFallback'] = $true
        }

        if ($RefreshReaderBridge) {
            if ($NoAhkFallback) {
                $jsonText = & $stimulusScript @stimulusArguments
            }
            else {
                $jsonText = & $stimulusScript @stimulusArguments
            }
        }
        elseif ($NoAhkFallback) {
            $jsonText = & $stimulusScript @stimulusArguments
        }
        else {
            $jsonText = & $stimulusScript @stimulusArguments
        }
        if ($LASTEXITCODE -ne 0) {
            throw "Stimulus helper failed for key '$key'."
        }

        $result = $jsonText | ConvertFrom-Json -Depth 60

        $yawDelta = if ($null -ne $result.Comparison.YawDeltaDegrees) { [double]$result.Comparison.YawDeltaDegrees } else { 0.0 }
        $pitchDelta = if ($null -ne $result.Comparison.PitchDeltaDegrees) { [double]$result.Comparison.PitchDeltaDegrees } else { 0.0 }
        $coordDelta = if ($null -ne $result.Comparison.AddonCoordDeltaMagnitude) { [double]$result.Comparison.AddonCoordDeltaMagnitude } elseif ($null -ne $result.Comparison.CoordDeltaMagnitude) { [double]$result.Comparison.CoordDeltaMagnitude } else { 0.0 }
        $preferredLiveCoordDelta = if ($null -ne $result.Comparison.PreferredLiveCoordDeltaMagnitude) { [double]$result.Comparison.PreferredLiveCoordDeltaMagnitude } else { 0.0 }
        $basisDeterminantAfter = $null
        $basisDuplicateDeltaAfter = $null
        $forwardYAfter = $null

        if ($result.After.ReaderOrientation.PreferredBasis) {
            if ($null -ne $result.After.ReaderOrientation.PreferredBasis.Determinant) {
                $basisDeterminantAfter = [double]$result.After.ReaderOrientation.PreferredBasis.Determinant
            }

            if ($null -ne $result.After.ReaderOrientation.PreferredBasis.Forward.Y) {
                $forwardYAfter = [double]$result.After.ReaderOrientation.PreferredBasis.Forward.Y
            }
        }

        if ($result.After.ReaderOrientation.DuplicateBasisAgreement -and $null -ne $result.After.ReaderOrientation.DuplicateBasisAgreement.MaxRowDeltaMagnitude) {
            $basisDuplicateDeltaAfter = [double]$result.After.ReaderOrientation.DuplicateBasisAgreement.MaxRowDeltaMagnitude
        }

        $results.Add([pscustomobject]@{
                Key = $key
                Classification = Classify-Response -YawDeltaDegrees $yawDelta -PitchDeltaDegrees $pitchDelta -CoordDeltaMagnitude $coordDelta
                YawDeltaDegrees = $yawDelta
                PitchDeltaDegrees = $pitchDelta
                CoordDeltaMagnitude = $coordDelta
                AddonCoordDeltaMagnitude = $coordDelta
                PreferredLiveCoordDeltaMagnitude = $preferredLiveCoordDelta
                AddonCoordMovementConfirmed = [bool]$result.Comparison.AddonCoordMovementConfirmed
                LiveCoordMovementConfirmed = [bool]$result.Comparison.LiveCoordMovementConfirmed
                AnyCoordMovementConfirmed = [bool]$result.Comparison.AnyCoordMovementConfirmed
                TelemetryAlignmentStatus = [string]$result.Comparison.TelemetryAlignmentStatus
                TelemetryBlocker = [bool]$result.Comparison.TelemetryBlocker
                BasisDeterminantAfter = $basisDeterminantAfter
                BasisDuplicateMaxRowDeltaAfter = $basisDuplicateDeltaAfter
                ForwardYAfter = $forwardYAfter
            })
    }
    catch {
        $results.Add([pscustomobject]@{
                Key = $key
                Error = $_.Exception.Message
            })
    }
}

$document = [pscustomobject]@{
    Mode = 'actor-orientation-key-profile'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
    OutputFile = $resolvedOutputFile
    ProcessName = $ProcessName
    ProcessId = if ($ProcessId -gt 0) { $ProcessId } else { $null }
    TargetWindowHandle = $TargetWindowHandle
    Keys = $Keys
    HoldMilliseconds = $HoldMilliseconds
    WaitMilliseconds = $WaitMilliseconds
    RefreshReaderBridge = [bool]$RefreshReaderBridge
    Results = $results
}

$outputDirectory = Split-Path -Path $resolvedOutputFile -Parent
if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

$jsonText = $document | ConvertTo-Json -Depth 60
[System.IO.File]::WriteAllText($resolvedOutputFile, $jsonText)

if ($Json) {
    Write-Output $jsonText
    exit 0
}

Write-Output (Write-ProfileText -Document $document)
