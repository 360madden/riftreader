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

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$script = Join-Path $repoRoot 'scripts\capture-riftscan-proof-pose.ps1'
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('RiftReader-riftscan-proof-pose-pointer-' + [System.Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

try {
    $candidateFile = Join-Path $tempRoot 'candidate.json'
    $pointerFile = Join-Path $tempRoot 'current-proof-anchor-readback.json'
    $referenceScript = Join-Path $tempRoot 'fake-reference.ps1'
    $readbackScript = Join-Path $tempRoot 'fake-readback.ps1'

    @{ schema = 'fixture-candidate' } | ConvertTo-Json | Set-Content -LiteralPath $candidateFile -Encoding UTF8

    $pointer = [ordered]@{
        schemaVersion = 1
        mode = 'current-proof-anchor-readback-pointer'
        status = 'movement-grade-current-session'
        target = [ordered]@{
            processName = 'rift_x64.exe'
            processId = 4242
            targetWindowHandle = '0x1234'
        }
        riftscanCandidateSource = [ordered]@{
            riftScanRoot = 'C:\RIFT MODDING\Riftscan'
            matchFile = [System.IO.Path]::GetFullPath($candidateFile)
            candidateId = 'fixture-candidate-000001'
            sourceBaseAddressHex = '0x10000000'
            sourceOffsetHex = '0x120'
            sourceAbsoluteAddressHex = '0x10000120'
            supportCount = 3
            bestMaxAbsDistance = 0.003
        }
    }
    $pointer | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $pointerFile -Encoding UTF8

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
    captured_at_utc = '2026-05-08T10:00:00.0000000Z'
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

$summaryFile = Join-Path $env:TEMP 'fixture-pointer-readback-summary.json'
$referenceFile = Get-ArgumentValue -Arguments $Remaining -Name '-ReferenceFile'
$candidateFile = Get-ArgumentValue -Arguments $Remaining -Name '-CandidateFile'

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
    Warnings = @()
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
                RecordedAtUtc = '2026-05-08T10:00:01.0000000Z'
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
            RecordedAtUtc = '2026-05-08T10:00:01.0000000Z'
        }
    }
    ReceivedReferenceFile = $referenceFile
    ReceivedCandidateFile = $candidateFile
}

$summary | ConvertTo-Json -Depth 20
exit 0
'@ | Set-Content -LiteralPath $readbackScript -Encoding UTF8

    $summaryJson = & $script `
        -CurrentProofPointerFile $pointerFile `
        -OutputRoot $tempRoot `
        -PoseLabel fixture-pointer `
        -ProcessId 4242 `
        -TargetWindowHandle 4660 `
        -ProcessName rift_x64 `
        -ReferenceScript $referenceScript `
        -ReadbackScript $readbackScript `
        -Json

    $summary = ConvertFrom-JsonCompat -Text ($summaryJson -join [Environment]::NewLine) -Depth 60
    Assert-Equal -Actual $summary.Mode -Expected 'riftscan-proof-pose-capture' -Message 'Unexpected summary mode.'
    Assert-Equal -Actual $summary.Status -Expected 'captured' -Message 'Pointer-resolved fixture should capture.'
    Assert-True -Condition ([bool]$summary.NoCheatEngine) -Message 'Wrapper must preserve no-CE boundary.'
    Assert-True -Condition (-not [bool]$summary.MovementSent) -Message 'Wrapper must not send movement.'
    Assert-Equal -Actual $summary.CandidateFile -Expected ([System.IO.Path]::GetFullPath($candidateFile)) -Message 'Pointer matchFile should resolve to candidate file.'
    Assert-True -Condition ([bool]$summary.CandidateResolvedFromPointer) -Message 'Candidate should be marked pointer-resolved when CandidateFile is omitted.'
    Assert-Equal -Actual $summary.CurrentProofPointerFile -Expected ([System.IO.Path]::GetFullPath($pointerFile)) -Message 'Pointer file should be recorded.'
    Assert-Equal -Actual $summary.CandidateSource.candidateId -Expected 'fixture-candidate-000001' -Message 'Pointer candidate source should be preserved.'
    Assert-Equal -Actual $summary.CandidateSource.sourceAbsoluteAddressHex -Expected '0x10000120' -Message 'Pointer address source should be preserved.'
    Assert-Equal -Actual $summary.Commands.Readback.Arguments[([Array]::IndexOf($summary.Commands.Readback.Arguments, '-CandidateFile') + 1)] -Expected ([System.IO.Path]::GetFullPath($candidateFile)) -Message 'Readback command should receive pointer-resolved candidate file.'

    $failed = $false
    $failureMessage = ''
    try {
        & $script `
            -CurrentProofPointerFile $pointerFile `
            -OutputRoot $tempRoot `
            -PoseLabel fixture-pointer-mismatch `
            -ProcessId 9999 `
            -TargetWindowHandle 4660 `
            -ProcessName rift_x64 `
            -ReferenceScript $referenceScript `
            -ReadbackScript $readbackScript `
            -Json | Out-Null
    }
    catch {
        $failed = $true
        $failureMessage = $_.Exception.Message
    }

    Assert-True -Condition $failed -Message 'PID mismatch should fail closed before readback.'
    Assert-True -Condition ($failureMessage -like '*target PID*does not match requested PID 9999*') -Message "PID mismatch should report pointer target mismatch. Actual: $failureMessage"

    Write-Host 'RiftScan proof pose pointer-resolution regression passed.' -ForegroundColor Green
}
finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}
