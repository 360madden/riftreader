[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$prototypeScript = Join-Path $PSScriptRoot 'run-a-to-b-prototype.ps1'

function Assert-Condition {
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

if (-not (Test-Path -LiteralPath $prototypeScript)) {
    throw "Navigation prototype script was not found: $prototypeScript"
}

$text = Get-Content -LiteralPath $prototypeScript -Raw

Assert-Condition `
    -Condition ($text.Contains("`$proofCoordPreflightScript = Join-Path `$repoRoot 'scripts\assert-current-proof-coord-anchor.ps1'")) `
    -Message 'Navigation prototype does not reference assert-current-proof-coord-anchor.ps1.'

Assert-Condition `
    -Condition ($text.Contains('function Assert-ProofCoordMovementPreflight')) `
    -Message 'Navigation prototype does not define the proof-anchor movement preflight guard.'

Assert-Condition `
    -Condition ($text.Contains('[string]$AutoTurnBackendEvidenceFile')) `
    -Message 'Navigation prototype does not expose an auto-turn backend evidence file parameter.'

Assert-Condition `
    -Condition ($text.Contains('function Assert-PromotedAutoTurnBackend')) `
    -Message 'Navigation prototype does not define the promoted auto-turn backend guard.'

$scriptJsonFunctionStart = $text.IndexOf('function Invoke-ScriptJson', [System.StringComparison]::Ordinal)
$proofGuardFunctionStart = $text.IndexOf('function Assert-ProofCoordMovementPreflight', [System.StringComparison]::Ordinal)
Assert-Condition -Condition ($scriptJsonFunctionStart -ge 0 -and $proofGuardFunctionStart -gt $scriptJsonFunctionStart) -Message 'Could not isolate Invoke-ScriptJson.'

$scriptJsonBlock = $text.Substring($scriptJsonFunctionStart, $proofGuardFunctionStart - $scriptJsonFunctionStart)
Assert-Condition -Condition ($scriptJsonBlock.Contains('[switch]$AllowFailureExitCode')) -Message 'Invoke-ScriptJson cannot parse failed proof-anchor JSON without throwing first.'
Assert-Condition -Condition ($scriptJsonBlock.Contains('if ($exitCode -ne 0 -and -not $AllowFailureExitCode)')) -Message 'Invoke-ScriptJson does not honor AllowFailureExitCode.'

$turnFunctionStart = $text.IndexOf('function Invoke-TurnKeyPulse', [System.StringComparison]::Ordinal)
$autoTurnFunctionStart = $text.IndexOf('function Invoke-AutoTurnAlignment', [System.StringComparison]::Ordinal)
Assert-Condition -Condition ($turnFunctionStart -ge 0 -and $autoTurnFunctionStart -gt $turnFunctionStart) -Message 'Could not isolate Invoke-TurnKeyPulse.'

$turnBlock = $text.Substring($turnFunctionStart, $autoTurnFunctionStart - $turnFunctionStart)
$turnGuardIndex = $turnBlock.IndexOf('Assert-ProofCoordMovementPreflight -Reason ("auto-turn-key:{0}" -f $PulseIndex)', [System.StringComparison]::Ordinal)
$turnInputIndex = $turnBlock.IndexOf("Invoke-ProcessText -FilePath 'pwsh' -ArgumentList `$scriptArguments", [System.StringComparison]::Ordinal)
Assert-Condition -Condition ($turnGuardIndex -ge 0) -Message 'Auto-turn key pulse path does not call the proof-anchor preflight guard.'
Assert-Condition -Condition ($turnInputIndex -gt $turnGuardIndex) -Message 'Auto-turn key pulse input can run before the proof-anchor preflight guard.'

$autoTurnFunctionEnd = $text.IndexOf('function Write-NavigationSummary', $autoTurnFunctionStart, [System.StringComparison]::Ordinal)
Assert-Condition -Condition ($autoTurnFunctionEnd -gt $autoTurnFunctionStart) -Message 'Could not isolate Invoke-AutoTurnAlignment.'
$autoTurnBlock = $text.Substring($autoTurnFunctionStart, $autoTurnFunctionEnd - $autoTurnFunctionStart)
$autoTurnBackendGuardIndex = $autoTurnBlock.IndexOf('Assert-PromotedAutoTurnBackend -Key $turnKey -InputMode $inputMode -EvidenceFile $resolvedAutoTurnBackendEvidenceFile', [System.StringComparison]::Ordinal)
$autoTurnPulseIndex = $autoTurnBlock.IndexOf('Invoke-TurnKeyPulse -Key $turnKey', [System.StringComparison]::Ordinal)
Assert-Condition -Condition ($autoTurnBackendGuardIndex -ge 0) -Message 'Auto-turn alignment does not require promoted backend evidence before turning.'
Assert-Condition -Condition ($autoTurnPulseIndex -gt $autoTurnBackendGuardIndex) -Message 'Auto-turn can pulse a key before the promoted backend guard.'

$movementPromptIndex = $text.IndexOf('Wait-ForOperator -Prompt "If the preflight looks correct, press Enter to start movement. Ctrl+C to cancel"', [System.StringComparison]::Ordinal)
$navigateGuardIndex = $text.IndexOf("[void](Assert-ProofCoordMovementPreflight -Reason 'navigate')", [System.StringComparison]::Ordinal)
$navigateInvokeNeedle = '$navigationResult = Invoke-ReaderJson -Arguments $navigationArguments -Step ''navigate'' -AllowFailureExitCode'
$navigateInvokeIndex = $text.IndexOf($navigateInvokeNeedle, [System.StringComparison]::Ordinal)
Assert-Condition -Condition ($movementPromptIndex -ge 0) -Message 'Could not find final movement confirmation prompt.'
Assert-Condition -Condition ($navigateGuardIndex -gt $movementPromptIndex) -Message 'Navigate proof-anchor preflight guard is not after final movement confirmation.'
Assert-Condition -Condition ($navigateInvokeIndex -gt $navigateGuardIndex) -Message 'Navigate command can run before the proof-anchor preflight guard.'

Write-Host 'run-a-to-b proof-anchor movement gate regression passed.' -ForegroundColor Green
