[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Left,

    [Parameter(Mandatory = $true, Position = 1)]
    [string]$Right,

    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Resolve-OwnerStateArtifactPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$InputPath
    )

    $resolved = [System.IO.Path]::GetFullPath($InputPath)
    if (-not (Test-Path -LiteralPath $resolved)) {
        throw "Path not found: $InputPath"
    }

    $item = Get-Item -LiteralPath $resolved
    if ($item.PSIsContainer) {
        $artifactPath = Join-Path $resolved 'artifacts\owner-state-neighborhood.json'
        if (-not (Test-Path -LiteralPath $artifactPath)) {
            throw "Directory does not contain artifacts\\owner-state-neighborhood.json: $resolved"
        }

        return $artifactPath
    }

    return $resolved
}

function Read-OwnerStateDocument {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json -Depth 80
}

function ConvertTo-SortedUniqueStringArray {
    param(
        $Values
    )

    $result = @()
    foreach ($value in @($Values)) {
        $text = [string]$value
        if ([string]::IsNullOrWhiteSpace($text)) {
            continue
        }

        $result += $text
    }

    return @($result | Sort-Object -Unique)
}

function Get-AddressSet {
    param(
        $Values
    )

    $set = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($value in @($Values)) {
        $text = [string]$value
        if ([string]::IsNullOrWhiteSpace($text)) {
            continue
        }

        [void]$set.Add($text)
    }

    return $set
}

function Compare-StringSet {
    param(
        [string[]]$LeftValues = @(),

        [string[]]$RightValues = @()
    )

    $leftSet = Get-AddressSet -Values @($LeftValues)
    $rightSet = Get-AddressSet -Values @($RightValues)

    $added = New-Object System.Collections.Generic.List[string]
    foreach ($value in $rightSet) {
        if (-not $leftSet.Contains($value)) {
            $added.Add($value) | Out-Null
        }
    }

    $removed = New-Object System.Collections.Generic.List[string]
    foreach ($value in $leftSet) {
        if (-not $rightSet.Contains($value)) {
            $removed.Add($value) | Out-Null
        }
    }

    return [ordered]@{
        Added = @($added.ToArray() | Sort-Object)
        Removed = @($removed.ToArray() | Sort-Object)
    }
}

function Get-FollowPointerMap {
    param(
        $Document
    )

    $map = [ordered]@{}
    foreach ($slot in @($Document.Slots)) {
        if ($null -eq $slot) {
            continue
        }

        $slotLabel = [string]$slot.Label
        if ([string]::IsNullOrWhiteSpace($slotLabel)) {
            continue
        }

        $map[$slotLabel] = ConvertTo-SortedUniqueStringArray -Values @($slot.FollowPointers | ForEach-Object { $_.Address })
    }

    return $map
}

function Get-NodeMap {
    param(
        $Document
    )

    $map = @{}
    $subgraphProperty = $Document.PSObject.Properties['PointerSubgraph']
    if ($null -eq $subgraphProperty -or $null -eq $subgraphProperty.Value) {
        return ,$map
    }

    foreach ($node in @($subgraphProperty.Value.Nodes)) {
        if ($null -eq $node -or [string]::IsNullOrWhiteSpace([string]$node.Address)) {
            continue
        }

        $map[[string]$node.Address] = $node
    }

    return ,$map
}

function Get-EdgeKeySet {
    param(
        $Document
    )

    $keys = New-Object System.Collections.Generic.HashSet[string]([System.StringComparer]::OrdinalIgnoreCase)
    $subgraphProperty = $Document.PSObject.Properties['PointerSubgraph']
    if ($null -eq $subgraphProperty -or $null -eq $subgraphProperty.Value) {
        return ,$keys
    }

    foreach ($edge in @($subgraphProperty.Value.Edges)) {
        if ($null -eq $edge) {
            continue
        }

        $fromAddress = [string]$edge.FromAddress
        $toAddress = [string]$edge.ToAddress
        $offsetHex = [string]$edge.SourceOffsetHex
        if ([string]::IsNullOrWhiteSpace($fromAddress) -or [string]::IsNullOrWhiteSpace($toAddress) -or [string]::IsNullOrWhiteSpace($offsetHex)) {
            continue
        }

        [void]$keys.Add(('{0}|{1}|{2}' -f $fromAddress, $toAddress, $offsetHex))
    }

    return ,$keys
}

function Compare-NodeMaps {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable]$LeftMap,

        [Parameter(Mandatory = $true)]
        [hashtable]$RightMap
    )

    $leftAddresses = @(ConvertTo-SortedUniqueStringArray -Values $LeftMap.Keys)
    $rightAddresses = @(ConvertTo-SortedUniqueStringArray -Values $RightMap.Keys)
    $addressDelta = Compare-StringSet -LeftValues @($leftAddresses) -RightValues @($rightAddresses)
    $changed = New-Object System.Collections.Generic.List[object]
    foreach ($address in @($leftAddresses)) {
        if (-not (@($rightAddresses) -contains $address)) {
            continue
        }

        $leftNode = $LeftMap[$address]
        $rightNode = $RightMap[$address]
        if ($null -eq $leftNode -or $null -eq $rightNode) {
            continue
        }

        $fieldChanges = New-Object System.Collections.Generic.List[string]
        if ([int]$leftNode.Depth -ne [int]$rightNode.Depth) {
            $fieldChanges.Add('Depth') | Out-Null
        }

        if ([string]$leftNode.AsciiPreview -ne [string]$rightNode.AsciiPreview) {
            $fieldChanges.Add('AsciiPreview') | Out-Null
        }

        $leftRoots = ConvertTo-SortedUniqueStringArray -Values $leftNode.RootLabels
        $rightRoots = ConvertTo-SortedUniqueStringArray -Values $rightNode.RootLabels
        if (($leftRoots -join '|') -ne ($rightRoots -join '|')) {
            $fieldChanges.Add('RootLabels') | Out-Null
        }

        if ([int]$leftNode.PointerMatchCount -ne [int]$rightNode.PointerMatchCount) {
            $fieldChanges.Add('PointerMatchCount') | Out-Null
        }

        $leftQwords = @($leftNode.QwordPreview).Count
        $rightQwords = @($rightNode.QwordPreview).Count
        if ($leftQwords -ne $rightQwords) {
            $fieldChanges.Add('QwordPreviewCount') | Out-Null
        }

        if ($fieldChanges.Count -gt 0) {
            $changed.Add([ordered]@{
                    Address = $address
                    Fields = @($fieldChanges.ToArray())
                }) | Out-Null
        }
    }

    return [ordered]@{
        Added = $addressDelta.Added
        Removed = $addressDelta.Removed
        Changed = @($changed.ToArray())
    }
}

$leftArtifact = Resolve-OwnerStateArtifactPath -InputPath $Left
$rightArtifact = Resolve-OwnerStateArtifactPath -InputPath $Right
$leftDoc = Read-OwnerStateDocument -Path $leftArtifact
$rightDoc = Read-OwnerStateDocument -Path $rightArtifact

$leftFollowPointerMap = Get-FollowPointerMap -Document $leftDoc
$rightFollowPointerMap = Get-FollowPointerMap -Document $rightDoc
$slotLabels = ConvertTo-SortedUniqueStringArray -Values @($leftFollowPointerMap.Keys + $rightFollowPointerMap.Keys)

$slotDiffs = New-Object System.Collections.Generic.List[object]
foreach ($slotLabel in $slotLabels) {
    $leftValues = if ($leftFollowPointerMap.Contains($slotLabel)) { @($leftFollowPointerMap[$slotLabel]) } else { @() }
    $rightValues = if ($rightFollowPointerMap.Contains($slotLabel)) { @($rightFollowPointerMap[$slotLabel]) } else { @() }
    $delta = Compare-StringSet -LeftValues $leftValues -RightValues $rightValues

    if (@($delta.Added).Count -gt 0 -or @($delta.Removed).Count -gt 0) {
        $slotDiffs.Add([ordered]@{
                SlotLabel = $slotLabel
                Added = @($delta.Added)
                Removed = @($delta.Removed)
            }) | Out-Null
    }
}

$leftNodeMap = Get-NodeMap -Document $leftDoc
$rightNodeMap = Get-NodeMap -Document $rightDoc
if ($null -eq $leftNodeMap) { $leftNodeMap = @{} }
if ($null -eq $rightNodeMap) { $rightNodeMap = @{} }
$leftEdgeKeys = Get-EdgeKeySet -Document $leftDoc
$rightEdgeKeys = Get-EdgeKeySet -Document $rightDoc
if ($null -eq $leftEdgeKeys) { $leftEdgeKeys = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase) }
if ($null -eq $rightEdgeKeys) { $rightEdgeKeys = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase) }

$leftHasSubgraph = ($leftDoc.PSObject.Properties['PointerSubgraph'] -ne $null -and $leftDoc.PSObject.Properties['PointerSubgraph'].Value -ne $null)
$rightHasSubgraph = ($rightDoc.PSObject.Properties['PointerSubgraph'] -ne $null -and $rightDoc.PSObject.Properties['PointerSubgraph'].Value -ne $null)

if ($leftHasSubgraph -and $rightHasSubgraph) {
    $nodeDiff = Compare-NodeMaps -LeftMap $leftNodeMap -RightMap $rightNodeMap
    $edgeDiff = Compare-StringSet -LeftValues @($leftEdgeKeys) -RightValues @($rightEdgeKeys)
}
else {
    $nodeDiff = [ordered]@{
        Added = if (-not $leftHasSubgraph -and $rightHasSubgraph) { @(ConvertTo-SortedUniqueStringArray -Values $rightNodeMap.Keys) } else { @() }
        Removed = if ($leftHasSubgraph -and -not $rightHasSubgraph) { @(ConvertTo-SortedUniqueStringArray -Values $leftNodeMap.Keys) } else { @() }
        Changed = @()
        Note = 'PointerSubgraph missing on one side; node-level field comparison skipped.'
    }
    $edgeDiff = [ordered]@{
        Added = if (-not $leftHasSubgraph -and $rightHasSubgraph) { @(ConvertTo-SortedUniqueStringArray -Values @($rightEdgeKeys)) } else { @() }
        Removed = if ($leftHasSubgraph -and -not $rightHasSubgraph) { @(ConvertTo-SortedUniqueStringArray -Values @($leftEdgeKeys)) } else { @() }
        Note = 'PointerSubgraph missing on one side; edge-level comparison skipped.'
    }
}

$result = [ordered]@{
    Mode = 'owner-state-neighborhood-diff'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    LeftArtifact = $leftArtifact
    RightArtifact = $rightArtifact
    LeftSummary = [ordered]@{
        GeneratedAtUtc = [string]$leftDoc.GeneratedAtUtc
        SelectedSourceAddress = [string]$leftDoc.Owner.SelectedSourceAddress
        StateRecordAddress = [string]$leftDoc.Owner.StateRecordAddress
        SlotCount = @($leftDoc.Slots).Count
        PointerSubgraphNodeCount = if ($null -ne $leftDoc.PSObject.Properties['PointerSubgraph'] -and $null -ne $leftDoc.PSObject.Properties['PointerSubgraph'].Value) { [int]$leftDoc.PSObject.Properties['PointerSubgraph'].Value.NodeCount } else { 0 }
        PointerSubgraphEdgeCount = if ($null -ne $leftDoc.PSObject.Properties['PointerSubgraph'] -and $null -ne $leftDoc.PSObject.Properties['PointerSubgraph'].Value) { [int]$leftDoc.PSObject.Properties['PointerSubgraph'].Value.EdgeCount } else { 0 }
    }
    RightSummary = [ordered]@{
        GeneratedAtUtc = [string]$rightDoc.GeneratedAtUtc
        SelectedSourceAddress = [string]$rightDoc.Owner.SelectedSourceAddress
        StateRecordAddress = [string]$rightDoc.Owner.StateRecordAddress
        SlotCount = @($rightDoc.Slots).Count
        PointerSubgraphNodeCount = if ($null -ne $rightDoc.PSObject.Properties['PointerSubgraph'] -and $null -ne $rightDoc.PSObject.Properties['PointerSubgraph'].Value) { [int]$rightDoc.PSObject.Properties['PointerSubgraph'].Value.NodeCount } else { 0 }
        PointerSubgraphEdgeCount = if ($null -ne $rightDoc.PSObject.Properties['PointerSubgraph'] -and $null -ne $rightDoc.PSObject.Properties['PointerSubgraph'].Value) { [int]$rightDoc.PSObject.Properties['PointerSubgraph'].Value.EdgeCount } else { 0 }
    }
    SlotFollowPointerDiffs = @($slotDiffs.ToArray())
    PointerSubgraph = [ordered]@{
        NodeDiff = $nodeDiff
        EdgeDiff = [ordered]@{
            Added = @($edgeDiff.Added)
            Removed = @($edgeDiff.Removed)
        }
    }
}

if ($Json) {
    $result | ConvertTo-Json -Depth 20
    exit 0
}

Write-Host 'Owner-state neighborhood diff generated.' -ForegroundColor Green
Write-Host ("Left:                 {0}" -f $leftArtifact)
Write-Host ("Right:                {0}" -f $rightArtifact)
Write-Host ("Slot diffs:           {0}" -f @($result.SlotFollowPointerDiffs).Count)
Write-Host ("Node additions:       {0}" -f @($result.PointerSubgraph.NodeDiff.Added).Count)
Write-Host ("Node removals:        {0}" -f @($result.PointerSubgraph.NodeDiff.Removed).Count)
Write-Host ("Node field changes:   {0}" -f @($result.PointerSubgraph.NodeDiff.Changed).Count)
Write-Host ("Edge additions:       {0}" -f @($result.PointerSubgraph.EdgeDiff.Added).Count)
Write-Host ("Edge removals:        {0}" -f @($result.PointerSubgraph.EdgeDiff.Removed).Count)
