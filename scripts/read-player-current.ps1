[CmdletBinding()]
param(
    [switch]$Json,
    [switch]$SkipRefresh,
    [switch]$RefreshAnchor,
    [switch]$RefreshTraceAnchor,
    [switch]$TraceRefreshOnly,
    [switch]$RequireSmartCapture,
    [switch]$NoAhkFallback,
    [string]$ProcessName = 'rift_x64',
    [int]$RecoveryAttempts = 2,
    [string]$RecoveryKey = 'w',
    [int]$RecoveryHoldMilliseconds = 1000,
    [ValidateSet('PostMessage', 'SendInput', 'AutoHotkey', 'Auto')]
    [string]$TraceRefreshStimulusMode = 'PostMessage',
    [int]$TraceRefreshTimeoutSeconds = 75,
    [int]$ScanContextBytes = 192,
    [int]$MaxHits = 12
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$refreshScript = Join-Path $PSScriptRoot 'refresh-readerbridge-export.ps1'
$smartCaptureScript = Join-Path $PSScriptRoot 'smart-capture-player-family.ps1'
$postKeyScript = Join-Path $PSScriptRoot 'post-rift-key.ps1'
$traceScript = Join-Path $PSScriptRoot 'trace-player-coord-write.ps1'
$traceOutputFile = Join-Path $PSScriptRoot 'captures\player-coord-write-trace.json'
$traceRefreshCaptureDirectory = Join-Path $PSScriptRoot 'captures\coord-trace-refresh'
$writeWorkflowHudStatusScript = Join-Path $PSScriptRoot 'write-workflow-hud-status.ps1'
$workflowHudStatusFile = Join-Path $repoRoot 'debug\workflow-hud-status.json'
$pwshPath = (Get-Command pwsh -ErrorAction Stop).Source

function Invoke-ReaderCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $output = & dotnet run --project $readerProject -- @Arguments 2>&1
    $exitCode = $LASTEXITCODE

    return [pscustomobject]@{
        ExitCode = $exitCode
        Output = ($output -join [Environment]::NewLine)
    }
}

function Write-ReaderCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    Write-Host ""
    Write-Host "[ReadPlayerCurrent] dotnet run --project $readerProject -- $($Arguments -join ' ')" -ForegroundColor DarkGray
}

function Write-WorkflowHudStatus {
    param(
        [ValidateSet('active', 'waiting', 'blocked', 'idle')]
        [string]$State,

        [Parameter(Mandatory = $true)]
        [string]$Action,

        [int]$StaleAfterSeconds = 20
    )

    if (-not (Test-Path -LiteralPath $writeWorkflowHudStatusScript)) {
        return
    }

    try {
        & $pwshPath `
            -NoLogo `
            -NoProfile `
            -ExecutionPolicy Bypass `
            -File $writeWorkflowHudStatusScript `
            -State $State `
            -Action $Action `
            -StatusFile $workflowHudStatusFile `
            -StaleAfterSeconds $StaleAfterSeconds `
            -Quiet | Out-Null
    }
    catch {
        # HUD publishing is best-effort only and must never break the workflow.
    }
}

function Read-KeyValueFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $map = [ordered]@{}
    foreach ($line in [System.IO.File]::ReadAllLines($Path)) {
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }

        $separator = $line.IndexOf('=')
        if ($separator -lt 0) {
            continue
        }

        $key = $line.Substring(0, $separator)
        $value = $line.Substring($separator + 1)
        $map[$key] = $value
    }

    return [pscustomobject]$map
}

function Get-FirstMeaningfulLine {
    param(
        [string]$Path
    )

    if ([string]::IsNullOrWhiteSpace($Path) -or -not (Test-Path -LiteralPath $Path)) {
        return $null
    }

    $text = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
    foreach ($line in ($text -split "\r?\n")) {
        $trimmed = $line.Trim()
        if (-not [string]::IsNullOrWhiteSpace($trimmed)) {
            return $trimmed
        }
    }

    return $null
}

function Get-TraceRefreshDiagnostics {
    param(
        [string]$AttemptOutputFile,
        [string]$StatusFile,
        [string]$StdOutFile,
        [string]$StdErrFile
    )

    $attemptSummary = $null
    if (-not [string]::IsNullOrWhiteSpace($AttemptOutputFile) -and (Test-Path -LiteralPath $AttemptOutputFile)) {
        try {
            $attemptDocument = Get-Content -LiteralPath $AttemptOutputFile -Raw -Encoding UTF8 | ConvertFrom-Json -Depth 20
            $attemptItems = if ($attemptDocument.PSObject.Properties['Candidates']) { @($attemptDocument.Candidates.Attempts) } else { @() }
            $lastAttempt = @($attemptItems | Select-Object -Last 1)
            $lastAttemptItem = if ($lastAttempt.Count -gt 0) { $lastAttempt[0] } else { $null }
            $stimulus = $null
            if ($attemptDocument.PSObject.Properties['Stimulus']) {
                $stimulus = [pscustomobject]@{
                    RequestedMode = [string]$attemptDocument.Stimulus.RequestedMode
                    SelectedMode = [string]$attemptDocument.Stimulus.SelectedMode
                    Key = [string]$attemptDocument.Stimulus.Key
                    AttemptCount = @($attemptDocument.Stimulus.Attempts).Count
                }
            }

            $trace = $null
            if ($attemptDocument.PSObject.Properties['Trace']) {
                $trace = [pscustomobject]@{
                    Status = [string]$attemptDocument.Trace.Status
                    CandidateAddress = [string]$attemptDocument.Trace.CandidateAddress
                    CandidateSource = [string]$attemptDocument.Trace.CandidateSource
                    DebugAttachLabel = [string]$attemptDocument.Trace.DebugAttachLabel
                    BreakpointMethod = [string]$attemptDocument.Trace.BreakpointMethod
                    Error = [string]$attemptDocument.Trace.Error
                }
            }

            $attemptSummary = [pscustomobject]@{
                Stage = [string]$attemptDocument.Stage
                Succeeded = [bool]$attemptDocument.Succeeded
                Error = [string]$attemptDocument.Error
                CanonicalOutputWritten = [bool]$attemptDocument.CanonicalOutputWritten
                CandidateCount = if ($attemptDocument.PSObject.Properties['Candidates']) { [int]$attemptDocument.Candidates.Count } else { 0 }
                AttemptCount = $attemptItems.Count
                Stimulus = $stimulus
                Trace = $trace
                LastAttemptStatus = if ($null -ne $lastAttemptItem) { [string]$lastAttemptItem.Status } else { $null }
                LastAttemptCandidateAddress = if ($null -ne $lastAttemptItem) { [string]$lastAttemptItem.CandidateAddress } else { $null }
                LastAttemptCandidateSource = if ($null -ne $lastAttemptItem) { [string]$lastAttemptItem.CandidateSource } else { $null }
                LastAttemptCandidateFamilyId = if ($null -ne $lastAttemptItem) { [string]$lastAttemptItem.CandidateFamilyId } else { $null }
                LastAttemptStimulusKey = if ($null -ne $lastAttemptItem) { [string]$lastAttemptItem.StimulusKey } else { $null }
                LastAttemptElapsedMilliseconds = if ($null -ne $lastAttemptItem) { [int]$lastAttemptItem.ElapsedMilliseconds } else { 0 }
                LastAttemptLastObservedStatus = if ($null -ne $lastAttemptItem) { [string]$lastAttemptItem.LastObservedStatus } else { $null }
                LastAttemptObservedStatuses = if ($null -ne $lastAttemptItem) { @($lastAttemptItem.ObservedStatuses | ForEach-Object { [string]$_.Status }) } else { @() }
                RecentAttempts = @($attemptItems | Select-Object -Last 4 | ForEach-Object {
                        [pscustomobject]@{
                            CandidateAddress = [string]$_.CandidateAddress
                            CandidateSource = [string]$_.CandidateSource
                            CandidateFamilyId = [string]$_.CandidateFamilyId
                            Status = [string]$_.Status
                            LastObservedStatus = [string]$_.LastObservedStatus
                            StimulusKey = [string]$_.StimulusKey
                            ElapsedMilliseconds = [int]$_.ElapsedMilliseconds
                            DebugAttachLabel = [string]$_.DebugAttachLabel
                            BreakpointMethod = [string]$_.BreakpointMethod
                        }
                    })
            }
        }
        catch {
            $attemptSummary = [pscustomobject]@{
                Stage = 'attempt-artifact-parse-failed'
                Succeeded = $false
                Error = $_.Exception.Message
            }
        }
    }

    $lastStatus = $null
    if (-not [string]::IsNullOrWhiteSpace($StatusFile) -and (Test-Path -LiteralPath $StatusFile)) {
        try {
            $statusDocument = Read-KeyValueFile -Path $StatusFile
            $lastStatus = [pscustomobject]@{
                Status = [string]$statusDocument.status
                DebugAttachLabel = [string]$statusDocument.debugAttachLabel
                BreakpointMethod = [string]$statusDocument.breakpointMethod
                VerificationMethod = [string]$statusDocument.verificationMethod
                TargetAddress = [string]$statusDocument.targetAddress
                EffectiveAddress = [string]$statusDocument.effectiveAddress
                Error = [string]$statusDocument.error
            }
        }
        catch {
            $lastStatus = [pscustomobject]@{
                Status = 'status-file-parse-failed'
                Error = $_.Exception.Message
            }
        }
    }

    return [pscustomobject]@{
        AttemptOutputFile = $AttemptOutputFile
        StatusFile = $StatusFile
        StdOutFile = $StdOutFile
        StdErrFile = $StdErrFile
        AttemptSummary = $attemptSummary
        LastStatus = $lastStatus
        StdOutSummary = Get-FirstMeaningfulLine -Path $StdOutFile
        StdErrSummary = Get-FirstMeaningfulLine -Path $StdErrFile
    }
}

function Get-TraceRefreshAttemptSummaryText {
    param(
        [object]$Diagnostics
    )

    if ($null -eq $Diagnostics -or $null -eq $Diagnostics.AttemptSummary) {
        return $null
    }

    $summary = $Diagnostics.AttemptSummary
    $parts = New-Object System.Collections.Generic.List[string]

    $lastStatus = [string]$summary.LastAttemptStatus
    $lastCandidate = [string]$summary.LastAttemptCandidateAddress
    $lastSource = [string]$summary.LastAttemptCandidateSource
    $lastKey = [string]$summary.LastAttemptStimulusKey
    $lastObservedStatus = [string]$summary.LastAttemptLastObservedStatus
    if (-not [string]::IsNullOrWhiteSpace($lastStatus)) {
        $parts.Add(("last={0} {1} [{2}] key={3} observed={4}" -f $lastStatus, $lastCandidate, $lastSource, $lastKey, $lastObservedStatus)) | Out-Null
    }

    $recentAttempts = @($summary.RecentAttempts)
    if ($recentAttempts.Count -gt 0) {
        $recentSummary = @($recentAttempts | ForEach-Object {
                "{0}:{1}[{2}] key={3}" -f $_.CandidateAddress, $_.Status, $_.CandidateSource, $_.StimulusKey
            }) -join '; '
        if (-not [string]::IsNullOrWhiteSpace($recentSummary)) {
            $parts.Add(("recent={0}" -f $recentSummary)) | Out-Null
        }
    }

    if ($parts.Count -le 0) {
        return $null
    }

    return ($parts -join ' | ')
}

function Invoke-CoordTraceRefreshPass {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PassName,

        [Parameter(Mandatory = $true)]
        [string]$StimulusMode,

        [Parameter(Mandatory = $true)]
        [ValidateSet('Write', 'Access')]
        [string]$WatchMode,

        [Parameter(Mandatory = $true)]
        [string[]]$AttachPreferences,

        [Parameter(Mandatory = $true)]
        [string[]]$BreakpointMethods,

        [Parameter(Mandatory = $true)]
        [string[]]$StimulusKeys,

        [Parameter(Mandatory = $true)]
        [int]$MovementHoldMilliseconds,

        [Parameter(Mandatory = $true)]
        [int]$TraceTimeoutSeconds,

        [Parameter(Mandatory = $true)]
        [int]$ProcessTimeoutSeconds,

        [datetime]$BeforeWriteTimeUtc,

        [switch]$TrustStimulusMode,

        [switch]$SamplePlayerCurrentDuringTrace,

        [Parameter(Mandatory = $true)]
        [string]$StdOutFile,

        [Parameter(Mandatory = $true)]
        [string]$StdErrFile,

        [Parameter(Mandatory = $true)]
        [string]$TraceStatusFile,

        [Parameter(Mandatory = $true)]
        [string]$TraceAttemptOutputFile
    )

    $passResult = [ordered]@{
        PassName = $PassName
        StimulusMode = $StimulusMode
        WatchMode = $WatchMode
        ExitCode = $null
        TimedOut = $false
        Error = $null
        Reason = $null
        AttemptOutputFile = $TraceAttemptOutputFile
        StatusFile = $TraceStatusFile
        Diagnostics = $null
        ArtifactUpdated = $false
        AfterArtifactWriteTimeUtc = $null
    }

    try {
        $traceArgumentList = @(
            '-NoLogo',
            '-NoProfile',
            '-File', ('"{0}"' -f $traceScript),
            '-Json',
            '-SkipRefresh',
            '-ProcessName', $ProcessName,
            '-StimulusMode', $StimulusMode,
            '-WatchMode', $WatchMode,
            '-TraceStimulusKeysCsv', ('"{0}"' -f ($StimulusKeys -join ',')),
            '-AttachPreferenceSequenceCsv', ('"{0}"' -f ($AttachPreferences -join ',')),
            '-BreakpointMethodSequenceCsv', ('"{0}"' -f ($BreakpointMethods -join ',')),
            '-MovementHoldMilliseconds', $MovementHoldMilliseconds.ToString([System.Globalization.CultureInfo]::InvariantCulture),
            '-TimeoutSeconds', $TraceTimeoutSeconds.ToString([System.Globalization.CultureInfo]::InvariantCulture),
            '-MaxCandidates', '4',
            '-TraceStatusFile', ('"{0}"' -f $TraceStatusFile),
            '-AttemptOutputFile', ('"{0}"' -f $TraceAttemptOutputFile)
        )

        if ($TrustStimulusMode) {
            $traceArgumentList += '-TrustStimulusMode'
        }

        if ($SamplePlayerCurrentDuringTrace) {
            $traceArgumentList += '-SamplePlayerCurrentDuringTrace'
        }

        $traceArgumentList = $traceArgumentList -join ' '

        $traceProcess = Start-Process -FilePath $pwshPath -ArgumentList $traceArgumentList -PassThru -WindowStyle Hidden -RedirectStandardOutput $StdOutFile -RedirectStandardError $StdErrFile

        if (-not $traceProcess.WaitForExit(($ProcessTimeoutSeconds * 1000))) {
            try {
                Stop-Process -Id $traceProcess.Id -Force -ErrorAction Stop
            }
            catch {
                # Best-effort stop only.
            }

            $passResult.TimedOut = $true
            $passResult.Diagnostics = Get-TraceRefreshDiagnostics -AttemptOutputFile $TraceAttemptOutputFile -StatusFile $TraceStatusFile -StdOutFile $StdOutFile -StdErrFile $StdErrFile
            $timedOutLastStatus = if ($null -ne $passResult.Diagnostics -and $null -ne $passResult.Diagnostics.LastStatus) { [string]$passResult.Diagnostics.LastStatus.Status } else { $null }
            $timedOutLastAttemptStatus = if ($null -ne $passResult.Diagnostics -and $null -ne $passResult.Diagnostics.AttemptSummary) { [string]$passResult.Diagnostics.AttemptSummary.LastAttemptStatus } else { $null }
            if ($timedOutLastStatus -eq 'armed' -or $timedOutLastAttemptStatus -eq 'armed-no-hit') {
                $passResult.Reason = 'trace-refresh-armed-no-hit'
                $passResult.Error = Get-TraceRefreshAttemptSummaryText -Diagnostics $passResult.Diagnostics
            }
            else {
                $passResult.Reason = 'trace-refresh-timeout'
            }

            return [pscustomobject]$passResult
        }

        $stdoutText = if (Test-Path -LiteralPath $StdOutFile) { Get-Content -LiteralPath $StdOutFile -Raw } else { '' }
        $stderrText = if (Test-Path -LiteralPath $StdErrFile) { Get-Content -LiteralPath $StdErrFile -Raw } else { '' }
        $passResult.ExitCode = $traceProcess.ExitCode

        if ($traceProcess.ExitCode -ne 0) {
            $detail = @($stdoutText, $stderrText) |
                Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
                ForEach-Object { $_.Trim() } |
                Select-Object -First 1

            $passResult.Diagnostics = Get-TraceRefreshDiagnostics -AttemptOutputFile $TraceAttemptOutputFile -StatusFile $TraceStatusFile -StdOutFile $StdOutFile -StdErrFile $StdErrFile
            $nonzeroLastStatus = if ($null -ne $passResult.Diagnostics -and $null -ne $passResult.Diagnostics.LastStatus) { [string]$passResult.Diagnostics.LastStatus.Status } else { $null }
            $nonzeroLastAttemptStatus = if ($null -ne $passResult.Diagnostics -and $null -ne $passResult.Diagnostics.AttemptSummary) { [string]$passResult.Diagnostics.AttemptSummary.LastAttemptStatus } else { $null }
            if ($nonzeroLastStatus -eq 'armed' -or $nonzeroLastAttemptStatus -eq 'armed-no-hit') {
                $passResult.Reason = 'trace-refresh-armed-no-hit'
                $passResult.Error = Get-TraceRefreshAttemptSummaryText -Diagnostics $passResult.Diagnostics
            }
            else {
                $passResult.Reason = 'trace-refresh-nonzero-exit'
                $passResult.Error = $detail
            }

            return [pscustomobject]$passResult
        }

        $afterWriteTimeUtc = if (Test-Path -LiteralPath $traceOutputFile) {
            (Get-Item -LiteralPath $traceOutputFile).LastWriteTimeUtc
        }
        else {
            $null
        }

        $artifactUpdated = $null -ne $afterWriteTimeUtc -and ($null -eq $beforeWriteTimeUtc -or $afterWriteTimeUtc -gt $beforeWriteTimeUtc)
        $passResult.AfterArtifactWriteTimeUtc = if ($null -ne $afterWriteTimeUtc) { $afterWriteTimeUtc.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture) } else { $null }
        $passResult.ArtifactUpdated = $artifactUpdated
        if (-not $artifactUpdated) {
            $passResult.Reason = 'trace-artifact-not-updated'
            $passResult.Diagnostics = Get-TraceRefreshDiagnostics -AttemptOutputFile $TraceAttemptOutputFile -StatusFile $TraceStatusFile -StdOutFile $StdOutFile -StdErrFile $StdErrFile
            return [pscustomobject]$passResult
        }

        $passResult.Reason = 'trace-artifact-updated'
        return [pscustomobject]$passResult
    }
    catch {
        $passResult.Reason = 'trace-refresh-exception'
        $passResult.Error = $_.Exception.Message
        $passResult.Diagnostics = Get-TraceRefreshDiagnostics -AttemptOutputFile $TraceAttemptOutputFile -StatusFile $TraceStatusFile -StdOutFile $StdOutFile -StdErrFile $StdErrFile
        return [pscustomobject]$passResult
    }
}

function Try-RefreshTraceAnchor {
    $result = [ordered]@{
        Mode = 'player-current-trace-refresh'
        Attempted = $false
        ProcessName = $ProcessName
        StimulusMode = $TraceRefreshStimulusMode
        ProcessTimeoutSeconds = $TraceRefreshTimeoutSeconds
        TraceOutputFile = $traceOutputFile
        BeforeArtifactWriteTimeUtc = if (Test-Path -LiteralPath $traceOutputFile) { (Get-Item -LiteralPath $traceOutputFile).LastWriteTimeUtc.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture) } else { $null }
        AfterArtifactWriteTimeUtc = $null
        ArtifactUpdated = $false
        ExitCode = $null
        TimedOut = $false
        Error = $null
        Reason = $null
        AttemptOutputFile = $null
        StatusFile = $null
        Diagnostics = $null
    }

    $anchorProbeArguments = @(
        '--process-name', $ProcessName,
        '--read-player-coord-anchor',
        '--json'
    )

    $anchorProbe = Invoke-ReaderCommand -Arguments $anchorProbeArguments
    if ($anchorProbe.ExitCode -ne 0) {
        Write-WorkflowHudStatus -State 'waiting' -Action 'coord trace unavailable' -StaleAfterSeconds 30
        Write-Host "[ReadPlayerCurrent] No usable coord-trace anchor artifact is available yet; skipping trace refresh." -ForegroundColor DarkGray
        $result.Reason = 'no-usable-anchor-artifact'
        return [pscustomobject]$result
    }

    $anchorState = $null
    try {
        $anchorState = $anchorProbe.Output | ConvertFrom-Json -Depth 20
    }
    catch {
        Write-WorkflowHudStatus -State 'blocked' -Action 'coord trace parse failed' -StaleAfterSeconds 60
        Write-Warning ("Unable to parse coord-trace anchor state; skipping trace refresh. {0}" -f $_.Exception.Message)
        $result.Reason = 'anchor-parse-failed'
        $result.Error = $_.Exception.Message
        return [pscustomobject]$result
    }

    if ($anchorState.TraceMatchesProcess -eq $true) {
        Write-WorkflowHudStatus -State 'active' -Action 'coord anchor current' -StaleAfterSeconds 30
        Write-Host "[ReadPlayerCurrent] Coord-trace anchor already matches the current Rift process." -ForegroundColor DarkGray
        $result.Reason = 'anchor-already-matches-process'
        return [pscustomobject]$result
    }

    Write-Host ""
    Write-Host "[ReadPlayerCurrent] Coord-trace anchor is stale; attempting a fresh coord trace for the current process..." -ForegroundColor Cyan
    $result.Attempted = $true
    $result.Reason = 'anchor-stale'
    Write-WorkflowHudStatus -State 'waiting' -Action 'coord trace refresh' -StaleAfterSeconds 60

    $beforeWriteTimeUtc = if (Test-Path -LiteralPath $traceOutputFile) {
        (Get-Item -LiteralPath $traceOutputFile).LastWriteTimeUtc
    }
    else {
        $null
    }

    New-Item -ItemType Directory -Path $traceRefreshCaptureDirectory -Force | Out-Null
    $traceRefreshId = [guid]::NewGuid().ToString('N')
    $stdoutPath = Join-Path $traceRefreshCaptureDirectory ("coord-trace-refresh-{0}.stdout.log" -f $traceRefreshId)
    $stderrPath = Join-Path $traceRefreshCaptureDirectory ("coord-trace-refresh-{0}.stderr.log" -f $traceRefreshId)
    $traceStatusPath = Join-Path $traceRefreshCaptureDirectory ("coord-trace-refresh-{0}.status.txt" -f $traceRefreshId)
    $traceAttemptOutputFile = Join-Path $traceRefreshCaptureDirectory ("coord-trace-refresh-{0}.attempt.json" -f $traceRefreshId)
    $result.AttemptOutputFile = $traceAttemptOutputFile
    $result.StatusFile = $traceStatusPath
    $traceStimulusKeys = New-Object System.Collections.Generic.List[string]
    $traceStimulusKeySeen = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($key in @($RecoveryKey, 'w', 'd')) {
        $normalizedKey = [string]$key
        if ([string]::IsNullOrWhiteSpace($normalizedKey)) {
            continue
        }

        $normalizedKey = $normalizedKey.Trim()
        if ($traceStimulusKeySeen.Add($normalizedKey)) {
            $traceStimulusKeys.Add($normalizedKey) | Out-Null
        }
    }

    $traceStimulusModes = New-Object System.Collections.Generic.List[string]
    $traceStimulusModeSeen = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
    $configuredTraceStimulusMode = [string]$TraceRefreshStimulusMode
    if ([string]::IsNullOrWhiteSpace($configuredTraceStimulusMode) -or $configuredTraceStimulusMode -eq 'Auto') {
        $configuredTraceStimulusMode = 'PostMessage'
    }

    foreach ($mode in @($configuredTraceStimulusMode, 'PostMessage', 'SendInput')) {
        $normalizedMode = [string]$mode
        if ([string]::IsNullOrWhiteSpace($normalizedMode)) {
            continue
        }

        $normalizedMode = $normalizedMode.Trim()
        if ($traceStimulusModeSeen.Add($normalizedMode)) {
            $traceStimulusModes.Add($normalizedMode) | Out-Null
        }
    }

    $passResults = New-Object System.Collections.Generic.List[object]
    $tracePasses = New-Object System.Collections.Generic.List[object]
    for ($modeIndex = 0; $modeIndex -lt $traceStimulusModes.Count; $modeIndex++) {
        $passStimulusMode = [string]$traceStimulusModes[$modeIndex]
        $passName = if ($modeIndex -eq 0) { 'debug-register' } else { 'debug-register-{0}' -f $passStimulusMode.ToLowerInvariant() }
        $tracePasses.Add([pscustomobject]@{
                Name = $passName
                StimulusMode = $passStimulusMode
                WatchMode = 'Write'
                TrustStimulusMode = $true
                SamplePlayerCurrentDuringTrace = ($modeIndex -gt 0)
                AttachPreferences = @('interface-2')
                BreakpointMethods = @('debug-register')
                MovementHoldMilliseconds = 650
                TimeoutSeconds = 3
            }) | Out-Null
    }

    $pageExceptionStimulusMode = if ($traceStimulusModes.Count -gt 1) { [string]$traceStimulusModes[1] } else { [string]$traceStimulusModes[0] }
    $tracePasses.Add([pscustomobject]@{
            Name = 'page-exception'
            StimulusMode = $pageExceptionStimulusMode
            WatchMode = 'Write'
            TrustStimulusMode = $true
            SamplePlayerCurrentDuringTrace = $true
            AttachPreferences = @('interface-2')
            BreakpointMethods = @('page-exception')
            MovementHoldMilliseconds = 650
            TimeoutSeconds = 3
        }) | Out-Null
    $tracePasses.Add([pscustomobject]@{
            Name = 'debug-register-access'
            StimulusMode = $pageExceptionStimulusMode
            WatchMode = 'Access'
            TrustStimulusMode = $true
            SamplePlayerCurrentDuringTrace = $true
            AttachPreferences = @('interface-2')
            BreakpointMethods = @('debug-register')
            MovementHoldMilliseconds = 650
            TimeoutSeconds = 3
        }) | Out-Null

    for ($passIndex = 0; $passIndex -lt $tracePasses.Count; $passIndex++) {
        $pass = $tracePasses[$passIndex]
        $passSlug = ((([string]$pass.Name) -replace '[^a-zA-Z0-9]+', '-').Trim('-')).ToLowerInvariant()
        $passStdOutPath = Join-Path $traceRefreshCaptureDirectory ("coord-trace-refresh-{0}-{1}.stdout.log" -f $traceRefreshId, $passSlug)
        $passStdErrPath = Join-Path $traceRefreshCaptureDirectory ("coord-trace-refresh-{0}-{1}.stderr.log" -f $traceRefreshId, $passSlug)
        $passTraceStatusPath = Join-Path $traceRefreshCaptureDirectory ("coord-trace-refresh-{0}-{1}.status.txt" -f $traceRefreshId, $passSlug)
        $passTraceAttemptOutputFile = Join-Path $traceRefreshCaptureDirectory ("coord-trace-refresh-{0}-{1}.attempt.json" -f $traceRefreshId, $passSlug)

        Write-WorkflowHudStatus -State 'active' -Action ('coord trace {0}' -f $passSlug) -StaleAfterSeconds 60
        $passResult = Invoke-CoordTraceRefreshPass `
            -PassName $pass.Name `
            -StimulusMode ([string]$pass.StimulusMode) `
            -WatchMode ([string]$pass.WatchMode) `
            -AttachPreferences @($pass.AttachPreferences) `
            -BreakpointMethods @($pass.BreakpointMethods) `
            -StimulusKeys @($traceStimulusKeys) `
            -MovementHoldMilliseconds ([int]$pass.MovementHoldMilliseconds) `
            -TraceTimeoutSeconds ([int]$pass.TimeoutSeconds) `
            -ProcessTimeoutSeconds $TraceRefreshTimeoutSeconds `
            -BeforeWriteTimeUtc $beforeWriteTimeUtc `
            -TrustStimulusMode:([bool]$pass.TrustStimulusMode) `
            -SamplePlayerCurrentDuringTrace:([bool]$pass.SamplePlayerCurrentDuringTrace) `
            -StdOutFile $passStdOutPath `
            -StdErrFile $passStdErrPath `
            -TraceStatusFile $passTraceStatusPath `
            -TraceAttemptOutputFile $passTraceAttemptOutputFile

        $passResults.Add($passResult) | Out-Null
        $result.ExitCode = $passResult.ExitCode
        $result.TimedOut = $passResult.TimedOut
        $result.Error = $passResult.Error
        $result.Reason = $passResult.Reason
        $result.AttemptOutputFile = $passResult.AttemptOutputFile
        $result.StatusFile = $passResult.StatusFile
        $result.Diagnostics = $passResult.Diagnostics
        $result.ArtifactUpdated = $passResult.ArtifactUpdated
        $result.AfterArtifactWriteTimeUtc = $passResult.AfterArtifactWriteTimeUtc
        $result.PassResults = @($passResults.ToArray())

        if ($passResult.Reason -eq 'trace-artifact-updated') {
            Write-WorkflowHudStatus -State 'active' -Action 'coord trace updated' -StaleAfterSeconds 30
            Write-Host ("[ReadPlayerCurrent] Coord-trace refresh updated {0} using {1} stimulus via pass '{2}'." -f $traceOutputFile, $passResult.StimulusMode, $pass.Name) -ForegroundColor DarkGray
            return [pscustomobject]$result
        }

        $hasFallbackPass = ($passIndex + 1) -lt $tracePasses.Count
        if ($passResult.Reason -eq 'trace-refresh-armed-no-hit' -and $hasFallbackPass) {
            $nextPass = $tracePasses[$passIndex + 1]
            Write-Host ("[ReadPlayerCurrent] Coord-trace pass '{0}' armed but saw no hit; escalating to '{1}' ({2})." -f $pass.Name, $nextPass.Name, $nextPass.StimulusMode) -ForegroundColor DarkGray
            continue
        }

        switch ($passResult.Reason) {
            'trace-refresh-timeout' {
                Write-WorkflowHudStatus -State 'blocked' -Action 'coord trace timeout' -StaleAfterSeconds 90
                Write-Warning ("Coord-trace refresh pass '{0}' timed out after {1}s; leaving the existing coord anchor in place." -f $pass.Name, $TraceRefreshTimeoutSeconds)
            }
            'trace-refresh-armed-no-hit' {
                Write-WorkflowHudStatus -State 'blocked' -Action 'coord trace armed no hit' -StaleAfterSeconds 90
                Write-Warning ("Coord-trace refresh pass '{0}' armed but saw no coord-write hit; leaving the existing coord anchor in place. {1}" -f $pass.Name, $passResult.Error)
            }
            'trace-refresh-nonzero-exit' {
                Write-WorkflowHudStatus -State 'blocked' -Action 'coord trace failed' -StaleAfterSeconds 90
                if ($passResult.Error) {
                    Write-Warning ("Coord-trace refresh pass '{0}' exited with code {1}; continuing without a fresh trace anchor. {2}" -f $pass.Name, $passResult.ExitCode, $passResult.Error)
                }
                else {
                    Write-Warning ("Coord-trace refresh pass '{0}' exited with code {1}; continuing without a fresh trace anchor." -f $pass.Name, $passResult.ExitCode)
                }
            }
            'trace-artifact-not-updated' {
                Write-WorkflowHudStatus -State 'blocked' -Action 'coord trace stale' -StaleAfterSeconds 90
                Write-Warning ("Coord-trace refresh pass '{0}' completed without updating the canonical player-coord-write-trace artifact; continuing without a fresh trace anchor." -f $pass.Name)
            }
            default {
                Write-WorkflowHudStatus -State 'blocked' -Action 'coord trace exception' -StaleAfterSeconds 90
                Write-Warning ("Coord-trace refresh pass '{0}' failed; continuing without a fresh trace anchor. {1}" -f $pass.Name, $passResult.Error)
            }
        }

        return [pscustomobject]$result
    }

    return [pscustomobject]$result
}

function Invoke-RecoveryMove {
    param(
        [Parameter(Mandatory = $true)]
        [int]$AttemptNumber
    )

    Write-Host ""
    Write-Host "[ReadPlayerCurrent] Recovery attempt $AttemptNumber/${RecoveryAttempts}: nudging the player to reacquire a full family..." -ForegroundColor Yellow
    & $postKeyScript -Key $RecoveryKey -HoldMilliseconds $RecoveryHoldMilliseconds

    $refreshArguments = @{
        NoReader = $true
    }
    if ($NoAhkFallback) {
        $refreshArguments['NoAhkFallback'] = $true
    }

    & $refreshScript @refreshArguments
}

if (-not $SkipRefresh) {
    Write-Host "[ReadPlayerCurrent] Refreshing ReaderBridge export first..." -ForegroundColor Cyan
    $refreshArguments = @{
        NoReader = $true
    }
    if ($NoAhkFallback) {
        $refreshArguments['NoAhkFallback'] = $true
    }

    & $refreshScript @refreshArguments
}

if ($RefreshTraceAnchor) {
    $traceRefreshResult = Try-RefreshTraceAnchor
    if ($TraceRefreshOnly) {
        if ($Json) {
            Write-Output (($traceRefreshResult | Microsoft.PowerShell.Utility\ConvertTo-Json -Depth 8 -Compress))
        }
        else {
            Write-Host ("[ReadPlayerCurrent] Trace refresh only result: {0}" -f (($traceRefreshResult | Microsoft.PowerShell.Utility\ConvertTo-Json -Depth 8 -Compress)))
        }

        exit 0
    }
}

if ($RefreshAnchor) {
    Write-Host ""
    Write-Host "[ReadPlayerCurrent] Refreshing the CE-backed player-family confirmation..." -ForegroundColor Cyan
    try {
        & $smartCaptureScript -ProcessName $ProcessName -ScanContextBytes $ScanContextBytes -MaxScanHits $MaxHits | Out-Null
    }
    catch {
        if ($RequireSmartCapture) {
            throw
        }

        Write-Warning ("CE-backed smart capture failed; continuing with normal family selection. {0}" -f $_.Exception.Message)
    }
}

$readerArguments = @(
    '--process-name', $ProcessName,
    '--read-player-current',
    '--scan-context', $ScanContextBytes.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '--max-hits', $MaxHits.ToString([System.Globalization.CultureInfo]::InvariantCulture)
)

if ($Json) {
    $readerArguments += '--json'
}

Write-ReaderCommand -Arguments $readerArguments
$readerResult = Invoke-ReaderCommand -Arguments $readerArguments
if ($readerResult.ExitCode -eq 0) {
    Write-Output $readerResult.Output
    exit 0
}

for ($attempt = 1; $attempt -le $RecoveryAttempts; $attempt++) {
    Invoke-RecoveryMove -AttemptNumber $attempt
    Write-ReaderCommand -Arguments $readerArguments
    $readerResult = Invoke-ReaderCommand -Arguments $readerArguments
    if ($readerResult.ExitCode -eq 0) {
        Write-Output $readerResult.Output
        exit 0
    }
}

Write-Error $readerResult.Output
exit $readerResult.ExitCode
