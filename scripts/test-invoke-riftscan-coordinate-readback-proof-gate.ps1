[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Assert-Contains {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Text,

        [Parameter(Mandatory = $true)]
        [string]$Needle,

        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    if (-not $Text.Contains($Needle)) {
        throw $Message
    }
}

function Assert-NotContains {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Text,

        [Parameter(Mandatory = $true)]
        [string]$Needle,

        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    if ($Text.Contains($Needle)) {
        throw $Message
    }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$wrapper = Join-Path $repoRoot 'scripts\invoke-riftscan-coordinate-readback.ps1'
$scriptText = Get-Content -LiteralPath $wrapper -Raw

Assert-Contains `
    -Text $scriptText `
    -Needle "assert-current-proof-coord-anchor.ps1" `
    -Message 'Readback wrapper must use the hard no-CE proof-anchor preflight gate.'

Assert-Contains `
    -Text $scriptText `
    -Needle "ProofAnchorMaxAgeSeconds" `
    -Message 'Readback wrapper must expose an explicit proof-anchor max-age gate.'

Assert-Contains `
    -Text $scriptText `
    -Needle 'MovementAllowed = $proofAnchorMovementAllowed' `
    -Message 'Readback summary must surface the proof-anchor movement gate result.'

Assert-Contains `
    -Text $scriptText `
    -Needle 'ProofAnchorMovementAllowed = $proofAnchorMovementAllowed' `
    -Message 'Readback summary must include explicit proof-anchor movement status.'

Assert-Contains `
    -Text $scriptText `
    -Needle 'ProofAnchorCandidateReadback = $proofAnchorCandidateReadback' `
    -Message 'Readback summary must tie the proof-anchor candidate to the current decoded readback.'

Assert-Contains `
    -Text $scriptText `
    -Needle 'proof-anchor-preflight-validated-current-readback' `
    -Message 'Readback summary must distinguish current readback support from metadata-only proof preflight.'

Assert-Contains `
    -Text $scriptText `
    -Needle 'satisfied_by_current_process_proof_coord_anchor_preflight' `
    -Message 'Readback summary must record when the current-process proof gate is satisfied.'

Assert-Contains `
    -Text $scriptText `
    -Needle "Movement:        no input sent" `
    -Message 'Human output must not report movement as blocked when this wrapper only performed readback.'

Assert-NotContains `
    -Text $scriptText `
    -Needle "'-SkipRefresh'" `
    -Message 'Readback wrapper must not call the legacy resolver with -SkipRefresh for proof-gate status.'

Write-Host 'RiftScan readback proof-gate regression passed.' -ForegroundColor Green
