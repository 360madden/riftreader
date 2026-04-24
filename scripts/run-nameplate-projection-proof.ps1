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
    [int]$MaxHits = 24,
    [ValidateSet('hoverOnly', 'allHits', 'none')]
    [string]$TextPointerScanMode = 'allHits',
    [switch]$SkipPointerScan,
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

if ($MaxHits -le 0) {
    throw 'MaxHits must be greater than zero.'
}

if ($NonInteractive -and -not $PlanOnly) {
    throw 'Nameplate baseline/zoom proof requires operator confirmation for each visible state. Use -PlanOnly for dry runs; do not use -NonInteractive for live proof capture.'
}

$expectedStateRoles = @($States | ForEach-Object {
    if ($_ -match '^zoom') {
        'active'
    }
    elseif ($_ -match '^baseline') {
        'baseline'
    }
    else {
        throw "Nameplate proof state '$_' must match either '^baseline' or '^zoom' so the post-capture audit can verify the expected proof sequence."
    }
})

$helperArgs = @(
    '-NoProfile',
    '-ExecutionPolicy', 'Bypass',
    '-File', $captureScript,
    '-CandidateAddress', $CandidateAddress,
    '-CandidateLength', $CandidateLength.ToString([Globalization.CultureInfo]::InvariantCulture),
    '-TooltipText', $NameplateText,
    '-States', ($States -join ','),
    '-MaxHits', $MaxHits.ToString([Globalization.CultureInfo]::InvariantCulture),
    '-TextPointerScanMode', $TextPointerScanMode,
    '-CaptureScreenshot',
    '-RequireUsableScreenshot',
    '-ScreenshotAttempts', $ScreenshotAttempts.ToString([Globalization.CultureInfo]::InvariantCulture),
    '-AnalyzeAfterCapture',
    '-AnalyzerBaselineStateRegex', '^baseline',
    '-AnalyzerActiveStateRegex', '^zoom',
    '-AnalyzerBaselineLabel', 'baseline',
    '-AnalyzerActiveLabel', 'zoom',
    '-AnalyzerRequireVisualGate',
    '-AnalyzerExpectedStates', ($States -join ','),
    '-AnalyzerExpectedStateRoles', ($expectedStateRoles -join ','),
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
if ($SkipPointerScan) { $helperArgs += '-SkipPointerScan' }

& pwsh @helperArgs
exit $LASTEXITCODE
