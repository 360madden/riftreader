[CmdletBinding()]
param(
    [string]$TruthCsv,

    [string]$LiveCoordsFile,

    [string]$MemoryTimeseriesCsv,

    [string]$MemoryDirectory,

    [string]$BundleDirectory,

    [string]$ScoresFile,

    [string]$PromotionGateFile,

    [string]$FlattenedMemoryTimeseriesCsv,

    [string]$TruthSurfaceFile,

    [string]$SavedVariablesFreshnessFile,

    [string]$CandidateId,

    [string[]]$MovementSamples = @(),

    [string[]]$StationarySamples = @(),

    [int]$MinimumComparedSamples = 3,

    [double]$MovementEpsilon = 0.05,

    [double]$StrongDistanceTolerance = 0.75,

    [double]$StationaryDriftTolerance = 0.15,

    [double]$MinimumPromotionScore = 80.0,

    [int]$MaximumMissingSamples = 0,

    [double]$MaximumAbsoluteRmse = 0.75,

    [double]$MaximumDeltaRmse = 0.75,

    [double]$MaximumStationaryDrift = 0.15,

    [switch]$AllowPromotionFailure,

    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$schemaVersion = 1

$scoreScript = Join-Path $PSScriptRoot 'score-candidate-trajectories.ps1'
$gateScript = Join-Path $PSScriptRoot 'write-promotion-gate.ps1'

if (-not (Test-Path -LiteralPath $scoreScript)) {
    throw "Score script not found: $scoreScript"
}

if (-not (Test-Path -LiteralPath $gateScript)) {
    throw "Promotion gate script not found: $gateScript"
}

if ([string]::IsNullOrWhiteSpace($BundleDirectory)) {
    $BundleDirectory = if (-not [string]::IsNullOrWhiteSpace($TruthCsv)) {
        Split-Path -Path ([System.IO.Path]::GetFullPath($TruthCsv)) -Parent
    }
    elseif (-not [string]::IsNullOrWhiteSpace($LiveCoordsFile)) {
        Split-Path -Path ([System.IO.Path]::GetFullPath($LiveCoordsFile)) -Parent
    }
    elseif (-not [string]::IsNullOrWhiteSpace($MemoryDirectory)) {
        [System.IO.Path]::GetFullPath($MemoryDirectory)
    }
    else {
        Join-Path $PSScriptRoot 'captures'
    }
}

$resolvedBundleDirectory = [System.IO.Path]::GetFullPath($BundleDirectory)
New-Item -ItemType Directory -Path $resolvedBundleDirectory -Force | Out-Null

if ([string]::IsNullOrWhiteSpace($ScoresFile)) {
    $ScoresFile = Join-Path $resolvedBundleDirectory 'candidate-trajectory-scores.json'
}

if ([string]::IsNullOrWhiteSpace($PromotionGateFile)) {
    $PromotionGateFile = Join-Path $resolvedBundleDirectory 'promotion-gate.json'
}

if ([string]::IsNullOrWhiteSpace($FlattenedMemoryTimeseriesCsv) -and -not [string]::IsNullOrWhiteSpace($MemoryDirectory)) {
    $FlattenedMemoryTimeseriesCsv = Join-Path $resolvedBundleDirectory 'memory-timeseries.csv'
}

if ([string]::IsNullOrWhiteSpace($TruthSurfaceFile)) {
    $candidateTruthSurfaceFile = Join-Path $resolvedBundleDirectory 'truth-surface.json'
    if (Test-Path -LiteralPath $candidateTruthSurfaceFile) {
        $TruthSurfaceFile = $candidateTruthSurfaceFile
    }
}

if ([string]::IsNullOrWhiteSpace($SavedVariablesFreshnessFile)) {
    $candidateFreshnessFile = Join-Path $resolvedBundleDirectory 'savedvariables-freshness.json'
    if (Test-Path -LiteralPath $candidateFreshnessFile) {
        $SavedVariablesFreshnessFile = $candidateFreshnessFile
    }
}

function Invoke-NativeCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $nativePreferenceVariable = Get-Variable -Name PSNativeCommandUseErrorActionPreference -Scope 1 -ErrorAction SilentlyContinue
    $previousNativeCommandPreference = if ($null -ne $nativePreferenceVariable) { $nativePreferenceVariable.Value } else { $null }
    try {
        $ErrorActionPreference = 'Continue'
        if ($null -ne $nativePreferenceVariable) {
            Set-Variable -Name PSNativeCommandUseErrorActionPreference -Scope 1 -Value $false
        }

        $output = & pwsh @Arguments 2>&1
        return [pscustomobject]@{
            ExitCode = $LASTEXITCODE
            Output = ($output -join [Environment]::NewLine)
        }
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
        if ($null -ne $nativePreferenceVariable) {
            Set-Variable -Name PSNativeCommandUseErrorActionPreference -Scope 1 -Value $previousNativeCommandPreference
        }
    }
}

function ConvertTo-SampleIndexArgumentList {
    param(
        [string[]]$Values,

        [Parameter(Mandatory = $true)]
        [string]$ParameterName
    )

    $samples = [System.Collections.Generic.List[string]]::new()
    foreach ($value in @($Values)) {
        if ([string]::IsNullOrWhiteSpace($value)) {
            continue
        }

        foreach ($part in ([string]$value -split '[,\s;]+')) {
            if ([string]::IsNullOrWhiteSpace($part)) {
                continue
            }

            try {
                $sample = [int]::Parse($part, [System.Globalization.CultureInfo]::InvariantCulture)
                $samples.Add($sample.ToString([System.Globalization.CultureInfo]::InvariantCulture)) | Out-Null
            }
            catch {
                throw "$ParameterName contains a non-integer sample index: $part"
            }
        }
    }

    return $samples.ToArray()
}

$resolvedMovementSamples = @(ConvertTo-SampleIndexArgumentList -Values $MovementSamples -ParameterName 'MovementSamples')
$resolvedStationarySamples = @(ConvertTo-SampleIndexArgumentList -Values $StationarySamples -ParameterName 'StationarySamples')

$scoreArguments = @(
    '-NoLogo',
    '-NoProfile',
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    $scoreScript,
    '-OutputFile',
    $ScoresFile,
    '-MinimumComparedSamples',
    $MinimumComparedSamples.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '-MovementEpsilon',
    $MovementEpsilon.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '-StrongDistanceTolerance',
    $StrongDistanceTolerance.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '-StationaryDriftTolerance',
    $StationaryDriftTolerance.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '-Json'
)

if (-not [string]::IsNullOrWhiteSpace($TruthCsv)) {
    $scoreArguments += @('-TruthCsv', $TruthCsv)
}
if (-not [string]::IsNullOrWhiteSpace($LiveCoordsFile)) {
    $scoreArguments += @('-LiveCoordsFile', $LiveCoordsFile)
}
if (-not [string]::IsNullOrWhiteSpace($MemoryTimeseriesCsv)) {
    $scoreArguments += @('-MemoryTimeseriesCsv', $MemoryTimeseriesCsv)
}
if (-not [string]::IsNullOrWhiteSpace($MemoryDirectory)) {
    $scoreArguments += @('-MemoryDirectory', $MemoryDirectory)
}
if (-not [string]::IsNullOrWhiteSpace($FlattenedMemoryTimeseriesCsv)) {
    $scoreArguments += @('-FlattenedMemoryTimeseriesCsv', $FlattenedMemoryTimeseriesCsv)
}
if ($resolvedMovementSamples.Count -gt 0) {
    $scoreArguments += @('-MovementSamples', ($resolvedMovementSamples -join ','))
}
if ($resolvedStationarySamples.Count -gt 0) {
    $scoreArguments += @('-StationarySamples', ($resolvedStationarySamples -join ','))
}

$scoreRun = Invoke-NativeCommand -Arguments $scoreArguments
if ($scoreRun.ExitCode -ne 0) {
    $failure = [ordered]@{
        schemaVersion = $schemaVersion
        mode = 'candidate-trajectory-gate-run'
        status = 'score-failed'
        promotionAllowed = $false
        scoresFile = [System.IO.Path]::GetFullPath($ScoresFile)
        promotionGateFile = [System.IO.Path]::GetFullPath($PromotionGateFile)
        scoreExitCode = $scoreRun.ExitCode
        scoreOutput = $scoreRun.Output
    }

    if ($Json) {
        $failure | ConvertTo-Json -Depth 32
    }
    else {
        Write-Host 'Candidate trajectory scoring failed.' -ForegroundColor Red
        Write-Host $scoreRun.Output
    }

    exit 1
}

$scoreDocument = $scoreRun.Output | ConvertFrom-Json -Depth 80

$gateArguments = @(
    '-NoLogo',
    '-NoProfile',
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    $gateScript,
    '-CandidateScoresFile',
    $ScoresFile,
    '-OutputFile',
    $PromotionGateFile,
    '-MinimumScore',
    $MinimumPromotionScore.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '-MinimumComparedSamples',
    $MinimumComparedSamples.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '-MaximumMissingSamples',
    $MaximumMissingSamples.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '-MaximumAbsoluteRmse',
    $MaximumAbsoluteRmse.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '-MaximumDeltaRmse',
    $MaximumDeltaRmse.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '-MaximumStationaryDrift',
    $MaximumStationaryDrift.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '-Json'
)

if (-not [string]::IsNullOrWhiteSpace($CandidateId)) {
    $gateArguments += @('-CandidateId', $CandidateId)
}
if (-not [string]::IsNullOrWhiteSpace($TruthSurfaceFile)) {
    $gateArguments += @('-TruthSurfaceFile', $TruthSurfaceFile)
}
if (-not [string]::IsNullOrWhiteSpace($SavedVariablesFreshnessFile)) {
    $gateArguments += @('-SavedVariablesFreshnessFile', $SavedVariablesFreshnessFile)
}

$gateRun = Invoke-NativeCommand -Arguments $gateArguments
$gateDocument = $null
if (-not [string]::IsNullOrWhiteSpace($gateRun.Output)) {
    try {
        $gateDocument = $gateRun.Output | ConvertFrom-Json -Depth 80
    }
    catch {
        $gateDocument = $null
    }
}

$promotionAllowed = $gateRun.ExitCode -eq 0 -and $null -ne $gateDocument -and [bool]$gateDocument.promotionAllowed
$status = if ($promotionAllowed) { 'pass' } else { 'promotion-blocked' }

$result = [ordered]@{
    schemaVersion = $schemaVersion
    mode = 'candidate-trajectory-gate-run'
    generatedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    status = $status
    promotionAllowed = $promotionAllowed
    bundleDirectory = $resolvedBundleDirectory
    scoresFile = [System.IO.Path]::GetFullPath($ScoresFile)
    promotionGateFile = [System.IO.Path]::GetFullPath($PromotionGateFile)
    flattenedMemoryTimeseriesCsv = $(if (-not [string]::IsNullOrWhiteSpace($FlattenedMemoryTimeseriesCsv)) { [System.IO.Path]::GetFullPath($FlattenedMemoryTimeseriesCsv) } else { $null })
    scoreExitCode = $scoreRun.ExitCode
    gateExitCode = $gateRun.ExitCode
    bestCandidate = $scoreDocument.bestCandidate
    gateFailures = $(if ($null -ne $gateDocument) { @($gateDocument.failures) } else { @('Promotion gate output could not be parsed.') })
    gateWarnings = $(if ($null -ne $gateDocument) { @($gateDocument.warnings) } else { @() })
}

if ($Json) {
    $result | ConvertTo-Json -Depth 80
}
else {
    $color = if ($promotionAllowed) { 'Green' } else { 'Yellow' }
    Write-Host ("Candidate trajectory gate run: {0}" -f $status) -ForegroundColor $color
    Write-Host ("Scores:         {0}" -f ([System.IO.Path]::GetFullPath($ScoresFile)))
    Write-Host ("Promotion gate: {0}" -f ([System.IO.Path]::GetFullPath($PromotionGateFile)))
    if ($null -ne $scoreDocument.bestCandidate) {
        Write-Host ("Best candidate: {0} score={1} class={2}" -f $scoreDocument.bestCandidate.candidateId, $scoreDocument.bestCandidate.score, $scoreDocument.bestCandidate.classification)
    }
    if (-not $promotionAllowed -and $null -ne $gateDocument) {
        Write-Host 'Gate failures:' -ForegroundColor Yellow
        foreach ($failure in @($gateDocument.failures)) {
            Write-Host ("- {0}" -f $failure)
        }
    }
}

if (-not $promotionAllowed -and -not $AllowPromotionFailure) {
    exit 1
}
