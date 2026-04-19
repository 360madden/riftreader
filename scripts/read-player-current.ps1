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
                AttemptCount = if ($attemptDocument.PSObject.Properties['Candidates']) { @($attemptDocument.Candidates.Attempts).Count } else { 0 }
                Stimulus = $stimulus
                Trace = $trace
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

    try {
        $traceArgumentList = @(
            '-NoLogo',
            '-NoProfile',
            '-File', ('"{0}"' -f $traceScript),
            '-Json',
            '-SkipRefresh',
            '-ProcessName', $ProcessName,
            '-StimulusMode', $TraceRefreshStimulusMode,
            '-TrustStimulusMode',
            '-TimeoutSeconds', '8',
            '-MaxCandidates', '4',
            '-TraceStatusFile', ('"{0}"' -f $traceStatusPath),
            '-AttemptOutputFile', ('"{0}"' -f $traceAttemptOutputFile)
        ) -join ' '

        Write-WorkflowHudStatus -State 'active' -Action 'coord trace launch' -StaleAfterSeconds 60
        $traceProcess = Start-Process -FilePath $pwshPath -ArgumentList $traceArgumentList -PassThru -WindowStyle Hidden -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath

        if (-not $traceProcess.WaitForExit(($TraceRefreshTimeoutSeconds * 1000))) {
            try {
                Stop-Process -Id $traceProcess.Id -Force -ErrorAction Stop
            }
            catch {
                Write-Warning ("Coord-trace refresh timed out after {0}s and the helper could not be stopped cleanly. {1}" -f $TraceRefreshTimeoutSeconds, $_.Exception.Message)
            }

            $result.TimedOut = $true
            $result.Reason = 'trace-refresh-timeout'
            $result.Diagnostics = Get-TraceRefreshDiagnostics -AttemptOutputFile $traceAttemptOutputFile -StatusFile $traceStatusPath -StdOutFile $stdoutPath -StdErrFile $stderrPath
            Write-WorkflowHudStatus -State 'blocked' -Action 'coord trace timeout' -StaleAfterSeconds 90
            Write-Warning ("Coord-trace refresh timed out after {0}s; leaving the existing coord anchor in place." -f $TraceRefreshTimeoutSeconds)
            return [pscustomobject]$result
        }

        $stdoutText = if (Test-Path -LiteralPath $stdoutPath) { Get-Content -LiteralPath $stdoutPath -Raw } else { '' }
        $stderrText = if (Test-Path -LiteralPath $stderrPath) { Get-Content -LiteralPath $stderrPath -Raw } else { '' }
        $result.ExitCode = $traceProcess.ExitCode

        if ($traceProcess.ExitCode -ne 0) {
            $detail = @($stdoutText, $stderrText) |
                Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
                ForEach-Object { $_.Trim() } |
                Select-Object -First 1
            $result.Reason = 'trace-refresh-nonzero-exit'
            $result.Error = $detail
            $result.Diagnostics = Get-TraceRefreshDiagnostics -AttemptOutputFile $traceAttemptOutputFile -StatusFile $traceStatusPath -StdOutFile $stdoutPath -StdErrFile $stderrPath
            Write-WorkflowHudStatus -State 'blocked' -Action 'coord trace failed' -StaleAfterSeconds 90
            if ($detail) {
                Write-Warning ("Coord-trace refresh exited with code {0}; continuing without a fresh trace anchor. {1}" -f $traceProcess.ExitCode, $detail)
            }
            else {
                Write-Warning ("Coord-trace refresh exited with code {0}; continuing without a fresh trace anchor." -f $traceProcess.ExitCode)
            }

            return [pscustomobject]$result
        }

        $afterWriteTimeUtc = if (Test-Path -LiteralPath $traceOutputFile) {
            (Get-Item -LiteralPath $traceOutputFile).LastWriteTimeUtc
        }
        else {
            $null
        }

        $artifactUpdated = $null -ne $afterWriteTimeUtc -and ($null -eq $beforeWriteTimeUtc -or $afterWriteTimeUtc -gt $beforeWriteTimeUtc)
        $result.AfterArtifactWriteTimeUtc = if ($null -ne $afterWriteTimeUtc) { $afterWriteTimeUtc.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture) } else { $null }
        $result.ArtifactUpdated = $artifactUpdated
        if (-not $artifactUpdated) {
            $result.Reason = 'trace-artifact-not-updated'
            $result.Diagnostics = Get-TraceRefreshDiagnostics -AttemptOutputFile $traceAttemptOutputFile -StatusFile $traceStatusPath -StdOutFile $stdoutPath -StdErrFile $stderrPath
            Write-WorkflowHudStatus -State 'blocked' -Action 'coord trace stale' -StaleAfterSeconds 90
            Write-Warning "Coord-trace refresh completed without updating the canonical player-coord-write-trace artifact; continuing without a fresh trace anchor."
            return [pscustomobject]$result
        }

        $result.Reason = 'trace-artifact-updated'
        Write-WorkflowHudStatus -State 'active' -Action 'coord trace updated' -StaleAfterSeconds 30
        Write-Host ("[ReadPlayerCurrent] Coord-trace refresh updated {0} using {1} stimulus." -f $traceOutputFile, $TraceRefreshStimulusMode) -ForegroundColor DarkGray
        return [pscustomobject]$result
    }
    catch {
        $result.Reason = 'trace-refresh-exception'
        $result.Error = $_.Exception.Message
        $result.Diagnostics = Get-TraceRefreshDiagnostics -AttemptOutputFile $traceAttemptOutputFile -StatusFile $traceStatusPath -StdOutFile $stdoutPath -StdErrFile $stderrPath
        Write-WorkflowHudStatus -State 'blocked' -Action 'coord trace exception' -StaleAfterSeconds 90
        Write-Warning ("Coord-trace refresh failed; continuing without a fresh trace anchor. {0}" -f $_.Exception.Message)
        return [pscustomobject]$result
    }
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
