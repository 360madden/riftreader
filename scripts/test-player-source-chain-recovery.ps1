[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Assert-True {
    param(
        [Parameter(Mandatory = $true)]
        [bool]$Condition,
        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    if (-not $Condition) {
        throw $Message
    }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$scriptFile = Join-Path $repoRoot 'scripts\capture-player-source-chain.ps1'
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('RiftReader-source-chain-recovery-' + [System.Guid]::NewGuid().ToString('N'))
$clusterFile = Join-Path $tempRoot 'player-coord-trace-cluster.json'
$outputFile = Join-Path $tempRoot 'player-source-chain.json'

New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

$clusterDocument = [ordered]@{
    Anchor = [ordered]@{
        ProcessId = 1234
        ProcessName = 'rift_x64'
        InstructionAddress = '0x7FF700001234'
        SourceObjectAddress = '0x1234567890'
        SourceObjectRegister = 'RDI'
        SourceObjectRegisterValue = '0x1234567890'
    }
    SuggestedClusterScan = $null
    Instructions = @(
        [ordered]@{
            Index = 0
            Address = '0x7FF700001234'
            Opcode = 'mov eax,[r8+rcx*4+04]'
            Full = '0x7FF700001234 - mov eax,[r8+rcx*4+04]'
        }
    )
}

$previousSourceChain = [ordered]@{
    Mode = 'player-source-chain'
    GeneratedAtUtc = '2026-04-22T05:35:08.9568729-04:00'
    ProcessId = 1234
    ProcessName = 'rift_x64'
    SourceObjectAddress = '0xCAFEBABE'
    SelectedSourceAddress = '0xCAFEBABE'
    SourceChain = [ordered]@{
        SourceObjectLoad = [ordered]@{
            Address = '0x7FF70000AAAA'
            Full = '0x7FF70000AAAA - mov rdi,[rcx+rdx*8]'
        }
        SourceResolveCall = [ordered]@{
            Address = '0x7FF70000BBBB'
            Full = '0x7FF70000BBBB - call 0x7FF70000CCCC'
        }
        SourceResolveTarget = '0x7FF70000CCCC'
        SourceCoordXRead = [ordered]@{
            Address = '0x7FF70000DDDD'
        }
        DestinationCoordXWrite = [ordered]@{
            Address = '0x7FF70000EEEE'
        }
        SourceCoordZRead = [ordered]@{
            Address = '0x7FF70000FFFF'
        }
        DestinationCoordZWrite = [ordered]@{
            Address = '0x7FF700001111'
        }
    }
    Accessor = [ordered]@{
        FunctionStart = '0x7FF70000CCCC'
        ReturnLea = [ordered]@{
            Address = '0x7FF700002222'
            Full = '0x7FF700002222 - lea rax,[rbx+48]'
        }
        ReturnOffset = 72
    }
    AccessorInstructions = @()
    SuggestedAccessorPattern = '40 53'
    SuggestedAccessorScan = [ordered]@{
        Found = $true
        Address = '0x7FF70000CCCC'
        RelativeOffsetHex = '0x00CCCC'
    }
    Preparation = [ordered]@{
        FunctionStart = '0x7FF700003333'
        GuardInstruction = [ordered]@{
            address = '0x7FF700003334'
            full = '0x7FF700003334 - cmp qword ptr [rcx+00000100],00'
        }
        GuardOffset = 256
    }
    SuggestedPreparationPattern = $null
    SuggestedPreparationScan = $null
    SuggestedSourceChainPattern = $null
    SuggestedSourceChainScan = $null
}

Set-Content -LiteralPath $clusterFile -Value ($clusterDocument | ConvertTo-Json -Depth 10) -Encoding UTF8
Set-Content -LiteralPath $outputFile -Value ($previousSourceChain | ConvertTo-Json -Depth 10) -Encoding UTF8

try {
    $resultJson = & pwsh `
        -NoLogo `
        -NoProfile `
        -ExecutionPolicy Bypass `
        -File $scriptFile `
        -Json `
        -ClusterFile $clusterFile `
        -OutputFile $outputFile

    if ($LASTEXITCODE -ne 0) {
        throw "capture-player-source-chain.ps1 exited with code $LASTEXITCODE."
    }

    $result = $resultJson | ConvertFrom-Json -Depth 20
    Assert-True -Condition ($result.Recovery.Mode -eq 'reuse-previous-source-chain') -Message 'Expected same-session source-chain recovery mode.'
    Assert-True -Condition ($null -eq $result.ClusterSummary.ClusterPatternAddress) -Message 'Expected ClusterPatternAddress to stay null when SuggestedClusterScan is null.'
    Assert-True -Condition ($null -eq $result.ClusterSummary.ClusterPatternOffset) -Message 'Expected ClusterPatternOffset to stay null when SuggestedClusterScan is null.'
    Assert-True -Condition ($result.SourceChain.SourceResolveTarget -eq '0x7FF70000CCCC') -Message 'Expected previous source-chain target to be reused.'
    Assert-True -Condition ($result.Recovery.Reason -match 'source container load') -Message 'Expected recovery reason to capture the missing source-container signature.'

    Write-Host 'capture-player-source-chain recovery regression check passed.' -ForegroundColor Green
}
finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}
