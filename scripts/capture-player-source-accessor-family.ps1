[CmdletBinding()]
param(
    [switch]$Json,
    [switch]$RefreshSourceChain,
    [string]$ProcessName = 'rift_x64',
    [int]$ProcessId,
    [string]$TargetWindowHandle,
    [string]$SourceChainFile = (Join-Path $PSScriptRoot 'captures\player-source-chain.json'),
    [string]$TraceFile = (Join-Path $PSScriptRoot 'captures\player-coord-write-trace.json'),
    [string]$OutputFile = (Join-Path $PSScriptRoot 'captures\player-source-accessor-family.json')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$sourceChainScript = Join-Path $PSScriptRoot 'capture-player-source-chain.ps1'
$ceExecScript = Join-Path $PSScriptRoot 'cheatengine-exec.ps1'
$clusterLuaFile = Join-Path $PSScriptRoot 'cheat-engine\RiftReaderDisasmCluster.lua'
$resolvedSourceChainFile = [System.IO.Path]::GetFullPath($SourceChainFile)
$resolvedTraceFile = [System.IO.Path]::GetFullPath($TraceFile)
$resolvedOutputFile = [System.IO.Path]::GetFullPath($OutputFile)

Add-Type @"
using System;
using System.Runtime.InteropServices;

public static class RiftAccessorFamilyTargetNative
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

    $text = $HandleText.Trim()
    $style = [System.Globalization.NumberStyles]::Integer
    if ($text.StartsWith('0x', [System.StringComparison]::OrdinalIgnoreCase)) {
        $text = $text.Substring(2)
        $style = [System.Globalization.NumberStyles]::HexNumber
    }

    return [IntPtr]([Int64]::Parse($text, $style, [System.Globalization.CultureInfo]::InvariantCulture))
}

function Get-EffectiveTargetProcessId {
    $handle = ConvertTo-WindowHandle -HandleText $TargetWindowHandle
    if ($handle -ne [IntPtr]::Zero) {
        if (-not [RiftAccessorFamilyTargetNative]::IsWindow($handle)) {
            throw "Target window handle '$TargetWindowHandle' is not a valid window."
        }

        $ownerProcessId = [uint32]0
        [void][RiftAccessorFamilyTargetNative]::GetWindowThreadProcessId($handle, [ref]$ownerProcessId)
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

function Get-ChildTargetArgumentMap {
    $argumentMap = @{
        ProcessName = $ProcessName
    }

    $effectiveProcessId = Get-EffectiveTargetProcessId
    if ($null -ne $effectiveProcessId -and $effectiveProcessId -gt 0) {
        $argumentMap['ProcessId'] = $effectiveProcessId
    }

    if (-not [string]::IsNullOrWhiteSpace($TargetWindowHandle)) {
        $argumentMap['TargetWindowHandle'] = $TargetWindowHandle
    }

    return $argumentMap
}

function Invoke-ReadBytes {
    param(
        [Parameter(Mandatory = $true)]
        [UInt64]$Address,

        [Parameter(Mandatory = $true)]
        [int]$Length
    )

    $arguments = @(Get-ReaderTargetArguments)
    $arguments += @(
        '--address', ('0x{0:X}' -f $Address),
        '--length', $Length.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '--json')

    return Invoke-ReaderJson -Arguments $arguments
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

function Normalize-Bytes {
    param([string]$Bytes)

    if ([string]::IsNullOrWhiteSpace($Bytes)) {
        return $null
    }

    $hex = ($Bytes -replace '\s+', '').Trim()
    if ([string]::IsNullOrWhiteSpace($hex)) {
        return $null
    }

    return (($hex -split '(.{2})' | Where-Object { $_ }) -join ' ').Trim().ToUpperInvariant()
}

function Get-PatternToken {
    param(
        [Parameter(Mandatory = $true)]
        [pscustomobject]$Instruction
    )

    $bytes = Normalize-Bytes -Bytes ([string]$Instruction.Bytes)
    if ([string]::IsNullOrWhiteSpace($bytes)) {
        throw "Instruction '$($Instruction.Full)' did not contain byte text."
    }

    $opcode = [string]$Instruction.Opcode
    $parts = $bytes.Split(' ', [System.StringSplitOptions]::RemoveEmptyEntries)
    if ($parts.Count -lt 1) {
        throw "Unable to tokenize instruction '$($Instruction.Full)'."
    }

    if ($opcode -like 'call *' -and $parts.Count -eq 5 -and $parts[0] -eq 'E8') {
        return 'E8 ?? ?? ?? ??'
    }

    if ($opcode -like 'j* *') {
        if ($parts.Count -eq 2) {
            return ($parts[0] + ' ??')
        }

        if ($parts.Count -eq 6 -and $parts[0] -eq '0F') {
            return ($parts[0] + ' ' + $parts[1] + ' ?? ?? ?? ??')
        }
    }

    return $bytes
}

function Invoke-DisasmCluster {
    param(
        [Parameter(Mandatory = $true)]
        [UInt64]$Address,

        [Parameter(Mandatory = $true)]
        [string]$OutputPath,

        [int]$Before = 140,
        [int]$After = 140
    )

    & $ceExecScript -LuaFile $clusterLuaFile | Out-Null

    $luaCode = @"
return RiftReaderDisasmCluster.dump([[$OutputPath]], $Address, $Before, $After)
"@
    & $ceExecScript -Code $luaCode | Out-Null

    if (-not (Test-Path -LiteralPath $OutputPath)) {
        throw "Cheat Engine did not produce disassembly cluster '$OutputPath'."
    }

    return @(Import-Csv -LiteralPath $OutputPath -Delimiter "`t")
}

function Convert-HexToBytes {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Hex
    )

    $normalized = ($Hex -replace '\s+', '').Trim()
    if ([string]::IsNullOrWhiteSpace($normalized) -or ($normalized.Length % 2) -ne 0) {
        return @()
    }

    $buffer = New-Object byte[] ($normalized.Length / 2)
    for ($index = 0; $index -lt $buffer.Length; $index++) {
        $buffer[$index] = [Convert]::ToByte($normalized.Substring($index * 2, 2), 16)
    }

    return $buffer
}

if ($RefreshSourceChain -or -not (Test-Path -LiteralPath $resolvedSourceChainFile)) {
    $sourceChainArguments = Get-ChildTargetArgumentMap
    $sourceChainArguments['Json'] = $true
    & $sourceChainScript @sourceChainArguments | Out-Null
}

if (-not (Test-Path -LiteralPath $resolvedSourceChainFile)) {
    throw "Player source-chain file not found: $resolvedSourceChainFile"
}

$sourceChain = Get-Content -LiteralPath $resolvedSourceChainFile -Raw | ConvertFrom-Json -Depth 30
$accessorStart = [string]$sourceChain.Accessor.FunctionStart
$preparationTarget = [string]$sourceChain.Preparation.FunctionStart

if ([string]::IsNullOrWhiteSpace($accessorStart)) {
    throw "Source-chain file did not contain an accessor start address."
}

if ([string]::IsNullOrWhiteSpace($preparationTarget)) {
    throw "Source-chain file did not contain the preparation function address."
}

$sourceObjectAddress = $null
if (Test-Path -LiteralPath $resolvedTraceFile) {
    $traceDocument = Get-Content -LiteralPath $resolvedTraceFile -Raw | ConvertFrom-Json -Depth 30
    $sourceRegisterValue = [string]$traceDocument.Trace.Registers.RDI
    if (-not [string]::IsNullOrWhiteSpace($sourceRegisterValue)) {
        $sourceObjectAddress = Parse-HexUInt64 -Value $sourceRegisterValue
    }
}

$familyClusterFile = [System.IO.Path]::ChangeExtension($resolvedOutputFile, '.tsv')
$instructions = Invoke-DisasmCluster -Address (Parse-HexUInt64 -Value $accessorStart) -OutputPath $familyClusterFile -Before 140 -After 140

$accessors = New-Object System.Collections.Generic.List[object]
for ($index = 0; $index -le ($instructions.Count - 8); $index++) {
    $window = $instructions[$index..($index + 7)]

    if ([string]$window[0].Opcode -ne 'push rbx') { continue }
    if ([string]$window[1].Opcode -ne 'sub rsp,20') { continue }
    if ([string]$window[2].Opcode -ne 'mov rbx,rcx') { continue }
    if ([string]$window[3].Opcode -ne "call $preparationTarget") { continue }
    if (-not ([string]$window[4].Opcode -match '^lea rax,\[rbx\+(?<offset>[0-9A-Fa-f]+)\]$')) { continue }
    if ([string]$window[5].Opcode -ne 'add rsp,20') { continue }
    if ([string]$window[6].Opcode -ne 'pop rbx') { continue }
    if (-not ([string]$window[7].Opcode -like 'ret*')) { continue }

    $returnOffset = [Convert]::ToInt32($Matches['offset'], 16)
    $pattern = ($window | ForEach-Object { Get-PatternToken -Instruction $_ }) -join ' '
    $scanArguments = @(Get-ReaderTargetArguments)
    $scanArguments += @(
        '--scan-module-pattern', $pattern,
        '--scan-module-name', 'rift_x64.exe',
        '--json')
    $scan = Invoke-ReaderJson -Arguments $scanArguments

    $liveProbe = $null
    if ($null -ne $sourceObjectAddress) {
        $readResult = Invoke-ReadBytes -Address ($sourceObjectAddress + [UInt64]$returnOffset) -Length 12
        $probeBytes = Convert-HexToBytes -Hex ([string]$readResult.BytesHex)
        if ($probeBytes.Length -ge 12) {
            $liveProbe = [ordered]@{
                SourceObjectAddress = ('0x{0:X}' -f $sourceObjectAddress)
                ProbeAddress = ('0x{0:X}' -f ($sourceObjectAddress + [UInt64]$returnOffset))
                Float0 = [BitConverter]::ToSingle($probeBytes, 0)
                Float1 = [BitConverter]::ToSingle($probeBytes, 4)
                Float2 = [BitConverter]::ToSingle($probeBytes, 8)
                Dword0 = [BitConverter]::ToUInt32($probeBytes, 0)
                Dword1 = [BitConverter]::ToUInt32($probeBytes, 4)
                Dword2 = [BitConverter]::ToUInt32($probeBytes, 8)
            }
        }
    }

    $accessors.Add([ordered]@{
        FunctionStart = [string]$window[0].Address
        ReturnOffset = $returnOffset
        ReturnOffsetHex = ('0x{0:X}' -f $returnOffset)
        PreparationTarget = $preparationTarget
        ReturnInstruction = $window[4]
        Pattern = $pattern
        PatternScan = $scan
        LiveProbe = $liveProbe
    })
}

$result = [ordered]@{
    Mode = 'player-source-accessor-family'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    ProcessName = $ProcessName
    ProcessId = Get-EffectiveTargetProcessId
    TargetWindowHandle = if (-not [string]::IsNullOrWhiteSpace($TargetWindowHandle)) { $TargetWindowHandle } else { $null }
    SourceChainFile = $resolvedSourceChainFile
    TraceFile = if (Test-Path -LiteralPath $resolvedTraceFile) { $resolvedTraceFile } else { $null }
    SourceObjectAddress = if ($null -ne $sourceObjectAddress) { ('0x{0:X}' -f $sourceObjectAddress) } else { $null }
    FamilyClusterFile = $familyClusterFile
    PreparationTarget = $preparationTarget
    AccessorCount = $accessors.Count
    Accessors = @($accessors | Sort-Object ReturnOffset)
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
    Write-Host "Accessor family file:  $resolvedOutputFile"
    Write-Host "Preparation target:    $preparationTarget"
    Write-Host "Accessor count:        $($accessors.Count)"
    foreach ($accessor in ($accessors | Sort-Object ReturnOffset)) {
        $scan = $accessor.PatternScan
        $scanText = if ($scan -and $scan.Found -eq $true) { "$($scan.Address) [$($scan.RelativeOffsetHex)]" } else { 'not found' }
        Write-Host ("  {0} -> {1} | {2}" -f $accessor.FunctionStart, $accessor.ReturnOffsetHex, $scanText)
    }
}
