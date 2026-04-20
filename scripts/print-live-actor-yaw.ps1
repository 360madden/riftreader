[CmdletBinding()]
param(
    [switch]$Json,
    [switch]$RefreshCapture,
    [string]$ProcessName = 'rift_x64',
    [string]$PreferredLeadFile = 'actor-facing-behavior-backed-lead.json',
    [string]$FacingSampleFile = 'captures\player-actor-facing.json',
    [string]$OutputFile = 'captures\actor-yaw-live.json'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptRoot = if ($PSScriptRoot) { $PSScriptRoot } elseif ($PSCommandPath) { Split-Path -Parent $PSCommandPath } else { (Get-Location).Path }

function Assert-PowerShell7 {
    if ($PSVersionTable.PSVersion.Major -lt 7) {
        throw "PowerShell 7+ (pwsh) is required for $PSCommandPath. Use C:\RIFT MODDING\RiftReader_facing\scripts\print-live-actor-yaw.cmd or run the script with pwsh.exe."
    }
}

function Resolve-ScriptRelativePath {
    param([Parameter(Mandatory = $true)][string]$Path)

    if ([System.IO.Path]::IsPathRooted($Path)) {
        return [System.IO.Path]::GetFullPath($Path)
    }

    return [System.IO.Path]::GetFullPath((Join-Path $scriptRoot $Path))
}

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

Assert-PowerShell7

. (Join-Path $scriptRoot 'actor-facing-common.ps1')

$captureActorFacingScript = Join-Path $scriptRoot 'capture-actor-facing.ps1'
$resolvedPreferredLeadFile = Resolve-ScriptRelativePath -Path $PreferredLeadFile
$resolvedFacingSampleFile = Resolve-ScriptRelativePath -Path $FacingSampleFile
$resolvedOutputFile = Resolve-ScriptRelativePath -Path $OutputFile

if ($RefreshCapture -or -not (Test-Path -LiteralPath $resolvedFacingSampleFile)) {
    $captureJson = & $captureActorFacingScript -Json -ProcessName $ProcessName -PreferredLeadFile $resolvedPreferredLeadFile
    if ($LASTEXITCODE -ne 0) {
        throw 'Actor-facing capture failed while refreshing the live actor-yaw sample.'
    }

    $captureDocument = $captureJson | ConvertFrom-Json -Depth 80
}
else {
    $captureDocument = (Get-Content -LiteralPath $resolvedFacingSampleFile -Raw) | ConvertFrom-Json -Depth 80
}

$sample = Get-OptionalPropertyValue -InputObject $captureDocument -PropertyName 'ActorFacingSample'
if ($null -eq $sample) {
    throw "Facing sample file '$resolvedFacingSampleFile' did not contain ActorFacingSample."
}

$canonicalLead = Get-BehaviorBackedLead -FilePath $resolvedPreferredLeadFile
$matchesCanonicalLead = if ($null -ne $canonicalLead) { Test-ActorFacingSampleMatchesLead -Sample $sample -Lead $canonicalLead } else { $null }
if ($null -ne $canonicalLead -and -not $matchesCanonicalLead) {
    throw "Actor-yaw print helper expected the canonical solved actor-facing source '$($canonicalLead.SourceAddress) @ $($canonicalLead.BasisPrimaryForwardOffset)' but loaded '$($sample.SourceAddress) @ $($sample.BasisForwardOffset)'."
}

$document = [pscustomobject]@{
    Mode                  = 'live-actor-yaw'
    GeneratedAtUtc        = [DateTimeOffset]::UtcNow.ToString('O')
    OutputFile            = $resolvedOutputFile
    FacingSampleFile      = $resolvedFacingSampleFile
    CanonicalLeadFile     = if ($null -ne $canonicalLead) { $canonicalLead.FilePath } else { $null }
    CanonicalLeadMatched  = $matchesCanonicalLead
    SourceAddress         = Get-OptionalPropertyValue -InputObject $sample -PropertyName 'SourceAddress'
    BasisForwardOffset    = Get-OptionalPropertyValue -InputObject $sample -PropertyName 'BasisForwardOffset'
    ForwardComponentOffsets = Get-OptionalPropertyValue -InputObject $sample -PropertyName 'ForwardComponentOffsets'
    HotTracedSiblingOffset = Get-OptionalPropertyValue -InputObject $sample -PropertyName 'HotTracedSiblingOffset'
    ForwardVector         = Get-OptionalPropertyValue -InputObject $sample -PropertyName 'ForwardVector'
    PlanarForward         = Get-OptionalPropertyValue -InputObject $sample -PropertyName 'PlanarForward'
    YawRadians            = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $sample -PropertyName 'YawRadians')
    YawDegrees            = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $sample -PropertyName 'YawDegrees')
    PitchRadians          = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $sample -PropertyName 'PitchRadians')
    PitchDegrees          = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $sample -PropertyName 'PitchDegrees')
    YawTruthMode          = Get-OptionalPropertyValue -InputObject $sample -PropertyName 'YawTruthMode'
    YawDerivationFormula  = Get-OptionalPropertyValue -InputObject $sample -PropertyName 'YawDerivationFormula'
    PitchDerivationFormula = Get-OptionalPropertyValue -InputObject $sample -PropertyName 'PitchDerivationFormula'
    StandaloneYawFloatStatus = Get-OptionalPropertyValue -InputObject $sample -PropertyName 'StandaloneYawFloatStatus'
    Status                = Get-OptionalPropertyValue -InputObject $sample -PropertyName 'Status'
    OperationalStatus     = Get-OptionalPropertyValue -InputObject $sample -PropertyName 'OperationalStatus'
    SolvedActorFacing     = [bool](Get-OptionalPropertyValue -InputObject $sample -PropertyName 'SolvedActorFacing')
    CanonicalActorYaw     = [bool](Get-OptionalPropertyValue -InputObject $sample -PropertyName 'CanonicalActorYaw')
    Notes                 = @(
        'Actor yaw is derived live from the canonical actor-facing basis row.',
        'Use this helper when you need the current yaw value without reopening yaw-source discovery.'
    )
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

$lines = New-Object System.Collections.Generic.List[string]
$lines.Add('Live actor yaw')
$lines.Add("Output file:                 $($document.OutputFile)")
$lines.Add("Generated (UTC):             $($document.GeneratedAtUtc)")
$lines.Add("Source address:              $($document.SourceAddress)")
$lines.Add("Basis forward offset:        $($document.BasisForwardOffset)")
$lines.Add("Forward offsets (x/y/z):     $(if ($document.ForwardComponentOffsets) { \"$($document.ForwardComponentOffsets.X) / $($document.ForwardComponentOffsets.Y) / $($document.ForwardComponentOffsets.Z)\" } else { 'n/a' })")
$lines.Add("Hot traced sibling offset:   $(if ($document.HotTracedSiblingOffset) { $document.HotTracedSiblingOffset } else { 'n/a' })")
$lines.Add("Yaw degrees/radians:         $(Format-Nullable $document.YawDegrees '0.000') / $(Format-Nullable $document.YawRadians '0.000000')")
$lines.Add("Pitch degrees/radians:       $(Format-Nullable $document.PitchDegrees '0.000') / $(Format-Nullable $document.PitchRadians '0.000000')")
$lines.Add("Yaw truth mode:              $(if ($document.YawTruthMode) { $document.YawTruthMode } else { 'n/a' })")
$lines.Add("Yaw formula:                 $(if ($document.YawDerivationFormula) { $document.YawDerivationFormula } else { 'n/a' })")
$lines.Add("Standalone yaw float status: $(if ($document.StandaloneYawFloatStatus) { $document.StandaloneYawFloatStatus } else { 'n/a' })")
$lines.Add("Status:                      $($document.Status)")
$lines.Add("Operational status:          $($document.OperationalStatus)")
$lines.Add("Canonical lead matched:      $($document.CanonicalLeadMatched)")

Write-Output ([string]::Join([Environment]::NewLine, $lines))
