[CmdletBinding()]
param(
    [switch]$Json,
    [string]$ActorFacingSampleFile = (Join-Path $PSScriptRoot 'captures\player-actor-facing.json'),
    [string]$ValidationHistoryFile = (Join-Path $PSScriptRoot 'captures\actor-facing-validation-history.ndjson'),
    [string]$OutputFile = (Join-Path $PSScriptRoot 'captures\navigation-facing-contract.json')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'actor-facing-common.ps1')

$resolvedActorFacingSampleFile = [System.IO.Path]::GetFullPath($ActorFacingSampleFile)
$resolvedValidationHistoryFile = [System.IO.Path]::GetFullPath($ValidationHistoryFile)
$resolvedOutputFile = [System.IO.Path]::GetFullPath($OutputFile)
$thresholds = Get-ActorFacingThresholds

function Format-Nullable {
    param(
        $Value,
        [string]$Format = '0.000'
    )

    if ($null -eq $Value) {
        return 'n/a'
    }

    return ([double]$Value).ToString($Format, [System.Globalization.CultureInfo]::InvariantCulture)
}

function Write-ContractText {
    param($Document)

    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add('Navigation facing contract')
    $lines.Add("Output file:                 $($Document.OutputFile)")
    $lines.Add("Generated (UTC):             $($Document.GeneratedAtUtc)")
    $lines.Add("Status:                      $($Document.Status)")
    $lines.Add("Source name/address:         $($Document.AuthoritativeSourceName) / $(if ($Document.SourceAddress) { $Document.SourceAddress } else { 'n/a' })")
    $lines.Add("Forward row offset:          $(if ($Document.AuthoritativeForwardRowOffset) { $Document.AuthoritativeForwardRowOffset } else { 'n/a' })")
    $lines.Add("Resolution mode:             $(if ($Document.ResolutionMode) { $Document.ResolutionMode } else { 'n/a' })")
    $lines.Add("Yaw formula:                 $($Document.YawFormula)")
    $lines.Add("Pitch formula:               $($Document.PitchFormula)")
    $lines.Add("Planar projection:           $($Document.PlanarProjectionFormula)")
    $lines.Add("Turn error formula:          $($Document.SignedTurnErrorFormula)")
    $lines.Add("Idle pass count:             $($Document.EvidenceSummary.IdlePassCount)")
    $lines.Add("Turn pass count:             left $($Document.EvidenceSummary.TurnLeftPassCount) | right $($Document.EvidenceSummary.TurnRightPassCount)")
    $lines.Add("Forward valid/pass count:    $($Document.EvidenceSummary.ForwardValidCount) / $($Document.EvidenceSummary.ForwardPassCount)")
    $lines.Add("Forward median/max err (deg): $(Format-Nullable $Document.EvidenceSummary.ForwardMedianAngularErrorDegrees '0.000') / $(Format-Nullable $Document.EvidenceSummary.ForwardMaxAngularErrorDegrees '0.000')")
    if ($Document.Notes -and $Document.Notes.Count -gt 0) {
        $lines.Add("Notes:                       $([string]::Join('; ', $Document.Notes))")
    }

    return [string]::Join([Environment]::NewLine, $lines)
}

if (-not (Test-Path -LiteralPath $resolvedActorFacingSampleFile)) {
    throw "Actor facing sample file was not found: $resolvedActorFacingSampleFile"
}

$sampleDocument = (Get-Content -LiteralPath $resolvedActorFacingSampleFile -Raw) | ConvertFrom-Json -Depth 80
$sample = Get-OptionalPropertyValue -InputObject $sampleDocument -PropertyName 'ActorFacingSample'
if ($null -eq $sample) {
    throw "Actor facing sample file '$resolvedActorFacingSampleFile' did not contain ActorFacingSample."
}

$historyEntries = Get-ValidationHistoryEntries -HistoryFile $resolvedValidationHistoryFile
$sourceAddress = [string](Get-OptionalPropertyValue -InputObject $sample -PropertyName 'SourceAddress')
$basisForwardOffset = [string](Get-OptionalPropertyValue -InputObject $sample -PropertyName 'BasisForwardOffset')
$matchingEntries = @($historyEntries | Where-Object {
        (Get-OptionalPropertyValue -InputObject $_ -PropertyName 'SourceAddress') -eq $sourceAddress -and
        (Get-OptionalPropertyValue -InputObject $_ -PropertyName 'BasisForwardOffset') -eq $basisForwardOffset
    })

$idleEntries = @($matchingEntries | Where-Object { (Get-OptionalPropertyValue -InputObject $_ -PropertyName 'StimulusType') -eq 'idle' })
$turnLeftEntries = @($matchingEntries | Where-Object { (Get-OptionalPropertyValue -InputObject $_ -PropertyName 'StimulusType') -eq 'turn-left' })
$turnRightEntries = @($matchingEntries | Where-Object { (Get-OptionalPropertyValue -InputObject $_ -PropertyName 'StimulusType') -eq 'turn-right' })
$forwardEntries = @($matchingEntries | Where-Object { (Get-OptionalPropertyValue -InputObject $_ -PropertyName 'StimulusType') -eq 'move-forward' })

$idlePassCount = @($idleEntries | Where-Object { (Get-OptionalPropertyValue -InputObject $_ -PropertyName 'Verdict') -eq 'pass' }).Count
$turnLeftPassCount = @($turnLeftEntries | Where-Object { (Get-OptionalPropertyValue -InputObject $_ -PropertyName 'Verdict') -eq 'pass' }).Count
$turnRightPassCount = @($turnRightEntries | Where-Object { (Get-OptionalPropertyValue -InputObject $_ -PropertyName 'Verdict') -eq 'pass' }).Count
$forwardPassEntries = @($forwardEntries | Where-Object { (Get-OptionalPropertyValue -InputObject $_ -PropertyName 'Verdict') -eq 'pass' })
$forwardPassCount = $forwardPassEntries.Count
$forwardValidEntries = @($forwardEntries | Where-Object { $null -ne (Get-OptionalPropertyValue -InputObject $_ -PropertyName 'SignedAngularErrorDegrees') })
$forwardValidCount = $forwardValidEntries.Count
$forwardAngularErrors = @($forwardValidEntries | ForEach-Object { [Math]::Abs([double](Get-OptionalPropertyValue -InputObject $_ -PropertyName 'SignedAngularErrorDegrees')) })
$forwardMedianAngularError = Get-Median -Values $forwardAngularErrors
$forwardMaxAngularError = Get-MaximumValue -Values $forwardAngularErrors
$integrityPass = [bool](Get-OptionalPropertyValue -InputObject (Get-OptionalPropertyValue -InputObject $sample -PropertyName 'Integrity') -PropertyName 'Pass')

$confirmed =
    $integrityPass -and
    $idlePassCount -ge 1 -and
    $turnLeftPassCount -ge 1 -and
    $turnRightPassCount -ge 1 -and
    $forwardValidCount -ge 5 -and
    $forwardPassCount -ge 5 -and
    $null -ne $forwardMedianAngularError -and $forwardMedianAngularError -le $thresholds.RepeatedForwardMedianAngularErrorDegrees -and
    $null -ne $forwardMaxAngularError -and $forwardMaxAngularError -le $thresholds.RepeatedForwardSingleAngularErrorDegrees

$notes = New-Object System.Collections.Generic.List[string]
if ($confirmed) {
    $notes.Add('The incumbent selected-source basis passed integrity, turn response, and repeated forward-movement correlation gates.')
}
else {
    $notes.Add('The contract remains candidate-only until idle, turn-left, turn-right, and five forward movement validations all pass for the same source and basis offset.')
}
$notes.Add('Pitch is retained in the contract as evidence, but flat-ground navigation should consume planar yaw / signed turn error only.')
$notes.Add('If runtime integrity gates fail, navigation must treat facing as unavailable and stop turning decisions.')

$document = [pscustomobject]@{
    Mode                     = 'navigation-facing-contract'
    GeneratedAtUtc           = [DateTimeOffset]::UtcNow.ToString('O')
    OutputFile               = $resolvedOutputFile
    Status                   = if ($confirmed) { 'confirmed' } elseif ($integrityPass) { 'candidate' } else { 'rejected' }
    AuthoritativeSourceName  = Get-OptionalPropertyValue -InputObject $sample -PropertyName 'SourceName'
    SourceAddress            = $sourceAddress
    AuthoritativeForwardRowOffset = $basisForwardOffset
    ResolutionMode           = Get-OptionalPropertyValue -InputObject $sample -PropertyName 'ResolutionMode'
    YawFormula               = 'atan2(forwardZ, forwardX)'
    PitchFormula             = 'atan2(forwardY, sqrt(forwardX^2 + forwardZ^2))'
    PlanarProjectionFormula  = 'normalize(forwardX, forwardZ)'
    SignedTurnErrorFormula   = 'Normalize(atan2(targetDeltaZ, targetDeltaX) - actorYawRadians)'
    AcceptanceThresholds     = [pscustomobject]@{
        DeterminantMinimum                       = $thresholds.DeterminantMinimum
        DeterminantMaximum                       = $thresholds.DeterminantMaximum
        RowMagnitudeMinimum                      = $thresholds.RowMagnitudeMinimum
        RowMagnitudeMaximum                      = $thresholds.RowMagnitudeMaximum
        CrossRowDotProductMaximumAbsolute        = $thresholds.CrossRowDotProductMaximumAbsolute
        DuplicateBasisMaximumRowDelta            = $thresholds.DuplicateBasisMaximumRowDelta
        IdleYawJitterDegrees                     = $thresholds.IdleYawJitterDegrees
        IdlePlanarCoordDrift                     = $thresholds.IdlePlanarCoordDrift
        TurnYawDeltaDegrees                      = $thresholds.TurnYawDeltaDegrees
        TurnPlanarCoordDrift                     = $thresholds.TurnPlanarCoordDrift
        ForwardMovementDistance                  = $thresholds.ForwardMovementDistance
        ForwardAngularErrorDegrees               = $thresholds.ForwardAngularErrorDegrees
        RepeatedForwardMedianAngularErrorDegrees = $thresholds.RepeatedForwardMedianAngularErrorDegrees
        RepeatedForwardSingleAngularErrorDegrees = $thresholds.RepeatedForwardSingleAngularErrorDegrees
    }
    DisqualifyingStates      = @(
        'integrity-instability',
        'sign-inverted',
        'wrong-axis',
        'locomotion-mismatch',
        'insufficient-movement'
    )
    Sample                   = $sample
    EvidenceSummary          = [pscustomobject]@{
        SampleStatus                     = Get-OptionalPropertyValue -InputObject $sample -PropertyName 'Status'
        IntegrityPass                    = $integrityPass
        IdlePassCount                    = $idlePassCount
        TurnLeftPassCount                = $turnLeftPassCount
        TurnRightPassCount               = $turnRightPassCount
        ForwardValidCount                = $forwardValidCount
        ForwardPassCount                 = $forwardPassCount
        ForwardMedianAngularErrorDegrees = $forwardMedianAngularError
        ForwardMaxAngularErrorDegrees    = $forwardMaxAngularError
        MatchingHistoryEntryCount        = $matchingEntries.Count
        HistoryFile                      = $resolvedValidationHistoryFile
    }
    Notes                    = $notes
}

$outputDirectory = Split-Path -Path $resolvedOutputFile -Parent
if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

$jsonText = $document | ConvertTo-Json -Depth 80
[System.IO.File]::WriteAllText($resolvedOutputFile, $jsonText)

if ($Json) {
    Write-Output $jsonText
    return
}

Write-Output (Write-ContractText -Document $document)
