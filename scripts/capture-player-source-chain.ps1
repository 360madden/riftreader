[CmdletBinding()]
param(
    [switch]$Json,
    [switch]$RefreshCluster,
    [string]$ClusterFile = (Join-Path $PSScriptRoot 'captures\player-coord-trace-cluster.json'),
    [string]$OutputFile = (Join-Path $PSScriptRoot 'captures\player-source-chain.json')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$clusterScript = Join-Path $PSScriptRoot 'capture-player-trace-cluster.ps1'
$ceExecScript = Join-Path $PSScriptRoot 'cheatengine-exec.ps1'
$clusterLuaFile = Join-Path $PSScriptRoot 'cheat-engine\RiftReaderDisasmCluster.lua'
$resolvedClusterFile = [System.IO.Path]::GetFullPath($ClusterFile)
$resolvedOutputFile = [System.IO.Path]::GetFullPath($OutputFile)

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

    if ($opcode -like 'call *') {
        if ($parts.Count -eq 5 -and $parts[0] -eq 'E8') {
            return 'E8 ?? ?? ?? ??'
        }
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

function Invoke-DisasmCluster {
    param(
        [Parameter(Mandatory = $true)]
        [UInt64]$Address,

        [Parameter(Mandatory = $true)]
        [string]$OutputPath,

        [int]$Before = 12,
        [int]$After = 12
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

function Normalize-RegisterName {
    param([string]$Name)

    if ([string]::IsNullOrWhiteSpace($Name)) {
        return $null
    }

    return $Name.Trim().ToUpperInvariant()
}

function Convert-HexTokenToInt32 {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    $normalized = $Value.Trim()
    if ($normalized.StartsWith('0x', [System.StringComparison]::OrdinalIgnoreCase)) {
        $normalized = $normalized.Substring(2)
    }

    return [Convert]::ToInt32($normalized, 16)
}

function Get-MemoryOperandText {
    param(
        [Parameter(Mandatory = $true)]
        [pscustomobject]$Instruction
    )

    if ($Instruction.PSObject.Properties['MemoryOperand'] -and -not [string]::IsNullOrWhiteSpace([string]$Instruction.MemoryOperand)) {
        return [string]$Instruction.MemoryOperand
    }

    $candidate = @([string]$Instruction.Opcode, [string]$Instruction.Extra, [string]$Instruction.Full) -join ' '
    $match = [regex]::Match($candidate, '\[[^\]]+\]')
    if ($match.Success) {
        return $match.Value
    }

    return $null
}

function Get-DestinationRegister {
    param(
        [Parameter(Mandatory = $true)]
        [pscustomobject]$Instruction
    )

    $opcode = ([string]$Instruction.Opcode).Trim()
    $match = [regex]::Match($opcode, '^[a-z0-9]+\s+(?<dest>[a-z0-9]+)\s*,', [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
    if (-not $match.Success) {
        return $null
    }

    return Normalize-RegisterName -Name $match.Groups['dest'].Value
}

function Get-RegisterCopySource {
    param(
        [Parameter(Mandatory = $true)]
        [pscustomobject]$Instruction,

        [Parameter(Mandatory = $true)]
        [string]$DestinationRegister
    )

    $opcode = ([string]$Instruction.Opcode).Trim().ToLowerInvariant()
    $pattern = '^(mov|movzx|movsx|movsxd)\s+' + [regex]::Escape($DestinationRegister.ToLowerInvariant()) + '\s*,\s*(?<source>[a-z0-9]+)$'
    $match = [regex]::Match($opcode, $pattern)
    if (-not $match.Success) {
        return $null
    }

    return Normalize-RegisterName -Name $match.Groups['source'].Value
}

function Parse-MemoryOperand {
    param(
        [string]$Operand
    )

    if ([string]::IsNullOrWhiteSpace($Operand)) {
        return $null
    }

    $normalized = $Operand.Trim()
    $normalized = $normalized -replace '(?i)\b(?:byte|word|dword|qword|ptr)\b', ''
    $normalized = $normalized.Replace(' ', '')
    if ($normalized.StartsWith('[') -and $normalized.EndsWith(']')) {
        $normalized = $normalized.Substring(1, $normalized.Length - 2)
    }

    if ([string]::IsNullOrWhiteSpace($normalized)) {
        return $null
    }

    $baseRegister = $null
    $indexRegister = $null
    $scale = 1
    $displacement = 0
    $registerTerms = New-Object System.Collections.Generic.List[string]

    $terms = [regex]::Matches($normalized, '[+-]?[^+-]+')
    foreach ($termMatch in $terms) {
        $token = $termMatch.Value
        if ([string]::IsNullOrWhiteSpace($token)) {
            continue
        }

        $sign = 1
        if ($token.StartsWith('-')) {
            $sign = -1
            $token = $token.Substring(1)
        }
        elseif ($token.StartsWith('+')) {
            $token = $token.Substring(1)
        }

        if ([string]::IsNullOrWhiteSpace($token)) {
            continue
        }

        if ($token -match '^(?<register>[a-z0-9]+)\*(?<scale>[1248])$') {
            $register = Normalize-RegisterName -Name $Matches['register']
            if (-not [string]::IsNullOrWhiteSpace($register)) {
                $indexRegister = $register
                $scale = [int]$Matches['scale']
                $registerTerms.Add($register) | Out-Null
            }

            continue
        }

        if ($token -match '^[a-z0-9]+$' -and $token -notmatch '^[0-9A-Fa-f]+$') {
            $register = Normalize-RegisterName -Name $token
            if ($null -eq $baseRegister) {
                $baseRegister = $register
            }
            elseif ($null -eq $indexRegister) {
                $indexRegister = $register
                $scale = 1
            }

            $registerTerms.Add($register) | Out-Null
            continue
        }

        if ($token -match '^(?:0x)?[0-9A-Fa-f]+$') {
            $displacement += ($sign * (Convert-HexTokenToInt32 -Value $token))
            continue
        }
    }

    return [pscustomobject]@{
        Operand = $Operand
        Normalized = $normalized
        BaseRegister = $baseRegister
        IndexRegister = $indexRegister
        Scale = $scale
        Displacement = $displacement
        Registers = @($registerTerms.ToArray())
    }
}

function Resolve-RegisterMemoryLineage {
    param(
        [Parameter(Mandatory = $true)]
        [object[]]$Instructions,

        [Parameter(Mandatory = $true)]
        [int]$StartPosition,

        [Parameter(Mandatory = $true)]
        [string]$DestinationRegister,

        [Parameter(Mandatory = $true)]
        [scriptblock]$MemoryPredicate,

        [Parameter(Mandatory = $true)]
        [string]$Description
    )

    $currentRegister = Normalize-RegisterName -Name $DestinationRegister
    $aliasChain = New-Object System.Collections.Generic.List[object]

    for ($position = $StartPosition; $position -ge 0; $position--) {
        $instruction = $Instructions[$position]
        $destination = Get-DestinationRegister -Instruction $instruction
        if ([string]::IsNullOrWhiteSpace($destination) -or $destination -ne $currentRegister) {
            continue
        }

        $memoryOperand = Get-MemoryOperandText -Instruction $instruction
        $parsedMemory = Parse-MemoryOperand -Operand $memoryOperand
        if ($parsedMemory -and (& $MemoryPredicate $parsedMemory $instruction)) {
            return [pscustomobject]@{
                Instruction = $instruction
                InstructionPosition = $position
                ResolvedRegister = $currentRegister
                Memory = $parsedMemory
                AliasChain = @($aliasChain.ToArray())
            }
        }

        $sourceRegister = Get-RegisterCopySource -Instruction $instruction -DestinationRegister $currentRegister
        if (-not [string]::IsNullOrWhiteSpace($sourceRegister)) {
            $aliasChain.Add([ordered]@{
                Address = [string]$instruction.Address
                Instruction = [string]$instruction.Full
                FromRegister = $sourceRegister
                ToRegister = $currentRegister
            }) | Out-Null
            $currentRegister = $sourceRegister
            continue
        }
    }

    throw "Owner/source lineage not reconstructed: unable to resolve $Description for register '$DestinationRegister'."
}

function Resolve-RegisterStackLineage {
    param(
        [Parameter(Mandatory = $true)]
        [object[]]$Instructions,

        [Parameter(Mandatory = $true)]
        [int]$StartPosition,

        [Parameter(Mandatory = $true)]
        [string]$DestinationRegister
    )

    $currentRegister = Normalize-RegisterName -Name $DestinationRegister
    $aliasChain = New-Object System.Collections.Generic.List[object]

    for ($position = $StartPosition; $position -ge 0; $position--) {
        $instruction = $Instructions[$position]
        $destination = Get-DestinationRegister -Instruction $instruction
        if ([string]::IsNullOrWhiteSpace($destination) -or $destination -ne $currentRegister) {
            continue
        }

        $memoryOperand = Get-MemoryOperandText -Instruction $instruction
        $parsedMemory = Parse-MemoryOperand -Operand $memoryOperand
        if ($parsedMemory -and -not $parsedMemory.IndexRegister -and $parsedMemory.BaseRegister -in @('RBP', 'RSP')) {
            return [pscustomobject]@{
                Instruction = $instruction
                InstructionPosition = $position
                ResolvedRegister = $currentRegister
                Memory = $parsedMemory
                AliasChain = @($aliasChain.ToArray())
            }
        }

        $sourceRegister = Get-RegisterCopySource -Instruction $instruction -DestinationRegister $currentRegister
        if (-not [string]::IsNullOrWhiteSpace($sourceRegister)) {
            $aliasChain.Add([ordered]@{
                Address = [string]$instruction.Address
                Instruction = [string]$instruction.Full
                FromRegister = $sourceRegister
                ToRegister = $currentRegister
            }) | Out-Null
            $currentRegister = $sourceRegister
            continue
        }
    }

    return $null
}

function Invoke-PatternScanSafe {
    param(
        [string]$Pattern
    )

    if ([string]::IsNullOrWhiteSpace($Pattern)) {
        return $null
    }

    try {
        return Invoke-ReaderJson -Arguments @(
            '--process-name', 'rift_x64',
            '--scan-module-pattern', $Pattern,
            '--scan-module-name', 'rift_x64.exe',
            '--json')
    }
    catch {
        return [pscustomobject]@{
            Mode = 'module-pattern-scan'
            Error = $_.Exception.Message
        }
    }
}

function Get-InstructionWindow {
    param(
        [Parameter(Mandatory = $true)]
        [object[]]$Instructions,

        [Parameter(Mandatory = $true)]
        [int]$StartPosition,

        [Parameter(Mandatory = $true)]
        [int]$EndPosition
    )

    $items = New-Object System.Collections.Generic.List[object]
    $start = [Math]::Max(0, $StartPosition)
    $end = [Math]::Min(($Instructions.Count - 1), $EndPosition)
    for ($position = $start; $position -le $end; $position++) {
        $items.Add($Instructions[$position]) | Out-Null
    }

    return @($items.ToArray())
}

if ($RefreshCluster -or -not (Test-Path -LiteralPath $resolvedClusterFile)) {
    & $clusterScript -Json -InstructionsBefore 40 -InstructionsAfter 24 | Out-Null
}

if (-not (Test-Path -LiteralPath $resolvedClusterFile)) {
    throw "Player trace cluster file not found: $resolvedClusterFile"
}

$cluster = Get-Content -LiteralPath $resolvedClusterFile -Raw | ConvertFrom-Json -Depth 30
$instructions = @($cluster.Instructions)
if ($instructions.Count -eq 0) {
    throw "Owner/source lineage not reconstructed: trace cluster '$resolvedClusterFile' did not contain instructions."
}

$clusterSourceObjectAddress = [string]$cluster.Anchor.SourceObjectAddress
$clusterSourceObjectRegister = Normalize-RegisterName -Name ([string]$cluster.Anchor.SourceObjectRegister)
$clusterSourceObjectRegisterValue = [string]$cluster.Anchor.SourceObjectRegisterValue

if ([string]::IsNullOrWhiteSpace($clusterSourceObjectRegister)) {
    throw "Owner/source lineage not reconstructed: trace cluster did not expose a source object register."
}

$selectedSourceLoad = Resolve-RegisterMemoryLineage -Instructions $instructions -StartPosition ($instructions.Count - 1) -DestinationRegister $clusterSourceObjectRegister -Description 'selected-source load' -MemoryPredicate {
    param($memory, $instruction)
    return -not [string]::IsNullOrWhiteSpace($memory.BaseRegister) -and -not [string]::IsNullOrWhiteSpace($memory.IndexRegister)
}

$sourceObjectLoad = $selectedSourceLoad.Instruction
$sourceObjectLoadMemory = $selectedSourceLoad.Memory
$containerRegister = $sourceObjectLoadMemory.BaseRegister
$selectorIndexRegister = $sourceObjectLoadMemory.IndexRegister
$selectorScale = if ($sourceObjectLoadMemory.Scale) { [int]$sourceObjectLoadMemory.Scale } else { 1 }
$selectorDisplacement = [int]$sourceObjectLoadMemory.Displacement

if ([string]::IsNullOrWhiteSpace($containerRegister) -or [string]::IsNullOrWhiteSpace($selectorIndexRegister)) {
    throw "Owner/source lineage not reconstructed: selected-source load did not expose both a container register and selector index register."
}

$sourceContainerLoad = Resolve-RegisterMemoryLineage -Instructions $instructions -StartPosition ($selectedSourceLoad.InstructionPosition - 1) -DestinationRegister $containerRegister -Description 'owner-container load' -MemoryPredicate {
    param($memory, $instruction)
    return -not [string]::IsNullOrWhiteSpace($memory.BaseRegister) -and [string]::IsNullOrWhiteSpace($memory.IndexRegister)
}

$sourceContainerLoadMemory = $sourceContainerLoad.Memory
$ownerObjectRegister = $sourceContainerLoadMemory.BaseRegister
$ownerContainerDisplacement = [int]$sourceContainerLoadMemory.Displacement

if ([string]::IsNullOrWhiteSpace($ownerObjectRegister)) {
    throw "Owner/source lineage not reconstructed: owner-container load did not expose an owner-object register."
}

$ownerObjectStackSource = Resolve-RegisterStackLineage -Instructions $instructions -StartPosition ($sourceContainerLoad.InstructionPosition - 1) -DestinationRegister $ownerObjectRegister

$sourceResolveCall = $instructions | Where-Object { [int]$_.Index -gt [int]$sourceObjectLoad.Index -and ([string]$_.Opcode -like 'call *') } | Select-Object -First 1
$sourceResolveTarget = $null
if ($sourceResolveCall -and ([string]$sourceResolveCall.Opcode -match '^call\s+(?<target>[0-9A-Fa-f`]+)$')) {
    $sourceResolveTarget = $Matches['target'] -replace '`', ''
}

$destinationCoordXWrite = $instructions | Where-Object { [int]$_.Index -gt [int]$sourceObjectLoad.Index -and [string]$_.RoleHint -eq 'coord-x' } | Select-Object -First 1
$destinationCoordYWrite = $instructions | Where-Object { [int]$_.Index -gt [int]$sourceObjectLoad.Index -and [string]$_.RoleHint -eq 'coord-y' } | Select-Object -First 1
$destinationCoordZWrite = $instructions | Where-Object { [int]$_.Index -gt [int]$sourceObjectLoad.Index -and [string]$_.RoleHint -eq 'coord-z' } | Select-Object -First 1
$sourceCoordXRead = if ($sourceResolveCall) { $instructions | Where-Object { [int]$_.Index -gt [int]$sourceResolveCall.Index -and [string]$_.Opcode -match '\[rax(?:\+00)?\]' } | Select-Object -First 1 } else { $null }
$sourceCoordZRead = if ($sourceResolveCall) { $instructions | Where-Object { [int]$_.Index -gt [int]$sourceResolveCall.Index -and [string]$_.Opcode -match '\[rax\+0*8\]' } | Select-Object -First 1 } else { $null }

$selectorWindowStart = if ($sourceContainerLoad.InstructionPosition -lt $selectedSourceLoad.InstructionPosition) { $sourceContainerLoad.InstructionPosition } else { $selectedSourceLoad.InstructionPosition }
$selectorWindow = Get-InstructionWindow -Instructions $instructions -StartPosition $selectorWindowStart -EndPosition ([Math]::Min(($selectedSourceLoad.InstructionPosition + 2), ($instructions.Count - 1)))
$suggestedSelectorPattern = if ($selectorWindow.Count -gt 0) { ($selectorWindow | ForEach-Object { Get-PatternToken -Instruction $_ }) -join ' ' } else { $null }
$suggestedSelectorScan = Invoke-PatternScanSafe -Pattern $suggestedSelectorPattern

$sourceChainPatternInstructions = New-Object System.Collections.Generic.List[object]
foreach ($instruction in @(
        $sourceContainerLoad.Instruction,
        $sourceObjectLoad,
        $sourceResolveCall,
        $sourceCoordXRead,
        $destinationCoordXWrite,
        $destinationCoordYWrite,
        $sourceCoordZRead,
        $destinationCoordZWrite)) {
    if ($null -ne $instruction) {
        $sourceChainPatternInstructions.Add($instruction) | Out-Null
    }
}

$sourceChainPattern = if ($sourceChainPatternInstructions.Count -gt 0) { (@($sourceChainPatternInstructions.ToArray()) | ForEach-Object { Get-PatternToken -Instruction $_ }) -join ' ' } else { $null }
$sourceChainScan = Invoke-PatternScanSafe -Pattern $sourceChainPattern

$accessorInstructions = @()
$accessorSummary = $null
$accessorPattern = $null
$accessorScan = $null
$preparationSummary = $null
$preparationPattern = $null
$preparationScan = $null
if (-not [string]::IsNullOrWhiteSpace($sourceResolveTarget)) {
    $accessorClusterFile = [System.IO.Path]::ChangeExtension($resolvedOutputFile, '.accessor.tsv')
    $accessorInstructions = Invoke-DisasmCluster -Address (Parse-HexUInt64 -Value $sourceResolveTarget) -OutputPath $accessorClusterFile -Before 4 -After 12

    $accessorReturnLea = $accessorInstructions | Where-Object { ([string]$_.Opcode) -match '^lea rax,\[[a-z0-9]+\+[0-9A-Fa-f]+\]$' } | Select-Object -First 1
    $accessorPrepCall = $accessorInstructions | Where-Object { $_.Opcode -like 'call *' } | Select-Object -First 1
    $accessorReturnOffset = $null
    if ($accessorReturnLea -and ([string]$accessorReturnLea.Opcode -match 'lea rax,\[[a-z0-9]+\+(?<offset>[0-9A-Fa-f]+)\]')) {
        $accessorReturnOffset = [Convert]::ToInt32($Matches['offset'], 16)
    }

    $accessorPatternInstructions = $accessorInstructions | Where-Object {
        ([string]$_.Opcode -eq 'sub rsp,20') -or
        ([string]$_.Opcode -like 'call *') -or
        (([string]$_.Opcode) -match '^lea rax,\[[a-z0-9]+\+[0-9A-Fa-f]+\]$') -or
        ([string]$_.Opcode -eq 'add rsp,20') -or
        ([string]$_.Opcode -like 'ret*')
    }

    if (@($accessorPatternInstructions).Count -gt 0) {
        $accessorPattern = (@($accessorPatternInstructions) | ForEach-Object { Get-PatternToken -Instruction $_ }) -join ' '
        $accessorScan = Invoke-PatternScanSafe -Pattern $accessorPattern
    }

    $accessorSummary = [ordered]@{
        FunctionStart = $sourceResolveTarget
        PreparationCall = $accessorPrepCall
        ReturnLea = $accessorReturnLea
        ReturnOffset = $accessorReturnOffset
        RawInstructionCount = @($accessorInstructions).Count
    }

    $preparationTarget = $null
    if ($accessorPrepCall -and ([string]$accessorPrepCall.Opcode -match '^call\s+(?<target>[0-9A-Fa-f`]+)$')) {
        $preparationTarget = $Matches['target'] -replace '`', ''
    }

    if (-not [string]::IsNullOrWhiteSpace($preparationTarget)) {
        $preparationClusterFile = [System.IO.Path]::ChangeExtension($resolvedOutputFile, '.preparation.tsv')
        $preparationInstructions = Invoke-DisasmCluster -Address (Parse-HexUInt64 -Value $preparationTarget) -OutputPath $preparationClusterFile -Before 4 -After 24

        $guardInstruction = $preparationInstructions | Where-Object { ([string]$_.Opcode) -match '^cmp .+\[[a-z0-9]+\+[0-9A-Fa-f]+\],00$' } | Select-Object -First 1
        $guardJump = $preparationInstructions | Where-Object { $null -ne $guardInstruction -and ([string]$_.Opcode) -like 'j* *' -and [int]$_.Index -gt [int]$guardInstruction.Index } | Select-Object -First 1
        $globalLoad = $preparationInstructions | Where-Object { ([string]$_.Opcode) -like 'mov *,[*]' } | Select-Object -First 1
        $globalTest = $preparationInstructions | Where-Object { $null -ne $globalLoad -and ([string]$_.Opcode) -match '^test [a-z0-9]+,[a-z0-9]+$' -and [int]$_.Index -gt [int]$globalLoad.Index } | Select-Object -First 1

        $preparationPatternInstructions = @(
            $guardInstruction,
            $guardJump,
            $globalLoad,
            $globalTest
        ) | Where-Object { $null -ne $_ }

        if (@($preparationPatternInstructions).Count -ge 3) {
            $preparationPattern = (@($preparationPatternInstructions) | ForEach-Object { Get-PatternToken -Instruction $_ }) -join ' '
            $preparationScan = Invoke-PatternScanSafe -Pattern $preparationPattern
        }

        $preparationSummary = [ordered]@{
            FunctionStart = $preparationTarget
            GuardInstruction = $guardInstruction
            GlobalLoad = $globalLoad
            RawInstructionCount = @($preparationInstructions).Count
        }
    }
}

$sourceCoord48Offset = if ($cluster.Anchor.PSObject.Properties['SourceCoordRelativeOffset'] -and $null -ne $cluster.Anchor.SourceCoordRelativeOffset) { [int]$cluster.Anchor.SourceCoordRelativeOffset } else { 0x48 }
$sourceCoord88Offset = 0x88

$result = [ordered]@{
    Mode = 'player-source-chain'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    ClusterFile = $resolvedClusterFile
    SourceObjectAddress = $clusterSourceObjectAddress
    SelectedSourceAddress = $clusterSourceObjectAddress
    TriggerInstruction = $sourceObjectLoad
    ClusterSummary = [ordered]@{
        TraceInstruction = $cluster.Anchor.InstructionAddress
        ClusterPatternAddress = $cluster.SuggestedClusterScan.Address
        ClusterPatternOffset = $cluster.SuggestedClusterScan.RelativeOffsetHex
        SourceObjectRegister = $clusterSourceObjectRegister
        SourceObjectRegisterValue = $clusterSourceObjectRegisterValue
        SourceObjectAddress = $clusterSourceObjectAddress
    }
    Reconstruction = [ordered]@{
        Status = 'reconstructed'
        SelectedSourceLineage = [ordered]@{
            RequestedRegister = $clusterSourceObjectRegister
            ResolvedRegister = $selectedSourceLoad.ResolvedRegister
            AliasChain = $selectedSourceLoad.AliasChain
            Memory = $sourceObjectLoadMemory
        }
        OwnerContainerLineage = [ordered]@{
            RequestedRegister = $containerRegister
            ResolvedRegister = $sourceContainerLoad.ResolvedRegister
            AliasChain = $sourceContainerLoad.AliasChain
            Memory = $sourceContainerLoadMemory
        }
        OwnerObjectStackSource = if ($ownerObjectStackSource) {
            [ordered]@{
                Register = $ownerObjectStackSource.ResolvedRegister
                AliasChain = $ownerObjectStackSource.AliasChain
                Memory = $ownerObjectStackSource.Memory
                Instruction = $ownerObjectStackSource.Instruction
            }
        }
        else {
            $null
        }
    }
    TraceConfiguration = [ordered]@{
        TriggerInstructionAddress = [string]$sourceObjectLoad.Address
        SelectedSourceRegister = $clusterSourceObjectRegister
        OwnerContainerRegister = $containerRegister
        SelectorIndexRegister = $selectorIndexRegister
        SelectorScale = $selectorScale
        SelectorDisplacement = $selectorDisplacement
        OwnerObjectRegister = $ownerObjectRegister
        OwnerContainerDisplacement = $ownerContainerDisplacement
        OwnerSlotBaseRegister = if ($ownerObjectStackSource) { [string]$ownerObjectStackSource.Memory.BaseRegister } else { $null }
        OwnerSlotDisplacement = if ($ownerObjectStackSource) { [int]$ownerObjectStackSource.Memory.Displacement } else { $null }
        SourceCoord48Offset = $sourceCoord48Offset
        SourceCoord88Offset = $sourceCoord88Offset
    }
    SourceChain = [ordered]@{
        SourceContainerLoad = $sourceContainerLoad.Instruction
        SourceObjectLoad = $sourceObjectLoad
        SourceResolveCall = $sourceResolveCall
        SourceResolveTarget = $sourceResolveTarget
        SourceCoordXRead = $sourceCoordXRead
        DestinationCoordXWrite = $destinationCoordXWrite
        SourceCoordZRead = $sourceCoordZRead
        DestinationCoordZWrite = $destinationCoordZWrite
    }
    Accessor = $accessorSummary
    AccessorInstructions = @($accessorInstructions)
    SuggestedAccessorPattern = $accessorPattern
    SuggestedAccessorScan = $accessorScan
    Preparation = $preparationSummary
    SuggestedPreparationPattern = $preparationPattern
    SuggestedPreparationScan = $preparationScan
    SuggestedSelectorPattern = $suggestedSelectorPattern
    SuggestedSelectorScan = $suggestedSelectorScan
    SuggestedSourceChainPattern = $sourceChainPattern
    SuggestedSourceChainScan = $sourceChainScan
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
    Write-Host "Source-chain file:     $resolvedOutputFile"
    Write-Host "Trigger instruction:   $($sourceObjectLoad.Address) | $($sourceObjectLoad.Full)"
    Write-Host "Selected source reg:   $clusterSourceObjectRegister"
    Write-Host "Container register:    $containerRegister"
    Write-Host "Selector index reg:    $selectorIndexRegister"
    Write-Host ("Selector access:       scale={0} disp=0x{1:X}" -f $selectorScale, $selectorDisplacement)
    Write-Host "Owner object register: $ownerObjectRegister"
    Write-Host ("Owner container off:   0x{0:X}" -f $ownerContainerDisplacement)
    if ($ownerObjectStackSource) {
        Write-Host ("Owner stack source:    {0} {1:+#;-#;0}" -f $ownerObjectStackSource.Memory.BaseRegister, $ownerObjectStackSource.Memory.Displacement)
    }
    if ($sourceResolveCall) {
        Write-Host "Source resolve call:   $($sourceResolveCall.Address) | $($sourceResolveCall.Full)"
        Write-Host "Source target:         $sourceResolveTarget"
    }
    if ($accessorSummary) {
        Write-Host "Accessor return lea:   $($accessorSummary.ReturnLea.Address) | $($accessorSummary.ReturnLea.Full)"
        if ($null -ne $accessorSummary.ReturnOffset) {
            Write-Host ("Accessor return off:   0x{0:X}" -f [int]$accessorSummary.ReturnOffset)
        }
        if ($accessorScan -and $accessorScan.Found -eq $true) {
            Write-Host "Accessor pattern:      $($accessorScan.Address) [$($accessorScan.RelativeOffsetHex)]"
        }
    }
    if ($preparationSummary) {
        Write-Host "Prep guard:            $($preparationSummary.GuardInstruction.Address) | $($preparationSummary.GuardInstruction.Full)"
        if ($preparationScan -and $preparationScan.Found -eq $true) {
            Write-Host "Prep pattern:          $($preparationScan.Address) [$($preparationScan.RelativeOffsetHex)]"
        }
    }
    Write-Host "Suggested selector:    $suggestedSelectorPattern"
    if ($suggestedSelectorScan -and $suggestedSelectorScan.Found -eq $true) {
        Write-Host "Selector pattern:      $($suggestedSelectorScan.Address) [$($suggestedSelectorScan.RelativeOffsetHex)]"
    }
    Write-Host "Suggested pattern:     $sourceChainPattern"
    if ($sourceChainScan -and $sourceChainScan.Found -eq $true) {
        Write-Host "Pattern match:         $($sourceChainScan.Address) [$($sourceChainScan.RelativeOffsetHex)]"
    }
}
