[CmdletBinding()]
param(
    [switch]$Json,
    [switch]$RefreshSourceChain,
    [int]$TimeoutSeconds = 8,
    [int]$MaxArmAttempts = 2,
    [int]$MovementHoldMilliseconds = 750,
    [string[]]$MovementKeys = @('w', 'd', 'a', 's'),
    [string]$SourceChainFile = (Join-Path $PSScriptRoot 'captures\player-source-chain.json'),
    [string]$CoordTraceFile = (Join-Path $PSScriptRoot 'captures\player-coord-write-trace.json'),
    [string]$OutputFile = (Join-Path $PSScriptRoot 'captures\player-selector-owner-trace.json'),
    [string]$StatusFile = (Join-Path $PSScriptRoot 'captures\player-selector-owner-trace.status.txt')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$sourceChainScript = Join-Path $PSScriptRoot 'capture-player-source-chain.ps1'
$selectorLuaFile = Join-Path $PSScriptRoot 'cheat-engine\RiftReaderSelectorTrace.lua'
$ceExecScript = Join-Path $PSScriptRoot 'cheatengine-exec.ps1'
$sendKeyScript = Join-Path $PSScriptRoot 'send-rift-key.ps1'
$resolvedSourceChainFile = [System.IO.Path]::GetFullPath($SourceChainFile)
$resolvedCoordTraceFile = [System.IO.Path]::GetFullPath($CoordTraceFile)
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

function Get-CoordTripletSample {
    param(
        [string]$Prefix
    )

    [ordered]@{
        X = Try-ParseDouble ([string]$status."${Prefix}X")
        Y = Try-ParseDouble ([string]$status."${Prefix}Y")
        Z = Try-ParseDouble ([string]$status."${Prefix}Z")
    }
}

if ($RefreshSourceChain -or -not (Test-Path -LiteralPath $resolvedSourceChainFile)) {
    & $sourceChainScript -Json | Out-Null
}

if (-not (Test-Path -LiteralPath $resolvedSourceChainFile)) {
    throw "Player source-chain file not found: $resolvedSourceChainFile"
}

$sourceChain = Get-Content -LiteralPath $resolvedSourceChainFile -Raw | ConvertFrom-Json -Depth 30
$triggerInstruction = $sourceChain.SourceChain.SourceObjectLoad
if ($null -eq $triggerInstruction -or [string]::IsNullOrWhiteSpace([string]$triggerInstruction.Address)) {
    throw 'Source-chain file did not contain the source-object load instruction.'
}

$selectorPattern = '0F B6 54 01 18 80 FA FF 0F 84 ?? ?? ?? ?? 48 8B 48 78 48 8B 3C D1 48 85 FF'
$selectorPatternScan = Invoke-ReaderJson -Arguments @(
    '--process-name', 'rift_x64',
    '--scan-module-pattern', $selectorPattern,
    '--scan-module-name', 'rift_x64.exe',
    '--json')

$triggerAddress = if ($selectorPatternScan.Found -eq $true -and -not [string]::IsNullOrWhiteSpace([string]$selectorPatternScan.Address)) {
    Parse-HexUInt64 -Value ([string]$selectorPatternScan.Address)
}
else {
    Parse-HexUInt64 -Value ([string]$triggerInstruction.Address)
}
$status = $null
$producedStatusFile = $false
$movementSequence = @($MovementKeys | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -Unique)

for ($armAttempt = 1; $armAttempt -le $MaxArmAttempts; $armAttempt++) {
    if (Test-Path -LiteralPath $resolvedStatusFile) {
        Remove-Item -LiteralPath $resolvedStatusFile -Force
    }

    & $ceExecScript -LuaFile $selectorLuaFile | Out-Null

    $luaCode = @"
return RiftReaderSelectorTrace.arm('rift_x64', $triggerAddress, [[$resolvedStatusFile]], 0x70)
"@
    & $ceExecScript -Code $luaCode | Out-Null

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    $status = $null
    foreach ($movementKey in $movementSequence) {
        if ([DateTime]::UtcNow -ge $deadline) {
            break
        }

        try {
            & $sendKeyScript -ProcessName 'rift_x64' -Key $movementKey -HoldMilliseconds $MovementHoldMilliseconds -NoRefocus | Out-Null
        }
        catch {
        }

        $movementDeadline = [DateTime]::UtcNow.AddMilliseconds([Math]::Min([Math]::Max(($MovementHoldMilliseconds + 400), 600), 1800))
        if ($movementDeadline -gt $deadline) {
            $movementDeadline = $deadline
        }

        while ([DateTime]::UtcNow -lt $movementDeadline) {
            if (Test-Path -LiteralPath $resolvedStatusFile) {
                $producedStatusFile = $true
                $status = Read-KeyValueFile -Path $resolvedStatusFile
                if ($status.status -eq 'hit' -or $status.status -eq 'error') {
                    break
                }
            }

            Start-Sleep -Milliseconds 150
        }

        if ($null -ne $status -and ($status.status -eq 'hit' -or $status.status -eq 'error')) {
            break
        }
    }

    while ([DateTime]::UtcNow -lt $deadline) {
        if (Test-Path -LiteralPath $resolvedStatusFile) {
            $producedStatusFile = $true
            $status = Read-KeyValueFile -Path $resolvedStatusFile
            if ($status.status -eq 'hit' -or $status.status -eq 'error') {
                break
            }
        }

        Start-Sleep -Milliseconds 200
    }

    if ($null -ne $status -and ($status.status -eq 'hit' -or $status.status -eq 'error')) {
        break
    }

    if ($armAttempt -lt $MaxArmAttempts) {
        Start-Sleep -Milliseconds 300
    }
}

if ($null -eq $status) {
    if ($producedStatusFile) {
        throw "Selector-owner trace did not produce a terminal hit/error status after $MaxArmAttempts arm attempt(s)."
    }

    throw "Selector-owner trace timed out without producing '$resolvedStatusFile' after $MaxArmAttempts arm attempt(s)."
}

if ($status.status -ne 'hit') {
    if ($producedStatusFile) {
        throw "Selector-owner trace failed with status '$($status.status)' after $MaxArmAttempts arm attempt(s)."
    }

    throw "Selector-owner trace did not produce a hit after $MaxArmAttempts arm attempt(s)."
}

$coordTrace = $null
if (Test-Path -LiteralPath $resolvedCoordTraceFile) {
    $coordTrace = Get-Content -LiteralPath $resolvedCoordTraceFile -Raw | ConvertFrom-Json -Depth 30
}

$selectedSourceAddress = [string]$status.selectedSourceAddress
$coordTraceSourceAddress = [string]$coordTrace.Trace.Registers.RDI
$selectedSourceMatchesCoordTrace = -not [string]::IsNullOrWhiteSpace($selectedSourceAddress) -and
    -not [string]::IsNullOrWhiteSpace($coordTraceSourceAddress) -and
    ($selectedSourceAddress -eq $coordTraceSourceAddress)

$selectedSourceCoord48 = [ordered]@{
    X = Try-ParseDouble ([string]$status.sourceCoord48X)
    Y = Try-ParseDouble ([string]$status.sourceCoord48Y)
    Z = Try-ParseDouble ([string]$status.sourceCoord48Z)
}
$selectedSourceCoord88 = [ordered]@{
    X = Try-ParseDouble ([string]$status.sourceCoord88X)
    Y = Try-ParseDouble ([string]$status.sourceCoord88Y)
    Z = Try-ParseDouble ([string]$status.sourceCoord88Z)
}
$ownerCoord48 = [ordered]@{
    X = Try-ParseDouble ([string]$status.ownerCoord48X)
    Y = Try-ParseDouble ([string]$status.ownerCoord48Y)
    Z = Try-ParseDouble ([string]$status.ownerCoord48Z)
}

$result = [ordered]@{
    Mode = 'player-selector-owner-trace'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    SourceChainFile = $resolvedSourceChainFile
    CoordTraceFile = if (Test-Path -LiteralPath $resolvedCoordTraceFile) { $resolvedCoordTraceFile } else { $null }
    TriggerInstruction = $triggerInstruction
    ArmedInstructionAddress = ('0x{0:X}' -f $triggerAddress)
    Trace = [ordered]@{
        Status = [string]$status.status
        HitCount = Try-ParseInt32 ([string]$status.hitCount)
        InstructionAddress = [string]$status.rip
        InstructionSymbol = [string]$status.instructionSymbol
        Instruction = [string]$status.instruction
        InstructionBytes = [string]$status.instructionBytes
        InstructionOpcode = [string]$status.instructionOpcode
        ModuleName = [string]$status.moduleName
        ModuleBase = [string]$status.moduleBase
        ModuleOffset = [string]$status.moduleOffset
        Registers = [ordered]@{
            RAX = [string]$status.rax
            RBX = [string]$status.rbx
            RCX = [string]$status.rcx
            RDX = [string]$status.rdx
            RSI = [string]$status.rsi
            RDI = [string]$status.rdi
            RBP = [string]$status.rbp
            RSP = [string]$status.rsp
            R8 = [string]$status.r8
            R9 = [string]$status.r9
            R10 = [string]$status.r10
            R11 = [string]$status.r11
            R12 = [string]$status.r12
            R13 = [string]$status.r13
            R14 = [string]$status.r14
            R15 = [string]$status.r15
        }
    }
    Owner = [ordered]@{
        SlotAddress = [string]$status.ownerSlotAddress
        ObjectAddress = [string]$status.ownerObjectAddress
        ContainerAddress = [string]$status.ownerContainerAddress
        ContainerFromObject = [string]$status.ownerContainerFromObject
        ContainerMatchesObject78 = ([string]$status.ownerContainerMatchesObject78) -eq 'true'
        SelectorIndex = Try-ParseInt32 ([string]$status.selectorIndex)
        Coord48 = $ownerCoord48
    }
    SelectedSource = [ordered]@{
        Address = $selectedSourceAddress
        MatchesCoordTraceSource = $selectedSourceMatchesCoordTrace
        Coord48 = $selectedSourceCoord48
        Coord88 = $selectedSourceCoord88
    }
    CoordTraceSourceAddress = $coordTraceSourceAddress
    SuggestedSelectorPattern = $selectorPattern
    SuggestedSelectorPatternScan = $selectorPatternScan
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
    Write-Host "Selector-owner trace:  $resolvedOutputFile"
    Write-Host "Trigger instruction:   $($triggerInstruction.Address) | $($triggerInstruction.Full)"
    Write-Host "Owner object:          $($result.Owner.ObjectAddress)"
    Write-Host "Owner container:       $($result.Owner.ContainerAddress)"
    Write-Host "Selector index:        $($result.Owner.SelectorIndex)"
    Write-Host "Selected source:       $($result.SelectedSource.Address)"
    Write-Host "Selected = coord trace: $($result.SelectedSource.MatchesCoordTraceSource)"
    Write-Host ("Selected +0x48:        {0}, {1}, {2}" -f $selectedSourceCoord48.X, $selectedSourceCoord48.Y, $selectedSourceCoord48.Z)
    Write-Host ("Selected +0x88:        {0}, {1}, {2}" -f $selectedSourceCoord88.X, $selectedSourceCoord88.Y, $selectedSourceCoord88.Z)
    if ($selectorPatternScan.Found -eq $true) {
        Write-Host "Selector pattern:      $($selectorPatternScan.Address) [$($selectorPatternScan.RelativeOffsetHex)]"
    }
}
