[CmdletBinding()]
param(
    [string]$ProcessName = 'rift_x64',
    [string]$OutputFile = (Join-Path $PSScriptRoot 'captures\session-watchset.json'),
    [int]$TopSharedHubs = 4,
    [int]$ObjectWindowBytes = 384,
    [int]$StateWindowBytes = 256,
    [int]$ProjectorSlotWindowBytes = 216,
    [int]$HubWindowBytes = 512,
    [int]$CombatFieldWindowBytes = 32,
    [int]$MaxOffsetsPerField = 4,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$capturesRoot = Join-Path $PSScriptRoot 'captures'
$resolvedOutputFile = [System.IO.Path]::GetFullPath($OutputFile)

$artifacts = [System.Collections.Generic.List[object]]::new()
$regions = [System.Collections.Generic.List[object]]::new()
$warnings = [System.Collections.Generic.List[string]]::new()
$regionKeys = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)

function Read-JsonArtifact {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [string]$Role,

        [switch]$Optional
    )

    $resolvedPath = [System.IO.Path]::GetFullPath($Path)
    if (-not (Test-Path -LiteralPath $resolvedPath)) {
        if ($Optional) {
            return $null
        }

        throw "Required artifact '$Role' was not found at '$resolvedPath'."
    }

    $document = Get-Content -LiteralPath $resolvedPath -Raw | ConvertFrom-Json -Depth 64
    Add-Artifact -Role $Role -File $resolvedPath -Document $document
    return $document
}

function Add-Artifact {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Role,

        [Parameter(Mandatory = $true)]
        [string]$File,

        [Parameter(Mandatory = $true)]
        $Document
    )

    $generatedAt = Get-NestedValue -Object $Document -Segments @('GeneratedAtUtc')
    if ([string]::IsNullOrWhiteSpace($generatedAt)) {
        $generatedAt = Get-NestedValue -Object $Document -Segments @('SavedAtUtc')
    }

    $selectedSourceAddress = $null
    foreach ($path in @(
            @('Owner', 'SelectedSourceAddress'),
            @('SelectedSource', 'Address'),
            @('SelectedSourceAddress'),
            @('SourceObjectAddress'))) {
        $selectedSourceAddress = Get-NestedValue -Object $Document -Segments $path
        if (-not [string]::IsNullOrWhiteSpace($selectedSourceAddress)) {
            break
        }
    }

    $artifacts.Add([ordered]@{
            Role = $Role
            File = $File
            GeneratedAtUtc = $generatedAt
            SelectedSourceAddress = $selectedSourceAddress
        }) | Out-Null
}

function Get-NestedValue {
    param(
        [Parameter(Mandatory = $true)]
        $Object,

        [Parameter(Mandatory = $true)]
        [string[]]$Segments
    )

    $current = $Object
    foreach ($segment in $Segments) {
        if ($null -eq $current) {
            return $null
        }

        $property = $current.PSObject.Properties[$segment]
        if ($null -eq $property) {
            return $null
        }

        $current = $property.Value
    }

    return $current
}

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

function Format-HexUInt64 {
    param(
        [Parameter(Mandatory = $true)]
        [UInt64]$Value
    )

    return ('0x{0:X}' -f $Value)
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

        [string]$SourceArtifactFile,

        [string]$Notes
    )

    if ($Address -le 0 -or $Length -le 0) {
        return
    }

    $addressHex = Format-HexUInt64 -Value $Address
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
            SourceArtifactFile = $SourceArtifactFile
            Notes = $Notes
        }) | Out-Null
}

function Add-OffsetRegion {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,

        [Parameter(Mandatory = $true)]
        [string]$Category,

        [Parameter(Mandatory = $true)]
        [string]$BaseAddress,

        [Parameter(Mandatory = $true)]
        [long]$Offset,

        [Parameter(Mandatory = $true)]
        [int]$Length,

        [Parameter(Mandatory = $true)]
        [bool]$Required,

        [Parameter(Mandatory = $true)]
        [int]$Priority,

        [string]$SourceArtifactFile,

        [string]$Notes
    )

    if ([string]::IsNullOrWhiteSpace($BaseAddress)) {
        return
    }

    $baseValue = Parse-HexUInt64 -Value $BaseAddress
    $targetValue = [long]$baseValue + $Offset
    if ($targetValue -le 0) {
        return
    }

    Add-Region -Name $Name -Category $Category -Address ([UInt64]$targetValue) -Length $Length -Required $Required -Priority $Priority -SourceArtifactFile $SourceArtifactFile -Notes $Notes
}

function Add-Warning {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    if (-not [string]::IsNullOrWhiteSpace($Message)) {
        $warnings.Add($Message) | Out-Null
    }
}

function Add-HubFieldRegions {
    param(
        [Parameter(Mandatory = $true)]
        $Hub,

        [Parameter(Mandatory = $true)]
        [int]$HubRank,

        [Parameter(Mandatory = $true)]
        [string]$HubCategory,

        [Parameter(Mandatory = $true)]
        [string]$SourceArtifactFile
    )

    $hubAddressText = [string]$Hub.Address
    if ([string]::IsNullOrWhiteSpace($hubAddressText)) {
        return
    }

    $fieldMap = @(
        @{ Property = 'LevelOffsets'; Label = 'level'; Priority = 78; Notes = 'Candidate level field neighborhood within ranked shared hub.' },
        @{ Property = 'HpOffsets'; Label = 'hp'; Priority = 82; Notes = 'Candidate health field neighborhood within ranked shared hub.' },
        @{ Property = 'HpMaxOffsets'; Label = 'hpmax'; Priority = 80; Notes = 'Candidate max-health field neighborhood within ranked shared hub.' },
        @{ Property = 'ResourceOffsets'; Label = 'resource'; Priority = 81; Notes = 'Candidate primary-resource field neighborhood within ranked shared hub.' },
        @{ Property = 'ResourceMaxOffsets'; Label = 'resource-max'; Priority = 79; Notes = 'Candidate max-resource field neighborhood within ranked shared hub.' },
        @{ Property = 'ComboOffsets'; Label = 'combo'; Priority = 74; Notes = 'Candidate combo/counter field neighborhood within ranked shared hub.' },
        @{ Property = 'PlanarMaxOffsets'; Label = 'planar-max'; Priority = 72; Notes = 'Candidate planar/capacity field neighborhood within ranked shared hub.' },
        @{ Property = 'OwnerOffsets'; Label = 'owner-backref'; Priority = 66; Notes = 'Owner-backreference field neighborhood within ranked shared hub.' },
        @{ Property = 'StateOffsets'; Label = 'state-backref'; Priority = 65; Notes = 'State-backreference field neighborhood within ranked shared hub.' },
        @{ Property = 'SourceOffsets'; Label = 'source-backref'; Priority = 64; Notes = 'Source-backreference field neighborhood within ranked shared hub.' }
    )

    foreach ($field in $fieldMap) {
        $property = $Hub.PSObject.Properties[$field.Property]
        if ($null -eq $property -or $null -eq $property.Value) {
            continue
        }

        $offsetCount = 0
        foreach ($offsetText in @($property.Value)) {
            if ($offsetCount -ge $MaxOffsetsPerField) {
                break
            }

            $offsetString = [string]$offsetText
            if ([string]::IsNullOrWhiteSpace($offsetString)) {
                continue
            }

            $offsetValue = [long](Parse-HexUInt64 -Value $offsetString)
            Add-OffsetRegion -Name ('shared-hub-{0}-{1}-{2}' -f $HubRank, $field.Label, ($offsetString -replace '^0x', '')) -Category ('{0}-{1}' -f $HubCategory, $field.Label) -BaseAddress $hubAddressText -Offset $offsetValue -Length $CombatFieldWindowBytes -Required $false -Priority ([Math]::Max(1, ([int]$field.Priority - ($HubRank - 1)))) -SourceArtifactFile $SourceArtifactFile -Notes ('{0} Offset {1} within ranked shared hub #{2}.' -f $field.Notes, $offsetString, $HubRank)
            $offsetCount++
        }
    }
}

function Add-ProjectorSlotRegions {
    param(
        [Parameter(Mandatory = $true)]
        $ProjectorTrace,

        [Parameter(Mandatory = $true)]
        [string]$SourceArtifactFile
    )

    if ($null -eq $ProjectorTrace -or $null -eq $ProjectorTrace.Owner) {
        return
    }

    $slotDefinitions = @(
        @{ Property = 'StateSlot50'; Offset = '0x50'; Priority = 83; Notes = 'Projector-traced owner state slot pointer at +0x50.' },
        @{ Property = 'StateSlot58'; Offset = '0x58'; Priority = 82; Notes = 'Projector-traced owner state slot pointer at +0x58.' },
        @{ Property = 'StateSlot60'; Offset = '0x60'; Priority = 81; Notes = 'Projector-traced owner state slot pointer at +0x60.' }
    )

    $slotMap = [ordered]@{}
    foreach ($definition in $slotDefinitions) {
        $property = $ProjectorTrace.Owner.PSObject.Properties[$definition.Property]
        if ($null -eq $property -or [string]::IsNullOrWhiteSpace([string]$property.Value)) {
            continue
        }

        $slotAddressText = [string]$property.Value
        $slotKey = $slotAddressText.ToUpperInvariant()
        if (-not $slotMap.Contains($slotKey)) {
            $slotMap[$slotKey] = [ordered]@{
                Address = $slotAddressText
                Offsets = [System.Collections.Generic.List[string]]::new()
                Notes = [System.Collections.Generic.List[string]]::new()
                Priority = [int]$definition.Priority
            }
        }

        $slotMap[$slotKey].Offsets.Add($definition.Offset) | Out-Null
        $slotMap[$slotKey].Notes.Add($definition.Notes) | Out-Null
        $slotMap[$slotKey].Priority = [Math]::Max([int]$slotMap[$slotKey].Priority, [int]$definition.Priority)
    }

    foreach ($slot in @($slotMap.Values)) {
        if ($null -eq $slot -or [string]::IsNullOrWhiteSpace([string]$slot.Address)) {
            continue
        }

        $offsetLabels = @($slot.Offsets | Select-Object -Unique)
        $offsetSuffix = (($offsetLabels | ForEach-Object { $_ -replace '^0x', '' }) -join '-').ToLowerInvariant()
        $slotNotes = @($slot.Notes | Select-Object -Unique)
        $note = if ($slotNotes.Count -gt 0) {
            '{0} Combined slot offsets: {1}.' -f ($slotNotes[0]), ($offsetLabels -join ', ')
        }
        else {
            'Projector-traced owner state slot.'
        }

        Add-Region -Name ('owner-state-slot-{0}' -f $offsetSuffix) -Category 'owner-state-slot' -Address (Parse-HexUInt64 -Value ([string]$slot.Address)) -Length $ProjectorSlotWindowBytes -Required $false -Priority ([int]$slot.Priority) -SourceArtifactFile $SourceArtifactFile -Notes $note
    }
}

$ownerComponentsFile = Join-Path $capturesRoot 'player-owner-components.json'
$selectorTraceFile = Join-Path $capturesRoot 'player-selector-owner-trace.json'
$sourceAccessorFile = Join-Path $capturesRoot 'player-source-accessor-family.json'
$statHubGraphFile = Join-Path $capturesRoot 'player-stat-hub-graph.json'
$currentAnchorFile = Join-Path $capturesRoot 'player-current-anchor.json'
$ownerGraphFile = Join-Path $capturesRoot 'player-owner-graph.json'
$sourceChainFile = Join-Path $capturesRoot 'player-source-chain.json'
$coordTraceFile = Join-Path $capturesRoot 'player-coord-write-trace.json'
$projectorTraceFile = Join-Path $capturesRoot 'player-state-projector-trace.json'

$ownerComponents = Read-JsonArtifact -Path $ownerComponentsFile -Role 'owner-components'
$selectorTrace = Read-JsonArtifact -Path $selectorTraceFile -Role 'selector-owner-trace' -Optional
$sourceAccessorFamily = Read-JsonArtifact -Path $sourceAccessorFile -Role 'source-accessor-family' -Optional
$statHubGraph = Read-JsonArtifact -Path $statHubGraphFile -Role 'stat-hub-graph' -Optional
$currentAnchor = Read-JsonArtifact -Path $currentAnchorFile -Role 'current-anchor' -Optional
$ownerGraph = Read-JsonArtifact -Path $ownerGraphFile -Role 'owner-graph' -Optional
$null = Read-JsonArtifact -Path $sourceChainFile -Role 'source-chain' -Optional
$null = Read-JsonArtifact -Path $coordTraceFile -Role 'coord-write-trace' -Optional
$projectorTrace = Read-JsonArtifact -Path $projectorTraceFile -Role 'state-projector-trace' -Optional

$selectedSourceAddress = [string]$ownerComponents.Owner.SelectedSourceAddress
$ownerAddress = [string]$ownerComponents.Owner.Address
$containerAddress = [string]$ownerComponents.Owner.ContainerAddress
$stateRecordAddress = [string]$ownerComponents.Owner.StateRecordAddress

if ([string]::IsNullOrWhiteSpace($selectedSourceAddress)) {
    throw "Owner-components artifact '$ownerComponentsFile' does not expose Owner.SelectedSourceAddress."
}

if ($selectorTrace) {
    $traceSelectedSource = [string]$selectorTrace.SelectedSource.Address
    if (-not [string]::IsNullOrWhiteSpace($traceSelectedSource) -and -not $traceSelectedSource.Equals($selectedSourceAddress, [System.StringComparison]::OrdinalIgnoreCase)) {
        Add-Warning "Selector trace selected source '$traceSelectedSource' differs from owner-components selected source '$selectedSourceAddress'."
    }
}

if ($sourceAccessorFamily) {
    $accessorSource = [string]$sourceAccessorFamily.SourceObjectAddress
    if (-not [string]::IsNullOrWhiteSpace($accessorSource) -and -not $accessorSource.Equals($selectedSourceAddress, [System.StringComparison]::OrdinalIgnoreCase)) {
        Add-Warning "Source-accessor family still points at '$accessorSource' while owner-components selected source is '$selectedSourceAddress'. Offsets were kept, but the lineage is stale."
    }
}

if ($statHubGraph) {
    $statSource = [string]$statHubGraph.SelectedSourceAddress
    if (-not [string]::IsNullOrWhiteSpace($statSource) -and -not $statSource.Equals($selectedSourceAddress, [System.StringComparison]::OrdinalIgnoreCase)) {
        Add-Warning "Stat-hub graph still points at '$statSource' while owner-components selected source is '$selectedSourceAddress'. Ranked hubs were included as optional stale-run regions."
    }
}

if ($projectorTrace) {
    $projectorOwnerAddress = [string]$projectorTrace.Owner.Address
    if (-not [string]::IsNullOrWhiteSpace($projectorOwnerAddress) -and -not $projectorOwnerAddress.Equals($ownerAddress, [System.StringComparison]::OrdinalIgnoreCase)) {
        Add-Warning "State-projector trace owner '$projectorOwnerAddress' differs from owner-components owner '$ownerAddress'. Projector slots were included as optional stale-run regions."
    }

    $projectorStateRecordAddress = [string]$projectorTrace.Owner.StateRecordAddress
    if (-not [string]::IsNullOrWhiteSpace($projectorStateRecordAddress) -and -not $projectorStateRecordAddress.Equals($stateRecordAddress, [System.StringComparison]::OrdinalIgnoreCase)) {
        Add-Warning "State-projector trace state record '$projectorStateRecordAddress' differs from owner-components state record '$stateRecordAddress'. Projector slots were included as optional stale-run regions."
    }
}

$ownerArtifactFile = [System.IO.Path]::GetFullPath($ownerComponentsFile)
$sourceArtifactFile = if ($sourceAccessorFamily) { [System.IO.Path]::GetFullPath($sourceAccessorFile) } else { $ownerArtifactFile }
$selectorArtifactFile = if ($selectorTrace) { [System.IO.Path]::GetFullPath($selectorTraceFile) } else { $ownerArtifactFile }
$statArtifactFile = if ($statHubGraph) { [System.IO.Path]::GetFullPath($statHubGraphFile) } else { $ownerArtifactFile }

$containerLength = [Math]::Max(128, ([int]$ownerComponents.EntryCount * 8))
Add-Region -Name 'selected-source-object' -Category 'source-object' -Address (Parse-HexUInt64 -Value $selectedSourceAddress) -Length $ObjectWindowBytes -Required $true -Priority 100 -SourceArtifactFile $ownerArtifactFile -Notes 'Primary selected source component from the owner/component table.'
Add-OffsetRegion -Name 'selected-source-coord48' -Category 'source-field' -BaseAddress $selectedSourceAddress -Offset 0x48 -Length 12 -Required $true -Priority 110 -SourceArtifactFile $sourceArtifactFile -Notes 'Coordinate triplet at +0x48.'
Add-OffsetRegion -Name 'selected-source-basis60' -Category 'source-field' -BaseAddress $selectedSourceAddress -Offset 0x60 -Length 36 -Required $true -Priority 105 -SourceArtifactFile $sourceArtifactFile -Notes 'Orientation/basis block at +0x60.'
Add-OffsetRegion -Name 'selected-source-coord88' -Category 'source-field' -BaseAddress $selectedSourceAddress -Offset 0x88 -Length 12 -Required $true -Priority 110 -SourceArtifactFile $sourceArtifactFile -Notes 'Duplicate coordinate triplet at +0x88.'
Add-OffsetRegion -Name 'selected-source-basis94' -Category 'source-field' -BaseAddress $selectedSourceAddress -Offset 0x94 -Length 36 -Required $true -Priority 105 -SourceArtifactFile $sourceArtifactFile -Notes 'Duplicate orientation/basis block at +0x94.'

if (-not [string]::IsNullOrWhiteSpace($ownerAddress)) {
    Add-Region -Name 'owner-object' -Category 'owner-object' -Address (Parse-HexUInt64 -Value $ownerAddress) -Length $ObjectWindowBytes -Required $true -Priority 90 -SourceArtifactFile $ownerArtifactFile -Notes 'Current owner object selected by the selector trace / owner-components chain.'
}

if (-not [string]::IsNullOrWhiteSpace($containerAddress)) {
    Add-Region -Name 'owner-container-slots' -Category 'owner-container' -Address (Parse-HexUInt64 -Value $containerAddress) -Length $containerLength -Required $true -Priority 90 -SourceArtifactFile $ownerArtifactFile -Notes 'Live owner container/component-table slots.'
}

if (-not [string]::IsNullOrWhiteSpace($stateRecordAddress)) {
    Add-Region -Name 'owner-state-record' -Category 'owner-state' -Address (Parse-HexUInt64 -Value $stateRecordAddress) -Length $StateWindowBytes -Required $true -Priority 85 -SourceArtifactFile $ownerArtifactFile -Notes 'Owner-linked state record sampled alongside the selected source.'
}

if ($projectorTrace) {
    Add-ProjectorSlotRegions -ProjectorTrace $projectorTrace -SourceArtifactFile ([System.IO.Path]::GetFullPath($projectorTraceFile))
}

$selectedEntry = $null
foreach ($entry in @($ownerComponents.Entries)) {
    if ($null -eq $entry) {
        continue
    }

    if ([string]$entry.Address -eq $selectedSourceAddress) {
        $selectedEntry = $entry
        break
    }
}

if ($selectedEntry -and -not [string]::IsNullOrWhiteSpace($containerAddress)) {
    $slotOffset = [long]$selectedEntry.Index * 8L
    Add-OffsetRegion -Name 'selected-source-slot' -Category 'owner-container-slot' -BaseAddress $containerAddress -Offset $slotOffset -Length 8 -Required $true -Priority 92 -SourceArtifactFile $ownerArtifactFile -Notes ('Container slot for selected source index {0}.' -f $selectedEntry.Index)
}

if ($ownerGraph) {
    $wrapperRank = 0
    $wrapperMap = [ordered]@{}
    foreach ($child in @($ownerGraph.Children | Where-Object { [string]$_.Role -eq 'owner-state-wrapper' } | Sort-Object OwnerOffset)) {
        $wrapperAddress = [string]$child.Address
        if ([string]::IsNullOrWhiteSpace($wrapperAddress)) {
            continue
        }

        if (-not $wrapperMap.Contains($wrapperAddress)) {
            $wrapperMap[$wrapperAddress] = $child
        }
    }

    foreach ($wrapper in @($wrapperMap.Values)) {
        if ($null -eq $wrapper -or [string]::IsNullOrWhiteSpace([string]$wrapper.Address)) {
            continue
        }

        $wrapperRank++
        Add-Region -Name ('owner-state-wrapper-{0}' -f $wrapperRank) -Category 'owner-state-wrapper' -Address (Parse-HexUInt64 -Value ([string]$wrapper.Address)) -Length $ObjectWindowBytes -Required $false -Priority (84 - $wrapperRank) -SourceArtifactFile ([System.IO.Path]::GetFullPath($ownerGraphFile)) -Notes ('Owner-linked state wrapper discovered in the owner graph at offset {0}.' -f [string]$wrapper.OwnerOffsetHex)
    }
}

if ($statHubGraph) {
    $lineageMatches = ([string]$statHubGraph.SelectedSourceAddress).Equals($selectedSourceAddress, [System.StringComparison]::OrdinalIgnoreCase)

    foreach ($component in @($statHubGraph.IdentityComponents | Select-Object -First 4)) {
        if ($null -eq $component -or [string]::IsNullOrWhiteSpace([string]$component.Address)) {
            continue
        }

        Add-Region -Name ('identity-component-{0}' -f $component.Index) -Category 'identity-component' -Address (Parse-HexUInt64 -Value ([string]$component.Address)) -Length $ObjectWindowBytes -Required $lineageMatches -Priority (70 - [int]$component.Index) -SourceArtifactFile $statArtifactFile -Notes ('Identity-bearing component candidate at index {0}.' -f $component.Index)
    }

    $hubRank = 0
    foreach ($hub in @($statHubGraph.RankedSharedHubs | Select-Object -First $TopSharedHubs)) {
        if ($null -eq $hub -or [string]::IsNullOrWhiteSpace([string]$hub.Address)) {
            continue
        }

        $hubRank++
        $reasons = @($hub.Reasons) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
        $note = if ($reasons.Count -gt 0) {
            'Ranked shared hub #{0}. {1}' -f $hubRank, ($reasons -join '; ')
        }
        else {
            'Ranked shared hub #{0}.' -f $hubRank
        }

        Add-Region -Name ('shared-hub-{0}' -f $hubRank) -Category ($(if ($lineageMatches) { 'stat-hub' } else { 'stat-hub-stale' })) -Address (Parse-HexUInt64 -Value ([string]$hub.Address)) -Length $HubWindowBytes -Required $false -Priority (60 - $hubRank) -SourceArtifactFile $statArtifactFile -Notes $note
        Add-HubFieldRegions -Hub $hub -HubRank $hubRank -HubCategory $(if ($lineageMatches) { 'stat-hub-field' } else { 'stat-hub-stale-field' }) -SourceArtifactFile $statArtifactFile
    }
}

if ($currentAnchor -and -not [string]::IsNullOrWhiteSpace([string]$currentAnchor.AddressHex)) {
    $anchorAddress = Parse-HexUInt64 -Value ([string]$currentAnchor.AddressHex)
    $candidateOffsets = @()
    foreach ($propertyName in 'LevelOffset', 'HealthOffset', 'CoordXOffset', 'CoordYOffset', 'CoordZOffset') {
        $property = $currentAnchor.PSObject.Properties[$propertyName]
        if ($null -ne $property -and $null -ne $property.Value) {
            $candidateOffsets += [int]$property.Value
        }
    }

    if ($candidateOffsets.Count -gt 0) {
        $windowStartOffset = ($candidateOffsets | Measure-Object -Minimum).Minimum
        $windowStart = [long]$anchorAddress + [long]$windowStartOffset - 16
        if ($windowStart -lt 1) {
            $windowStart = 1
        }

        $windowLength = [Math]::Max(192, ([Math]::Abs([int]$windowStartOffset) + 160))
        Add-Region -Name 'player-current-cache-window' -Category 'bootstrap-cache' -Address ([UInt64]$windowStart) -Length $windowLength -Required $false -Priority 20 -SourceArtifactFile ([System.IO.Path]::GetFullPath($currentAnchorFile)) -Notes 'Legacy current-player cache/blob window kept only as a bootstrap/reference capture.'
    }
}

$document = [ordered]@{
    Mode = 'session-watchset'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
    ProcessName = $ProcessName
    PreferredSourceAddress = $selectedSourceAddress
    Artifacts = $artifacts.ToArray()
    Warnings = $warnings.ToArray()
    Regions = $regions.ToArray()
}

$outputDirectory = Split-Path -Path $resolvedOutputFile -Parent
if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

$document | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $resolvedOutputFile -Encoding UTF8

$result = [ordered]@{
    Mode = 'session-watchset-export'
    OutputFile = $resolvedOutputFile
    ProcessName = $ProcessName
    PreferredSourceAddress = $selectedSourceAddress
    RegionCount = $regions.Count
    WarningCount = $warnings.Count
    Warnings = $warnings.ToArray()
}

if ($Json) {
    $result | ConvertTo-Json -Depth 8
    exit 0
}

Write-Host "Discovery watchset exported." -ForegroundColor Green
Write-Host ("Output:              {0}" -f $resolvedOutputFile)
Write-Host ("Preferred source:    {0}" -f $selectedSourceAddress)
Write-Host ("Regions:             {0}" -f $regions.Count)
Write-Host ("Warnings:            {0}" -f $warnings.Count)

if ($warnings.Count -gt 0) {
    Write-Host ""
    Write-Host "Warnings:" -ForegroundColor Yellow
    foreach ($warning in $warnings) {
        Write-Host ("- {0}" -f $warning)
    }
}
