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
$validatorScript = Join-Path $repoRoot 'scripts\validate-current-actor-yaw-restart-check.ps1'
$packetFile = Join-Path $repoRoot 'docs\recovery\current-actor-yaw-restart-check.json'
$leadFile = Join-Path $repoRoot 'scripts\actor-facing-behavior-backed-lead.json'
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('RiftReader-current-actor-yaw-restart-validator-' + [System.Guid]::NewGuid().ToString('N'))
$badPacketFile = Join-Path $tempRoot 'current-actor-yaw-restart-check.bad.json'
$badMovementGateFile = Join-Path $tempRoot 'current-actor-yaw-restart-check.bad-movement-gate.json'

New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

try {
    $passOutput = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $validatorScript -PacketFile $packetFile -LeadFile $leadFile -Json 2>&1
    Assert-True -Condition ($LASTEXITCODE -eq 0) -Message ("Expected restart packet validation to pass: {0}" -f ($passOutput -join [Environment]::NewLine))
    $passResult = ($passOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 80
    Assert-Equal -Actual ([string]$passResult.status) -Expected 'pass' -Message 'Restart packet validation status mismatch.'

    $badPacket = Get-Content -LiteralPath $packetFile -Raw | ConvertFrom-Json -Depth 80
    $badPacket.actorFacing.sourceAddress = '0xDEADBEEF'
    Set-Content -LiteralPath $badPacketFile -Value ($badPacket | ConvertTo-Json -Depth 80) -Encoding UTF8

    $badOutput = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $validatorScript -PacketFile $badPacketFile -LeadFile $leadFile -Json 2>&1
    Assert-True -Condition ($LASTEXITCODE -ne 0) -Message 'Expected mismatched source address validation to fail.'
    $badResult = ($badOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 80
    Assert-Equal -Actual ([string]$badResult.status) -Expected 'fail' -Message 'Mismatched source address status mismatch.'
    Assert-True -Condition (@($badResult.failures | Where-Object { $_ -like '*sourceAddress does not match lead*' }).Count -gt 0) -Message 'Mismatched source validation did not report the lead mismatch.'

    $badMovementGatePacket = Get-Content -LiteralPath $packetFile -Raw | ConvertFrom-Json -Depth 80
    $badMovementGatePacket.movementGate.activeMovementAllowed = $true
    Set-Content -LiteralPath $badMovementGateFile -Value ($badMovementGatePacket | ConvertTo-Json -Depth 80) -Encoding UTF8

    $badMovementGateOutput = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $validatorScript -PacketFile $badMovementGateFile -LeadFile $leadFile -Json 2>&1
    Assert-True -Condition ($LASTEXITCODE -ne 0) -Message 'Expected unsafe movement gate validation to fail.'
    $badMovementGateResult = ($badMovementGateOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 80
    Assert-Equal -Actual ([string]$badMovementGateResult.status) -Expected 'fail' -Message 'Unsafe movement gate status mismatch.'
    Assert-True -Condition (@($badMovementGateResult.failures | Where-Object { $_ -like '*activeMovementAllowed must be false*' }).Count -gt 0) -Message 'Unsafe movement gate validation did not report the movement gate failure.'
}
finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}

Write-Host 'current actor-yaw restart packet validator regression check passed.' -ForegroundColor Green
