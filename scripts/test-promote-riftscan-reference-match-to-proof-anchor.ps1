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

function New-ReadbackSummaryFixture {
    param(
        [Parameter(Mandatory = $true)]
        [int]$ProcessId,

        [string]$TargetWindowHandle,

        [Parameter(Mandatory = $true)]
        [double]$ReferenceX,

        [Parameter(Mandatory = $true)]
        [double]$ReferenceY,

        [Parameter(Mandatory = $true)]
        [double]$ReferenceZ,

        [Parameter(Mandatory = $true)]
        [double]$CandidateX,

        [Parameter(Mandatory = $true)]
        [double]$CandidateY,

        [Parameter(Mandatory = $true)]
        [double]$CandidateZ,

        [int]$SampleIndex = 0
    )

    return [ordered]@{
        SchemaVersion = 1
        Mode = 'riftscan-riftreader-coordinate-readback'
        GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
        ProcessName = $script:TargetProcessName
        ProcessId = $ProcessId
        TargetWindowHandle = $TargetWindowHandle
        NoCheatEngine = $true
        MovementSent = $false
        MovementAllowed = $false
        ReferenceCoordinate = [ordered]@{
            Source = 'fixture-reference'
            X = $ReferenceX
            Y = $ReferenceY
            Z = $ReferenceZ
            Tolerance = 0.25
            CapturedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
        }
        CandidateReadbacks = @(
            [ordered]@{
                CandidateId = 'vec3-000001'
                CandidateAddressHex = '0x12345000'
                RegionAddressHex = '0x12344FC0'
                RegionLength = 140
                CandidateOffsetInRegion = 64
                DecodedSampleCount = 2
                MaxAbsDeltaAcrossReadbackSamples = 0.0
                StableAcrossReadbackSamples = $true
                ReferenceMaxAbsDelta = 0.05
                ReferencePlanarDistance = 0.05
                ReferenceSpatialDistance = 0.05
                ReferenceMatchesReadback = $true
                DecodedSamples = @(
                    [ordered]@{
                        SampleIndex = $SampleIndex
                        RecordedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
                        X = $CandidateX
                        Y = $CandidateY
                        Z = $CandidateZ
                    },
                    [ordered]@{
                        SampleIndex = $SampleIndex + 1
                        RecordedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
                        X = $CandidateX
                        Y = $CandidateY
                        Z = $CandidateZ
                    }
                )
            }
        )
    }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$promoteScript = Join-Path $repoRoot 'scripts\promote-riftscan-reference-match-to-proof-anchor.ps1'
$preflightScript = Join-Path $repoRoot 'scripts\assert-current-proof-coord-anchor.ps1'
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('RiftReader-no-ce-riftscan-proof-promotion-' + [System.Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

try {
    $targetProcess = Get-Process -Id $PID -ErrorAction Stop
    $script:TargetProcessName = $targetProcess.ProcessName
    $targetProcessId = [int]$targetProcess.Id
    $targetWindowHandle = if ($targetProcess.MainWindowHandle -ne 0) { '0x{0:X}' -f $targetProcess.MainWindowHandle.ToInt64() } else { $null }

    $poseAFile = Join-Path $tempRoot 'pose-a-summary.json'
    $poseBFile = Join-Path $tempRoot 'pose-b-summary.json'
    $anchorFile = Join-Path $tempRoot 'promoted-anchor.json'

    New-ReadbackSummaryFixture `
        -ProcessId $targetProcessId `
        -TargetWindowHandle $targetWindowHandle `
        -ReferenceX 10.0 `
        -ReferenceY 2.0 `
        -ReferenceZ 20.0 `
        -CandidateX 10.02 `
        -CandidateY 2.0 `
        -CandidateZ 19.99 `
        -SampleIndex 0 |
        ConvertTo-Json -Depth 40 |
        Set-Content -LiteralPath $poseAFile -Encoding UTF8

    New-ReadbackSummaryFixture `
        -ProcessId $targetProcessId `
        -TargetWindowHandle $targetWindowHandle `
        -ReferenceX 13.0 `
        -ReferenceY 2.0 `
        -ReferenceZ 24.0 `
        -CandidateX 13.03 `
        -CandidateY 2.0 `
        -CandidateZ 24.01 `
        -SampleIndex 2 |
        ConvertTo-Json -Depth 40 |
        Set-Content -LiteralPath $poseBFile -Encoding UTF8

    & $promoteScript `
        -ReadbackSummaryFile @($poseAFile, $poseBFile) `
        -CandidateId 'vec3-000001' `
        -ProcessId $targetProcessId `
        -ProcessName $script:TargetProcessName `
        -OutputFile $anchorFile `
        -MinReferenceDisplacement 1.0 `
        -MaxDeltaError 0.25 `
        -MaxEvidenceAgeSeconds 300 `
        -Json | Out-Null

    $anchor = Get-Content -LiteralPath $anchorFile -Raw | ConvertFrom-Json -Depth 80
    Assert-Equal -Actual $anchor.Mode -Expected 'proof-coord-anchor' -Message 'Promoted anchor mode mismatch.'
    Assert-Equal -Actual $anchor.CanonicalCoordSourceKind -Expected 'riftscan-reference-validated-candidate' -Message 'Promoted anchor source kind mismatch.'
    Assert-Equal -Actual $anchor.ProofMethod -Expected 'no-ce-riftscan-reference-multisample' -Message 'Promoted anchor proof method mismatch.'
    Assert-True -Condition ([bool]$anchor.NoCheatEngine) -Message 'Promoted anchor must report NoCheatEngine=true.'
    Assert-True -Condition ([bool]$anchor.ProofProcessMatchesProcess) -Message 'Promoted anchor must report ProofProcessMatchesProcess=true.'
    Assert-Equal -Actual $anchor.Evidence.PoseCount -Expected 2 -Message 'Promoted anchor pose count mismatch.'
    Assert-True -Condition ([double]$anchor.Evidence.MaxReferencePlanarDisplacement -ge 5.0) -Message 'Promoted anchor should preserve reference displacement.'
    Assert-True -Condition ([double]$anchor.Evidence.MaxDeltaError -le 0.25) -Message 'Promoted anchor delta error should be within threshold.'

    $preflightOutput = & powershell `
        -NoLogo `
        -NoProfile `
        -ExecutionPolicy Bypass `
        -File $preflightScript `
        -ProcessId $targetProcessId `
        -ProcessName $script:TargetProcessName `
        -ProofCoordAnchorFile $anchorFile `
        -UseCacheOnly `
        -MaxAgeSeconds 300 `
        -Json 2>&1

    if ($LASTEXITCODE -ne 0) {
        throw "Preflight rejected promoted no-CE anchor: $($preflightOutput -join [Environment]::NewLine)"
    }

    $preflight = ($preflightOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 80
    Assert-Equal -Actual $preflight.Status -Expected 'valid' -Message 'Preflight should accept promoted no-CE anchor.'
    Assert-True -Condition ([bool]$preflight.MovementAllowed) -Message 'Preflight should allow movement gate for promoted no-CE anchor fixture.'

    $weakAnchorFile = Join-Path $tempRoot 'weak-anchor.json'
    $weakFailed = $false
    $weakMessage = ''
    try {
        & $promoteScript `
            -ReadbackSummaryFile @($poseAFile) `
            -CandidateId 'vec3-000001' `
            -ProcessId $targetProcessId `
            -ProcessName $script:TargetProcessName `
            -OutputFile $weakAnchorFile `
            -MinReferenceDisplacement 1.0 `
            -Json | Out-Null
    }
    catch {
        $weakFailed = $true
        $weakMessage = $_.Exception.Message
    }

    Assert-True -Condition $weakFailed -Message 'Promotion should fail closed with only one pose.'
    Assert-True -Condition ($weakMessage -like '*At least 2 readback summary files are required*') -Message 'Weak promotion failure reason should mention pose count.'

    Write-Host 'No-CE RiftScan reference proof promotion regression passed.' -ForegroundColor Green
}
finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}
