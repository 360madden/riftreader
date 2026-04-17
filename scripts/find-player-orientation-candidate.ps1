[CmdletBinding()]
param(
    [switch]$Json,
    [string]$ProcessName = 'rift_x64',
    [int]$MaxHits = 8,
    [string]$OrientationCandidateLedgerFile,
    [string]$OutputFile = (Join-Path $PSScriptRoot 'captures\player-orientation-candidate-search.json')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$resolvedOutputFile = [System.IO.Path]::GetFullPath($OutputFile)

function Invoke-ReaderJson {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $output = & dotnet run --project $readerProject -- @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "Reader command failed (`$LASTEXITCODE=$exitCode): $($output -join [Environment]::NewLine)"
    }

    $jsonText = $output -join [Environment]::NewLine
    if ((Get-Command Microsoft.PowerShell.Utility\ConvertFrom-Json).Parameters.ContainsKey('Depth')) {
        return ($jsonText | Microsoft.PowerShell.Utility\ConvertFrom-Json -Depth 80)
    }

    return ($jsonText | Microsoft.PowerShell.Utility\ConvertFrom-Json)
}

$arguments = @(
    '--process-name', $ProcessName,
    '--find-player-orientation-candidate',
    '--max-hits', $MaxHits.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '--json')

if (-not [string]::IsNullOrWhiteSpace($OrientationCandidateLedgerFile)) {
    $arguments += @('--orientation-candidate-ledger-file', $OrientationCandidateLedgerFile)
}

$result = Invoke-ReaderJson -Arguments $arguments
$outputDirectory = Split-Path -Parent $resolvedOutputFile
if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

$jsonText = $result | ConvertTo-Json -Depth 80
Set-Content -LiteralPath $resolvedOutputFile -Value $jsonText -Encoding UTF8

if ($Json) {
    Write-Output $jsonText
    return
}

Write-Host "Player orientation candidate search"
Write-Host ("Process:                     {0}" -f $ProcessName)
Write-Host ("Candidate count:             {0}" -f $result.CandidateCount)
Write-Host ("Pointer-hop candidate count: {0}" -f $result.PointerHopCandidateCount)

$bestPointerHop = $result.BestPointerHopCandidate
$bestLocal = $result.BestCandidate

if ($null -ne $bestPointerHop) {
    Write-Host ("Best pointer-hop candidate:  {0} @ {1}" -f $bestPointerHop.Address, $bestPointerHop.BasisPrimaryForwardOffset)
    Write-Host ("Pointer-hop yaw/pitch (deg): {0} / {1}" -f `
        ($(if ($null -ne $bestPointerHop.PreferredEstimate.YawDegrees) { ([double]$bestPointerHop.PreferredEstimate.YawDegrees).ToString('0.000', [System.Globalization.CultureInfo]::InvariantCulture) } else { 'n/a' })), `
        ($(if ($null -ne $bestPointerHop.PreferredEstimate.PitchDegrees) { ([double]$bestPointerHop.PreferredEstimate.PitchDegrees).ToString('0.000', [System.Globalization.CultureInfo]::InvariantCulture) } else { 'n/a' })))
}
elseif ($null -ne $bestLocal) {
    Write-Host ("Best local candidate:        {0} @ {1}" -f $bestLocal.Address, $bestLocal.BasisPrimaryForwardOffset)
    Write-Host ("Local yaw/pitch (deg):       {0} / {1}" -f `
        ($(if ($null -ne $bestLocal.PreferredEstimate.YawDegrees) { ([double]$bestLocal.PreferredEstimate.YawDegrees).ToString('0.000', [System.Globalization.CultureInfo]::InvariantCulture) } else { 'n/a' })), `
        ($(if ($null -ne $bestLocal.PreferredEstimate.PitchDegrees) { ([double]$bestLocal.PreferredEstimate.PitchDegrees).ToString('0.000', [System.Globalization.CultureInfo]::InvariantCulture) } else { 'n/a' })))
}

foreach ($note in @($result.Notes)) {
    Write-Host ("- {0}" -f $note)
}
Write-Host ("Output file:                 {0}" -f $resolvedOutputFile)
