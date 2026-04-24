[CmdletBinding()]
param(
    [string]$ProcessName = 'rift_x64',
    [int]$ProcessId,
    [Parameter(Mandatory = $true)]
    [string]$CandidateAddress,
    [int]$CandidateLength = 1024,
    [Parameter(Mandatory = $true)]
    [string]$NameplateText,
    [string[]]$States = @('baseline1', 'zoom1', 'baseline2', 'zoom2'),
    [int]$ScreenshotAttempts = 3,
    [string]$RunLabel = 'nameplate-baseline-zoom',
    [string]$OutputRoot,
    [switch]$PlanOnly,
    [switch]$Json,
    [switch]$NonInteractive
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$captureScript = Join-Path $PSScriptRoot 'capture-tooltip-hover-diff.ps1'

if (-not (Test-Path -LiteralPath $captureScript -PathType Leaf)) {
    throw "Capture helper not found: $captureScript"
}

if ([string]::IsNullOrWhiteSpace($CandidateAddress)) {
    throw 'CandidateAddress is required.'
}

if ([string]::IsNullOrWhiteSpace($NameplateText)) {
    throw 'NameplateText is required.'
}

if ($ScreenshotAttempts -lt 1) {
    throw 'ScreenshotAttempts must be at least 1.'
}

$helperArgs = @(
    '-NoProfile',
    '-ExecutionPolicy', 'Bypass',
    '-File', $captureScript,
    '-CandidateAddress', $CandidateAddress,
    '-CandidateLength', $CandidateLength.ToString([Globalization.CultureInfo]::InvariantCulture),
    '-TooltipText', $NameplateText,
    '-States', ($States -join ','),
    '-TextPointerScanMode', 'allHits',
    '-CaptureScreenshot',
    '-RequireUsableScreenshot',
    '-ScreenshotAttempts', $ScreenshotAttempts.ToString([Globalization.CultureInfo]::InvariantCulture),
    '-AnalyzeAfterCapture',
    '-AnalyzerBaselineStateRegex', '^baseline',
    '-AnalyzerActiveStateRegex', '^zoom',
    '-AnalyzerBaselineLabel', 'baseline',
    '-AnalyzerActiveLabel', 'zoom',
    '-AnalyzerRequireVisualGate',
    '-RunLabel', $RunLabel
)

if ($PSBoundParameters.ContainsKey('ProcessId')) {
    $helperArgs += @('-ProcessId', $ProcessId.ToString([Globalization.CultureInfo]::InvariantCulture))
}
else {
    $helperArgs += @('-ProcessName', $ProcessName)
}

if (-not [string]::IsNullOrWhiteSpace($OutputRoot)) {
    $helperArgs += @('-OutputRoot', $OutputRoot)
}

if ($PlanOnly) { $helperArgs += '-PlanOnly' }
if ($Json) { $helperArgs += '-Json' }
if ($NonInteractive) { $helperArgs += '-NonInteractive' }

& pwsh @helperArgs
exit $LASTEXITCODE
