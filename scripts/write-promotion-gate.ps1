[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$CandidateScoresFile,

    [string]$OutputFile,

    [string]$CandidateId,

    [string]$TruthSurfaceFile,

    [string]$SavedVariablesFreshnessFile,

    [double]$MinimumScore = 80.0,

    [int]$MinimumComparedSamples = 3,

    [int]$MaximumMissingSamples = 0,

    [double]$MaximumAbsoluteRmse = 0.75,

    [double]$MaximumDeltaRmse = 0.75,

    [double]$MaximumStationaryDrift = 0.15,

    [switch]$AllowFailureExitZero,

    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$schemaVersion = 1

function Write-Utf8TextAtomic {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [string]$Content
    )

    $directory = Split-Path -Path $Path -Parent
    if (-not [string]::IsNullOrWhiteSpace($directory)) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }

    $tempPath = '{0}.{1}.tmp' -f $Path, ([Guid]::NewGuid().ToString('N'))
    try {
        [System.IO.File]::WriteAllText($tempPath, $Content, [System.Text.UTF8Encoding]::new($false))
        Move-Item -LiteralPath $tempPath -Destination $Path -Force
    }
    finally {
        if (Test-Path -LiteralPath $tempPath) {
            Remove-Item -LiteralPath $tempPath -Force
        }
    }
}

function Get-PropertyValue {
    param(
        [object]$InputObject,
        [Parameter(Mandatory = $true)]
        [string[]]$Names
    )

    if ($null -eq $InputObject) {
        return $null
    }

    foreach ($name in $Names) {
        if ($InputObject -is [System.Collections.IDictionary]) {
            if ($InputObject.Contains($name)) {
                return $InputObject[$name]
            }
        }
        else {
            $property = $InputObject.PSObject.Properties[$name]
            if ($null -ne $property) {
                return $property.Value
            }
        }
    }

    return $null
}

function ConvertTo-DoubleOrNull {
    param([object]$Value)

    if ($null -eq $Value) {
        return $null
    }

    $text = [string]$Value
    if ([string]::IsNullOrWhiteSpace($text)) {
        return $null
    }

    try {
        $number = [double]::Parse($text, [System.Globalization.CultureInfo]::InvariantCulture)
        if ([double]::IsNaN($number) -or [double]::IsInfinity($number)) {
            return $null
        }

        return $number
    }
    catch {
        return $null
    }
}

function ConvertTo-IntOrNull {
    param([object]$Value)

    if ($null -eq $Value) {
        return $null
    }

    $text = [string]$Value
    if ([string]::IsNullOrWhiteSpace($text)) {
        return $null
    }

    try {
        return [int]::Parse($text, [System.Globalization.CultureInfo]::InvariantCulture)
    }
    catch {
        return $null
    }
}

function Add-Check {
    param(
        [System.Collections.Generic.List[object]]$Checks,

        [Parameter(Mandatory = $true)]
        [string]$Name,

        [Parameter(Mandatory = $true)]
        [bool]$Passed,

        [Parameter(Mandatory = $true)]
        [string]$Message,

        [System.Collections.Generic.List[string]]$Failures,

        [System.Collections.Generic.List[string]]$Warnings,

        [switch]$WarningOnly
    )

    $status = if ($Passed) { 'pass' } elseif ($WarningOnly) { 'warning' } else { 'fail' }
    $Checks.Add([ordered]@{
            name = $Name
            status = $status
            message = $Message
        }) | Out-Null

    if (-not $Passed) {
        if ($WarningOnly) {
            $Warnings.Add($Message) | Out-Null
        }
        else {
            $Failures.Add($Message) | Out-Null
        }
    }
}

function Find-Candidate {
    param(
        [Parameter(Mandatory = $true)]
        $ScoresDocument,

        [string]$RequestedCandidateId
    )

    if (-not [string]::IsNullOrWhiteSpace($RequestedCandidateId)) {
        foreach ($candidate in @($ScoresDocument.candidates)) {
            if ([string]$candidate.candidateId -eq $RequestedCandidateId -or [string]$candidate.addressHex -eq $RequestedCandidateId) {
                return $candidate
            }
        }

        return $null
    }

    return $ScoresDocument.bestCandidate
}

$resolvedCandidateScoresFile = [System.IO.Path]::GetFullPath($CandidateScoresFile)
if (-not (Test-Path -LiteralPath $resolvedCandidateScoresFile)) {
    throw "Candidate scores file not found: $resolvedCandidateScoresFile"
}

if ([string]::IsNullOrWhiteSpace($OutputFile)) {
    $OutputFile = Join-Path (Split-Path -Path $resolvedCandidateScoresFile -Parent) 'promotion-gate.json'
}

$resolvedOutputFile = [System.IO.Path]::GetFullPath($OutputFile)
$scoresDocument = Get-Content -LiteralPath $resolvedCandidateScoresFile -Raw | ConvertFrom-Json -Depth 80
$candidate = Find-Candidate -ScoresDocument $scoresDocument -RequestedCandidateId $CandidateId

$failures = [System.Collections.Generic.List[string]]::new()
$warnings = [System.Collections.Generic.List[string]]::new()
$checks = [System.Collections.Generic.List[object]]::new()

Add-Check -Checks $checks -Name 'scores-status' -Passed ([string]$scoresDocument.status -eq 'complete') -Message "Candidate scores status must be complete; actual=$($scoresDocument.status)." -Failures $failures -Warnings $warnings
Add-Check -Checks $checks -Name 'scores-promotion-ready' -Passed ([bool]$scoresDocument.promotionReady -eq $true) -Message 'Candidate scores document must have promotionReady=true.' -Failures $failures -Warnings $warnings

if ($null -eq $candidate) {
    Add-Check -Checks $checks -Name 'candidate-present' -Passed $false -Message "Requested candidate was not found: $CandidateId" -Failures $failures -Warnings $warnings
}
else {
    Add-Check -Checks $checks -Name 'candidate-present' -Passed $true -Message "Selected candidate: $($candidate.candidateId)" -Failures $failures -Warnings $warnings

    $classification = [string](Get-PropertyValue -InputObject $candidate -Names @('classification'))
    $score = ConvertTo-DoubleOrNull (Get-PropertyValue -InputObject $candidate -Names @('score'))
    $comparedSampleCount = ConvertTo-IntOrNull (Get-PropertyValue -InputObject $candidate -Names @('comparedSampleCount'))
    $missingSampleCount = ConvertTo-IntOrNull (Get-PropertyValue -InputObject $candidate -Names @('missingSampleCount'))
    $absoluteRmse = ConvertTo-DoubleOrNull (Get-PropertyValue -InputObject $candidate -Names @('absoluteRmse'))
    $deltaRmse = ConvertTo-DoubleOrNull (Get-PropertyValue -InputObject $candidate -Names @('deltaRmse'))
    $stationaryDriftMax = ConvertTo-DoubleOrNull (Get-PropertyValue -InputObject $candidate -Names @('stationaryDriftMax'))

    Add-Check -Checks $checks -Name 'candidate-classification' -Passed ($classification -eq 'trajectory-match') -Message "Selected candidate classification must be trajectory-match; actual=$classification." -Failures $failures -Warnings $warnings
    Add-Check -Checks $checks -Name 'candidate-score' -Passed ($null -ne $score -and $score -ge $MinimumScore) -Message "Selected candidate score must be >= $MinimumScore; actual=$score." -Failures $failures -Warnings $warnings
    Add-Check -Checks $checks -Name 'candidate-compared-samples' -Passed ($null -ne $comparedSampleCount -and $comparedSampleCount -ge $MinimumComparedSamples) -Message "Compared sample count must be >= $MinimumComparedSamples; actual=$comparedSampleCount." -Failures $failures -Warnings $warnings
    Add-Check -Checks $checks -Name 'candidate-missing-samples' -Passed ($null -ne $missingSampleCount -and $missingSampleCount -le $MaximumMissingSamples) -Message "Missing sample count must be <= $MaximumMissingSamples; actual=$missingSampleCount." -Failures $failures -Warnings $warnings
    Add-Check -Checks $checks -Name 'candidate-absolute-rmse' -Passed ($null -ne $absoluteRmse -and $absoluteRmse -le $MaximumAbsoluteRmse) -Message "Absolute RMSE must be <= $MaximumAbsoluteRmse; actual=$absoluteRmse." -Failures $failures -Warnings $warnings
    Add-Check -Checks $checks -Name 'candidate-delta-rmse' -Passed ($null -ne $deltaRmse -and $deltaRmse -le $MaximumDeltaRmse) -Message "Delta RMSE must be <= $MaximumDeltaRmse; actual=$deltaRmse." -Failures $failures -Warnings $warnings
    Add-Check -Checks $checks -Name 'candidate-stationary-drift' -Passed ($null -ne $stationaryDriftMax -and $stationaryDriftMax -le $MaximumStationaryDrift) -Message "Stationary drift max must be <= $MaximumStationaryDrift; actual=$stationaryDriftMax." -Failures $failures -Warnings $warnings
}

$truthSurfaceDocument = $null
if (-not [string]::IsNullOrWhiteSpace($TruthSurfaceFile)) {
    $resolvedTruthSurfaceFile = [System.IO.Path]::GetFullPath($TruthSurfaceFile)
    if (Test-Path -LiteralPath $resolvedTruthSurfaceFile) {
        $truthSurfaceDocument = Get-Content -LiteralPath $resolvedTruthSurfaceFile -Raw | ConvertFrom-Json -Depth 64
        $truthSurface = [string](Get-PropertyValue -InputObject $truthSurfaceDocument -Names @('authoritativeTruthSurface', 'truthSurface'))
        Add-Check -Checks $checks -Name 'truth-surface-not-savedvariables-live' -Passed ($truthSurface -ne 'savedvariables-live') -Message "Authoritative truth surface must not be savedvariables-live; actual=$truthSurface." -Failures $failures -Warnings $warnings
    }
    else {
        Add-Check -Checks $checks -Name 'truth-surface-file-present' -Passed $false -Message "Truth surface file not found: $resolvedTruthSurfaceFile" -Failures $failures -Warnings $warnings
    }
}
else {
    Add-Check -Checks $checks -Name 'truth-surface-file-present' -Passed $false -Message 'No truth-surface file was provided; gate relies on candidate score evidence only.' -Failures $failures -Warnings $warnings -WarningOnly
}

if (-not [string]::IsNullOrWhiteSpace($SavedVariablesFreshnessFile)) {
    $resolvedSavedVariablesFreshnessFile = [System.IO.Path]::GetFullPath($SavedVariablesFreshnessFile)
    if (Test-Path -LiteralPath $resolvedSavedVariablesFreshnessFile) {
        $savedVariablesFreshnessDocument = Get-Content -LiteralPath $resolvedSavedVariablesFreshnessFile -Raw | ConvertFrom-Json -Depth 64
        $usableAsLiveTruth = Get-PropertyValue -InputObject $savedVariablesFreshnessDocument -Names @('usableAsLiveTruth', 'savedVariablesUsableAsLiveTruth')
        $freshnessClassification = [string](Get-PropertyValue -InputObject $savedVariablesFreshnessDocument -Names @('freshnessClassification'))
        Add-Check -Checks $checks -Name 'savedvariables-not-live-truth' -Passed ($usableAsLiveTruth -ne $true) -Message "SavedVariables freshness must not mark usableAsLiveTruth=true; freshness=$freshnessClassification." -Failures $failures -Warnings $warnings
    }
    else {
        Add-Check -Checks $checks -Name 'savedvariables-freshness-file-present' -Passed $false -Message "SavedVariables freshness file not found: $resolvedSavedVariablesFreshnessFile" -Failures $failures -Warnings $warnings
    }
}

$promotionAllowed = $failures.Count -eq 0
$status = if ($promotionAllowed) { 'pass' } else { 'fail' }

$result = [ordered]@{
    schemaVersion = $schemaVersion
    mode = 'promotion-gate'
    generatedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    status = $status
    promotionAllowed = $promotionAllowed
    candidateScoresFile = $resolvedCandidateScoresFile
    outputFile = $resolvedOutputFile
    selectedCandidateId = $(if ($null -ne $candidate) { [string]$candidate.candidateId } else { $CandidateId })
    selectedCandidate = $candidate
    thresholds = [ordered]@{
        minimumScore = $MinimumScore
        minimumComparedSamples = $MinimumComparedSamples
        maximumMissingSamples = $MaximumMissingSamples
        maximumAbsoluteRmse = $MaximumAbsoluteRmse
        maximumDeltaRmse = $MaximumDeltaRmse
        maximumStationaryDrift = $MaximumStationaryDrift
    }
    checks = $checks.ToArray()
    failures = $failures.ToArray()
    warnings = $warnings.ToArray()
    notes = @(
        'This gate only permits promotion of trajectory-match candidates with strong score and error metrics.',
        'Static-cache, stale, wrong-origin, and stationary-tail-drift candidates must remain candidate/negative evidence.'
    )
}

Write-Utf8TextAtomic -Path $resolvedOutputFile -Content ($result | ConvertTo-Json -Depth 64)

if ($Json) {
    $result | ConvertTo-Json -Depth 64
}
else {
    $color = if ($promotionAllowed) { 'Green' } else { 'Red' }
    Write-Host ("Promotion gate: {0}" -f $status) -ForegroundColor $color
    Write-Host ("Output: {0}" -f $resolvedOutputFile)
    if ($failures.Count -gt 0) {
        Write-Host 'Failures:' -ForegroundColor Red
        foreach ($failure in $failures) {
            Write-Host ("- {0}" -f $failure)
        }
    }
    if ($warnings.Count -gt 0) {
        Write-Host 'Warnings:' -ForegroundColor Yellow
        foreach ($warning in $warnings) {
            Write-Host ("- {0}" -f $warning)
        }
    }
}

if (-not $promotionAllowed -and -not $AllowFailureExitZero) {
    exit 1
}
