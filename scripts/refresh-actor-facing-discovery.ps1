[CmdletBinding()]
param(
    [switch]$Json,
    [switch]$RestartSession,
    [switch]$RunProvenance,
    [switch]$RunInstructionTrace,
    [string]$ProcessName = 'rift_x64',
    [int]$ProcessId,
    [string]$TargetWindowHandle,
    [int]$SearchMaxHits = 16,
    [int]$TopCount = 8,
    [string]$OrientationCandidateLedgerFile,
    [ValidateSet('PostMessage', 'SendInput', 'AutoHotkey', 'Manual')]
    [string]$StimulusMode = 'AutoHotkey',
    [string]$StimulusKey = 'd',
    [string]$ReverseStimulusKey = 'a',
    [int]$HoldMilliseconds = 700,
    [int]$WaitMilliseconds = 250,
    [int]$RepeatCount = 1,
    [int]$PostStimulusSampleCount = 1,
    [int]$PostStimulusSampleIntervalMilliseconds = 0,
    [int]$ManualWindowMilliseconds = 0,
    [double]$MinYawResponseDegrees = 1.0,
    [double]$MinReversibleYawResponseDegrees = 2.0,
    [double]$MaxCoordDrift = 0.35,
    [string]$InstructionAddressHex = '',
    [string]$InstructionBasisOffsetHex = '0xD4',
    [string]$BehaviorBackedLeadFile = (Join-Path $PSScriptRoot 'actor-facing-behavior-backed-lead.json'),
    [string]$SessionFile = (Join-Path $PSScriptRoot 'captures\actor-facing-discovery\session.json'),
    [string]$DiscoveryOutputFile = (Join-Path $PSScriptRoot 'captures\actor-facing-discovery\search.json'),
    [string]$ValidationOutputFile = (Join-Path $PSScriptRoot 'captures\actor-facing-discovery\validation.json'),
    [string]$CaptureConfirmationFile = (Join-Path $PSScriptRoot 'captures\actor-facing-discovery\capture-confirm.json'),
    [string]$ReaderConfirmationFile = (Join-Path $PSScriptRoot 'captures\actor-facing-discovery\reader-confirm.json')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$readerDll = Join-Path $repoRoot 'reader\RiftReader.Reader\bin\Debug\net10.0-windows\RiftReader.Reader.dll'
$findCandidateScript = Join-Path $PSScriptRoot 'find-player-orientation-candidate.ps1'
$testCandidateScript = Join-Path $PSScriptRoot 'test-actor-yaw-candidates.ps1'
$captureOrientationScript = Join-Path $PSScriptRoot 'capture-actor-orientation.ps1'
$refreshDiscoveryChainScript = Join-Path $PSScriptRoot 'refresh-discovery-chain.ps1'
$traceFacingInstructionScript = Join-Path $PSScriptRoot 'trace-actor-facing-instruction.ps1'
$resolvedBehaviorBackedLeadFile = [System.IO.Path]::GetFullPath($BehaviorBackedLeadFile)
$resolvedSessionFile = [System.IO.Path]::GetFullPath($SessionFile)
$resolvedDiscoveryOutputFile = [System.IO.Path]::GetFullPath($DiscoveryOutputFile)
$resolvedValidationOutputFile = [System.IO.Path]::GetFullPath($ValidationOutputFile)
$resolvedCaptureConfirmationFile = [System.IO.Path]::GetFullPath($CaptureConfirmationFile)
$resolvedReaderConfirmationFile = [System.IO.Path]::GetFullPath($ReaderConfirmationFile)
$resolvedOrientationCandidateLedgerFile = if ([string]::IsNullOrWhiteSpace($OrientationCandidateLedgerFile)) { $null } else { [System.IO.Path]::GetFullPath($OrientationCandidateLedgerFile) }

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public static class RiftActorFacingDiscoveryNative
{
    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool IsWindow(IntPtr hWnd);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
}
"@

function Get-CurrentUtcIso {
    return [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
}

function Get-OptionalPropertyValue {
    param(
        $Object,
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    if ($null -eq $Object) {
        return $null
    }

    if ($Object -is [System.Collections.IDictionary]) {
        if ($Object.Contains($Name)) {
            return $Object[$Name]
        }

        return $null
    }

    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $null
    }

    return $property.Value
}

function Convert-ToPlainObject {
    param($Value)

    if ($null -eq $Value) {
        return $null
    }

    if ($Value -is [string] -or $Value -is [ValueType]) {
        return $Value
    }

    if ($Value -is [DateTime]) {
        return ([DateTimeOffset]$Value).ToUniversalTime().ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    }

    if ($Value -is [DateTimeOffset]) {
        return $Value.ToUniversalTime().ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    }

    if ($Value -is [System.Collections.IDictionary]) {
        $result = [ordered]@{}
        foreach ($key in $Value.Keys) {
            $result[[string]$key] = Convert-ToPlainObject -Value $Value[$key]
        }

        return $result
    }

    if ($Value -is [pscustomobject]) {
        $result = [ordered]@{}
        foreach ($property in $Value.PSObject.Properties) {
            $result[$property.Name] = Convert-ToPlainObject -Value $property.Value
        }

        return $result
    }

    if (($Value -is [System.Collections.IEnumerable]) -and -not ($Value -is [string])) {
        $items = New-Object System.Collections.Generic.List[object]
        foreach ($item in $Value) {
            $items.Add((Convert-ToPlainObject -Value $item)) | Out-Null
        }

        return ,@($items.ToArray())
    }

    $properties = $Value.PSObject.Properties
    if ($properties.Count -gt 0) {
        $result = [ordered]@{}
        foreach ($property in $properties) {
            $result[$property.Name] = Convert-ToPlainObject -Value $property.Value
        }

        return $result
    }

    return $Value
}

function Load-JsonDocument {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "JSON file not found: $Path"
    }

    $json = Get-Content -LiteralPath $Path -Raw
    if ([string]::IsNullOrWhiteSpace($json)) {
        throw "JSON file '$Path' is empty."
    }

    $document = if ((Get-Command Microsoft.PowerShell.Utility\ConvertFrom-Json).Parameters.ContainsKey('Depth')) {
        $json | Microsoft.PowerShell.Utility\ConvertFrom-Json -Depth 100
    }
    else {
        $json | Microsoft.PowerShell.Utility\ConvertFrom-Json
    }

    return Convert-ToPlainObject -Value $document
}

function Save-JsonDocument {
    param(
        [Parameter(Mandatory = $true)]
        $Document,
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $directory = Split-Path -Parent $Path
    if (-not [string]::IsNullOrWhiteSpace($directory)) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }

    $plain = Convert-ToPlainObject -Value $Document
    $json = $plain | ConvertTo-Json -Depth 100
    Set-Content -LiteralPath $Path -Value $json -Encoding UTF8
}

function Normalize-HexString {
    param([string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $null
    }

    $normalized = $Value.Trim()
    if (-not $normalized.StartsWith('0x', [System.StringComparison]::OrdinalIgnoreCase)) {
        $normalized = "0x$normalized"
    }

    return $normalized.ToUpperInvariant()
}

function ConvertTo-WindowHandle {
    param([string]$HandleText)

    if ([string]::IsNullOrWhiteSpace($HandleText)) {
        return [IntPtr]::Zero
    }

    if ($HandleText.StartsWith('0x', [System.StringComparison]::OrdinalIgnoreCase)) {
        $raw = [UInt64]::Parse($HandleText.Substring(2), [System.Globalization.NumberStyles]::AllowHexSpecifier, [System.Globalization.CultureInfo]::InvariantCulture)
        return [IntPtr]([Int64]$raw)
    }

    return [IntPtr]([Int64]::Parse($HandleText, [System.Globalization.CultureInfo]::InvariantCulture))
}

function Get-ProcessSessionKey {
    param($ProcessMetadata)

    return ('{0}|{1}|{2}' -f `
        [string](Get-OptionalPropertyValue -Object $ProcessMetadata -Name 'ProcessName'), `
        [string](Get-OptionalPropertyValue -Object $ProcessMetadata -Name 'ProcessId'), `
        [string](Get-OptionalPropertyValue -Object $ProcessMetadata -Name 'StartTimeUtc'))
}

function Get-LiveProcessMetadata {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [int]$Id,
        [string]$WindowHandle
    )

    $handle = ConvertTo-WindowHandle -HandleText $WindowHandle
    if ($handle -ne [IntPtr]::Zero) {
        if (-not [RiftActorFacingDiscoveryNative]::IsWindow($handle)) {
            throw "Target window handle '$WindowHandle' is not a valid window."
        }

        $ownerProcessId = [uint32]0
        [void][RiftActorFacingDiscoveryNative]::GetWindowThreadProcessId($handle, [ref]$ownerProcessId)
        if ($ownerProcessId -eq 0) {
            throw "Target window handle '$WindowHandle' did not resolve to a process id."
        }

        if ($Id -gt 0 -and [int]$ownerProcessId -ne $Id) {
            throw "Target window handle '$WindowHandle' belongs to PID $ownerProcessId, not PID $Id."
        }

        $Id = [int]$ownerProcessId
    }

    $process = if ($Id -gt 0) {
        Get-Process -Id $Id -ErrorAction Stop
    }
    else {
        $matches = @(Get-Process -Name $Name -ErrorAction Stop | Where-Object { $_.MainWindowHandle -ne 0 })
        if ($matches.Count -gt 1) {
            $ids = ($matches | Sort-Object Id | ForEach-Object { $_.Id }) -join ', '
            throw "Process name '$Name' matched multiple windowed processes ($ids). Use -ProcessId or -TargetWindowHandle for actor-facing discovery."
        }

        $matches | Select-Object -First 1
    }

    if ($null -eq $process) {
        throw "No process named '$Name' with a main window was found."
    }

    if (-not [string]::IsNullOrWhiteSpace($Name) -and
        -not [string]::Equals($process.ProcessName, [System.IO.Path]::GetFileNameWithoutExtension($Name), [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Target PID $($process.Id) is '$($process.ProcessName)', not '$Name'."
    }

    if ($handle -ne [IntPtr]::Zero -and [Int64]$process.MainWindowHandle -ne $handle.ToInt64()) {
        throw ("Target PID $($process.Id) main window 0x{0:X} does not match requested window '$WindowHandle'." -f ([Int64]$process.MainWindowHandle))
    }

    $startTimeUtc = $null
    try {
        $startTimeUtc = $process.StartTime.ToUniversalTime().ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    }
    catch {
        throw "Unable to read the start time for process '$Name' (PID $($process.Id)): $($_.Exception.Message)"
    }

    return [ordered]@{
        ProcessId = $process.Id
        ProcessName = $process.ProcessName
        StartTimeUtc = $startTimeUtc
        MainWindowTitle = $process.MainWindowTitle
        MainWindowHandleHex = ('0x{0:X}' -f $process.MainWindowHandle)
        Responding = $process.Responding
        SessionKey = $null
    }
}

function New-StageRecord {
    param([Parameter(Mandatory = $true)][string]$Name)

    return [ordered]@{
        Name = $Name
        Status = 'pending'
        StartedAtUtc = $null
        CompletedAtUtc = $null
        ArtifactFile = $null
        ProcessSessionKey = $null
        Reused = $false
        Summary = $null
        Error = $null
        Notes = @()
    }
}

function New-SessionDocument {
    param(
        [Parameter(Mandatory = $true)]
        $ProcessMetadata,
        [Parameter(Mandatory = $true)]
        [string]$ParameterFingerprint,
        [string]$ResetReason
    )

    return [ordered]@{
        Mode = 'actor-facing-discovery-session'
        SchemaVersion = 1
        GeneratedAtUtc = Get-CurrentUtcIso
        UpdatedAtUtc = Get-CurrentUtcIso
        SessionFile = $resolvedSessionFile
        Process = [ordered]@{
            ProcessId = $ProcessMetadata.ProcessId
            ProcessName = $ProcessMetadata.ProcessName
            StartTimeUtc = $ProcessMetadata.StartTimeUtc
            MainWindowTitle = $ProcessMetadata.MainWindowTitle
            MainWindowHandleHex = $ProcessMetadata.MainWindowHandleHex
            Responding = $ProcessMetadata.Responding
            SessionKey = $ProcessMetadata.SessionKey
        }
        Parameters = [ordered]@{
            SearchMaxHits = $SearchMaxHits
            TopCount = $TopCount
            OrientationCandidateLedgerFile = $resolvedOrientationCandidateLedgerFile
            StimulusMode = $StimulusMode
            StimulusKey = $StimulusKey
            ReverseStimulusKey = $ReverseStimulusKey
            HoldMilliseconds = $HoldMilliseconds
            WaitMilliseconds = $WaitMilliseconds
            RepeatCount = $RepeatCount
            PostStimulusSampleCount = $PostStimulusSampleCount
            PostStimulusSampleIntervalMilliseconds = $PostStimulusSampleIntervalMilliseconds
            ManualWindowMilliseconds = $ManualWindowMilliseconds
            MinYawResponseDegrees = $MinYawResponseDegrees
            MinReversibleYawResponseDegrees = $MinReversibleYawResponseDegrees
            MaxCoordDrift = $MaxCoordDrift
            RunProvenance = [bool]$RunProvenance
            RunInstructionTrace = [bool]$RunInstructionTrace
            InstructionAddressHex = if ([string]::IsNullOrWhiteSpace($InstructionAddressHex)) { $null } else { (Normalize-HexString -Value $InstructionAddressHex) }
            InstructionBasisOffsetHex = Normalize-HexString -Value $InstructionBasisOffsetHex
            ParameterFingerprint = $ParameterFingerprint
        }
        Artifacts = [ordered]@{
            Discovery = $resolvedDiscoveryOutputFile
            Validation = $resolvedValidationOutputFile
            CaptureConfirmation = $resolvedCaptureConfirmationFile
            ReaderConfirmation = $resolvedReaderConfirmationFile
        }
        LiveTruthStatus = 'blocked'
        ProvenanceStatus = 'not-run'
        Outcome = 'pending'
        PromotionStatus = 'pending'
        SessionConsistency = 'consistent'
        ResetReason = $ResetReason
        WinningCandidate = $null
        ExistingLead = $null
        CandidateEvaluations = @()
        RejectionReasons = @()
        NextActions = @()
        Notes = @()
        Stages = [ordered]@{
            Discover = New-StageRecord -Name 'Discover'
            Validate = New-StageRecord -Name 'Validate'
            Promote = New-StageRecord -Name 'Promote'
            Confirm = New-StageRecord -Name 'Confirm'
            Provenance = New-StageRecord -Name 'Provenance'
            Report = New-StageRecord -Name 'Report'
        }
    }
}

function Get-ParameterFingerprint {
    $values = @(
        "searchMaxHits=$SearchMaxHits",
        "topCount=$TopCount",
        "ledger=$resolvedOrientationCandidateLedgerFile",
        "stimulusMode=$StimulusMode",
        "stimulusKey=$StimulusKey",
        "reverseStimulusKey=$ReverseStimulusKey",
        "holdMs=$HoldMilliseconds",
        "waitMs=$WaitMilliseconds",
        "repeatCount=$RepeatCount",
        "postSamples=$PostStimulusSampleCount",
        "postSampleIntervalMs=$PostStimulusSampleIntervalMilliseconds",
        "manualWindowMs=$ManualWindowMilliseconds",
        "minYaw=$MinYawResponseDegrees",
        "minReversibleYaw=$MinReversibleYawResponseDegrees",
        "maxCoordDrift=$MaxCoordDrift",
        "runProvenance=$RunProvenance",
        "runInstructionTrace=$RunInstructionTrace",
        "instructionAddress=$(Normalize-HexString -Value $InstructionAddressHex)",
        "instructionBasisOffset=$(Normalize-HexString -Value $InstructionBasisOffsetHex)"
    )

    return [string]::Join(';', $values)
}

function Update-SessionTimestamp {
    param($Session)

    $Session['UpdatedAtUtc'] = Get-CurrentUtcIso
}

function Save-Session {
    param($Session)

    Update-SessionTimestamp -Session $Session
    Save-JsonDocument -Document $Session -Path $resolvedSessionFile
}

function Get-StageRecord {
    param(
        $Session,
        [Parameter(Mandatory = $true)]
        [string]$StageName
    )

    return $Session['Stages'][$StageName]
}

function Set-StageStarted {
    param(
        $Session,
        [Parameter(Mandatory = $true)]
        [string]$StageName
    )

    $stage = Get-StageRecord -Session $Session -StageName $StageName
    $stage['Status'] = 'in-progress'
    $stage['StartedAtUtc'] = Get-CurrentUtcIso
    $stage['CompletedAtUtc'] = $null
    $stage['Error'] = $null
    $stage['Reused'] = $false
    $stage['ProcessSessionKey'] = $Session['Process']['SessionKey']
    return $stage
}

function Set-StageCompleted {
    param(
        $Session,
        [Parameter(Mandatory = $true)]
        [string]$StageName,
        $Summary,
        [string]$ArtifactFile,
        [bool]$Reused = $false,
        [string[]]$Notes = @()
    )

    $stage = Get-StageRecord -Session $Session -StageName $StageName
    $stage['Status'] = 'completed'
    if ($null -eq $stage['StartedAtUtc']) {
        $stage['StartedAtUtc'] = Get-CurrentUtcIso
    }
    $stage['CompletedAtUtc'] = Get-CurrentUtcIso
    $stage['ArtifactFile'] = $ArtifactFile
    $stage['Summary'] = Convert-ToPlainObject -Value $Summary
    $stage['Error'] = $null
    $stage['Reused'] = $Reused
    $stage['ProcessSessionKey'] = $Session['Process']['SessionKey']
    $stage['Notes'] = @($Notes)
}

function Set-StageFailed {
    param(
        $Session,
        [Parameter(Mandatory = $true)]
        [string]$StageName,
        [Parameter(Mandatory = $true)]
        [string]$ErrorMessage,
        $Summary
    )

    $stage = Get-StageRecord -Session $Session -StageName $StageName
    $stage['Status'] = 'failed'
    if ($null -eq $stage['StartedAtUtc']) {
        $stage['StartedAtUtc'] = Get-CurrentUtcIso
    }
    $stage['CompletedAtUtc'] = Get-CurrentUtcIso
    $stage['Error'] = $ErrorMessage
    $stage['Summary'] = Convert-ToPlainObject -Value $Summary
    $stage['ProcessSessionKey'] = $Session['Process']['SessionKey']
}

function Set-StageSkipped {
    param(
        $Session,
        [Parameter(Mandatory = $true)]
        [string]$StageName,
        [Parameter(Mandatory = $true)]
        [string]$Reason,
        $Summary
    )

    $stage = Get-StageRecord -Session $Session -StageName $StageName
    $stage['Status'] = 'skipped'
    if ($null -eq $stage['StartedAtUtc']) {
        $stage['StartedAtUtc'] = Get-CurrentUtcIso
    }
    $stage['CompletedAtUtc'] = Get-CurrentUtcIso
    $stage['Error'] = $null
    $stage['Summary'] = Convert-ToPlainObject -Value $Summary
    $stage['Notes'] = @($Reason)
    $stage['ProcessSessionKey'] = $Session['Process']['SessionKey']
}

function Test-StageReusable {
    param(
        $Session,
        [Parameter(Mandatory = $true)]
        [string]$StageName,
        [string]$ArtifactFile
    )

    $stage = Get-StageRecord -Session $Session -StageName $StageName
    if ($null -eq $stage) {
        return $false
    }

    if ([string]$stage['Status'] -ne 'completed') {
        return $false
    }

    if ([string]$stage['ProcessSessionKey'] -ne [string]$Session['Process']['SessionKey']) {
        return $false
    }

    if (-not [string]::IsNullOrWhiteSpace($ArtifactFile) -and -not (Test-Path -LiteralPath $ArtifactFile)) {
        return $false
    }

    return $true
}

function Get-DiscoveryCandidates {
    param($DiscoveryDocument)

    $rows = New-Object System.Collections.Generic.List[object]
    $rank = 0

    foreach ($candidate in @((Get-OptionalPropertyValue -Object $DiscoveryDocument -Name 'PointerHopCandidates'))) {
        if ($null -eq $candidate) {
            continue
        }

        $rank++
        $rows.Add([ordered]@{
                Rank = $rank
                SourceAddress = Normalize-HexString -Value ([string](Get-OptionalPropertyValue -Object $candidate -Name 'Address'))
                BasisForwardOffset = Normalize-HexString -Value ([string](Get-OptionalPropertyValue -Object $candidate -Name 'BasisPrimaryForwardOffset'))
                DiscoveryMode = [string](Get-OptionalPropertyValue -Object $candidate -Name 'DiscoveryMode')
                ParentAddress = Normalize-HexString -Value ([string](Get-OptionalPropertyValue -Object $candidate -Name 'ParentAddress'))
                RootAddress = Normalize-HexString -Value ([string](Get-OptionalPropertyValue -Object $candidate -Name 'RootAddress'))
                SearchScore = Get-OptionalPropertyValue -Object $candidate -Name 'Score'
                Basis = Convert-ToPlainObject -Value (Get-OptionalPropertyValue -Object $candidate -Name 'Basis')
                PreferredEstimate = Convert-ToPlainObject -Value (Get-OptionalPropertyValue -Object $candidate -Name 'PreferredEstimate')
            }) | Out-Null
    }

    foreach ($candidate in @((Get-OptionalPropertyValue -Object $DiscoveryDocument -Name 'Candidates'))) {
        if ($null -eq $candidate) {
            continue
        }

        $rank++
        $rows.Add([ordered]@{
                Rank = $rank
                SourceAddress = Normalize-HexString -Value ([string](Get-OptionalPropertyValue -Object $candidate -Name 'Address'))
                BasisForwardOffset = Normalize-HexString -Value ([string](Get-OptionalPropertyValue -Object $candidate -Name 'BasisPrimaryForwardOffset'))
                DiscoveryMode = [string](Get-OptionalPropertyValue -Object $candidate -Name 'DiscoveryMode')
                ParentAddress = Normalize-HexString -Value ([string](Get-OptionalPropertyValue -Object $candidate -Name 'ProbeRootAddress'))
                RootAddress = Normalize-HexString -Value ([string](Get-OptionalPropertyValue -Object $candidate -Name 'ProbeRootAddress'))
                SearchScore = Get-OptionalPropertyValue -Object $candidate -Name 'Score'
                Basis = Convert-ToPlainObject -Value (Get-OptionalPropertyValue -Object $candidate -Name 'Basis')
                PreferredEstimate = Convert-ToPlainObject -Value (Get-OptionalPropertyValue -Object $candidate -Name 'PreferredEstimate')
            }) | Out-Null
    }

    return @($rows.ToArray())
}

function Get-CandidateKey {
    param(
        [string]$SourceAddress,
        [string]$BasisForwardOffset
    )

    return ('{0}|{1}' -f (Normalize-HexString -Value $SourceAddress), (Normalize-HexString -Value $BasisForwardOffset))
}

function Find-DiscoveryCandidate {
    param(
        $DiscoveryDocument,
        [string]$SourceAddress,
        [string]$BasisForwardOffset
    )

    $targetKey = Get-CandidateKey -SourceAddress $SourceAddress -BasisForwardOffset $BasisForwardOffset
    foreach ($candidate in @(Get-DiscoveryCandidates -DiscoveryDocument $DiscoveryDocument)) {
        if ((Get-CandidateKey -SourceAddress $candidate['SourceAddress'] -BasisForwardOffset $candidate['BasisForwardOffset']) -eq $targetKey) {
            return $candidate
        }
    }

    return $null
}

function Get-MaxAbsoluteValue {
    param($Values)

    $candidates = @($Values | Where-Object { $null -ne $_ } | ForEach-Object { [Math]::Abs([double]$_) })
    if ($candidates.Count -le 0) {
        return $null
    }

    return ($candidates | Measure-Object -Maximum).Maximum
}

function Test-BasisCandidatePlausible {
    param($DiscoveryCandidate)

    $reasons = New-Object System.Collections.Generic.List[string]
    $basis = Get-OptionalPropertyValue -Object $DiscoveryCandidate -Name 'Basis'
    $estimate = Get-OptionalPropertyValue -Object $DiscoveryCandidate -Name 'PreferredEstimate'

    if ($null -eq $basis) {
        $reasons.Add('discovery_basis_missing') | Out-Null
    }
    else {
        $isOrthonormal = Get-OptionalPropertyValue -Object $basis -Name 'IsOrthonormal'
        if ($isOrthonormal -ne $true) {
            $reasons.Add('basis_not_orthonormal') | Out-Null
        }

        $determinant = Get-OptionalPropertyValue -Object $basis -Name 'Determinant'
        if ($null -eq $determinant -or [Math]::Abs([Math]::Abs([double]$determinant) - 1.0) -gt 0.05) {
            $reasons.Add('basis_determinant_out_of_range') | Out-Null
        }
    }

    $magnitude = Get-OptionalPropertyValue -Object $estimate -Name 'Magnitude'
    if ($null -eq $magnitude -or [double]$magnitude -lt 0.85 -or [double]$magnitude -gt 1.15) {
        $reasons.Add('basis_forward_magnitude_out_of_range') | Out-Null
    }

    return [ordered]@{
        Passed = ($reasons.Count -eq 0)
        RejectionReasons = @($reasons.ToArray())
        Magnitude = $magnitude
        Determinant = if ($null -ne $basis) { Get-OptionalPropertyValue -Object $basis -Name 'Determinant' } else { $null }
        IsOrthonormal = if ($null -ne $basis) { Get-OptionalPropertyValue -Object $basis -Name 'IsOrthonormal' } else { $false }
    }
}

function Get-PhaseHealthIssues {
    param(
        $Phase,
        $ProcessMetadata,
        [bool]$RequireForegroundMatch = $true
    )

    $issues = New-Object System.Collections.Generic.List[string]
    if ($null -eq $Phase) {
        $issues.Add('phase_missing') | Out-Null
        return @($issues.ToArray())
    }

    $targetWindowInfo = Get-OptionalPropertyValue -Object $Phase -Name 'TargetWindowInfo'
    if ($null -eq $targetWindowInfo) {
        $issues.Add('target_window_info_missing') | Out-Null
    }
    else {
        $phasePid = Get-OptionalPropertyValue -Object $targetWindowInfo -Name 'ProcessId'
        if ($null -eq $phasePid -or [int]$phasePid -ne [int]$ProcessMetadata.ProcessId) {
            $issues.Add('target_process_mismatch') | Out-Null
        }

        $responding = Get-OptionalPropertyValue -Object $targetWindowInfo -Name 'Responding'
        if ($responding -ne $true) {
            $issues.Add('target_process_not_responding') | Out-Null
        }
    }

    if ($RequireForegroundMatch) {
        foreach ($propertyName in @('ForegroundBeforeStimulus', 'ForegroundAfterLaunch', 'ForegroundAfterStimulus')) {
            $foreground = Get-OptionalPropertyValue -Object $Phase -Name $propertyName
            if ($null -eq $foreground) {
                continue
            }

            $matchesProcess = Get-OptionalPropertyValue -Object $foreground -Name 'MatchesTargetProcess'
            $matchesWindow = Get-OptionalPropertyValue -Object $foreground -Name 'MatchesTargetMainWindow'
            if ($matchesProcess -ne $true -or $matchesWindow -ne $true) {
                $issues.Add(("foreground_mismatch_{0}" -f $propertyName.ToLowerInvariant())) | Out-Null
            }
        }
    }

    return @($issues.ToArray())
}

function Test-ValidationCandidatePromotable {
    param(
        $ValidationCandidate,
        $DiscoveryCandidate,
        $ProcessMetadata
    )

    $reasons = New-Object System.Collections.Generic.List[string]
    if ($null -eq $ValidationCandidate) {
        $reasons.Add('validation_candidate_missing') | Out-Null
    }

    if ($null -eq $DiscoveryCandidate) {
        $reasons.Add('discovery_candidate_missing') | Out-Null
    }

    $candidateResponsive = Get-OptionalPropertyValue -Object $ValidationCandidate -Name 'CandidateResponsive'
    if ($candidateResponsive -ne $true) {
        $reasons.Add('candidate_nonresponsive') | Out-Null
    }

    $playerStayedMostlyStill = Get-OptionalPropertyValue -Object $ValidationCandidate -Name 'PlayerStayedMostlyStill'
    if ($playerStayedMostlyStill -ne $true) {
        $reasons.Add('coord_drift_exceeded') | Out-Null
    }

    $coordDeltaMagnitude = Get-OptionalPropertyValue -Object $ValidationCandidate -Name 'PlayerCoordDeltaMagnitude'
    if ($null -ne $coordDeltaMagnitude -and [double]$coordDeltaMagnitude -gt $MaxCoordDrift) {
        $reasons.Add('coord_drift_exceeded') | Out-Null
    }

    $forwardPeak = Get-MaxAbsoluteValue -Values (Get-OptionalPropertyValue -Object $ValidationCandidate -Name 'ForwardPeakYawDeltas')
    if ($null -eq $forwardPeak) {
        $forwardPeak = Get-MaxAbsoluteValue -Values @((Get-OptionalPropertyValue -Object $ValidationCandidate -Name 'YawDeltaDegrees'))
    }

    if ($null -eq $forwardPeak -or [double]$forwardPeak -lt $MinYawResponseDegrees) {
        $reasons.Add('forward_yaw_response_below_threshold') | Out-Null
    }

    if (-not [string]::IsNullOrWhiteSpace($ReverseStimulusKey)) {
        $reversePeak = Get-MaxAbsoluteValue -Values (Get-OptionalPropertyValue -Object $ValidationCandidate -Name 'ReversePeakYawDeltas')
        if ($null -eq $reversePeak) {
            $reversePeak = Get-MaxAbsoluteValue -Values @((Get-OptionalPropertyValue -Object $ValidationCandidate -Name 'ReverseYawDeltaDegrees'))
        }

        $reversibleCycleCount = Get-OptionalPropertyValue -Object $ValidationCandidate -Name 'ReversibleCycleCount'
        if (($null -eq $reversibleCycleCount -or [int]$reversibleCycleCount -lt 1) -or ($null -eq $reversePeak) -or ([double]$reversePeak -lt $MinReversibleYawResponseDegrees)) {
            $reasons.Add('reversible_yaw_response_below_threshold') | Out-Null
        }
    }

    $basisValidation = Test-BasisCandidatePlausible -DiscoveryCandidate $DiscoveryCandidate
    foreach ($reason in @($basisValidation['RejectionReasons'])) {
        $reasons.Add($reason) | Out-Null
    }

    $requireForegroundMatch = ($StimulusMode -in @('SendInput', 'AutoHotkey'))
    foreach ($cycle in @((Get-OptionalPropertyValue -Object $ValidationCandidate -Name 'CycleSummaries'))) {
        foreach ($phaseName in @('Forward', 'Reverse')) {
            $phase = Get-OptionalPropertyValue -Object $cycle -Name $phaseName
            if ($null -eq $phase) {
                continue
            }

            foreach ($issue in @(Get-PhaseHealthIssues -Phase $phase -ProcessMetadata $ProcessMetadata -RequireForegroundMatch:$requireForegroundMatch)) {
                $reasons.Add($issue) | Out-Null
            }
        }

        $cycleStayedMostlyStill = Get-OptionalPropertyValue -Object $cycle -Name 'PlayerStayedMostlyStill'
        if ($null -ne $cycleStayedMostlyStill -and $cycleStayedMostlyStill -ne $true) {
            $reasons.Add('coord_drift_exceeded') | Out-Null
        }
    }

    $uniqueReasons = @($reasons.ToArray() | Select-Object -Unique)
    return [ordered]@{
        Passed = ($uniqueReasons.Count -eq 0)
        RejectionReasons = $uniqueReasons
        ForwardPeakYawDegrees = $forwardPeak
        ReversePeakYawDegrees = if (-not [string]::IsNullOrWhiteSpace($ReverseStimulusKey)) {
            Get-MaxAbsoluteValue -Values (Get-OptionalPropertyValue -Object $ValidationCandidate -Name 'ReversePeakYawDeltas')
        }
        else {
            $null
        }
        CandidateResponsive = $candidateResponsive
        PlayerStayedMostlyStill = $playerStayedMostlyStill
        PlayerCoordDeltaMagnitude = $coordDeltaMagnitude
        BasisIsOrthonormal = $basisValidation['IsOrthonormal']
        BasisForwardMagnitude = $basisValidation['Magnitude']
        BasisDeterminant = $basisValidation['Determinant']
    }
}

function Load-BehaviorBackedLead {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return $null
    }

    return Load-JsonDocument -Path $Path
}

function Get-LeadFileSnapshot {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return [ordered]@{
            Exists = $false
            Content = $null
        }
    }

    return [ordered]@{
        Exists = $true
        Content = Get-Content -LiteralPath $Path -Raw
    }
}

function Restore-LeadFileSnapshot {
    param(
        [Parameter(Mandatory = $true)]$Snapshot,
        [Parameter(Mandatory = $true)][string]$Path
    )

    if ($Snapshot['Exists']) {
        $directory = Split-Path -Parent $Path
        if (-not [string]::IsNullOrWhiteSpace($directory)) {
            New-Item -ItemType Directory -Path $directory -Force | Out-Null
        }

        Set-Content -LiteralPath $Path -Value $Snapshot['Content'] -Encoding UTF8
        return
    }

    if (Test-Path -LiteralPath $Path) {
        Remove-Item -LiteralPath $Path -Force
    }
}

function Get-ValidationSummaryNote {
    param(
        $PromotedCandidate,
        $ProcessMetadata
    )

    $now = [DateTimeOffset]::UtcNow.ToLocalTime()
    $dateText = $now.ToString('MMMM d, yyyy', [System.Globalization.CultureInfo]::InvariantCulture)
    $forward = Get-OptionalPropertyValue -Object $PromotedCandidate -Name 'ForwardPeakYawDegrees'
    $reverse = Get-OptionalPropertyValue -Object $PromotedCandidate -Name 'ReversePeakYawDegrees'
    $coordDrift = Get-OptionalPropertyValue -Object $PromotedCandidate -Name 'PlayerCoordDeltaMagnitude'
    $cycles = Get-OptionalPropertyValue -Object $PromotedCandidate -Name 'ReversibleCycleCount'
    if ($null -eq $cycles) {
        $cycles = Get-OptionalPropertyValue -Object $PromotedCandidate -Name 'RepeatCount'
    }

    return ("Fresh agentic actor-facing discovery on {0} confirmed that the live actor-facing basis is the forward row at {1} on source {2}. Focused {3} {4}/{5} validation produced reversible yaw deltas of about {6}/{7} degrees with {8} coord drift across {9} cycle(s). This lead was promoted from the current-session actor-facing discovery session and targets live PID {10} started at {11}." -f `
        $dateText, `
        (Get-OptionalPropertyValue -Object $PromotedCandidate -Name 'BasisForwardOffset'), `
        (Get-OptionalPropertyValue -Object $PromotedCandidate -Name 'SourceAddress'), `
        $StimulusMode, `
        $StimulusKey.ToUpperInvariant(), `
        $ReverseStimulusKey.ToUpperInvariant(), `
        ($(if ($null -ne $forward) { ([double]$forward).ToString('0.###', [System.Globalization.CultureInfo]::InvariantCulture) } else { 'n/a' })), `
        ($(if ($null -ne $reverse) { ([double]$reverse).ToString('0.###', [System.Globalization.CultureInfo]::InvariantCulture) } else { 'n/a' })), `
        ($(if ($null -ne $coordDrift) { ([double]$coordDrift).ToString('0.###', [System.Globalization.CultureInfo]::InvariantCulture) } else { 'n/a' })), `
        ($(if ($null -ne $cycles) { [string]$cycles } else { '0' })), `
        $ProcessMetadata.ProcessId, `
        $ProcessMetadata.StartTimeUtc)
}

function New-PromotedLeadDocument {
    param(
        $PromotedCandidate,
        $ProcessMetadata,
        [string]$DiscoveryArtifactFile,
        [string]$ValidationArtifactFile
    )

    return [ordered]@{
        Mode = 'actor-facing-behavior-backed-lead'
        GeneratedAtUtc = Get-CurrentUtcIso
        ValidatedAtUtc = Get-CurrentUtcIso
        ProcessName = $ProcessMetadata.ProcessName
        SourceAddress = Get-OptionalPropertyValue -Object $PromotedCandidate -Name 'SourceAddress'
        BasisForwardOffset = Get-OptionalPropertyValue -Object $PromotedCandidate -Name 'BasisForwardOffset'
        BasisDuplicateForwardOffset = $null
        Status = 'preferred-solved-lead'
        OperationalStatus = 'behavior-backed-lead'
        PreferredLead = $true
        SolvedActorFacing = $true
        CanonicalActorYaw = $true
        CanonicalPitchFormula = 'atan2(forwardY, sqrt(forwardX^2 + forwardZ^2))'
        CanonicalYawFormula = 'atan2(forwardZ, forwardX)'
        Notes = @(
            (Get-ValidationSummaryNote -PromotedCandidate $PromotedCandidate -ProcessMetadata $ProcessMetadata)
        )
        CandidateDiagnostics = [ordered]@{
            Rank = Get-OptionalPropertyValue -Object $PromotedCandidate -Name 'Rank'
            DiscoveryMode = Get-OptionalPropertyValue -Object $PromotedCandidate -Name 'DiscoveryMode'
            ParentAddress = Get-OptionalPropertyValue -Object $PromotedCandidate -Name 'ParentAddress'
            RootAddress = Get-OptionalPropertyValue -Object $PromotedCandidate -Name 'RootAddress'
            ReversibleCycleCount = Get-OptionalPropertyValue -Object $PromotedCandidate -Name 'ReversibleCycleCount'
            CandidateResponsive = Get-OptionalPropertyValue -Object $PromotedCandidate -Name 'CandidateResponsive'
            PlayerStayedMostlyStill = Get-OptionalPropertyValue -Object $PromotedCandidate -Name 'PlayerStayedMostlyStill'
            CandidateSearchFile = $DiscoveryArtifactFile
            ValidationArtifact = $ValidationArtifactFile
            DiscoverySessionFile = $resolvedSessionFile
            ProcessId = $ProcessMetadata.ProcessId
            ProcessStartTimeUtc = $ProcessMetadata.StartTimeUtc
            ForwardPeakYawDegrees = Get-OptionalPropertyValue -Object $PromotedCandidate -Name 'ForwardPeakYawDegrees'
            ReversePeakYawDegrees = Get-OptionalPropertyValue -Object $PromotedCandidate -Name 'ReversePeakYawDegrees'
            PlayerCoordDeltaMagnitude = Get-OptionalPropertyValue -Object $PromotedCandidate -Name 'PlayerCoordDeltaMagnitude'
        }
    }
}

function Invoke-WorkerScript {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ScriptPath,
        [Parameter(Mandatory = $true)]
        [hashtable]$Arguments
    )

    & $ScriptPath @Arguments | Out-Null
}

function Invoke-ReaderJson {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    if (Test-Path -LiteralPath $readerDll) {
        $output = & dotnet $readerDll @Arguments 2>&1
    }
    else {
        $output = & dotnet run --project $readerProject -- @Arguments 2>&1
    }

    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "Reader command failed (`$LASTEXITCODE=$exitCode): $($output -join [Environment]::NewLine)"
    }

    $json = ($output -join [Environment]::NewLine)
    $document = if ((Get-Command Microsoft.PowerShell.Utility\ConvertFrom-Json).Parameters.ContainsKey('Depth')) {
        $json | Microsoft.PowerShell.Utility\ConvertFrom-Json -Depth 100
    }
    else {
        $json | Microsoft.PowerShell.Utility\ConvertFrom-Json
    }

    return Convert-ToPlainObject -Value $document
}

function Invoke-Confirmation {
    param(
        [Parameter(Mandatory = $true)]
        $ProcessMetadata
    )

    Invoke-WorkerScript -ScriptPath $captureOrientationScript -Arguments @{
        Json = $true
        ProcessName = $ProcessMetadata.ProcessName
        ProcessId = $ProcessMetadata.ProcessId
        BehaviorBackedLeadFile = $resolvedBehaviorBackedLeadFile
        OutputFile = $resolvedCaptureConfirmationFile
    }

    $captureDocument = Load-JsonDocument -Path $resolvedCaptureConfirmationFile
    $readerDocument = Invoke-ReaderJson -Arguments @(
        '--pid', ([string]$ProcessMetadata.ProcessId),
        '--read-player-orientation',
        '--json')
    Save-JsonDocument -Document $readerDocument -Path $resolvedReaderConfirmationFile

    $captureOrientation = Get-OptionalPropertyValue -Object $captureDocument -Name 'ReaderOrientation'
    $captureSource = Normalize-HexString -Value ([string](Get-OptionalPropertyValue -Object $captureOrientation -Name 'SelectedSourceAddress'))
    $captureBasis = Normalize-HexString -Value ([string](Get-OptionalPropertyValue -Object $captureOrientation -Name 'BasisForwardOffset'))
    $readerSource = Normalize-HexString -Value ([string](Get-OptionalPropertyValue -Object $readerDocument -Name 'SelectedSourceAddress'))
    $readerBasis = Normalize-HexString -Value ([string](Get-OptionalPropertyValue -Object $readerDocument -Name 'BasisPrimaryForwardOffset'))

    $reasons = New-Object System.Collections.Generic.List[string]
    if ([string]::IsNullOrWhiteSpace($captureSource) -or [string]::IsNullOrWhiteSpace($readerSource)) {
        $reasons.Add('confirmation_source_missing') | Out-Null
    }
    elseif ($captureSource -ne $readerSource) {
        $reasons.Add('confirmation_source_mismatch') | Out-Null
    }

    if ([string]::IsNullOrWhiteSpace($captureBasis) -or [string]::IsNullOrWhiteSpace($readerBasis)) {
        $reasons.Add('confirmation_basis_missing') | Out-Null
    }
    elseif ($captureBasis -ne $readerBasis) {
        $reasons.Add('confirmation_basis_mismatch') | Out-Null
    }

    return [ordered]@{
        CaptureDocument = $captureDocument
        ReaderDocument = $readerDocument
        CaptureArtifactFile = $resolvedCaptureConfirmationFile
        ReaderArtifactFile = $resolvedReaderConfirmationFile
        CaptureSourceAddress = $captureSource
        CaptureBasisForwardOffset = $captureBasis
        ReaderSourceAddress = $readerSource
        ReaderBasisForwardOffset = $readerBasis
        CaptureMatchesReader = ($reasons.Count -eq 0)
        RejectionReasons = @($reasons.ToArray())
    }
}

function Build-NextActions {
    param($Session)

    $actions = New-Object System.Collections.Generic.List[string]
    switch ([string]$Session['LiveTruthStatus']) {
        'confirmed' {
            $actions.Add('Use the promoted behavior-backed lead for live actor-facing work on the current session.') | Out-Null
            if ([string]$Session['ProvenanceStatus'] -eq 'partial') {
                $actions.Add('Resume provenance refresh later; live truth is green, but lineage evidence is still partial.') | Out-Null
            }
        }
        'retained-existing' {
            $actions.Add('Keep the current behavior-backed lead; no promotable same-session candidate beat it in this run.') | Out-Null
            $actions.Add('If you want a fresh promotion, rerun with live stimulus enabled after confirming the target window is healthy and focused.') | Out-Null
        }
        default {
            $actions.Add('Rerun discovery after re-establishing a healthy same-session target window and a fresh reversible stimulus pass.') | Out-Null
            $actions.Add('Do not promote historical source-chain truth automatically; keep the lane blocked until a same-session candidate confirms.') | Out-Null
        }
    }

    if ([string]$Session['ProvenanceStatus'] -eq 'not-run' -and $RunProvenance -eq $false -and [string]$Session['LiveTruthStatus'] -ne 'blocked') {
        $actions.Add('Run -RunProvenance when you want to deepen selector/source-chain evidence behind the confirmed live lead.') | Out-Null
    }

    return ,@($actions.ToArray())
}

function Write-SessionText {
    param($Session)

    Write-Host 'Actor-facing discovery conductor'
    Write-Host ("Process:                     {0} (PID {1})" -f $Session['Process']['ProcessName'], $Session['Process']['ProcessId'])
    Write-Host ("Process start (UTC):         {0}" -f $Session['Process']['StartTimeUtc'])
    Write-Host ("Live truth status:           {0}" -f $Session['LiveTruthStatus'])
    Write-Host ("Provenance status:           {0}" -f $Session['ProvenanceStatus'])
    Write-Host ("Outcome:                     {0}" -f $Session['Outcome'])
    Write-Host ("Promotion status:            {0}" -f $Session['PromotionStatus'])
    Write-Host ("Session consistency:         {0}" -f $Session['SessionConsistency'])

    $winningCandidate = $Session['WinningCandidate']
    if ($null -ne $winningCandidate) {
        Write-Host ("Winning candidate:           {0} @ {1}" -f $winningCandidate['SourceAddress'], $winningCandidate['BasisForwardOffset'])
    }
    else {
        Write-Host 'Winning candidate:           n/a'
    }

    if (@($Session['RejectionReasons']).Count -gt 0) {
        Write-Host ("Rejection reasons:           {0}" -f ([string]::Join(', ', @($Session['RejectionReasons']))))
    }

    foreach ($stageName in @('Discover', 'Validate', 'Promote', 'Confirm', 'Provenance')) {
        $stage = $Session['Stages'][$stageName]
        Write-Host ("Stage {0}:                  {1}" -f $stageName, $stage['Status'])
    }

    Write-Host ("Session file:                {0}" -f $resolvedSessionFile)
}

$parameterFingerprint = Get-ParameterFingerprint
$processMetadata = Get-LiveProcessMetadata -Name $ProcessName -Id $ProcessId -WindowHandle $TargetWindowHandle
$processMetadata['SessionKey'] = Get-ProcessSessionKey -ProcessMetadata $processMetadata

$session = $null
$resetReason = $null
if (-not $RestartSession -and (Test-Path -LiteralPath $resolvedSessionFile)) {
    $loadedSession = Load-JsonDocument -Path $resolvedSessionFile
    $loadedProcess = Get-OptionalPropertyValue -Object $loadedSession -Name 'Process'
    $loadedParameters = Get-OptionalPropertyValue -Object $loadedSession -Name 'Parameters'
    $loadedSessionKey = Get-OptionalPropertyValue -Object $loadedProcess -Name 'SessionKey'
    $loadedFingerprint = Get-OptionalPropertyValue -Object $loadedParameters -Name 'ParameterFingerprint'

    if ([string]$loadedSessionKey -eq [string]$processMetadata.SessionKey -and [string]$loadedFingerprint -eq $parameterFingerprint) {
        $session = $loadedSession
    }
    elseif ([string]$loadedSessionKey -ne [string]$processMetadata.SessionKey) {
        $resetReason = 'process_identity_changed'
    }
    else {
        $resetReason = 'parameter_fingerprint_changed'
    }
}

if ($null -eq $session) {
    $session = New-SessionDocument -ProcessMetadata $processMetadata -ParameterFingerprint $parameterFingerprint -ResetReason $resetReason
}
else {
    $session['Process'] = [ordered]@{
        ProcessId = $processMetadata.ProcessId
        ProcessName = $processMetadata.ProcessName
        StartTimeUtc = $processMetadata.StartTimeUtc
        MainWindowTitle = $processMetadata.MainWindowTitle
        MainWindowHandleHex = $processMetadata.MainWindowHandleHex
        Responding = $processMetadata.Responding
        SessionKey = $processMetadata.SessionKey
    }
    $session['ResetReason'] = $null
}

$existingLead = Load-BehaviorBackedLead -Path $resolvedBehaviorBackedLeadFile
$session['ExistingLead'] = if ($null -eq $existingLead) {
    $null
}
else {
    [ordered]@{
        SourceAddress = Normalize-HexString -Value ([string](Get-OptionalPropertyValue -Object $existingLead -Name 'SourceAddress'))
        BasisForwardOffset = Normalize-HexString -Value ([string](Get-OptionalPropertyValue -Object $existingLead -Name 'BasisForwardOffset'))
        ValidatedAtUtc = Get-OptionalPropertyValue -Object $existingLead -Name 'ValidatedAtUtc'
        GeneratedAtUtc = Get-OptionalPropertyValue -Object $existingLead -Name 'GeneratedAtUtc'
        Status = Get-OptionalPropertyValue -Object $existingLead -Name 'Status'
    }
}

Save-Session -Session $session

$discoveryDocument = $null
$validationDocument = $null
$confirmationResult = $null
$leadBackup = $null
$provenanceOnlyMode = ($RunProvenance -and -not $RestartSession -and $null -ne $existingLead)

try {
    $session['RejectionReasons'] = @()
    $session['Notes'] = @()
    $session['NextActions'] = @()

    if ($provenanceOnlyMode) {
        Set-StageSkipped -Session $session -StageName 'Discover' -Reason 'Using the current behavior-backed lead as live truth for a provenance-only run.' -Summary $session['ExistingLead']
        Set-StageSkipped -Session $session -StageName 'Validate' -Reason 'Using the current behavior-backed lead as live truth for a provenance-only run.' -Summary $session['ExistingLead']
        Set-StageSkipped -Session $session -StageName 'Promote' -Reason 'Using the current behavior-backed lead as live truth for a provenance-only run.' -Summary $session['ExistingLead']
        Save-Session -Session $session

        Set-StageStarted -Session $session -StageName 'Confirm' | Out-Null
        $confirmationResult = Invoke-Confirmation -ProcessMetadata $processMetadata
        if (-not $confirmationResult['CaptureMatchesReader']) {
            throw ("Existing lead confirmation failed before provenance: {0}" -f ([string]::Join(', ', @($confirmationResult['RejectionReasons']))))
        }

        $session['LiveTruthStatus'] = 'retained-existing'
        $session['Outcome'] = 'retained-existing'
        $session['PromotionStatus'] = 'retained-existing'
        $session['SessionConsistency'] = 'consistent'
        Set-StageCompleted -Session $session -StageName 'Confirm' -ArtifactFile $resolvedCaptureConfirmationFile -Summary ([ordered]@{
                CaptureSourceAddress = $confirmationResult['CaptureSourceAddress']
                CaptureBasisForwardOffset = $confirmationResult['CaptureBasisForwardOffset']
                ReaderSourceAddress = $confirmationResult['ReaderSourceAddress']
                ReaderBasisForwardOffset = $confirmationResult['ReaderBasisForwardOffset']
                CaptureMatchesReader = $confirmationResult['CaptureMatchesReader']
            })
        Save-Session -Session $session
    }
    else {
    if (Test-StageReusable -Session $session -StageName 'Discover' -ArtifactFile $resolvedDiscoveryOutputFile) {
        $discoveryDocument = Load-JsonDocument -Path $resolvedDiscoveryOutputFile
        Set-StageCompleted -Session $session -StageName 'Discover' -ArtifactFile $resolvedDiscoveryOutputFile -Reused:$true -Notes @('Reused existing discovery artifact for the same process session.') -Summary ([ordered]@{
                ProcessId = Get-OptionalPropertyValue -Object $discoveryDocument -Name 'ProcessId'
                CandidateCount = Get-OptionalPropertyValue -Object $discoveryDocument -Name 'CandidateCount'
                PointerHopCandidateCount = Get-OptionalPropertyValue -Object $discoveryDocument -Name 'PointerHopCandidateCount'
            })
    }
    else {
        Set-StageStarted -Session $session -StageName 'Discover' | Out-Null
        Invoke-WorkerScript -ScriptPath $findCandidateScript -Arguments @{
            Json = $true
            ProcessName = $processMetadata.ProcessName
            ProcessId = $processMetadata.ProcessId
            MaxHits = $SearchMaxHits
            OutputFile = $resolvedDiscoveryOutputFile
            OrientationCandidateLedgerFile = $resolvedOrientationCandidateLedgerFile
        }
        $discoveryDocument = Load-JsonDocument -Path $resolvedDiscoveryOutputFile
        Set-StageCompleted -Session $session -StageName 'Discover' -ArtifactFile $resolvedDiscoveryOutputFile -Summary ([ordered]@{
                ProcessId = Get-OptionalPropertyValue -Object $discoveryDocument -Name 'ProcessId'
                CandidateCount = Get-OptionalPropertyValue -Object $discoveryDocument -Name 'CandidateCount'
                PointerHopCandidateCount = Get-OptionalPropertyValue -Object $discoveryDocument -Name 'PointerHopCandidateCount'
                BestPointerHopCandidate = Convert-ToPlainObject -Value (Get-OptionalPropertyValue -Object $discoveryDocument -Name 'BestPointerHopCandidate')
            })
    }
    Save-Session -Session $session

    $discoveryProcessId = Get-OptionalPropertyValue -Object $discoveryDocument -Name 'ProcessId'
    if ($null -eq $discoveryProcessId -or [int]$discoveryProcessId -ne [int]$processMetadata.ProcessId) {
        throw "Discovery artifact '$resolvedDiscoveryOutputFile' is stale for live PID $($processMetadata.ProcessId)."
    }

    if (Test-StageReusable -Session $session -StageName 'Validate' -ArtifactFile $resolvedValidationOutputFile) {
        $validationDocument = Load-JsonDocument -Path $resolvedValidationOutputFile
        Set-StageCompleted -Session $session -StageName 'Validate' -ArtifactFile $resolvedValidationOutputFile -Reused:$true -Notes @('Reused existing validation artifact for the same process session.') -Summary ([ordered]@{
                CandidateCount = Get-OptionalPropertyValue -Object $validationDocument -Name 'CandidateCount'
                TruthLikeCandidateCount = Get-OptionalPropertyValue -Object $validationDocument -Name 'TruthLikeCandidateCount'
                BestTruthLikeCandidate = Convert-ToPlainObject -Value (Get-OptionalPropertyValue -Object $validationDocument -Name 'BestTruthLikeCandidate')
            })
    }
    else {
        Set-StageStarted -Session $session -StageName 'Validate' | Out-Null
        $validationArguments = @{
            Json = $true
            ProcessName = $processMetadata.ProcessName
            ProcessId = $processMetadata.ProcessId
            TargetWindowHandle = $processMetadata.MainWindowHandleHex
            CandidateScreenFile = $resolvedDiscoveryOutputFile
            OutputFile = $resolvedValidationOutputFile
            TopCount = $TopCount
            StimulusKey = $StimulusKey
            ReverseStimulusKey = $ReverseStimulusKey
            StimulusMode = $StimulusMode
            HoldMilliseconds = $HoldMilliseconds
            WaitMilliseconds = $WaitMilliseconds
            RepeatCount = $RepeatCount
            PostStimulusSampleCount = $PostStimulusSampleCount
            PostStimulusSampleIntervalMilliseconds = $PostStimulusSampleIntervalMilliseconds
            ManualWindowMilliseconds = $ManualWindowMilliseconds
            MinYawResponseDegrees = $MinYawResponseDegrees
            MinReversibleYawResponseDegrees = $MinReversibleYawResponseDegrees
            MaxCoordDrift = $MaxCoordDrift
        }

        Invoke-WorkerScript -ScriptPath $testCandidateScript -Arguments $validationArguments
        $validationDocument = Load-JsonDocument -Path $resolvedValidationOutputFile
        Set-StageCompleted -Session $session -StageName 'Validate' -ArtifactFile $resolvedValidationOutputFile -Summary ([ordered]@{
                CandidateCount = Get-OptionalPropertyValue -Object $validationDocument -Name 'CandidateCount'
                TruthLikeCandidateCount = Get-OptionalPropertyValue -Object $validationDocument -Name 'TruthLikeCandidateCount'
                BestTruthLikeCandidate = Convert-ToPlainObject -Value (Get-OptionalPropertyValue -Object $validationDocument -Name 'BestTruthLikeCandidate')
            })
    }
    Save-Session -Session $session

    $validationResults = @((Get-OptionalPropertyValue -Object $validationDocument -Name 'Results'))
    if ($validationResults.Count -le 0) {
        $bestTruthLikeCandidate = Get-OptionalPropertyValue -Object $validationDocument -Name 'BestTruthLikeCandidate'
        if ($null -ne $bestTruthLikeCandidate) {
            $validationResults = @($bestTruthLikeCandidate)
        }
    }

    $orderedValidationResults = New-Object System.Collections.Generic.List[object]
    $bestTruthLikeCandidate = Get-OptionalPropertyValue -Object $validationDocument -Name 'BestTruthLikeCandidate'
    if ($null -ne $bestTruthLikeCandidate) {
        $orderedValidationResults.Add((Convert-ToPlainObject -Value $bestTruthLikeCandidate)) | Out-Null
    }

    $bestTruthLikeKey = if ($null -ne $bestTruthLikeCandidate) {
        Get-CandidateKey -SourceAddress ([string](Get-OptionalPropertyValue -Object $bestTruthLikeCandidate -Name 'SourceAddress')) -BasisForwardOffset ([string](Get-OptionalPropertyValue -Object $bestTruthLikeCandidate -Name 'BasisForwardOffset'))
    }
    else {
        $null
    }

    foreach ($candidate in @($validationResults | Sort-Object Rank)) {
        $candidateKey = Get-CandidateKey -SourceAddress ([string](Get-OptionalPropertyValue -Object $candidate -Name 'SourceAddress')) -BasisForwardOffset ([string](Get-OptionalPropertyValue -Object $candidate -Name 'BasisForwardOffset'))
        if ($null -ne $bestTruthLikeKey -and $candidateKey -eq $bestTruthLikeKey) {
            continue
        }

        $orderedValidationResults.Add((Convert-ToPlainObject -Value $candidate)) | Out-Null
    }

    $candidateEvaluations = New-Object System.Collections.Generic.List[object]
    $promotableCandidate = $null

    foreach ($candidate in @($orderedValidationResults.ToArray())) {
        $sourceAddress = Normalize-HexString -Value ([string](Get-OptionalPropertyValue -Object $candidate -Name 'SourceAddress'))
        $basisForwardOffset = Normalize-HexString -Value ([string](Get-OptionalPropertyValue -Object $candidate -Name 'BasisForwardOffset'))
        $discoveryCandidate = Find-DiscoveryCandidate -DiscoveryDocument $discoveryDocument -SourceAddress $sourceAddress -BasisForwardOffset $basisForwardOffset
        $promotionCheck = Test-ValidationCandidatePromotable -ValidationCandidate $candidate -DiscoveryCandidate $discoveryCandidate -ProcessMetadata $processMetadata

        $evaluation = [ordered]@{
            Rank = Get-OptionalPropertyValue -Object $candidate -Name 'Rank'
            SourceAddress = $sourceAddress
            BasisForwardOffset = $basisForwardOffset
            DiscoveryMode = Get-OptionalPropertyValue -Object $candidate -Name 'DiscoveryMode'
            ParentAddress = Normalize-HexString -Value ([string](Get-OptionalPropertyValue -Object $candidate -Name 'ParentAddress'))
            RootAddress = Normalize-HexString -Value ([string](Get-OptionalPropertyValue -Object $candidate -Name 'RootAddress'))
            TruthLike = Get-OptionalPropertyValue -Object $candidate -Name 'TruthLike'
            CandidateResponsive = $promotionCheck['CandidateResponsive']
            PlayerStayedMostlyStill = $promotionCheck['PlayerStayedMostlyStill']
            PlayerCoordDeltaMagnitude = $promotionCheck['PlayerCoordDeltaMagnitude']
            ReversibleCycleCount = Get-OptionalPropertyValue -Object $candidate -Name 'ReversibleCycleCount'
            ForwardPeakYawDegrees = $promotionCheck['ForwardPeakYawDegrees']
            ReversePeakYawDegrees = $promotionCheck['ReversePeakYawDegrees']
            BasisIsOrthonormal = $promotionCheck['BasisIsOrthonormal']
            BasisForwardMagnitude = $promotionCheck['BasisForwardMagnitude']
            BasisDeterminant = $promotionCheck['BasisDeterminant']
            PromotionPassed = $promotionCheck['Passed']
            RejectionReasons = @($promotionCheck['RejectionReasons'])
        }

        $candidateEvaluations.Add($evaluation) | Out-Null
        if ($null -eq $promotableCandidate -and $promotionCheck['Passed']) {
            $promotableCandidate = $evaluation
        }
    }

    $session['CandidateEvaluations'] = @($candidateEvaluations.ToArray())

    if ($null -ne $promotableCandidate) {
        $session['WinningCandidate'] = $promotableCandidate
        $session['PromotionStatus'] = 'candidate-selected'
        Set-StageStarted -Session $session -StageName 'Promote' | Out-Null
        $leadBackup = Get-LeadFileSnapshot -Path $resolvedBehaviorBackedLeadFile
        $leadDocument = New-PromotedLeadDocument -PromotedCandidate $promotableCandidate -ProcessMetadata $processMetadata -DiscoveryArtifactFile $resolvedDiscoveryOutputFile -ValidationArtifactFile $resolvedValidationOutputFile
        Save-JsonDocument -Document $leadDocument -Path $resolvedBehaviorBackedLeadFile
        Set-StageCompleted -Session $session -StageName 'Promote' -ArtifactFile $resolvedBehaviorBackedLeadFile -Summary ([ordered]@{
                SourceAddress = $leadDocument['SourceAddress']
                BasisForwardOffset = $leadDocument['BasisForwardOffset']
                CandidateDiagnostics = $leadDocument['CandidateDiagnostics']
            })
        Save-Session -Session $session

        try {
            Set-StageStarted -Session $session -StageName 'Confirm' | Out-Null
            $confirmationResult = Invoke-Confirmation -ProcessMetadata $processMetadata
            if (-not $confirmationResult['CaptureMatchesReader']) {
                throw ("Confirmation failed: {0}" -f ([string]::Join(', ', @($confirmationResult['RejectionReasons']))))
            }

            $session['LiveTruthStatus'] = 'confirmed'
            $session['Outcome'] = 'promoted'
            $session['PromotionStatus'] = 'promoted'
            $session['SessionConsistency'] = 'consistent'
            Set-StageCompleted -Session $session -StageName 'Confirm' -ArtifactFile $resolvedCaptureConfirmationFile -Summary ([ordered]@{
                    CaptureSourceAddress = $confirmationResult['CaptureSourceAddress']
                    CaptureBasisForwardOffset = $confirmationResult['CaptureBasisForwardOffset']
                    ReaderSourceAddress = $confirmationResult['ReaderSourceAddress']
                    ReaderBasisForwardOffset = $confirmationResult['ReaderBasisForwardOffset']
                    CaptureMatchesReader = $confirmationResult['CaptureMatchesReader']
                })
        }
        catch {
            Restore-LeadFileSnapshot -Snapshot $leadBackup -Path $resolvedBehaviorBackedLeadFile
            $session['PromotionStatus'] = 'rolled-back-after-confirm-failure'
            $session['SessionConsistency'] = 'promotion-confirmation-failed'
            $session['RejectionReasons'] = @('promotion_confirm_failed')
            Set-StageFailed -Session $session -StageName 'Confirm' -ErrorMessage $_.Exception.Message -Summary $confirmationResult

            $restoredLead = Load-BehaviorBackedLead -Path $resolvedBehaviorBackedLeadFile
            if ($null -ne $restoredLead) {
                try {
                    $confirmationResult = Invoke-Confirmation -ProcessMetadata $processMetadata
                    if ($confirmationResult['CaptureMatchesReader']) {
                        $session['LiveTruthStatus'] = 'retained-existing'
                        $session['Outcome'] = 'retained-existing-after-rollback'
                        $session['ExistingLead'] = [ordered]@{
                            SourceAddress = Normalize-HexString -Value ([string](Get-OptionalPropertyValue -Object $restoredLead -Name 'SourceAddress'))
                            BasisForwardOffset = Normalize-HexString -Value ([string](Get-OptionalPropertyValue -Object $restoredLead -Name 'BasisForwardOffset'))
                            ValidatedAtUtc = Get-OptionalPropertyValue -Object $restoredLead -Name 'ValidatedAtUtc'
                            GeneratedAtUtc = Get-OptionalPropertyValue -Object $restoredLead -Name 'GeneratedAtUtc'
                            Status = Get-OptionalPropertyValue -Object $restoredLead -Name 'Status'
                        }
                        $session['Notes'] = @('Candidate promotion failed confirmation, so the previous lead was restored and re-confirmed.')
                    }
                    else {
                        $session['LiveTruthStatus'] = 'blocked'
                        $session['Outcome'] = 'blocked'
                    }
                }
                catch {
                    $session['LiveTruthStatus'] = 'blocked'
                    $session['Outcome'] = 'blocked'
                    $session['Notes'] = @("Candidate promotion failed confirmation, and the restored lead could not be re-confirmed: $($_.Exception.Message)")
                }
            }
            else {
                $session['LiveTruthStatus'] = 'blocked'
                $session['Outcome'] = 'blocked'
                $session['Notes'] = @('Candidate promotion failed confirmation, and no previous lead existed to restore.')
            }
        }
    }
    else {
        $session['WinningCandidate'] = $null
        $allRejections = @($candidateEvaluations.ToArray() | ForEach-Object { @($_['RejectionReasons']) } | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) } | Select-Object -Unique)
        $session['RejectionReasons'] = $allRejections
        Set-StageSkipped -Session $session -StageName 'Promote' -Reason 'No promotable same-session candidate passed the hard gates.' -Summary ([ordered]@{
                CandidateCount = $candidateEvaluations.Count
                RejectionReasons = $allRejections
            })
        Save-Session -Session $session

        if ($null -ne $existingLead) {
            Set-StageStarted -Session $session -StageName 'Confirm' | Out-Null
            try {
                $confirmationResult = Invoke-Confirmation -ProcessMetadata $processMetadata
                if (-not $confirmationResult['CaptureMatchesReader']) {
                    throw ("Existing lead confirmation failed: {0}" -f ([string]::Join(', ', @($confirmationResult['RejectionReasons']))))
                }

                $session['LiveTruthStatus'] = 'retained-existing'
                $session['Outcome'] = 'retained-existing'
                $session['PromotionStatus'] = 'retained-existing'
                Set-StageCompleted -Session $session -StageName 'Confirm' -ArtifactFile $resolvedCaptureConfirmationFile -Summary ([ordered]@{
                        CaptureSourceAddress = $confirmationResult['CaptureSourceAddress']
                        CaptureBasisForwardOffset = $confirmationResult['CaptureBasisForwardOffset']
                        ReaderSourceAddress = $confirmationResult['ReaderSourceAddress']
                        ReaderBasisForwardOffset = $confirmationResult['ReaderBasisForwardOffset']
                        CaptureMatchesReader = $confirmationResult['CaptureMatchesReader']
                    })
            }
            catch {
                $session['LiveTruthStatus'] = 'blocked'
                $session['Outcome'] = 'blocked'
                $session['PromotionStatus'] = 'blocked'
                $session['SessionConsistency'] = 'existing-lead-confirmation-failed'
                Set-StageFailed -Session $session -StageName 'Confirm' -ErrorMessage $_.Exception.Message -Summary $confirmationResult
            }
        }
        else {
            $session['LiveTruthStatus'] = 'blocked'
            $session['Outcome'] = 'blocked'
            $session['PromotionStatus'] = 'blocked'
            Set-StageSkipped -Session $session -StageName 'Confirm' -Reason 'No behavior-backed lead exists to retain after candidate rejection.' -Summary ([ordered]@{
                    ExistingLeadPresent = $false
                })
        }
    }
    Save-Session -Session $session
    }

    if ($RunProvenance) {
        if ([string]$session['LiveTruthStatus'] -eq 'blocked') {
            $session['ProvenanceStatus'] = 'blocked'
            Set-StageSkipped -Session $session -StageName 'Provenance' -Reason 'Provenance is blocked until live truth is green.' -Summary $null
        }
        else {
            Set-StageStarted -Session $session -StageName 'Provenance' | Out-Null
            $provenanceNotes = New-Object System.Collections.Generic.List[string]
            $successfulSteps = 0
            $failedSteps = 0
            $instructionTraceArtifact = $null

            try {
                $discoveryChainArguments = @{
                    ProcessName = $processMetadata.ProcessName
                    ProcessId = $processMetadata.ProcessId
                    TargetWindowHandle = $processMetadata.MainWindowHandleHex
                }
                & $refreshDiscoveryChainScript @discoveryChainArguments | Out-Null
                $successfulSteps++
                $provenanceNotes.Add('refresh-discovery-chain.ps1 completed successfully.') | Out-Null
            }
            catch {
                $failedSteps++
                $provenanceNotes.Add("refresh-discovery-chain.ps1 failed: $($_.Exception.Message)") | Out-Null
            }

            if ($RunInstructionTrace) {
                if ([string]::IsNullOrWhiteSpace($InstructionAddressHex)) {
                    $failedSteps++
                    $provenanceNotes.Add('Instruction trace was requested, but no InstructionAddressHex was provided.') | Out-Null
                }
                else {
                    $instructionTraceArtifact = Join-Path (Split-Path -Parent $resolvedSessionFile) 'actor-facing-instruction-trace.json'
                    try {
                        & $traceFacingInstructionScript -Json -ProcessName $processMetadata.ProcessName -ProcessId $processMetadata.ProcessId -TargetWindowHandle $processMetadata.MainWindowHandleHex -InstructionAddressHex (Normalize-HexString -Value $InstructionAddressHex) -BasisOffsetHex (Normalize-HexString -Value $InstructionBasisOffsetHex) -OutputFile $instructionTraceArtifact | Out-Null
                        $successfulSteps++
                        $provenanceNotes.Add("trace-actor-facing-instruction.ps1 completed successfully: $instructionTraceArtifact") | Out-Null
                    }
                    catch {
                        $failedSteps++
                        $provenanceNotes.Add("trace-actor-facing-instruction.ps1 failed: $($_.Exception.Message)") | Out-Null
                    }
                }
            }

            if ($failedSteps -gt 0) {
                $session['ProvenanceStatus'] = 'partial'
            }
            else {
                $session['ProvenanceStatus'] = 'confirmed'
            }

            Set-StageCompleted -Session $session -StageName 'Provenance' -ArtifactFile $instructionTraceArtifact -Summary ([ordered]@{
                    SuccessfulSteps = $successfulSteps
                    FailedSteps = $failedSteps
                    Notes = @($provenanceNotes.ToArray())
                }) -Notes @($provenanceNotes.ToArray())
        }
    }
    else {
        $session['ProvenanceStatus'] = 'not-run'
        Set-StageSkipped -Session $session -StageName 'Provenance' -Reason 'RunProvenance was not requested.' -Summary $null
    }

    $session['NextActions'] = Build-NextActions -Session $session
    Set-StageCompleted -Session $session -StageName 'Report' -ArtifactFile $resolvedSessionFile -Summary ([ordered]@{
            LiveTruthStatus = $session['LiveTruthStatus']
            ProvenanceStatus = $session['ProvenanceStatus']
            Outcome = $session['Outcome']
            WinningCandidate = $session['WinningCandidate']
        })
    Save-Session -Session $session
}
catch {
    $session['LiveTruthStatus'] = 'blocked'
    if ([string]$session['Outcome'] -eq 'pending') {
        $session['Outcome'] = 'blocked'
    }

    $session['SessionConsistency'] = 'failed'
    $session['RejectionReasons'] = @('conductor_failed')
    $session['Notes'] = @("refresh-actor-facing-discovery.ps1 failed: $($_.Exception.Message)")
    Set-StageFailed -Session $session -StageName 'Report' -ErrorMessage $_.Exception.Message -Summary $null
    Save-Session -Session $session
    throw
}

if ($Json) {
    Write-Output ((Convert-ToPlainObject -Value $session) | ConvertTo-Json -Depth 100)
    return
}

Write-SessionText -Session $session
