[CmdletBinding()]
param(
    [string]$ProcessName = 'rift_x64',
    [int]$ProcessId,
    [string]$TargetWindowHandle,
    [string]$OutputFile = (Join-Path $PSScriptRoot 'captures\proof-polling-watchset.json'),
    [string]$ProofCoordAnchorFile,
    [int]$CoordTraceObjectWindowBytes = 384,
    [int]$CandidateSourceWindowBytes = 384,
    [int]$BasisWindowBytes = 36,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$watchsetSchemaVersion = 1
$resolvedOutputFile = [System.IO.Path]::GetFullPath($OutputFile)
$resolveAnchorScript = Join-Path $PSScriptRoot 'resolve-proof-coord-anchor.ps1'

$regions = [System.Collections.Generic.List[object]]::new()
$warnings = [System.Collections.Generic.List[string]]::new()
$regionKeys = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)

function Parse-HexUInt64 {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    $normalized = $Value.Trim()
    if ($normalized.StartsWith('0x', [System.StringComparison]::OrdinalIgnoreCase)) {
        $normalized = $normalized.Substring(2)
    }

    return [UInt64]::Parse($normalized, [System.Globalization.NumberStyles]::HexNumber, [System.Globalization.CultureInfo]::InvariantCulture)
}

function Add-Region {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,

        [Parameter(Mandatory = $true)]
        [string]$Category,

        [Parameter(Mandatory = $true)]
        [UInt64]$Address,

        [Parameter(Mandatory = $true)]
        [int]$Length,

        [Parameter(Mandatory = $true)]
        [bool]$Required,

        [Parameter(Mandatory = $true)]
        [int]$Priority,

        [string]$Notes
    )

    if ($Address -le 0 -or $Length -le 0) {
        return
    }

    $addressHex = ('0x{0:X}' -f $Address)
    $key = '{0}|{1}|{2}' -f $Name, $addressHex, $Length
    if (-not $regionKeys.Add($key)) {
        return
    }

    $regions.Add([ordered]@{
            Name = $Name
            Category = $Category
            Address = $addressHex
            Length = $Length
            Required = $Required
            Priority = $Priority
            Notes = $Notes
        }) | Out-Null
}

function Get-OptionalPropertyValue {
    param(
        $Object,

        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    if ($null -eq $Object) {
        return $null
    }

    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $null
    }

    return $property.Value
}

function Write-Utf8TextAtomic {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [string]$Content
    )

    $directory = Split-Path -Path $Path -Parent
    if (-not [string]::IsNullOrWhiteSpace($directory)) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }

    $tempPath = '{0}.{1}.tmp' -f $Path, ([Guid]::NewGuid().ToString('N'))
    try {
        [System.IO.File]::WriteAllText($tempPath, $Content, [System.Text.UTF8Encoding]::new($false))
        Move-Item -LiteralPath $tempPath -Destination $Path -Force
    }
    finally {
        if (Test-Path -LiteralPath $tempPath) {
            Remove-Item -LiteralPath $tempPath -Force
        }
    }
}

$resolveArguments = @{
    ProcessName = $ProcessName
    Json = $true
}
if ($PSBoundParameters.ContainsKey('ProcessId') -and $ProcessId -gt 0) {
    $resolveArguments['ProcessId'] = $ProcessId
}
if (-not [string]::IsNullOrWhiteSpace($TargetWindowHandle)) {
    $resolveArguments['TargetWindowHandle'] = $TargetWindowHandle
}

if (-not [string]::IsNullOrWhiteSpace($ProofCoordAnchorFile)) {
    $resolvedProofCoordAnchorFile = [System.IO.Path]::GetFullPath($ProofCoordAnchorFile)
    if (-not (Test-Path -LiteralPath $resolvedProofCoordAnchorFile)) {
        throw "Proof coord-anchor file not found: $resolvedProofCoordAnchorFile"
    }

    $coordAnchor = Get-Content -LiteralPath $resolvedProofCoordAnchorFile -Raw | ConvertFrom-Json -Depth 32
}
else {
    $coordAnchor = & $resolveAnchorScript @resolveArguments | ConvertFrom-Json -Depth 32
}

if ($coordAnchor.PSObject.Properties['Status'] -and $coordAnchor.Status -eq 'failed') {
    throw [string]$coordAnchor.Error
}

$coordRegionAddress = Parse-HexUInt64 -Value ([string]$coordAnchor.CoordRegionAddress)
$coordTraceObjectAddress = Parse-HexUInt64 -Value ([string]$coordAnchor.ObjectBaseAddress)
$levelRelativeOffset = Get-OptionalPropertyValue -Object $coordAnchor -Name 'LevelRelativeOffset'
$healthRelativeOffset = Get-OptionalPropertyValue -Object $coordAnchor -Name 'HealthRelativeOffset'

Add-Region -Name 'coord-trace-coords' -Category 'coord-trace-field' -Address $coordRegionAddress -Length 12 -Required $true -Priority 140 -Notes 'Proof-grade movement coordinate triplet from the validated coord-trace anchor. This is the canonical movement polling source.'
Add-Region -Name 'coord-trace-object' -Category 'coord-trace-object' -Address $coordTraceObjectAddress -Length $CoordTraceObjectWindowBytes -Required $true -Priority 130 -Notes 'Owning object window for the validated coord-trace anchor.'

if ($null -ne $levelRelativeOffset) {
    Add-Region -Name 'coord-trace-level' -Category 'coord-trace-field' -Address ([UInt64]([long]$coordTraceObjectAddress + [long]$levelRelativeOffset)) -Length 4 -Required $false -Priority 90 -Notes 'Level field from the validated coord-trace anchor object.'
}

if ($null -ne $healthRelativeOffset) {
    Add-Region -Name 'coord-trace-health' -Category 'coord-trace-field' -Address ([UInt64]([long]$coordTraceObjectAddress + [long]$healthRelativeOffset)) -Length 4 -Required $false -Priority 90 -Notes 'Health field from the validated coord-trace anchor object.'
}

if (-not [string]::IsNullOrWhiteSpace([string]$coordAnchor.SourceObjectAddress)) {
    $sourceObjectAddress = Parse-HexUInt64 -Value ([string]$coordAnchor.SourceObjectAddress)
    Add-Region -Name 'actor-source-object-candidate' -Category 'actor-facing-candidate-object' -Address $sourceObjectAddress -Length $CandidateSourceWindowBytes -Required $false -Priority 80 -Notes 'Candidate actor-facing source object captured from the coord-trace anchor context. Candidate-only; not a movement truth source.'
    Add-Region -Name 'actor-source-basis60-candidate' -Category 'actor-facing-candidate-field' -Address ([UInt64]([long]$sourceObjectAddress + 0x60L)) -Length $BasisWindowBytes -Required $false -Priority 85 -Notes 'Candidate actor-facing basis block at +0x60 from the coord-trace-linked source object. Candidate-only.'
    Add-Region -Name 'actor-source-basis94-candidate' -Category 'actor-facing-candidate-field' -Address ([UInt64]([long]$sourceObjectAddress + 0x94L)) -Length $BasisWindowBytes -Required $false -Priority 84 -Notes 'Candidate actor-facing basis block at +0x94 from the coord-trace-linked source object. Candidate-only.'
}
else {
    $warnings.Add('Coord-trace anchor did not expose a source-object address, so actor-facing candidate basis fields were omitted.') | Out-Null
}

$sortedRegions = @(
    $regions.ToArray() |
        Sort-Object `
            @{ Expression = { if ([bool]$_.Required) { 0 } else { 1 } } }, `
            @{ Expression = { -1 * [int]$_.Priority } }, `
            Category, `
            Name, `
            Address, `
            Length
)

$document = [ordered]@{
    SchemaVersion = $watchsetSchemaVersion
    Mode = 'proof-polling-watchset'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
    ProcessName = $ProcessName
    ProcessId = if ($PSBoundParameters.ContainsKey('ProcessId') -and $ProcessId -gt 0) { $ProcessId } else { $null }
    TargetWindowHandle = if (-not [string]::IsNullOrWhiteSpace($TargetWindowHandle)) { $TargetWindowHandle } else { $null }
    CanonicalCoordSource = 'coord-trace-anchor'
    Anchor = $coordAnchor
    Warnings = @($warnings.ToArray())
    Regions = $sortedRegions
}

Write-Utf8TextAtomic -Path $resolvedOutputFile -Content ($document | ConvertTo-Json -Depth 16)

$result = [ordered]@{
    Mode = 'proof-polling-watchset-export'
    OutputFile = $resolvedOutputFile
    ProcessName = $ProcessName
    ProcessId = if ($PSBoundParameters.ContainsKey('ProcessId') -and $ProcessId -gt 0) { $ProcessId } else { $null }
    TargetWindowHandle = if (-not [string]::IsNullOrWhiteSpace($TargetWindowHandle)) { $TargetWindowHandle } else { $null }
    CanonicalCoordSource = 'coord-trace-anchor'
    CoordRegionAddress = [string]$coordAnchor.CoordRegionAddress
    ObjectBaseAddress = [string]$coordAnchor.ObjectBaseAddress
    RegionCount = $sortedRegions.Count
    Warnings = @($warnings.ToArray())
}

if ($Json) {
    $result | ConvertTo-Json -Depth 16
    exit 0
}

Write-Host 'Proof polling watchset exported.' -ForegroundColor Green
Write-Host ("Output:              {0}" -f $resolvedOutputFile)
Write-Host ("Coord source:        {0}" -f $result.CanonicalCoordSource)
Write-Host ("Coord region:        {0}" -f $result.CoordRegionAddress)
Write-Host ("Object base:         {0}" -f $result.ObjectBaseAddress)
Write-Host ("Regions:             {0}" -f $result.RegionCount)
