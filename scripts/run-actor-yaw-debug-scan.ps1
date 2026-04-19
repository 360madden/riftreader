[CmdletBinding()]
param(
    [switch]$Json,
    [string]$ProcessName = 'rift_x64',
    [int]$MaxHits = 8,
    [int]$TopCount = 4,
    [string]$OrientationCandidateLedgerFile = (Join-Path $(if ($PSScriptRoot) { $PSScriptRoot } elseif ($PSCommandPath) { Split-Path -Parent $PSCommandPath } else { (Get-Location).Path }) 'captures\actor-orientation-candidate-ledger.ndjson'),
    [string]$StimulusKey = 'Right',
    [ValidateSet('PostMessage', 'SendInput', 'AutoHotkey', 'Manual')]
    [string]$StimulusMode = 'PostMessage',
    [int]$HoldMilliseconds = 700,
    [int]$WaitMilliseconds = 250,
    [int]$ForegroundActivationSettleMilliseconds = 500,
    [int]$ManualWindowMilliseconds = 0,
    [switch]$SkipStimulus,
    [ValidateSet('X', 'Y', 'Z')]
    [string]$WatchComponent = 'X',
    [ValidateSet('Access', 'Write')]
    [string]$DebugMode = 'Access',
    [int]$DebugTimeoutMs = 4000,
    [int]$DebugMaxHits = 4,
    [string]$OutputDirectory
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptRoot = if ($PSScriptRoot) {
    $PSScriptRoot
}
elseif ($PSCommandPath) {
    Split-Path -Parent $PSCommandPath
}
else {
    (Get-Location).Path
}

$repoRoot = (Resolve-Path (Join-Path $scriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$pwshExe = try {
    $currentProcessPath = (Get-Process -Id $PID -ErrorAction Stop).Path
    if ([string]::IsNullOrWhiteSpace($currentProcessPath)) {
        (Get-Command pwsh -ErrorAction Stop).Source
    }
    else {
        $currentProcessPath
    }
}
catch {
    (Get-Command pwsh -ErrorAction Stop).Source
}

$inspectDebugStateScript = Join-Path $scriptRoot 'inspect-rift-debug-state.ps1'
$readPlayerCurrentScript = Join-Path $scriptRoot 'read-player-current.ps1'
$findPlayerOrientationCandidateScript = Join-Path $scriptRoot 'find-player-orientation-candidate.ps1'
$testActorYawCandidatesScript = Join-Path $scriptRoot 'test-actor-yaw-candidates.ps1'
$updateOrientationCandidateLedgerScript = Join-Path $scriptRoot 'update-orientation-candidate-ledger.ps1'

$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$resolvedOutputDirectory = if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    [System.IO.Path]::GetFullPath((Join-Path $scriptRoot "captures\actor-yaw-debug\$timestamp"))
}
else {
    [System.IO.Path]::GetFullPath($OutputDirectory)
}

$candidateSearchFile = Join-Path $resolvedOutputDirectory 'player-orientation-candidate-search.json'
$candidateTestFile = Join-Path $resolvedOutputDirectory 'actor-yaw-candidate-test.json'
$debugTraceDirectory = Join-Path $resolvedOutputDirectory 'debug-trace'
$summaryFile = Join-Path $resolvedOutputDirectory 'actor-yaw-debug-workflow.json'

New-Item -ItemType Directory -Path $resolvedOutputDirectory -Force | Out-Null

function Test-CommandSupportsParameter {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,

        [Parameter(Mandatory = $true)]
        [string]$ParameterName
    )

    $command = Get-Command $Name -ErrorAction Stop
    return $command.Parameters.ContainsKey($ParameterName)
}

function ConvertFrom-JsonText {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Text
    )

    function Invoke-JsonParse {
        param(
            [Parameter(Mandatory = $true)]
            [string]$CandidateText
        )

        if (Test-CommandSupportsParameter -Name 'Microsoft.PowerShell.Utility\ConvertFrom-Json' -ParameterName 'Depth') {
            return ($CandidateText | Microsoft.PowerShell.Utility\ConvertFrom-Json -Depth 100)
        }

        return ($CandidateText | Microsoft.PowerShell.Utility\ConvertFrom-Json)
    }

    $trimmedText = $Text.Trim()
    $originalError = $null
    try {
        return (Invoke-JsonParse -CandidateText $trimmedText)
    }
    catch {
        $originalError = $_
    }

    $lines = $trimmedText -split "\r?\n"
    for ($index = 0; $index -lt $lines.Length; $index++) {
        $line = $lines[$index].TrimStart()
        if (-not ($line.StartsWith('{') -or $line.StartsWith('['))) {
            continue
        }

        $candidateText = ($lines[$index..($lines.Length - 1)] -join [Environment]::NewLine).Trim()
        if ([string]::IsNullOrWhiteSpace($candidateText)) {
            continue
        }

        try {
            return (Invoke-JsonParse -CandidateText $candidateText)
        }
        catch {
            continue
        }
    }

    throw $originalError
}

function ConvertTo-JsonText {
    param(
        [Parameter(Mandatory = $true)]
        [object]$InputObject
    )

    if (Test-CommandSupportsParameter -Name 'Microsoft.PowerShell.Utility\ConvertTo-Json' -ParameterName 'Depth') {
        return ($InputObject | Microsoft.PowerShell.Utility\ConvertTo-Json -Depth 100)
    }

    return ($InputObject | Microsoft.PowerShell.Utility\ConvertTo-Json)
}

function Parse-HexUInt64 {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    $normalized = $Value.Trim()
    if ($normalized.StartsWith('0x', [System.StringComparison]::OrdinalIgnoreCase)) {
        $normalized = $normalized.Substring(2)
    }

    return [UInt64]::Parse($normalized, [System.Globalization.NumberStyles]::HexNumber, [System.Globalization.CultureInfo]::InvariantCulture)
}

function Format-HexUInt64 {
    param(
        [Parameter(Mandatory = $true)]
        [UInt64]$Value
    )

    return ('0x{0:X}' -f $Value)
}

function Get-PropertyValue {
    param(
        [Parameter(Mandatory = $true)]
        [object]$InputObject,

        [Parameter(Mandatory = $true)]
        [string]$PropertyName
    )

    if ($null -eq $InputObject) {
        return $null
    }

    $property = $InputObject.PSObject.Properties[$PropertyName]
    if ($null -eq $property) {
        return $null
    }

    return $property.Value
}

function Invoke-ExternalCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,

        [string[]]$Arguments = @(),

        [Parameter(Mandatory = $true)]
        [string]$Label
    )

    $output = & $FilePath @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    $text = (($output | ForEach-Object {
                if ($null -eq $_) {
                    ''
                }
                else {
                    $_.ToString()
                }
            }) -join [Environment]::NewLine).Trim()

    return [pscustomobject]@{
        Label = $Label
        ExitCode = $exitCode
        Text = $text
    }
}

function Invoke-RepoPowerShellScript {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ScriptPath,

        [string[]]$Arguments = @(),

        [Parameter(Mandatory = $true)]
        [string]$Label
    )

    if (-not (Test-Path -LiteralPath $ScriptPath)) {
        throw "Required script was not found: $ScriptPath"
    }

    $commandArguments = @(
        '-NoLogo',
        '-NoProfile',
        '-ExecutionPolicy',
        'Bypass',
        '-File',
        $ScriptPath
    )
    if ($Arguments.Count -gt 0) {
        $commandArguments += $Arguments
    }

    $result = Invoke-ExternalCommand -FilePath $pwshExe -Arguments $commandArguments -Label $Label

    if ($result.ExitCode -ne 0) {
        throw "$Label failed with exit code $($result.ExitCode). $($result.Text)"
    }

    return $result.Text
}

function Invoke-RepoPowerShellScriptJson {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ScriptPath,

        [string[]]$Arguments = @(),

        [Parameter(Mandatory = $true)]
        [string]$Label
    )

    $text = Invoke-RepoPowerShellScript -ScriptPath $ScriptPath -Arguments $Arguments -Label $Label
    if ([string]::IsNullOrWhiteSpace($text)) {
        throw "$Label returned no JSON payload."
    }

    return (ConvertFrom-JsonText -Text $text)
}

function Invoke-ReaderJson {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        [Parameter(Mandatory = $true)]
        [string]$Label
    )

    if (-not (Test-Path -LiteralPath $readerProject)) {
        throw "Reader project was not found: $readerProject"
    }

    $commandArguments = @(
        'run',
        '--project',
        $readerProject,
        '--'
    )
    if ($Arguments.Count -gt 0) {
        $commandArguments += $Arguments
    }

    $result = Invoke-ExternalCommand -FilePath 'dotnet' -Arguments $commandArguments -Label $Label

    if ($result.ExitCode -ne 0) {
        throw "$Label failed with exit code $($result.ExitCode). $($result.Text)"
    }

    if ([string]::IsNullOrWhiteSpace($result.Text)) {
        throw "$Label returned no JSON payload."
    }

    return (ConvertFrom-JsonText -Text $result.Text)
}

function Get-DebugStateSummary {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RawOutput
    )

    $processDetected = -not [string]::IsNullOrWhiteSpace($RawOutput) -and $RawOutput -notmatch 'No running process matched'
    $alreadyDebugged = $RawOutput -match 'already debugged' -or $RawOutput -match 'already marked as debugged'
    $helperMatches = [regex]::Matches($RawOutput, '(?im)\b([A-Za-z0-9_.-]+\.exe)\s+\[(\d+)\]')
    $attachHelpers = @()
    foreach ($match in $helperMatches) {
        $value = $match.Value.Trim()
        if ([string]::IsNullOrWhiteSpace($value)) {
            continue
        }

        if ($attachHelpers -notcontains $value) {
            $attachHelpers += $value
        }
    }

    $commandLineMatches = [regex]::Matches($RawOutput, '(?im)^\[RiftDebug\] Attach helper command line:\s*(.+)$')
    $commandLines = @($commandLineMatches | ForEach-Object { $_.Groups[1].Value.Trim() } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })

    return [pscustomobject]@{
        ProcessDetected = $processDetected
        AlreadyDebugged = $alreadyDebugged
        AttachHelpers = $attachHelpers
        AttachHelperCommandLines = $commandLines
        RawOutput = $RawOutput
    }
}

function Get-PlayerCurrentSummary {
    param(
        [Parameter(Mandatory = $true)]
        [object]$PlayerCurrent
    )

    $memory = Get-PropertyValue -InputObject $PlayerCurrent -PropertyName 'Memory'

    return [pscustomobject]@{
        ProcessName = Get-PropertyValue -InputObject $PlayerCurrent -PropertyName 'ProcessName'
        ProcessId = Get-PropertyValue -InputObject $PlayerCurrent -PropertyName 'ProcessId'
        SelectionSource = Get-PropertyValue -InputObject $PlayerCurrent -PropertyName 'SelectionSource'
        AnchorProvenance = Get-PropertyValue -InputObject $PlayerCurrent -PropertyName 'AnchorProvenance'
        AddressHex = Get-PropertyValue -InputObject $memory -PropertyName 'AddressHex'
        Level = Get-PropertyValue -InputObject $memory -PropertyName 'Level'
        Health = Get-PropertyValue -InputObject $memory -PropertyName 'Health'
        CoordX = Get-PropertyValue -InputObject $memory -PropertyName 'CoordX'
        CoordY = Get-PropertyValue -InputObject $memory -PropertyName 'CoordY'
        CoordZ = Get-PropertyValue -InputObject $memory -PropertyName 'CoordZ'
    }
}

function Get-CoordAnchorSummary {
    param(
        [Parameter(Mandatory = $true)]
        [object]$CoordAnchor
    )

    $modulePattern = Get-PropertyValue -InputObject $CoordAnchor -PropertyName 'ModulePattern'

    return [pscustomobject]@{
        TraceMatchesProcess = Get-PropertyValue -InputObject $CoordAnchor -PropertyName 'TraceMatchesProcess'
        CandidateAddress = Get-PropertyValue -InputObject $CoordAnchor -PropertyName 'CandidateAddress'
        CandidateSource = Get-PropertyValue -InputObject $CoordAnchor -PropertyName 'CandidateSource'
        TargetAddress = Get-PropertyValue -InputObject $CoordAnchor -PropertyName 'TargetAddress'
        EffectiveAddress = Get-PropertyValue -InputObject $CoordAnchor -PropertyName 'EffectiveAddress'
        BaseRegister = Get-PropertyValue -InputObject $CoordAnchor -PropertyName 'BaseRegister'
        BaseRegisterValue = Get-PropertyValue -InputObject $CoordAnchor -PropertyName 'BaseRegisterValue'
        ObjectBaseAddress = Get-PropertyValue -InputObject $CoordAnchor -PropertyName 'ObjectBaseAddress'
        InferredCoordBaseRelativeOffset = Get-PropertyValue -InputObject $CoordAnchor -PropertyName 'InferredCoordBaseRelativeOffset'
        CoordXRelativeOffset = Get-PropertyValue -InputObject $CoordAnchor -PropertyName 'CoordXRelativeOffset'
        CoordYRelativeOffset = Get-PropertyValue -InputObject $CoordAnchor -PropertyName 'CoordYRelativeOffset'
        CoordZRelativeOffset = Get-PropertyValue -InputObject $CoordAnchor -PropertyName 'CoordZRelativeOffset'
        SourceObjectRegister = Get-PropertyValue -InputObject $CoordAnchor -PropertyName 'SourceObjectRegister'
        SourceObjectAddress = Get-PropertyValue -InputObject $CoordAnchor -PropertyName 'SourceObjectAddress'
        SourceCoordRelativeOffset = Get-PropertyValue -InputObject $CoordAnchor -PropertyName 'SourceCoordRelativeOffset'
        InstructionAddress = Get-PropertyValue -InputObject $CoordAnchor -PropertyName 'InstructionAddress'
        ModulePattern = if ($null -eq $modulePattern) {
            $null
        }
        else {
            [pscustomobject]@{
                Found = Get-PropertyValue -InputObject $modulePattern -PropertyName 'Found'
                Address = Get-PropertyValue -InputObject $modulePattern -PropertyName 'Address'
                RelativeOffsetHex = Get-PropertyValue -InputObject $modulePattern -PropertyName 'RelativeOffsetHex'
            }
        }
    }
}

function Get-SearchCandidateBrief {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Candidate
    )

    return [pscustomobject]@{
        SourceAddress = [string](Get-PropertyValue -InputObject $Candidate -PropertyName 'Address')
        BasisForwardOffset = [string](Get-PropertyValue -InputObject $Candidate -PropertyName 'BasisPrimaryForwardOffset')
        DiscoveryMode = [string](Get-PropertyValue -InputObject $Candidate -PropertyName 'DiscoveryMode')
        ParentAddress = [string](Get-PropertyValue -InputObject $Candidate -PropertyName 'ParentAddress')
        ParentFamilyId = [string](Get-PropertyValue -InputObject $Candidate -PropertyName 'ParentFamilyId')
        RootAddress = [string](Get-PropertyValue -InputObject $Candidate -PropertyName 'RootAddress')
        RootSource = [string](Get-PropertyValue -InputObject $Candidate -PropertyName 'RootSource')
        SearchScore = Get-PropertyValue -InputObject $Candidate -PropertyName 'Score'
        HopDepth = Get-PropertyValue -InputObject $Candidate -PropertyName 'HopDepth'
        LedgerPenalty = Get-PropertyValue -InputObject $Candidate -PropertyName 'LedgerPenalty'
        LedgerRejectionReason = [string](Get-PropertyValue -InputObject $Candidate -PropertyName 'LedgerRejectionReason')
        LedgerFamilyKey = [string](Get-PropertyValue -InputObject $Candidate -PropertyName 'LedgerFamilyKey')
        LedgerFamilyPenalty = Get-PropertyValue -InputObject $Candidate -PropertyName 'LedgerFamilyPenalty'
        LedgerFamilyBonus = Get-PropertyValue -InputObject $Candidate -PropertyName 'LedgerFamilyBonus'
    }
}

function Get-CandidateSearchSummary {
    param(
        [Parameter(Mandatory = $true)]
        [object]$CandidateSearch,

        [Parameter(Mandatory = $true)]
        [string]$CandidateSearchFile,

        [string]$OrientationCandidateLedgerFile
    )

    $bestCandidate = Get-PropertyValue -InputObject $CandidateSearch -PropertyName 'BestCandidate'
    $bestPointerHopCandidate = Get-PropertyValue -InputObject $CandidateSearch -PropertyName 'BestPointerHopCandidate'

    return [pscustomobject]@{
        SearchArtifactFile = $CandidateSearchFile
        EvidenceState = 'live-search'
        CandidateCount = [int](Get-PropertyValue -InputObject $CandidateSearch -PropertyName 'CandidateCount')
        PointerHopCandidateCount = [int](Get-PropertyValue -InputObject $CandidateSearch -PropertyName 'PointerHopCandidateCount')
        LedgerFile = if ([string]::IsNullOrWhiteSpace($OrientationCandidateLedgerFile)) { $null } else { [System.IO.Path]::GetFullPath($OrientationCandidateLedgerFile) }
        BestCandidate = if ($null -eq $bestCandidate) { $null } else { Get-SearchCandidateBrief -Candidate $bestCandidate }
        BestPointerHopCandidate = if ($null -eq $bestPointerHopCandidate) { $null } else { Get-SearchCandidateBrief -Candidate $bestPointerHopCandidate }
        Notes = @(
            @(Get-PropertyValue -InputObject $CandidateSearch -PropertyName 'Notes') |
                Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) } |
                ForEach-Object { [string]$_ })
    }
}

function Get-CandidateProofSummary {
    param(
        [object]$CandidateTest,
        [string]$CandidateTestFile,
        [string]$StimulusKey,
        [string]$StimulusMode,
        [switch]$SkipStimulus,
        [int]$HoldMilliseconds,
        [int]$WaitMilliseconds,
        [int]$ForegroundActivationSettleMilliseconds,
        [int]$ManualWindowMilliseconds,
        [string]$ErrorMessage
    )

    if ($null -eq $CandidateTest) {
        return [pscustomobject]@{
            ProofArtifactFile = $CandidateTestFile
            Attempted = $true
            Succeeded = $false
            Error = $ErrorMessage
            StimulusKey = $StimulusKey
            StimulusMode = $StimulusMode
            SkipStimulus = ($SkipStimulus -or $StimulusMode -eq 'Manual')
            StimulusApplied = -not ($SkipStimulus -or $StimulusMode -eq 'Manual')
            ManualWindowMilliseconds = $ManualWindowMilliseconds
            HoldMilliseconds = $HoldMilliseconds
            WaitMilliseconds = $WaitMilliseconds
            ForegroundActivationSettleMilliseconds = $ForegroundActivationSettleMilliseconds
            MinYawResponseDegrees = $null
            MaxCoordDrift = $null
            CandidateCount = 0
            TruthLikeCandidateCount = 0
            TurnObserved = $false
            TurnVerification = $null
            StimulusWindowState = $null
            FamilySummaries = @()
            BestTruthLikeCandidate = $null
            Notes = @()
        }
    }

    $bestTruthLikeCandidate = Get-PropertyValue -InputObject $CandidateTest -PropertyName 'BestTruthLikeCandidate'

    return [pscustomobject]@{
        ProofArtifactFile = $CandidateTestFile
        Attempted = $true
        Succeeded = $true
        Error = $null
        StimulusKey = [string](Get-PropertyValue -InputObject $CandidateTest -PropertyName 'StimulusKey')
        StimulusMode = [string](Get-PropertyValue -InputObject $CandidateTest -PropertyName 'StimulusMode')
        SkipStimulus = [bool](Get-PropertyValue -InputObject $CandidateTest -PropertyName 'SkipStimulus')
        StimulusApplied = [bool](Get-PropertyValue -InputObject $CandidateTest -PropertyName 'StimulusApplied')
        ManualWindowMilliseconds = Get-PropertyValue -InputObject $CandidateTest -PropertyName 'ManualWindowMilliseconds'
        HoldMilliseconds = Get-PropertyValue -InputObject $CandidateTest -PropertyName 'HoldMilliseconds'
        WaitMilliseconds = Get-PropertyValue -InputObject $CandidateTest -PropertyName 'WaitMilliseconds'
        ForegroundActivationSettleMilliseconds = Get-PropertyValue -InputObject $CandidateTest -PropertyName 'ForegroundActivationSettleMilliseconds'
        MinYawResponseDegrees = Get-PropertyValue -InputObject $CandidateTest -PropertyName 'MinYawResponseDegrees'
        MaxCoordDrift = Get-PropertyValue -InputObject $CandidateTest -PropertyName 'MaxCoordDrift'
        CandidateCount = [int](Get-PropertyValue -InputObject $CandidateTest -PropertyName 'CandidateCount')
        TruthLikeCandidateCount = [int](Get-PropertyValue -InputObject $CandidateTest -PropertyName 'TruthLikeCandidateCount')
        TurnObserved = [bool](Get-PropertyValue -InputObject $CandidateTest -PropertyName 'TurnObserved')
        TurnVerification = Get-PropertyValue -InputObject $CandidateTest -PropertyName 'TurnVerification'
        StimulusWindowState = Get-PropertyValue -InputObject $CandidateTest -PropertyName 'StimulusWindowState'
        FamilySummaries = @(
            @(Get-PropertyValue -InputObject $CandidateTest -PropertyName 'FamilySummaries'))
        BestTruthLikeCandidate = if ($null -eq $bestTruthLikeCandidate) { $null } else { Get-NormalizedCandidateFromTest -Candidate $bestTruthLikeCandidate }
        Notes = @(
            @(Get-PropertyValue -InputObject $CandidateTest -PropertyName 'Notes') |
                Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) } |
                ForEach-Object { [string]$_ })
    }
}

function New-EvidenceStageRecord {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Stage,

        [Parameter(Mandatory = $true)]
        [string]$State,

        [Parameter(Mandatory = $true)]
        [string]$Reason,

        [bool]$Blocking = $false,

        [object]$Details = $null
    )

    return [pscustomobject]@{
        Stage = $Stage
        State = $State
        Blocking = $Blocking
        Reason = $Reason
        Details = $Details
    }
}

function New-DegradedStateRecord {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Stage,

        [Parameter(Mandatory = $true)]
        [string]$State,

        [Parameter(Mandatory = $true)]
        [string]$Reason,

        [bool]$Blocking = $true,

        [object]$Details = $null
    )

    return [pscustomobject]@{
        Stage = $Stage
        State = $State
        Blocking = $Blocking
        Reason = $Reason
        Details = $Details
    }
}

function Remove-StageRecords {
    param(
        [Parameter(Mandatory = $true)]
        [System.Collections.Generic.List[object]]$Records,

        [Parameter(Mandatory = $true)]
        [string]$Stage
    )

    for ($index = $Records.Count - 1; $index -ge 0; $index--) {
        $recordStage = [string](Get-PropertyValue -InputObject $Records[$index] -PropertyName 'Stage')
        if ($recordStage -eq $Stage) {
            $Records.RemoveAt($index)
        }
    }
}

function Get-CoordAnchorAssessment {
    param(
        [object]$CoordAnchorSummary
    )

    $state = 'verified-pattern'
    $reason = 'Coord-anchor truth matched the current process and module pattern.'
    $blocking = $false
    $shouldDegrade = $false

    if ($null -eq $CoordAnchorSummary -or $CoordAnchorSummary.TraceMatchesProcess -ne $true) {
        $state = 'process-mismatch'
        $reason = 'Coord-anchor truth did not match the current process.'
        $blocking = $true
        $shouldDegrade = $true
    }
    elseif ($null -eq $CoordAnchorSummary.ModulePattern -or $CoordAnchorSummary.ModulePattern.Found -ne $true) {
        $state = 'pattern-unverified'
        $reason = 'Coord-anchor module pattern was not verified for the current run.'
        $blocking = $true
        $shouldDegrade = $true
    }

    return [pscustomobject]@{
        State = $state
        Reason = $reason
        Blocking = $blocking
        ShouldDegrade = $shouldDegrade
    }
}

function Get-PromotionAssessment {
    param(
        [object[]]$DegradedStates,
        [object]$SelectedCandidate,
        [object]$CandidateProofSummary,
        [object]$CoordAnchorSummary
    )

    $blockingReasons = New-Object System.Collections.Generic.List[string]
    foreach ($state in @($DegradedStates)) {
        if ($null -eq $state -or $state.Blocking -ne $true) {
            continue
        }

        $reason = [string]$state.Reason
        if (-not [string]::IsNullOrWhiteSpace($reason) -and -not $blockingReasons.Contains($reason)) {
            $blockingReasons.Add($reason) | Out-Null
        }
    }

    if ($null -eq $SelectedCandidate) {
        $blockingReasons.Add('No selected candidate was available for truth promotion.') | Out-Null
    }
    elseif ([string]$SelectedCandidate.SelectionSource -ne 'candidate-proof-truth-like' -or -not [bool]$SelectedCandidate.TruthLike) {
        $reason = 'The selected candidate was not confirmed by a truth-like proof result.'
        if (-not $blockingReasons.Contains($reason)) {
            $blockingReasons.Add($reason) | Out-Null
        }
    }

    if ($null -eq $CandidateProofSummary -or -not [bool]$CandidateProofSummary.Succeeded) {
        $reason = 'Turn-based candidate proof did not complete successfully.'
        if (-not $blockingReasons.Contains($reason)) {
            $blockingReasons.Add($reason) | Out-Null
        }
    }

    if ($null -eq $CoordAnchorSummary -or $CoordAnchorSummary.TraceMatchesProcess -ne $true) {
        $reason = 'Coord-anchor truth did not verify against the current process.'
        if (-not $blockingReasons.Contains($reason)) {
            $blockingReasons.Add($reason) | Out-Null
        }
    }

    $modulePatternFound = $false
    if ($null -ne $CoordAnchorSummary -and
        $CoordAnchorSummary.PSObject.Properties['ModulePattern'] -and
        $null -ne $CoordAnchorSummary.ModulePattern) {
        $modulePatternFound = ($CoordAnchorSummary.ModulePattern.Found -eq $true)
    }

    if (-not $modulePatternFound) {
        $reason = 'Coord-anchor module pattern was not verified for the current run.'
        if (-not $blockingReasons.Contains($reason)) {
            $blockingReasons.Add($reason) | Out-Null
        }
    }

    $promotionReady = ($blockingReasons.Count -eq 0)

    return [pscustomobject]@{
        PromotionReady = $promotionReady
        State = if ($promotionReady) { 'promotion-ready' } elseif ($null -eq $SelectedCandidate) { 'no-candidate' } else { 'blocked' }
        SelectedCandidateSource = if ($null -eq $SelectedCandidate) { $null } else { [string]$SelectedCandidate.SelectionSource }
        BlockingReasons = @($blockingReasons.ToArray())
        Guidance = if ($promotionReady) {
            'Promotion-ready evidence is present. Repo truth docs may be updated from this workflow summary.'
        }
        else {
            'Keep actor orientation stale or provisional in repo truth docs until a promotion-ready workflow summary exists.'
        }
    }
}

function Get-NormalizedCandidateFromTest {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Candidate
    )

    return [pscustomobject]@{
        SelectionSource = 'candidate-proof-truth-like'
        CandidateFamilyKey = [string](Get-PropertyValue -InputObject $Candidate -PropertyName 'CandidateFamilyKey')
        SourceAddress = [string](Get-PropertyValue -InputObject $Candidate -PropertyName 'SourceAddress')
        BasisForwardOffset = [string](Get-PropertyValue -InputObject $Candidate -PropertyName 'BasisForwardOffset')
        DiscoveryMode = [string](Get-PropertyValue -InputObject $Candidate -PropertyName 'DiscoveryMode')
        ParentAddress = [string](Get-PropertyValue -InputObject $Candidate -PropertyName 'ParentAddress')
        RootAddress = [string](Get-PropertyValue -InputObject $Candidate -PropertyName 'RootAddress')
        SearchScore = Get-PropertyValue -InputObject $Candidate -PropertyName 'SearchScore'
        TruthLike = [bool](Get-PropertyValue -InputObject $Candidate -PropertyName 'TruthLike')
        CandidateResponsive = Get-PropertyValue -InputObject $Candidate -PropertyName 'CandidateResponsive'
        PlayerStayedMostlyStill = Get-PropertyValue -InputObject $Candidate -PropertyName 'PlayerStayedMostlyStill'
        YawDeltaDegrees = Get-PropertyValue -InputObject $Candidate -PropertyName 'YawDeltaDegrees'
        PitchDeltaDegrees = Get-PropertyValue -InputObject $Candidate -PropertyName 'PitchDeltaDegrees'
        PlayerCoordDeltaMagnitude = Get-PropertyValue -InputObject $Candidate -PropertyName 'PlayerCoordDeltaMagnitude'
        CandidateRejectedReason = [string](Get-PropertyValue -InputObject $Candidate -PropertyName 'CandidateRejectedReason')
        TruthLikeEvidence = Get-PropertyValue -InputObject $Candidate -PropertyName 'TruthLikeEvidence'
    }
}

function Get-NormalizedCandidateFromPointerHopSearch {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Candidate
    )

    return [pscustomobject]@{
        SelectionSource = 'candidate-search-best-pointer-hop'
        CandidateFamilyKey = Get-CandidateFamilyKey -Candidate $Candidate -AddressPropertyName 'Address' -ForwardOffsetPropertyName 'BasisPrimaryForwardOffset'
        SourceAddress = [string](Get-PropertyValue -InputObject $Candidate -PropertyName 'Address')
        BasisForwardOffset = [string](Get-PropertyValue -InputObject $Candidate -PropertyName 'BasisPrimaryForwardOffset')
        DiscoveryMode = [string](Get-PropertyValue -InputObject $Candidate -PropertyName 'DiscoveryMode')
        ParentAddress = [string](Get-PropertyValue -InputObject $Candidate -PropertyName 'ParentAddress')
        RootAddress = [string](Get-PropertyValue -InputObject $Candidate -PropertyName 'RootAddress')
        SearchScore = Get-PropertyValue -InputObject $Candidate -PropertyName 'Score'
        TruthLike = $false
        CandidateResponsive = $null
        PlayerStayedMostlyStill = $null
        YawDeltaDegrees = $null
        PitchDeltaDegrees = $null
        PlayerCoordDeltaMagnitude = $null
        CandidateRejectedReason = [string](Get-PropertyValue -InputObject $Candidate -PropertyName 'LedgerRejectionReason')
        TruthLikeEvidence = $null
    }
}

function Get-NormalizedCandidateFromLocalSearch {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Candidate
    )

    $probeRootAddress = [string](Get-PropertyValue -InputObject $Candidate -PropertyName 'ProbeRootAddress')

    return [pscustomobject]@{
        SelectionSource = 'candidate-search-best-local'
        CandidateFamilyKey = Get-CandidateFamilyKey -Candidate $Candidate -AddressPropertyName 'Address' -ForwardOffsetPropertyName 'BasisPrimaryForwardOffset'
        SourceAddress = [string](Get-PropertyValue -InputObject $Candidate -PropertyName 'Address')
        BasisForwardOffset = [string](Get-PropertyValue -InputObject $Candidate -PropertyName 'BasisPrimaryForwardOffset')
        DiscoveryMode = [string](Get-PropertyValue -InputObject $Candidate -PropertyName 'DiscoveryMode')
        ParentAddress = $probeRootAddress
        RootAddress = $probeRootAddress
        SearchScore = Get-PropertyValue -InputObject $Candidate -PropertyName 'Score'
        TruthLike = $false
        CandidateResponsive = $null
        PlayerStayedMostlyStill = $null
        YawDeltaDegrees = $null
        PitchDeltaDegrees = $null
        PlayerCoordDeltaMagnitude = $null
        CandidateRejectedReason = $null
        TruthLikeEvidence = $null
    }
}

function Resolve-WatchedAddress {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Candidate,

        [Parameter(Mandatory = $true)]
        [ValidateSet('X', 'Y', 'Z')]
        [string]$Component
    )

    $sourceAddress = Parse-HexUInt64 -Value ([string]$Candidate.SourceAddress)
    $basisForwardOffset = Parse-HexUInt64 -Value ([string]$Candidate.BasisForwardOffset)
    $componentOffset = switch ($Component) {
        'X' { [UInt64]0 }
        'Y' { [UInt64]4 }
        'Z' { [UInt64]8 }
        default { throw "Unsupported watch component '$Component'." }
    }

    return (Format-HexUInt64 -Value ($sourceAddress + $basisForwardOffset + $componentOffset))
}

function Get-CandidateFamilyKey {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Candidate,

        [string]$AddressPropertyName = 'SourceAddress',

        [string]$ForwardOffsetPropertyName = 'BasisForwardOffset'
    )

    $rootAddress = [string](Get-PropertyValue -InputObject $Candidate -PropertyName 'RootAddress')
    if ([string]::IsNullOrWhiteSpace($rootAddress)) {
        $rootAddress = [string](Get-PropertyValue -InputObject $Candidate -PropertyName 'ParentAddress')
    }

    if ([string]::IsNullOrWhiteSpace($rootAddress)) {
        $rootAddress = [string](Get-PropertyValue -InputObject $Candidate -PropertyName $AddressPropertyName)
    }

    $discoveryMode = [string](Get-PropertyValue -InputObject $Candidate -PropertyName 'DiscoveryMode')
    if ([string]::IsNullOrWhiteSpace($discoveryMode)) {
        $discoveryMode = 'unknown'
    }

    $basisForwardOffset = [string](Get-PropertyValue -InputObject $Candidate -PropertyName $ForwardOffsetPropertyName)
    if ([string]::IsNullOrWhiteSpace($basisForwardOffset)) {
        $basisForwardOffset = 'unknown'
    }

    return ('{0}|{1}|{2}' -f $discoveryMode.ToLowerInvariant(), $basisForwardOffset.ToUpperInvariant(), $rootAddress.ToUpperInvariant())
}

function Get-DownRankedFamilyMap {
    param(
        [object]$CandidateTest
    )

    $map = @{}
    if ($null -eq $CandidateTest) {
        return $map
    }

    foreach ($family in @(Get-PropertyValue -InputObject $CandidateTest -PropertyName 'FamilySummaries')) {
        if ($null -eq $family) {
            continue
        }

        $familyKey = [string](Get-PropertyValue -InputObject $family -PropertyName 'CandidateFamilyKey')
        if ([string]::IsNullOrWhiteSpace($familyKey)) {
            continue
        }

        if ([bool](Get-PropertyValue -InputObject $family -PropertyName 'DownRanked')) {
            $map[$familyKey] = [pscustomobject]@{
                CandidateFamilyKey = $familyKey
                Reason = [string](Get-PropertyValue -InputObject $family -PropertyName 'DownRankReason')
                AggregateRejectedReasons = @(
                    @(Get-PropertyValue -InputObject $family -PropertyName 'AggregateRejectedReasons') |
                        Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) } |
                        ForEach-Object { [string]$_ })
            }
        }
    }

    return $map
}

function Get-BestSearchCandidateForDebug {
    param(
        [Parameter(Mandatory = $true)]
        [object]$CandidateSearch,

        [hashtable]$DownRankedFamilyMap
    )

    foreach ($candidate in @(Get-PropertyValue -InputObject $CandidateSearch -PropertyName 'PointerHopCandidates')) {
        if ($null -eq $candidate) {
            continue
        }

        $familyKey = Get-CandidateFamilyKey -Candidate $candidate -AddressPropertyName 'Address' -ForwardOffsetPropertyName 'BasisPrimaryForwardOffset'
        if ($null -eq $DownRankedFamilyMap -or -not $DownRankedFamilyMap.ContainsKey($familyKey)) {
            return (Get-NormalizedCandidateFromPointerHopSearch -Candidate $candidate)
        }
    }

    foreach ($candidate in @(Get-PropertyValue -InputObject $CandidateSearch -PropertyName 'Candidates')) {
        if ($null -eq $candidate) {
            continue
        }

        $familyKey = Get-CandidateFamilyKey -Candidate $candidate -AddressPropertyName 'Address' -ForwardOffsetPropertyName 'BasisPrimaryForwardOffset'
        if ($null -eq $DownRankedFamilyMap -or -not $DownRankedFamilyMap.ContainsKey($familyKey)) {
            return (Get-NormalizedCandidateFromLocalSearch -Candidate $candidate)
        }
    }

    return $null
}

function Write-WorkflowSummaryFile {
    param(
        [Parameter(Mandatory = $true)]
        [System.Collections.IDictionary]$Document,

        [Parameter(Mandatory = $true)]
        [System.Collections.Generic.List[string]]$NoteList,

        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $Document['Notes'] = @($NoteList.ToArray())
    $jsonText = ConvertTo-JsonText -InputObject $Document
    Set-Content -LiteralPath $Path -Value $jsonText -Encoding UTF8
}

function Write-TerminalSummary {
    param(
        [Parameter(Mandatory = $true)]
        [System.Collections.IDictionary]$Document,

        [Parameter(Mandatory = $true)]
        [string]$SummaryPath,

        [Parameter(Mandatory = $true)]
        [int]$ExitCode
    )

    $verdict = if ($ExitCode -eq 0) { '# **✅ RESULT**' } else { '# **⚠️ BLOCKER**' }
    Write-Host ''
    Write-Host $verdict
    Write-Host ''

    $rows = @(
        [pscustomobject]@{ Field = 'Status'; Value = [string]$Document.Status }
        [pscustomobject]@{ Field = 'Promotion'; Value = if ($null -eq $Document.Promotion) { 'n/a' } else { [string]$Document.Promotion.State } }
        [pscustomobject]@{ Field = 'Promotion ready'; Value = if ($null -eq $Document.Promotion) { 'False' } else { [string][bool]$Document.Promotion.PromotionReady } }
        [pscustomobject]@{ Field = 'Process'; Value = [string]$Document.ProcessName }
        [pscustomobject]@{ Field = 'Watch component'; Value = [string]$Document.WatchComponent }
        [pscustomobject]@{ Field = 'Watched address'; Value = [string]$Document.WatchedAddress }
        [pscustomobject]@{ Field = 'Debug mode'; Value = [string]$Document.DebugMode }
        [pscustomobject]@{ Field = 'Degraded states'; Value = @($Document.DegradedStates).Count }
        [pscustomobject]@{ Field = 'Summary file'; Value = $SummaryPath }
    )

    $rows | Format-Table -AutoSize

    if ($null -ne $Document.SelectedCandidate) {
        Write-Host ''
        @(
            [pscustomobject]@{ Field = 'Candidate source'; Value = [string]$Document.SelectedCandidate.SelectionSource }
            [pscustomobject]@{ Field = 'Source address'; Value = [string]$Document.SelectedCandidate.SourceAddress }
            [pscustomobject]@{ Field = 'Basis forward offset'; Value = [string]$Document.SelectedCandidate.BasisForwardOffset }
            [pscustomobject]@{ Field = 'Discovery mode'; Value = [string]$Document.SelectedCandidate.DiscoveryMode }
        ) | Format-Table -AutoSize
    }

    if ($null -ne $Document.Promotion -and @($Document.Promotion.BlockingReasons).Count -gt 0) {
        Write-Host ''
        Write-Host 'Promotion blockers'
        foreach ($reason in @($Document.Promotion.BlockingReasons)) {
            Write-Host ("- {0}" -f $reason)
        }
    }

    if (@($Document.Notes).Count -gt 0) {
        Write-Host ''
        foreach ($note in @($Document.Notes)) {
            Write-Host ("- {0}" -f $note)
        }
    }
}

$notes = New-Object System.Collections.Generic.List[string]
$evidenceStages = New-Object System.Collections.Generic.List[object]
$degradedStates = New-Object System.Collections.Generic.List[object]
$candidateTestError = $null
$candidateTest = $null
$summary = [ordered]@{
    Mode = 'actor-yaw-debug-workflow'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    Status = 'preflight-failed'
    ProcessName = $ProcessName
    OutputDirectory = $resolvedOutputDirectory
    ArtifactFiles = [pscustomobject]@{
        SummaryFile = $summaryFile
        CandidateSearchFile = $candidateSearchFile
        CandidateTestFile = $candidateTestFile
        DebugTraceDirectory = $debugTraceDirectory
        OrientationCandidateLedgerFile = if ([string]::IsNullOrWhiteSpace($OrientationCandidateLedgerFile)) { $null } else { [System.IO.Path]::GetFullPath($OrientationCandidateLedgerFile) }
    }
    SelectionPolicy = @(
        'candidate-proof-truth-like',
        'candidate-search-best-pointer-hop',
        'candidate-search-best-local')
    DebugState = $null
    PlayerCurrentSummary = $null
    CoordAnchorSummary = $null
    CoordAnchorRefresh = $null
    CandidateSearchSummary = $null
    CandidateProofSummary = $null
    LedgerUpdate = $null
    CandidateSearchFile = $candidateSearchFile
    CandidateTestFile = $candidateTestFile
    SelectedCandidate = $null
    WatchComponent = $WatchComponent
    WatchedAddress = $null
    DebugMode = if ($DebugMode -eq 'Access') { 'memory-access' } else { 'memory-write' }
    DebugTraceDirectory = $null
    DebugTraceSummary = $null
    EvidenceStages = @()
    DegradedStates = @()
    Promotion = $null
    Notes = @()
}

$exitCode = 0

try {
    $debugStateOutput = Invoke-RepoPowerShellScript -ScriptPath $inspectDebugStateScript -Arguments @('-ProcessName', $ProcessName) -Label 'inspect-rift-debug-state'
    $summary.DebugState = Get-DebugStateSummary -RawOutput $debugStateOutput

    if (-not $summary.DebugState.ProcessDetected) {
        $evidenceStages.Add((New-EvidenceStageRecord -Stage 'debug-preflight' -State 'process-missing' -Reason "Target process '$ProcessName' was not detected." -Blocking $true)) | Out-Null
        $degradedStates.Add((New-DegradedStateRecord -Stage 'debug-preflight' -State 'process-missing' -Reason "Target process '$ProcessName' was not detected.")) | Out-Null
        $notes.Add("Target process '$ProcessName' was not detected during debug preflight.") | Out-Null
        throw "Target process '$ProcessName' was not detected."
    }
    else {
        $preflightState = if ($summary.DebugState.AlreadyDebugged) { 'debugger-present' } else { 'ready' }
        $preflightReason = if ($summary.DebugState.AlreadyDebugged) {
            'Target process was detected, but a debugger relationship is already present.'
        }
        else {
            'Target process was detected and is eligible for live proof collection.'
        }

        $evidenceStages.Add((New-EvidenceStageRecord -Stage 'debug-preflight' -State $preflightState -Reason $preflightReason -Blocking ($summary.DebugState.AlreadyDebugged) -Details $summary.DebugState)) | Out-Null
    }

    $playerCurrent = Invoke-RepoPowerShellScriptJson -ScriptPath $readPlayerCurrentScript -Arguments @('-Json', '-SkipRefresh', '-ProcessName', $ProcessName) -Label 'read-player-current'
    $summary.PlayerCurrentSummary = Get-PlayerCurrentSummary -PlayerCurrent $playerCurrent
    $playerCurrentReason = 'Loaded a player-current baseline without forcing a startup /reloadui refresh.'
    $evidenceStages.Add((New-EvidenceStageRecord -Stage 'player-current' -State 'live-baseline' -Reason $playerCurrentReason -Details $summary.PlayerCurrentSummary)) | Out-Null
    $notes.Add('Skipped the startup ReaderBridge /reloadui refresh to avoid disruptive in-client UI side effects before proof begins.') | Out-Null

    $coordAnchor = Invoke-ReaderJson -Arguments @('--process-name', $ProcessName, '--read-player-coord-anchor', '--json') -Label 'read-player-coord-anchor'
    $summary.CoordAnchorSummary = Get-CoordAnchorSummary -CoordAnchor $coordAnchor
    $coordAnchorAssessment = Get-CoordAnchorAssessment -CoordAnchorSummary $summary.CoordAnchorSummary
    if ($coordAnchorAssessment.ShouldDegrade) {
        $degradedStates.Add((New-DegradedStateRecord -Stage 'coord-anchor' -State $coordAnchorAssessment.State -Reason $coordAnchorAssessment.Reason -Details $summary.CoordAnchorSummary)) | Out-Null
    }
    $evidenceStages.Add((New-EvidenceStageRecord -Stage 'coord-anchor' -State $coordAnchorAssessment.State -Reason $coordAnchorAssessment.Reason -Blocking $coordAnchorAssessment.Blocking -Details $summary.CoordAnchorSummary)) | Out-Null

    $searchArguments = @(
        '-Json',
        '-ProcessName', $ProcessName,
        '-MaxHits', $MaxHits.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '-OutputFile', $candidateSearchFile)
    if (-not [string]::IsNullOrWhiteSpace($OrientationCandidateLedgerFile)) {
        $searchArguments += @('-OrientationCandidateLedgerFile', $OrientationCandidateLedgerFile)
    }

    $candidateSearch = Invoke-RepoPowerShellScriptJson -ScriptPath $findPlayerOrientationCandidateScript -Arguments $searchArguments -Label 'find-player-orientation-candidate'
    $summary.CandidateSearchSummary = Get-CandidateSearchSummary -CandidateSearch $candidateSearch -CandidateSearchFile $candidateSearchFile -OrientationCandidateLedgerFile $OrientationCandidateLedgerFile
    $candidateSearchCount = [int](Get-PropertyValue -InputObject $candidateSearch -PropertyName 'CandidateCount')
    $pointerHopCount = [int](Get-PropertyValue -InputObject $candidateSearch -PropertyName 'PointerHopCandidateCount')
    $candidateSearchState = if ($candidateSearchCount -gt 0 -or $pointerHopCount -gt 0) { 'live-search' } else { 'candidate-missing' }
    $candidateSearchReason = if ($candidateSearchCount -gt 0 -or $pointerHopCount -gt 0) {
        'Live actor-yaw candidate search completed with at least one qualifying candidate.'
    }
    else {
        'Live actor-yaw candidate search returned no local or pointer-hop candidates.'
    }
    $evidenceStages.Add((New-EvidenceStageRecord -Stage 'candidate-search' -State $candidateSearchState -Reason $candidateSearchReason -Blocking ($candidateSearchCount -le 0 -and $pointerHopCount -le 0) -Details $summary.CandidateSearchSummary)) | Out-Null

    if ($candidateSearchCount -le 0 -and $pointerHopCount -le 0) {
        $summary.Status = 'candidate-missing'
        $degradedStates.Add((New-DegradedStateRecord -Stage 'candidate-search' -State 'candidate-missing' -Reason 'Candidate search returned no local or pointer-hop orientation candidates.' -Details $summary.CandidateSearchSummary)) | Out-Null
        $notes.Add('Candidate search returned no local or pointer-hop orientation candidates.') | Out-Null
        throw 'Candidate search returned no candidates.'
    }

    try {
        $candidateTestArguments = @(
            '-Json',
            '-ProcessName', $ProcessName,
            '-CandidateScreenFile', $candidateSearchFile,
            '-OutputFile', $candidateTestFile,
            '-TopCount', $TopCount.ToString([System.Globalization.CultureInfo]::InvariantCulture),
            '-StimulusKey', $StimulusKey,
        '-StimulusMode', $StimulusMode,
        '-HoldMilliseconds', $HoldMilliseconds.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '-WaitMilliseconds', $WaitMilliseconds.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '-ForegroundActivationSettleMilliseconds', $ForegroundActivationSettleMilliseconds.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '-ManualWindowMilliseconds', $ManualWindowMilliseconds.ToString([System.Globalization.CultureInfo]::InvariantCulture))

        if ($SkipStimulus) {
            $candidateTestArguments += '-SkipStimulus'
        }

        $candidateTest = Invoke-RepoPowerShellScriptJson -ScriptPath $testActorYawCandidatesScript -Arguments $candidateTestArguments -Label 'test-actor-yaw-candidates'
    }
    catch {
        $candidateTestError = $_.Exception.Message
        $notes.Add("Candidate proof step failed; falling back to candidate-search ordering. $($_.Exception.Message)") | Out-Null
    }
    $summary.CandidateProofSummary = Get-CandidateProofSummary `
        -CandidateTest $candidateTest `
        -CandidateTestFile $candidateTestFile `
        -StimulusKey $StimulusKey `
        -StimulusMode $StimulusMode `
        -SkipStimulus:$SkipStimulus `
        -HoldMilliseconds $HoldMilliseconds `
        -WaitMilliseconds $WaitMilliseconds `
        -ForegroundActivationSettleMilliseconds $ForegroundActivationSettleMilliseconds `
        -ManualWindowMilliseconds $ManualWindowMilliseconds `
        -ErrorMessage $candidateTestError

    if ($null -ne $candidateTest -and -not [string]::IsNullOrWhiteSpace($OrientationCandidateLedgerFile)) {
        try {
            $summary.LedgerUpdate = Invoke-RepoPowerShellScriptJson -ScriptPath $updateOrientationCandidateLedgerScript -Arguments @(
                '-Json',
                '-CandidateTestFile', $candidateTestFile,
                '-LedgerFile', $OrientationCandidateLedgerFile,
                '-ProcessName', $ProcessName) -Label 'update-orientation-candidate-ledger'
            $evidenceStages.Add((New-EvidenceStageRecord -Stage 'candidate-ledger' -State 'updated' -Reason 'Candidate proof results were persisted to the orientation-candidate ledger for future down-ranking.' -Details $summary.LedgerUpdate)) | Out-Null
            $notes.Add(("Persisted {0} candidate-proof rows to the orientation-candidate ledger." -f [int](Get-PropertyValue -InputObject $summary.LedgerUpdate -PropertyName 'AppendedEntryCount'))) | Out-Null
        }
        catch {
            $summary.LedgerUpdate = [pscustomobject]@{
                Mode = 'orientation-candidate-ledger-update'
                LedgerFile = [System.IO.Path]::GetFullPath($OrientationCandidateLedgerFile)
                AppendedEntryCount = 0
                Error = $_.Exception.Message
            }
            $evidenceStages.Add((New-EvidenceStageRecord -Stage 'candidate-ledger' -State 'update-failed' -Reason 'Candidate proof results could not be persisted to the orientation-candidate ledger.' -Details $summary.LedgerUpdate)) | Out-Null
            $degradedStates.Add((New-DegradedStateRecord -Stage 'candidate-ledger' -State 'update-failed' -Reason 'Candidate proof results could not be persisted to the orientation-candidate ledger.' -Blocking $false -Details $summary.LedgerUpdate)) | Out-Null
            $notes.Add("Orientation-candidate ledger update failed. $($_.Exception.Message)") | Out-Null
        }
    }

    if ($null -eq $candidateTest) {
        $evidenceStages.Add((New-EvidenceStageRecord -Stage 'candidate-proof' -State 'proof-failed' -Reason 'Turn-based candidate proof did not complete successfully.' -Blocking $true -Details $summary.CandidateProofSummary)) | Out-Null
        $degradedStates.Add((New-DegradedStateRecord -Stage 'candidate-proof' -State 'proof-failed' -Reason 'Turn-based candidate proof did not complete successfully.' -Details $summary.CandidateProofSummary)) | Out-Null
    }
    else {
        $proofSkipStimulus = [bool](Get-PropertyValue -InputObject $candidateTest -PropertyName 'SkipStimulus')
        $truthLikeCount = [int](Get-PropertyValue -InputObject $candidateTest -PropertyName 'TruthLikeCandidateCount')
        $turnObserved = [bool](Get-PropertyValue -InputObject $candidateTest -PropertyName 'TurnObserved')

        if ($proofSkipStimulus) {
            $proofState = if ([string](Get-PropertyValue -InputObject $candidateTest -PropertyName 'StimulusMode') -eq 'Manual') { 'manual-turn-window' } else { 'stimulus-skipped' }
            $proofReason = 'Candidate proof used a manual or read-only window instead of a controlled turn stimulus.'
            $evidenceStages.Add((New-EvidenceStageRecord -Stage 'candidate-proof' -State $proofState -Reason $proofReason -Blocking $true -Details $summary.CandidateProofSummary)) | Out-Null
            $degradedStates.Add((New-DegradedStateRecord -Stage 'candidate-proof' -State $proofState -Reason $proofReason -Details $summary.CandidateProofSummary)) | Out-Null
        }
        elseif ($truthLikeCount -gt 0) {
            $evidenceStages.Add((New-EvidenceStageRecord -Stage 'candidate-proof' -State 'truth-like-confirmed' -Reason 'Turn-based proof produced at least one truth-like candidate.' -Details $summary.CandidateProofSummary)) | Out-Null
        }
        elseif (-not $turnObserved) {
            $evidenceStages.Add((New-EvidenceStageRecord -Stage 'candidate-proof' -State 'turn-unverified' -Reason 'Turn-based proof did not observe a responsive candidate family, so the turn stimulus was not verified for debug promotion.' -Blocking $true -Details $summary.CandidateProofSummary)) | Out-Null
            $degradedStates.Add((New-DegradedStateRecord -Stage 'candidate-proof' -State 'turn-unverified' -Reason 'Turn-based proof did not observe a responsive candidate family, so the turn stimulus was not verified for debug promotion.' -Details $summary.CandidateProofSummary)) | Out-Null
        }
        else {
            $evidenceStages.Add((New-EvidenceStageRecord -Stage 'candidate-proof' -State 'no-truth-like-candidate' -Reason 'Turn-based proof completed but did not produce a truth-like candidate.' -Blocking $true -Details $summary.CandidateProofSummary)) | Out-Null
            $degradedStates.Add((New-DegradedStateRecord -Stage 'candidate-proof' -State 'no-truth-like-candidate' -Reason 'Turn-based proof completed but did not produce a truth-like candidate.' -Details $summary.CandidateProofSummary)) | Out-Null
        }
    }

    if ($null -ne $candidateTest -and
        [int](Get-PropertyValue -InputObject $candidateTest -PropertyName 'TruthLikeCandidateCount') -gt 0 -and
        $summary.CoordAnchorSummary.TraceMatchesProcess -ne $true) {
        try {
            $coordAnchorBeforeRefresh = $summary.CoordAnchorSummary
            [void](Invoke-RepoPowerShellScriptJson -ScriptPath $readPlayerCurrentScript -Arguments @(
                    '-Json',
                    '-SkipRefresh',
                    '-RefreshTraceAnchor',
                    '-ProcessName', $ProcessName) -Label 'refresh-player-coord-anchor')

            $refreshedCoordAnchor = Invoke-ReaderJson -Arguments @('--process-name', $ProcessName, '--read-player-coord-anchor', '--json') -Label 'read-player-coord-anchor-refresh'
            $summary.CoordAnchorSummary = Get-CoordAnchorSummary -CoordAnchor $refreshedCoordAnchor
            $coordAnchorAssessment = Get-CoordAnchorAssessment -CoordAnchorSummary $summary.CoordAnchorSummary
            $summary.CoordAnchorRefresh = [pscustomobject]@{
                Attempted = $true
                RefreshCallSucceeded = $true
                Succeeded = ($summary.CoordAnchorSummary.TraceMatchesProcess -eq $true)
                BeforeTraceMatchesProcess = ($coordAnchorBeforeRefresh.TraceMatchesProcess -eq $true)
                AfterTraceMatchesProcess = ($summary.CoordAnchorSummary.TraceMatchesProcess -eq $true)
                Error = $null
            }

            Remove-StageRecords -Records $evidenceStages -Stage 'coord-anchor'
            Remove-StageRecords -Records $degradedStates -Stage 'coord-anchor'

            if ($coordAnchorAssessment.ShouldDegrade) {
                $degradedStates.Add((New-DegradedStateRecord -Stage 'coord-anchor' -State $coordAnchorAssessment.State -Reason $coordAnchorAssessment.Reason -Details $summary.CoordAnchorSummary)) | Out-Null
            }

            $evidenceStages.Add((New-EvidenceStageRecord -Stage 'coord-anchor' -State $coordAnchorAssessment.State -Reason $coordAnchorAssessment.Reason -Blocking $coordAnchorAssessment.Blocking -Details $summary.CoordAnchorSummary)) | Out-Null
            $refreshState = if ($summary.CoordAnchorSummary.TraceMatchesProcess -eq $true) { 'refreshed-match' } else { 'refreshed-still-stale' }
            $refreshReason = if ($summary.CoordAnchorSummary.TraceMatchesProcess -eq $true) {
                'Coord-trace refresh updated the anchor so it now matches the current process.'
            }
            else {
                'Coord-trace refresh ran, but the coord anchor still did not match the current process.'
            }
            $evidenceStages.Add((New-EvidenceStageRecord -Stage 'coord-anchor-refresh' -State $refreshState -Reason $refreshReason -Blocking ($summary.CoordAnchorSummary.TraceMatchesProcess -ne $true) -Details $summary.CoordAnchorRefresh)) | Out-Null
            $notes.Add($refreshReason) | Out-Null
        }
        catch {
            $summary.CoordAnchorRefresh = [pscustomobject]@{
                Attempted = $true
                RefreshCallSucceeded = $false
                Succeeded = $false
                Error = $_.Exception.Message
            }
            $evidenceStages.Add((New-EvidenceStageRecord -Stage 'coord-anchor-refresh' -State 'refresh-failed' -Reason 'Coord-trace refresh failed after a truth-like yaw proof winner was found.' -Details $summary.CoordAnchorRefresh)) | Out-Null
            $notes.Add("Coord-trace refresh failed after the proof step. $($_.Exception.Message)") | Out-Null
        }
    }

    $selectedCandidate = $null
    if ($null -ne $candidateTest) {
        $truthLikeCount = [int](Get-PropertyValue -InputObject $candidateTest -PropertyName 'TruthLikeCandidateCount')
        $bestTruthLikeCandidate = Get-PropertyValue -InputObject $candidateTest -PropertyName 'BestTruthLikeCandidate'
        $isTruthLike = $false
        if ($null -ne $bestTruthLikeCandidate) {
            $truthLikeValue = Get-PropertyValue -InputObject $bestTruthLikeCandidate -PropertyName 'TruthLike'
            if ($null -ne $truthLikeValue) {
                $isTruthLike = [bool]$truthLikeValue
            }
        }

        if ($truthLikeCount -gt 0 -and $null -ne $bestTruthLikeCandidate -and $isTruthLike) {
            $selectedCandidate = Get-NormalizedCandidateFromTest -Candidate $bestTruthLikeCandidate
            $notes.Add('Selected the best truth-like candidate from the actor yaw proof step.') | Out-Null
        }
    }

    if ($null -eq $selectedCandidate) {
        $degradedStates.Add((New-DegradedStateRecord -Stage 'candidate-selection' -State 'proof-fallback' -Reason 'Selected candidate fell back to search ordering because no truth-like proof winner was available.')) | Out-Null
        $downRankedFamilyMap = Get-DownRankedFamilyMap -CandidateTest $candidateTest
        $selectedCandidate = Get-BestSearchCandidateForDebug -CandidateSearch $candidateSearch -DownRankedFamilyMap $downRankedFamilyMap
        if ($null -ne $selectedCandidate) {
            if ([string]$selectedCandidate.SelectionSource -eq 'candidate-search-best-pointer-hop') {
                $notes.Add('Selected the best non-down-ranked pointer-hop candidate from the search output.') | Out-Null
            }
            else {
                $notes.Add('Selected the best non-down-ranked local near-coord candidate from the search output.') | Out-Null
            }
        }
        elseif ($downRankedFamilyMap.Count -gt 0) {
            $degradedStates.Add((New-DegradedStateRecord -Stage 'candidate-selection' -State 'all-search-families-downranked' -Reason 'All search candidates belonged to proof-tested families that were down-ranked before native debug confirmation.' -Details @($downRankedFamilyMap.Values))) | Out-Null
            $notes.Add('No debug candidate remained after down-ranking nonresponsive proof-tested families.') | Out-Null
        }
    }

    if ($null -eq $selectedCandidate) {
        $summary.Status = 'candidate-missing'
        $degradedStates.Add((New-DegradedStateRecord -Stage 'candidate-selection' -State 'selection-missing' -Reason 'No candidate survived the deterministic selection rules.')) | Out-Null
        $notes.Add('No candidate survived the deterministic selection rules.') | Out-Null
        throw 'No candidate survived the selection rules.'
    }

    $summary.SelectedCandidate = $selectedCandidate
    $summary.WatchedAddress = Resolve-WatchedAddress -Candidate $selectedCandidate -Component $WatchComponent
    $evidenceStages.Add((New-EvidenceStageRecord -Stage 'candidate-selection' -State ([string]$selectedCandidate.SelectionSource) -Reason 'Deterministic candidate-selection ordering chose the final actor-yaw source for this run.' -Blocking ($selectedCandidate.SelectionSource -ne 'candidate-proof-truth-like') -Details $selectedCandidate)) | Out-Null

    if ($summary.DebugState.AlreadyDebugged) {
        $summary.Status = 'debug-blocked'
        $evidenceStages.Add((New-EvidenceStageRecord -Stage 'debug-confirmation' -State 'debug-blocked' -Reason 'Debug confirmation was skipped because the live client is already under a debugger relationship.' -Blocking $true -Details $summary.DebugState)) | Out-Null
        $degradedStates.Add((New-DegradedStateRecord -Stage 'debug-confirmation' -State 'debug-blocked' -Reason 'Debug confirmation was skipped because the live client is already under a debugger relationship.' -Details $summary.DebugState)) | Out-Null
        $notes.Add('Debug confirmation was skipped because the live client is already under a debugger relationship.') | Out-Null
        if ($summary.DebugState.AttachHelpers.Count -gt 0) {
            $notes.Add(("Attach helpers reported by preflight: {0}" -f ($summary.DebugState.AttachHelpers -join ', '))) | Out-Null
        }
    }
    elseif ($null -ne $candidateTest -and -not [bool](Get-PropertyValue -InputObject $candidateTest -PropertyName 'TurnObserved')) {
        $summary.Status = 'turn-unverified'
        $evidenceStages.Add((New-EvidenceStageRecord -Stage 'debug-confirmation' -State 'skipped-turn-unverified' -Reason 'Native debug confirmation was skipped because the proof run did not verify a turn response.' -Blocking $true -Details $summary.CandidateProofSummary)) | Out-Null
        $degradedStates.Add((New-DegradedStateRecord -Stage 'debug-confirmation' -State 'skipped-turn-unverified' -Reason 'Native debug confirmation was skipped because the proof run did not verify a turn response.' -Details $summary.CandidateProofSummary)) | Out-Null
        $notes.Add('Skipped native debug confirmation because no candidate family responded during the proof step.') | Out-Null
    }
    else {
        New-Item -ItemType Directory -Path $debugTraceDirectory -Force | Out-Null
        $summary.DebugTraceDirectory = $debugTraceDirectory

        $debugArguments = @(
            '--process-name', $ProcessName,
            $(if ($DebugMode -eq 'Access') { '--debug-trace-memory-access' } else { '--debug-trace-memory-write' }),
            '--debug-address', $summary.WatchedAddress,
            '--debug-width', '4',
            '--debug-timeout-ms', $DebugTimeoutMs.ToString([System.Globalization.CultureInfo]::InvariantCulture),
            '--debug-max-hits', $DebugMaxHits.ToString([System.Globalization.CultureInfo]::InvariantCulture),
            '--debug-output-directory', $debugTraceDirectory,
            '--json')

        try {
            [void](Invoke-ReaderJson -Arguments $debugArguments -Label 'debug-trace-memory-watch')
            $summary.DebugTraceSummary = Invoke-ReaderJson -Arguments @('--debug-trace-summary', '--trace-directory', $debugTraceDirectory, '--json') -Label 'debug-trace-summary'
            $summary.Status = 'success'
            $evidenceStages.Add((New-EvidenceStageRecord -Stage 'debug-confirmation' -State 'confirmed' -Reason 'Bounded debug watchpoint confirmation completed successfully.' -Details $summary.DebugTraceSummary)) | Out-Null
            $notes.Add('Bounded x64 debug watchpoint trace completed successfully against the selected basis-row component.') | Out-Null
        }
        catch {
            $summary.Status = 'trace-failed'
            $evidenceStages.Add((New-EvidenceStageRecord -Stage 'debug-confirmation' -State 'trace-failed' -Reason 'Debug confirmation failed after candidate selection.' -Blocking $true)) | Out-Null
            $degradedStates.Add((New-DegradedStateRecord -Stage 'debug-confirmation' -State 'trace-failed' -Reason 'Debug confirmation failed after candidate selection.')) | Out-Null
            $notes.Add("Debug trace failed after candidate selection. $($_.Exception.Message)") | Out-Null
            throw
        }
    }
}
catch {
    if ([string]::IsNullOrWhiteSpace([string]$summary.Status) -or $summary.Status -eq 'preflight-failed') {
        $summary.Status = 'preflight-failed'
    }

    if ($summary.Status -ne 'debug-blocked') {
        $exitCode = 1
    }

    if ($notes.Count -eq 0 -or $notes[$notes.Count - 1] -notlike '*'+$_.Exception.Message+'*') {
        $notes.Add($_.Exception.Message) | Out-Null
    }
}
finally {
    $summary.EvidenceStages = @($evidenceStages.ToArray())
    $summary.DegradedStates = @($degradedStates.ToArray())
    $summary.Promotion = Get-PromotionAssessment `
        -DegradedStates @($summary.DegradedStates) `
        -SelectedCandidate $summary.SelectedCandidate `
        -CandidateProofSummary $summary.CandidateProofSummary `
        -CoordAnchorSummary $summary.CoordAnchorSummary
    Write-WorkflowSummaryFile -Document $summary -NoteList $notes -Path $summaryFile
}

if ($Json) {
    Write-Output (ConvertTo-JsonText -InputObject $summary)
}
else {
    Write-TerminalSummary -Document $summary -SummaryPath $summaryFile -ExitCode $exitCode
}

exit $exitCode
