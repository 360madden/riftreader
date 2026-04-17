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
$postKeyScript = Join-Path $PSScriptRoot 'post-rift-key.ps1'
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

function Normalize-RegisterName {
    param([string]$Name)

    if ([string]::IsNullOrWhiteSpace($Name)) {
        return $null
    }

    return $Name.Trim().ToUpperInvariant()
}

function ConvertTo-LuaLiteral {
    param($Value)

    if ($null -eq $Value) {
        return 'nil'
    }

    if ($Value -is [bool]) {
        return $Value.ToString().ToLowerInvariant()
    }

    if ($Value -is [byte] -or $Value -is [sbyte] -or $Value -is [short] -or $Value -is [ushort] -or
        $Value -is [int] -or $Value -is [uint32] -or $Value -is [long] -or $Value -is [uint64]) {
        return ([System.Convert]::ToString($Value, [System.Globalization.CultureInfo]::InvariantCulture))
    }

    if ($Value -is [float] -or $Value -is [double] -or $Value -is [decimal]) {
        return ([string]::Format([System.Globalization.CultureInfo]::InvariantCulture, '{0}', $Value))
    }

    $text = [string]$Value
    $text = $text.Replace('\', '\\').Replace("'", "\'")
    return "'" + $text + "'"
}

function ConvertTo-LuaTable {
    param(
        [Parameter(Mandatory = $true)]
        [System.Collections.IDictionary]$Table
    )

    $pairs = foreach ($property in $Table.GetEnumerator()) {
        "{0} = {1}" -f $property.Key, (ConvertTo-LuaLiteral -Value $property.Value)
    }

    return '{ ' + ($pairs -join ', ') + ' }'
}

function Get-ConfigurationValue {
    param(
        [Parameter(Mandatory = $true)]
        $Configuration,

        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    if ($null -eq $Configuration -or -not $Configuration.PSObject.Properties[$Name]) {
        return $null
    }

    return $Configuration.$Name
}

function Get-CoordTraceSelectedSourceAddress {
    param(
        $CoordTrace,
        [string]$PreferredRegister
    )

    if ($null -eq $CoordTrace) {
        return $null
    }

    if ($CoordTrace.PSObject.Properties['SourceObjectRegisterValue'] -and -not [string]::IsNullOrWhiteSpace([string]$CoordTrace.SourceObjectRegisterValue)) {
        return [string]$CoordTrace.SourceObjectRegisterValue
    }

    if ($CoordTrace.PSObject.Properties['Trace'] -and $CoordTrace.Trace -and $CoordTrace.Trace.PSObject.Properties['Registers']) {
        $registers = $CoordTrace.Trace.Registers
        $normalizedPreferredRegister = Normalize-RegisterName -Name $PreferredRegister
        if (-not [string]::IsNullOrWhiteSpace($normalizedPreferredRegister) -and $registers.PSObject.Properties[$normalizedPreferredRegister]) {
            $value = [string]$registers.$normalizedPreferredRegister
            if (-not [string]::IsNullOrWhiteSpace($value)) {
                return $value
            }
        }

        if ($registers.PSObject.Properties['RDI']) {
            $value = [string]$registers.RDI
            if (-not [string]::IsNullOrWhiteSpace($value)) {
                return $value
            }
        }
    }

    return $null
}

if ($RefreshSourceChain -or -not (Test-Path -LiteralPath $resolvedSourceChainFile)) {
    & $sourceChainScript -Json | Out-Null
}

if (-not (Test-Path -LiteralPath $resolvedSourceChainFile)) {
    throw "Player source-chain file not found: $resolvedSourceChainFile"
}

$sourceChain = Get-Content -LiteralPath $resolvedSourceChainFile -Raw | ConvertFrom-Json -Depth 30
$traceConfiguration = $sourceChain.TraceConfiguration
$triggerInstruction = if ($sourceChain.TriggerInstruction) { $sourceChain.TriggerInstruction } else { $sourceChain.SourceChain.SourceObjectLoad }
if ($null -eq $triggerInstruction -or [string]::IsNullOrWhiteSpace([string]$triggerInstruction.Address)) {
    throw 'Source-chain file did not contain a valid trigger instruction.'
}

$selectorPattern = [string]$sourceChain.SuggestedSelectorPattern
$selectorPatternScan = $null
if (-not [string]::IsNullOrWhiteSpace($selectorPattern)) {
    try {
        $selectorPatternScan = Invoke-ReaderJson -Arguments @(
            '--process-name', 'rift_x64',
            '--scan-module-pattern', $selectorPattern,
            '--scan-module-name', 'rift_x64.exe',
            '--json')
    }
    catch {
        $selectorPatternScan = [pscustomobject]@{
            Mode = 'module-pattern-scan'
            Error = $_.Exception.Message
        }
    }
}

$luaConfiguration = [ordered]@{
    ownerObjectRegister = Normalize-RegisterName -Name ([string](Get-ConfigurationValue -Configuration $traceConfiguration -Name 'OwnerObjectRegister'))
    ownerContainerRegister = Normalize-RegisterName -Name ([string](Get-ConfigurationValue -Configuration $traceConfiguration -Name 'OwnerContainerRegister'))
    selectorIndexRegister = Normalize-RegisterName -Name ([string](Get-ConfigurationValue -Configuration $traceConfiguration -Name 'SelectorIndexRegister'))
    selectedSourceRegister = Normalize-RegisterName -Name ([string](Get-ConfigurationValue -Configuration $traceConfiguration -Name 'SelectedSourceRegister'))
    selectorScale = Try-ParseInt32 ([string](Get-ConfigurationValue -Configuration $traceConfiguration -Name 'SelectorScale'))
    selectorDisplacement = Try-ParseInt32 ([string](Get-ConfigurationValue -Configuration $traceConfiguration -Name 'SelectorDisplacement'))
    ownerContainerDisplacement = Try-ParseInt32 ([string](Get-ConfigurationValue -Configuration $traceConfiguration -Name 'OwnerContainerDisplacement'))
    ownerSlotBaseRegister = Normalize-RegisterName -Name ([string](Get-ConfigurationValue -Configuration $traceConfiguration -Name 'OwnerSlotBaseRegister'))
    ownerSlotDisplacement = Try-ParseInt32 ([string](Get-ConfigurationValue -Configuration $traceConfiguration -Name 'OwnerSlotDisplacement'))
    sourceCoord48Offset = Try-ParseInt32 ([string](Get-ConfigurationValue -Configuration $traceConfiguration -Name 'SourceCoord48Offset'))
    sourceCoord88Offset = Try-ParseInt32 ([string](Get-ConfigurationValue -Configuration $traceConfiguration -Name 'SourceCoord88Offset'))
}

if ($null -eq $luaConfiguration.selectorScale) {
    $luaConfiguration.selectorScale = 8
}

if ($null -eq $luaConfiguration.selectorDisplacement) {
    $luaConfiguration.selectorDisplacement = 0
}

if ($null -eq $luaConfiguration.sourceCoord48Offset) {
    $luaConfiguration.sourceCoord48Offset = 0x48
}

if ($null -eq $luaConfiguration.sourceCoord88Offset) {
    $luaConfiguration.sourceCoord88Offset = 0x88
}

$luaConfigurationLiteral = ConvertTo-LuaTable -Table $luaConfiguration
$triggerAddress = Parse-HexUInt64 -Value ([string]$triggerInstruction.Address)
$status = $null
$producedStatusFile = $false
$movementSequence = @($MovementKeys | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -Unique)

for ($armAttempt = 1; $armAttempt -le $MaxArmAttempts; $armAttempt++) {
    if (Test-Path -LiteralPath $resolvedStatusFile) {
        Remove-Item -LiteralPath $resolvedStatusFile -Force
    }

    & $ceExecScript -LuaFile $selectorLuaFile | Out-Null

    $luaCode = @"
return RiftReaderSelectorTrace.arm('rift_x64', $triggerAddress, [[$resolvedStatusFile]], $luaConfigurationLiteral)
"@
    & $ceExecScript -Code $luaCode | Out-Null

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    $status = $null
    foreach ($movementKey in $movementSequence) {
        if ([DateTime]::UtcNow -ge $deadline) {
            break
        }

        try {
            & $postKeyScript -Key $movementKey -HoldMilliseconds $MovementHoldMilliseconds | Out-Null
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
$coordTraceSourceAddress = Get-CoordTraceSelectedSourceAddress -CoordTrace $coordTrace -PreferredRegister ([string]$status.selectedSourceRegister)
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
    TraceConfiguration = [ordered]@{
        OwnerObjectRegister = [string]$status.ownerObjectRegister
        OwnerContainerRegister = [string]$status.ownerContainerRegister
        SelectorIndexRegister = [string]$status.selectorIndexRegister
        SelectedSourceRegister = [string]$status.selectedSourceRegister
        SelectorScale = Try-ParseInt32 ([string]$status.selectorScale)
        SelectorDisplacement = Try-ParseInt32 ([string]$status.selectorDisplacement)
        OwnerContainerDisplacement = Try-ParseInt32 ([string]$status.ownerContainerDisplacement)
        OwnerSlotBaseRegister = [string]$status.ownerSlotBaseRegister
        OwnerSlotDisplacement = Try-ParseInt32 ([string]$status.ownerSlotDisplacement)
        SourceCoord48Offset = Try-ParseInt32 ([string]$status.sourceCoord48Offset)
        SourceCoord88Offset = Try-ParseInt32 ([string]$status.sourceCoord88Offset)
        SelectedSourceComputation = [string]$status.selectedSourceComputation
    }
    Trace = [ordered]@{
        Status = [string]$status.status
        Stage = [string]$status.stage
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
        ObjectAddressSource = [string]$status.ownerObjectSource
        ContainerAddress = [string]$status.ownerContainerAddress
        ContainerFromObject = [string]$status.ownerContainerFromObject
        ContainerMatchesObject78 = ([string]$status.ownerContainerMatchesObject78) -eq 'true'
        SelectorIndex = Try-ParseInt32 ([string]$status.selectorIndex)
        Coord48 = $ownerCoord48
    }
    SelectedSource = [ordered]@{
        Address = $selectedSourceAddress
        AddressSource = [string]$status.selectedSourceComputation
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
    if ($selectorPatternScan -and $selectorPatternScan.Found -eq $true) {
        Write-Host "Selector pattern:      $($selectorPatternScan.Address) [$($selectorPatternScan.RelativeOffsetHex)]"
    }
}
