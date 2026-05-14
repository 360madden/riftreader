[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Assert-Equal {
    param(
        [Parameter(Mandatory = $true)]
        $Actual,

        [Parameter(Mandatory = $true)]
        $Expected,

        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    if ($Actual -ne $Expected) {
        throw "$Message Expected '$Expected', got '$Actual'."
    }
}

function Assert-True {
    param(
        [Parameter(Mandatory = $true)]
        [bool]$Condition,

        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    if (-not $Condition) {
        throw $Message
    }
}

function ConvertFrom-JsonCompat {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Text,
        [int]$Depth = 80
    )

    $command = Get-Command -Name ConvertFrom-Json -CommandType Cmdlet
    if ($command.Parameters.ContainsKey('Depth')) {
        return $Text | ConvertFrom-Json -Depth $Depth
    }

    return $Text | ConvertFrom-Json
}

function ConvertTo-TestUtcString {
    param($Value)

    if ($Value -is [DateTime]) {
        return ([DateTime]$Value).ToUniversalTime().ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    }

    if ($Value -is [DateTimeOffset]) {
        return ([DateTimeOffset]$Value).ToUniversalTime().ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    }

    return [string]$Value
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$script = Join-Path $repoRoot 'scripts\capture-riftscan-proof-pose.ps1'
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('RiftReader-riftscan-proof-pose-success-' + [System.Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

try {
    $candidateFile = Join-Path $tempRoot 'candidate.json'
    $referenceScript = Join-Path $tempRoot 'fake-reference.ps1'
    $readbackScript = Join-Path $tempRoot 'fake-readback.ps1'

    @{ schema = 'fixture-candidate' } | ConvertTo-Json | Set-Content -LiteralPath $candidateFile -Encoding UTF8

    @'
[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Remaining
)

function Get-ArgumentValue {
    param(
        [string[]]$Arguments,
        [string]$Name
    )

    $index = [Array]::IndexOf($Arguments, $Name)
    if ($index -lt 0 -or $index -ge ($Arguments.Count - 1)) {
        return $null
    }

    return $Arguments[$index + 1]
}

$outputFile = Get-ArgumentValue -Arguments $Remaining -Name '-OutputFile'
if ([string]::IsNullOrWhiteSpace($outputFile)) {
    Write-Error 'missing -OutputFile'
    exit 1
}

$reference = [ordered]@{
    source = 'fixture-reference'
    captured_at_utc = '2026-05-07T04:00:00.0000000Z'
    tolerance = 0.25
    coordinate = [ordered]@{
        x = 1.25
        y = 2.5
        z = 3.75
    }
    noCheatEngine = $true
    movementSent = $false
    savedVariablesUse = 'none'
}
$reference | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $outputFile -Encoding UTF8

$summary = [ordered]@{
    Mode = 'rift-api-reference-coordinate-capture'
    Status = 'captured'
    ReferenceFile = [System.IO.Path]::GetFullPath($outputFile)
    NoCheatEngine = $true
    MovementSent = $false
}
$summary | ConvertTo-Json -Depth 10
exit 0
'@ | Set-Content -LiteralPath $referenceScript -Encoding UTF8

    @'
[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Remaining
)

function Get-ArgumentValue {
    param(
        [string[]]$Arguments,
        [string]$Name
    )

    $index = [Array]::IndexOf($Arguments, $Name)
    if ($index -lt 0 -or $index -ge ($Arguments.Count - 1)) {
        return $null
    }

    return $Arguments[$index + 1]
}

$summaryFile = Join-Path $env:TEMP 'fixture-success-readback-summary.json'
$referenceFile = Get-ArgumentValue -Arguments $Remaining -Name '-ReferenceFile'

$summary = [ordered]@{
    ProcessName = 'rift_x64'
    ProcessId = 4242
    TargetWindowHandle = '0x1234'
    MovementAllowed = $false
    ReferenceMatchCount = 1
    ReadbackTotalRegionReadFailures = 0
    StableDecodedCandidateCount = 1
    ProofAnchorStatus = 'failed'
    ProofAnchorIssues = @('fixture-proof-anchor-blocked')
    MovementGate = 'blocked_until_fixture'
    Warnings = @('fixture-readback-warning')
    SummaryFile = $summaryFile
    BestReferenceMatches = @(
        [ordered]@{
            Rank = 1
            CandidateId = 'fixture-candidate-000001'
            CandidateAddressHex = '0x1010'
            ReferenceMatchesReadback = $true
            ReferenceMaxAbsDelta = 0.0
            StableAcrossReadbackSamples = $true
            DecodedSampleCount = 2
            FirstDecodedSample = [ordered]@{
                SampleIndex = 0
                RecordedAtUtc = '2026-05-07T04:00:01.0000000Z'
                X = 1.25
                Y = 2.5
                Z = 3.75
            }
        }
    )
    ProofAnchorCandidateReadback = [ordered]@{
        CurrentCoordinate = [ordered]@{
            X = 1.25
            Y = 2.5
            Z = 3.75
            RecordedAtUtc = '2026-05-07T04:00:01.0000000Z'
        }
    }
    ReceivedReferenceFile = $referenceFile
}

$summary | ConvertTo-Json -Depth 20
exit 0
'@ | Set-Content -LiteralPath $readbackScript -Encoding UTF8

    $summaryJson = & $script `
        -CandidateFile $candidateFile `
        -OutputRoot $tempRoot `
        -PoseLabel fixture-success `
        -ProcessId 4242 `
        -TargetWindowHandle 0x1234 `
        -ReferenceScript $referenceScript `
        -ReadbackScript $readbackScript `
        -Json

    $summary = ConvertFrom-JsonCompat -Text ($summaryJson -join [Environment]::NewLine) -Depth 40
    Assert-Equal -Actual $summary.Mode -Expected 'riftscan-proof-pose-capture' -Message 'Unexpected summary mode.'
    Assert-Equal -Actual $summary.Status -Expected 'captured' -Message 'Successful fixture should produce captured status.'
    Assert-True -Condition ([bool]$summary.NoCheatEngine) -Message 'Wrapper must preserve no-CE boundary.'
    Assert-True -Condition (-not [bool]$summary.MovementSent) -Message 'Wrapper must not send movement.'
    Assert-True -Condition (-not [bool]$summary.MovementAllowed) -Message 'Fixture still should not unlock movement.'
    Assert-Equal -Actual $summary.CandidateFile -Expected ([System.IO.Path]::GetFullPath($candidateFile)) -Message 'Explicit candidate file should be preserved.'
    Assert-True -Condition (-not [bool]$summary.CandidateResolvedFromPointer) -Message 'Explicit CandidateFile should not be marked pointer-resolved.'
    Assert-True -Condition ($null -eq $summary.CurrentProofPointerFile) -Message 'Explicit CandidateFile should not require a current proof pointer.'
    Assert-True -Condition ($null -eq $summary.CandidateSource) -Message 'Explicit CandidateFile should not synthesize a pointer candidate source.'
    Assert-True -Condition ([bool]$summary.ReferenceCaptured) -Message 'ReferenceCaptured should be true on success.'
    Assert-Equal -Actual $summary.ReferenceCaptureExitCode -Expected 0 -Message 'Reference helper exit code should be preserved.'
    Assert-True -Condition (-not [string]::IsNullOrWhiteSpace([string]$summary.ReferenceFile)) -Message 'ReferenceFile should be populated.'
    Assert-True -Condition (Test-Path -LiteralPath ([string]$summary.ReferenceFile) -PathType Leaf) -Message 'ReferenceFile should exist.'
    Assert-Equal -Actual $summary.ReferenceMatchCount -Expected 1 -Message 'Reference match count should be parsed.'
    Assert-Equal -Actual $summary.StableDecodedCandidateCount -Expected 1 -Message 'Stable decoded count should be parsed.'
    Assert-Equal -Actual $summary.ReadbackTotalRegionReadFailures -Expected 0 -Message 'Readback failures should be parsed.'
    Assert-Equal -Actual $summary.ReadbackWarningCount -Expected 1 -Message 'Wrapper should expose readback warning count.'
    Assert-True -Condition (@($summary.ReadbackWarnings) -contains 'fixture-readback-warning') -Message 'Readback warnings should be preserved separately.'
    Assert-Equal -Actual $summary.WarningCount -Expected 4 -Message 'Wrapper should expose total warning count.'
    Assert-True -Condition (@($summary.Warnings) -contains 'Readback: fixture-readback-warning') -Message 'Readback warnings should be surfaced in wrapper warnings.'
    Assert-Equal -Actual $summary.BestReferenceMatch.CandidateId -Expected 'fixture-candidate-000001' -Message 'Best reference match should be preserved.'
    Assert-True -Condition ($summaryJson -match '"RecordedAtUtc":\s*"2026-05-07T04:00:01.0000000Z"') -Message 'Wrapper JSON should preserve readback timestamps as ISO UTC strings.'
    Assert-Equal -Actual (ConvertTo-TestUtcString -Value $summary.CurrentCoordinate.RecordedAtUtc) -Expected '2026-05-07T04:00:01.0000000Z' -Message 'Current coordinate should be copied from readback summary.'
    Assert-True -Condition ($summary.Commands.Reference.Arguments -contains '-ScanContextBytes') -Message 'Reference capture should receive robust scan context control.'
    Assert-True -Condition ($summary.Commands.Reference.Arguments -contains '4096') -Message 'Reference capture should default to a wider RRAPICOORD scan context.'
    Assert-True -Condition ($summary.Commands.Reference.Arguments -contains '-MaxHits') -Message 'Reference capture should receive robust max-hit control.'
    Assert-True -Condition ($summary.Commands.Reference.Arguments -contains '512') -Message 'Reference capture should default to enough RRAPICOORD scan hits for live-marker capture.'
    Assert-True -Condition ($summary.Commands.Reference.Arguments -contains '-ScanAttempts') -Message 'Reference capture should receive retry control.'
    Assert-True -Condition ($summary.Commands.Reference.Arguments -contains '5') -Message 'Reference capture should default to repeated RRAPICOORD capture attempts.'
    Assert-True -Condition ($summary.Commands.Readback.Arguments -contains '-ReferenceFile') -Message 'Readback should receive -ReferenceFile on reference success.'
    Assert-Equal -Actual $summary.Commands.Readback.ExitCode -Expected 0 -Message 'Readback command exit code should be preserved.'

    Write-Host 'RiftScan proof pose success regression passed.' -ForegroundColor Green
}
finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}
