[CmdletBinding()]
param(
    [switch]$Json,
    [string]$ProcessName = 'rift_x64',
    [int]$MaxHits = 16,
    [int]$FullRecoveryLimit = 4,
    [int]$TriageMaxHits = 24,
    [bool]$RetestLedgerRejected = $true,
    [bool]$SkipUiClearCheck = $true,
    [bool]$RequireTargetFocus = $true,
    [bool]$SkipLiveInputWarning = $true,
    [bool]$StopOnFirstRecoveredYaw = $true,
    [bool]$RefreshReaderBridge = $true,
    [string]$OutputRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$screenScript = Join-Path $PSScriptRoot 'screen-actor-orientation-candidates.ps1'

if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path $PSScriptRoot 'captures'
}

$resolvedOutputRoot = [System.IO.Path]::GetFullPath($OutputRoot)
$ledgerFile = Join-Path $resolvedOutputRoot 'actor-orientation-candidate-ledger.aggressive.ndjson'
$screenOutputFile = Join-Path $resolvedOutputRoot 'actor-orientation-candidate-screen.aggressive.json'
$historyFile = Join-Path $resolvedOutputRoot 'actor-orientation-candidate-screen-history.aggressive.ndjson'
$triageBundleFile = Join-Path $resolvedOutputRoot 'post-update-triage-bundle.aggressive.json'
$watchSampleOutputFile = Join-Path $resolvedOutputRoot 'post-update-triage-watch-sample.aggressive.json'
$recoveryOutputDirectory = Join-Path $resolvedOutputRoot 'screening\aggressive'

function ConvertFrom-JsonCompat {
    param(
        [Parameter(Mandatory = $true)]
        [string]$JsonText,
        [int]$Depth = 20
    )

    if ($PSVersionTable.PSVersion.Major -ge 6) {
        return $JsonText | ConvertFrom-Json -Depth $Depth
    }

    return $JsonText | ConvertFrom-Json
}

function Get-OptionalPropertyValue {
    param(
        [Parameter(Mandatory = $true)]
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

function Save-JsonFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        $InputObject
    )

    $directory = Split-Path -Path $Path -Parent
    if (-not [string]::IsNullOrWhiteSpace($directory)) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }

    [System.IO.File]::WriteAllText($Path, ($InputObject | ConvertTo-Json -Depth 80))
}

function Test-RefreshFailureMessage {
    param([string]$Message)

    if ([string]::IsNullOrWhiteSpace($Message)) {
        return $false
    }

    return (
        $Message -match 'AutoHotkey helper exited with code' -or
        $Message -match 'refresh-readerbridge-export' -or
        $Message -match 'Forcing a Rift UI reload' -or
        $Message -match '/reloadui'
    )
}

function Invoke-ScriptJson {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [hashtable]$Arguments,

        [Parameter(Mandatory = $true)]
        [string]$FailureContext
    )

    try {
        $jsonText = & $Path @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "$FailureContext failed (`$LASTEXITCODE=$LASTEXITCODE)."
        }

        return ConvertFrom-JsonCompat -JsonText ([string]$jsonText) -Depth 100
    }
    catch {
        $message = $_.Exception.Message
        if ($message -match 'RequireTargetFocus failed') {
            throw "Focused PostMessage stage could not verify Rift foreground on the selected desktop. Operator action needed: activate the Rift window on Desktop 2 so it can become foreground, then rerun. Original error: $message"
        }

        throw
    }
}

function Invoke-AggressiveScreen {
    param([bool]$EnableRefresh)

    $screenArguments = @{
        Json = $true
        ProcessName = $ProcessName
        MaxHits = $MaxHits
        PreflightKey = 'D'
        DualKeyPreflight = $true
        SecondaryPreflightKey = 'A'
        FullRecoveryLimit = $FullRecoveryLimit
        MinimumYawResponseDegrees = 0.5
        MaxCoordDrift = 0.35
        MaxInterPreflightIdleDriftDegrees = 8.0
        StopOnFirstRecoveredYaw = $StopOnFirstRecoveredYaw
        LedgerFile = $ledgerFile
        HistoryFile = $historyFile
        RecoveryOutputDirectory = $recoveryOutputDirectory
        OutputFile = $screenOutputFile
    }

    if ($RetestLedgerRejected) {
        $screenArguments['RetestLedgerRejected'] = $true
    }

    if ($EnableRefresh) {
        $screenArguments['RefreshReaderBridge'] = $true
    }

    if ($SkipUiClearCheck) {
        $screenArguments['SkipUiClearCheck'] = $true
    }

    if ($RequireTargetFocus) {
        $screenArguments['RequireTargetFocus'] = $true
    }

    if ($SkipLiveInputWarning) {
        $screenArguments['SkipLiveInputWarning'] = $true
    }

    try {
        return [pscustomobject]@{
            Document = Invoke-ScriptJson -Path $screenScript -Arguments $screenArguments -FailureContext 'Aggressive candidate screen'
            RefreshReaderBridgeUsed = $EnableRefresh
            RefreshFallbackUsed = $false
            RefreshFailureMessage = $null
        }
    }
    catch {
        $message = $_.Exception.Message
        if ($EnableRefresh -and (Test-RefreshFailureMessage -Message $message)) {
            $retry = Invoke-AggressiveScreen -EnableRefresh $false
            return [pscustomobject]@{
                Document = $retry.Document
                RefreshReaderBridgeUsed = [bool]$retry.RefreshReaderBridgeUsed
                RefreshFallbackUsed = $true
                RefreshFailureMessage = $message
            }
        }

        throw
    }
}

function Invoke-ReaderJson {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        [Parameter(Mandatory = $true)]
        [string]$FailureContext
    )

    $output = & dotnet run --project $readerProject -- @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "$FailureContext failed (`$LASTEXITCODE=$exitCode): $($output -join [Environment]::NewLine)"
    }

    return ConvertFrom-JsonCompat -JsonText ($output -join [Environment]::NewLine) -Depth 100
}

function New-CandidateSummary {
    param($Result)

    if ($null -eq $Result) {
        return $null
    }

    $stimulus = Get-OptionalPropertyValue -Object $Result -Name 'Stimulus'
    $secondaryStimulus = Get-OptionalPropertyValue -Object $Result -Name 'SecondaryStimulus'
    $recovery = Get-OptionalPropertyValue -Object $Result -Name 'Recovery'

    return [pscustomobject]@{
        Rank = Get-OptionalPropertyValue -Object $Result -Name 'Rank'
        CandidateType = [string](Get-OptionalPropertyValue -Object $Result -Name 'CandidateType')
        SourceAddress = [string](Get-OptionalPropertyValue -Object $Result -Name 'SourceAddress')
        BasisForwardOffset = [string](Get-OptionalPropertyValue -Object $Result -Name 'BasisForwardOffset')
        SearchScore = Get-OptionalPropertyValue -Object $Result -Name 'SearchScore'
        PreflightPassed = [bool](Get-OptionalPropertyValue -Object $Result -Name 'PreflightPassed')
        PreflightRejectedReason = [string](Get-OptionalPropertyValue -Object $Result -Name 'PreflightRejectedReason')
        PrimaryPreflightKey = if ($null -ne $stimulus) { [string](Get-OptionalPropertyValue -Object $stimulus -Name 'Key') } else { $null }
        PrimaryYawDeltaDegrees = if ($null -ne $stimulus) { Get-OptionalPropertyValue -Object $stimulus -Name 'YawDeltaDegrees' } else { $null }
        SecondaryPreflightKey = if ($null -ne $secondaryStimulus) { [string](Get-OptionalPropertyValue -Object $secondaryStimulus -Name 'Key') } else { $null }
        SecondaryYawDeltaDegrees = if ($null -ne $secondaryStimulus) { Get-OptionalPropertyValue -Object $secondaryStimulus -Name 'YawDeltaDegrees' } else { $null }
        RecoveryRan = $null -ne $recovery
        YawRecovered = if ($null -ne $recovery) { [bool](Get-OptionalPropertyValue -Object $recovery -Name 'YawRecovered') } else { $false }
        RecoveryCandidateResponsive = if ($null -ne $recovery) { [bool](Get-OptionalPropertyValue -Object $recovery -Name 'CandidateResponsive') } else { $false }
        RecoveryCandidateRejectedReason = if ($null -ne $recovery) { [string](Get-OptionalPropertyValue -Object $recovery -Name 'CandidateRejectedReason') } else { $null }
        RecoveryOutputFile = if ($null -ne $recovery) { [string](Get-OptionalPropertyValue -Object $recovery -Name 'OutputFile') } else { $null }
    }
}

function Get-TopCandidate {
    param([object[]]$Results)

    $withRecovery = @($Results | Where-Object { $null -ne (Get-OptionalPropertyValue -Object $_ -Name 'Recovery') })
    if ($withRecovery.Count -gt 0) {
        return $withRecovery | Select-Object -First 1
    }

    $preflightPassed = @($Results | Where-Object { [bool](Get-OptionalPropertyValue -Object $_ -Name 'PreflightPassed') })
    if ($preflightPassed.Count -gt 0) {
        return $preflightPassed | Select-Object -First 1
    }

    $notSkipped = @($Results | Where-Object { -not [bool](Get-OptionalPropertyValue -Object $_ -Name 'SkippedBecauseLedger') })
    if ($notSkipped.Count -gt 0) {
        return $notSkipped | Select-Object -First 1
    }

    return ($Results | Select-Object -First 1)
}

function Get-TopRejectionReasons {
    param([object[]]$Results)

    $reasons = New-Object System.Collections.Generic.List[string]

    foreach ($result in @($Results)) {
        $preflightRejectedReason = [string](Get-OptionalPropertyValue -Object $result -Name 'PreflightRejectedReason')
        if (-not [string]::IsNullOrWhiteSpace($preflightRejectedReason)) {
            $reasons.Add($preflightRejectedReason)
        }

        $recovery = Get-OptionalPropertyValue -Object $result -Name 'Recovery'
        $recoveryRejectedReason = if ($null -ne $recovery) { [string](Get-OptionalPropertyValue -Object $recovery -Name 'CandidateRejectedReason') } else { $null }
        if (-not [string]::IsNullOrWhiteSpace($recoveryRejectedReason)) {
            $reasons.Add($recoveryRejectedReason)
        }
    }

    return @($reasons |
        Group-Object |
        Sort-Object -Property Count, Name -Descending |
        ForEach-Object {
            [pscustomobject]@{
                Reason = $_.Name
                Count = $_.Count
            }
        })
}

function Write-Result {
    param(
        [Parameter(Mandatory = $true)]
        $Document,

        [int]$ExitCode = 0
    )

    if ($Json) {
        Write-Output ($Document | ConvertTo-Json -Depth 80)
        exit $ExitCode
    }

    $responsiveCandidateCount = if ($null -ne $Document.Screening) { $Document.Screening.ResponsiveCandidateCount } else { 'n/a' }
    $recoveryRunCount = if ($null -ne $Document.Screening) { $Document.Screening.RecoveryRunCount } else { 'n/a' }

    Write-Host 'Aggressive actor-yaw discovery'
    Write-Host ("Status:                      {0}" -f $Document.Status)
    Write-Host ("Process:                     {0}" -f $Document.ProcessName)
    Write-Host ("Require target focus:        {0}" -f $Document.RequireTargetFocus)
    Write-Host ("Skip UI clear-check:         {0}" -f $Document.SkipUiClearCheck)
    Write-Host ("Skip live warning:           {0}" -f $Document.SkipLiveInputWarning)
    Write-Host ("Stop on yaw winner:          {0}" -f $Document.StopOnFirstRecoveredYaw)
    Write-Host ("Refresh requested/used:      {0} / {1}" -f $Document.RefreshReaderBridgeRequested, $Document.RefreshReaderBridgeUsed)
    Write-Host ("Refresh fallback used:       {0}" -f $Document.RefreshFallbackUsed)
    Write-Host ("Screen output:               {0}" -f $Document.Artifacts.ScreenOutputFile)
    Write-Host ("Ledger file:                 {0}" -f $Document.Artifacts.LedgerFile)
    Write-Host ("History file:                {0}" -f $Document.Artifacts.HistoryFile)
    Write-Host ("Recovery output dir:         {0}" -f $Document.Artifacts.RecoveryOutputDirectory)
    Write-Host ("Triage bundle file:          {0}" -f $Document.Artifacts.TriageBundleFile)
    if (-not [string]::IsNullOrWhiteSpace([string]$Document.Artifacts.WatchRegionSampleFile)) {
        Write-Host ("Watch sample file:           {0}" -f $Document.Artifacts.WatchRegionSampleFile)
    }
    Write-Host ("Responsive candidates:       {0}" -f $responsiveCandidateCount)
    Write-Host ("Recovery runs:               {0}" -f $recoveryRunCount)

    if ($null -ne $Document.Winner) {
        Write-Host ("Winner:                      {0} @ {1}" -f $Document.Winner.SourceAddress, $Document.Winner.BasisForwardOffset)
        Write-Host ("Winner recovery file:        {0}" -f $Document.Winner.RecoveryOutputFile)
    }
    elseif ($null -ne $Document.TopCandidate) {
        Write-Host ("Top candidate:               {0} @ {1}" -f $Document.TopCandidate.SourceAddress, $Document.TopCandidate.BasisForwardOffset)
        Write-Host ("Top rejected reason:         {0}" -f $(if (-not [string]::IsNullOrWhiteSpace([string]$Document.TopCandidate.RecoveryCandidateRejectedReason)) { $Document.TopCandidate.RecoveryCandidateRejectedReason } elseif (-not [string]::IsNullOrWhiteSpace([string]$Document.TopCandidate.PreflightRejectedReason)) { $Document.TopCandidate.PreflightRejectedReason } else { 'n/a' }))
    }

    if (-not [string]::IsNullOrWhiteSpace([string]$Document.BlockerReason)) {
        Write-Host ("Blocker reason:              {0}" -f $Document.BlockerReason)
    }

    if (-not [string]::IsNullOrWhiteSpace([string]$Document.OperatorActionNeeded)) {
        Write-Host ("Operator action:             {0}" -f $Document.OperatorActionNeeded)
    }

    foreach ($reason in @($Document.TopRejectionReasons | Select-Object -First 5)) {
        Write-Host ("Rejection signal:            {0} ({1})" -f $reason.Reason, $reason.Count)
    }

    exit $ExitCode
}

    $artifacts = [pscustomobject]@{
    OutputRoot = $resolvedOutputRoot
    LedgerFile = $ledgerFile
    ScreenOutputFile = $screenOutputFile
    HistoryFile = $historyFile
    RecoveryOutputDirectory = $recoveryOutputDirectory
    TriageBundleFile = $triageBundleFile
    WatchRegionSampleFile = $watchSampleOutputFile
}

try {
    New-Item -ItemType Directory -Path $resolvedOutputRoot -Force | Out-Null
    New-Item -ItemType Directory -Path $recoveryOutputDirectory -Force | Out-Null

    $screenRun = Invoke-AggressiveScreen -EnableRefresh $RefreshReaderBridge
    $screenDocument = $screenRun.Document
    $refreshReaderBridgeUsed = [bool]$screenRun.RefreshReaderBridgeUsed
    $refreshFallbackUsed = [bool]$screenRun.RefreshFallbackUsed
    $refreshFailureMessage = [string]$screenRun.RefreshFailureMessage
    $screenResults = @($screenDocument.Results)
    $winningResult = $screenResults | Where-Object {
            $recovery = Get-OptionalPropertyValue -Object $_ -Name 'Recovery'
            $null -ne $recovery -and [bool](Get-OptionalPropertyValue -Object $recovery -Name 'YawRecovered')
        } | Select-Object -First 1
    $topCandidate = Get-TopCandidate -Results $screenResults
    $topRejectionReasons = Get-TopRejectionReasons -Results $screenResults

    if ($null -ne $winningResult) {
        $successDocument = [pscustomobject]@{
            Mode = 'aggressive-actor-yaw-discovery'
            GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
            Status = 'success'
            ProcessName = $ProcessName
            RequireTargetFocus = $RequireTargetFocus
            SkipUiClearCheck = $SkipUiClearCheck
            SkipLiveInputWarning = $SkipLiveInputWarning
            StopOnFirstRecoveredYaw = $StopOnFirstRecoveredYaw
            RefreshReaderBridgeRequested = $RefreshReaderBridge
            RefreshReaderBridgeUsed = $refreshReaderBridgeUsed
            RefreshFallbackUsed = $refreshFallbackUsed
            RefreshFailureMessage = $(if ($refreshFallbackUsed) { $refreshFailureMessage } else { $null })
            Artifacts = [pscustomobject]@{
                OutputRoot = $resolvedOutputRoot
                LedgerFile = $ledgerFile
                ScreenOutputFile = $screenOutputFile
                HistoryFile = $historyFile
                RecoveryOutputDirectory = $recoveryOutputDirectory
                TriageBundleFile = $null
                WatchRegionSampleFile = $null
            }
            Screening = [pscustomobject]@{
                ScreenOutputFile = $screenOutputFile
                ScreenedCandidateCount = Get-OptionalPropertyValue -Object $screenDocument -Name 'ScreenedCandidateCount'
                ResponsiveCandidateCount = Get-OptionalPropertyValue -Object $screenDocument -Name 'ResponsiveCandidateCount'
                RecoveryRunCount = Get-OptionalPropertyValue -Object $screenDocument -Name 'RecoveryRunCount'
            }
            Winner = New-CandidateSummary -Result $winningResult
            TopCandidate = New-CandidateSummary -Result $topCandidate
            TopRejectionReasons = $topRejectionReasons
            BlockerReason = $null
            OperatorActionNeeded = $null
            Notes = @(
                'Focused PostMessage is the trusted live-input path for this aggressive Desktop-2 workflow.',
                $(if ($StopOnFirstRecoveredYaw) { 'The wrapper stops after the first validated yaw recovery winner.' } else { 'The wrapper may continue through additional candidates after a validated yaw recovery winner.' }),
                $(if ($refreshFallbackUsed) { 'ReaderBridge refresh failed, so the wrapper retried the screen without refresh and continued unattended.' } else { 'ReaderBridge refresh did not require fallback for this run.' })
            )
        }

        Write-Result -Document $successDocument -ExitCode 0
    }

    $null = Invoke-ReaderJson -Arguments @(
        '--process-name', $ProcessName,
        '--post-update-triage',
        '--recovery-bundle-file', $triageBundleFile,
        '--max-hits', $TriageMaxHits.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '--json') -FailureContext 'Post-update triage'

    $watchRegionSample = Invoke-ReaderJson -Arguments @(
        '--process-name', $ProcessName,
        '--sample-triage-watch-regions',
        '--recovery-bundle-file', $triageBundleFile,
        '--max-hits', $TriageMaxHits.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '--json') -FailureContext 'Watch-region sampling'

    Save-JsonFile -Path $watchSampleOutputFile -InputObject $watchRegionSample

    $blockedDocument = [pscustomobject]@{
        Mode = 'aggressive-actor-yaw-discovery'
        GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
        Status = 'blocked'
        ProcessName = $ProcessName
        RequireTargetFocus = $RequireTargetFocus
        SkipUiClearCheck = $SkipUiClearCheck
        SkipLiveInputWarning = $SkipLiveInputWarning
        StopOnFirstRecoveredYaw = $StopOnFirstRecoveredYaw
        RefreshReaderBridgeRequested = $RefreshReaderBridge
        RefreshReaderBridgeUsed = $refreshReaderBridgeUsed
        RefreshFallbackUsed = $refreshFallbackUsed
        RefreshFailureMessage = $(if ($refreshFallbackUsed) { $refreshFailureMessage } else { $null })
        Artifacts = $artifacts
        Screening = [pscustomobject]@{
            ScreenOutputFile = $screenOutputFile
            ScreenedCandidateCount = Get-OptionalPropertyValue -Object $screenDocument -Name 'ScreenedCandidateCount'
            ResponsiveCandidateCount = Get-OptionalPropertyValue -Object $screenDocument -Name 'ResponsiveCandidateCount'
            RecoveryRunCount = Get-OptionalPropertyValue -Object $screenDocument -Name 'RecoveryRunCount'
        }
        Winner = $null
        TopCandidate = New-CandidateSummary -Result $topCandidate
        TopRejectionReasons = $topRejectionReasons
        BlockerReason = 'no_validated_yaw_candidate'
        OperatorActionNeeded = $null
        Notes = @(
            'No validated yaw winner was found during aggressive screening, so post-update triage and watch-region sampling were run automatically.',
            'Focused PostMessage remained the live-input default; foreground SendInput is still not trusted here.',
            $(if ($refreshFallbackUsed) { 'ReaderBridge refresh failed, so the wrapper continued with a no-refresh fallback before triage.' } else { 'ReaderBridge refresh state did not require fallback before triage.' })
        )
    }

    Write-Result -Document $blockedDocument -ExitCode 1
}
catch {
    $message = $_.Exception.Message
    $operatorAction = $null
    $blockerReason = 'execution_failed'
    if ($message -match 'Focused PostMessage stage could not verify Rift foreground') {
        $blockerReason = 'focus_verification_failed'
        $operatorAction = 'Activate the Rift window on Desktop 2 so it can become foreground, then rerun the wrapper.'
    }

    $errorDocument = [pscustomobject]@{
        Mode = 'aggressive-actor-yaw-discovery'
        GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
        Status = 'blocked'
        ProcessName = $ProcessName
        RequireTargetFocus = $RequireTargetFocus
        SkipUiClearCheck = $SkipUiClearCheck
        SkipLiveInputWarning = $SkipLiveInputWarning
        StopOnFirstRecoveredYaw = $StopOnFirstRecoveredYaw
        RefreshReaderBridgeRequested = $RefreshReaderBridge
        RefreshReaderBridgeUsed = $false
        RefreshFallbackUsed = $false
        RefreshFailureMessage = $null
        Artifacts = $artifacts
        Screening = $null
        Winner = $null
        TopCandidate = $null
        TopRejectionReasons = @()
        BlockerReason = $blockerReason
        OperatorActionNeeded = $operatorAction
        Error = $message
        Notes = @(
            'The wrapper stops immediately on focus verification failure because Rift input is not trusted unless the game can take focus.',
            'No automatic virtual-desktop switching is attempted by this branch workflow.'
        )
    }

    Write-Result -Document $errorDocument -ExitCode 1
}
