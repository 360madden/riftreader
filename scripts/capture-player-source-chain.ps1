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

function Get-RequiredInstruction {
    param(
        [Parameter(Mandatory = $true)]
        [object[]]$Instructions,

        [Parameter(Mandatory = $true)]
        [scriptblock]$Predicate,

        [Parameter(Mandatory = $true)]
        [string]$Description
    )

    $match = $Instructions | Where-Object $Predicate | Select-Object -First 1
    if ($null -eq $match) {
        throw "Unable to locate required instruction: $Description"
    }

    return $match
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
        return $null
    }

    $opcode = [string]$Instruction.Opcode
    $parts = $bytes.Split(' ', [System.StringSplitOptions]::RemoveEmptyEntries)
    if ($parts.Count -lt 1) {
        return $null
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

function Try-LoadJsonDocument {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return $null
    }

    try {
        $json = Get-Content -LiteralPath $Path -Raw
        if ([string]::IsNullOrWhiteSpace($json)) {
            return $null
        }

        if ((Get-Command Microsoft.PowerShell.Utility\ConvertFrom-Json).Parameters.ContainsKey('Depth')) {
            return ($json | Microsoft.PowerShell.Utility\ConvertFrom-Json -Depth 40)
        }

        return ($json | Microsoft.PowerShell.Utility\ConvertFrom-Json)
    }
    catch {
        return $null
    }
}

function Test-ReusablePreviousSourceChain {
    param(
        $Document,
        $Cluster
    )

    if ($null -eq $Document) {
        return $false
    }

    $documentMode = if ($Document.PSObject.Properties['Mode']) { [string]$Document.Mode } else { $null }
    if ($documentMode -ne 'player-source-chain') {
        return $false
    }

    $accessor = if ($Document.PSObject.Properties['Accessor']) { $Document.Accessor } else { $null }
    $preparation = if ($Document.PSObject.Properties['Preparation']) { $Document.Preparation } else { $null }
    if ($null -eq $accessor -or [string]::IsNullOrWhiteSpace([string]$accessor.FunctionStart)) {
        return $false
    }

    if ($null -eq $preparation -or [string]::IsNullOrWhiteSpace([string]$preparation.FunctionStart)) {
        return $false
    }

    $currentProcessId = if ($Cluster.Anchor.PSObject.Properties['ProcessId']) { [string]$Cluster.Anchor.ProcessId } else { $null }
    $documentProcessId = if ($Document.PSObject.Properties['ProcessId']) { [string]$Document.ProcessId } else { $null }
    if (-not [string]::IsNullOrWhiteSpace($documentProcessId) -and
        -not [string]::Equals($documentProcessId, $currentProcessId, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $false
    }

    return $true
}

function Get-PreviousSourceChainPattern {
    param(
        $Document
    )

    if ($null -eq $Document) {
        return $null
    }

    if ($Document.PSObject.Properties['SuggestedSourceChainPattern']) {
        $pattern = [string]$Document.SuggestedSourceChainPattern
        if (-not [string]::IsNullOrWhiteSpace($pattern)) {
            return $pattern
        }
    }

    return $null
}

function Convert-ToCanonicalInstruction {
    param(
        $Instruction
    )

    if ($null -eq $Instruction) {
        return $null
    }

    return [ordered]@{
        Index = if ($Instruction.PSObject.Properties['Index']) { $Instruction.Index } elseif ($Instruction.PSObject.Properties['index']) { $Instruction.index } else { $null }
        Address = if ($Instruction.PSObject.Properties['Address']) { $Instruction.Address } elseif ($Instruction.PSObject.Properties['address']) { $Instruction.address } else { $null }
        Bytes = if ($Instruction.PSObject.Properties['Bytes']) { $Instruction.Bytes } elseif ($Instruction.PSObject.Properties['bytes']) { $Instruction.bytes } else { $null }
        Opcode = if ($Instruction.PSObject.Properties['Opcode']) { $Instruction.Opcode } elseif ($Instruction.PSObject.Properties['opcode']) { $Instruction.opcode } else { $null }
        Extra = if ($Instruction.PSObject.Properties['Extra']) { $Instruction.Extra } elseif ($Instruction.PSObject.Properties['extra']) { $Instruction.extra } else { $null }
        Full = if ($Instruction.PSObject.Properties['Full']) { $Instruction.Full } elseif ($Instruction.PSObject.Properties['full']) { $Instruction.full } else { $null }
        UsesBaseRegister = if ($Instruction.PSObject.Properties['UsesBaseRegister']) { $Instruction.UsesBaseRegister } else { $null }
        MemoryOperand = if ($Instruction.PSObject.Properties['MemoryOperand']) { $Instruction.MemoryOperand } else { $null }
        RelativeOffset = if ($Instruction.PSObject.Properties['RelativeOffset']) { $Instruction.RelativeOffset } else { $null }
        RoleHint = if ($Instruction.PSObject.Properties['RoleHint']) { $Instruction.RoleHint } else { $null }
    }
}

function Build-SourceChainArtifacts {
    param(
        [Parameter(Mandatory = $true)]
        [object[]]$Instructions,

        [Parameter(Mandatory = $true)]
        [string]$ArtifactBasePath,

        [Parameter(Mandatory = $true)]
        [string]$ProcessName
    )

    $sourceContainerLoad = Get-RequiredInstruction -Instructions $Instructions -Description 'source container load' -Predicate {
        $_.Opcode -eq 'mov rcx,[rax+78]'
    }
    $sourceObjectLoad = Get-RequiredInstruction -Instructions $Instructions -Description 'source object load' -Predicate {
        $_.Opcode -eq 'mov rdi,[rcx+rdx*8]'
    }
    $sourceObjectLoadIndex = [int]$sourceObjectLoad.Index

    $sourceResolveCall = $null
    foreach ($instruction in $Instructions) {
        $instructionIndex = [int]$instruction.Index
        if ($instructionIndex -le $sourceObjectLoadIndex) {
            continue
        }

        if (-not ([string]$instruction.Opcode -like 'call *')) {
            continue
        }

        $previous = $Instructions | Where-Object { [int]$_.Index -eq ($instructionIndex - 1) } | Select-Object -First 1
        $next = $Instructions | Where-Object { [int]$_.Index -eq ($instructionIndex + 1) } | Select-Object -First 1
        if ($previous -and $next -and ([string]$previous.Opcode -eq 'mov rcx,rdi') -and ([string]$next.Opcode -eq 'mov rcx,rdi')) {
            $sourceResolveCall = $instruction
            break
        }
    }

    if ($null -eq $sourceResolveCall) {
        throw "Unable to locate the source resolve call in the current trace cluster."
    }

    $sourceResolveCallIndex = [int]$sourceResolveCall.Index
    $sourceCoordXRead = Get-RequiredInstruction -Instructions $Instructions -Description 'source coord-x read' -Predicate {
        [int]$_.Index -gt $sourceResolveCallIndex -and $_.Opcode -eq 'movsd xmm0,[rax]'
    }
    $sourceCoordXReadIndex = [int]$sourceCoordXRead.Index
    $destCoordXWrite = Get-RequiredInstruction -Instructions $Instructions -Description 'destination coord-x write' -Predicate {
        [int]$_.Index -gt $sourceCoordXReadIndex -and $_.Opcode -eq 'movsd [rsi+00000158],xmm0'
    }
    $destCoordXWriteIndex = [int]$destCoordXWrite.Index
    $sourceCoordZRead = Get-RequiredInstruction -Instructions $Instructions -Description 'source coord-z read' -Predicate {
        [int]$_.Index -gt $destCoordXWriteIndex -and $_.Opcode -eq 'mov eax,[rax+08]'
    }
    $sourceCoordZReadIndex = [int]$sourceCoordZRead.Index
    $destCoordZWrite = Get-RequiredInstruction -Instructions $Instructions -Description 'destination coord-z write' -Predicate {
        [int]$_.Index -gt $sourceCoordZReadIndex -and $_.Opcode -eq 'mov [rsi+00000160],eax'
    }

    $patternInstructions = @(
        $sourceContainerLoad,
        $sourceObjectLoad,
        ($Instructions | Where-Object { [int]$_.Index -eq ($sourceObjectLoadIndex + 1) } | Select-Object -First 1),
        ($Instructions | Where-Object { [int]$_.Index -eq ($sourceObjectLoadIndex + 2) } | Select-Object -First 1),
        ($Instructions | Where-Object { [int]$_.Index -eq ($sourceResolveCallIndex - 1) } | Select-Object -First 1),
        $sourceResolveCall,
        ($Instructions | Where-Object { [int]$_.Index -eq ($sourceResolveCallIndex + 1) } | Select-Object -First 1),
        $sourceCoordXRead,
        $destCoordXWrite,
        $sourceCoordZRead,
        $destCoordZWrite
    ) | Where-Object { $null -ne $_ }

    $sourceChainPatternTokens = @(
        $patternInstructions |
            ForEach-Object { Get-PatternToken -Instruction $_ } |
            Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    )

    if ($sourceChainPatternTokens.Count -lt 6) {
        throw 'Unable to build a stable source-chain pattern from the current disassembly cluster.'
    }

    $sourceChainPattern = $sourceChainPatternTokens -join ' '
    $sourceChainScan = Invoke-ReaderJson -Arguments @(
        '--process-name', $ProcessName,
        '--scan-module-pattern', $sourceChainPattern,
        '--scan-module-name', 'rift_x64.exe',
        '--json')

    $sourceResolveTarget = $null
    if ([string]$sourceResolveCall.Opcode -match '^call\s+(?<target>[0-9A-Fa-f`]+)$') {
        $sourceResolveTarget = $Matches['target'] -replace '`', ''
    }

    $accessorInstructions = @()
    $accessorSummary = $null
    $accessorPattern = $null
    $accessorScan = $null
    $preparationSummary = $null
    $preparationPattern = $null
    $preparationScan = $null

    if (-not [string]::IsNullOrWhiteSpace($sourceResolveTarget)) {
        $accessorClusterFile = [System.IO.Path]::ChangeExtension($ArtifactBasePath, '.accessor.tsv')
        $accessorInstructions = Invoke-DisasmCluster -Address (Parse-HexUInt64 -Value $sourceResolveTarget) -OutputPath $accessorClusterFile -Before 4 -After 12

        $accessorReturnLea = $accessorInstructions | Where-Object { ([string]$_.opcode) -match '^lea rax,\[rbx\+[0-9A-Fa-f]+\]$' } | Select-Object -First 1
        $accessorPrepCall = $accessorInstructions | Where-Object { $_.Opcode -like 'call *' } | Select-Object -First 1
        $accessorReturnOffset = $null
        if ($accessorReturnLea -and ([string]$accessorReturnLea.Opcode -match 'lea rax,\[rbx\+(?<offset>[0-9A-Fa-f]+)\]')) {
            $accessorReturnOffset = [Convert]::ToInt32($Matches['offset'], 16)
        }

        $accessorPatternInstructions = $accessorInstructions | Where-Object {
            $_.Address -and ((Parse-HexUInt64 -Value ([string]$_.Address)) -ge (Parse-HexUInt64 -Value $sourceResolveTarget)) -and (
                $_.Address -eq $sourceResolveTarget -or
                ([string]$_.Opcode -eq 'sub rsp,20') -or
                ([string]$_.Opcode -eq 'mov rbx,rcx') -or
                ([string]$_.Opcode -like 'call *') -or
                (([string]$_.opcode) -match '^lea rax,\[rbx\+[0-9A-Fa-f]+\]$') -or
                ([string]$_.Opcode -eq 'add rsp,20') -or
                ([string]$_.Opcode -eq 'pop rbx') -or
                ([string]$_.Opcode -like 'ret*')
            )
        }

        if (@($accessorPatternInstructions).Count -gt 0) {
            $accessorPatternTokens = @(
                @($accessorPatternInstructions) |
                    ForEach-Object { Get-PatternToken -Instruction $_ } |
                    Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
            )

            if ($accessorPatternTokens.Count -gt 0) {
                $accessorPattern = $accessorPatternTokens -join ' '
                $accessorScan = Invoke-ReaderJson -Arguments @(
                    '--process-name', $ProcessName,
                    '--scan-module-pattern', $accessorPattern,
                    '--scan-module-name', 'rift_x64.exe',
                    '--json')
            }
        }

        $accessorSummary = [ordered]@{
            FunctionStart = $sourceResolveTarget
            PreparationCall = $accessorPrepCall
            ReturnLea = $accessorReturnLea
            ReturnOffset = $accessorReturnOffset
            RawInstructionCount = @($accessorInstructions).Count
        }

        $preparationTarget = $null
        if ($accessorPrepCall -and ([string]$accessorPrepCall.opcode -match '^call\s+(?<target>[0-9A-Fa-f`]+)$')) {
            $preparationTarget = $Matches['target'] -replace '`', ''
        }

        if (-not [string]::IsNullOrWhiteSpace($preparationTarget)) {
            $preparationClusterFile = [System.IO.Path]::ChangeExtension($ArtifactBasePath, '.preparation.tsv')
            $preparationInstructions = Invoke-DisasmCluster -Address (Parse-HexUInt64 -Value $preparationTarget) -OutputPath $preparationClusterFile -Before 4 -After 24

            $guardMove = $preparationInstructions | Where-Object { ([string]$_.opcode) -eq 'mov rdi,rcx' } | Select-Object -First 1
            $guardInstruction = $preparationInstructions | Where-Object { ([string]$_.opcode) -eq 'cmp qword ptr [rcx+00000100],00' } | Select-Object -First 1
            $guardJump = $preparationInstructions | Where-Object { $null -ne $guardInstruction -and ([string]$_.opcode) -like 'je *' -and [int]$_.index -gt [int]$guardInstruction.index } | Select-Object -First 1
            $globalLoad = $preparationInstructions | Where-Object { ([string]$_.opcode) -like 'mov rbx,[*]' } | Select-Object -First 1
            $globalTest = $preparationInstructions | Where-Object { $null -ne $globalLoad -and ([string]$_.opcode) -eq 'test rbx,rbx' -and [int]$_.index -gt [int]$globalLoad.index } | Select-Object -First 1

            $preparationPatternInstructions = @(
                $guardMove,
                $guardInstruction,
                $guardJump,
                $globalLoad,
                $globalTest
            ) | Where-Object { $null -ne $_ }

            if (@($preparationPatternInstructions).Count -ge 5) {
                $preparationPatternTokens = @(
                    @($preparationPatternInstructions) |
                        ForEach-Object { Get-PatternToken -Instruction $_ } |
                        Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
                )

                if ($preparationPatternTokens.Count -ge 5) {
                    $preparationPattern = $preparationPatternTokens -join ' '
                    $preparationScan = Invoke-ReaderJson -Arguments @(
                        '--process-name', $ProcessName,
                        '--scan-module-pattern', $preparationPattern,
                        '--scan-module-name', 'rift_x64.exe',
                        '--json')
                }
            }

            $preparationSummary = [ordered]@{
                FunctionStart = $preparationTarget
                GuardInstruction = $guardInstruction
                GuardOffset = if ($guardInstruction) { 0x100 } else { $null }
                GlobalLoad = $globalLoad
                RawInstructionCount = @($preparationInstructions).Count
            }
        }
    }

    return [ordered]@{
        SourceChain = [ordered]@{
            SourceContainerLoad = Convert-ToCanonicalInstruction -Instruction $sourceContainerLoad
            SourceObjectLoad = Convert-ToCanonicalInstruction -Instruction $sourceObjectLoad
            SourceResolveCall = Convert-ToCanonicalInstruction -Instruction $sourceResolveCall
            SourceResolveTarget = $sourceResolveTarget
            SourceCoordXRead = Convert-ToCanonicalInstruction -Instruction $sourceCoordXRead
            DestinationCoordXWrite = Convert-ToCanonicalInstruction -Instruction $destCoordXWrite
            SourceCoordZRead = Convert-ToCanonicalInstruction -Instruction $sourceCoordZRead
            DestinationCoordZWrite = Convert-ToCanonicalInstruction -Instruction $destCoordZWrite
        }
        Accessor = if ($null -ne $accessorSummary) {
            [ordered]@{
                FunctionStart = $accessorSummary.FunctionStart
                PreparationCall = Convert-ToCanonicalInstruction -Instruction $accessorSummary.PreparationCall
                ReturnLea = Convert-ToCanonicalInstruction -Instruction $accessorSummary.ReturnLea
                ReturnOffset = $accessorSummary.ReturnOffset
                RawInstructionCount = $accessorSummary.RawInstructionCount
            }
        } else {
            $null
        }
        AccessorInstructions = @($accessorInstructions | ForEach-Object { Convert-ToCanonicalInstruction -Instruction $_ })
        SuggestedAccessorPattern = $accessorPattern
        SuggestedAccessorScan = $accessorScan
        Preparation = if ($null -ne $preparationSummary) {
            [ordered]@{
                FunctionStart = $preparationSummary.FunctionStart
                GuardInstruction = Convert-ToCanonicalInstruction -Instruction $preparationSummary.GuardInstruction
                GuardOffset = $preparationSummary.GuardOffset
                GlobalLoad = Convert-ToCanonicalInstruction -Instruction $preparationSummary.GlobalLoad
                RawInstructionCount = $preparationSummary.RawInstructionCount
            }
        } else {
            $null
        }
        SuggestedPreparationPattern = $preparationPattern
        SuggestedPreparationScan = $preparationScan
        SuggestedSourceChainPattern = $sourceChainPattern
        SuggestedSourceChainScan = $sourceChainScan
    }
}

if ($RefreshCluster -or -not (Test-Path -LiteralPath $resolvedClusterFile)) {
    & $clusterScript -Json -InstructionsBefore 40 -InstructionsAfter 24 | Out-Null
}

if (-not (Test-Path -LiteralPath $resolvedClusterFile)) {
    throw "Player trace cluster file not found: $resolvedClusterFile"
}

$cluster = Get-Content -LiteralPath $resolvedClusterFile -Raw | ConvertFrom-Json -Depth 30
$instructions = @($cluster.Instructions)
$clusterSourceObjectAddress = [string]$cluster.Anchor.SourceObjectAddress
$clusterSourceObjectRegister = [string]$cluster.Anchor.SourceObjectRegister
$clusterSourceObjectRegisterValue = [string]$cluster.Anchor.SourceObjectRegisterValue
$clusterSuggestedClusterScan = $null
$clusterPatternAddress = $null
$clusterPatternOffset = $null
if ($cluster.PSObject.Properties['SuggestedClusterScan']) {
    $clusterSuggestedClusterScan = $cluster.SuggestedClusterScan
    if ($null -ne $clusterSuggestedClusterScan) {
        if ($clusterSuggestedClusterScan.PSObject.Properties['Address']) {
            $clusterPatternAddress = [string]$clusterSuggestedClusterScan.Address
        }
        if ($clusterSuggestedClusterScan.PSObject.Properties['RelativeOffsetHex']) {
            $clusterPatternOffset = [string]$clusterSuggestedClusterScan.RelativeOffsetHex
        }
    }
}
$previousSourceChain = Try-LoadJsonDocument -Path $resolvedOutputFile
$sourceContainerLoad = $null
$sourceObjectLoad = $null
$sourceResolveCall = $null
$sourceCoordXRead = $null
$destCoordXWrite = $null
$sourceCoordZRead = $null
$destCoordZWrite = $null
$sourceChainPattern = $null
$sourceChainScan = $null
$sourceResolveTarget = $null
$accessorInstructions = @()
$accessorSummary = $null
$accessorPattern = $null
$accessorScan = $null
$preparationSummary = $null
$preparationPattern = $null
$preparationScan = $null
$result = $null
$sourceChainBuildError = $null
$freshSourceChainRecovery = $null

try {
    $builtArtifacts = Build-SourceChainArtifacts -Instructions $instructions -ArtifactBasePath $resolvedOutputFile -ProcessName ([string]$cluster.Anchor.ProcessName)

    $sourceChainPattern = $builtArtifacts.SuggestedSourceChainPattern
    $sourceChainScan = $builtArtifacts.SuggestedSourceChainScan
    $accessorSummary = $builtArtifacts.Accessor
    $accessorInstructions = @($builtArtifacts.AccessorInstructions)
    $accessorPattern = $builtArtifacts.SuggestedAccessorPattern
    $accessorScan = $builtArtifacts.SuggestedAccessorScan
    $preparationSummary = $builtArtifacts.Preparation
    $preparationPattern = $builtArtifacts.SuggestedPreparationPattern
    $preparationScan = $builtArtifacts.SuggestedPreparationScan

    $result = [ordered]@{
        Mode = 'player-source-chain'
        GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
        ProcessId = $cluster.Anchor.ProcessId
        ProcessName = $cluster.Anchor.ProcessName
        ClusterFile = $resolvedClusterFile
        SourceObjectAddress = $clusterSourceObjectAddress
        SelectedSourceAddress = $clusterSourceObjectAddress
        ClusterSummary = [ordered]@{
            TraceInstruction = $cluster.Anchor.InstructionAddress
            ClusterPatternAddress = $clusterPatternAddress
            ClusterPatternOffset = $clusterPatternOffset
            SourceObjectRegister = $clusterSourceObjectRegister
            SourceObjectRegisterValue = $clusterSourceObjectRegisterValue
            SourceObjectAddress = $clusterSourceObjectAddress
        }
        SourceChain = $builtArtifacts.SourceChain
        Accessor = $accessorSummary
        AccessorInstructions = @($accessorInstructions)
        SuggestedAccessorPattern = $accessorPattern
        SuggestedAccessorScan = $accessorScan
        Preparation = $preparationSummary
        SuggestedPreparationPattern = $preparationPattern
        SuggestedPreparationScan = $preparationScan
        SuggestedSourceChainPattern = $sourceChainPattern
        SuggestedSourceChainScan = $sourceChainScan
    }
}
catch {
    $sourceChainBuildError = $_.Exception
}

if ($null -ne $sourceChainBuildError) {
    $canReusePreviousSourceChain = Test-ReusablePreviousSourceChain -Document $previousSourceChain -Cluster $cluster
    if ($canReusePreviousSourceChain) {
        $previousSourceChainPattern = Get-PreviousSourceChainPattern -Document $previousSourceChain
        if (-not [string]::IsNullOrWhiteSpace($previousSourceChainPattern)) {
            try {
                $freshSourceChainScan = Invoke-ReaderJson -Arguments @(
                    '--process-name', [string]$cluster.Anchor.ProcessName,
                    '--scan-module-pattern', $previousSourceChainPattern,
                    '--scan-module-name', 'rift_x64.exe',
                    '--json')

                if ($freshSourceChainScan.Found -eq $true -and -not [string]::IsNullOrWhiteSpace([string]$freshSourceChainScan.Address)) {
                    $freshSourceChainClusterFile = [System.IO.Path]::ChangeExtension($resolvedOutputFile, '.fresh-source-chain.tsv')
                    $freshSourceChainInstructions = Invoke-DisasmCluster -Address (Parse-HexUInt64 -Value ([string]$freshSourceChainScan.Address)) -OutputPath $freshSourceChainClusterFile -Before 8 -After 40
                    $freshSourceChainArtifactBasePath = [System.IO.Path]::ChangeExtension($resolvedOutputFile, '.fresh-source-chain.json')
                    $freshBuiltArtifacts = Build-SourceChainArtifacts -Instructions $freshSourceChainInstructions -ArtifactBasePath $freshSourceChainArtifactBasePath -ProcessName ([string]$cluster.Anchor.ProcessName)

                    $result = [ordered]@{
                        Mode = 'player-source-chain'
                        GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
                        ProcessId = $cluster.Anchor.ProcessId
                        ProcessName = $cluster.Anchor.ProcessName
                        ClusterFile = $resolvedClusterFile
                        SourceObjectAddress = $clusterSourceObjectAddress
                        SelectedSourceAddress = $clusterSourceObjectAddress
                        ClusterSummary = [ordered]@{
                            TraceInstruction = $cluster.Anchor.InstructionAddress
                            ClusterPatternAddress = $clusterPatternAddress
                            ClusterPatternOffset = $clusterPatternOffset
                            SourceObjectRegister = $clusterSourceObjectRegister
                            SourceObjectRegisterValue = $clusterSourceObjectRegisterValue
                            SourceObjectAddress = $clusterSourceObjectAddress
                        }
                        Recovery = [ordered]@{
                            Mode = 'rebuild-from-suggested-source-chain-pattern'
                            TriggerReason = $sourceChainBuildError.Message
                            Pattern = $previousSourceChainPattern
                            PatternScanAddress = [string]$freshSourceChainScan.Address
                            PatternScanOffset = [string]$freshSourceChainScan.RelativeOffsetHex
                        }
                        SourceChain = $freshBuiltArtifacts.SourceChain
                        Accessor = $freshBuiltArtifacts.Accessor
                        AccessorInstructions = @($freshBuiltArtifacts.AccessorInstructions)
                        SuggestedAccessorPattern = $freshBuiltArtifacts.SuggestedAccessorPattern
                        SuggestedAccessorScan = $freshBuiltArtifacts.SuggestedAccessorScan
                        Preparation = $freshBuiltArtifacts.Preparation
                        SuggestedPreparationPattern = $freshBuiltArtifacts.SuggestedPreparationPattern
                        SuggestedPreparationScan = $freshBuiltArtifacts.SuggestedPreparationScan
                        SuggestedSourceChainPattern = $freshBuiltArtifacts.SuggestedSourceChainPattern
                        SuggestedSourceChainScan = $freshBuiltArtifacts.SuggestedSourceChainScan
                    }

                    $freshSourceChainRecovery = $result.Recovery
                }
            }
            catch {
                # Fall through to the last-good same-session reuse path below.
            }
        }
    }

    if ($null -ne $result) {
        $sourceChainBuildError = $null
    }
    elseif (-not $canReusePreviousSourceChain) {
        throw $sourceChainBuildError
    }
    else {
        $result = [ordered]@{
            Mode = 'player-source-chain'
            GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
            ProcessId = $cluster.Anchor.ProcessId
            ProcessName = $cluster.Anchor.ProcessName
            ClusterFile = $resolvedClusterFile
            SourceObjectAddress = if (-not [string]::IsNullOrWhiteSpace([string]$previousSourceChain.SourceObjectAddress)) { [string]$previousSourceChain.SourceObjectAddress } else { $clusterSourceObjectAddress }
            SelectedSourceAddress = if (-not [string]::IsNullOrWhiteSpace([string]$previousSourceChain.SelectedSourceAddress)) { [string]$previousSourceChain.SelectedSourceAddress } else { $clusterSourceObjectAddress }
            ClusterSummary = [ordered]@{
                TraceInstruction = $cluster.Anchor.InstructionAddress
                ClusterPatternAddress = $clusterPatternAddress
                ClusterPatternOffset = $clusterPatternOffset
                SourceObjectRegister = $clusterSourceObjectRegister
                SourceObjectRegisterValue = $clusterSourceObjectRegisterValue
                SourceObjectAddress = $clusterSourceObjectAddress
            }
            Recovery = [ordered]@{
                Mode = 'reuse-previous-source-chain'
                PreviousArtifactFile = $resolvedOutputFile
                PreviousGeneratedAtUtc = $previousSourceChain.GeneratedAtUtc
                Reason = $sourceChainBuildError.Message
                ReusedAccessorFunctionStart = [string]$previousSourceChain.Accessor.FunctionStart
                ReusedPreparationFunctionStart = [string]$previousSourceChain.Preparation.FunctionStart
            }
            SourceChain = $previousSourceChain.SourceChain
            Accessor = $previousSourceChain.Accessor
            AccessorInstructions = @($previousSourceChain.AccessorInstructions)
            SuggestedAccessorPattern = $previousSourceChain.SuggestedAccessorPattern
            SuggestedAccessorScan = $previousSourceChain.SuggestedAccessorScan
            Preparation = $previousSourceChain.Preparation
            SuggestedPreparationPattern = $previousSourceChain.SuggestedPreparationPattern
            SuggestedPreparationScan = $previousSourceChain.SuggestedPreparationScan
            SuggestedSourceChainPattern = $previousSourceChain.SuggestedSourceChainPattern
            SuggestedSourceChainScan = $previousSourceChain.SuggestedSourceChainScan
        }
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
    Write-Host "Source-chain file:     $resolvedOutputFile"
    if ($result.Recovery) {
        $recoveryReason = if ($result.Recovery.PSObject.Properties['Reason']) { $result.Recovery.Reason } elseif ($result.Recovery.PSObject.Properties['TriggerReason']) { $result.Recovery.TriggerReason } else { $null }
        Write-Host "Recovery mode:         $($result.Recovery.Mode)"
        if (-not [string]::IsNullOrWhiteSpace([string]$recoveryReason)) {
            Write-Host "Recovery reason:       $recoveryReason"
        }
    }
    Write-Host "Source object load:    $($result.SourceChain.SourceObjectLoad.Address) | $($result.SourceChain.SourceObjectLoad.Full)"
    Write-Host "Source resolve call:   $($result.SourceChain.SourceResolveCall.Address) | $($result.SourceChain.SourceResolveCall.Full)"
    Write-Host "Source target:         $($result.SourceChain.SourceResolveTarget)"
    if ($result.Accessor) {
        Write-Host "Accessor return lea:   $($result.Accessor.ReturnLea.Address) | $($result.Accessor.ReturnLea.Full)"
        if ($null -ne $result.Accessor.ReturnOffset) {
            Write-Host ("Accessor return off:   0x{0:X}" -f [int]$result.Accessor.ReturnOffset)
        }
        if ($result.SuggestedAccessorScan -and $result.SuggestedAccessorScan.Found -eq $true) {
            Write-Host "Accessor pattern:      $($result.SuggestedAccessorScan.Address) [$($result.SuggestedAccessorScan.RelativeOffsetHex)]"
        }
    }
    if ($result.Preparation) {
        Write-Host "Prep guard:            $($result.Preparation.GuardInstruction.address) | $($result.Preparation.GuardInstruction.full)"
        if ($null -ne $result.Preparation.GuardOffset) {
            Write-Host ("Prep guard off:        0x{0:X}" -f [int]$result.Preparation.GuardOffset)
        }
        if ($result.SuggestedPreparationScan -and $result.SuggestedPreparationScan.Found -eq $true) {
            Write-Host "Prep pattern:          $($result.SuggestedPreparationScan.Address) [$($result.SuggestedPreparationScan.RelativeOffsetHex)]"
        }
    }
    Write-Host "Coord X read/write:    $($result.SourceChain.SourceCoordXRead.Address) -> $($result.SourceChain.DestinationCoordXWrite.Address)"
    Write-Host "Coord Z read/write:    $($result.SourceChain.SourceCoordZRead.Address) -> $($result.SourceChain.DestinationCoordZWrite.Address)"
    Write-Host "Suggested pattern:     $($result.SuggestedSourceChainPattern)"
    if ($result.SuggestedSourceChainScan.Found -eq $true) {
        Write-Host "Pattern match:         $($result.SuggestedSourceChainScan.Address) [$($result.SuggestedSourceChainScan.RelativeOffsetHex)]"
    }
}
