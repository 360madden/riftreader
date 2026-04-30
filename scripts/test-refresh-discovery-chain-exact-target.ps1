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

function Assert-Equal {
    param(
        $Actual,
        $Expected,
        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    if ($Actual -ne $Expected) {
        throw ("{0} Expected '{1}', got '{2}'." -f $Message, $Expected, $Actual)
    }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$sourceScript = Join-Path $repoRoot 'scripts\refresh-discovery-chain.ps1'
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('RiftReader-refresh-discovery-chain-target-' + [System.Guid]::NewGuid().ToString('N'))
$tempScript = Join-Path $tempRoot 'refresh-discovery-chain.ps1'
$logFile = Join-Path $tempRoot 'calls.ndjson'

$childScriptNames = @(
    'refresh-readerbridge-export.ps1',
    'capture-player-source-chain.ps1',
    'trace-player-selector-owner.ps1',
    'capture-player-owner-components.ps1',
    'capture-player-owner-graph.ps1',
    'capture-player-source-accessor-family.ps1',
    'capture-player-stat-hub-graph.ps1'
)

$fakeChildScript = @'
[CmdletBinding()]
param(
    [string]$ProcessName,
    [int]$ProcessId,
    [string]$TargetWindowHandle,
    [switch]$RefreshCluster,
    [switch]$RefreshSourceChain,
    [switch]$RefreshSelectorTrace,
    [switch]$RefreshOwnerComponents
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$switches = @(
    $PSBoundParameters.GetEnumerator() |
        Where-Object {
            $_.Value -is [System.Management.Automation.SwitchParameter] -and
            $_.Value.IsPresent
        } |
        ForEach-Object { $_.Key } |
        Sort-Object
)

$entry = [ordered]@{
    Script = Split-Path -Leaf $PSCommandPath
    ProcessName = $ProcessName
    ProcessId = $ProcessId
    TargetWindowHandle = $TargetWindowHandle
    Switches = @($switches)
}

Add-Content -LiteralPath $env:RIFT_READER_FAKE_CHAIN_LOG -Value ($entry | ConvertTo-Json -Compress)
$global:LASTEXITCODE = 0
'@

New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

try {
    Copy-Item -LiteralPath $sourceScript -Destination $tempScript -Force
    foreach ($childName in $childScriptNames) {
        Set-Content -LiteralPath (Join-Path $tempRoot $childName) -Value $fakeChildScript -Encoding UTF8
    }

    $env:RIFT_READER_FAKE_CHAIN_LOG = $logFile

    & pwsh `
        -NoLogo `
        -NoProfile `
        -ExecutionPolicy Bypass `
        -File $tempScript `
        -ProcessName 'rift_x64' `
        -ProcessId 41220 `
        -TargetWindowHandle '0xBD0D94' | Out-Null

    if ($LASTEXITCODE -ne 0) {
        throw "refresh-discovery-chain.ps1 exited with code $LASTEXITCODE."
    }

    Assert-True -Condition (Test-Path -LiteralPath $logFile) -Message 'Expected fake child invocation log to be created.'
    $calls = @(Get-Content -LiteralPath $logFile | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | ForEach-Object { $_ | ConvertFrom-Json })
    Assert-Equal -Actual $calls.Count -Expected 7 -Message 'Expected all discovery-chain child scripts to be invoked.'

    $callsByScript = @{}
    foreach ($call in $calls) {
        $callsByScript[[string]$call.Script] = $call
    }

    function Assert-ChildCall {
        param(
            [Parameter(Mandatory = $true)]
            [string]$ScriptName,
            [string]$ExpectedSwitch
        )

        Assert-True -Condition $callsByScript.ContainsKey($ScriptName) -Message "Expected '$ScriptName' to be invoked."
        $call = $callsByScript[$ScriptName]
        Assert-Equal -Actual ([string]$call.ProcessName) -Expected 'rift_x64' -Message "$ScriptName should receive ProcessName."
        Assert-Equal -Actual ([int]$call.ProcessId) -Expected 41220 -Message "$ScriptName should receive ProcessId."
        Assert-Equal -Actual ([string]$call.TargetWindowHandle) -Expected '0xBD0D94' -Message "$ScriptName should receive TargetWindowHandle."

        $switches = @($call.Switches)
        if ([string]::IsNullOrWhiteSpace($ExpectedSwitch)) {
            Assert-Equal -Actual $switches.Count -Expected 0 -Message "$ScriptName should not receive a refresh switch."
        }
        else {
            Assert-Equal -Actual $switches.Count -Expected 1 -Message "$ScriptName should receive exactly one refresh switch."
            Assert-Equal -Actual ([string]$switches[0]) -Expected $ExpectedSwitch -Message "$ScriptName should receive the expected refresh switch."
        }
    }

    Assert-ChildCall -ScriptName 'refresh-readerbridge-export.ps1' -ExpectedSwitch $null
    Assert-ChildCall -ScriptName 'capture-player-source-chain.ps1' -ExpectedSwitch 'RefreshCluster'
    Assert-ChildCall -ScriptName 'trace-player-selector-owner.ps1' -ExpectedSwitch 'RefreshSourceChain'
    Assert-ChildCall -ScriptName 'capture-player-owner-components.ps1' -ExpectedSwitch 'RefreshSelectorTrace'
    Assert-ChildCall -ScriptName 'capture-player-owner-graph.ps1' -ExpectedSwitch 'RefreshSelectorTrace'
    Assert-ChildCall -ScriptName 'capture-player-source-accessor-family.ps1' -ExpectedSwitch 'RefreshSourceChain'
    Assert-ChildCall -ScriptName 'capture-player-stat-hub-graph.ps1' -ExpectedSwitch 'RefreshOwnerComponents'

    Write-Host 'refresh-discovery-chain exact-target propagation regression check passed.' -ForegroundColor Green
}
finally {
    Remove-Item Env:RIFT_READER_FAKE_CHAIN_LOG -ErrorAction SilentlyContinue
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}
