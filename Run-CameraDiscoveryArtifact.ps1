# ====================================================================================
# Script: Run-CameraDiscoveryArtifact.ps1
# Version: 1.0.0
# Purpose: Run the existing camera discovery stimulus scripts from the repo root,
#          write durable repo-local artifacts during execution, and preserve partial
#          results/errors so the files can be committed and pushed for remote review.
# CharacterCount: 12562
# ====================================================================================

[CmdletBinding()]
param(
    [string]$ProcessName = 'rift_x64',
    [int]$HoldMilliseconds = 300,
    [int]$WaitMilliseconds = 500,
    [int]$ReadLength = 1024,
    [string]$ArtifactDirectory = 'artifacts\camera-discovery',
    [switch]$RefreshOwnerComponents,
    [switch]$SkipBackgroundFocus,
    [switch]$SkipAltS,
    [switch]$SkipAltZ,
    [switch]$ContinueOnError = $true,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$scriptRoot = Join-Path $repoRoot 'scripts'
$altSScript = Join-Path $scriptRoot 'test-camera-alts-stimulus.ps1'
$altZScript = Join-Path $scriptRoot 'test-camera-altz-stimulus.ps1'
$artifactRoot = Join-Path $repoRoot $ArtifactDirectory

function Assert-PathExists {
    param(
        [Parameter(Mandatory)]
        [string]$Path,
        [Parameter(Mandatory)]
        [string]$Label
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "$Label not found: $Path"
    }
}

function Write-Utf8File {
    param(
        [Parameter(Mandatory)]
        [string]$Path,
        [Parameter(Mandatory)]
        [string]$Content
    )

    $parent = Split-Path -Parent $Path
    if (-not [string]::IsNullOrWhiteSpace($parent) -and -not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }

    Set-Content -LiteralPath $Path -Value $Content -Encoding UTF8
}

function Save-Bundle {
    param(
        [Parameter(Mandatory)]
        [object]$Bundle,
        [Parameter(Mandatory)]
        [string]$Path
    )

    $jsonText = $Bundle | ConvertTo-Json -Depth 100
    Write-Utf8File -Path $Path -Content $jsonText
}

function Add-EventLine {
    param(
        [Parameter(Mandatory)]
        [string]$EventsPath,
        [Parameter(Mandatory)]
        [string]$Phase,
        [Parameter(Mandatory)]
        [string]$Kind,
        [object]$Data
    )

    $record = [ordered]@{
        TimestampUtc = [DateTimeOffset]::UtcNow.ToString('O')
        Phase = $Phase
        Kind = $Kind
        Data = if ($null -ne $Data) { $Data } else { [ordered]@{} }
    }

    $line = ($record | ConvertTo-Json -Depth 30 -Compress)
    Add-Content -LiteralPath $EventsPath -Value $line -Encoding UTF8
}

function Get-JsonFromText {
    param(
        [Parameter(Mandatory)]
        [string]$Text
    )

    $startIdx = $Text.IndexOf('{')
    if ($startIdx -lt 0) {
        throw 'No JSON object found in child script output.'
    }

    $jsonText = $Text.Substring($startIdx)
    return $jsonText | ConvertFrom-Json -Depth 100
}

function Invoke-ChildScriptStreaming {
    param(
        [Parameter(Mandatory)]
        [string]$ScriptPath,
        [Parameter(Mandatory)]
        [string]$Phase,
        [Parameter(Mandatory)]
        [string]$StdoutLogPath,
        [Parameter(Mandatory)]
        [string]$EventsPath
    )

    $hostExe = Join-Path $PSHOME 'pwsh.exe'
    if (-not (Test-Path -LiteralPath $hostExe)) {
        $hostExe = (Get-Process -Id $PID).Path
    }

    $argList = New-Object System.Collections.Generic.List[string]
    $argList.Add('-NoProfile')
    $argList.Add('-ExecutionPolicy')
    $argList.Add('Bypass')
    $argList.Add('-File')
    $argList.Add($ScriptPath)
    $argList.Add('-ProcessName')
    $argList.Add($ProcessName)
    $argList.Add('-HoldMilliseconds')
    $argList.Add($HoldMilliseconds.ToString([System.Globalization.CultureInfo]::InvariantCulture))
    $argList.Add('-WaitMilliseconds')
    $argList.Add($WaitMilliseconds.ToString([System.Globalization.CultureInfo]::InvariantCulture))
    $argList.Add('-ReadLength')
    $argList.Add($ReadLength.ToString([System.Globalization.CultureInfo]::InvariantCulture))
    $argList.Add('-Json')

    if ($RefreshOwnerComponents) {
        $argList.Add('-RefreshOwnerComponents')
    }

    if ($SkipBackgroundFocus) {
        $argList.Add('-SkipBackgroundFocus')
    }

    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = $hostExe
    foreach ($arg in $argList) {
        [void]$psi.ArgumentList.Add($arg)
    }
    $psi.WorkingDirectory = $repoRoot
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true

    $proc = [System.Diagnostics.Process]::new()
    $proc.StartInfo = $psi
    $proc.EnableRaisingEvents = $true

    $stdoutLines = New-Object System.Collections.Generic.List[string]
    $stderrLines = New-Object System.Collections.Generic.List[string]
    $allLines = New-Object System.Collections.Generic.List[string]

    $stdoutHandler = [System.Diagnostics.DataReceivedEventHandler]{
        param($sender, $eventArgs)
        if ($null -ne $eventArgs.Data) {
            $line = $eventArgs.Data
            $stdoutLines.Add($line)
            $allLines.Add($line)
            Add-Content -LiteralPath $StdoutLogPath -Value ("[{0}] [stdout] {1}" -f $Phase, $line) -Encoding UTF8
            Write-Host $line
        }
    }

    $stderrHandler = [System.Diagnostics.DataReceivedEventHandler]{
        param($sender, $eventArgs)
        if ($null -ne $eventArgs.Data) {
            $line = $eventArgs.Data
            $stderrLines.Add($line)
            $allLines.Add($line)
            Add-Content -LiteralPath $StdoutLogPath -Value ("[{0}] [stderr] {1}" -f $Phase, $line) -Encoding UTF8
            Write-Host $line -ForegroundColor DarkYellow
        }
    }

    try {
        if (-not $proc.Start()) {
            throw "Failed to start child script process: $ScriptPath"
        }

        $proc.add_OutputDataReceived($stdoutHandler)
        $proc.add_ErrorDataReceived($stderrHandler)
        $proc.BeginOutputReadLine()
        $proc.BeginErrorReadLine()
        $proc.WaitForExit()

        $text = ($allLines.ToArray() -join [Environment]::NewLine)
        $resultObject = $null
        $parseError = $null

        try {
            if (-not [string]::IsNullOrWhiteSpace($text)) {
                $resultObject = Get-JsonFromText -Text $text
            }
        }
        catch {
            $parseError = $_.Exception.Message
        }

        return [ordered]@{
            ExitCode = $proc.ExitCode
            StdoutLineCount = $stdoutLines.Count
            StderrLineCount = $stderrLines.Count
            OutputText = $text
            ParsedJson = $resultObject
            ParseError = $parseError
        }
    }
    finally {
        try { $proc.remove_OutputDataReceived($stdoutHandler) } catch {}
        try { $proc.remove_ErrorDataReceived($stderrHandler) } catch {}
        $proc.Dispose()
    }
}

Assert-PathExists -Path $scriptRoot -Label 'scripts folder'
Assert-PathExists -Path $altSScript -Label 'Alt-S script'
Assert-PathExists -Path $altZScript -Label 'Alt-Z script'

if (-not (Test-Path -LiteralPath $artifactRoot)) {
    New-Item -ItemType Directory -Path $artifactRoot -Force | Out-Null
}

$runId = Get-Date -Format 'yyyyMMdd-HHmmss'
$bundlePath = Join-Path $artifactRoot ("camera-discovery-bundle-{0}.json" -f $runId)
$eventsPath = Join-Path $artifactRoot ("camera-discovery-events-{0}.jsonl" -f $runId)
$stdoutLogPath = Join-Path $artifactRoot ("camera-discovery-console-{0}.log" -f $runId)

Write-Utf8File -Path $eventsPath -Content ''
Write-Utf8File -Path $stdoutLogPath -Content ''

$bundle = [ordered]@{
    Mode = 'camera-discovery-artifact'
    Version = '1.0.0'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
    RunId = $runId
    RepoRoot = $repoRoot
    ArtifactDirectory = $artifactRoot
    BundlePath = $bundlePath
    EventsPath = $eventsPath
    ConsoleLogPath = $stdoutLogPath
    ProcessName = $ProcessName
    HoldMilliseconds = $HoldMilliseconds
    WaitMilliseconds = $WaitMilliseconds
    ReadLength = $ReadLength
    RefreshOwnerComponents = [bool]$RefreshOwnerComponents
    SkipBackgroundFocus = [bool]$SkipBackgroundFocus
    ContinueOnError = [bool]$ContinueOnError
    Status = 'running'
    Results = [ordered]@{}
    Errors = @()
}

Save-Bundle -Bundle $bundle -Path $bundlePath
Add-EventLine -EventsPath $eventsPath -Phase 'suite' -Kind 'start' -Data ([ordered]@{
    RunId = $runId
    RefreshOwnerComponents = [bool]$RefreshOwnerComponents
})

$phases = @()
if (-not $SkipAltS) {
    $phases += [ordered]@{ Name = 'AltS'; ScriptPath = $altSScript }
}
if (-not $SkipAltZ) {
    $phases += [ordered]@{ Name = 'AltZ'; ScriptPath = $altZScript }
}

foreach ($phase in $phases) {
    Add-EventLine -EventsPath $eventsPath -Phase $phase.Name -Kind 'phase-start' -Data ([ordered]@{
        ScriptPath = $phase.ScriptPath
    })
    Save-Bundle -Bundle $bundle -Path $bundlePath

    try {
        $child = Invoke-ChildScriptStreaming -ScriptPath $phase.ScriptPath -Phase $phase.Name -StdoutLogPath $stdoutLogPath -EventsPath $eventsPath

        $phaseRecord = [ordered]@{
            ExitCode = $child.ExitCode
            StdoutLineCount = $child.StdoutLineCount
            StderrLineCount = $child.StderrLineCount
            ParseError = $child.ParseError
            OutputTextTail = if ([string]::IsNullOrWhiteSpace($child.OutputText)) {
                $null
            } elseif ($child.OutputText.Length -gt 4000) {
                $child.OutputText.Substring($child.OutputText.Length - 4000)
            } else {
                $child.OutputText
            }
            ParsedJson = $child.ParsedJson
        }

        $bundle.Results[$phase.Name] = $phaseRecord

        $kind = if ($child.ExitCode -eq 0) { 'phase-success' } else { 'phase-nonzero-exit' }
        Add-EventLine -EventsPath $eventsPath -Phase $phase.Name -Kind $kind -Data ([ordered]@{
            ExitCode = $child.ExitCode
            ParseError = $child.ParseError
        })

        if ($child.ExitCode -ne 0 -and -not $ContinueOnError) {
            throw "Phase $($phase.Name) exited with code $($child.ExitCode)."
        }
    }
    catch {
        $errorRecord = [ordered]@{
            Phase = $phase.Name
            Message = $_.Exception.Message
            Stack = $_.ScriptStackTrace
        }
        $bundle.Errors += $errorRecord
        Add-EventLine -EventsPath $eventsPath -Phase $phase.Name -Kind 'phase-error' -Data $errorRecord
        Save-Bundle -Bundle $bundle -Path $bundlePath

        if (-not $ContinueOnError) {
            $bundle.Status = 'failed'
            Save-Bundle -Bundle $bundle -Path $bundlePath
            throw
        }
    }

    Save-Bundle -Bundle $bundle -Path $bundlePath
}

$bundle.Status = if ($bundle.Errors.Count -gt 0) { 'completed-with-errors' } else { 'completed' }
$bundle.Summary = [ordered]@{
    PhaseCount = $phases.Count
    ErrorCount = $bundle.Errors.Count
    HasAltS = $bundle.Results.Contains('AltS')
    HasAltZ = $bundle.Results.Contains('AltZ')
    AltSExitCode = if ($bundle.Results.Contains('AltS')) { $bundle.Results.AltS.ExitCode } else { $null }
    AltZExitCode = if ($bundle.Results.Contains('AltZ')) { $bundle.Results.AltZ.ExitCode } else { $null }
    AltSFlipCandidateCount = if ($bundle.Results.Contains('AltS') -and $null -ne $bundle.Results.AltS.ParsedJson) {
        $bundle.Results.AltS.ParsedJson.FlipCandidateCount
    } else { $null }
    AltZDistanceCandidateCount = if ($bundle.Results.Contains('AltZ') -and $null -ne $bundle.Results.AltZ.ParsedJson) {
        $bundle.Results.AltZ.ParsedJson.DistanceCandidateCount
    } else { $null }
}
Save-Bundle -Bundle $bundle -Path $bundlePath
Add-EventLine -EventsPath $eventsPath -Phase 'suite' -Kind 'finish' -Data ([ordered]@{
    Status = $bundle.Status
    ErrorCount = $bundle.Errors.Count
})

Write-Host ''
Write-Host '=== Camera Discovery Artifact Run Complete ===' -ForegroundColor Green
Write-Host "Bundle:    $bundlePath" -ForegroundColor Green
Write-Host "Events:    $eventsPath" -ForegroundColor Green
Write-Host "Console:   $stdoutLogPath" -ForegroundColor Green
Write-Host "Status:    $($bundle.Status)" -ForegroundColor White

if ($Json) {
    $bundle | ConvertTo-Json -Depth 100
}

# End of script
