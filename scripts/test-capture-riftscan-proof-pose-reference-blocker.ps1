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

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$script = Join-Path $repoRoot 'scripts\capture-riftscan-proof-pose.ps1'
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('RiftReader-riftscan-proof-pose-blocker-' + [System.Guid]::NewGuid().ToString('N'))
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

Write-Error 'fixture reference unavailable'
exit 1
'@ | Set-Content -LiteralPath $referenceScript -Encoding UTF8

    @'
[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Remaining
)

$summary = [ordered]@{
    ProcessName = 'rift_x64'
    ProcessId = 4242
    TargetWindowHandle = '0x1234'
    MovementAllowed = $false
    ReferenceMatchCount = 0
    ReadbackTotalRegionReadFailures = 0
    StableDecodedCandidateCount = 1
    ProofAnchorStatus = 'failed'
    ProofAnchorIssues = @('fixture-proof-anchor-blocked')
    MovementGate = 'blocked_until_fixture'
    SummaryFile = (Join-Path $env:TEMP 'fixture-readback-summary.json')
    ReceivedReferenceFileArgument = ($Remaining -contains '-ReferenceFile')
}

$summary | ConvertTo-Json -Depth 10
exit 0
'@ | Set-Content -LiteralPath $readbackScript -Encoding UTF8

    $summaryJson = & $script `
        -CandidateFile $candidateFile `
        -OutputRoot $tempRoot `
        -PoseLabel fixture `
        -ProcessId 4242 `
        -TargetWindowHandle 0x1234 `
        -ReferenceScript $referenceScript `
        -ReadbackScript $readbackScript `
        -Json

    $summary = $summaryJson | ConvertFrom-Json -Depth 30
    Assert-Equal -Actual $summary.Mode -Expected 'riftscan-proof-pose-capture' -Message 'Unexpected summary mode.'
    Assert-Equal -Actual $summary.Status -Expected 'blocked-reference-unavailable' -Message 'Reference failure should be structured as a blocker status.'
    Assert-True -Condition ([bool]$summary.NoCheatEngine) -Message 'Wrapper must preserve no-CE boundary.'
    Assert-True -Condition (-not [bool]$summary.MovementSent) -Message 'Wrapper must not send movement.'
    Assert-True -Condition (-not [bool]$summary.MovementAllowed) -Message 'Movement must remain blocked.'
    Assert-True -Condition (-not [bool]$summary.ReferenceCaptured) -Message 'ReferenceCaptured must be false when helper fails.'
    Assert-Equal -Actual $summary.ReferenceCaptureExitCode -Expected 1 -Message 'Reference helper exit code should be preserved.'
    Assert-True -Condition ([string]::IsNullOrWhiteSpace([string]$summary.ReferenceFile)) -Message 'ReferenceFile should be empty when no reference is captured.'
    Assert-True -Condition ([string]$summary.ReferenceCaptureError -like '*fixture reference unavailable*') -Message 'Reference failure output should be preserved.'
    Assert-Equal -Actual $summary.ReferenceMatchCount -Expected 0 -Message 'Reference matches should be zero without a reference.'
    Assert-Equal -Actual $summary.ReadbackTotalRegionReadFailures -Expected 0 -Message 'Fixture readback should be parsed.'
    Assert-Equal -Actual $summary.ProofAnchorStatus -Expected 'failed' -Message 'Proof anchor status should be parsed from readback summary.'
    Assert-True -Condition (-not ($summary.Commands.Readback.Arguments -contains '-ReferenceFile')) -Message 'Readback should not receive -ReferenceFile when reference capture failed.'
    Assert-Equal -Actual $summary.Commands.Readback.ExitCode -Expected 0 -Message 'Readback command should still run and succeed.'

    Write-Host 'RiftScan proof pose reference-blocker regression passed.' -ForegroundColor Green
}
finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}
