[CmdletBinding()]
param(
    [switch]$Json,
    [string]$Label,
    [switch]$RefreshOwnerComponents,
    [switch]$RefreshReaderBridge,
    [switch]$NoAhkFallback,
    [string]$ProcessName = 'rift_x64',
    [string]$OwnerComponentsFile = (Join-Path $PSScriptRoot 'captures\player-owner-components.json'),
    [string]$OrientationOutputFile = (Join-Path $PSScriptRoot 'captures\player-actor-orientation.json'),
    [string]$OrientationPreviousFile = (Join-Path $PSScriptRoot 'captures\player-actor-orientation.previous.json'),
    [string]$OutputFile = (Join-Path $PSScriptRoot 'captures\player-actor-facing.json'),
    [string]$PreviousFile = (Join-Path $PSScriptRoot 'captures\player-actor-facing.previous.json')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'actor-facing-common.ps1')

$captureOrientationScript = Join-Path $PSScriptRoot 'capture-actor-orientation.ps1'
$resolvedOwnerComponentsFile = [System.IO.Path]::GetFullPath($OwnerComponentsFile)
$resolvedOrientationOutputFile = [System.IO.Path]::GetFullPath($OrientationOutputFile)
$resolvedOrientationPreviousFile = [System.IO.Path]::GetFullPath($OrientationPreviousFile)
$resolvedOutputFile = [System.IO.Path]::GetFullPath($OutputFile)
$resolvedPreviousFile = [System.IO.Path]::GetFullPath($PreviousFile)

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

function Format-PlanarVector {
    param($Vector)

    if ($null -eq $Vector) {
        return 'n/a'
    }

    $x = Get-OptionalPropertyValue -InputObject $Vector -PropertyName 'X'
    $z = Get-OptionalPropertyValue -InputObject $Vector -PropertyName 'Z'
    if ($null -eq $x -or $null -eq $z) {
        return 'n/a'
    }

    return '{0}, {1}' -f
        (Format-Nullable -Value $x -Format '0.00000'),
        (Format-Nullable -Value $z -Format '0.00000')
}

function Format-Vector {
    param($Vector)

    if ($null -eq $Vector) {
        return 'n/a'
    }

    $x = Get-OptionalPropertyValue -InputObject $Vector -PropertyName 'X'
    $y = Get-OptionalPropertyValue -InputObject $Vector -PropertyName 'Y'
    $z = Get-OptionalPropertyValue -InputObject $Vector -PropertyName 'Z'
    if ($null -eq $x -or $null -eq $y -or $null -eq $z) {
        return 'n/a'
    }

    return '{0}, {1}, {2}' -f
        (Format-Nullable -Value $x -Format '0.00000'),
        (Format-Nullable -Value $y -Format '0.00000'),
        (Format-Nullable -Value $z -Format '0.00000')
}

function Get-PreviousSampleDelta {
    param(
        $CurrentSample,
        $PreviousSample,
        [string]$PreviousPath
    )

    if ($null -eq $PreviousSample) {
        return $null
    }

    $currentYaw = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $CurrentSample -PropertyName 'YawRadians')
    $previousYaw = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $PreviousSample -PropertyName 'YawRadians')
    $currentPitch = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $CurrentSample -PropertyName 'PitchRadians')
    $previousPitch = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $PreviousSample -PropertyName 'PitchRadians')
    $currentCoord = Get-OptionalPropertyValue -InputObject $CurrentSample -PropertyName 'PlayerCoord'
    $previousCoord = Get-OptionalPropertyValue -InputObject $PreviousSample -PropertyName 'PlayerCoord'
    $currentPlanar = Get-OptionalPropertyValue -InputObject $CurrentSample -PropertyName 'PlanarForward'
    $previousPlanar = Get-OptionalPropertyValue -InputObject $PreviousSample -PropertyName 'PlanarForward'

    $planarForwardDelta = $null
    if ($null -ne $currentPlanar -and $null -ne $previousPlanar) {
        $planarForwardDelta = Get-PlanarMagnitude `
            -ValueX ((Get-OptionalPropertyValue -InputObject $currentPlanar -PropertyName 'X') - (Get-OptionalPropertyValue -InputObject $previousPlanar -PropertyName 'X')) `
            -ValueZ ((Get-OptionalPropertyValue -InputObject $currentPlanar -PropertyName 'Z') - (Get-OptionalPropertyValue -InputObject $previousPlanar -PropertyName 'Z'))
    }

    return [pscustomobject]@{
        PreviousFile              = $PreviousPath
        PreviousStatus            = Get-OptionalPropertyValue -InputObject $PreviousSample -PropertyName 'Status'
        PreviousYawDeltaDegrees   = if ($null -ne $currentYaw -and $null -ne $previousYaw) { Convert-RadiansToDegrees -Radians (Normalize-AngleRadians -Radians ($currentYaw - $previousYaw)) } else { $null }
        PreviousPitchDeltaDegrees = if ($null -ne $currentPitch -and $null -ne $previousPitch) { Convert-RadiansToDegrees -Radians (Normalize-AngleRadians -Radians ($currentPitch - $previousPitch)) } else { $null }
        PreviousPlanarForwardDelta = $planarForwardDelta
        PreviousPlanarCoordDelta  = Get-PlanarDistance -LeftCoord $previousCoord -RightCoord $currentCoord
        PreviousDeterminantDelta  = if ($null -ne $CurrentSample.Determinant -and $null -ne $PreviousSample.Determinant) { [double]$CurrentSample.Determinant - [double]$PreviousSample.Determinant } else { $null }
    }
}

function Write-ActorFacingText {
    param($Document)

    $sample = $Document.ActorFacingSample
    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add('Actor facing capture')
    $lines.Add("Output file:                 $($Document.OutputFile)")
    $lines.Add("Generated (UTC):             $($Document.GeneratedAtUtc)")
    $lines.Add("Label:                       $(if ([string]::IsNullOrWhiteSpace([string]$Document.Label)) { 'n/a' } else { [string]$Document.Label })")
    $lines.Add("Source capture:              $($Document.SourceCaptureFile)")
    $lines.Add("Source address:              $(if ($sample.SourceAddress) { $sample.SourceAddress } else { 'n/a' })")
    $lines.Add("Selected entry:              index $(if ($null -ne $sample.SelectedEntryIndex) { $sample.SelectedEntryIndex } else { 'n/a' }) | $(if ($sample.SelectedEntryAddress) { $sample.SelectedEntryAddress } else { 'n/a' })")
    $lines.Add("Basis forward offset:        $(if ($sample.BasisForwardOffset) { $sample.BasisForwardOffset } else { 'n/a' })")
    $lines.Add("Status:                      $($sample.Status)")
    $lines.Add("Forward vector:              $(Format-Vector $sample.ForwardVector)")
    $lines.Add("Planar forward:              $(Format-PlanarVector $sample.PlanarForward)")
    $lines.Add("Yaw/pitch (deg):             $(Format-Nullable $sample.YawDegrees '0.000') / $(Format-Nullable $sample.PitchDegrees '0.000')")
    $lines.Add("Basis determinant:           $(Format-Nullable $sample.Determinant '0.000000')")
    $lines.Add("Basis row magnitudes:        f $(Format-Nullable $sample.RowMagnitudes.Forward '0.000000') | u $(Format-Nullable $sample.RowMagnitudes.Up '0.000000') | r $(Format-Nullable $sample.RowMagnitudes.Right '0.000000')")
    $lines.Add("Basis row dots:              f·u $(Format-Nullable $sample.RowDotProducts.ForwardUp '0.000000') | f·r $(Format-Nullable $sample.RowDotProducts.ForwardRight '0.000000') | u·r $(Format-Nullable $sample.RowDotProducts.UpRight '0.000000')")
    $lines.Add("Duplicate basis delta:       $(Format-Nullable $sample.DuplicateBasisDelta '0.000000')")
    $lines.Add("Integrity gates:             det $($sample.Integrity.DeterminantPass) | rows $($sample.Integrity.RowMagnitudesPass) | dots $($sample.Integrity.CrossRowDotProductsPass) | dup $($sample.Integrity.DuplicateBasisPass) | pass $($sample.Integrity.Pass)")
    $lines.Add("Resolution mode:             $(if ($sample.ResolutionMode) { $sample.ResolutionMode } else { 'n/a' })")
    if ($Document.ChangeFromPrevious) {
        $lines.Add("Prev yaw/pitch delta (deg):  $(Format-Nullable $Document.ChangeFromPrevious.PreviousYawDeltaDegrees '0.000') / $(Format-Nullable $Document.ChangeFromPrevious.PreviousPitchDeltaDegrees '0.000')")
        $lines.Add("Prev planar forward delta:   $(Format-Nullable $Document.ChangeFromPrevious.PreviousPlanarForwardDelta '0.000000')")
        $lines.Add("Prev planar coord delta:     $(Format-Nullable $Document.ChangeFromPrevious.PreviousPlanarCoordDelta '0.000000')")
    }
    if ($sample.Notes -and $sample.Notes.Count -gt 0) {
        $lines.Add("Notes:                       $([string]::Join('; ', $sample.Notes))")
    }

    return [string]::Join([Environment]::NewLine, $lines)
}

$captureArgs = @{
    Json                = $true
    ProcessName         = $ProcessName
    OwnerComponentsFile = $resolvedOwnerComponentsFile
    OutputFile          = $resolvedOrientationOutputFile
    PreviousFile        = $resolvedOrientationPreviousFile
}

if (-not [string]::IsNullOrWhiteSpace($Label)) {
    $captureArgs['Label'] = $Label
}
if ($RefreshOwnerComponents) {
    $captureArgs['RefreshOwnerComponents'] = $true
}
if ($RefreshReaderBridge) {
    $captureArgs['RefreshReaderBridge'] = $true
}
if ($NoAhkFallback) {
    $captureArgs['NoAhkFallback'] = $true
}

$orientationJson = & $captureOrientationScript @captureArgs
if ($LASTEXITCODE -ne 0) {
    throw 'Actor orientation capture failed.'
}

$orientationCapture = $orientationJson | ConvertFrom-Json -Depth 80
$sample = ConvertTo-ActorFacingSample -CaptureDocument $orientationCapture

$notes = New-Object System.Collections.Generic.List[string]
$notes.Add('This helper normalizes the incumbent selected-source basis into a navigation-ready actor-facing sample.')
$notes.Add('Use the output as the candidate sample for idle / turn / forward movement correlation runs.')
$notes.Add('A confirmed navigation-facing contract still requires live movement validation against addon boundary coords.')

$document = [pscustomobject]@{
    Mode              = 'actor-facing-sample'
    GeneratedAtUtc    = [DateTimeOffset]::UtcNow.ToString('O')
    Label             = $Label
    OutputFile        = $resolvedOutputFile
    PreviousFile      = $resolvedPreviousFile
    SourceCaptureFile = $resolvedOrientationOutputFile
    ActorFacingSample = $sample
    Notes             = $notes
}

$previousSample = $null
if (Test-Path -LiteralPath $resolvedOutputFile) {
    $previousJson = Get-Content -LiteralPath $resolvedOutputFile -Raw
    if (-not [string]::IsNullOrWhiteSpace($previousJson)) {
        $previousDocument = $previousJson | ConvertFrom-Json -Depth 80
        $previousSample = Get-OptionalPropertyValue -InputObject $previousDocument -PropertyName 'ActorFacingSample'
    }

    $previousDirectory = Split-Path -Path $resolvedPreviousFile -Parent
    if (-not [string]::IsNullOrWhiteSpace($previousDirectory)) {
        New-Item -ItemType Directory -Path $previousDirectory -Force | Out-Null
    }

    Copy-Item -LiteralPath $resolvedOutputFile -Destination $resolvedPreviousFile -Force
}

$document | Add-Member -NotePropertyName ChangeFromPrevious -NotePropertyValue (Get-PreviousSampleDelta -CurrentSample $sample -PreviousSample $previousSample -PreviousPath $resolvedPreviousFile)

$outputDirectory = Split-Path -Path $resolvedOutputFile -Parent
if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

$jsonText = $document | ConvertTo-Json -Depth 60
[System.IO.File]::WriteAllText($resolvedOutputFile, $jsonText)

if ($Json) {
    Write-Output $jsonText
    return
}

Write-Output (Write-ActorFacingText -Document $document)
