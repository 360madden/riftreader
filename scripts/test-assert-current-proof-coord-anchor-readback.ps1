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
$scriptPath = Join-Path $repoRoot 'scripts\assert-current-proof-coord-anchor-readback.ps1'
$scriptText = Get-Content -LiteralPath $scriptPath -Raw

Assert-Contains `
    -Text $scriptText `
    -Needle "assert-current-proof-coord-anchor.ps1" `
    -Message 'Readback proof script must gate on the current no-CE proof-anchor preflight.'

Assert-Contains `
    -Text $scriptText `
    -Needle "'--pid'" `
    -Message 'Readback proof script must attach the Reader session to the exact resolved PID.'

Assert-Contains `
    -Text $scriptText `
    -Needle "'--record-session'" `
    -Message 'Readback proof script must use the Reader record-session path for memory-only samples.'

Assert-Contains `
    -Text $scriptText `
    -Needle "MovementSent = `$false" `
    -Message 'Readback proof script must mark that it sends no movement.'

Assert-Contains `
    -Text $scriptText `
    -Needle "NoCheatEngine = `$true" `
    -Message 'Readback proof script must mark the no-CE invariant.'

Assert-Contains `
    -Text $scriptText `
    -Needle "SavedVariables are not used as live truth." `
    -Message 'Readback proof script must explicitly avoid SavedVariables live truth.'

Assert-Contains `
    -Text $scriptText `
    -Needle "proof-anchor-current-readback" `
    -Message 'Readback proof script must publish a distinct canonical current-readback source.'

Assert-Contains `
    -Text $scriptText `
    -Needle "CandidateOffsetInRegion" `
    -Message 'Readback proof script must decode the coordinate triplet from the anchor candidate offset.'

Assert-Contains `
    -Text $scriptText `
    -Needle "StableAcrossReadbackSamples" `
    -Message 'Readback proof script must require stability across no-input samples.'

Assert-Contains `
    -Text $scriptText `
    -Needle "Movement:        no input sent" `
    -Message 'Human output must make the no-input behavior explicit.'

Assert-NotContains `
    -Text $scriptText `
    -Needle "cheatengine-exec.ps1" `
    -Message 'Readback proof script must not call Cheat Engine helper scripts.'

Assert-NotContains `
    -Text $scriptText `
    -Needle "'-SkipRefresh'" `
    -Message 'Readback proof script must not use the legacy resolver SkipRefresh path directly.'

Assert-NotContains `
    -Text $scriptText `
    -Needle "post-rift-key.ps1" `
    -Message 'Readback proof script must not invoke key-input helpers.'

Assert-NotContains `
    -Text $scriptText `
    -Needle "ReaderBridgeExport.lua" `
    -Message 'Readback proof script must not consume SavedVariables as live coordinate truth.'

Write-Host 'Proof coord anchor current-readback regression passed.' -ForegroundColor Green
