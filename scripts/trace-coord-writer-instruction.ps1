[CmdletBinding()]
param(
    [switch]$Json,
    [string]$ProcessName = 'rift_x64',
    [int]$ProcessId,
    [string]$TargetWindowHandle,
    [string]$ModuleName = 'rift_x64.exe',
    [string]$ModuleOffsetHex = '0x674B6F',
    [string]$InstructionAddressHex,
    [int]$ArmReadyTimeoutSeconds = 40,
    [int]$TimeoutSeconds = 10,
    [int]$MaxHits = 160,
    [ValidateSet('None', 'SendInput', 'AutoHotkey')]
    [string]$StimulusMode = 'None',
    [string]$StimulusKey = 'w',
    [int]$StimulusHoldMilliseconds = 1000,
    [int]$StimulusStartDelayMilliseconds = 250,
    [string]$PrimaryRegister = 'RBX',
    [string]$PrimaryCoordOffsetHex = '0x3BC',
    [string]$PrimaryWriteOffsetHex = '0x3C0',
    [string]$SecondaryRegister = 'R13',
    [string]$SecondaryCoordOffsetHex = '0x2E8',
    [string]$OutputFile = (Join-Path $PSScriptRoot 'captures\coord-writer-instruction-trace.json'),
    [string]$StatusFile = (Join-Path $PSScriptRoot 'captures\coord-writer-instruction-trace.status.txt'),
    [string]$HitsFile = (Join-Path $PSScriptRoot 'captures\coord-writer-instruction-trace.hits.ndjson')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$ceExecScript = Join-Path $PSScriptRoot 'cheatengine-exec.ps1'
$traceLuaFile = Join-Path $PSScriptRoot 'cheat-engine\RiftReaderCoordWriterTrace.lua'
$sendKeyScript = Join-Path $PSScriptRoot 'send-rift-key.ps1'
$sendKeyAhkScript = Join-Path $PSScriptRoot 'send-rift-key-ahk.ps1'
$resolvedOutputFile = [System.IO.Path]::GetFullPath($OutputFile)
$resolvedStatusFile = [System.IO.Path]::GetFullPath($StatusFile)
$resolvedHitsFile = [System.IO.Path]::GetFullPath($HitsFile)

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public static class RiftCoordWriterTraceTargetNative
{
    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool IsWindow(IntPtr hWnd);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
}
"@

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
    param([Parameter(Mandatory = $true)][UInt64]$Value)

    return ('0x{0:X}' -f $Value)
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
        if (-not [RiftCoordWriterTraceTargetNative]::IsWindow($handle)) {
            throw "Target window handle '$TargetWindowHandle' is not a valid window."
        }

        $ownerProcessId = [uint32]0
        [void][RiftCoordWriterTraceTargetNative]::GetWindowThreadProcessId($handle, [ref]$ownerProcessId)
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

    return ($output -join [Environment]::NewLine) | ConvertFrom-Json -Depth 32
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
            throw "Process name '$Name' matched multiple windowed processes ($ids). Use -ProcessId or -TargetWindowHandle for coord-writer tracing."
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
    return (($title -like '*Not Responding*') -or ($title -eq 'Error') -or ($title -like '*Error*'))
}

function Resolve-InstructionAddress {
    param([int]$EffectiveProcessId)

    if (-not [string]::IsNullOrWhiteSpace($InstructionAddressHex)) {
        return [pscustomobject]@{
            Address = Parse-HexUInt64 -Value $InstructionAddressHex
            ModuleBase = $null
            ModuleOffset = $null
            Source = 'explicit-address'
        }
    }

    $moduleOffset = Parse-HexUInt64 -Value $ModuleOffsetHex
    $process = Get-Process -Id $EffectiveProcessId -ErrorAction Stop
    $module = @($process.Modules | Where-Object { [string]::Equals($_.ModuleName, $ModuleName, [System.StringComparison]::OrdinalIgnoreCase) } | Select-Object -First 1)
    if ($null -eq $module) {
        throw "Module '$ModuleName' was not found in PID $EffectiveProcessId."
    }

    $moduleBase = [UInt64]$module.BaseAddress.ToInt64()
    return [pscustomobject]@{
        Address = [UInt64]($moduleBase + $moduleOffset)
        ModuleBase = $moduleBase
        ModuleOffset = $moduleOffset
        Source = 'module-offset'
    }
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
    if ($StimulusMode -eq 'None') {
        return
    }

    $effectiveProcessId = Get-EffectiveTargetProcessId
    if ($null -eq $effectiveProcessId -or $effectiveProcessId -le 0) {
        throw "Coord-writer instruction stimulus uses live input and requires -ProcessId or -TargetWindowHandle. Refusing name-only '$ProcessName' targeting."
    }
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
    param($Value)

    if ($null -eq $Value -or [string]::IsNullOrWhiteSpace([string]$Value)) {
        return $null
    }

    $parsed = 0.0
    if ([double]::TryParse([string]$Value, [System.Globalization.NumberStyles]::Float, [System.Globalization.CultureInfo]::InvariantCulture, [ref]$parsed)) {
        return $parsed
    }

    return $null
}

function Get-JsonPropertyValue {
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

function Read-Hits {
    if (-not (Test-Path -LiteralPath $resolvedHitsFile -PathType Leaf)) {
        return @()
    }

    $hits = New-Object System.Collections.Generic.List[object]
    foreach ($line in [System.IO.File]::ReadLines($resolvedHitsFile)) {
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }

        try {
            $hits.Add(($line | ConvertFrom-Json -Depth 16)) | Out-Null
        }
        catch {
            $hits.Add([pscustomobject]@{ ParseError = $_.Exception.Message; RawLine = $line }) | Out-Null
        }
    }

    return @($hits.ToArray())
}

function Get-ExpectedCoords {
    param($ReaderSnapshot)

    if ($null -eq $ReaderSnapshot -or $null -eq $ReaderSnapshot.Expected) {
        return $null
    }

    return [pscustomobject]@{
        X = Try-ParseDouble $ReaderSnapshot.Expected.CoordX
        Y = Try-ParseDouble $ReaderSnapshot.Expected.CoordY
        Z = Try-ParseDouble $ReaderSnapshot.Expected.CoordZ
    }
}

function Get-CoordDistance {
    param($Hit, $Expected)

    if ($null -eq $Hit -or $null -eq $Expected) {
        return $null
    }

    $x = Try-ParseDouble (Get-JsonPropertyValue -Object $Hit -Name 'PrimaryX')
    $y = Try-ParseDouble (Get-JsonPropertyValue -Object $Hit -Name 'PrimaryY')
    $z = Try-ParseDouble (Get-JsonPropertyValue -Object $Hit -Name 'PrimaryZ')
    if ($null -eq $x -or $null -eq $y -or $null -eq $z -or $null -eq $Expected.X -or $null -eq $Expected.Y -or $null -eq $Expected.Z) {
        return $null
    }

    return [Math]::Sqrt((($x - $Expected.X) * ($x - $Expected.X)) + (($y - $Expected.Y) * ($y - $Expected.Y)) + (($z - $Expected.Z) * ($z - $Expected.Z)))
}

function Get-CoordDelta {
    param($First, $Last)

    if ($null -eq $First -or $null -eq $Last) {
        return $null
    }

    $fx = Try-ParseDouble (Get-JsonPropertyValue -Object $First -Name 'PrimaryX')
    $fy = Try-ParseDouble (Get-JsonPropertyValue -Object $First -Name 'PrimaryY')
    $fz = Try-ParseDouble (Get-JsonPropertyValue -Object $First -Name 'PrimaryZ')
    $lx = Try-ParseDouble (Get-JsonPropertyValue -Object $Last -Name 'PrimaryX')
    $ly = Try-ParseDouble (Get-JsonPropertyValue -Object $Last -Name 'PrimaryY')
    $lz = Try-ParseDouble (Get-JsonPropertyValue -Object $Last -Name 'PrimaryZ')
    if ($null -eq $fx -or $null -eq $fy -or $null -eq $fz -or $null -eq $lx -or $null -eq $ly -or $null -eq $lz) {
        return $null
    }

    return [pscustomobject]@{
        X = $lx - $fx
        Y = $ly - $fy
        Z = $lz - $fz
        Magnitude = [Math]::Sqrt((($lx - $fx) * ($lx - $fx)) + (($ly - $fy) * ($ly - $fy)) + (($lz - $fz) * ($lz - $fz)))
    }
}

function New-Coord {
    param($Hit)

    if ($null -eq $Hit) {
        return $null
    }

    return [pscustomobject]@{
        X = Try-ParseDouble (Get-JsonPropertyValue -Object $Hit -Name 'PrimaryX')
        Y = Try-ParseDouble (Get-JsonPropertyValue -Object $Hit -Name 'PrimaryY')
        Z = Try-ParseDouble (Get-JsonPropertyValue -Object $Hit -Name 'PrimaryZ')
    }
}

function Summarize-Hits {
    param(
        [object[]]$Hits,
        $PreExpected,
        $PostExpected
    )

    $validHits = @($Hits | Where-Object {
            -not (Get-JsonPropertyValue -Object $_ -Name 'ParseError') -and
            -not [string]::IsNullOrWhiteSpace([string](Get-JsonPropertyValue -Object $_ -Name 'PrimaryBase'))
        })

    return @(
        $validHits |
            Group-Object { [string](Get-JsonPropertyValue -Object $_ -Name 'PrimaryBase') } |
            ForEach-Object {
                $groupHits = @($_.Group | Sort-Object { [int](Get-JsonPropertyValue -Object $_ -Name 'HitIndex') })
                $firstHit = $groupHits | Select-Object -First 1
                $lastHit = $groupHits | Select-Object -Last 1
                $lastDistancePre = Get-CoordDistance -Hit $lastHit -Expected $PreExpected
                $lastDistancePost = Get-CoordDistance -Hit $lastHit -Expected $PostExpected
                $delta = Get-CoordDelta -First $firstHit -Last $lastHit

                [pscustomobject]@{
                    PrimaryBase = $_.Name
                    PrimaryCoordAddress = [string](Get-JsonPropertyValue -Object $lastHit -Name 'PrimaryCoordAddress')
                    HitCount = $_.Count
                    FirstCoord = New-Coord -Hit $firstHit
                    LastCoord = New-Coord -Hit $lastHit
                    InTraceDelta = $delta
                    DistanceToPreReaderBridge = $lastDistancePre
                    DistanceToPostReaderBridge = $lastDistancePost
                    LastSecondaryBase = [string](Get-JsonPropertyValue -Object $lastHit -Name 'SecondaryBase')
                    LastSecondaryCoordAddress = [string](Get-JsonPropertyValue -Object $lastHit -Name 'SecondaryCoordAddress')
                    LastRip = [string](Get-JsonPropertyValue -Object $lastHit -Name 'Rip')
                    LastInstruction = [string](Get-JsonPropertyValue -Object $lastHit -Name 'InstructionText')
                }
            } |
            Sort-Object @{ Expression = { if ($null -eq $_.DistanceToPostReaderBridge) { [double]::PositiveInfinity } else { $_.DistanceToPostReaderBridge } } },
                @{ Expression = { -1 * [int]$_.HitCount } },
                PrimaryBase
    )
}

function ConvertTo-LuaLongString {
    param([string]$Value)

    if ($null -eq $Value) {
        $Value = ''
    }

    return ('[=[{0}]=]' -f ($Value -replace '\]=\]', ']= ]'))
}

Assert-ExactStimulusTarget

foreach ($path in @($resolvedStatusFile, $resolvedHitsFile, $resolvedOutputFile)) {
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Force
    }
}

foreach ($directory in @((Split-Path -Parent $resolvedOutputFile), (Split-Path -Parent $resolvedStatusFile), (Split-Path -Parent $resolvedHitsFile))) {
    if (-not [string]::IsNullOrWhiteSpace($directory)) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }
}

$effectiveProcessId = Get-EffectiveTargetProcessId
if ($null -eq $effectiveProcessId -or $effectiveProcessId -le 0) {
    throw 'Coord-writer instruction trace requires an exact live PID or HWND.'
}

$instruction = Resolve-InstructionAddress -EffectiveProcessId $effectiveProcessId
$instructionAddress = [UInt64]$instruction.Address
$primaryCoordOffset = Parse-HexUInt64 -Value $PrimaryCoordOffsetHex
$primaryWriteOffset = Parse-HexUInt64 -Value $PrimaryWriteOffsetHex
$secondaryCoordOffset = Parse-HexUInt64 -Value $SecondaryCoordOffsetHex

$preTraceRiftState = Get-ProcessState -Name $ProcessName -Id $effectiveProcessId
$preTraceCeState = Get-ProcessState -Name 'cheatengine-x86_64-SSE4-AVX2' -Id 0
$preReader = $null
$preReaderError = $null
try {
    $preReader = Invoke-ReaderJson -Arguments (@(Get-ReaderTargetArguments) + @('--read-player-current', '--json'))
}
catch {
    $preReaderError = $_.Exception.Message
}

& $ceExecScript -LuaFile $traceLuaFile | Out-Null

$processSelectorLiteral = $effectiveProcessId.ToString([System.Globalization.CultureInfo]::InvariantCulture)
$luaCode = @"
return RiftReaderCoordWriterTrace.armAsync($processSelectorLiteral, $instructionAddress, $(ConvertTo-LuaLongString $resolvedStatusFile), $(ConvertTo-LuaLongString $resolvedHitsFile), $MaxHits, $($TimeoutSeconds * 1000), $(ConvertTo-LuaLongString $PrimaryRegister), $primaryCoordOffset, $primaryWriteOffset, $(ConvertTo-LuaLongString $SecondaryRegister), $secondaryCoordOffset, [=[auto]=])
"@
& $ceExecScript -Code $luaCode | Out-Null

$status = $null
$armDeadline = [DateTime]::UtcNow.AddSeconds([Math]::Max(3, $ArmReadyTimeoutSeconds))
while ([DateTime]::UtcNow -lt $armDeadline) {
    if (Test-Path -LiteralPath $resolvedStatusFile) {
        $status = Read-KeyValueFile -Path $resolvedStatusFile
        if ($status.status -in @('armed', 'completed', 'error')) {
            break
        }
    }

    Start-Sleep -Milliseconds 100
}

if ($null -eq $status -or $status.status -notin @('armed', 'completed', 'error')) {
    try {
        & $ceExecScript -Code 'return RiftReaderCoordWriterTrace.cleanup()' | Out-Null
    }
    catch {
    }

    throw "Coord-writer instruction trace did not arm before timeout. Status file: $resolvedStatusFile"
}

$stimulusProcess = $null
$stimulusAttempted = $false
if ($status.status -eq 'armed' -and $StimulusMode -ne 'None' -and -not [string]::IsNullOrWhiteSpace($StimulusKey)) {
    Start-Sleep -Milliseconds $StimulusStartDelayMilliseconds
    $stimulusProcess = Start-StimulusProcess
    $stimulusAttempted = $true
}

$deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
while ([DateTime]::UtcNow -lt $deadline) {
    if (Test-Path -LiteralPath $resolvedStatusFile) {
        $status = Read-KeyValueFile -Path $resolvedStatusFile
        if ($status.status -in @('completed', 'error')) {
            break
        }
    }

    Start-Sleep -Milliseconds 150
}

$stimulusExitCode = Wait-StimulusProcess -Process $stimulusProcess

if (($null -eq $status) -or ($status.status -notin @('completed', 'error'))) {
    try {
        & $ceExecScript -Code 'return RiftReaderCoordWriterTrace.cleanup()' | Out-Null
    }
    catch {
    }

    if (Test-Path -LiteralPath $resolvedStatusFile) {
        $status = Read-KeyValueFile -Path $resolvedStatusFile
    }
}

$postTraceRiftState = Get-ProcessState -Name $ProcessName -Id $effectiveProcessId
$postTraceCeState = Get-ProcessState -Name 'cheatengine-x86_64-SSE4-AVX2' -Id 0
$sessionCompromised = (Test-ProcessStateCompromised -ProcessState $postTraceRiftState) -or (Test-ProcessStateCompromised -ProcessState $postTraceCeState)
$cleanupAttempted = $false
$cleanupSucceeded = $false
if (-not $sessionCompromised) {
    $cleanupAttempted = $true
    try {
        & $ceExecScript -Code 'return RiftReaderCoordWriterTrace.cleanup()' | Out-Null
        $cleanupSucceeded = $true
    }
    catch {
        Write-Warning ("Unable to clean up coord-writer trace helper cleanly: {0}" -f $_.Exception.Message)
    }
}
else {
    Write-Warning 'Skipping CE coord-writer trace cleanup because the live session is already compromised.'
}

$postCleanupRiftState = Get-ProcessState -Name $ProcessName -Id $effectiveProcessId
$postCleanupCeState = Get-ProcessState -Name 'cheatengine-x86_64-SSE4-AVX2' -Id 0

$postReader = $null
$postReaderError = $null
try {
    $postReader = Invoke-ReaderJson -Arguments (@(Get-ReaderTargetArguments) + @('--read-player-current', '--json'))
}
catch {
    $postReaderError = $_.Exception.Message
}

$hits = Read-Hits
$preExpected = Get-ExpectedCoords -ReaderSnapshot $preReader
$postExpected = Get-ExpectedCoords -ReaderSnapshot $postReader
$groups = Summarize-Hits -Hits $hits -PreExpected $preExpected -PostExpected $postExpected
$topGroups = @($groups | Select-Object -First 20)

$resultStatus = if ($sessionCompromised) {
    'session-compromised'
}
elseif ($null -ne $status -and $status.status -eq 'error') {
    'error'
}
elseif (@($hits).Count -gt 0) {
    'collected'
}
else {
    'no-hits'
}

$result = [ordered]@{
    Mode = 'coord-writer-instruction-trace'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    Status = $resultStatus
    ProcessName = $ProcessName
    ProcessId = $effectiveProcessId
    TargetWindowHandle = $TargetWindowHandle
    ModuleName = $ModuleName
    ModuleBase = if ($null -ne $instruction.ModuleBase) { Format-HexUInt64 -Value ([UInt64]$instruction.ModuleBase) } else { $null }
    ModuleOffset = if ($null -ne $instruction.ModuleOffset) { Format-HexUInt64 -Value ([UInt64]$instruction.ModuleOffset) } else { $ModuleOffsetHex }
    InstructionAddress = Format-HexUInt64 -Value $instructionAddress
    InstructionAddressSource = [string]$instruction.Source
    Primary = [ordered]@{
        Register = $PrimaryRegister
        CoordOffset = Format-HexUInt64 -Value $primaryCoordOffset
        WriteOffset = Format-HexUInt64 -Value $primaryWriteOffset
    }
    Secondary = [ordered]@{
        Register = $SecondaryRegister
        CoordOffset = Format-HexUInt64 -Value $secondaryCoordOffset
    }
    Stimulus = [ordered]@{
        Attempted = [bool]$stimulusAttempted
        Mode = $StimulusMode
        Key = $StimulusKey
        HoldMilliseconds = $StimulusHoldMilliseconds
        ExitCode = $stimulusExitCode
    }
    StatusFile = $resolvedStatusFile
    HitsFile = $resolvedHitsFile
    HitCount = @($hits).Count
    TraceStatus = $status
    PreReaderError = $preReaderError
    PreReader = $preReader
    PostReaderError = $postReaderError
    PostReader = $postReader
    CandidateGroups = @($groups)
    TopCandidateGroups = $topGroups
    Session = [ordered]@{
        Compromised = [bool]$sessionCompromised
        PreTraceRift = $preTraceRiftState
        PostTraceRift = $postTraceRiftState
        PostCleanupRift = $postCleanupRiftState
        PreTraceCheatEngine = $preTraceCeState
        PostTraceCheatEngine = $postTraceCeState
        PostCleanupCheatEngine = $postCleanupCeState
        CleanupAttempted = [bool]$cleanupAttempted
        CleanupSucceeded = [bool]$cleanupSucceeded
    }
    PromotionGate = [ordered]@{
        Promoted = $false
        ActiveMovementAllowed = $false
        Reason = 'Collector output is candidate-only until a same-PID coord access proof resolves coord-trace-coords.'
    }
    OutputFile = $resolvedOutputFile
}

$jsonText = $result | ConvertTo-Json -Depth 64
$jsonText | Set-Content -Path $resolvedOutputFile -Encoding utf8

if ($Json) {
    Write-Output $jsonText
}
else {
    Write-Host "Coord-writer trace:   $resolvedOutputFile"
    Write-Host "Status:               $resultStatus"
    Write-Host "Instruction:          $($result.InstructionAddress) ($ModuleName+$($result.ModuleOffset))"
    Write-Host "Hits:                 $(@($hits).Count)"
    Write-Host "Active movement gate: false"
}

if ($resultStatus -eq 'error') {
    exit 1
}

if ($resultStatus -eq 'session-compromised') {
    exit 2
}
