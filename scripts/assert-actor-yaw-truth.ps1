[CmdletBinding()]
param(
    [switch]$Json,
    [switch]$RefreshCapture,
    [string]$ProcessName = 'rift_x64',
    [string]$PreferredLeadFile = 'actor-facing-behavior-backed-lead.json',
    [string]$FacingSampleFile = 'captures\player-actor-facing.json',
    [string]$ValidationHistoryFile = 'captures\actor-facing-validation-history.ndjson',
    [string]$ContractFile = 'captures\navigation-facing-contract.json',
    [string]$OutputFile = 'captures\actor-yaw-truth.json'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptRoot = if ($PSScriptRoot) { $PSScriptRoot } elseif ($PSCommandPath) { Split-Path -Parent $PSCommandPath } else { (Get-Location).Path }

function Assert-PowerShell7 {
    if ($PSVersionTable.PSVersion.Major -lt 7) {
        throw "PowerShell 7+ (pwsh) is required for $PSCommandPath. Use C:\RIFT MODDING\RiftReader_facing\scripts\assert-actor-yaw-truth.cmd or run the script with pwsh.exe."
    }
}

function Resolve-ScriptRelativePath {
    param([Parameter(Mandatory = $true)][string]$Path)

    if ([System.IO.Path]::IsPathRooted($Path)) {
        return [System.IO.Path]::GetFullPath($Path)
    }

    return [System.IO.Path]::GetFullPath((Join-Path $scriptRoot $Path))
}

Assert-PowerShell7

. (Join-Path $scriptRoot 'actor-facing-common.ps1')

$captureActorFacingScript = Join-Path $scriptRoot 'capture-actor-facing.ps1'
$resolvedPreferredLeadFile = Resolve-ScriptRelativePath -Path $PreferredLeadFile
$resolvedFacingSampleFile = Resolve-ScriptRelativePath -Path $FacingSampleFile
$resolvedValidationHistoryFile = Resolve-ScriptRelativePath -Path $ValidationHistoryFile
$resolvedContractFile = Resolve-ScriptRelativePath -Path $ContractFile
$resolvedOutputFile = Resolve-ScriptRelativePath -Path $OutputFile

if ($RefreshCapture -or -not (Test-Path -LiteralPath $resolvedFacingSampleFile)) {
    $captureJson = & $captureActorFacingScript -Json -ProcessName $ProcessName -PreferredLeadFile $resolvedPreferredLeadFile
    if ($LASTEXITCODE -ne 0) {
        throw 'Actor-facing capture failed while refreshing the actor-yaw truth assertion sample.'
    }
}

if (-not (Test-Path -LiteralPath $resolvedFacingSampleFile)) {
    throw "Facing sample file was not found: $resolvedFacingSampleFile"
}

$sampleDocument = (Get-Content -LiteralPath $resolvedFacingSampleFile -Raw) | ConvertFrom-Json -Depth 80
$sample = Get-OptionalPropertyValue -InputObject $sampleDocument -PropertyName 'ActorFacingSample'
if ($null -eq $sample) {
    throw "Facing sample file '$resolvedFacingSampleFile' did not contain ActorFacingSample."
}

$canonicalLead = Get-BehaviorBackedLead -FilePath $resolvedPreferredLeadFile
if ($null -eq $canonicalLead) {
    throw "Canonical solved lead file was not found or was invalid: $resolvedPreferredLeadFile"
}

$historyEntries = Get-ValidationHistoryEntries -HistoryFile $resolvedValidationHistoryFile
$sourceAddress = [string](Get-OptionalPropertyValue -InputObject $sample -PropertyName 'SourceAddress')
$basisForwardOffset = [string](Get-OptionalPropertyValue -InputObject $sample -PropertyName 'BasisForwardOffset')
$matchingHistoryEntries = @($historyEntries | Where-Object {
        (Get-OptionalPropertyValue -InputObject $_ -PropertyName 'SourceAddress') -eq $sourceAddress -and
        (Get-OptionalPropertyValue -InputObject $_ -PropertyName 'BasisForwardOffset') -eq $basisForwardOffset
    })
$turnLeftPassCount = @($matchingHistoryEntries | Where-Object {
        (Get-OptionalPropertyValue -InputObject $_ -PropertyName 'StimulusType') -eq 'turn-left' -and
        (Get-OptionalPropertyValue -InputObject $_ -PropertyName 'Verdict') -eq 'pass'
    }).Count
$turnRightPassCount = @($matchingHistoryEntries | Where-Object {
        (Get-OptionalPropertyValue -InputObject $_ -PropertyName 'StimulusType') -eq 'turn-right' -and
        (Get-OptionalPropertyValue -InputObject $_ -PropertyName 'Verdict') -eq 'pass'
    }).Count

$contractDocument = $null
if (Test-Path -LiteralPath $resolvedContractFile) {
    $contractDocument = (Get-Content -LiteralPath $resolvedContractFile -Raw) | ConvertFrom-Json -Depth 80
}

$checks = @(
    [pscustomobject]@{ Name = 'Canonical lead file loaded'; Pass = $null -ne $canonicalLead; Detail = $canonicalLead.FilePath },
    [pscustomobject]@{ Name = 'Sample matches canonical lead'; Pass = (Test-ActorFacingSampleMatchesLead -Sample $sample -Lead $canonicalLead); Detail = "$sourceAddress @ $basisForwardOffset" },
    [pscustomobject]@{ Name = 'Sample status is preferred-solved-lead'; Pass = ([string](Get-OptionalPropertyValue -InputObject $sample -PropertyName 'Status') -eq 'preferred-solved-lead'); Detail = [string](Get-OptionalPropertyValue -InputObject $sample -PropertyName 'Status') },
    [pscustomobject]@{ Name = 'Operational status is behavior-backed-lead'; Pass = ([string](Get-OptionalPropertyValue -InputObject $sample -PropertyName 'OperationalStatus') -eq 'behavior-backed-lead'); Detail = [string](Get-OptionalPropertyValue -InputObject $sample -PropertyName 'OperationalStatus') },
    [pscustomobject]@{ Name = 'Solved actor-facing flag is true'; Pass = [bool](Get-OptionalPropertyValue -InputObject $sample -PropertyName 'SolvedActorFacing'); Detail = [string](Get-OptionalPropertyValue -InputObject $sample -PropertyName 'SolvedActorFacing') },
    [pscustomobject]@{ Name = 'Canonical actor-yaw flag is true'; Pass = [bool](Get-OptionalPropertyValue -InputObject $sample -PropertyName 'CanonicalActorYaw'); Detail = [string](Get-OptionalPropertyValue -InputObject $sample -PropertyName 'CanonicalActorYaw') },
    [pscustomobject]@{ Name = 'Integrity gates pass'; Pass = [bool](Get-OptionalPropertyValue -InputObject (Get-OptionalPropertyValue -InputObject $sample -PropertyName 'Integrity') -PropertyName 'Pass'); Detail = [string](Get-OptionalPropertyValue -InputObject (Get-OptionalPropertyValue -InputObject $sample -PropertyName 'Integrity') -PropertyName 'Pass') },
    [pscustomobject]@{ Name = 'Yaw formula is canonical'; Pass = ([string](Get-OptionalPropertyValue -InputObject $sample -PropertyName 'YawDerivationFormula') -eq 'atan2(forwardZ, forwardX)'); Detail = [string](Get-OptionalPropertyValue -InputObject $sample -PropertyName 'YawDerivationFormula') },
    [pscustomobject]@{ Name = 'Forward Z hot sibling is +0xDC'; Pass = ([string](Get-OptionalPropertyValue -InputObject $sample -PropertyName 'HotTracedSiblingOffset') -eq '0xDC'); Detail = [string](Get-OptionalPropertyValue -InputObject $sample -PropertyName 'HotTracedSiblingOffset') },
    [pscustomobject]@{ Name = 'Forward offsets resolve to +0xD4/+0xD8/+0xDC'; Pass = ((Get-OptionalPropertyValue -InputObject (Get-OptionalPropertyValue -InputObject $sample -PropertyName 'ForwardComponentOffsets') -PropertyName 'X') -eq '0xD4' -and (Get-OptionalPropertyValue -InputObject (Get-OptionalPropertyValue -InputObject $sample -PropertyName 'ForwardComponentOffsets') -PropertyName 'Y') -eq '0xD8' -and (Get-OptionalPropertyValue -InputObject (Get-OptionalPropertyValue -InputObject $sample -PropertyName 'ForwardComponentOffsets') -PropertyName 'Z') -eq '0xDC'); Detail = ((Get-OptionalPropertyValue -InputObject $sample -PropertyName 'ForwardComponentOffsets') | ConvertTo-Json -Compress) },
    [pscustomobject]@{ Name = 'Standalone yaw float search stays closed'; Pass = ([string](Get-OptionalPropertyValue -InputObject $sample -PropertyName 'StandaloneYawFloatStatus') -eq 'not-required-unless-contradicted'); Detail = [string](Get-OptionalPropertyValue -InputObject $sample -PropertyName 'StandaloneYawFloatStatus') },
    [pscustomobject]@{ Name = 'Sample is not the rejected incumbent'; Pass = -not ($sourceAddress -eq $canonicalLead.SupersededRejectedSourceAddress -and $basisForwardOffset -eq $canonicalLead.SupersededRejectedBasisForwardOffset); Detail = "$($canonicalLead.SupersededRejectedSourceAddress) @ $($canonicalLead.SupersededRejectedBasisForwardOffset)" },
    [pscustomobject]@{ Name = 'Turn-left regression pass exists'; Pass = $turnLeftPassCount -ge 1; Detail = "$turnLeftPassCount pass run(s)" },
    [pscustomobject]@{ Name = 'Turn-right regression pass exists'; Pass = $turnRightPassCount -ge 1; Detail = "$turnRightPassCount pass run(s)" },
    [pscustomobject]@{ Name = 'Navigation contract still says actor-facing solved'; Pass = ($null -eq $contractDocument -or [string](Get-OptionalPropertyValue -InputObject $contractDocument -PropertyName 'ActorFacingStatus') -eq 'solved'); Detail = if ($null -ne $contractDocument) { [string](Get-OptionalPropertyValue -InputObject $contractDocument -PropertyName 'ActorFacingStatus') } else { 'contract file missing; skipped' } },
    [pscustomobject]@{ Name = 'Navigation contract still matches canonical lead'; Pass = ($null -eq $contractDocument -or [bool](Get-OptionalPropertyValue -InputObject $contractDocument -PropertyName 'CanonicalLeadMatched')); Detail = if ($null -ne $contractDocument) { [string](Get-OptionalPropertyValue -InputObject $contractDocument -PropertyName 'CanonicalLeadMatched') } else { 'contract file missing; skipped' } }
)

$failedChecks = @($checks | Where-Object { -not $_.Pass })
$document = [pscustomobject]@{
    Mode                    = 'actor-yaw-truth-assertion'
    GeneratedAtUtc          = [DateTimeOffset]::UtcNow.ToString('O')
    OutputFile              = $resolvedOutputFile
    FacingSampleFile        = $resolvedFacingSampleFile
    ValidationHistoryFile   = $resolvedValidationHistoryFile
    ContractFile            = if (Test-Path -LiteralPath $resolvedContractFile) { $resolvedContractFile } else { $null }
    CanonicalLeadFile       = $canonicalLead.FilePath
    SourceAddress           = $sourceAddress
    BasisForwardOffset      = $basisForwardOffset
    OverallVerdict          = if ($failedChecks.Count -eq 0) { 'pass' } else { 'fail' }
    TurnLeftPassCount       = $turnLeftPassCount
    TurnRightPassCount      = $turnRightPassCount
    Checks                  = $checks
    Notes                   = @(
        'Actor yaw truth is asserted through the canonical actor-facing basis row, not through a standalone yaw float.',
        'Movement and navigation remain separate downstream tracks.'
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
$lines.Add('Actor yaw truth assertion')
$lines.Add("Output file:                 $($document.OutputFile)")
$lines.Add("Generated (UTC):             $($document.GeneratedAtUtc)")
$lines.Add("Source address:              $($document.SourceAddress)")
$lines.Add("Basis forward offset:        $($document.BasisForwardOffset)")
$lines.Add("Overall verdict:             $($document.OverallVerdict)")
$lines.Add("Turn-left/right pass count:  $($document.TurnLeftPassCount) / $($document.TurnRightPassCount)")
$lines.Add('Checks:')
foreach ($check in $document.Checks) {
    $lines.Add("  - $($check.Name): $($check.Pass) ($(if ([string]::IsNullOrWhiteSpace([string]$check.Detail)) { 'n/a' } else { [string]$check.Detail }))")
}

Write-Output ([string]::Join([Environment]::NewLine, $lines))
