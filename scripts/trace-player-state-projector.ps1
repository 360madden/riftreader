[CmdletBinding()]
param(
    [switch]$Json,
    [switch]$RefreshOwnerGraph,
    [int]$TimeoutSeconds = 10,
    [int]$RepeatCount = 3,
    [int]$MoveHoldMilliseconds = 800,
    [string]$OwnerGraphFile = (Join-Path $PSScriptRoot 'captures\player-owner-graph.json'),
    [string]$OutputFile = (Join-Path $PSScriptRoot 'captures\player-state-projector-trace.json'),
    [string]$StatusFile = (Join-Path $PSScriptRoot 'captures\player-state-projector-trace.status.txt')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$ownerGraphScript = Join-Path $PSScriptRoot 'capture-player-owner-graph.ps1'
$ceExecScript = Join-Path $PSScriptRoot 'cheatengine-exec.ps1'
$projectorLuaFile = Join-Path $PSScriptRoot 'cheat-engine\RiftReaderProjectorTrace.lua'
$postKeyScript = Join-Path $PSScriptRoot 'post-rift-key.ps1'
$resolvedOwnerGraphFile = [System.IO.Path]::GetFullPath($OwnerGraphFile)
$resolvedOutputFile = [System.IO.Path]::GetFullPath($OutputFile)
$resolvedStatusFile = [System.IO.Path]::GetFullPath($StatusFile)

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

function Try-ParseUInt64Hex {
    param([string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $null
    }

    try {
        return Parse-HexUInt64 -Value $Value
    }
    catch {
        return $null
    }
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

function Read-Bytes {
    param(
        [Parameter(Mandatory = $true)]
        [UInt64]$Address,

        [Parameter(Mandatory = $true)]
        [int]$Length
    )

    $result = Invoke-ReaderJson -Arguments @(
        '--process-name', 'rift_x64',
        '--address', ('0x{0:X}' -f $Address),
        '--length', $Length.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '--json')

    return Convert-HexToBytes -Hex ([string]$result.BytesHex)
}

function Read-FloatObjectSnapshot {
    param(
        [Parameter(Mandatory = $true)]
        [UInt64]$Address
    )

    $bytes = Read-Bytes -Address $Address -Length 0xD8
    if ($bytes.Length -lt 0xD8) {
        return $null
    }

    return [ordered]@{
        Address = ('0x{0:X}' -f $Address)
        B8 = [BitConverter]::ToSingle($bytes, 0xB8)
        BC = [BitConverter]::ToSingle($bytes, 0xBC)
        C0 = [BitConverter]::ToSingle($bytes, 0xC0)
        D0 = [BitConverter]::ToSingle($bytes, 0xD0)
        D4 = [BitConverter]::ToUInt32($bytes, 0xD4)
    }
}

if ($RefreshOwnerGraph -or -not (Test-Path -LiteralPath $resolvedOwnerGraphFile)) {
    & $ownerGraphScript -Json | Out-Null
}

if (-not (Test-Path -LiteralPath $resolvedOwnerGraphFile)) {
    throw "Owner graph file not found: $resolvedOwnerGraphFile"
}

$ownerGraph = Get-Content -LiteralPath $resolvedOwnerGraphFile -Raw | ConvertFrom-Json -Depth 30
$ownerAddress = Parse-HexUInt64 -Value ([string]$ownerGraph.Owner.Address)
$selectedSourceAddress = [string]$ownerGraph.Owner.SelectedSourceAddress
$stateRecordAddress = $ownerAddress + 0xC8
$stateRecordBytes = Read-Bytes -Address $stateRecordAddress -Length 0x80
if ($stateRecordBytes.Length -lt 0x68) {
    throw "Unable to read owner state record at 0x{0:X}." -f $stateRecordAddress
}

$stateSlot50 = [BitConverter]::ToUInt64($stateRecordBytes, 0x50)
$stateSlot58 = [BitConverter]::ToUInt64($stateRecordBytes, 0x58)
$stateSlot60 = [BitConverter]::ToUInt64($stateRecordBytes, 0x60)

$projectorWriteClusterPattern = '44 89 81 D4 00 00 00 48 8B 02 F3 0F 10 40 28 F3 0F 11 81 B8 00 00 00 F3 0F 11 81 BC 00 00 00 F3 0F 11 81 C0 00 00 00 F3 0F 11 81 D0 00 00 00 C3'
$projectorFunctionDelta = 0x0B
$projectorScan = Invoke-ReaderJson -Arguments @(
    '--process-name', 'rift_x64',
    '--scan-module-pattern', $projectorWriteClusterPattern,
    '--scan-module-name', 'rift_x64.exe',
    '--json')

if ($projectorScan.Found -ne $true -or [string]::IsNullOrWhiteSpace([string]$projectorScan.Address)) {
    throw 'Unable to find the projector pattern in rift_x64.exe.'
}

$projectorAddress = (Parse-HexUInt64 -Value ([string]$projectorScan.Address)) - [UInt64]$projectorFunctionDelta
$attempts = New-Object System.Collections.Generic.List[object]

for ($attemptIndex = 1; $attemptIndex -le $RepeatCount; $attemptIndex++) {
    if (Test-Path -LiteralPath $resolvedStatusFile) {
        Remove-Item -LiteralPath $resolvedStatusFile -Force
    }

    & $ceExecScript -LuaFile $projectorLuaFile | Out-Null

    $luaCode = @"
return RiftReaderProjectorTrace.armAsync('rift_x64', $projectorAddress, [[$resolvedStatusFile]])
"@
    & $ceExecScript -Code $luaCode | Out-Null

    Start-Sleep -Milliseconds 250
    & $postKeyScript -Key 'w' -HoldMilliseconds $MoveHoldMilliseconds | Out-Null

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    $status = $null
    while ([DateTime]::UtcNow -lt $deadline) {
        if (Test-Path -LiteralPath $resolvedStatusFile) {
            $status = Read-KeyValueFile -Path $resolvedStatusFile
            if ($status.status -eq 'hit' -or $status.status -eq 'error') {
                break
            }
        }

        Start-Sleep -Milliseconds 200
    }

    if ($null -eq $status) {
        $attempts.Add([ordered]@{
            Attempt = $attemptIndex
            Status = 'timeout'
        })
        continue
    }

    if ($status.status -ne 'hit') {
        $attempts.Add([ordered]@{
            Attempt = $attemptIndex
            Status = [string]$status.status
        })
        continue
    }

    $targetObjectAddress = Try-ParseUInt64Hex ([string]$status.targetObjectAddress)
    $sourceArgumentAddress = Try-ParseUInt64Hex ([string]$status.sourceArgumentAddress)
    $sourceNodeAddress = Try-ParseUInt64Hex ([string]$status.sourceNodeAddress)
    $postTargetSnapshot = if ($null -ne $targetObjectAddress) { Read-FloatObjectSnapshot -Address $targetObjectAddress } else { $null }

    $attempts.Add([ordered]@{
        Attempt = $attemptIndex
        Status = [string]$status.status
        InstructionAddress = [string]$status.rip
        InstructionSymbol = [string]$status.instructionSymbol
        Instruction = [string]$status.instruction
        TargetObjectAddress = if ($null -ne $targetObjectAddress) { ('0x{0:X}' -f $targetObjectAddress) } else { $null }
        TargetMatchesOwnerState = ($null -ne $targetObjectAddress) -and ($targetObjectAddress -eq $stateRecordAddress)
        SourceArgumentAddress = if ($null -ne $sourceArgumentAddress) { ('0x{0:X}' -f $sourceArgumentAddress) } else { $null }
        SourceArgumentMatchesState50 = ($null -ne $sourceArgumentAddress) -and ($sourceArgumentAddress -eq $stateSlot50)
        SourceArgumentMatchesState58 = ($null -ne $sourceArgumentAddress) -and ($sourceArgumentAddress -eq $stateSlot58)
        SourceArgumentMatchesState60 = ($null -ne $sourceArgumentAddress) -and ($sourceArgumentAddress -eq $stateSlot60)
        SourceNodeAddress = if ($null -ne $sourceNodeAddress) { ('0x{0:X}' -f $sourceNodeAddress) } else { $null }
        SourceFloat28 = Try-ParseDouble ([string]$status.sourceFloat28)
        TargetBefore = [ordered]@{
            B8 = Try-ParseDouble ([string]$status.targetB8Before)
            BC = Try-ParseDouble ([string]$status.targetBCBefore)
            C0 = Try-ParseDouble ([string]$status.targetC0Before)
            D0 = Try-ParseDouble ([string]$status.targetD0Before)
            D4 = Try-ParseInt32 ([string]$status.targetD4Before)
        }
        TargetAfter = $postTargetSnapshot
        Registers = [ordered]@{
            RCX = [string]$status.rcx
            RDX = [string]$status.rdx
            RAX = [string]$status.rax
            RSI = [string]$status.rsi
            RDI = [string]$status.rdi
            RBP = [string]$status.rbp
        }
    })

    Start-Sleep -Milliseconds 200
}

$successfulAttempts = @($attempts | Where-Object { $_.Status -eq 'hit' })
$targetMatches = @($successfulAttempts | Where-Object { $_.TargetMatchesOwnerState })
$source50Matches = @($successfulAttempts | Where-Object { $_.SourceArgumentMatchesState50 })
$source58Matches = @($successfulAttempts | Where-Object { $_.SourceArgumentMatchesState58 })
$source60Matches = @($successfulAttempts | Where-Object { $_.SourceArgumentMatchesState60 })
$attemptArray = @($attempts.ToArray())

$result = @{
    Mode = 'player-state-projector-trace'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    OwnerGraphFile = $resolvedOwnerGraphFile
    ProjectorWriteClusterPattern = $projectorWriteClusterPattern
    ProjectorFunctionDelta = ('0x{0:X}' -f $projectorFunctionDelta)
    ProjectorPatternScan = $projectorScan
    ProjectorFunctionAddress = ('0x{0:X}' -f $projectorAddress)
    Owner = [ordered]@{
        Address = ('0x{0:X}' -f $ownerAddress)
        SelectedSourceAddress = $selectedSourceAddress
        StateRecordAddress = ('0x{0:X}' -f $stateRecordAddress)
        StateSlot50 = ('0x{0:X}' -f $stateSlot50)
        StateSlot58 = ('0x{0:X}' -f $stateSlot58)
        StateSlot60 = ('0x{0:X}' -f $stateSlot60)
    }
    AttemptCount = $attempts.Count
    SuccessfulAttemptCount = $successfulAttempts.Count
    StableTargetMatchCount = $targetMatches.Count
    StableState50SourceCount = $source50Matches.Count
    StableState58SourceCount = $source58Matches.Count
    StableState60SourceCount = $source60Matches.Count
    Attempts = $attemptArray
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
    Write-Host "State-projector trace: $resolvedOutputFile"
    Write-Host "Projector write block: $($projectorScan.Address) [$($projectorScan.RelativeOffsetHex)]"
    Write-Host "Projector function:    0x$('{0:X}' -f $projectorAddress)"
    Write-Host "Owner state record:    0x$('{0:X}' -f $stateRecordAddress)"
    Write-Host "State slot +0x50:      0x$('{0:X}' -f $stateSlot50)"
    Write-Host "State slot +0x58:      0x$('{0:X}' -f $stateSlot58)"
    Write-Host "State slot +0x60:      0x$('{0:X}' -f $stateSlot60)"
    Write-Host "Successful attempts:   $($successfulAttempts.Count)/$($attempts.Count)"
    Write-Host "Target = owner+0xC8:   $($targetMatches.Count)"
    Write-Host "Source = state+0x50:   $($source50Matches.Count)"
    Write-Host "Source = state+0x58:   $($source58Matches.Count)"
    Write-Host "Source = state+0x60:   $($source60Matches.Count)"
}
