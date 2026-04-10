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

if ($RefreshCluster -or -not (Test-Path -LiteralPath $resolvedClusterFile)) {
    & $clusterScript -Json -InstructionsBefore 40 -InstructionsAfter 24 | Out-Null
}

if (-not (Test-Path -LiteralPath $resolvedClusterFile)) {
    throw "Player trace cluster file not found: $resolvedClusterFile"
}

$cluster = Get-Content -LiteralPath $resolvedClusterFile -Raw | ConvertFrom-Json -Depth 30
$instructions = @($cluster.Instructions)

$sourceContainerLoad = Get-RequiredInstruction -Instructions $instructions -Description 'source container load' -Predicate {
    $_.Opcode -eq 'mov rcx,[rax+78]'
}
$sourceObjectLoad = Get-RequiredInstruction -Instructions $instructions -Description 'source object load' -Predicate {
    $_.Opcode -eq 'mov rdi,[rcx+rdx*8]'
}
$sourceResolveCall = $null
foreach ($instruction in $instructions) {
    if ($instruction.Index -le $sourceObjectLoad.Index) {
        continue
    }

    if (-not ([string]$instruction.Opcode -like 'call *')) {
        continue
    }

    $previous = $instructions | Where-Object { $_.Index -eq ($instruction.Index - 1) } | Select-Object -First 1
    $next = $instructions | Where-Object { $_.Index -eq ($instruction.Index + 1) } | Select-Object -First 1
    if ($previous -and $next -and ([string]$previous.Opcode -eq 'mov rcx,rdi') -and ([string]$next.Opcode -eq 'mov rcx,rdi')) {
        $sourceResolveCall = $instruction
        break
    }
}

if ($null -eq $sourceResolveCall) {
    throw "Unable to locate the source resolve call in the current trace cluster."
}

$sourceCoordXRead = Get-RequiredInstruction -Instructions $instructions -Description 'source coord-x read' -Predicate {
    $_.Index -gt $sourceResolveCall.Index -and $_.Opcode -eq 'movsd xmm0,[rax]'
}
$destCoordXWrite = Get-RequiredInstruction -Instructions $instructions -Description 'destination coord-x write' -Predicate {
    $_.Index -gt $sourceCoordXRead.Index -and $_.Opcode -eq 'movsd [rsi+00000158],xmm0'
}
$sourceCoordZRead = Get-RequiredInstruction -Instructions $instructions -Description 'source coord-z read' -Predicate {
    $_.Index -gt $destCoordXWrite.Index -and $_.Opcode -eq 'mov eax,[rax+08]'
}
$destCoordZWrite = Get-RequiredInstruction -Instructions $instructions -Description 'destination coord-z write' -Predicate {
    $_.Index -gt $sourceCoordZRead.Index -and $_.Opcode -eq 'mov [rsi+00000160],eax'
}

$patternInstructions = @(
    $sourceContainerLoad,
    $sourceObjectLoad,
    ($instructions | Where-Object { $_.Index -eq ($sourceObjectLoad.Index + 1) } | Select-Object -First 1),
    ($instructions | Where-Object { $_.Index -eq ($sourceObjectLoad.Index + 2) } | Select-Object -First 1),
    ($instructions | Where-Object { $_.Index -eq ($sourceResolveCall.Index - 1) } | Select-Object -First 1),
    $sourceResolveCall,
    ($instructions | Where-Object { $_.Index -eq ($sourceResolveCall.Index + 1) } | Select-Object -First 1),
    $sourceCoordXRead,
    $destCoordXWrite,
    $sourceCoordZRead,
    $destCoordZWrite
) | Where-Object { $null -ne $_ }

$sourceChainPattern = ($patternInstructions | ForEach-Object { Get-PatternToken -Instruction $_ }) -join ' '
$sourceChainScan = Invoke-ReaderJson -Arguments @(
    '--process-name', 'rift_x64',
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
    $accessorClusterFile = [System.IO.Path]::ChangeExtension($resolvedOutputFile, '.accessor.tsv')
    $accessorInstructions = Invoke-DisasmCluster -Address (Parse-HexUInt64 -Value $sourceResolveTarget) -OutputPath $accessorClusterFile -Before 4 -After 12

    $accessorFunctionStart = $accessorInstructions | Where-Object { $_.Address -eq $sourceResolveTarget } | Select-Object -First 1
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
        $accessorPattern = (@($accessorPatternInstructions) | ForEach-Object { Get-PatternToken -Instruction $_ }) -join ' '
        $accessorScan = Invoke-ReaderJson -Arguments @(
            '--process-name', 'rift_x64',
            '--scan-module-pattern', $accessorPattern,
            '--scan-module-name', 'rift_x64.exe',
            '--json')
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
        $preparationClusterFile = [System.IO.Path]::ChangeExtension($resolvedOutputFile, '.preparation.tsv')
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
            $preparationPattern = (@($preparationPatternInstructions) | ForEach-Object { Get-PatternToken -Instruction $_ }) -join ' '
            $preparationScan = Invoke-ReaderJson -Arguments @(
                '--process-name', 'rift_x64',
                '--scan-module-pattern', $preparationPattern,
                '--scan-module-name', 'rift_x64.exe',
                '--json')
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

$result = [ordered]@{
    Mode = 'player-source-chain'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    ClusterFile = $resolvedClusterFile
    ClusterSummary = [ordered]@{
        TraceInstruction = $cluster.Anchor.InstructionAddress
        ClusterPatternAddress = $cluster.SuggestedClusterScan.Address
        ClusterPatternOffset = $cluster.SuggestedClusterScan.RelativeOffsetHex
    }
    SourceChain = [ordered]@{
        SourceContainerLoad = $sourceContainerLoad
        SourceObjectLoad = $sourceObjectLoad
        SourceResolveCall = $sourceResolveCall
        SourceResolveTarget = $sourceResolveTarget
        SourceCoordXRead = $sourceCoordXRead
        DestinationCoordXWrite = $destCoordXWrite
        SourceCoordZRead = $sourceCoordZRead
        DestinationCoordZWrite = $destCoordZWrite
    }
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
    Write-Host "Source object load:    $($sourceObjectLoad.Address) | $($sourceObjectLoad.Full)"
        Write-Host "Source resolve call:   $($sourceResolveCall.Address) | $($sourceResolveCall.Full)"
        Write-Host "Source target:         $sourceResolveTarget"
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
        Write-Host "Prep guard:            $($preparationSummary.GuardInstruction.address) | $($preparationSummary.GuardInstruction.full)"
        if ($null -ne $preparationSummary.GuardOffset) {
            Write-Host ("Prep guard off:        0x{0:X}" -f [int]$preparationSummary.GuardOffset)
        }
        if ($preparationScan -and $preparationScan.Found -eq $true) {
            Write-Host "Prep pattern:          $($preparationScan.Address) [$($preparationScan.RelativeOffsetHex)]"
        }
    }
    Write-Host "Coord X read/write:    $($sourceCoordXRead.Address) -> $($destCoordXWrite.Address)"
    Write-Host "Coord Z read/write:    $($sourceCoordZRead.Address) -> $($destCoordZWrite.Address)"
    Write-Host "Suggested pattern:     $sourceChainPattern"
    if ($sourceChainScan.Found -eq $true) {
        Write-Host "Pattern match:         $($sourceChainScan.Address) [$($sourceChainScan.RelativeOffsetHex)]"
    }
}
