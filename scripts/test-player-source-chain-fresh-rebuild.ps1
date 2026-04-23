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
$sourceScript = Join-Path $repoRoot 'scripts\capture-player-source-chain.ps1'
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('RiftReader-source-chain-fresh-rebuild-' + [System.Guid]::NewGuid().ToString('N'))
$tempScriptsRoot = Join-Path $tempRoot 'scripts'
$tempReaderRoot = Join-Path $tempRoot 'reader\RiftReader.Reader'
$tempCheatEngineRoot = Join-Path $tempScriptsRoot 'cheat-engine'
$capturesRoot = Join-Path $tempScriptsRoot 'captures'
$clusterFile = Join-Path $capturesRoot 'player-coord-trace-cluster.json'
$outputFile = Join-Path $capturesRoot 'player-source-chain.json'
$tempScriptFile = Join-Path $tempScriptsRoot 'capture-player-source-chain.ps1'
$fakeCeExecFile = Join-Path $tempScriptsRoot 'cheatengine-exec.ps1'
$fakeClusterLuaFile = Join-Path $tempCheatEngineRoot 'RiftReaderDisasmCluster.lua'
$fakeProjectFile = Join-Path $tempReaderRoot 'RiftReader.Reader.csproj'
$shimDirectory = Join-Path $tempRoot 'shim'
$fakeDotnetPath = Join-Path $shimDirectory 'dotnet.cmd'

New-Item -ItemType Directory -Path $tempScriptsRoot -Force | Out-Null
New-Item -ItemType Directory -Path $tempReaderRoot -Force | Out-Null
New-Item -ItemType Directory -Path $tempCheatEngineRoot -Force | Out-Null
New-Item -ItemType Directory -Path $capturesRoot -Force | Out-Null
New-Item -ItemType Directory -Path $shimDirectory -Force | Out-Null

Copy-Item -LiteralPath $sourceScript -Destination $tempScriptFile -Force
Set-Content -LiteralPath $fakeClusterLuaFile -Value '-- shim' -Encoding ASCII
Set-Content -LiteralPath $fakeProjectFile -Value '<Project Sdk="Microsoft.NET.Sdk" />' -Encoding ASCII

$fakeCeExecContent = @'
param(
    [string]$Code,
    [string]$LuaFile,
    [UInt64]$Parameter = 0,
    [string]$PipeName = "RiftReader",
    [switch]$Async
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-DisasmTsv {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [object[]]$Rows
    )

    $directory = Split-Path -Parent $Path
    if (-not [string]::IsNullOrWhiteSpace($directory)) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }

    $header = "index`taddress`tbytes`topcode`textra`tfull"
    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add($header) | Out-Null
    foreach ($row in $Rows) {
        $lines.Add(("{0}`t{1}`t{2}`t{3}`t{4}`t{5}" -f $row.index, $row.address, $row.bytes, $row.opcode, $row.extra, $row.full)) | Out-Null
    }

    Set-Content -LiteralPath $Path -Value $lines -Encoding ASCII
}

if (-not [string]::IsNullOrWhiteSpace($LuaFile)) {
    Write-Output 1
    exit 0
}

if ([string]::IsNullOrWhiteSpace($Code)) {
    throw 'Expected -Code or -LuaFile.'
}

$match = [regex]::Match($Code, '\[\[(?<path>.*?)\]\]')
if (-not $match.Success) {
    throw "Unable to extract output path from fake CE code: $Code"
}

$outputPath = $match.Groups['path'].Value

if ($outputPath -like '*.fresh-source-chain.accessor.tsv') {
    Write-DisasmTsv -Path $outputPath -Rows @(
        @{ index = 0; address = '7FF70000BBBB'; bytes = '40 53'; opcode = 'push rbx'; extra = ''; full = '7FF70000BBBB - 40 53 - push rbx' }
        @{ index = 1; address = '7FF70000BBBD'; bytes = '48 83 EC 20'; opcode = 'sub rsp,20'; extra = ''; full = '7FF70000BBBD - 48 83 EC 20 - sub rsp,20' }
        @{ index = 2; address = '7FF70000BBC1'; bytes = '48 8B D9'; opcode = 'mov rbx,rcx'; extra = ''; full = '7FF70000BBC1 - 48 8B D9  - mov rbx,rcx' }
        @{ index = 3; address = '7FF70000BBC4'; bytes = 'E8 37000000'; opcode = 'call 7FF70000CCCC'; extra = ''; full = '7FF70000BBC4 - E8 37000000 - call 7FF70000CCCC' }
        @{ index = 4; address = '7FF70000BBC9'; bytes = '48 8D 43 48'; opcode = 'lea rax,[rbx+48]'; extra = ''; full = '7FF70000BBC9 - 48 8D 43 48  - lea rax,[rbx+48]' }
        @{ index = 5; address = '7FF70000BBCD'; bytes = '48 83 C4 20'; opcode = 'add rsp,20'; extra = ''; full = '7FF70000BBCD - 48 83 C4 20 - add rsp,20' }
        @{ index = 6; address = '7FF70000BBD1'; bytes = '5B'; opcode = 'pop rbx'; extra = ''; full = '7FF70000BBD1 - 5B - pop rbx' }
        @{ index = 7; address = '7FF70000BBD2'; bytes = 'C3'; opcode = 'ret '; extra = ''; full = '7FF70000BBD2 - C3 - ret ' }
    )
}
elseif ($outputPath -like '*.fresh-source-chain.preparation.tsv') {
    Write-DisasmTsv -Path $outputPath -Rows @(
        @{ index = 0; address = '7FF70000CCCC'; bytes = '48 8B F9'; opcode = 'mov rdi,rcx'; extra = ''; full = '7FF70000CCCC - 48 8B F9 - mov rdi,rcx' }
        @{ index = 1; address = '7FF70000CCCF'; bytes = '48 83 B9 00010000 00'; opcode = 'cmp qword ptr [rcx+00000100],00'; extra = ''; full = '7FF70000CCCF - 48 83 B9 00010000 00 - cmp qword ptr [rcx+00000100],00' }
    )
}
elseif ($outputPath -like '*.fresh-source-chain.tsv') {
    Write-DisasmTsv -Path $outputPath -Rows @(
        @{ index = 0; address = '7FF70000AAA0'; bytes = '84 C0'; opcode = 'test al,al'; extra = ''; full = '7FF70000AAA0 - 84 C0  - test al,al' }
        @{ index = 1; address = '7FF70000AAA2'; bytes = '0F84 04010000'; opcode = 'je 7FF70000ABAC'; extra = ''; full = '7FF70000AAA2 - 0F84 04010000 - je 7FF70000ABAC' }
        @{ index = 2; address = '7FF70000AAA8'; bytes = '48 8B 45 90'; opcode = 'mov rax,[rbp-70]'; extra = ''; full = '7FF70000AAA8 - 48 8B 45 90  - mov rax,[rbp-70]' }
        @{ index = 3; address = '7FF70000AAAC'; bytes = '0F B6 54 01 18'; opcode = 'movzx edx,byte ptr [rcx+rax+18]'; extra = ''; full = '7FF70000AAAC - 0F B6 54 01 18  - movzx edx,byte ptr [rcx+rax+18]' }
        @{ index = 4; address = '7FF70000AAB1'; bytes = '48 8B 48 78'; opcode = 'mov rcx,[rax+78]'; extra = ''; full = '7FF70000AAB1 - 48 8B 48 78  - mov rcx,[rax+78]' }
        @{ index = 5; address = '7FF70000AAB5'; bytes = '48 8B 3C D1'; opcode = 'mov rdi,[rcx+rdx*8]'; extra = ''; full = '7FF70000AAB5 - 48 8B 3C D1   - mov rdi,[rcx+rdx*8]' }
        @{ index = 6; address = '7FF70000AAB9'; bytes = '48 85 FF'; opcode = 'test rdi,rdi'; extra = ''; full = '7FF70000AAB9 - 48 85 FF  - test rdi,rdi' }
        @{ index = 7; address = '7FF70000AABC'; bytes = '0F84 D8000000'; opcode = 'je 7FF70000AB9A'; extra = ''; full = '7FF70000AABC - 0F84 D8000000 - je 7FF70000AB9A' }
        @{ index = 8; address = '7FF70000AAC2'; bytes = '48 8B CF'; opcode = 'mov rcx,rdi'; extra = ''; full = '7FF70000AAC2 - 48 8B CF  - mov rcx,rdi' }
        @{ index = 9; address = '7FF70000AAC5'; bytes = 'E8 F1000000'; opcode = 'call 7FF70000BBBB'; extra = ''; full = '7FF70000AAC5 - E8 F1000000 - call 7FF70000BBBB' }
        @{ index = 10; address = '7FF70000AACA'; bytes = '48 8B CF'; opcode = 'mov rcx,rdi'; extra = ''; full = '7FF70000AACA - 48 8B CF  - mov rcx,rdi' }
        @{ index = 11; address = '7FF70000AACD'; bytes = 'F2 0F10 00'; opcode = 'movsd xmm0,[rax]'; extra = ''; full = '7FF70000AACD - F2 0F10 00  - movsd xmm0,[rax]' }
        @{ index = 12; address = '7FF70000AAD1'; bytes = 'F2 0F11 86 58010000'; opcode = 'movsd [rsi+00000158],xmm0'; extra = ''; full = '7FF70000AAD1 - F2 0F11 86 58010000  - movsd [rsi+00000158],xmm0' }
        @{ index = 13; address = '7FF70000AAD9'; bytes = '8B 40 08'; opcode = 'mov eax,[rax+08]'; extra = ''; full = '7FF70000AAD9 - 8B 40 08  - mov eax,[rax+08]' }
        @{ index = 14; address = '7FF70000AADC'; bytes = '89 86 60010000'; opcode = 'mov [rsi+00000160],eax'; extra = ''; full = '7FF70000AADC - 89 86 60010000  - mov [rsi+00000160],eax' }
    )
}
else {
    throw "Unhandled fake CE output path: $outputPath"
}

Write-Output 1
'@
Set-Content -LiteralPath $fakeCeExecFile -Value $fakeCeExecContent -Encoding UTF8

$fakeDotnetJson = @'
{
  "Mode": "module-pattern-scan",
  "ProcessId": 1234,
  "ProcessName": "rift_x64",
  "ModuleName": "rift_x64.exe",
  "ModuleFileName": "C:\\fake\\rift_x64.exe",
  "ModuleBaseAddress": "0x7FF700000000",
  "ModuleMemorySize": 16777216,
  "Pattern": "shim",
  "Found": true,
  "RelativeOffset": 43680,
  "RelativeOffsetHex": "0xAAA0",
  "Address": "0x7FF70000AAA0",
  "ContextBytes": 0
}
'@
$fakeDotnetLines = @('@echo off', 'setlocal')
$fakeDotnetLines += ($fakeDotnetJson.Trim().Split("`n") | ForEach-Object { 'echo ' + $_.TrimEnd("`r") })
$fakeDotnetLines += 'exit /b 0'
Set-Content -LiteralPath $fakeDotnetPath -Value $fakeDotnetLines -Encoding ASCII

$clusterDocument = [ordered]@{
    Anchor = [ordered]@{
        ProcessId = 1234
        ProcessName = 'rift_x64'
        InstructionAddress = '0x7FF700001234'
        SourceObjectAddress = '0x1111111111'
        SourceObjectRegister = 'RDI'
        SourceObjectRegisterValue = '0x1111111111'
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
    GeneratedAtUtc = '2026-04-23T00:00:00Z'
    ProcessId = 1234
    ProcessName = 'rift_x64'
    SuggestedSourceChainPattern = '48 8B 48 78 48 8B 3C D1 48 85 FF 0F 84 ?? ?? ?? ?? 48 8B CF E8 ?? ?? ?? ?? 48 8B CF F2 0F 10 00 F2 0F 11 86 58 01 00 00 8B 40 08 89 86 60 01 00 00'
    Accessor = [ordered]@{
        FunctionStart = '0x7FF70000BBBB'
    }
    Preparation = [ordered]@{
        FunctionStart = '0x7FF70000CCCC'
    }
}

Set-Content -LiteralPath $clusterFile -Value ($clusterDocument | ConvertTo-Json -Depth 10) -Encoding UTF8
Set-Content -LiteralPath $outputFile -Value ($previousSourceChain | ConvertTo-Json -Depth 10) -Encoding UTF8

$originalPath = $env:PATH

try {
    $env:PATH = "$shimDirectory;$originalPath"

    $resultJson = & pwsh `
        -NoLogo `
        -NoProfile `
        -ExecutionPolicy Bypass `
        -File $tempScriptFile `
        -Json `
        -ClusterFile $clusterFile `
        -OutputFile $outputFile

    if ($LASTEXITCODE -ne 0) {
        throw "capture-player-source-chain.ps1 exited with code $LASTEXITCODE."
    }

    $result = $resultJson | ConvertFrom-Json -Depth 30
    Assert-True -Condition ($result.Recovery.Mode -eq 'rebuild-from-suggested-source-chain-pattern') -Message 'Expected fresh source-chain rebuild recovery mode.'
    Assert-True -Condition ($result.Recovery.PatternScanAddress -eq '0x7FF70000AAA0') -Message 'Expected fresh pattern scan address to be preserved.'
    Assert-True -Condition ($result.SourceChain.SourceObjectLoad.Address -eq '7FF70000AAB5') -Message 'Expected fresh rebuilt source-object load to come from the new disassembly cluster.'
    Assert-True -Condition ($result.SourceChain.SourceResolveTarget -eq '7FF70000BBBB') -Message 'Expected fresh rebuilt source resolve target.'
    Assert-True -Condition ($result.Accessor.FunctionStart -eq '7FF70000BBBB') -Message 'Expected fresh rebuilt accessor function start.'
    Assert-True -Condition ($null -eq $result.ClusterSummary.ClusterPatternAddress) -Message 'Expected null-safe cluster summary preservation.'

    Write-Host 'capture-player-source-chain fresh rebuild regression check passed.' -ForegroundColor Green
}
finally {
    $env:PATH = $originalPath
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}
