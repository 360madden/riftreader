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

function New-ProofAnchorFixture {
    param(
        [Parameter(Mandatory = $true)]
        [int]$ProcessId,

        [Parameter(Mandatory = $true)]
        [string]$ProcessName,

        [DateTimeOffset]$GeneratedAtUtc = [DateTimeOffset]::UtcNow,

        [bool]$TraceMatchesProcess = $true,

        [bool]$CoordMatchesWithinTolerance = $true,

        [int]$CoordXRelativeOffset = 0,

        [int]$CoordYRelativeOffset = 4,

        [int]$CoordZRelativeOffset = 8
    )

    return [ordered]@{
        Mode = 'proof-coord-anchor'
        GeneratedAtUtc = $GeneratedAtUtc.ToUniversalTime().ToString('O')
        ProcessName = $ProcessName
        ProcessId = $ProcessId
        CanonicalCoordSourceKind = 'coord-trace-source-object'
        MatchSource = 'source-object'
        TraceSourceFile = 'fixture-player-coord-write-trace.json'
        VerificationMethod = 'coord-triplet-access'
        TraceMatchesProcess = $TraceMatchesProcess
        ObjectBaseAddress = '0x1000'
        CoordRegionAddress = '0x1048'
        CoordXRelativeOffset = $CoordXRelativeOffset
        CoordYRelativeOffset = $CoordYRelativeOffset
        CoordZRelativeOffset = $CoordZRelativeOffset
        Match = [ordered]@{
            CoordMatchesWithinTolerance = $CoordMatchesWithinTolerance
            DeltaX = 0.0
            DeltaY = 0.0
            DeltaZ = 0.0
        }
    }
}

function New-NoCeRiftScanProofAnchorFixture {
    param(
        [Parameter(Mandatory = $true)]
        [int]$ProcessId,

        [Parameter(Mandatory = $true)]
        [string]$ProcessName,

        [DateTimeOffset]$GeneratedAtUtc = [DateTimeOffset]::UtcNow,

        [bool]$ProofProcessMatchesProcess = $true,

        [string]$ProofValidationStatus = 'validated',

        [int]$PoseCount = 2,

        [double]$MaxReferencePlanarDisplacement = 5.0
    )

    return [ordered]@{
        Mode = 'proof-coord-anchor'
        GeneratedAtUtc = $GeneratedAtUtc.ToUniversalTime().ToString('O')
        ProcessName = $ProcessName
        ProcessId = $ProcessId
        CanonicalCoordSourceKind = 'riftscan-reference-validated-candidate'
        ProofMethod = 'no-ce-riftscan-reference-multisample'
        ProofValidationStatus = $ProofValidationStatus
        ProofProcessMatchesProcess = $ProofProcessMatchesProcess
        NoCheatEngine = $true
        TraceMatchesProcess = $false
        ObjectBaseAddress = '0x2000'
        CoordRegionAddress = '0x2000'
        CoordXRelativeOffset = 0
        CoordYRelativeOffset = 4
        CoordZRelativeOffset = 8
        Match = [ordered]@{
            CoordMatchesWithinTolerance = $true
            MaxDeltaError = 0.05
        }
        Evidence = [ordered]@{
            PoseCount = $PoseCount
            MaxReferencePlanarDisplacement = $MaxReferencePlanarDisplacement
            MaxDeltaError = 0.05
        }
    }
}

function Invoke-Preflight {
    param(
        [Parameter(Mandatory = $true)]
        [string]$AnchorFile,

        [Parameter(Mandatory = $true)]
        [int]$TargetProcessId,

        [Parameter(Mandatory = $true)]
        [string]$TargetProcessName,

        [int]$MaxAgeSeconds = 300,

        [bool]$UseCacheOnly = $true
    )

    $arguments = @(
        '-NoLogo',
        '-NoProfile',
        '-ExecutionPolicy',
        'Bypass',
        '-File',
        $script:PreflightScript,
        '-ProcessId',
        $TargetProcessId,
        '-ProcessName',
        $TargetProcessName,
        '-ProofCoordAnchorFile',
        $AnchorFile,
        '-MaxAgeSeconds',
        $MaxAgeSeconds,
        '-Json'
    )
    if ($UseCacheOnly) {
        $arguments += '-UseCacheOnly'
    }

    $output = & powershell @arguments 2>&1

    $exitCode = $LASTEXITCODE
    $text = ($output -join [Environment]::NewLine).Trim()
    if ([string]::IsNullOrWhiteSpace($text)) {
        throw "Preflight produced no JSON. ExitCode=$exitCode"
    }

    return [pscustomobject]@{
        ExitCode = $exitCode
        Document = $text | ConvertFrom-Json -Depth 40
        Raw = $text
    }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$script:PreflightScript = Join-Path $repoRoot 'scripts\assert-current-proof-coord-anchor.ps1'
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('RiftReader-proof-anchor-preflight-' + [System.Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

try {
    $targetProcess = Get-Process -Id $PID -ErrorAction Stop
    $targetProcessId = [int]$targetProcess.Id
    $targetProcessName = $targetProcess.ProcessName

    $validAnchorFile = Join-Path $tempRoot 'valid-anchor.json'
    New-ProofAnchorFixture -ProcessId $targetProcessId -ProcessName $targetProcessName |
        ConvertTo-Json -Depth 20 |
        Set-Content -LiteralPath $validAnchorFile -Encoding UTF8

    $valid = Invoke-Preflight -AnchorFile $validAnchorFile -TargetProcessId $targetProcessId -TargetProcessName $targetProcessName
    Assert-Equal -Actual $valid.ExitCode -Expected 0 -Message 'Valid fixture should exit 0.'
    Assert-Equal -Actual $valid.Document.Status -Expected 'valid' -Message 'Valid fixture should produce valid status.'
    Assert-True -Condition ([bool]$valid.Document.MovementAllowed) -Message 'Valid fixture should allow movement gate.'
    Assert-True -Condition ([bool]$valid.Document.NoCheatEngine) -Message 'Preflight must mark no CE.'
    Assert-True -Condition (-not [bool]$valid.Document.MovementSent) -Message 'Preflight must not send movement.'

    $validNoCeAnchorFile = Join-Path $tempRoot 'valid-no-ce-anchor.json'
    New-NoCeRiftScanProofAnchorFixture -ProcessId $targetProcessId -ProcessName $targetProcessName |
        ConvertTo-Json -Depth 20 |
        Set-Content -LiteralPath $validNoCeAnchorFile -Encoding UTF8

    $validNoCe = Invoke-Preflight -AnchorFile $validNoCeAnchorFile -TargetProcessId $targetProcessId -TargetProcessName $targetProcessName
    Assert-Equal -Actual $validNoCe.ExitCode -Expected 0 -Message 'Valid no-CE RiftScan reference proof fixture should exit 0.'
    Assert-Equal -Actual $validNoCe.Document.Status -Expected 'valid' -Message 'Valid no-CE RiftScan reference proof fixture should produce valid status.'
    Assert-True -Condition ([bool]$validNoCe.Document.MovementAllowed) -Message 'Valid no-CE RiftScan reference proof fixture should allow movement gate.'

    $validNoCeDefault = Invoke-Preflight -AnchorFile $validNoCeAnchorFile -TargetProcessId $targetProcessId -TargetProcessName $targetProcessName -UseCacheOnly:$false
    Assert-Equal -Actual $validNoCeDefault.ExitCode -Expected 0 -Message 'Default preflight should accept valid no-CE RiftScan reference proof cache.'
    Assert-Equal -Actual $validNoCeDefault.Document.Status -Expected 'valid' -Message 'Default preflight should produce valid status for no-CE RiftScan reference proof cache.'
    Assert-Equal -Actual $validNoCeDefault.Document.AnchorSource -Expected 'cache' -Message 'Default preflight should use no-CE RiftScan reference proof cache before legacy resolver.'
    Assert-True -Condition ([bool]$validNoCeDefault.Document.MovementAllowed) -Message 'Default preflight should allow movement for valid no-CE RiftScan reference proof cache.'

    $badNoCeAnchorFile = Join-Path $tempRoot 'bad-no-ce-anchor.json'
    New-NoCeRiftScanProofAnchorFixture -ProcessId $targetProcessId -ProcessName $targetProcessName -ProofProcessMatchesProcess:$false |
        ConvertTo-Json -Depth 20 |
        Set-Content -LiteralPath $badNoCeAnchorFile -Encoding UTF8

    $badNoCe = Invoke-Preflight -AnchorFile $badNoCeAnchorFile -TargetProcessId $targetProcessId -TargetProcessName $targetProcessName
    Assert-Equal -Actual $badNoCe.ExitCode -Expected 1 -Message 'Bad no-CE process proof fixture should exit 1.'
    Assert-True -Condition (($badNoCe.Document.Issues -join '|') -like '*proof_anchor_no_ce_process_proof_does_not_match_process*') -Message 'Bad no-CE process proof issue should be reported.'

    $pidMismatchAnchorFile = Join-Path $tempRoot 'pid-mismatch-anchor.json'
    New-ProofAnchorFixture -ProcessId ($targetProcessId + 999999) -ProcessName $targetProcessName |
        ConvertTo-Json -Depth 20 |
        Set-Content -LiteralPath $pidMismatchAnchorFile -Encoding UTF8

    $pidMismatch = Invoke-Preflight -AnchorFile $pidMismatchAnchorFile -TargetProcessId $targetProcessId -TargetProcessName $targetProcessName
    Assert-Equal -Actual $pidMismatch.ExitCode -Expected 1 -Message 'PID mismatch fixture should exit 1.'
    Assert-Equal -Actual $pidMismatch.Document.Status -Expected 'failed' -Message 'PID mismatch fixture should fail.'
    Assert-True -Condition (-not [bool]$pidMismatch.Document.MovementAllowed) -Message 'PID mismatch fixture should block movement.'
    Assert-True -Condition (($pidMismatch.Document.Issues -join '|') -like '*proof_anchor_pid_mismatch*') -Message 'PID mismatch issue should be reported.'

    $badMatchAnchorFile = Join-Path $tempRoot 'bad-match-anchor.json'
    New-ProofAnchorFixture -ProcessId $targetProcessId -ProcessName $targetProcessName -CoordMatchesWithinTolerance:$false |
        ConvertTo-Json -Depth 20 |
        Set-Content -LiteralPath $badMatchAnchorFile -Encoding UTF8

    $badMatch = Invoke-Preflight -AnchorFile $badMatchAnchorFile -TargetProcessId $targetProcessId -TargetProcessName $targetProcessName
    Assert-Equal -Actual $badMatch.ExitCode -Expected 1 -Message 'Bad match fixture should exit 1.'
    Assert-True -Condition (($badMatch.Document.Issues -join '|') -like '*proof_anchor_match_not_within_tolerance*') -Message 'Bad match issue should be reported.'

    $staleAnchorFile = Join-Path $tempRoot 'stale-anchor.json'
    New-ProofAnchorFixture -ProcessId $targetProcessId -ProcessName $targetProcessName -GeneratedAtUtc ([DateTimeOffset]::UtcNow.AddMinutes(-10)) |
        ConvertTo-Json -Depth 20 |
        Set-Content -LiteralPath $staleAnchorFile -Encoding UTF8

    $stale = Invoke-Preflight -AnchorFile $staleAnchorFile -TargetProcessId $targetProcessId -TargetProcessName $targetProcessName -MaxAgeSeconds 1
    Assert-Equal -Actual $stale.ExitCode -Expected 1 -Message 'Stale fixture should exit 1.'
    Assert-True -Condition (($stale.Document.Issues -join '|') -like '*proof_anchor_age_out_of_range_seconds*') -Message 'Stale age issue should be reported.'

    Write-Host 'Proof coord anchor preflight regression passed.' -ForegroundColor Green
}
finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}
