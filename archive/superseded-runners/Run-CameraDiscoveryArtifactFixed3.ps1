# ====================================================================================
# Script: Run-CameraDiscoveryArtifactFixed3.ps1
# Version: 1.0.3
# Purpose: Run the existing camera discovery stimulus scripts from the repo root,
#          write repo-local artifact files, and avoid async callback runspace issues.
# CharacterCount: 8076
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

function Ensure-ParentDirectory {
    param([Parameter(Mandatory)][string]$Path)
    $parent = Split-Path -Parent $Path
    if (-not [string]::IsNullOrWhiteSpace($parent) -and -not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
}

function Write-Utf8File {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][AllowEmptyString()][string]$Content
    )

    Ensure-ParentDirectory -Path $Path
    [System.IO.File]::WriteAllText($Path, $Content, [System.Text.UTF8Encoding]::new($false))
}

function Save-Bundle {
    param(
        [Parameter(Mandatory)][object]$Bundle,
        [Parameter(Mandatory)][string]$Path
    )

    $jsonText = $Bundle | ConvertTo-Json -Depth 100
    Write-Utf8File -Path $Path -Content $jsonText
}

function Add-EventLine {
    param(
        [Parameter(Mandatory)][string]$EventsPath,
        [Parameter(Mandatory)][string]$Phase,
        [Parameter(Mandatory)][string]$Kind,
        [object]$Data
    )

    $record = [ordered]@{
        TimestampUtc = [DateTimeOffset]::UtcNow.ToString('O')
        Phase = $Phase
        Kind = $Kind
        Data = if ($null -ne $Data) { $Data } else { [ordered]@{} }
    }

    Add-Content -LiteralPath $EventsPath -Value (($record | ConvertTo-Json -Depth 30 -Compress)) -Encoding UTF8
}

function Get-JsonFromText {
    param([Parameter(Mandatory)][string]$Text)

    $startIdx = $Text.IndexOf('{')
    if ($startIdx -lt 0) {
        throw 'No JSON object found in child script output.'
    }

    return ($Text.Substring($startIdx) | ConvertFrom-Json -Depth 100)
}

function Invoke-Phase {
    param(
        [Parameter(Mandatory)][string]$ScriptPath,
        [Parameter(Mandatory)][string]$ConsoleLogPath
    )

    $args = @{
        ProcessName = $ProcessName
        HoldMilliseconds = $HoldMilliseconds
        WaitMilliseconds = $WaitMilliseconds
        ReadLength = $ReadLength
        Json = $true
    }

    if ($RefreshOwnerComponents) {
        $args['RefreshOwnerComponents'] = $true
    }
    if ($SkipBackgroundFocus) {
        $args['SkipBackgroundFocus'] = $true
    }

    $rawOutput = & $ScriptPath @args 2>&1 | Tee-Object -FilePath $ConsoleLogPath -Append
    $exitCode = if ($null -ne $LASTEXITCODE) { $LASTEXITCODE } else { 0 }
    $textLines = @($rawOutput | ForEach-Object { $_.ToString() })
    $text = $textLines -join [Environment]::NewLine

    $parsedJson = $null
    $parseError = $null
    try {
        if (-not [string]::IsNullOrWhiteSpace($text)) {
            $parsedJson = Get-JsonFromText -Text $text
        }
    }
    catch {
        $parseError = $_.Exception.Message
    }

    return [ordered]@{
        ExitCode = $exitCode
        LineCount = $textLines.Count
        ParseError = $parseError
        OutputText = $text
        ParsedJson = $parsedJson
    }
}

if (-not (Test-Path -LiteralPath $altSScript)) { throw "Alt-S script not found: $altSScript" }
if (-not (Test-Path -LiteralPath $altZScript)) { throw "Alt-Z script not found: $altZScript" }
if (-not (Test-Path -LiteralPath $artifactRoot)) { New-Item -ItemType Directory -Path $artifactRoot -Force | Out-Null }

$runId = Get-Date -Format 'yyyyMMdd-HHmmss'
$bundlePath = Join-Path $artifactRoot ("camera-discovery-bundle-{0}.json" -f $runId)
$eventsPath = Join-Path $artifactRoot ("camera-discovery-events-{0}.jsonl" -f $runId)
$consoleLogPath = Join-Path $artifactRoot ("camera-discovery-console-{0}.log" -f $runId)
Write-Utf8File -Path $eventsPath -Content ''
Write-Utf8File -Path $consoleLogPath -Content ''

$bundle = [ordered]@{
    Mode = 'camera-discovery-artifact'
    Version = '1.0.3'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
    RunId = $runId
    RepoRoot = $repoRoot
    ArtifactDirectory = $artifactRoot
    BundlePath = $bundlePath
    EventsPath = $eventsPath
    ConsoleLogPath = $consoleLogPath
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
Add-EventLine -EventsPath $eventsPath -Phase 'suite' -Kind 'start' -Data ([ordered]@{ RunId = $runId })

$phases = @()
if (-not $SkipAltS) { $phases += [ordered]@{ Name = 'AltS'; ScriptPath = $altSScript } }
if (-not $SkipAltZ) { $phases += [ordered]@{ Name = 'AltZ'; ScriptPath = $altZScript } }

foreach ($phase in $phases) {
    Add-EventLine -EventsPath $eventsPath -Phase $phase.Name -Kind 'phase-start' -Data ([ordered]@{ ScriptPath = $phase.ScriptPath })
    Save-Bundle -Bundle $bundle -Path $bundlePath
    try {
        $phaseResult = Invoke-Phase -ScriptPath $phase.ScriptPath -ConsoleLogPath $consoleLogPath
        $bundle.Results[$phase.Name] = [ordered]@{
            ExitCode = $phaseResult.ExitCode
            LineCount = $phaseResult.LineCount
            ParseError = $phaseResult.ParseError
            OutputTextTail = if ([string]::IsNullOrWhiteSpace($phaseResult.OutputText)) { $null } elseif ($phaseResult.OutputText.Length -gt 4000) { $phaseResult.OutputText.Substring($phaseResult.OutputText.Length - 4000) } else { $phaseResult.OutputText }
            ParsedJson = $phaseResult.ParsedJson
        }
        Add-EventLine -EventsPath $eventsPath -Phase $phase.Name -Kind 'phase-finish' -Data ([ordered]@{ ExitCode = $phaseResult.ExitCode; ParseError = $phaseResult.ParseError })
    }
    catch {
        $errorRecord = [ordered]@{ Phase = $phase.Name; Message = $_.Exception.Message; Stack = $_.ScriptStackTrace }
        $bundle.Errors += $errorRecord
        Add-EventLine -EventsPath $eventsPath -Phase $phase.Name -Kind 'phase-error' -Data $errorRecord
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
    AltSExitCode = if ($bundle.Results.Contains('AltS')) { $bundle.Results.AltS.ExitCode } else { $null }
    AltZExitCode = if ($bundle.Results.Contains('AltZ')) { $bundle.Results.AltZ.ExitCode } else { $null }
}
Save-Bundle -Bundle $bundle -Path $bundlePath
Add-EventLine -EventsPath $eventsPath -Phase 'suite' -Kind 'finish' -Data ([ordered]@{ Status = $bundle.Status; ErrorCount = $bundle.Errors.Count })

Write-Host ''
Write-Host '=== Camera Discovery Artifact Run Complete ===' -ForegroundColor Green
Write-Host "Bundle:    $bundlePath" -ForegroundColor Green
Write-Host "Events:    $eventsPath" -ForegroundColor Green
Write-Host "Console:   $consoleLogPath" -ForegroundColor Green
Write-Host "Status:    $($bundle.Status)" -ForegroundColor White

if ($Json) {
    $bundle | ConvertTo-Json -Depth 100
}

# End of script
