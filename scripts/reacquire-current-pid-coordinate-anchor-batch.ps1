# Version: riftreader-current-pid-coordinate-anchor-batch-v0.1.3
# Total-Character-Count: 22115
# Purpose: Batch reacquire current-PID coordinate anchor evidence across multiple poses by reusing a coordinate-family candidate file, moving with the proven C# SendInput path between poses, and scoring candidate readbacks across all poses.

[CmdletBinding()]
param(
    [int]$PoseCount = 4,
    [int]$MinimumPromotionPoseSupport = 3,
    [int]$MinimumMovementPulsesForPromotion = 2,
    [string]$Key = "w",
    [int]$HoldMilliseconds = 750,
    [ValidateSet("ScanCode", "VirtualKey")]
    [string]$InputMode = "ScanCode",
    [int]$FocusDelayMilliseconds = 250,
    [int]$SettleSeconds = 2,
    [string]$ProcessName = "rift_x64",
    [string]$TitleContains = "RIFT",
    [string]$CandidateFile,
    [string]$OutputRoot,
    [double]$ReferenceTolerance = 0.25,
    [int]$ReferenceMaxAgeSeconds = 300,
    [int]$ReadbackSampleCount = 4,
    [int]$ReadbackIntervalMilliseconds = 100,
    [int]$TopReferenceMatches = 27,
    [int]$ScanContextBytes = 65536,
    [int]$MaxHits = 2048,
    [int]$ScanAttempts = 12,
    [int]$ScanRetryDelayMilliseconds = 1500,
    [switch]$NoMovement,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ReferenceScript = Join-Path $RepoRoot "scripts\capture-rift-api-reference-coordinate.ps1"
$ProofPoseScript = Join-Path $RepoRoot "scripts\capture-riftscan-proof-pose.ps1"
$SenderScript = Join-Path $RepoRoot "scripts\send-rift-key-csharp.ps1"

foreach ($requiredScript in @($ReferenceScript, $ProofPoseScript, $SenderScript)) {
    if (-not (Test-Path -LiteralPath $requiredScript -PathType Leaf)) {
        throw "Required script not found: $requiredScript"
    }
}

if ($PoseCount -lt 2) {
    throw "PoseCount must be at least 2."
}

if ($MinimumPromotionPoseSupport -lt 2) {
    throw "MinimumPromotionPoseSupport must be at least 2."
}

if ($MinimumMovementPulsesForPromotion -lt 1) {
    throw "MinimumMovementPulsesForPromotion must be at least 1."
}

if ($SettleSeconds -lt 0 -or $HoldMilliseconds -le 0 -or $FocusDelayMilliseconds -lt 0) {
    throw "SettleSeconds and FocusDelayMilliseconds must be zero or greater; HoldMilliseconds must be greater than zero."
}

function Write-Human {
    param([string]$Message)
    if (-not $Json.IsPresent) {
        Write-Host $Message
    }
}

function Invoke-JsonCommand {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$OutputDirectory,
        [switch]$AllowFailure
    )

    New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null

    $stdoutPath = Join-Path $OutputDirectory "$Label.stdout.json"
    $stderrPath = Join-Path $OutputDirectory "$Label.stderr.txt"
    $commandPath = Join-Path $OutputDirectory "$Label.command.json"
    $startedAt = Get-Date

    $output = & $FilePath @Arguments 2> $stderrPath
    $exitCode = $LASTEXITCODE
    $text = ($output -join "`n")
    Set-Content -LiteralPath $stdoutPath -Value $text -Encoding UTF8

    $completedAt = Get-Date
    [ordered]@{
        label = $Label
        filePath = $FilePath
        arguments = @($Arguments)
        startedAtUtc = $startedAt.ToUniversalTime().ToString("o")
        completedAtUtc = $completedAt.ToUniversalTime().ToString("o")
        durationSeconds = ($completedAt - $startedAt).TotalSeconds
        exitCode = $exitCode
        stdoutPath = $stdoutPath
        stderrPath = $stderrPath
    } | ConvertTo-Json -Depth 16 | Set-Content -LiteralPath $commandPath -Encoding UTF8

    $parsed = $null
    $parseError = $null
    if (-not [string]::IsNullOrWhiteSpace($text)) {
        try {
            $parsed = $text | ConvertFrom-Json -Depth 100
        }
        catch {
            $parseError = $_.Exception.Message
        }
    }

    if ($exitCode -ne 0 -and -not $AllowFailure.IsPresent) {
        $stderrText = if (Test-Path -LiteralPath $stderrPath) { Get-Content -LiteralPath $stderrPath -Raw } else { "" }
        throw "$Label failed exit=$exitCode stdout=$stdoutPath stderr=$stderrPath $stderrText"
    }

    return [pscustomobject]@{
        Json = $parsed
        JsonParseError = $parseError
        ExitCode = $exitCode
        StdoutPath = $stdoutPath
        StderrPath = $stderrPath
        CommandPath = $commandPath
        DurationSeconds = ($completedAt - $startedAt).TotalSeconds
        StdoutText = $text
    }
}

function Resolve-RiftTarget {
    $targets = @(
        Get-Process -Name $ProcessName -ErrorAction Stop |
            Where-Object {
                $_.MainWindowHandle -ne 0 -and
                $_.MainWindowTitle -like "*$TitleContains*"
            } |
            Sort-Object StartTime -Descending
    )

    if ($targets.Count -ne 1) {
        $detail = $targets |
            Select-Object Id, ProcessName, MainWindowTitle, MainWindowHandle, StartTime |
            Format-Table |
            Out-String
        throw "Expected exactly one windowed RIFT target; found $($targets.Count).`n$detail"
    }

    $target = $targets[0]
    return [pscustomobject]@{
        ProcessId = [int]$target.Id
        Hwnd = ("0x{0:X}" -f ([int64]$target.MainWindowHandle))
        Title = $target.MainWindowTitle
    }
}

function Resolve-CandidatePath {
    param([int]$RiftPid)

    if (-not [string]::IsNullOrWhiteSpace($CandidateFile)) {
        $resolved = [System.IO.Path]::GetFullPath($CandidateFile)
        if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
            throw "CandidateFile not found: $resolved"
        }

        return $resolved
    }

    $latest = Get-ChildItem (Join-Path $RepoRoot "scripts\captures") -Directory -Filter "family-scan-currentpid-$RiftPid-*" |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1

    if ($null -eq $latest) {
        throw "No family-scan-currentpid-$RiftPid-* capture directory found."
    }

    $candidate = Join-Path $latest.FullName "api-family-vec3-candidates.jsonl"
    if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
        throw "Candidate file missing: $candidate"
    }

    return $candidate
}

function Get-JsonValue {
    param(
        $Object,
        [Parameter(Mandatory = $true)][string]$Name
    )

    if ($null -eq $Object) {
        return $null
    }

    foreach ($property in @($Object.PSObject.Properties)) {
        if ([string]::Equals($property.Name, $Name, [System.StringComparison]::OrdinalIgnoreCase)) {
            return $property.Value
        }
    }

    return $null
}

function Read-ReferenceMatches {
    param($ProofJson)

    $matches = [System.Collections.Generic.List[object]]::new()

    $summaryFile = [string](Get-JsonValue -Object $ProofJson -Name "ReadbackSummaryFile")
    if (-not [string]::IsNullOrWhiteSpace($summaryFile) -and (Test-Path -LiteralPath $summaryFile -PathType Leaf)) {
        try {
            $readbackSummary = Get-Content -LiteralPath $summaryFile -Raw | ConvertFrom-Json -Depth 100
            $top = @(Get-JsonValue -Object $readbackSummary -Name "BestReferenceMatches")
            foreach ($item in $top) {
                if ($null -ne $item) {
                    $matches.Add($item) | Out-Null
                }
            }
        }
        catch {
            # Fall back to BestReferenceMatch below.
        }
    }

    if ($matches.Count -eq 0) {
        $best = Get-JsonValue -Object $ProofJson -Name "BestReferenceMatch"
        if ($null -ne $best) {
            $matches.Add($best) | Out-Null
        }
    }

    return @($matches.ToArray())
}

function New-MatchKey {
    param($Match)

    $candidateId = [string](Get-JsonValue -Object $Match -Name "CandidateId")
    $address = [string](Get-JsonValue -Object $Match -Name "CandidateAddressHex")
    if ([string]::IsNullOrWhiteSpace($candidateId)) { $candidateId = "unknown-id" }
    if ([string]::IsNullOrWhiteSpace($address)) { $address = "unknown-address" }
    return "$candidateId@$address"
}

$targetInfo = Resolve-RiftTarget
$RiftPid = [int]$targetInfo.ProcessId
$RiftHwnd = [string]$targetInfo.Hwnd
$candidatePath = Resolve-CandidatePath -RiftPid $RiftPid

if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $OutputRoot = Join-Path $RepoRoot "scripts\captures\current-pid-coordinate-anchor-batch-$stamp"
}

$runRoot = [System.IO.Path]::GetFullPath($OutputRoot)
$childRoot = Join-Path $runRoot "child-outputs"
New-Item -ItemType Directory -Path $runRoot, $childRoot -Force | Out-Null

Write-Human "Target PID : $RiftPid"
Write-Human "Target HWND: $RiftHwnd"
Write-Human "Candidate  : $candidatePath"
Write-Human "RunRoot    : $runRoot"
Write-Human "PoseCount  : $PoseCount"
Write-Human "Promotion minimum: supportPoses=$MinimumPromotionPoseSupport movementPulses=$MinimumMovementPulsesForPromotion"

$poseResults = [System.Collections.Generic.List[object]]::new()
$scoreEvidence = [System.Collections.Generic.List[object]]::new()
$movementSentCount = 0
$startedAtUtc = (Get-Date).ToUniversalTime().ToString("o")

for ($poseIndex = 1; $poseIndex -le $PoseCount; $poseIndex++) {
    $poseName = "pose-{0:D2}" -f $poseIndex
    $poseLabel = "batch-$poseName-currentpid-coordinate-anchor"
    $poseRoot = Join-Path $runRoot $poseName
    New-Item -ItemType Directory -Path $poseRoot -Force | Out-Null

    Write-Human "=== $poseName ==="

    $movement = $null
    if ($poseIndex -gt 1 -and -not $NoMovement.IsPresent) {
        Write-Human "moving: C# SendInput $InputMode key=$Key hold=${HoldMilliseconds}ms"
        $movement = Invoke-JsonCommand `
            -Label "$poseName-csharp-sendinput" `
            -FilePath "pwsh" `
            -Arguments @(
                "-NoLogo",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                $SenderScript,
                "--key",
                $Key,
                "--hold-ms",
                ([string]$HoldMilliseconds),
                "--process-name",
                $ProcessName,
                "--pid",
                ([string]$RiftPid),
                "--hwnd",
                $RiftHwnd,
                "--title-contains",
                $TitleContains,
                "--input-mode",
                $InputMode,
                "--focus-delay-ms",
                ([string]$FocusDelayMilliseconds),
                "--no-refocus",
                "--json"
            ) `
            -OutputDirectory $childRoot

        if ($movement.ExitCode -ne 0 -or $null -eq $movement.Json -or -not [bool]$movement.Json.ok) {
            throw "$poseName movement failed; stopping batch to avoid ambiguous pose evidence."
        }

        $movementSentCount += 1
        Start-Sleep -Seconds $SettleSeconds
    }

    $referenceFile = Join-Path $poseRoot "$poseName-api-reference.json"

    $reference = Invoke-JsonCommand `
        -Label "$poseName-reference" `
        -FilePath "pwsh" `
        -Arguments @(
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            $ReferenceScript,
            "-ProcessName",
            $ProcessName,
            "-ProcessId",
            ([string]$RiftPid),
            "-TargetWindowHandle",
            $RiftHwnd,
            "-OutputRoot",
            $poseRoot,
            "-OutputFile",
            $referenceFile,
            "-ScanContextBytes",
            ([string]$ScanContextBytes),
            "-MaxHits",
            ([string]$MaxHits),
            "-ScanAttempts",
            ([string]$ScanAttempts),
            "-ScanRetryDelayMilliseconds",
            ([string]$ScanRetryDelayMilliseconds),
            "-Json"
        ) `
        -OutputDirectory $childRoot `
        -AllowFailure

    if ($reference.ExitCode -ne 0 -or $null -eq $reference.Json -or [string](Get-JsonValue -Object $reference.Json -Name "Status") -ne "captured") {
        $poseResults.Add([pscustomobject][ordered]@{
            poseIndex = $poseIndex
            poseName = $poseName
            status = "blocked-reference-unavailable"
            movement = if ($null -eq $movement) { $null } else { $movement.Json }
            referenceExitCode = $reference.ExitCode
            referenceStdout = $reference.StdoutPath
            referenceStderr = $reference.StderrPath
            proofPose = $null
            referenceMatches = @()
        }) | Out-Null
        Write-Human "$poseName reference unavailable; continuing."
        continue
    }

    $proof = Invoke-JsonCommand `
        -Label "$poseName-proof-pose" `
        -FilePath "pwsh" `
        -Arguments @(
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            $ProofPoseScript,
            "-ProcessName",
            $ProcessName,
            "-ProcessId",
            ([string]$RiftPid),
            "-TargetWindowHandle",
            $RiftHwnd,
            "-CandidateFile",
            $candidatePath,
            "-ReferenceFile",
            $referenceFile,
            "-OutputRoot",
            $poseRoot,
            "-PoseLabel",
            $poseLabel,
            "-ReferenceTolerance",
            ([string]$ReferenceTolerance),
            "-ReferenceMaxAgeSeconds",
            ([string]$ReferenceMaxAgeSeconds),
            "-ReadbackSampleCount",
            ([string]$ReadbackSampleCount),
            "-ReadbackIntervalMilliseconds",
            ([string]$ReadbackIntervalMilliseconds),
            "-TopReferenceMatches",
            ([string]$TopReferenceMatches),
            "-Json"
        ) `
        -OutputDirectory $childRoot `
        -AllowFailure

    $matches = @()
    if ($null -ne $proof.Json) {
        $matches = @(Read-ReferenceMatches -ProofJson $proof.Json)
    }

    foreach ($match in $matches) {
        $referenceMatchesReadback = [bool](Get-JsonValue -Object $match -Name "ReferenceMatchesReadback")
        $stable = [bool](Get-JsonValue -Object $match -Name "StableAcrossReadbackSamples")
        if ($referenceMatchesReadback -and $stable) {
            $scoreEvidence.Add([pscustomobject][ordered]@{
                key = New-MatchKey -Match $match
                poseIndex = $poseIndex
                poseName = $poseName
                candidateId = [string](Get-JsonValue -Object $match -Name "CandidateId")
                candidateAddressHex = [string](Get-JsonValue -Object $match -Name "CandidateAddressHex")
                referenceMaxAbsDelta = [double](Get-JsonValue -Object $match -Name "ReferenceMaxAbsDelta")
                referencePlanarDistance = [double](Get-JsonValue -Object $match -Name "ReferencePlanarDistance")
                referenceSpatialDistance = [double](Get-JsonValue -Object $match -Name "ReferenceSpatialDistance")
                decodedSampleCount = [int](Get-JsonValue -Object $match -Name "DecodedSampleCount")
            }) | Out-Null
        }
    }

    $poseResults.Add([pscustomobject][ordered]@{
        poseIndex = $poseIndex
        poseName = $poseName
        status = if ($null -eq $proof.Json) { "failed-proof-json-unavailable" } else { [string](Get-JsonValue -Object $proof.Json -Name "Status") }
        movement = if ($null -eq $movement) { $null } else { $movement.Json }
        reference = $reference.Json
        proofPose = $proof.Json
        referenceMatches = $matches
        proofExitCode = $proof.ExitCode
        proofStdout = $proof.StdoutPath
        proofStderr = $proof.StderrPath
    }) | Out-Null

    $best = if ($matches.Count -gt 0) { $matches[0] } else { $null }
    if ($null -ne $best) {
        Write-Human ("$poseName best={0} addr={1} maxAbs={2}" -f (Get-JsonValue -Object $best -Name "CandidateId"), (Get-JsonValue -Object $best -Name "CandidateAddressHex"), (Get-JsonValue -Object $best -Name "ReferenceMaxAbsDelta"))
    }
}

$scoreRows = [System.Collections.Generic.List[object]]::new()
$groups = @($scoreEvidence.ToArray() | Group-Object -Property key)
foreach ($group in $groups) {
    $items = @($group.Group)
    $uniquePoses = @($items | Select-Object -ExpandProperty poseIndex -Unique)
    $maxAbs = @($items | ForEach-Object { [double]$_.referenceMaxAbsDelta } | Measure-Object -Maximum).Maximum
    $avgPlanar = @($items | ForEach-Object { [double]$_.referencePlanarDistance } | Measure-Object -Average).Average
    $first = $items[0]
    $scoreRows.Add([pscustomobject][ordered]@{
        key = [string]$group.Name
        candidateId = [string]$first.candidateId
        candidateAddressHex = [string]$first.candidateAddressHex
        supportPoseCount = [int]$uniquePoses.Count
        evidenceRowCount = [int]$items.Count
        maxReferenceMaxAbsDelta = [double]$maxAbs
        averageReferencePlanarDistance = [double]$avgPlanar
        poseNames = @($items | Select-Object -ExpandProperty poseName -Unique)
    }) | Out-Null
}

$rankedCandidates = @($scoreRows.ToArray() | Sort-Object -Property @{Expression = "supportPoseCount"; Descending = $true}, @{Expression = "maxReferenceMaxAbsDelta"; Descending = $false}, @{Expression = "averageReferencePlanarDistance"; Descending = $false})
$capturedPoseCount = @($poseResults.ToArray() | Where-Object { $_.status -eq "captured" }).Count
$topCandidate = if ($rankedCandidates.Count -gt 0) { $rankedCandidates[0] } else { $null }
$topCandidateId = if ($null -eq $topCandidate) { $null } else { [string]$topCandidate.candidateId }
$topCandidateAddressHex = if ($null -eq $topCandidate) { $null } else { [string]$topCandidate.candidateAddressHex }
$topCandidateSupportPoseCount = if ($null -eq $topCandidate) { 0 } else { [int]$topCandidate.supportPoseCount }
$topCandidateMaxReferenceMaxAbsDelta = if ($null -eq $topCandidate) { $null } else { [double]$topCandidate.maxReferenceMaxAbsDelta }
$movementEvidenceSatisfied = (-not $NoMovement.IsPresent -and $movementSentCount -ge $MinimumMovementPulsesForPromotion)
$promotionReady = ($movementEvidenceSatisfied -and $capturedPoseCount -ge $MinimumPromotionPoseSupport -and $null -ne $topCandidate -and $topCandidateSupportPoseCount -ge $MinimumPromotionPoseSupport -and $topCandidateMaxReferenceMaxAbsDelta -le $ReferenceTolerance)

$summaryJson = Join-Path $runRoot "coordinate-anchor-batch-summary.json"
$summaryMarkdown = Join-Path $runRoot "coordinate-anchor-batch-summary.md"

$summary = [ordered]@{
    schemaVersion = 1
    mode = "current-pid-coordinate-anchor-batch-reacquisition"
    status = if ($promotionReady) { "promotion-candidate-found" } elseif ($capturedPoseCount -ge 2) { "captured-but-no-promotion-candidate" } else { "insufficient-captured-poses" }
    ok = $promotionReady
    generatedAtUtc = (Get-Date).ToUniversalTime().ToString("o")
    target = [ordered]@{
        processName = $ProcessName
        processId = $RiftPid
        targetWindowHandle = $RiftHwnd
        title = $targetInfo.Title
    }
    candidateFile = $candidatePath
    poseCountRequested = $PoseCount
    capturedPoseCount = $capturedPoseCount
    movementSentCount = $movementSentCount
    noMovementMode = [bool]$NoMovement.IsPresent
    minimumPromotionPoseSupport = $MinimumPromotionPoseSupport
    minimumMovementPulsesForPromotion = $MinimumMovementPulsesForPromotion
    movementEvidenceSatisfied = $movementEvidenceSatisfied
    topCandidate = $topCandidate
    rankedCandidates = @($rankedCandidates | Select-Object -First 25)
    poseResults = @($poseResults.ToArray())
    artifacts = [ordered]@{
        runRoot = $runRoot
        childOutputs = $childRoot
        summaryJson = $summaryJson
        summaryMarkdown = $summaryMarkdown
    }
    safety = [ordered]@{
        movementSent = ($movementSentCount -gt 0)
        inputSent = ($movementSentCount -gt 0)
        automaticEscUsed = $false
        reloaduiSent = $false
        screenshotKeySent = $false
        noCheatEngine = $true
        savedVariablesLiveTruthUsed = $false
        githubConnectorWrites = $false
    }
    next = [ordered]@{
        recommendedAction = if ($promotionReady) { "Review topCandidate and promote/rebuild current proof anchor with current PID/HWND using this batch summary." } else { "Collect more displaced poses or inspect rankedCandidates; do not promote a current proof anchor yet." }
    }
}

$summary | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $summaryJson -Encoding UTF8

@"
# Current-PID coordinate anchor batch reacquisition

| Field | Value |
|---|---|
| Status | `$($summary.status)` |
| Target | `$ProcessName PID $RiftPid HWND $RiftHwnd` |
| Candidate file | `$candidatePath` |
| Poses requested | `$PoseCount` |
| Captured poses | `$capturedPoseCount` |
| Movement pulses sent | `$movementSentCount` |
| Movement evidence satisfied | `$movementEvidenceSatisfied` |
| Top candidate | `$topCandidateId $topCandidateAddressHex` |
| Top support poses | `$topCandidateSupportPoseCount` |
| Promotion ready | `$promotionReady` |
| Summary JSON | `$summaryJson` |
"@ | Set-Content -LiteralPath $summaryMarkdown -Encoding UTF8

if ($Json.IsPresent) {
    Get-Content -LiteralPath $summaryJson -Raw
}
else {
    Write-Host ""
    Write-Host "=== Current-PID coordinate anchor batch summary ===" -ForegroundColor Cyan
    Write-Host ("Status        : {0}" -f $summary.status)
    Write-Host ("Captured poses: {0}/{1}" -f $capturedPoseCount, $PoseCount)
    Write-Host ("Movement sent : {0}" -f $movementSentCount)
    Write-Host ("Movement gate : {0}" -f $movementEvidenceSatisfied)
    if ($null -ne $topCandidate) {
        Write-Host ("Top candidate : {0} {1}" -f $topCandidate.candidateId, $topCandidate.candidateAddressHex)
        Write-Host ("Top support   : {0} poses" -f $topCandidate.supportPoseCount)
        Write-Host ("Top max delta : {0}" -f $topCandidate.maxReferenceMaxAbsDelta)
    }
    Write-Host ("Promotion ready: {0}" -f $promotionReady)
    Write-Host ("Summary JSON  : {0}" -f $summaryJson)
}

# END_OF_SCRIPT_MARKER
