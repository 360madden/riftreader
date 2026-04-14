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
$projectorLuaFile = Join-Path $PSScriptRoot 'cheat-engine\RiftReaderProjectorTrace.lua'
$ceExecScript = Join-Path $PSScriptRoot 'cheatengine-exec.ps1'
$sendKeyScript = Join-Path $PSScriptRoot 'send-rift-key.ps1'
$rmbCameraScript = Join-Path $PSScriptRoot 'test-rmb-camera.ps1'
$resolvedSourceChainFile = [System.IO.Path]::GetFullPath($SourceChainFile)
$resolvedCoordTraceFile = [System.IO.Path]::GetFullPath($CoordTraceFile)
$resolvedOutputFile = [System.IO.Path]::GetFullPath($OutputFile)
$resolvedStatusFile = [System.IO.Path]::GetFullPath($StatusFile)
$resolvedCoordAnchorStatusFile = [System.IO.Path]::ChangeExtension($resolvedStatusFile, '.coord-anchor.txt')

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

function Get-ObjectValue {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Object,

        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $null
    }

    return $property.Value
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

function Convert-HexToBytes {
    param(
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

function Read-BytesByPid {
    param(
        [Parameter(Mandatory = $true)]
        [int]$ProcessId,

        [Parameter(Mandatory = $true)]
        [UInt64]$Address,

        [Parameter(Mandatory = $true)]
        [int]$Length
    )

    $result = Invoke-ReaderJson -Arguments @(
        '--pid', $ProcessId.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '--address', ('0x{0:X}' -f $Address),
        '--length', $Length.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '--json')

    return Convert-HexToBytes -Hex ([string]$result.BytesHex)
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

function Read-SingleAt {
    param(
        [Parameter(Mandatory = $true)]
        [byte[]]$Bytes,

        [Parameter(Mandatory = $true)]
        [int]$Offset
    )

    if (($Offset + 4) -gt $Bytes.Length) {
        return $null
    }

    $value = [double][BitConverter]::ToSingle($Bytes, $Offset)
    if ([double]::IsNaN($value) -or [double]::IsInfinity($value)) {
        return $null
    }

    return $value
}

function Read-CoordTripletAt {
    param(
        [Parameter(Mandatory = $true)]
        [byte[]]$Bytes,

        [Parameter(Mandatory = $true)]
        [int]$Offset
    )

    return [ordered]@{
        X = Read-SingleAt -Bytes $Bytes -Offset $Offset
        Y = Read-SingleAt -Bytes $Bytes -Offset ($Offset + 4)
        Z = Read-SingleAt -Bytes $Bytes -Offset ($Offset + 8)
    }
}

function Get-QwordContextEntries {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Hit
    )

    $context = Get-ObjectValue -Object $Hit -Name 'Context'
    if ($null -eq $context) {
        return @()
    }

    $windowStartText = [string](Get-ObjectValue -Object $context -Name 'WindowStart')
    $bytesHex = [string](Get-ObjectValue -Object $context -Name 'BytesHex')
    if ([string]::IsNullOrWhiteSpace($windowStartText) -or [string]::IsNullOrWhiteSpace($bytesHex)) {
        return @()
    }

    $windowStart = Parse-HexUInt64 -Value $windowStartText
    $bytes = Convert-HexToBytes -Hex $bytesHex
    if ($bytes.Length -lt 8) {
        return @()
    }

    $entries = New-Object System.Collections.Generic.List[object]
    for ($offset = 0; ($offset + 8) -le $bytes.Length; $offset += 8) {
        $slotAddress = $windowStart + [UInt64]$offset
        $value = [BitConverter]::ToUInt64($bytes, $offset)
        $entries.Add([pscustomobject]@{
                SlotAddress = $slotAddress
                SlotAddressHex = ('0x{0:X}' -f $slotAddress)
                Value = $value
                ValueHex = ('0x{0:X}' -f $value)
            }) | Out-Null
    }

    return $entries.ToArray()
}

function Find-ContainerCandidateFromPointerHits {
    param(
        [Parameter(Mandatory = $true)]
        [UInt64]$SelectedSourceAddress,

        [Parameter(Mandatory = $true)]
        [pscustomobject]$PointerScan
    )

    $regionMask = [UInt64]::Parse('FFFFFFFFFFFF0000', [System.Globalization.NumberStyles]::HexNumber, [System.Globalization.CultureInfo]::InvariantCulture)
    $selectedRegionKey = $SelectedSourceAddress -band $regionMask
    $bestCandidate = $null
    $minimumPointerValue = [UInt64]0x10000

    foreach ($hit in @($PointerScan.Hits)) {
        $entries = @(Get-QwordContextEntries -Hit $hit)
        if ($entries.Count -eq 0) {
            continue
        }

        for ($index = 0; $index -lt $entries.Count; $index++) {
            if ([UInt64]$entries[$index].Value -ne $SelectedSourceAddress) {
                continue
            }

            $startIndex = $index
            while ($startIndex -gt 0 -and [UInt64]$entries[$startIndex - 1].Value -ge $minimumPointerValue) {
                $startIndex--
            }

            $endIndex = $index
            while (($endIndex + 1) -lt $entries.Count -and [UInt64]$entries[$endIndex + 1].Value -ge $minimumPointerValue) {
                $endIndex++
            }

            $sameRegionCount = 0
            for ($entryIndex = $startIndex; $entryIndex -le $endIndex; $entryIndex++) {
                $entryValue = [UInt64]$entries[$entryIndex].Value
                if ($entryValue -ne 0 -and (($entryValue -band $regionMask) -eq $selectedRegionKey)) {
                    $sameRegionCount++
                }
            }

            $candidate = [pscustomobject]@{
                ContainerBase = [UInt64]$entries[$startIndex].SlotAddress
                ContainerBaseHex = [string]$entries[$startIndex].SlotAddressHex
                SelectedSlotAddress = [UInt64]$entries[$index].SlotAddress
                SelectedSlotAddressHex = [string]$entries[$index].SlotAddressHex
                SelectorIndex = [int]((([Int64]$entries[$index].SlotAddress) - ([Int64]$entries[$startIndex].SlotAddress)) / 8)
                SameRegionCount = $sameRegionCount
                ContiguousCount = ($endIndex - $startIndex + 1)
                PointerHitAddress = Parse-HexUInt64 -Value ([string]$hit.AddressHex)
                PointerHitAddressHex = [string]$hit.AddressHex
            }

            if ($null -eq $bestCandidate -or
                $candidate.SameRegionCount -gt $bestCandidate.SameRegionCount -or
                ($candidate.SameRegionCount -eq $bestCandidate.SameRegionCount -and $candidate.ContiguousCount -gt $bestCandidate.ContiguousCount)) {
                $bestCandidate = $candidate
            }
        }
    }

    return $bestCandidate
}

function Find-OwnerCandidateFromContainer {
    param(
        [Parameter(Mandatory = $true)]
        [int]$ProcessId,

        [Parameter(Mandatory = $true)]
        [UInt64]$ContainerBase
    )

    $containerBaseHex = ('0x{0:X}' -f $ContainerBase)
    $pointerScan = Invoke-ReaderJson -Arguments @(
        '--process-name', 'rift_x64',
        '--scan-pointer', $containerBaseHex,
        '--pointer-width', '8',
        '--scan-context', '48',
        '--max-hits', '32',
        '--json')

    foreach ($hit in @($pointerScan.Hits)) {
        $slotAddress = Parse-HexUInt64 -Value ([string]$hit.AddressHex)
        if ($slotAddress -lt 0x78) {
            continue
        }

        $ownerAddress = [UInt64](([Int64]$slotAddress) - 0x78)
        $ownerBytes = Read-BytesByPid -ProcessId $ProcessId -Address $ownerAddress -Length 0x100
        if ($ownerBytes.Length -lt 0x80) {
            continue
        }

        $containerAt78 = Read-UInt64At -Bytes $ownerBytes -Offset 0x78
        if ($null -eq $containerAt78 -or $containerAt78 -ne $ContainerBase) {
            continue
        }

        return [pscustomobject]@{
            OwnerAddress = $ownerAddress
            OwnerAddressHex = ('0x{0:X}' -f $ownerAddress)
            OwnerPointerHitAddress = $slotAddress
            OwnerPointerHitAddressHex = [string]$hit.AddressHex
            ContainerAddress = $containerAt78
            ContainerAddressHex = ('0x{0:X}' -f $containerAt78)
        }
    }

    return $null
}

function Invoke-CameraDrivenSelectorOwnerFallback {
    param(
        [Parameter(Mandatory = $true)]
        [pscustomobject]$SelectorPatternScanResult,

        [Parameter(Mandatory = $true)]
        [string]$SelectorPatternText
    )

    $coordAnchorPattern = 'F3 0F 10 86 5C 01 00 00'
    $coordAnchorScan = Invoke-ReaderJson -Arguments @(
        '--process-name', 'rift_x64',
        '--scan-module-pattern', $coordAnchorPattern,
        '--scan-module-name', 'rift_x64.exe',
        '--json')

    if ($coordAnchorScan.Found -ne $true -or [string]::IsNullOrWhiteSpace([string]$coordAnchorScan.Address)) {
        throw 'Camera fallback could not find the live coord-anchor pattern.'
    }

    if (Test-Path -LiteralPath $resolvedCoordAnchorStatusFile) {
        Remove-Item -LiteralPath $resolvedCoordAnchorStatusFile -Force
    }

    $coordAnchorAddress = Parse-HexUInt64 -Value ([string]$coordAnchorScan.Address)
    & $ceExecScript -LuaFile $projectorLuaFile | Out-Null

    $luaCode = @"
return RiftReaderProjectorTrace.armAsync('rift_x64', $coordAnchorAddress, [[$resolvedCoordAnchorStatusFile]])
"@
    & $ceExecScript -Code $luaCode | Out-Null

    Start-Sleep -Milliseconds 200
    & $rmbCameraScript | Out-Null

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    $coordAnchorStatus = $null
    while ([DateTime]::UtcNow -lt $deadline) {
        if (Test-Path -LiteralPath $resolvedCoordAnchorStatusFile) {
            $coordAnchorStatus = Read-KeyValueFile -Path $resolvedCoordAnchorStatusFile
            if ($coordAnchorStatus.status -eq 'hit' -or $coordAnchorStatus.status -eq 'error') {
                break
            }
        }

        Start-Sleep -Milliseconds 150
    }

    if ($null -eq $coordAnchorStatus -or $coordAnchorStatus.status -ne 'hit') {
        $statusText = if ($coordAnchorStatus) { [string]$coordAnchorStatus.status } else { 'timeout' }
        throw "Camera fallback coord-anchor trace did not hit (status=$statusText)."
    }

    $riftProcess = Get-Process -Name 'rift_x64' -ErrorAction Stop |
        Where-Object { $_.MainWindowHandle -ne 0 } |
        Select-Object -First 1
    if (-not $riftProcess) {
        throw "No windowed rift_x64 process found for camera fallback."
    }

    $selectedSourceAddress = Try-ParseUInt64Hex ([string]$coordAnchorStatus.rdi)
    if ($null -eq $selectedSourceAddress -or $selectedSourceAddress -eq 0) {
        throw 'Camera fallback did not capture a live selected-source address from RDI.'
    }

    $selectedSourceBytes = Read-BytesByPid -ProcessId $riftProcess.Id -Address $selectedSourceAddress -Length 0xA0
    if ($selectedSourceBytes.Length -lt 0xA0) {
        throw ('Camera fallback could not read the selected source at 0x{0:X}.' -f $selectedSourceAddress)
    }

    $pointerScan = Invoke-ReaderJson -Arguments @(
        '--process-name', 'rift_x64',
        '--scan-pointer', ('0x{0:X}' -f $selectedSourceAddress),
        '--pointer-width', '8',
        '--scan-context', '64',
        '--max-hits', '64',
        '--json')

    $containerCandidate = Find-ContainerCandidateFromPointerHits -SelectedSourceAddress $selectedSourceAddress -PointerScan $pointerScan
    if ($null -eq $containerCandidate) {
        throw ('Camera fallback could not identify a container window that referenced selected source 0x{0:X}.' -f $selectedSourceAddress)
    }

    $ownerCandidate = Find-OwnerCandidateFromContainer -ProcessId $riftProcess.Id -ContainerBase $containerCandidate.ContainerBase
    if ($null -eq $ownerCandidate) {
        throw ('Camera fallback could not find an owner object whose +0x78 pointed to container 0x{0:X}.' -f $containerCandidate.ContainerBase)
    }

    $coordTrace = $null
    if (Test-Path -LiteralPath $resolvedCoordTraceFile) {
        $coordTrace = Get-Content -LiteralPath $resolvedCoordTraceFile -Raw | ConvertFrom-Json -Depth 30
    }

    $coordTraceSourceAddress = [string]$coordTrace.Trace.Registers.RDI
    $selectedSourceAddressHex = ('0x{0:X}' -f $selectedSourceAddress)
    $selectedSourceMatchesCoordTrace = -not [string]::IsNullOrWhiteSpace($coordTraceSourceAddress) -and
        ($coordTraceSourceAddress -eq $selectedSourceAddressHex)

    $selectedSourceCoord48 = Read-CoordTripletAt -Bytes $selectedSourceBytes -Offset 0x48
    $selectedSourceCoord88 = Read-CoordTripletAt -Bytes $selectedSourceBytes -Offset 0x88

    return [ordered]@{
        Mode = 'player-selector-owner-trace'
        GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
        SourceChainFile = $resolvedSourceChainFile
        CoordTraceFile = if (Test-Path -LiteralPath $resolvedCoordTraceFile) { $resolvedCoordTraceFile } else { $null }
        TriggerInstruction = [ordered]@{
            Address = ('0x{0:X}' -f $coordAnchorAddress)
            Opcode = 'movss xmm0,[rsi+0000015C]'
            Full = 'camera-driven coord-anchor fallback'
        }
        ArmedInstructionAddress = ('0x{0:X}' -f $coordAnchorAddress)
        RecoveryMode = 'camera-coord-anchor'
        Trace = [ordered]@{
            Status = [string]$coordAnchorStatus.status
            HitCount = Try-ParseInt32 ([string]$coordAnchorStatus.hitCount)
            InstructionAddress = [string]$coordAnchorStatus.rip
            InstructionSymbol = [string]$coordAnchorStatus.instructionSymbol
            Instruction = [string]$coordAnchorStatus.instruction
            InstructionBytes = [string]$coordAnchorStatus.instructionBytes
            InstructionOpcode = [string]$coordAnchorStatus.instructionOpcode
            ModuleName = [string]$coordAnchorStatus.moduleName
            ModuleBase = [string]$coordAnchorStatus.moduleBase
            ModuleOffset = [string]$coordAnchorStatus.moduleOffset
            Registers = [ordered]@{
                RAX = [string]$coordAnchorStatus.rax
                RBX = [string]$coordAnchorStatus.rbx
                RCX = [string]$coordAnchorStatus.rcx
                RDX = [string]$coordAnchorStatus.rdx
                RSI = [string]$coordAnchorStatus.rsi
                RDI = [string]$coordAnchorStatus.rdi
                RBP = [string]$coordAnchorStatus.rbp
                RSP = [string]$coordAnchorStatus.rsp
                R8 = [string]$coordAnchorStatus.r8
                R9 = [string]$coordAnchorStatus.r9
                R10 = [string]$coordAnchorStatus.r10
                R11 = [string]$coordAnchorStatus.r11
                R12 = [string]$coordAnchorStatus.r12
                R13 = [string]$coordAnchorStatus.r13
                R14 = [string]$coordAnchorStatus.r14
                R15 = [string]$coordAnchorStatus.r15
            }
        }
        Owner = [ordered]@{
            SlotAddress = $null
            ObjectAddress = $ownerCandidate.OwnerAddressHex
            ContainerAddress = $ownerCandidate.ContainerAddressHex
            ContainerFromObject = $ownerCandidate.ContainerAddressHex
            ContainerMatchesObject78 = $true
            SelectorIndex = $containerCandidate.SelectorIndex
            Coord48 = [ordered]@{
                X = $null
                Y = $null
                Z = $null
            }
        }
        SelectedSource = [ordered]@{
            Address = $selectedSourceAddressHex
            MatchesCoordTraceSource = $selectedSourceMatchesCoordTrace
            Coord48 = $selectedSourceCoord48
            Coord88 = $selectedSourceCoord88
        }
        CoordTraceSourceAddress = $coordTraceSourceAddress
        SuggestedSelectorPattern = $SelectorPatternText
        SuggestedSelectorPatternScan = $SelectorPatternScanResult
        Recovery = [ordered]@{
            CoordAnchorPattern = $coordAnchorPattern
            CoordAnchorPatternScan = $coordAnchorScan
            CoordAnchorStatusFile = $resolvedCoordAnchorStatusFile
            PointerHitAddress = $containerCandidate.PointerHitAddressHex
            ContainerBaseAddress = $containerCandidate.ContainerBaseHex
            SelectedSourceSlotAddress = $containerCandidate.SelectedSlotAddressHex
            OwnerPointerHitAddress = $ownerCandidate.OwnerPointerHitAddressHex
        }
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

$result = $null
if ($null -eq $status -or $status.status -ne 'hit') {
    try {
        $result = Invoke-CameraDrivenSelectorOwnerFallback -SelectorPatternScanResult $selectorPatternScan -SelectorPatternText $selectorPattern
    }
    catch {
        $fallbackDetail = $_.Exception.Message
        if ($_.InvocationInfo -and $_.InvocationInfo.ScriptLineNumber) {
            $fallbackDetail = "$fallbackDetail [line $($_.InvocationInfo.ScriptLineNumber)]"
        }

        $primaryFailure = if ($null -eq $status) {
            if ($producedStatusFile) {
                "Selector-owner trace did not produce a terminal hit/error status after $MaxArmAttempts arm attempt(s)."
            }
            else {
                "Selector-owner trace timed out without producing '$resolvedStatusFile' after $MaxArmAttempts arm attempt(s)."
            }
        }
        elseif ($producedStatusFile) {
            "Selector-owner trace failed with status '$($status.status)' after $MaxArmAttempts arm attempt(s)."
        }
        else {
            "Selector-owner trace did not produce a hit after $MaxArmAttempts arm attempt(s)."
        }

        throw "$primaryFailure Camera fallback also failed: $fallbackDetail"
    }
}
else {
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
    if ($result.RecoveryMode) {
        Write-Host "Recovery mode:         $($result.RecoveryMode)"
    }
    Write-Host "Owner object:          $($result.Owner.ObjectAddress)"
    Write-Host "Owner container:       $($result.Owner.ContainerAddress)"
    Write-Host "Selector index:        $($result.Owner.SelectorIndex)"
    Write-Host "Selected source:       $($result.SelectedSource.Address)"
    Write-Host "Selected = coord trace: $($result.SelectedSource.MatchesCoordTraceSource)"
    Write-Host ("Selected +0x48:        {0}, {1}, {2}" -f $result.SelectedSource.Coord48.X, $result.SelectedSource.Coord48.Y, $result.SelectedSource.Coord48.Z)
    Write-Host ("Selected +0x88:        {0}, {1}, {2}" -f $result.SelectedSource.Coord88.X, $result.SelectedSource.Coord88.Y, $result.SelectedSource.Coord88.Z)
    if ($selectorPatternScan.Found -eq $true) {
        Write-Host "Selector pattern:      $($selectorPatternScan.Address) [$($selectorPatternScan.RelativeOffsetHex)]"
    }
}
