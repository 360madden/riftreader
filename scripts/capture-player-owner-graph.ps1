[CmdletBinding()]
param(
    [switch]$Json,
    [switch]$RefreshSelectorTrace,
    [string]$ProcessName = 'rift_x64',
    [int]$ProcessId,
    [string]$TargetWindowHandle,
    [string]$SelectorTraceFile = (Join-Path $PSScriptRoot 'captures\player-selector-owner-trace.json'),
    [string]$OutputFile = (Join-Path $PSScriptRoot 'captures\player-owner-graph.json')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$selectorTraceScript = Join-Path $PSScriptRoot 'trace-player-selector-owner.ps1'
$resolvedSelectorTraceFile = [System.IO.Path]::GetFullPath($SelectorTraceFile)
$resolvedOutputFile = [System.IO.Path]::GetFullPath($OutputFile)

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public static class RiftOwnerGraphTargetNative
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
        if (-not [RiftOwnerGraphTargetNative]::IsWindow($handle)) {
            throw "Target window handle '$TargetWindowHandle' is not a valid window."
        }

        $ownerProcessId = [uint32]0
        [void][RiftOwnerGraphTargetNative]::GetWindowThreadProcessId($handle, [ref]$ownerProcessId)
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

function Read-Bytes {
    param(
        [Parameter(Mandatory = $true)]
        [UInt64]$Address,

        [Parameter(Mandatory = $true)]
        [int]$Length
    )

    $arguments = @(Get-ReaderTargetArguments) + @(
        '--address', ('0x{0:X}' -f $Address),
        '--length', $Length.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '--json')
    $result = Invoke-ReaderJson -Arguments $arguments

    $hex = ([string]$result.BytesHex -replace '\s+', '').Trim()
    $bytes = New-Object byte[] ($hex.Length / 2)
    for ($index = 0; $index -lt $bytes.Length; $index++) {
        $bytes[$index] = [Convert]::ToByte($hex.Substring($index * 2, 2), 16)
    }

    return $bytes
}

function Read-UInt64At {
    param(
        [Parameter(Mandatory = $true)]
        [byte[]]$Bytes,

        [Parameter(Mandatory = $true)]
        [int]$Offset
    )

    if (($Offset + 8) -gt $Bytes.Length) {
        return $null
    }

    return [BitConverter]::ToUInt64($Bytes, $Offset)
}

function Read-FloatAt {
    param(
        [Parameter(Mandatory = $true)]
        [byte[]]$Bytes,

        [Parameter(Mandatory = $true)]
        [int]$Offset
    )

    if (($Offset + 4) -gt $Bytes.Length) {
        return $null
    }

    return [BitConverter]::ToSingle($Bytes, $Offset)
}

function Test-CoordMatch {
    param(
        $ExpectedX,
        $ExpectedY,
        $ExpectedZ,
        $ActualX,
        $ActualY,
        $ActualZ
    )

    if ($null -eq $ActualX -or $null -eq $ActualY -or $null -eq $ActualZ) {
        return $false
    }

    return ([math]::Abs($ActualX - $ExpectedX) -le 0.25) -and
        ([math]::Abs($ActualY - $ExpectedY) -le 0.25) -and
        ([math]::Abs($ActualZ - $ExpectedZ) -le 0.25)
}

if ($RefreshSelectorTrace -or -not (Test-Path -LiteralPath $resolvedSelectorTraceFile)) {
    $selectorTraceArguments = @{
        Json = $true
        ProcessName = $ProcessName
    }
    $effectiveProcessId = Get-EffectiveTargetProcessId
    if ($null -ne $effectiveProcessId -and $effectiveProcessId -gt 0) {
        $selectorTraceArguments['ProcessId'] = $effectiveProcessId
    }
    if (-not [string]::IsNullOrWhiteSpace($TargetWindowHandle)) {
        $selectorTraceArguments['TargetWindowHandle'] = $TargetWindowHandle
    }
    & $selectorTraceScript @selectorTraceArguments | Out-Null
}

if (-not (Test-Path -LiteralPath $resolvedSelectorTraceFile)) {
    throw "Selector-owner trace file not found: $resolvedSelectorTraceFile"
}

$selectorTrace = Get-Content -LiteralPath $resolvedSelectorTraceFile -Raw | ConvertFrom-Json -Depth 30
$ownerAddress = Parse-HexUInt64 -Value ([string]$selectorTrace.Owner.ObjectAddress)
$selectedSourceAddress = Parse-HexUInt64 -Value ([string]$selectorTrace.SelectedSource.Address)
$expectedX = [double]$selectorTrace.SelectedSource.Coord48.X
$expectedY = [double]$selectorTrace.SelectedSource.Coord48.Y
$expectedZ = [double]$selectorTrace.SelectedSource.Coord48.Z

$ownerBytes = Read-Bytes -Address $ownerAddress -Length 0x200
$children = New-Object System.Collections.Generic.List[object]

for ($offset = 0; $offset -lt 0x180; $offset += 8) {
    $pointerValue = Read-UInt64At -Bytes $ownerBytes -Offset $offset
    if ($null -eq $pointerValue -or $pointerValue -le 0x100000000 -or $pointerValue -ge 0x7FFFFFFFFFFF) {
        continue
    }

    $childBytes = Read-Bytes -Address $pointerValue -Length 0x180
    $backref100 = Read-UInt64At -Bytes $childBytes -Offset 0x100
    $backref68 = Read-UInt64At -Bytes $childBytes -Offset 0x68
    $sourceAt8 = Read-UInt64At -Bytes $childBytes -Offset 0x8
    $coord48x = Read-FloatAt -Bytes $childBytes -Offset 0x48
    $coord48y = Read-FloatAt -Bytes $childBytes -Offset 0x4C
    $coord48z = Read-FloatAt -Bytes $childBytes -Offset 0x50
    $coord88x = if (0x88 + 12 -le $childBytes.Length) { Read-FloatAt -Bytes $childBytes -Offset 0x88 } else { $null }
    $coord88y = if (0x8C + 12 -le $childBytes.Length) { Read-FloatAt -Bytes $childBytes -Offset 0x8C } else { $null }
    $coord88z = if (0x90 + 12 -le $childBytes.Length) { Read-FloatAt -Bytes $childBytes -Offset 0x90 } else { $null }

    $coord48Matches = ($null -ne $coord48x) -and ($null -ne $coord48y) -and ($null -ne $coord48z) -and
        (Test-CoordMatch -ExpectedX $expectedX -ExpectedY $expectedY -ExpectedZ $expectedZ -ActualX $coord48x -ActualY $coord48y -ActualZ $coord48z)
    $coord88Matches = ($null -ne $coord88x) -and ($null -ne $coord88y) -and ($null -ne $coord88z) -and
        (Test-CoordMatch -ExpectedX $expectedX -ExpectedY $expectedY -ExpectedZ $expectedZ -ActualX $coord88x -ActualY $coord88y -ActualZ $coord88z)

    $role = 'linked-child'
    if ($sourceAt8 -eq $selectedSourceAddress -and $backref100 -eq $ownerAddress) {
        $role = 'source-wrapper'
    }
    elseif ($backref68 -eq $ownerAddress) {
        $role = 'owner-backref-wrapper'
    }
    elseif ($sourceAt8 -eq ($ownerAddress + 0xC8)) {
        $role = 'owner-state-wrapper'
    }
    elseif ($coord48Matches -or $coord88Matches) {
        $role = 'coord-bearing-child'
    }

    $children.Add([ordered]@{
        OwnerOffset = $offset
        OwnerOffsetHex = ('0x{0:X}' -f $offset)
        Address = ('0x{0:X}' -f $pointerValue)
        Role = $role
        BackrefAt100 = if ($backref100) { ('0x{0:X}' -f $backref100) } else { $null }
        BackrefAt68 = if ($backref68) { ('0x{0:X}' -f $backref68) } else { $null }
        SourceAt8 = if ($sourceAt8) { ('0x{0:X}' -f $sourceAt8) } else { $null }
        Coord48 = [ordered]@{
            X = $coord48x
            Y = $coord48y
            Z = $coord48z
            MatchesSelectedSource = $coord48Matches
        }
        Coord88 = [ordered]@{
            X = $coord88x
            Y = $coord88y
            Z = $coord88z
            MatchesSelectedSource = $coord88Matches
        }
    })
}

$result = [ordered]@{
    Mode = 'player-owner-graph'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    ProcessName = $ProcessName
    ProcessId = Get-EffectiveTargetProcessId
    TargetWindowHandle = $TargetWindowHandle
    SelectorTraceFile = $resolvedSelectorTraceFile
    Owner = [ordered]@{
        Address = ('0x{0:X}' -f $ownerAddress)
        SelectedSourceAddress = ('0x{0:X}' -f $selectedSourceAddress)
        ContainerAddress = [string]$selectorTrace.Owner.ContainerAddress
        SelectorIndex = [int]$selectorTrace.Owner.SelectorIndex
    }
    ChildCount = $children.Count
    Children = $children.ToArray()
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
    Write-Host "Owner graph file:       $resolvedOutputFile"
    Write-Host "Owner object:           0x$('{0:X}' -f $ownerAddress)"
    Write-Host "Selected source:        0x$('{0:X}' -f $selectedSourceAddress)"
    foreach ($child in $children) {
        Write-Host ("  {0} -> {1} [{2}]" -f $child.OwnerOffsetHex, $child.Address, $child.Role)
    }
}
