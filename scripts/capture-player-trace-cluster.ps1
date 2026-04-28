[CmdletBinding()]
param(
    [switch]$Json,
    [switch]$RefreshTrace,
    [int]$InstructionsBefore = 8,
    [int]$InstructionsAfter = 16,
    [string]$ProcessName = 'rift_x64',
    [int]$ProcessId,
    [string]$TargetWindowHandle,
    [string]$TraceFile = (Join-Path $PSScriptRoot 'captures\player-coord-write-trace.json'),
    [string]$OutputFile = (Join-Path $PSScriptRoot 'captures\player-coord-trace-cluster.json')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$traceScript = Join-Path $PSScriptRoot 'trace-player-coord-write.ps1'
$ceExecScript = Join-Path $PSScriptRoot 'cheatengine-exec.ps1'
$clusterLuaFile = Join-Path $PSScriptRoot 'cheat-engine\RiftReaderDisasmCluster.lua'
$resolvedTraceFile = [System.IO.Path]::GetFullPath($TraceFile)
$resolvedOutputFile = [System.IO.Path]::GetFullPath($OutputFile)
$rawClusterFile = [System.IO.Path]::ChangeExtension($resolvedOutputFile, '.tsv')

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public static class RiftTraceClusterTargetNative
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

function Get-EffectiveTargetProcessId {
    $handle = ConvertTo-WindowHandle -HandleText $TargetWindowHandle
    if ($handle -ne [IntPtr]::Zero) {
        if (-not [RiftTraceClusterTargetNative]::IsWindow($handle)) {
            throw "Target window handle '$TargetWindowHandle' is not a valid window."
        }

        $ownerProcessId = [uint32]0
        [void][RiftTraceClusterTargetNative]::GetWindowThreadProcessId($handle, [ref]$ownerProcessId)
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

function Get-TraceTargetArguments {
    $arguments = @('-ProcessName', $ProcessName)
    $effectiveProcessId = Get-EffectiveTargetProcessId
    if ($null -ne $effectiveProcessId -and $effectiveProcessId -gt 0) {
        $arguments += @('-ProcessId', $effectiveProcessId.ToString([System.Globalization.CultureInfo]::InvariantCulture))
    }

    if (-not [string]::IsNullOrWhiteSpace($TargetWindowHandle)) {
        $arguments += @('-TargetWindowHandle', $TargetWindowHandle)
    }

    return $arguments
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

function Get-MemoryOperand {
    param(
        [string]$Opcode,
        [string]$Extra
    )

    $candidate = @($Opcode, $Extra) -join ' '
    $match = [regex]::Match($candidate, '\[[^\]]+\]')
    if ($match.Success) {
        return $match.Value
    }

    return $null
}

function Get-RegisterRelativeOffset {
    param(
        [string]$Operand,
        [string]$Register
    )

    if ([string]::IsNullOrWhiteSpace($Operand) -or [string]::IsNullOrWhiteSpace($Register)) {
        return $null
    }

    $pattern = '\[\s*' + [regex]::Escape($Register.ToLowerInvariant()) + '\s*(?<sign>[+-])\s*(?<value>[0-9A-Fa-f]+)\s*\]'
    $match = [regex]::Match($Operand.ToLowerInvariant(), $pattern)
    if (-not $match.Success) {
        return $null
    }

    $value = [Convert]::ToInt32($match.Groups['value'].Value, 16)
    if ($match.Groups['sign'].Value -eq '-') {
        return -1 * $value
    }

    return $value
}

function Get-RoleHint {
    param(
        [int]$Offset,
        [pscustomobject]$Anchor
    )

    if ($Offset -eq [int]$Anchor.CoordXRelativeOffset) { return 'coord-x' }
    if ($Offset -eq [int]$Anchor.CoordYRelativeOffset) { return 'coord-y' }
    if ($Offset -eq [int]$Anchor.CoordZRelativeOffset) { return 'coord-z' }
    if ($Offset -eq [int]$Anchor.LevelRelativeOffset) { return 'level' }
    if ($Offset -eq [int]$Anchor.HealthRelativeOffset) { return 'health' }
    return $null
}

function Convert-OffsetToLittleEndianPattern {
    param(
        [Parameter(Mandatory = $true)]
        [int]$Offset
    )

    $bytes = [BitConverter]::GetBytes([int]$Offset)
    return ($bytes | ForEach-Object { $_.ToString('X2', [System.Globalization.CultureInfo]::InvariantCulture) }) -join ' '
}

function Invoke-CoordTraceRefresh {
    param(
        [int]$MaxAttempts = 3,
        [int]$RetryDelayMilliseconds = 1500
    )

    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        try {
            $traceArguments = @{
                Json = $true
                MaxCandidates = 4
                WatchMode = 'access'
                BreakpointSize = 12
                StimulusMode = 'AutoHotkey'
                ProcessName = $ProcessName
            }
            $effectiveProcessId = Get-EffectiveTargetProcessId
            if ($null -ne $effectiveProcessId -and $effectiveProcessId -gt 0) {
                $traceArguments['ProcessId'] = $effectiveProcessId
            }
            if (-not [string]::IsNullOrWhiteSpace($TargetWindowHandle)) {
                $traceArguments['TargetWindowHandle'] = $TargetWindowHandle
            }

            & $traceScript @traceArguments | Out-Null
            return
        }
        catch {
            $message = $_.Exception.Message
            $playerNotReady = $message -like '*Current player snapshot is not ready after refresh*'
            if ($playerNotReady -and $attempt -lt $MaxAttempts) {
                Write-Warning ("Coord-trace refresh outran current-player recovery after /reloadui; retrying in {0} ms (attempt {1}/{2})." -f $RetryDelayMilliseconds, ($attempt + 1), $MaxAttempts)
                Start-Sleep -Milliseconds $RetryDelayMilliseconds
                continue
            }

            throw
        }
    }
}

if ($RefreshTrace -or -not (Test-Path -LiteralPath $resolvedTraceFile)) {
    Invoke-CoordTraceRefresh
}

$anchor = Invoke-ReaderJson -Arguments (@(Get-ReaderTargetArguments) + @('--read-player-coord-anchor', '--json'))
if (-not $anchor.TraceMatchesProcess) {
    Invoke-CoordTraceRefresh
    $anchor = Invoke-ReaderJson -Arguments (@(Get-ReaderTargetArguments) + @('--read-player-coord-anchor', '--json'))
}

if (-not $anchor.TraceMatchesProcess) {
    throw "The saved coord trace still does not match the current Rift process."
}

if (-not $anchor.InstructionAddress) {
    throw "The coord-trace anchor did not contain an instruction address."
}

$instructionAddress = Parse-HexUInt64 -Value ([string]$anchor.InstructionAddress)
$rawDirectory = Split-Path -Parent $rawClusterFile
if (-not [string]::IsNullOrWhiteSpace($rawDirectory)) {
    New-Item -ItemType Directory -Path $rawDirectory -Force | Out-Null
}

& $ceExecScript -LuaFile $clusterLuaFile | Out-Null
$luaCode = @"
return RiftReaderDisasmCluster.dump([[$rawClusterFile]], $instructionAddress, $InstructionsBefore, $InstructionsAfter)
"@
& $ceExecScript -Code $luaCode | Out-Null

if (-not (Test-Path -LiteralPath $rawClusterFile)) {
    throw "Cheat Engine did not produce the disassembly cluster file '$rawClusterFile'."
}

$rows = Import-Csv -LiteralPath $rawClusterFile -Delimiter "`t"
$baseRegister = [string]$anchor.BaseRegister
$interesting = New-Object System.Collections.Generic.List[object]
$instructions = foreach ($row in $rows) {
    $opcode = [string](Get-ObjectValue -Object $row -Name 'opcode')
    $extra = [string](Get-ObjectValue -Object $row -Name 'extra')
    $full = [string](Get-ObjectValue -Object $row -Name 'full')
    $memoryOperand = Get-MemoryOperand -Opcode $opcode -Extra $extra
    $relativeOffset = if ($memoryOperand) { Get-RegisterRelativeOffset -Operand $memoryOperand -Register $baseRegister } else { $null }
    $roleHint = if ($null -ne $relativeOffset) { Get-RoleHint -Offset $relativeOffset -Anchor $anchor } else { $null }
    $usesBaseRegister = -not [string]::IsNullOrWhiteSpace($baseRegister) -and ($full -match [regex]::Escape($baseRegister))

    $record = [pscustomobject]@{
        Index = [int](Get-ObjectValue -Object $row -Name 'index')
        Address = [string](Get-ObjectValue -Object $row -Name 'address')
        Bytes = [string](Get-ObjectValue -Object $row -Name 'bytes')
        Opcode = $opcode
        Extra = $extra
        Full = $full
        UsesBaseRegister = $usesBaseRegister
        MemoryOperand = $memoryOperand
        RelativeOffset = $relativeOffset
        RoleHint = $roleHint
    }

    if ($usesBaseRegister -or $roleHint) {
        $interesting.Add($record) | Out-Null
    }

    $record
}

$suggestedClusterPattern = $null
$suggestedClusterScan = $null
if ($anchor.CoordXRelativeOffset -and $anchor.CoordYRelativeOffset -and $anchor.CoordZRelativeOffset) {
    $coordXPattern = Convert-OffsetToLittleEndianPattern -Offset ([int]$anchor.CoordXRelativeOffset)
    $coordYPattern = Convert-OffsetToLittleEndianPattern -Offset ([int]$anchor.CoordYRelativeOffset)
    $coordZPattern = Convert-OffsetToLittleEndianPattern -Offset ([int]$anchor.CoordZRelativeOffset)

    $suggestedClusterPattern = @(
        "F3 0F 10 86 $coordXPattern",
        'E8 ?? ?? ?? ??',
        "F3 0F 11 86 $coordXPattern",
        "F3 0F 10 86 $coordYPattern",
        'E8 ?? ?? ?? ??',
        "F3 0F 11 86 $coordYPattern",
        "F3 0F 10 86 $coordZPattern",
        'E8 ?? ?? ?? ??',
        "F3 0F 11 86 $coordZPattern"
    ) -join ' '

    try {
        $suggestedClusterArguments = @(Get-ReaderTargetArguments) + @(
            '--scan-module-pattern', $suggestedClusterPattern,
            '--scan-module-name', 'rift_x64.exe',
            '--json')
        $suggestedClusterScan = Invoke-ReaderJson -Arguments $suggestedClusterArguments
    }
    catch {
        $suggestedClusterScan = [pscustomobject]@{
            Mode = 'module-pattern-scan'
            Error = $_.Exception.Message
        }
    }
}

$result = [ordered]@{
    Mode = 'player-coord-trace-cluster'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    TraceFile = $resolvedTraceFile
    SourceObjectAddress = [string]$anchor.SourceObjectAddress
    SelectedSourceAddress = [string]$anchor.SourceObjectAddress
    Anchor = $anchor
    RawClusterFile = $rawClusterFile
    InstructionsBefore = $InstructionsBefore
    InstructionsAfter = $InstructionsAfter
    InstructionCount = @($instructions).Count
    InterestingInstructionCount = $interesting.Count
    SuggestedClusterPattern = $suggestedClusterPattern
    SuggestedClusterScan = $suggestedClusterScan
    Interesting = @($interesting.ToArray())
    Instructions = @($instructions)
}

$outputDirectory = Split-Path -Parent $resolvedOutputFile
if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

$jsonText = $result | ConvertTo-Json -Depth 20
Set-Content -LiteralPath $resolvedOutputFile -Value $jsonText -Encoding UTF8

if ($Json) {
    Write-Output $jsonText
}
else {
    Write-Host "Cluster file:          $resolvedOutputFile"
    Write-Host "Raw cluster TSV:       $rawClusterFile"
    Write-Host "Instruction address:   $($anchor.InstructionAddress)"
    Write-Host "Base register:         $baseRegister"
    Write-Host "Interesting count:     $($interesting.Count)"
    if ($suggestedClusterPattern) {
        Write-Host "Suggested pattern:     $suggestedClusterPattern"
        if ($suggestedClusterScan -and $suggestedClusterScan.Found -eq $true) {
            Write-Host "Suggested match:       $($suggestedClusterScan.Address) [$($suggestedClusterScan.RelativeOffsetHex)]"
        }
    }

    foreach ($item in $interesting) {
        $offsetText = if ($null -ne $item.RelativeOffset) { ("0x{0:X}" -f [int]$item.RelativeOffset) } else { 'n/a' }
        $roleText = if ($item.RoleHint) { $item.RoleHint } else { 'base-reg' }
        Write-Host ("[{0}] {1} | {2} | {3} | {4}" -f $item.Index, $item.Address, $roleText, $offsetText, $item.Full)
    }
}
