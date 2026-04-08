[CmdletBinding()]
param(
    [switch]$Json,
    [switch]$SkipRefresh,
    [switch]$SkipCleanup,
    [int]$MovementHoldMilliseconds = 1000,
    [int]$TimeoutSeconds = 8,
    [string]$OutputFile = (Join-Path $PSScriptRoot 'captures\player-coord-write-trace.json'),
    [string]$TraceStatusFile = (Join-Path $PSScriptRoot 'captures\player-coord-write-trace.status.txt')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$refreshScript = Join-Path $PSScriptRoot 'refresh-readerbridge-export.ps1'
$postKeyScript = Join-Path $PSScriptRoot 'post-rift-key.ps1'
$ceExecScript = Join-Path $PSScriptRoot 'cheatengine-exec.ps1'
$traceLuaFile = Join-Path $PSScriptRoot 'cheat-engine\RiftReaderWriteTrace.lua'
$resolvedOutputFile = [System.IO.Path]::GetFullPath($OutputFile)
$resolvedStatusFile = [System.IO.Path]::GetFullPath($TraceStatusFile)

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

function Parse-HexAddress {
    param(
        [Parameter(Mandatory = $true)]
        [string]$AddressHex
    )

    $normalized = $AddressHex
    if ($normalized.StartsWith('0x', [System.StringComparison]::OrdinalIgnoreCase)) {
        $normalized = $normalized.Substring(2)
    }

    return [UInt64]::Parse($normalized, [System.Globalization.NumberStyles]::HexNumber, [System.Globalization.CultureInfo]::InvariantCulture)
}

function Convert-ToModulePattern {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ByteText
    )

    $hex = ($ByteText -replace '\s+', '').Trim()
    if ([string]::IsNullOrWhiteSpace($hex) -or ($hex.Length % 2) -ne 0) {
        return $null
    }

    if ($hex -notmatch '^[0-9A-Fa-f]+$') {
        return $null
    }

    $pairs = for ($index = 0; $index -lt $hex.Length; $index += 2) {
        $hex.Substring($index, 2).ToUpperInvariant()
    }

    return ($pairs -join ' ')
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

function Get-CoordTraceResult {
    param(
        [Parameter(Mandatory = $true)]
        [pscustomobject]$PlayerRead
    )

    $baseAddress = Parse-HexAddress -AddressHex $PlayerRead.Memory.AddressHex
    $coordAddress = $baseAddress

    if (Test-Path -LiteralPath $resolvedStatusFile) {
        Remove-Item -LiteralPath $resolvedStatusFile -Force
    }

    & $ceExecScript -LuaFile $traceLuaFile | Out-Null

    $luaCode = @"
return RiftReaderWriteTrace.arm('rift_x64', $coordAddress, 4, [[$resolvedStatusFile]])
"@
    & $ceExecScript -Code $luaCode | Out-Null

    & $postKeyScript -Key 'w' -HoldMilliseconds $MovementHoldMilliseconds

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        if (Test-Path -LiteralPath $resolvedStatusFile) {
            $status = Read-KeyValueFile -Path $resolvedStatusFile
            if ($status.status -eq 'hit') {
                return $status
            }
            if ($status.status -eq 'error') {
                throw "CE trace helper error: $($status.error)"
            }
        }

        Start-Sleep -Milliseconds 200
    }

    if (Test-Path -LiteralPath $resolvedStatusFile) {
        return Read-KeyValueFile -Path $resolvedStatusFile
    }

    throw "Timed out waiting for a coord write trace hit."
}

function Cleanup-Trace {
    if ($SkipCleanup) {
        return
    }

    try {
        & $ceExecScript -Code "return RiftReaderWriteTrace.cleanup()" | Out-Null
    }
    catch {
        Write-Warning ("Unable to clean up the CE trace helper cleanly: {0}" -f $_.Exception.Message)
    }
}

try {
    if (-not $SkipRefresh) {
        & $refreshScript -NoReader
    }

    $playerRead = Invoke-ReaderJson -Arguments @('--process-name', 'rift_x64', '--read-player-current', '--json')
    $traceStatus = Get-CoordTraceResult -PlayerRead $playerRead

    $modulePattern = $null
    $normalizedPattern = $null
    if (-not [string]::IsNullOrWhiteSpace($traceStatus.moduleName) -and -not [string]::IsNullOrWhiteSpace($traceStatus.instructionBytes)) {
        $normalizedPattern = Convert-ToModulePattern -ByteText $traceStatus.instructionBytes
        try {
            if ([string]::IsNullOrWhiteSpace($normalizedPattern)) {
                throw "Unable to normalize instruction bytes '$($traceStatus.instructionBytes)' into an AOB pattern."
            }

            $modulePattern = Invoke-ReaderJson -Arguments @(
                '--process-name', 'rift_x64',
                '--scan-module-pattern', $normalizedPattern,
                '--scan-module-name', $traceStatus.moduleName,
                '--scan-context', '16',
                '--json')
        }
        catch {
            $modulePattern = [pscustomobject]@{
                Mode = 'module-pattern-scan'
                Error = $_.Exception.Message
            }
        }
    }

    $result = [ordered]@{
        Mode = 'player-coord-write-trace'
        GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
        Reader = $playerRead
        Trace = [ordered]@{
            Status = $traceStatus.status
            TargetAddress = $traceStatus.targetAddress
            HitCount = if ($traceStatus.hitCount) { [int]$traceStatus.hitCount } else { 0 }
            InstructionAddress = $traceStatus.rip
            InstructionSymbol = $traceStatus.instructionSymbol
            Instruction = $traceStatus.instruction
            InstructionBytes = $traceStatus.instructionBytes
            NormalizedPattern = $normalizedPattern
            InstructionOpcode = $traceStatus.instructionOpcode
            InstructionExtra = $traceStatus.instructionExtra
            InstructionSize = $traceStatus.instructionSize
            ModuleName = $traceStatus.moduleName
            ModuleBase = $traceStatus.moduleBase
            ModuleOffset = $traceStatus.moduleOffset
            Registers = [ordered]@{
                RAX = $traceStatus.rax
                RBX = $traceStatus.rbx
                RCX = $traceStatus.rcx
                RDX = $traceStatus.rdx
                RSI = $traceStatus.rsi
                RDI = $traceStatus.rdi
                RBP = $traceStatus.rbp
                RSP = $traceStatus.rsp
                R8 = $traceStatus.r8
                R9 = $traceStatus.r9
                R10 = $traceStatus.r10
                R11 = $traceStatus.r11
                R12 = $traceStatus.r12
                R13 = $traceStatus.r13
                R14 = $traceStatus.r14
                R15 = $traceStatus.r15
            }
        }
        ModulePattern = $modulePattern
        OutputFile = $resolvedOutputFile
    }

    $outputDirectory = Split-Path -Parent $resolvedOutputFile
    if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
        New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
    }

    $jsonText = $result | ConvertTo-Json -Depth 10
    Set-Content -Path $resolvedOutputFile -Value $jsonText -Encoding UTF8

    if ($Json) {
        Write-Output $jsonText
    }
    else {
        Write-Host "Trace file:           $resolvedOutputFile"
        Write-Host "Player sample:        $($playerRead.Memory.AddressHex)"
        Write-Host "Coord write target:   $($traceStatus.targetAddress)"
        Write-Host "Writer RIP:           $($traceStatus.rip)"
        Write-Host "Writer symbol:        $($traceStatus.instructionSymbol)"
        Write-Host "Instruction:          $($traceStatus.instruction)"
        Write-Host "Module pattern bytes: $($traceStatus.instructionBytes)"
        if ($modulePattern -and $modulePattern.Found -eq $true) {
            Write-Host "Pattern match:        $($modulePattern.MatchAddress) in $($modulePattern.ModuleName)"
        }
    }
}
finally {
    Cleanup-Trace
}
