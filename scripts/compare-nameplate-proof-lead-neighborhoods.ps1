[CmdletBinding()]
param(
    [string]$BaselineRunRoot,
    [string]$ReproofRunRoot,
    [string]$BaselineFile,
    [string]$ReproofFile,
    [int]$MinRepeatedRootCount = 1,
    [int]$MinRepeatedEdgeCount = 0,
    [int]$Top = 20,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Resolve-NeighborhoodPath {
    param(
        [string]$RunRoot,
        [string]$File,
        [Parameter(Mandatory = $true)][string]$Label
    )

    if (-not [string]::IsNullOrWhiteSpace($File)) {
        return (Resolve-Path -LiteralPath $File).Path
    }

    if (-not [string]::IsNullOrWhiteSpace($RunRoot)) {
        $resolvedRunRoot = (Resolve-Path -LiteralPath $RunRoot).Path
        return (Resolve-Path -LiteralPath (Join-Path $resolvedRunRoot 'lead-neighborhoods\nameplate-proof-lead-neighborhoods.json')).Path
    }

    throw "Provide either -${Label}RunRoot or -${Label}File."
}

function Read-JsonFile {
    param([Parameter(Mandatory = $true)][string]$Path)
    return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json -Depth 100
}

function Normalize-Address {
    param([object]$Value)

    if ($null -eq $Value) {
        return $null
    }

    $text = ([string]$Value).Trim()
    if ([string]::IsNullOrWhiteSpace($text)) {
        return $null
    }

    if ($text.StartsWith('0x', [System.StringComparison]::OrdinalIgnoreCase)) {
        $text = $text.Substring(2)
    }

    if ($text -notmatch '^[0-9A-Fa-f]+$') {
        return $null
    }

    return ('0X{0}' -f $text.ToUpperInvariant())
}

function Add-Check {
    param(
        [System.Collections.Generic.List[object]]$Checks,
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][bool]$Passed,
        [string]$Detail,
        [object]$Data
    )

    $Checks.Add([pscustomobject][ordered]@{
        name = $Name
        status = if ($Passed) { 'passed' } else { 'failed' }
        detail = $Detail
        data = $Data
    }) | Out-Null
}

function Get-SelectedRootAddresses {
    param([object]$Document)

    if ($null -eq $Document.leadSelection -or $null -eq $Document.leadSelection.selectedLeads) {
        return @()
    }

    return @($Document.leadSelection.selectedLeads |
        ForEach-Object { Normalize-Address -Value $_.address } |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
        Sort-Object -Unique)
}

function Get-RootNodeAddresses {
    param([object]$Document)

    if ($null -eq $Document.pointerSubgraph -or $null -eq $Document.pointerSubgraph.nodes) {
        return @()
    }

    return @($Document.pointerSubgraph.nodes |
        Where-Object { [int]$_.depth -eq 0 } |
        ForEach-Object { Normalize-Address -Value $_.address } |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
        Sort-Object -Unique)
}

function Get-NodeAddressMap {
    param([object]$Document)

    $map = @{}
    if ($null -eq $Document.pointerSubgraph -or $null -eq $Document.pointerSubgraph.nodes) {
        return $map
    }

    foreach ($node in @($Document.pointerSubgraph.nodes)) {
        $address = Normalize-Address -Value $node.address
        if (-not [string]::IsNullOrWhiteSpace($address) -and -not $map.ContainsKey($address)) {
            $map[$address] = $node
        }
    }

    return $map
}

function Get-EdgeKey {
    param([object]$Edge)

    $from = Normalize-Address -Value $Edge.fromAddress
    $to = Normalize-Address -Value $Edge.toAddress
    if ([string]::IsNullOrWhiteSpace($from) -or [string]::IsNullOrWhiteSpace($to)) {
        return $null
    }

    return ('{0}->{1}@{2}' -f $from, $to, [string]$Edge.sourceOffsetHex)
}

function Get-EdgeMap {
    param([object]$Document)

    $map = @{}
    if ($null -eq $Document.pointerSubgraph -or $null -eq $Document.pointerSubgraph.edges) {
        return $map
    }

    foreach ($edge in @($Document.pointerSubgraph.edges)) {
        $key = Get-EdgeKey -Edge $edge
        if (-not [string]::IsNullOrWhiteSpace($key) -and -not $map.ContainsKey($key)) {
            $map[$key] = $edge
        }
    }

    return $map
}

function Intersect-Strings {
    param([string[]]$Left, [string[]]$Right)

    $rightSet = [System.Collections.Generic.HashSet[string]]::new([string[]]@($Right), [System.StringComparer]::OrdinalIgnoreCase)
    return @($Left | Where-Object { $rightSet.Contains([string]$_) } | Sort-Object -Unique)
}

function Get-OptionalPropertyValue {
    param(
        [object]$InputObject,
        [Parameter(Mandatory = $true)][string]$Name,
        [object]$Default = $null
    )

    if ($null -eq $InputObject) {
        return $Default
    }

    $property = $InputObject.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $Default
    }

    return $property.Value
}

if ($MinRepeatedRootCount -lt 0) {
    throw 'MinRepeatedRootCount cannot be negative.'
}
if ($MinRepeatedEdgeCount -lt 0) {
    throw 'MinRepeatedEdgeCount cannot be negative.'
}
if ($Top -le 0) {
    throw 'Top must be greater than zero.'
}

$baselinePath = Resolve-NeighborhoodPath -RunRoot $BaselineRunRoot -File $BaselineFile -Label 'Baseline'
$reproofPath = Resolve-NeighborhoodPath -RunRoot $ReproofRunRoot -File $ReproofFile -Label 'Reproof'
$baseline = Read-JsonFile -Path $baselinePath
$reproof = Read-JsonFile -Path $reproofPath
$checks = [System.Collections.Generic.List[object]]::new()

foreach ($entry in @(
    [pscustomobject]@{ Name = 'baseline'; Document = $baseline; Path = $baselinePath },
    [pscustomobject]@{ Name = 'reproof'; Document = $reproof; Path = $reproofPath }
)) {
    Add-Check -Checks $checks -Name "$($entry.Name)-ok" -Passed ([bool]$entry.Document.ok) -Detail "ok=$($entry.Document.ok), path=$($entry.Path)"
    Add-Check -Checks $checks -Name "$($entry.Name)-capture-mode" -Passed ([string]$entry.Document.mode -eq 'capture') -Detail "mode=$($entry.Document.mode)"
    Add-Check -Checks $checks -Name "$($entry.Name)-controls-input-false" -Passed (-not [bool]$entry.Document.controlsInput) -Detail "controlsInput=$($entry.Document.controlsInput)"
    Add-Check -Checks $checks -Name "$($entry.Name)-subgraph-present" -Passed ($null -ne $entry.Document.pointerSubgraph) -Detail 'Expected pointerSubgraph in captured lead-neighborhood artifact.'
}

$baselineSelectedRoots = @(Get-SelectedRootAddresses -Document $baseline)
$reproofSelectedRoots = @(Get-SelectedRootAddresses -Document $reproof)
$baselineRootNodes = @(Get-RootNodeAddresses -Document $baseline)
$reproofRootNodes = @(Get-RootNodeAddresses -Document $reproof)
$repeatedSelectedRoots = @(Intersect-Strings -Left $baselineSelectedRoots -Right $reproofSelectedRoots)
$repeatedRootNodes = @(Intersect-Strings -Left $baselineRootNodes -Right $reproofRootNodes)

$baselineNodes = Get-NodeAddressMap -Document $baseline
$reproofNodes = Get-NodeAddressMap -Document $reproof
$repeatedNodeAddresses = @(Intersect-Strings -Left ([string[]]@($baselineNodes.Keys)) -Right ([string[]]@($reproofNodes.Keys)))

$baselineEdges = Get-EdgeMap -Document $baseline
$reproofEdges = Get-EdgeMap -Document $reproof
$repeatedEdgeKeys = @(Intersect-Strings -Left ([string[]]@($baselineEdges.Keys)) -Right ([string[]]@($reproofEdges.Keys)))

Add-Check -Checks $checks -Name 'minimum-repeated-selected-roots' -Passed ($repeatedSelectedRoots.Count -ge $MinRepeatedRootCount) -Detail "repeatedSelectedRootCount=$($repeatedSelectedRoots.Count), required=$MinRepeatedRootCount" -Data @($repeatedSelectedRoots)
Add-Check -Checks $checks -Name 'minimum-repeated-edges' -Passed ($repeatedEdgeKeys.Count -ge $MinRepeatedEdgeCount) -Detail "repeatedEdgeCount=$($repeatedEdgeKeys.Count), required=$MinRepeatedEdgeCount" -Data @($repeatedEdgeKeys | Select-Object -First $Top)

$nodeMatches = @($repeatedNodeAddresses | Select-Object -First $Top | ForEach-Object {
    $address = [string]$_
    $baselineNode = $baselineNodes[$address]
    $reproofNode = $reproofNodes[$address]
    $baselineAsciiPreview = [string](Get-OptionalPropertyValue -InputObject $baselineNode -Name 'asciiPreview' -Default '')
    $reproofAsciiPreview = [string](Get-OptionalPropertyValue -InputObject $reproofNode -Name 'asciiPreview' -Default '')
    [pscustomobject][ordered]@{
        address = $address
        baselineDepth = [int]$baselineNode.depth
        reproofDepth = [int]$reproofNode.depth
        baselineRootLabels = @(Get-OptionalPropertyValue -InputObject $baselineNode -Name 'rootLabels' -Default @())
        reproofRootLabels = @(Get-OptionalPropertyValue -InputObject $reproofNode -Name 'rootLabels' -Default @())
        asciiPreviewMatches = ($baselineAsciiPreview -eq $reproofAsciiPreview)
        baselineAsciiPreview = $baselineAsciiPreview
        reproofAsciiPreview = $reproofAsciiPreview
    }
})

$edgeMatches = @($repeatedEdgeKeys | Select-Object -First $Top | ForEach-Object {
    $key = [string]$_
    $edge = $baselineEdges[$key]
    [pscustomobject][ordered]@{
        key = $key
        fromAddress = (Normalize-Address -Value $edge.fromAddress)
        toAddress = (Normalize-Address -Value $edge.toAddress)
        sourceOffsetHex = [string]$edge.sourceOffsetHex
    }
})

$failedChecks = @($checks | Where-Object { $_.status -ne 'passed' })
$result = [pscustomobject][ordered]@{
    ok = ($failedChecks.Count -eq 0)
    baselineFile = $baselinePath
    reproofFile = $reproofPath
    checks = @($checks)
    counts = [pscustomobject][ordered]@{
        baselineSelectedRoots = $baselineSelectedRoots.Count
        reproofSelectedRoots = $reproofSelectedRoots.Count
        repeatedSelectedRoots = $repeatedSelectedRoots.Count
        baselineRootNodes = $baselineRootNodes.Count
        reproofRootNodes = $reproofRootNodes.Count
        repeatedRootNodes = $repeatedRootNodes.Count
        baselineNodes = $baselineNodes.Count
        reproofNodes = $reproofNodes.Count
        repeatedNodes = $repeatedNodeAddresses.Count
        baselineEdges = $baselineEdges.Count
        reproofEdges = $reproofEdges.Count
        repeatedEdges = $repeatedEdgeKeys.Count
    }
    repeatedSelectedRoots = @($repeatedSelectedRoots | Select-Object -First $Top)
    repeatedRootNodes = @($repeatedRootNodes | Select-Object -First $Top)
    repeatedNodes = @($nodeMatches)
    repeatedEdges = @($edgeMatches)
}

if ($Json) {
    $result | ConvertTo-Json -Depth 80
}
else {
    $result
}

if (-not $result.ok) {
    exit 1
}
