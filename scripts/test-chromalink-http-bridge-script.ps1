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
$script = Join-Path $repoRoot 'scripts\test-chromalink-http-bridge.ps1'

$output = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $script `
    -BaseUrl 'http://127.0.0.1:1' `
    -WaitSeconds 0 `
    -RequestTimeoutSeconds 1 `
    -SkipContractCheck `
    -Json 2>&1

Assert-True -Condition ($LASTEXITCODE -ne 0) -Message 'Expected unavailable bridge readiness check to fail.'
$result = ($output -join [Environment]::NewLine) | ConvertFrom-Json -Depth 32
Assert-Equal -Actual ([string]$result.status) -Expected 'unavailable' -Message 'Unavailable status mismatch.'
Assert-Equal -Actual ([bool]$result.apiReachable) -Expected $false -Message 'apiReachable mismatch.'
Assert-True -Condition (@($result.failures).Count -gt 0) -Message 'Expected at least one failure.'

Write-Host 'ChromaLink HTTP bridge readiness regression check passed.' -ForegroundColor Green
