[CmdletBinding()]
param(
    [switch]$Json,
    [string]$ProcessName = 'rift_x64',
    [int]$ProcessId,
    [string]$TargetWindowHandle,
    [int]$TimeoutSeconds = 8,
    [int]$MaxHits = 24,
    [switch]$StopOnPlausible,
    [string]$StimulusKey = '',
    [ValidateSet('None', 'SendInput', 'AutoHotkey')]
    [string]$StimulusMode = 'None',
    [int]$StimulusHoldMilliseconds = 700,
    [int]$StimulusStartDelayMilliseconds = 250,
    [string]$InstructionAddressHex,
    [string]$Pattern = 'F3 0F 10 59 08',
    [string]$ModuleName = 'rift_x64.exe',
    [string]$BasisOffsetHex = '0x60',
    [string]$OutputFile = (Join-Path $PSScriptRoot 'captures\actor-facing-instruction-trace.json'),
    [string]$StatusFile = (Join-Path $PSScriptRoot 'captures\actor-facing-instruction-trace.status.txt'),
    [string]$HitsFile = (Join-Path $PSScriptRoot 'captures\actor-facing-instruction-trace.hits.tsv')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$ceExecScript = Join-Path $PSScriptRoot 'cheatengine-exec.ps1'
$traceLuaFile = Join-Path $PSScriptRoot 'cheat-engine\RiftReaderFacingInstructionTrace.lua'
$sendKeyScript = Join-Path $PSScriptRoot 'send-rift-key.ps1'
$sendKeyAhkScript = Join-Path $PSScriptRoot 'send-rift-key-ahk.ps1'
$resolvedOutputFile = [System.IO.Path]::GetFullPath($OutputFile)
$resolvedStatusFile = [System.IO.Path]::GetFullPath($StatusFile)
$resolvedHitsFile = [System.IO.Path]::GetFullPath($HitsFile)

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public static class RiftTraceTargetNative
{
    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool IsWindow(IntPtr hWnd);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
}
"@

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

    return ($output -join [Environment]::NewLine) | ConvertFrom-Json -Depth 20
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

function Get-TargetExeName {
    if ([string]::IsNullOrWhiteSpace($ProcessName)) {
        return $ProcessName
    }

    $trimmed = $ProcessName.Trim()
    if ($trimmed.EndsWith('.exe', [System.StringComparison]::OrdinalIgnoreCase)) {
        return $trimmed
    }

    return "$trimmed.exe"
}

function Get-EffectiveTargetProcessId {
    $handle = ConvertTo-WindowHandle -HandleText $TargetWindowHandle
    if ($handle -ne [IntPtr]::Zero) {
        if (-not [RiftTraceTargetNative]::IsWindow($handle)) {
            throw "Target window handle '$TargetWindowHandle' is not a valid window."
        }

        $ownerProcessId = [uint32]0
        [void][RiftTraceTargetNative]::GetWindowThreadProcessId($handle, [ref]$ownerProcessId)
        if ($ownerProcessId -eq 0) {
            throw "Target window handle '$TargetWindowHandle' did not resolve to a process id."
        }

        if ($ProcessId -gt 0 -and [int]$ownerProcessId -ne $ProcessId) {
            throw "Target window handle '$TargetWindowHandle' belongs to PID $ownerProcessId, not PID $ProcessId."
        }

        return [int]$ownerProcessId
    }

    if ($ProcessId -gt 0) {
        return $ProcessId
    }

    return $null
}

function Get-ReaderTargetArguments {
    $effectiveProcessId = Get-EffectiveTargetProcessId
    if ($null -ne $effectiveProcessId -and $effectiveProcessId -gt 0) {
        return @('--pid', $effectiveProcessId.ToString([System.Globalization.CultureInfo]::InvariantCulture))
    }

    return @('--process-name', $ProcessName)
}

function Get-StimulusTargetArguments {
    param([Parameter(Mandatory = $true)][string]$Mode)

    $effectiveProcessId = Get-EffectiveTargetProcessId
    $arguments = @()
    switch ($Mode) {
        'SendInput' { $arguments += @('-ProcessName', $ProcessName) }
        'AutoHotkey' { $arguments += @('-TargetExe', (Get-TargetExeName)) }
        default { }
    }

    if ($null -ne $effectiveProcessId -and $effectiveProcessId -gt 0) {
        $arguments += @('-TargetProcessId', $effectiveProcessId.ToString([System.Globalization.CultureInfo]::InvariantCulture))
    }

    if (-not [string]::IsNullOrWhiteSpace($TargetWindowHandle)) {
        $arguments += @('-TargetWindowHandle', $TargetWindowHandle)
    }

    return $arguments
}

function Assert-ExactStimulusTarget {
    $effectiveProcessId = Get-EffectiveTargetProcessId
    if ($null -eq $effectiveProcessId -or $effectiveProcessId -le 0) {
        throw "Actor-facing instruction stimulus uses live input and requires -ProcessId or -TargetWindowHandle. Refusing name-only '$ProcessName' targeting."
    }
}

function Get-ProcessState {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [int]$Id
    )

    $process = if ($Id -gt 0) {
        Get-Process -Id $Id -ErrorAction SilentlyContinue
    }
    else {
        $matches = @(Get-Process -Name $Name -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 })
        if ($matches.Count -gt 1) {
            $ids = ($matches | Sort-Object Id | ForEach-Object { $_.Id }) -join ', '
            throw "Process name '$Name' matched multiple windowed processes ($ids). Use -ProcessId or -TargetWindowHandle for instruction tracing."
        }

        $matches | Select-Object -First 1
    }
    if ($null -eq $process) {
        return $null
    }

    if (-not [string]::IsNullOrWhiteSpace($Name) -and
        -not [string]::Equals($process.ProcessName, [System.IO.Path]::GetFileNameWithoutExtension($Name), [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Target PID $($process.Id) is '$($process.ProcessName)', not '$Name'."
    }

    return [pscustomobject]@{
        Name = $process.ProcessName
        Id = $process.Id
        Responding = $process.Responding
        MainWindowTitle = $process.MainWindowTitle
        StartTime = try { $process.StartTime } catch { $null }
    }
}

function Test-ProcessStateCompromised {
    param($ProcessState)

    if ($null -eq $ProcessState) {
        return $true
    }

    if (-not $ProcessState.Responding) {
        return $true
    }

    $title = [string]$ProcessState.MainWindowTitle
    return ($title -like '*Not Responding*')
}

function Start-StimulusProcess {
    if ([string]::IsNullOrWhiteSpace($StimulusKey) -or $StimulusMode -eq 'None') {
        return $null
    }

    Assert-ExactStimulusTarget

    $scriptPath = $null
    switch ($StimulusMode) {
        'SendInput' { $scriptPath = $sendKeyScript }
        'AutoHotkey' { $scriptPath = $sendKeyAhkScript }
        default { throw "Unsupported stimulus mode '$StimulusMode'." }
    }

    $argumentList = @(
        '-NoProfile',
        '-ExecutionPolicy',
        'Bypass',
        '-File',
        ('"{0}"' -f $scriptPath)
    ) + (Get-StimulusTargetArguments -Mode $StimulusMode) + @(
        '-Key',
        $StimulusKey,
        '-HoldMilliseconds',
        $StimulusHoldMilliseconds.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '-NoRefocus'
    )

    return Start-Process -FilePath 'powershell.exe' -ArgumentList $argumentList -PassThru -WindowStyle Hidden
}

function Wait-StimulusProcess {
    param($Process)

    if ($null -eq $Process) {
        return $null
    }

    try {
        if (-not $Process.HasExited) {
            Wait-Process -Id $Process.Id -ErrorAction Stop
        }
    }
    catch [System.InvalidOperationException] {
    }

    $Process.Refresh()
    return $Process.ExitCode
}

function Read-KeyValueFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [int]$RetryCount = 8,
        [int]$RetryDelayMilliseconds = 50
    )

    $map = [ordered]@{}
    for ($attempt = 0; $attempt -lt $RetryCount; $attempt++) {
        try {
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
        catch [System.IO.IOException] {
            if ($attempt -ge ($RetryCount - 1)) {
                throw
            }

            Start-Sleep -Milliseconds $RetryDelayMilliseconds
            $map = [ordered]@{}
        }
    }
}

function Try-ParseDouble {
    param([string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $null
    }

    $parsed = 0.0
    if ([double]::TryParse($Value, [System.Globalization.NumberStyles]::Float, [System.Globalization.CultureInfo]::InvariantCulture, [ref]$parsed)) {
        return $parsed
    }

    return $null
}

function Try-ParseInt32 {
    param([string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $null
    }

    $parsed = 0
    if ([int]::TryParse($Value, [ref]$parsed)) {
        return $parsed
    }

    return $null
}

function Get-ObjectValue {
    param(
        [Parameter(Mandatory = $true)]
        [psobject]$Object,

        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $null
    }

    return $property.Value
}

function Convert-HitRow {
    param(
        [Parameter(Mandatory = $true)]
        [psobject]$Row
    )

    [pscustomobject]@{
        SavedAtUtc = [string](Get-ObjectValue -Object $Row -Name 'SavedAtUtc')
        HitIndex = Try-ParseInt32 ([string](Get-ObjectValue -Object $Row -Name 'HitIndex'))
        Rip = [string](Get-ObjectValue -Object $Row -Name 'Rip')
        Instruction = [string](Get-ObjectValue -Object $Row -Name 'Instruction')
        ModuleName = [string](Get-ObjectValue -Object $Row -Name 'ModuleName')
        ModuleOffset = [string](Get-ObjectValue -Object $Row -Name 'ModuleOffset')
        RCX = [string](Get-ObjectValue -Object $Row -Name 'RCX')
        SourceBase = [string](Get-ObjectValue -Object $Row -Name 'SourceBase')
        R12 = [string](Get-ObjectValue -Object $Row -Name 'R12')
        RSI = [string](Get-ObjectValue -Object $Row -Name 'RSI')
        RDI = [string](Get-ObjectValue -Object $Row -Name 'RDI')
        Forward = [ordered]@{
            X = Try-ParseDouble ([string](Get-ObjectValue -Object $Row -Name 'ForwardX'))
            Y = Try-ParseDouble ([string](Get-ObjectValue -Object $Row -Name 'ForwardY'))
            Z = Try-ParseDouble ([string](Get-ObjectValue -Object $Row -Name 'ForwardZ'))
        }
        Up = [ordered]@{
            X = Try-ParseDouble ([string](Get-ObjectValue -Object $Row -Name 'UpX'))
            Y = Try-ParseDouble ([string](Get-ObjectValue -Object $Row -Name 'UpY'))
            Z = Try-ParseDouble ([string](Get-ObjectValue -Object $Row -Name 'UpZ'))
        }
        Right = [ordered]@{
            X = Try-ParseDouble ([string](Get-ObjectValue -Object $Row -Name 'RightX'))
            Y = Try-ParseDouble ([string](Get-ObjectValue -Object $Row -Name 'RightY'))
            Z = Try-ParseDouble ([string](Get-ObjectValue -Object $Row -Name 'RightZ'))
        }
        ForwardMagnitude = Try-ParseDouble ([string](Get-ObjectValue -Object $Row -Name 'ForwardMagnitude'))
        UpMagnitude = Try-ParseDouble ([string](Get-ObjectValue -Object $Row -Name 'UpMagnitude'))
        RightMagnitude = Try-ParseDouble ([string](Get-ObjectValue -Object $Row -Name 'RightMagnitude'))
        DotForwardUp = Try-ParseDouble ([string](Get-ObjectValue -Object $Row -Name 'DotForwardUp'))
        DotForwardRight = Try-ParseDouble ([string](Get-ObjectValue -Object $Row -Name 'DotForwardRight'))
        DotUpRight = Try-ParseDouble ([string](Get-ObjectValue -Object $Row -Name 'DotUpRight'))
        Determinant = Try-ParseDouble ([string](Get-ObjectValue -Object $Row -Name 'Determinant'))
        BasisPass = ([string](Get-ObjectValue -Object $Row -Name 'BasisPass')) -eq 'true'
    }
}

Assert-ExactStimulusTarget

if ([string]::IsNullOrWhiteSpace($InstructionAddressHex)) {
    $scanArguments = @(Get-ReaderTargetArguments) + @(
        '--scan-module-pattern', $Pattern,
        '--scan-module-name', $ModuleName,
        '--json')
    $scan = Invoke-ReaderJson -Arguments $scanArguments

    if ($scan.Found -ne $true -or [string]::IsNullOrWhiteSpace([string]$scan.Address)) {
        throw "Unable to resolve actor-facing instruction pattern '$Pattern' in module '$ModuleName'."
    }

    $InstructionAddressHex = [string]$scan.Address
    $patternScan = $scan
}
else {
    $patternScan = $null
}

$instructionAddress = Parse-HexUInt64 -Value $InstructionAddressHex
$basisOffset = Parse-HexUInt64 -Value $BasisOffsetHex

foreach ($path in @($resolvedStatusFile, $resolvedHitsFile)) {
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Force
    }
}

$outputDirectory = Split-Path -Parent $resolvedOutputFile
foreach ($directory in @($outputDirectory, (Split-Path -Parent $resolvedStatusFile), (Split-Path -Parent $resolvedHitsFile))) {
    if (-not [string]::IsNullOrWhiteSpace($directory)) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }
}

$effectiveTraceProcessId = Get-EffectiveTargetProcessId
$preTraceRiftState = Get-ProcessState -Name $ProcessName -Id $(if ($null -ne $effectiveTraceProcessId) { $effectiveTraceProcessId } else { 0 })
$preTraceCeState = Get-ProcessState -Name 'cheatengine-x86_64-SSE4-AVX2'

& $ceExecScript -LuaFile $traceLuaFile | Out-Null

$stopOnPlausibleLiteral = if ($StopOnPlausible) { 'true' } else { 'false' }
$processSelectorLiteral = if ($null -ne $effectiveTraceProcessId -and $effectiveTraceProcessId -gt 0) {
    $effectiveTraceProcessId.ToString([System.Globalization.CultureInfo]::InvariantCulture)
}
else {
    "'$($ProcessName.Replace('\', '\\').Replace("'", "\\'"))'"
}
$luaCode = @"
return RiftReaderFacingInstructionTrace.armAsync($processSelectorLiteral, $instructionAddress, [[$resolvedStatusFile]], [[$resolvedHitsFile]], $basisOffset, $MaxHits, $stopOnPlausibleLiteral)
"@
& $ceExecScript -Code $luaCode | Out-Null

$stimulusProcess = $null
$stimulusAttempted = $false
$stimulusExitCode = $null
if (-not [string]::IsNullOrWhiteSpace($StimulusKey) -and $StimulusMode -ne 'None') {
    Start-Sleep -Milliseconds $StimulusStartDelayMilliseconds
    $stimulusProcess = Start-StimulusProcess
    $stimulusAttempted = $true
}

$deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
$status = $null
while ([DateTime]::UtcNow -lt $deadline) {
    if (Test-Path -LiteralPath $resolvedStatusFile) {
        $status = Read-KeyValueFile -Path $resolvedStatusFile
        if ($status.status -in @('hit', 'collected', 'error')) {
            break
        }
    }

    Start-Sleep -Milliseconds 200
}

if (($null -eq $status) -or ($status.status -notin @('hit', 'collected', 'error'))) {
    try {
        & $ceExecScript -Code 'return RiftReaderFacingInstructionTrace.cleanup()' | Out-Null
    }
    catch {
    }

    if (Test-Path -LiteralPath $resolvedStatusFile) {
        $status = Read-KeyValueFile -Path $resolvedStatusFile
    }
}

$stimulusExitCode = Wait-StimulusProcess -Process $stimulusProcess

$hits = @()
if (Test-Path -LiteralPath $resolvedHitsFile) {
    $hits = @(Import-Csv -LiteralPath $resolvedHitsFile -Delimiter "`t" | ForEach-Object { Convert-HitRow -Row $_ })
}

$postTraceRiftState = Get-ProcessState -Name $ProcessName -Id $(if ($null -ne $effectiveTraceProcessId) { $effectiveTraceProcessId } else { 0 })
$postTraceCeState = Get-ProcessState -Name 'cheatengine-x86_64-SSE4-AVX2'
$sessionCompromised = (Test-ProcessStateCompromised -ProcessState $postTraceRiftState) -or (Test-ProcessStateCompromised -ProcessState $postTraceCeState)
$cleanupAttempted = $false
$cleanupSucceeded = $false

if (-not $sessionCompromised) {
    $cleanupAttempted = $true
    try {
        & $ceExecScript -Code 'return RiftReaderFacingInstructionTrace.cleanup()' | Out-Null
        $cleanupSucceeded = $true
    }
    catch {
        Write-Warning ("Unable to clean up the CE facing trace helper cleanly: {0}" -f $_.Exception.Message)
    }
}
else {
    Write-Warning 'Skipping CE facing trace cleanup because the live session is already compromised.'
}

$postCleanupRiftState = Get-ProcessState -Name $ProcessName -Id $(if ($null -ne $effectiveTraceProcessId) { $effectiveTraceProcessId } else { 0 })
$postCleanupCeState = Get-ProcessState -Name 'cheatengine-x86_64-SSE4-AVX2'

$bySource = @(
    $hits |
        Group-Object SourceBase |
        Sort-Object Count -Descending |
        ForEach-Object {
            $groupHits = @($_.Group)
            $plausibleHits = @($groupHits | Where-Object { $_.BasisPass })
            $lastHit = $groupHits | Sort-Object HitIndex -Descending | Select-Object -First 1

            [pscustomobject]@{
                SourceBase = $_.Name
                HitCount = $_.Count
                PlausibleHitCount = $plausibleHits.Count
                LastForward = $lastHit.Forward
                LastDeterminant = $lastHit.Determinant
                LastModuleOffset = $lastHit.ModuleOffset
                LastRCX = $lastHit.RCX
                LastR12 = $lastHit.R12
                LastRSI = $lastHit.RSI
                LastRDI = $lastHit.RDI
                BasisPass = $lastHit.BasisPass
            }
        })

$plausibleSources = @($bySource | Where-Object { $_.PlausibleHitCount -gt 0 })
$topSource = $bySource | Select-Object -First 1

$result = [ordered]@{
    Mode = 'actor-facing-instruction-trace'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    ProcessName = $ProcessName
    ProcessId = $effectiveTraceProcessId
    TargetWindowHandle = $TargetWindowHandle
    InstructionAddress = ('0x{0:X}' -f $instructionAddress)
    BasisOffset = ('0x{0:X}' -f $basisOffset)
    Pattern = $Pattern
    PatternScan = $patternScan
    TimeoutSeconds = $TimeoutSeconds
    MaxHits = $MaxHits
    StopOnPlausible = $StopOnPlausible.IsPresent
    StimulusKey = $StimulusKey
    StimulusMode = $StimulusMode
    StimulusHoldMilliseconds = $StimulusHoldMilliseconds
    StimulusStartDelayMilliseconds = $StimulusStartDelayMilliseconds
    StimulusAttempted = $stimulusAttempted
    StimulusExitCode = $stimulusExitCode
    StatusFile = $resolvedStatusFile
    HitsFile = $resolvedHitsFile
    Status = $status
    HitCount = $hits.Count
    PreTraceRiftState = $preTraceRiftState
    PreTraceCeState = $preTraceCeState
    PostTraceRiftState = $postTraceRiftState
    PostTraceCeState = $postTraceCeState
    LiveSessionCompromised = $sessionCompromised
    CleanupAttempted = $cleanupAttempted
    CleanupSucceeded = $cleanupSucceeded
    PostCleanupRiftState = $postCleanupRiftState
    PostCleanupCeState = $postCleanupCeState
    SourceCount = @($bySource).Count
    PlausibleSourceCount = @($plausibleSources).Count
    TopSource = $topSource
    Sources = $bySource
    Hits = $hits
}

$jsonText = $result | ConvertTo-Json -Depth 20
Set-Content -LiteralPath $resolvedOutputFile -Value $jsonText -Encoding UTF8

if ($Json) {
    Write-Output $jsonText
}
else {
    Write-Host "Actor-facing instruction trace: $resolvedOutputFile"
    Write-Host "Instruction:                   $($result.InstructionAddress)"
    Write-Host "Hits captured:                  $($hits.Count)"
    Write-Host "Unique source bases:            $($result.SourceCount)"
    Write-Host "Plausible source bases:         $($result.PlausibleSourceCount)"
    Write-Host "Live session compromised:       $($result.LiveSessionCompromised)"
    if ($topSource) {
        Write-Host "Top source base:                $($topSource.SourceBase) ($($topSource.HitCount) hits, plausible $($topSource.PlausibleHitCount))"
    }
}
