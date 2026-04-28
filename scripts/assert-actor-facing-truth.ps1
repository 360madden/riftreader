[CmdletBinding()]
param(
    [switch]$Json,
    [string]$ProcessName = 'rift_x64',
    [string]$BehaviorBackedLeadFile = (Join-Path $PSScriptRoot 'actor-facing-behavior-backed-lead.json'),
    [string]$DiscoverySessionFile = (Join-Path $PSScriptRoot 'captures\actor-facing-discovery\session.json'),
    [string]$SourceChainFile = (Join-Path $PSScriptRoot 'captures\player-source-chain.json'),
    [string]$OutputFile = (Join-Path $PSScriptRoot 'captures\actor-facing-truth-proof.json'),
    [double]$MaxYawDeltaDegrees = 0.05,
    [double]$MaxPitchDeltaDegrees = 0.05,
    [switch]$SkipWrite
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$captureScript = Join-Path $PSScriptRoot 'capture-actor-orientation.ps1'

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

    return ConvertFrom-JsonCompat -JsonText ($output -join [Environment]::NewLine)
}

function Invoke-ScriptJson {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ScriptFile,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $output = & pwsh -NoProfile -ExecutionPolicy Bypass -File $ScriptFile @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "Script command failed (`$LASTEXITCODE=$exitCode): $($output -join [Environment]::NewLine)"
    }

    return ConvertFrom-JsonCompat -JsonText ($output -join [Environment]::NewLine)
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

    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $null
    }

    return $property.Value
}

function ConvertFrom-JsonCompat {
    param(
        [Parameter(Mandatory = $true)]
        [string]$JsonText
    )

    $command = Get-Command ConvertFrom-Json -ErrorAction Stop
    if ($command.Parameters.ContainsKey('DateKind')) {
        return $JsonText | ConvertFrom-Json -Depth 40 -DateKind String
    }

    return $JsonText | ConvertFrom-Json -Depth 40
}

function Convert-ToDateTimeOffsetOrNull {
    param($Value)

    if ($null -eq $Value) {
        return $null
    }

    if ($Value -is [DateTimeOffset]) {
        return [DateTimeOffset]$Value
    }

    $text = [string]$Value
    if ([string]::IsNullOrWhiteSpace($text)) {
        return $null
    }

    return [DateTimeOffset]::Parse($text, [System.Globalization.CultureInfo]::InvariantCulture, [System.Globalization.DateTimeStyles]::RoundtripKind)
}

function Normalize-NullableString {
    param([AllowNull()]$Value)

    if ($null -eq $Value) {
        return $null
    }

    $text = [string]$Value
    if ([string]::IsNullOrWhiteSpace($text)) {
        return $null
    }

    return $text
}

function Get-LiveProcessSnapshot {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $matches = @(Get-Process -Name $Name -ErrorAction Stop)
    if ($matches.Count -eq 0) {
        throw "Unable to find a live process named '$Name'."
    }

    $windowed = @($matches | Where-Object { $_.MainWindowHandle -ne 0 })
    if ($windowed.Count -gt 1) {
        $pidList = ($windowed | ForEach-Object { $_.Id }) -join ', '
        throw "Multiple windowed '$Name' processes were found ($pidList); actor-facing truth proof is ambiguous."
    }

    if ($windowed.Count -eq 1) {
        $selected = $windowed[0]
        $selectionNote = if ($matches.Count -gt 1) { "Selected the only windowed '$Name' process out of $($matches.Count) matches." } else { $null }
    }
    elseif ($matches.Count -eq 1) {
        $selected = $matches[0]
        $selectionNote = $null
    }
    else {
        $pidList = ($matches | ForEach-Object { $_.Id }) -join ', '
        throw "Multiple non-windowed '$Name' processes were found ($pidList); actor-facing truth proof is ambiguous."
    }

    $startTimeUtc = [DateTimeOffset]$selected.StartTime.ToUniversalTime()

    return [pscustomobject]@{
        ProcessId = [int]$selected.Id
        ProcessName = [string]$selected.ProcessName
        StartTimeUtc = $startTimeUtc
        StartTimeUtcText = $startTimeUtc.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
        MainWindowTitle = [string]$selected.MainWindowTitle
        MainWindowHandleHex = ('0x{0:X}' -f ([int64]$selected.MainWindowHandle))
        Responding = [bool]$selected.Responding
        SelectionNote = $selectionNote
    }
}

function Get-OrientationSummary {
    param(
        [Parameter(Mandatory = $true)]
        [psobject]$Document
    )

    $basisPrimaryForwardOffset = $null
    if ($Document.PSObject.Properties['BasisPrimaryForwardOffset']) {
        $basisPrimaryForwardOffset = [string]$Document.BasisPrimaryForwardOffset
    }
    elseif ($Document.PSObject.Properties['BasisForwardOffset']) {
        $basisPrimaryForwardOffset = [string]$Document.BasisForwardOffset
    }
    elseif ($Document.PSObject.Properties['LiveSourceSample'] -and $null -ne $Document.LiveSourceSample) {
        if ($Document.LiveSourceSample.PSObject.Properties['BasisPrimaryForwardOffset']) {
            $basisPrimaryForwardOffset = [string]$Document.LiveSourceSample.BasisPrimaryForwardOffset
        }
        elseif ($Document.LiveSourceSample.PSObject.Properties['ResolvedForwardOffset']) {
            $basisPrimaryForwardOffset = [string]$Document.LiveSourceSample.ResolvedForwardOffset
        }
    }

    $basisDuplicateForwardOffset = $null
    if ($Document.PSObject.Properties['BasisDuplicateForwardOffset']) {
        $basisDuplicateForwardOffset = [string]$Document.BasisDuplicateForwardOffset
    }
    elseif ($Document.PSObject.Properties['LiveSourceSample'] -and $null -ne $Document.LiveSourceSample) {
        if ($Document.LiveSourceSample.PSObject.Properties['BasisDuplicateForwardOffset']) {
            $basisDuplicateForwardOffset = [string]$Document.LiveSourceSample.BasisDuplicateForwardOffset
        }
        elseif ($Document.LiveSourceSample.PSObject.Properties['ResolvedDuplicateForwardOffset']) {
            $basisDuplicateForwardOffset = [string]$Document.LiveSourceSample.ResolvedDuplicateForwardOffset
        }
    }

    return [pscustomobject]@{
        SelectedSourceAddress = Normalize-NullableString $Document.SelectedSourceAddress
        ResolutionMode = Normalize-NullableString (Get-OptionalPropertyValue -Object $Document -Name 'ResolutionMode')
        BasisPrimaryForwardOffset = $basisPrimaryForwardOffset
        BasisDuplicateForwardOffset = $basisDuplicateForwardOffset
        PreferredYawDegrees = if ($null -ne $Document.PreferredEstimate -and $null -ne $Document.PreferredEstimate.YawDegrees) { [double]$Document.PreferredEstimate.YawDegrees } else { $null }
        PreferredPitchDegrees = if ($null -ne $Document.PreferredEstimate -and $null -ne $Document.PreferredEstimate.PitchDegrees) { [double]$Document.PreferredEstimate.PitchDegrees } else { $null }
        ArtifactFile = Normalize-NullableString (Get-OptionalPropertyValue -Object $Document -Name 'ArtifactFile')
        ArtifactGeneratedAtUtc = Normalize-NullableString (Get-OptionalPropertyValue -Object $Document -Name 'ArtifactGeneratedAtUtc')
    }
}

function Test-StringEqualsOrdinalIgnoreCase {
    param(
        [AllowNull()][string]$Left,
        [AllowNull()][string]$Right
    )

    return [string]::Equals($Left, $Right, [System.StringComparison]::OrdinalIgnoreCase)
}

function Get-LeadValidationSummary {
    param(
        [Parameter(Mandatory = $true)]
        $LeadDocument,
        [Parameter(Mandatory = $true)]
        $ProcessSnapshot
    )

    $issues = New-Object System.Collections.Generic.List[string]
    $warnings = New-Object System.Collections.Generic.List[string]

    $leadTimestampValue = if ($LeadDocument.ValidatedAtUtc) { $LeadDocument.ValidatedAtUtc } else { $LeadDocument.GeneratedAtUtc }
    $leadTimestamp = Convert-ToDateTimeOffsetOrNull -Value $leadTimestampValue
    if (-not [string]::IsNullOrWhiteSpace([string]$LeadDocument.ProcessName) -and
        -not (Test-StringEqualsOrdinalIgnoreCase -Left ([string]$LeadDocument.ProcessName) -Right ([string]$ProcessSnapshot.ProcessName))) {
        $issues.Add("Behavior-backed lead targets process '$($LeadDocument.ProcessName)', but live process is '$($ProcessSnapshot.ProcessName)'.")
    }

    if ([string]::IsNullOrWhiteSpace([string]$LeadDocument.SourceAddress)) {
        $issues.Add('Behavior-backed lead is missing SourceAddress.')
    }

    if ([string]::IsNullOrWhiteSpace([string]$LeadDocument.BasisForwardOffset)) {
        $issues.Add('Behavior-backed lead is missing BasisForwardOffset.')
    }

    if ($null -eq $leadTimestamp) {
        $warnings.Add('Behavior-backed lead has no GeneratedAtUtc/ValidatedAtUtc timestamp; same-session freshness falls back to live capture/read parity only.')
    }
    elseif ($leadTimestamp -lt $ProcessSnapshot.StartTimeUtc.AddSeconds(-1)) {
        $issues.Add("Behavior-backed lead timestamp $($leadTimestamp.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)) predates live process start $($ProcessSnapshot.StartTimeUtcText).")
    }

    $candidateDiagnostics = Get-OptionalPropertyValue -Object $LeadDocument -Name 'CandidateDiagnostics'
    $diagnosticProcessId = Get-OptionalPropertyValue -Object $candidateDiagnostics -Name 'ProcessId'
    if ($null -ne $diagnosticProcessId) {
        if ([int]$diagnosticProcessId -ne [int]$ProcessSnapshot.ProcessId) {
            $issues.Add("Behavior-backed lead candidate diagnostics target PID $diagnosticProcessId, but live PID is $($ProcessSnapshot.ProcessId).")
        }
    }
    else {
        $warnings.Add('Behavior-backed lead does not record CandidateDiagnostics.ProcessId.')
    }

    $diagnosticProcessStart = Convert-ToDateTimeOffsetOrNull -Value (Get-OptionalPropertyValue -Object $candidateDiagnostics -Name 'ProcessStartTimeUtc')
    if ($null -ne $diagnosticProcessStart) {
        $deltaSeconds = [Math]::Abs(($diagnosticProcessStart - $ProcessSnapshot.StartTimeUtc).TotalSeconds)
        if ($deltaSeconds -gt 1.0) {
            $issues.Add("Behavior-backed lead candidate diagnostics target process start $($diagnosticProcessStart.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)), but live process start is $($ProcessSnapshot.StartTimeUtcText).")
        }
    }
    else {
        $warnings.Add('Behavior-backed lead does not record CandidateDiagnostics.ProcessStartTimeUtc.')
    }

    return [pscustomobject]@{
        SourceFile = $BehaviorBackedLeadFile
        SourceAddress = Normalize-NullableString $LeadDocument.SourceAddress
        BasisForwardOffset = Normalize-NullableString $LeadDocument.BasisForwardOffset
        BasisDuplicateForwardOffset = Normalize-NullableString $LeadDocument.BasisDuplicateForwardOffset
        Status = Normalize-NullableString $LeadDocument.Status
        OperationalStatus = Normalize-NullableString $LeadDocument.OperationalStatus
        GeneratedAtUtc = if ($LeadDocument.GeneratedAtUtc) { (Convert-ToDateTimeOffsetOrNull -Value $LeadDocument.GeneratedAtUtc).ToString('O', [System.Globalization.CultureInfo]::InvariantCulture) } else { $null }
        ValidatedAtUtc = if ($LeadDocument.ValidatedAtUtc) { (Convert-ToDateTimeOffsetOrNull -Value $LeadDocument.ValidatedAtUtc).ToString('O', [System.Globalization.CultureInfo]::InvariantCulture) } else { $null }
        LeadTimestampUtc = if ($leadTimestamp) { $leadTimestamp.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture) } else { $null }
        CandidateProcessId = $diagnosticProcessId
        CandidateProcessStartTimeUtc = if ($diagnosticProcessStart) { $diagnosticProcessStart.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture) } else { $null }
        IsValid = ($issues.Count -eq 0)
        Issues = @($issues)
        Warnings = @($warnings)
    }
}

function Get-FileJsonOrNull {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return $null
    }

    return ConvertFrom-JsonCompat -JsonText (Get-Content -LiteralPath $Path -Raw)
}

function Write-Utf8Json {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$Content
    )

    $directory = Split-Path -Parent $Path
    if (-not [string]::IsNullOrWhiteSpace($directory) -and -not (Test-Path -LiteralPath $directory)) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }

    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Content, $encoding)
}

$issues = New-Object System.Collections.Generic.List[string]
$warnings = New-Object System.Collections.Generic.List[string]
$notes = New-Object System.Collections.Generic.List[string]

$processSnapshot = Get-LiveProcessSnapshot -Name $ProcessName
if ($processSnapshot.SelectionNote) {
    $notes.Add([string]$processSnapshot.SelectionNote)
}

if (-not (Test-Path -LiteralPath $BehaviorBackedLeadFile)) {
    throw "Behavior-backed lead file '$BehaviorBackedLeadFile' does not exist."
}

$leadDocument = Get-FileJsonOrNull -Path $BehaviorBackedLeadFile
if ($null -eq $leadDocument) {
    throw "Behavior-backed lead file '$BehaviorBackedLeadFile' did not contain a readable JSON document."
}

$leadSummary = Get-LeadValidationSummary -LeadDocument $leadDocument -ProcessSnapshot $processSnapshot
foreach ($leadIssue in $leadSummary.Issues) {
    $issues.Add([string]$leadIssue)
}
foreach ($leadWarning in $leadSummary.Warnings) {
    $warnings.Add([string]$leadWarning)
}

$captureDocument = Invoke-ScriptJson -ScriptFile $captureScript -Arguments @('-Json', '-ProcessName', $ProcessName)
$readerDocument = Invoke-ReaderJson -Arguments @('--process-name', $ProcessName, '--read-player-orientation', '--json')

$captureOrientation = Get-OrientationSummary -Document $captureDocument.ReaderOrientation
$readerOrientation = Get-OrientationSummary -Document $readerDocument

$leadMatchesCapture =
    (Test-StringEqualsOrdinalIgnoreCase -Left $leadSummary.SourceAddress -Right $captureOrientation.SelectedSourceAddress) -and
    (Test-StringEqualsOrdinalIgnoreCase -Left $leadSummary.BasisForwardOffset -Right $captureOrientation.BasisPrimaryForwardOffset)

$leadMatchesReader =
    (Test-StringEqualsOrdinalIgnoreCase -Left $leadSummary.SourceAddress -Right $readerOrientation.SelectedSourceAddress) -and
    (Test-StringEqualsOrdinalIgnoreCase -Left $leadSummary.BasisForwardOffset -Right $readerOrientation.BasisPrimaryForwardOffset)

$captureMatchesReaderSource = Test-StringEqualsOrdinalIgnoreCase -Left $captureOrientation.SelectedSourceAddress -Right $readerOrientation.SelectedSourceAddress
$captureMatchesReaderBasis = Test-StringEqualsOrdinalIgnoreCase -Left $captureOrientation.BasisPrimaryForwardOffset -Right $readerOrientation.BasisPrimaryForwardOffset
$captureMatchesReaderDuplicateBasis = Test-StringEqualsOrdinalIgnoreCase -Left $captureOrientation.BasisDuplicateForwardOffset -Right $readerOrientation.BasisDuplicateForwardOffset

$yawDeltaDegrees = if ($null -ne $captureOrientation.PreferredYawDegrees -and $null -ne $readerOrientation.PreferredYawDegrees) {
    [Math]::Abs([double]$captureOrientation.PreferredYawDegrees - [double]$readerOrientation.PreferredYawDegrees)
}
else {
    $null
}

$pitchDeltaDegrees = if ($null -ne $captureOrientation.PreferredPitchDegrees -and $null -ne $readerOrientation.PreferredPitchDegrees) {
    [Math]::Abs([double]$captureOrientation.PreferredPitchDegrees - [double]$readerOrientation.PreferredPitchDegrees)
}
else {
    $null
}

if (-not $leadMatchesCapture) {
    $issues.Add("Behavior-backed lead does not match capture output: lead=$($leadSummary.SourceAddress)@$($leadSummary.BasisForwardOffset); capture=$($captureOrientation.SelectedSourceAddress)@$($captureOrientation.BasisPrimaryForwardOffset).")
}

if (-not $leadMatchesReader) {
    $issues.Add("Behavior-backed lead does not match reader output: lead=$($leadSummary.SourceAddress)@$($leadSummary.BasisForwardOffset); reader=$($readerOrientation.SelectedSourceAddress)@$($readerOrientation.BasisPrimaryForwardOffset).")
}

if (-not $captureMatchesReaderSource) {
    $issues.Add("Capture and reader selected different live sources: capture=$($captureOrientation.SelectedSourceAddress); reader=$($readerOrientation.SelectedSourceAddress).")
}

if (-not $captureMatchesReaderBasis) {
    $issues.Add("Capture and reader resolved different basis forward offsets: capture=$($captureOrientation.BasisPrimaryForwardOffset); reader=$($readerOrientation.BasisPrimaryForwardOffset).")
}

if (-not $captureMatchesReaderDuplicateBasis) {
    $issues.Add("Capture and reader resolved different duplicate basis offsets: capture=$($captureOrientation.BasisDuplicateForwardOffset); reader=$($readerOrientation.BasisDuplicateForwardOffset).")
}

if ($null -ne $yawDeltaDegrees -and $yawDeltaDegrees -gt $MaxYawDeltaDegrees) {
    $issues.Add("Yaw delta $([Math]::Round($yawDeltaDegrees, 6)) deg exceeded tolerance $MaxYawDeltaDegrees deg.")
}

if ($null -ne $pitchDeltaDegrees -and $pitchDeltaDegrees -gt $MaxPitchDeltaDegrees) {
    $issues.Add("Pitch delta $([Math]::Round($pitchDeltaDegrees, 6)) deg exceeded tolerance $MaxPitchDeltaDegrees deg.")
}

if (-not ((Test-StringEqualsOrdinalIgnoreCase -Left $captureOrientation.ResolutionMode -Right 'behavior-backed-lead') -or
          (Test-StringEqualsOrdinalIgnoreCase -Left $captureOrientation.ResolutionMode -Right 'live-behavior-backed-lead'))) {
    $issues.Add("Capture resolved orientation through '$($captureOrientation.ResolutionMode)', not 'behavior-backed-lead'.")
}

if (-not ((Test-StringEqualsOrdinalIgnoreCase -Left $readerOrientation.ResolutionMode -Right 'behavior-backed-lead') -or
          (Test-StringEqualsOrdinalIgnoreCase -Left $readerOrientation.ResolutionMode -Right 'live-behavior-backed-lead'))) {
    $issues.Add("Reader resolved orientation through '$($readerOrientation.ResolutionMode)', not a behavior-backed lead mode.")
}

$discoverySession = Get-FileJsonOrNull -Path $DiscoverySessionFile
$discoverySessionSummary = $null
if ($null -ne $discoverySession) {
    $sessionProcess = Get-OptionalPropertyValue -Object $discoverySession -Name 'Process'
    $sessionProcessId = Get-OptionalPropertyValue -Object $sessionProcess -Name 'ProcessId'
    $sessionProcessStart = Convert-ToDateTimeOffsetOrNull -Value (Get-OptionalPropertyValue -Object $sessionProcess -Name 'StartTimeUtc')
    $sameProcess = ($null -ne $sessionProcessId) -and ([int]$sessionProcessId -eq [int]$processSnapshot.ProcessId)
    if ($sameProcess -and $null -ne $sessionProcessStart) {
        $sameProcess = [Math]::Abs(($sessionProcessStart - $processSnapshot.StartTimeUtc).TotalSeconds) -le 1.0
    }

    $discoverySessionSummary = [pscustomobject]@{
        File = $DiscoverySessionFile
        Exists = $true
        SameProcessSession = $sameProcess
        LiveTruthStatus = [string](Get-OptionalPropertyValue -Object $discoverySession -Name 'LiveTruthStatus')
        ProvenanceStatus = [string](Get-OptionalPropertyValue -Object $discoverySession -Name 'ProvenanceStatus')
        SessionConsistency = [string](Get-OptionalPropertyValue -Object $discoverySession -Name 'SessionConsistency')
        Outcome = [string](Get-OptionalPropertyValue -Object $discoverySession -Name 'Outcome')
        ConfirmStageStatus = [string](Get-OptionalPropertyValue -Object (Get-OptionalPropertyValue -Object (Get-OptionalPropertyValue -Object $discoverySession -Name 'Stages') -Name 'Confirm') -Name 'Status')
        ExistingLeadSourceAddress = [string](Get-OptionalPropertyValue -Object (Get-OptionalPropertyValue -Object $discoverySession -Name 'ExistingLead') -Name 'SourceAddress')
        ExistingLeadBasisForwardOffset = [string](Get-OptionalPropertyValue -Object (Get-OptionalPropertyValue -Object $discoverySession -Name 'ExistingLead') -Name 'BasisForwardOffset')
        UpdatedAtUtc = [string](Get-OptionalPropertyValue -Object $discoverySession -Name 'UpdatedAtUtc')
    }

    if (-not $sameProcess) {
        $warnings.Add("Discovery session artifact '$DiscoverySessionFile' does not target the current live process.")
    }
    elseif (-not [string]::Equals($discoverySessionSummary.SessionConsistency, 'consistent', [System.StringComparison]::OrdinalIgnoreCase)) {
        $warnings.Add("Discovery session consistency is '$($discoverySessionSummary.SessionConsistency)'.")
    }
}
else {
    $discoverySessionSummary = [pscustomobject]@{
        File = $DiscoverySessionFile
        Exists = $false
        SameProcessSession = $false
        LiveTruthStatus = $null
        ProvenanceStatus = $null
        SessionConsistency = $null
        Outcome = $null
        ConfirmStageStatus = $null
        ExistingLeadSourceAddress = $null
        ExistingLeadBasisForwardOffset = $null
        UpdatedAtUtc = $null
    }
    $warnings.Add("Discovery session artifact '$DiscoverySessionFile' is missing.")
}

$sourceChainDocument = Get-FileJsonOrNull -Path $SourceChainFile
$sourceChainSummary = $null
if ($null -ne $sourceChainDocument) {
    $sameProcess = ($null -ne $sourceChainDocument.ProcessId) -and ([int]$sourceChainDocument.ProcessId -eq [int]$processSnapshot.ProcessId)
    $sourceChainSummary = [pscustomobject]@{
        File = $SourceChainFile
        Exists = $true
        SameProcess = $sameProcess
        GeneratedAtUtc = [string](Get-OptionalPropertyValue -Object $sourceChainDocument -Name 'GeneratedAtUtc')
        RecoveryMode = [string](Get-OptionalPropertyValue -Object (Get-OptionalPropertyValue -Object $sourceChainDocument -Name 'Recovery') -Name 'Mode')
        RecoveryTriggerReason = [string](Get-OptionalPropertyValue -Object (Get-OptionalPropertyValue -Object $sourceChainDocument -Name 'Recovery') -Name 'TriggerReason')
        PatternScanAddress = [string](Get-OptionalPropertyValue -Object (Get-OptionalPropertyValue -Object $sourceChainDocument -Name 'Recovery') -Name 'PatternScanAddress')
        SourceResolveTarget = [string](Get-OptionalPropertyValue -Object (Get-OptionalPropertyValue -Object $sourceChainDocument -Name 'SourceChain') -Name 'SourceResolveTarget')
    }

    if (-not $sameProcess) {
        $warnings.Add("Source-chain artifact '$SourceChainFile' does not target the current live PID.")
    }
}
else {
    $sourceChainSummary = [pscustomobject]@{
        File = $SourceChainFile
        Exists = $false
        SameProcess = $false
        GeneratedAtUtc = $null
        RecoveryMode = $null
        RecoveryTriggerReason = $null
        PatternScanAddress = $null
        SourceResolveTarget = $null
    }
    $warnings.Add("Source-chain artifact '$SourceChainFile' is missing.")
}

$provenanceStatus = if ($discoverySessionSummary.Exists -and $discoverySessionSummary.SameProcessSession -and -not [string]::IsNullOrWhiteSpace($discoverySessionSummary.ProvenanceStatus)) {
    $discoverySessionSummary.ProvenanceStatus
}
elseif ($sourceChainSummary.Exists -and $sourceChainSummary.SameProcess) {
    'current-source-chain-artifact'
}
else {
    'unknown'
}

if ($sourceChainSummary.Exists -and $sourceChainSummary.SameProcess -and
    -not [string]::Equals($sourceChainSummary.RecoveryMode, 'rebuild-from-suggested-source-chain-pattern', [System.StringComparison]::OrdinalIgnoreCase) -and
    -not [string]::Equals($sourceChainSummary.RecoveryMode, 'reuse-previous-source-chain', [System.StringComparison]::OrdinalIgnoreCase)) {
    $warnings.Add("Source-chain recovery mode '$($sourceChainSummary.RecoveryMode)' is not one of the expected actor-facing provenance refresh paths.")
}

$result = [ordered]@{
    Mode = 'actor-facing-truth-proof'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    OutputFile = $OutputFile
    Process = $processSnapshot
    TruthStatus = if ($issues.Count -eq 0) { 'confirmed' } else { 'blocked' }
    ProvenanceStatus = $provenanceStatus
    Lead = $leadSummary
    Capture = $captureOrientation
    Reader = $readerOrientation
    LeadMatchesCapture = $leadMatchesCapture
    LeadMatchesReader = $leadMatchesReader
    CaptureMatchesReader = ($captureMatchesReaderSource -and $captureMatchesReaderBasis -and $captureMatchesReaderDuplicateBasis)
    YawDeltaDegrees = $yawDeltaDegrees
    PitchDeltaDegrees = $pitchDeltaDegrees
    MaxYawDeltaDegrees = $MaxYawDeltaDegrees
    MaxPitchDeltaDegrees = $MaxPitchDeltaDegrees
    DiscoverySession = $discoverySessionSummary
    SourceChain = $sourceChainSummary
    Notes = @($notes)
    Warnings = @($warnings)
    Issues = @($issues)
}

$jsonText = $result | ConvertTo-Json -Depth 20
if (-not $SkipWrite) {
    Write-Utf8Json -Path $OutputFile -Content $jsonText
}

if ($Json) {
    Write-Output $jsonText
}
else {
    Write-Host "Actor-facing truth proof: $($result.TruthStatus)"
    Write-Host "Live PID / process start : $($processSnapshot.ProcessId) / $($processSnapshot.StartTimeUtcText)"
    Write-Host "Lead source / basis      : $($leadSummary.SourceAddress) / $($leadSummary.BasisForwardOffset)"
    Write-Host "Capture source / basis   : $($captureOrientation.SelectedSourceAddress) / $($captureOrientation.BasisPrimaryForwardOffset)"
    Write-Host "Reader source / basis    : $($readerOrientation.SelectedSourceAddress) / $($readerOrientation.BasisPrimaryForwardOffset)"
    Write-Host "Yaw delta (deg)          : $yawDeltaDegrees"
    Write-Host "Pitch delta (deg)        : $pitchDeltaDegrees"
    Write-Host "Provenance status        : $provenanceStatus"
    if ($warnings.Count -gt 0) {
        Write-Host 'Warnings:'
        foreach ($warning in $warnings) {
            Write-Host "  - $warning"
        }
    }

    if ($issues.Count -gt 0) {
        Write-Host 'Issues:'
        foreach ($issue in $issues) {
            Write-Host "  - $issue"
        }
    }
}

if ($issues.Count -gt 0) {
    exit 1
}
