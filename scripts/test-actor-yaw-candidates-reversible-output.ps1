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
$sourceScript = Join-Path $repoRoot 'scripts\test-actor-yaw-candidates.ps1'
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('RiftReader-yaw-candidates-reversible-' + [System.Guid]::NewGuid().ToString('N'))
$tempScriptsRoot = Join-Path $tempRoot 'scripts'
$tempReaderRoot = Join-Path $tempRoot 'reader\RiftReader.Reader'
$capturesRoot = Join-Path $tempScriptsRoot 'captures'
$shimDirectory = Join-Path $tempRoot 'shim'
$tempScriptFile = Join-Path $tempScriptsRoot 'test-actor-yaw-candidates.ps1'
$candidateScreenFile = Join-Path $capturesRoot 'candidate-screen.json'
$jsonOutputFile = Join-Path $capturesRoot 'yaw-output-json.json'
$textOutputFile = Join-Path $capturesRoot 'yaw-output-text.json'
$fakeProjectFile = Join-Path $tempReaderRoot 'RiftReader.Reader.csproj'
$fakeDotnetCmd = Join-Path $shimDirectory 'dotnet.cmd'
$fakeDotnetPs1 = Join-Path $shimDirectory 'dotnet.ps1'

New-Item -ItemType Directory -Path $tempScriptsRoot -Force | Out-Null
New-Item -ItemType Directory -Path $tempReaderRoot -Force | Out-Null
New-Item -ItemType Directory -Path $capturesRoot -Force | Out-Null
New-Item -ItemType Directory -Path $shimDirectory -Force | Out-Null

try {
    Copy-Item -LiteralPath $sourceScript -Destination $tempScriptFile -Force
    Set-Content -LiteralPath $fakeProjectFile -Value '<Project Sdk="Microsoft.NET.Sdk" />' -Encoding UTF8

    $candidateScreen = [ordered]@{
        Mode = 'actor-orientation-candidate-screen'
        GeneratedAtUtc = '2026-04-30T00:00:00.0000000+00:00'
        Results = @(
            [ordered]@{
                Rank = 1
                SourceAddress = '0x100000'
                BasisForwardOffset = '0x60'
                DiscoveryMode = 'test-fixture'
                ParentAddress = '0x0'
                RootAddress = '0x100000'
                SearchScore = 100
            }
        )
    }
    Set-Content -LiteralPath $candidateScreenFile -Value ($candidateScreen | ConvertTo-Json -Depth 10) -Encoding UTF8

    $fakeDotnetScript = @'
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Arguments
)

$ErrorActionPreference = 'Stop'

if ($Arguments -contains '--read-player-current') {
    [pscustomobject]@{
        Mode = 'player-current-read'
        Memory = [pscustomobject]@{
            CoordX = 1.0
            CoordY = 2.0
            CoordZ = 3.0
        }
    } | ConvertTo-Json -Depth 8
    exit 0
}

if ($Arguments -contains '--address') {
    $bytes = New-Object byte[] 384

    function Write-Single {
        param(
            [Parameter(Mandatory = $true)]
            [int]$Offset,
            [Parameter(Mandatory = $true)]
            [single]$Value
        )

        [BitConverter]::GetBytes($Value).CopyTo($bytes, $Offset)
    }

    Write-Single -Offset 0x60 -Value 1.0
    Write-Single -Offset 0x64 -Value 0.0
    Write-Single -Offset 0x68 -Value 0.0
    Write-Single -Offset 0x6C -Value 0.0
    Write-Single -Offset 0x70 -Value 1.0
    Write-Single -Offset 0x74 -Value 0.0
    Write-Single -Offset 0x78 -Value 0.0
    Write-Single -Offset 0x7C -Value 0.0
    Write-Single -Offset 0x80 -Value 1.0

    [pscustomobject]@{
        BytesHex = -join ($bytes | ForEach-Object { $_.ToString('X2', [System.Globalization.CultureInfo]::InvariantCulture) })
    } | ConvertTo-Json -Depth 4
    exit 0
}

Write-Error ("Unexpected fake dotnet invocation: {0}" -f ($Arguments -join ' '))
exit 1
'@
    Set-Content -LiteralPath $fakeDotnetPs1 -Value $fakeDotnetScript -Encoding UTF8
    Set-Content -LiteralPath $fakeDotnetCmd -Value @"
@echo off
pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0dotnet.ps1" %*
exit /b %ERRORLEVEL%
"@ -Encoding ASCII

    $oldPath = $env:PATH
    $env:PATH = "$shimDirectory;$oldPath"
    try {
        $jsonRunOutput = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $tempScriptFile `
            -CandidateScreenFile $candidateScreenFile `
            -OutputFile $jsonOutputFile `
            -TopCount 1 `
            -SkipStimulus `
            -Json 2>&1
        Assert-True -Condition ($LASTEXITCODE -eq 0) -Message ("JSON yaw candidate run failed: {0}" -f ($jsonRunOutput -join [Environment]::NewLine))

        $document = Get-Content -LiteralPath $jsonOutputFile -Raw | ConvertFrom-Json -Depth 80
        $result = @($document.Results)[0]
        Assert-True -Condition ($null -ne $result) -Message 'Yaw candidate output did not contain a result row.'
        Assert-True -Condition ($null -ne $result.PSObject.Properties['Reversible']) -Message 'Yaw candidate result row did not include the Reversible property.'
        Assert-True -Condition ($null -eq $result.Reversible) -Message 'Single-pass yaw candidate run should emit Reversible=null.'
        Assert-True -Condition (-not [bool]$result.TruthLike) -Message 'No-stimulus fixture should not be truth-like.'

        $textRunOutput = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $tempScriptFile `
            -CandidateScreenFile $candidateScreenFile `
            -OutputFile $textOutputFile `
            -TopCount 1 `
            -SkipStimulus 2>&1
        Assert-True -Condition ($LASTEXITCODE -eq 0) -Message ("Text yaw candidate run failed: {0}" -f ($textRunOutput -join [Environment]::NewLine))
        Assert-True -Condition (([string]::Join([Environment]::NewLine, $textRunOutput)) -match 'reversible=') -Message 'Human-readable yaw candidate output did not include reversible=.'
    }
    finally {
        $env:PATH = $oldPath
    }
}
finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}

Write-Host 'actor yaw candidate reversible output regression check passed.' -ForegroundColor Green
