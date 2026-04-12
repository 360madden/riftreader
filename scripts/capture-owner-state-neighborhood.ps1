[CmdletBinding()]
param(
    [switch]$Json,
    [switch]$RefreshProjectorTrace,
    [int]$StateRecordLength = 128,
    [int]$SlotLength = 384,
    [int]$TopHubs = 6,
    [int]$FollowPointerDepth = 2,
    [int]$MaxFollowPointersPerNode = 4,
    [int]$FollowPointerReadLength = 128,
    [int]$MaxSubgraphNodes = 18,
    [string]$ProjectorTraceFile = (Join-Path $PSScriptRoot 'captures\player-state-projector-trace.json'),
    [string]$OwnerComponentsFile = (Join-Path $PSScriptRoot 'captures\player-owner-components.json'),
    [string]$StatHubGraphFile = (Join-Path $PSScriptRoot 'captures\player-stat-hub-graph.json'),
    [string]$OutputFile = (Join-Path $PSScriptRoot 'captures\owner-state-neighborhood.json')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$projectorTraceScript = Join-Path $PSScriptRoot 'trace-player-state-projector.ps1'
$resolvedProjectorTraceFile = [System.IO.Path]::GetFullPath($ProjectorTraceFile)
$resolvedOwnerComponentsFile = [System.IO.Path]::GetFullPath($OwnerComponentsFile)
$resolvedStatHubGraphFile = [System.IO.Path]::GetFullPath($StatHubGraphFile)
$resolvedOutputFile = [System.IO.Path]::GetFullPath($OutputFile)

function Invoke-ReaderJson {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $output = & dotnet run --project $readerProject -- @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "Reader command failed (`$LASTEXITCODE=$exitCode): $($output -join [Environment]::NewLine)"
    }

    return ($output -join [Environment]::NewLine) | ConvertFrom-Json -Depth 40
}

function Read-JsonFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [switch]$Optional
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        if ($Optional) {
            return $null
        }

        throw "Required JSON file not found: $Path"
    }

    return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json -Depth 50
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

function Convert-HexToBytes {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Hex
    )

    $normalized = ($Hex -replace '\s+', '').Trim()
    if ([string]::IsNullOrWhiteSpace($normalized) -or ($normalized.Length % 2) -ne 0) {
        return @()
    }

    $buffer = New-Object byte[] ($normalized.Length / 2)
    for ($index = 0; $index -lt $buffer.Length; $index++) {
        $buffer[$index] = [Convert]::ToByte($normalized.Substring($index * 2, 2), 16)
    }

    return $buffer
}

function Read-Bytes {
    param(
        [Parameter(Mandatory = $true)]
        [UInt64]$Address,

        [Parameter(Mandatory = $true)]
        [int]$Length
    )

    $result = Invoke-ReaderJson -Arguments @(
        '--process-name', 'rift_x64',
        '--address', (Format-HexUInt64 -Value $Address),
        '--length', $Length.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '--json')

    return Convert-HexToBytes -Hex ([string]$result.BytesHex)
}

function Read-UInt64At {
    param(
        [Parameter(Mandatory = $true)]
        [byte[]]$Bytes,

        [Parameter(Mandatory = $true)]
        [int]$Offset
    )

    if (($Offset + 8) -gt $Bytes.Length) {
        return $null
    }

    return [BitConverter]::ToUInt64($Bytes, $Offset)
}

function Read-Int32At {
    param(
        [Parameter(Mandatory = $true)]
        [byte[]]$Bytes,

        [Parameter(Mandatory = $true)]
        [int]$Offset
    )

    if (($Offset + 4) -gt $Bytes.Length) {
        return $null
    }

    return [BitConverter]::ToInt32($Bytes, $Offset)
}

function Read-FloatAt {
    param(
        [Parameter(Mandatory = $true)]
        [byte[]]$Bytes,

        [Parameter(Mandatory = $true)]
        [int]$Offset
    )

    if (($Offset + 4) -gt $Bytes.Length) {
        return $null
    }

    return [BitConverter]::ToSingle($Bytes, $Offset)
}

function Test-CloseFloat {
    param(
        [double]$Left,
        [double]$Right,
        [double]$Tolerance = 0.25
    )

    return [math]::Abs($Left - $Right) -le $Tolerance
}

function Find-Int32Offsets {
    param(
        [byte[]]$Bytes,
        [int]$Value
    )

    $offsets = New-Object System.Collections.Generic.List[string]
    for ($offset = 0; $offset -le ($Bytes.Length - 4); $offset += 4) {
        if ([BitConverter]::ToInt32($Bytes, $offset) -eq $Value) {
            $offsets.Add(('0x{0:X}' -f $offset)) | Out-Null
        }
    }

    return @($offsets.ToArray())
}

function Get-PointerMatches {
    param(
        [Parameter(Mandatory = $true)]
        [byte[]]$Bytes,

        [Parameter(Mandatory = $true)]
        [hashtable]$KnownAddresses
    )

    $matches = New-Object System.Collections.Generic.List[object]
    for ($offset = 0; $offset -le ($Bytes.Length - 8); $offset += 8) {
        $value = Read-UInt64At -Bytes $Bytes -Offset $offset
        if ($null -eq $value -or $value -eq 0) {
            continue
        }

        $valueHex = Format-HexUInt64 -Value $value
        $normalized = $valueHex.ToUpperInvariant()
        if (-not $KnownAddresses.ContainsKey($normalized)) {
            continue
        }

        $matches.Add([ordered]@{
                Offset = $offset
                OffsetHex = ('0x{0:X}' -f $offset)
                Address = $valueHex
                Labels = @($KnownAddresses[$normalized].ToArray())
            }) | Out-Null
    }

    return @($matches.ToArray())
}

function Add-KnownAddress {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable]$Map,

        [Parameter(Mandatory = $true)]
        [string]$Label,

        [string]$Address
    )

    if ([string]::IsNullOrWhiteSpace($Address)) {
        return
    }

    $normalized = $Address.Trim().ToUpperInvariant()
    if ($normalized -eq '0X0') {
        return
    }

    if (-not $Map.ContainsKey($normalized)) {
        $Map[$normalized] = [System.Collections.Generic.List[string]]::new()
    }

    if (-not $Map[$normalized].Contains($Label)) {
        $Map[$normalized].Add($Label) | Out-Null
    }
}

function Get-AsciiPreview {
    param(
        [Parameter(Mandatory = $true)]
        [byte[]]$Bytes,

        [int]$MaxLength = 64
    )

    $length = [Math]::Min($Bytes.Length, [Math]::Max($MaxLength, 0))
    $builder = [System.Text.StringBuilder]::new()
    for ($index = 0; $index -lt $length; $index++) {
        $value = $Bytes[$index]
        if ($value -ge 32 -and $value -le 126) {
            [void]$builder.Append([char]$value)
        }
        elseif ($value -eq 0) {
            [void]$builder.Append('.')
        }
        else {
            [void]$builder.Append('?')
        }
    }

    return $builder.ToString()
}

function Get-NonZeroQwordPreview {
    param(
        [Parameter(Mandatory = $true)]
        [byte[]]$Bytes,

        [Parameter(Mandatory = $true)]
        [hashtable]$KnownAddresses,

        [int]$MaxCount = 16
    )

    $items = New-Object System.Collections.Generic.List[object]
    for ($offset = 0; $offset -le ($Bytes.Length - 8); $offset += 8) {
        $value = Read-UInt64At -Bytes $Bytes -Offset $offset
        if ($null -eq $value -or $value -eq 0) {
            continue
        }

        $valueHex = Format-HexUInt64 -Value $value
        $normalized = $valueHex.ToUpperInvariant()
        $items.Add([ordered]@{
                Offset = $offset
                OffsetHex = ('0x{0:X}' -f $offset)
                Value = $valueHex
                Labels = if ($KnownAddresses.ContainsKey($normalized)) { @($KnownAddresses[$normalized].ToArray()) } else { @() }
            }) | Out-Null

        if ($items.Count -ge $MaxCount) {
            break
        }
    }

    return @($items.ToArray())
}

function Test-PlausibleHeapPointer {
    param(
        [Parameter(Mandatory = $true)]
        [UInt64]$Value
    )

    $minAddress = Parse-HexUInt64 -Value '0x0000000100000000'
    $maxAddress = Parse-HexUInt64 -Value '0x00007FF000000000'
    return ($Value -ge $minAddress) -and ($Value -lt $maxAddress)
}

function Get-CandidatePointers {
    param(
        [Parameter(Mandatory = $true)]
        [byte[]]$Bytes,

        [Parameter(Mandatory = $true)]
        [hashtable]$KnownAddresses,

        [int]$MaxPointers = 4
    )

    $items = New-Object System.Collections.Generic.List[object]
    $seen = New-Object 'System.Collections.Generic.HashSet[string]'

    for ($offset = 0; $offset -le ($Bytes.Length - 8); $offset += 8) {
        if ($items.Count -ge $MaxPointers) {
            break
        }

        $value = Read-UInt64At -Bytes $Bytes -Offset $offset
        if ($null -eq $value -or -not (Test-PlausibleHeapPointer -Value $value)) {
            continue
        }

        $valueHex = Format-HexUInt64 -Value $value
        $normalized = $valueHex.ToUpperInvariant()
        if (-not $seen.Add($normalized)) {
            continue
        }

        $items.Add([ordered]@{
                SourceOffset = $offset
                SourceOffsetHex = ('0x{0:X}' -f $offset)
                Address = $valueHex
                Labels = if ($KnownAddresses.ContainsKey($normalized)) { @($KnownAddresses[$normalized].ToArray()) } else { @() }
            }) | Out-Null
    }

    return @($items.ToArray())
}

function Get-SubgraphNodeSummary {
    param(
        [Parameter(Mandatory = $true)]
        [UInt64]$Address,

        [Parameter(Mandatory = $true)]
        [byte[]]$Bytes,

        [Parameter(Mandatory = $true)]
        [hashtable]$KnownAddresses,

        [string[]]$RootLabels = @(),

        [int]$Depth = 0
    )

    $addressHex = Format-HexUInt64 -Value $Address
    $normalized = $addressHex.ToUpperInvariant()
    $pointerMatches = @(Get-PointerMatches -Bytes $Bytes -KnownAddresses $KnownAddresses)
    return [ordered]@{
        Address = $addressHex
        Depth = $Depth
        RootLabels = @($RootLabels | Sort-Object -Unique)
        KnownLabels = if ($KnownAddresses.ContainsKey($normalized)) { @($KnownAddresses[$normalized].ToArray()) } else { @() }
        AsciiPreview = Get-AsciiPreview -Bytes $Bytes
        QwordPreview = @(Get-NonZeroQwordPreview -Bytes $Bytes -KnownAddresses $KnownAddresses)
        PointerMatches = $pointerMatches
        PointerMatchCount = @($pointerMatches).Count
    }
}

function Get-FollowPointerSummaries {
    param(
        [Parameter(Mandatory = $true)]
        [byte[]]$Bytes,

        [Parameter(Mandatory = $true)]
        [hashtable]$KnownAddresses,

        [int]$MaxPointers = 4,

        [int]$ReadLength = 128
    )

    $results = New-Object System.Collections.Generic.List[object]
    foreach ($candidate in @(Get-CandidatePointers -Bytes $Bytes -KnownAddresses $KnownAddresses -MaxPointers $MaxPointers)) {
        $valueHex = [string]$candidate.Address

        try {
            $targetBytes = Read-Bytes -Address (Parse-HexUInt64 -Value $valueHex) -Length $ReadLength
            $pointerMatches = @(Get-PointerMatches -Bytes $targetBytes -KnownAddresses $KnownAddresses)
            $results.Add([ordered]@{
                    SourceOffset = [int]$candidate.SourceOffset
                    SourceOffsetHex = [string]$candidate.SourceOffsetHex
                    Address = $valueHex
                    Labels = @($candidate.Labels)
                    AsciiPreview = Get-AsciiPreview -Bytes $targetBytes
                    PointerMatches = $pointerMatches
                    PointerMatchCount = @($pointerMatches).Count
                    QwordPreview = @(Get-NonZeroQwordPreview -Bytes $targetBytes -KnownAddresses $KnownAddresses)
                }) | Out-Null
        }
        catch {
            $results.Add([ordered]@{
                    SourceOffset = [int]$candidate.SourceOffset
                    SourceOffsetHex = [string]$candidate.SourceOffsetHex
                    Address = $valueHex
                    Labels = @($candidate.Labels)
                    Error = $_.Exception.Message
                }) | Out-Null
        }
    }

    return @($results.ToArray())
}

function Build-PointerSubgraph {
    param(
        [Parameter(Mandatory = $true)]
        [object[]]$Roots,

        [Parameter(Mandatory = $true)]
        [hashtable]$KnownAddresses,

        [int]$MaxDepth = 2,

        [int]$MaxPointersPerNode = 4,

        [int]$ReadLength = 128,

        [int]$MaxNodes = 18
    )

    $queue = [System.Collections.Generic.Queue[object]]::new()
    $nodesByAddress = @{}
    $edgesByKey = @{}
    $seenRead = New-Object 'System.Collections.Generic.HashSet[string]'

    foreach ($root in @($Roots)) {
        if ($null -eq $root) {
            continue
        }

        $rootAddress = [string]$root.Address
        if ([string]::IsNullOrWhiteSpace($rootAddress)) {
            continue
        }

        $queue.Enqueue([ordered]@{
                Address = $rootAddress
                Depth = 0
                RootLabel = [string]$root.Label
                Bytes = $root.Bytes
            })
    }

    while ($queue.Count -gt 0 -and $nodesByAddress.Count -lt $MaxNodes) {
        $item = $queue.Dequeue()
        $addressHex = [string]$item.Address
        $normalized = $addressHex.ToUpperInvariant()
        if ([string]::IsNullOrWhiteSpace($normalized)) {
            continue
        }

        $bytes = $item.Bytes
        if ($null -eq $bytes) {
            if (-not $seenRead.Add($normalized)) {
                continue
            }

            try {
                $bytes = Read-Bytes -Address (Parse-HexUInt64 -Value $addressHex) -Length $ReadLength
            }
            catch {
                if (-not $nodesByAddress.ContainsKey($normalized)) {
                    $nodesByAddress[$normalized] = [ordered]@{
                        Address = $addressHex
                        Depth = [int]$item.Depth
                        RootLabels = @([string]$item.RootLabel)
                        KnownLabels = if ($KnownAddresses.ContainsKey($normalized)) { @($KnownAddresses[$normalized].ToArray()) } else { @() }
                        Error = $_.Exception.Message
                    }
                }
                continue
            }
        }

        if (-not $nodesByAddress.ContainsKey($normalized)) {
            $nodesByAddress[$normalized] = Get-SubgraphNodeSummary -Address (Parse-HexUInt64 -Value $addressHex) -Bytes $bytes -KnownAddresses $KnownAddresses -RootLabels @([string]$item.RootLabel) -Depth ([int]$item.Depth)
        }
        else {
            $existingNode = $nodesByAddress[$normalized]
            $existingRoots = @($existingNode.RootLabels)
            if ($existingRoots -notcontains [string]$item.RootLabel) {
                $existingNode.RootLabels = @($existingRoots + [string]$item.RootLabel | Sort-Object -Unique)
            }

            if ([int]$item.Depth -lt [int]$existingNode.Depth) {
                $existingNode.Depth = [int]$item.Depth
            }
        }

        if ([int]$item.Depth -ge $MaxDepth) {
            continue
        }

        foreach ($candidate in @(Get-CandidatePointers -Bytes $bytes -KnownAddresses $KnownAddresses -MaxPointers $MaxPointersPerNode)) {
            $childAddress = [string]$candidate.Address
            $edgeKey = '{0}|{1}|{2}' -f $normalized, $childAddress.ToUpperInvariant(), [string]$candidate.SourceOffsetHex
            if (-not $edgesByKey.ContainsKey($edgeKey)) {
                $edgesByKey[$edgeKey] = [ordered]@{
                    FromAddress = $addressHex
                    ToAddress = $childAddress
                    SourceOffset = [int]$candidate.SourceOffset
                    SourceOffsetHex = [string]$candidate.SourceOffsetHex
                    Depth = ([int]$item.Depth + 1)
                    RootLabel = [string]$item.RootLabel
                    Labels = @($candidate.Labels)
                }
            }

            $childNormalized = $childAddress.ToUpperInvariant()
            if ($nodesByAddress.ContainsKey($childNormalized)) {
                $childNode = $nodesByAddress[$childNormalized]
                $childRoots = @($childNode.RootLabels)
                if ($childRoots -notcontains [string]$item.RootLabel) {
                    $childNode.RootLabels = @($childRoots + [string]$item.RootLabel | Sort-Object -Unique)
                }

                if (([int]$item.Depth + 1) -lt [int]$childNode.Depth) {
                    $childNode.Depth = ([int]$item.Depth + 1)
                }
                continue
            }

            if (($queue.Count + $nodesByAddress.Count) -ge $MaxNodes) {
                continue
            }

            $queue.Enqueue([ordered]@{
                    Address = $childAddress
                    Depth = ([int]$item.Depth + 1)
                    RootLabel = [string]$item.RootLabel
                    Bytes = $null
                })
        }
    }

    return [ordered]@{
        MaxDepth = $MaxDepth
        MaxNodes = $MaxNodes
        ReadLength = $ReadLength
        MaxPointersPerNode = $MaxPointersPerNode
        NodeCount = $nodesByAddress.Count
        EdgeCount = $edgesByKey.Count
        Nodes = @($nodesByAddress.Values | Sort-Object Depth, Address)
        Edges = @($edgesByKey.Values | Sort-Object Depth, FromAddress, SourceOffset)
    }
}

function Get-StateObjectSummary {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Label,

        [Parameter(Mandatory = $true)]
        [UInt64]$Address,

        [Parameter(Mandatory = $true)]
        [byte[]]$Bytes,

        [Parameter(Mandatory = $true)]
        [hashtable]$KnownAddresses,

        [Parameter(Mandatory = $true)]
        $Player
    )

    $b8 = Read-FloatAt -Bytes $Bytes -Offset 0xB8
    $bc = Read-FloatAt -Bytes $Bytes -Offset 0xBC
    $c0 = Read-FloatAt -Bytes $Bytes -Offset 0xC0
    $d0 = Read-FloatAt -Bytes $Bytes -Offset 0xD0
    $d4 = Read-Int32At -Bytes $Bytes -Offset 0xD4
    $pointerMatches = @(Get-PointerMatches -Bytes $Bytes -KnownAddresses $KnownAddresses)
    $qwordPreview = @(Get-NonZeroQwordPreview -Bytes $Bytes -KnownAddresses $KnownAddresses)
    $followPointers = @(Get-FollowPointerSummaries -Bytes $Bytes -KnownAddresses $KnownAddresses)

    $vectorMatch = $false
    if ($null -ne $b8 -and $null -ne $bc -and $null -ne $c0) {
        $vectorMatch =
            (Test-CloseFloat -Left $b8 -Right ([double]$Player.Coord.X)) -and
            (Test-CloseFloat -Left $bc -Right ([double]$Player.Coord.Y)) -and
            (Test-CloseFloat -Left $c0 -Right ([double]$Player.Coord.Z))
    }

    return [ordered]@{
        Label = $Label
        Address = (Format-HexUInt64 -Value $Address)
        Length = $Bytes.Length
        AsciiPreview = Get-AsciiPreview -Bytes $Bytes
        PointerMatches = $pointerMatches
        PointerMatchCount = @($pointerMatches).Count
        QwordPreview = $qwordPreview
        FollowPointers = $followPointers
        IntMatches = [ordered]@{
            LevelOffsets = @(Find-Int32Offsets -Bytes $Bytes -Value ([int]$Player.Level))
            HpOffsets = @(Find-Int32Offsets -Bytes $Bytes -Value ([int]$Player.Hp))
            HpMaxOffsets = @(Find-Int32Offsets -Bytes $Bytes -Value ([int]$Player.HpMax))
            ResourceOffsets = @(Find-Int32Offsets -Bytes $Bytes -Value ([int]$Player.Resource))
            ResourceMaxOffsets = @(Find-Int32Offsets -Bytes $Bytes -Value ([int]$Player.ResourceMax))
            ComboOffsets = @(Find-Int32Offsets -Bytes $Bytes -Value ([int]$Player.Combo))
            PlanarMaxOffsets = @(Find-Int32Offsets -Bytes $Bytes -Value ([int]$Player.PlanarMax))
        }
        ProjectorVector = [ordered]@{
            B8 = $b8
            BC = $bc
            C0 = $c0
            D0 = $d0
            D4 = $d4
            MatchesPlayerCoords = $vectorMatch
            DeltaX = if ($null -ne $b8) { [double]$b8 - [double]$Player.Coord.X } else { $null }
            DeltaY = if ($null -ne $bc) { [double]$bc - [double]$Player.Coord.Y } else { $null }
            DeltaZ = if ($null -ne $c0) { [double]$c0 - [double]$Player.Coord.Z } else { $null }
        }
    }
}

if ($RefreshProjectorTrace -or -not (Test-Path -LiteralPath $resolvedProjectorTraceFile)) {
    & $projectorTraceScript -Json | Out-Null
}

$projectorTrace = Read-JsonFile -Path $resolvedProjectorTraceFile
$ownerComponents = Read-JsonFile -Path $resolvedOwnerComponentsFile -Optional
$statHubGraph = Read-JsonFile -Path $resolvedStatHubGraphFile -Optional
$snapshot = Invoke-ReaderJson -Arguments @('--readerbridge-snapshot', '--json')
$player = $snapshot.Current.Player

$knownAddresses = @{}
Add-KnownAddress -Map $knownAddresses -Label 'owner-object' -Address ([string]$projectorTrace.Owner.Address)
Add-KnownAddress -Map $knownAddresses -Label 'selected-source' -Address ([string]$projectorTrace.Owner.SelectedSourceAddress)
Add-KnownAddress -Map $knownAddresses -Label 'owner-state-record' -Address ([string]$projectorTrace.Owner.StateRecordAddress)
Add-KnownAddress -Map $knownAddresses -Label 'state-slot-50' -Address ([string]$projectorTrace.Owner.StateSlot50)
Add-KnownAddress -Map $knownAddresses -Label 'state-slot-58' -Address ([string]$projectorTrace.Owner.StateSlot58)
Add-KnownAddress -Map $knownAddresses -Label 'state-slot-60' -Address ([string]$projectorTrace.Owner.StateSlot60)

if ($ownerComponents) {
    Add-KnownAddress -Map $knownAddresses -Label 'owner-container' -Address ([string]$ownerComponents.Owner.ContainerAddress)
}

if ($statHubGraph) {
    $hubRank = 0
    foreach ($hub in @($statHubGraph.RankedSharedHubs | Select-Object -First $TopHubs)) {
        if ($null -eq $hub -or [string]::IsNullOrWhiteSpace([string]$hub.Address)) {
            continue
        }

        $hubRank++
        Add-KnownAddress -Map $knownAddresses -Label ('shared-hub-{0}' -f $hubRank) -Address ([string]$hub.Address)
    }
}

$stateRecordAddress = Parse-HexUInt64 -Value ([string]$projectorTrace.Owner.StateRecordAddress)
$stateRecordBytes = Read-Bytes -Address $stateRecordAddress -Length $StateRecordLength

$slotMap = [ordered]@{}
foreach ($slotSpec in @(
        @{ Label = 'slot-50-58'; Address = [string]$projectorTrace.Owner.StateSlot50 },
        @{ Label = 'slot-60'; Address = [string]$projectorTrace.Owner.StateSlot60 })) {
    $addressText = [string]$slotSpec.Address
    if ([string]::IsNullOrWhiteSpace($addressText) -or $slotMap.Contains($addressText.ToUpperInvariant())) {
        continue
    }

    $slotMap[$addressText.ToUpperInvariant()] = [ordered]@{
        Label = [string]$slotSpec.Label
        Address = $addressText
    }
}

$slotRecords = New-Object System.Collections.Generic.List[object]
$slotRootData = New-Object System.Collections.Generic.List[object]
foreach ($slot in @($slotMap.Values)) {
    $slotAddress = Parse-HexUInt64 -Value ([string]$slot.Address)
    $slotBytes = Read-Bytes -Address $slotAddress -Length $SlotLength
    $slotLabel = [string]$slot.Label
    $slotRecords.Add((Get-StateObjectSummary -Label $slotLabel -Address $slotAddress -Bytes $slotBytes -KnownAddresses $knownAddresses -Player $player)) | Out-Null
    $slotRootData.Add([ordered]@{
            Label = $slotLabel
            Address = (Format-HexUInt64 -Value $slotAddress)
            Bytes = $slotBytes
        }) | Out-Null
}

$stateRecordPointers = @(Get-PointerMatches -Bytes $stateRecordBytes -KnownAddresses $knownAddresses)
$subgraphRoots = @(
    [ordered]@{
        Label = 'state-record'
        Address = (Format-HexUInt64 -Value $stateRecordAddress)
        Bytes = $stateRecordBytes
    }
)
foreach ($slotRoot in @($slotRootData.ToArray())) {
    $subgraphRoots += $slotRoot
}
$pointerSubgraph = Build-PointerSubgraph -Roots $subgraphRoots -KnownAddresses $knownAddresses -MaxDepth $FollowPointerDepth -MaxPointersPerNode $MaxFollowPointersPerNode -ReadLength $FollowPointerReadLength -MaxNodes $MaxSubgraphNodes

$document = [ordered]@{
    Mode = 'owner-state-neighborhood'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    ProjectorTraceFile = $resolvedProjectorTraceFile
    OwnerComponentsFile = if (Test-Path -LiteralPath $resolvedOwnerComponentsFile) { $resolvedOwnerComponentsFile } else { $null }
    StatHubGraphFile = if (Test-Path -LiteralPath $resolvedStatHubGraphFile) { $resolvedStatHubGraphFile } else { $null }
    Owner = [ordered]@{
        Address = [string]$projectorTrace.Owner.Address
        SelectedSourceAddress = [string]$projectorTrace.Owner.SelectedSourceAddress
        StateRecordAddress = [string]$projectorTrace.Owner.StateRecordAddress
        StateSlot50 = [string]$projectorTrace.Owner.StateSlot50
        StateSlot58 = [string]$projectorTrace.Owner.StateSlot58
        StateSlot60 = [string]$projectorTrace.Owner.StateSlot60
    }
    PlayerSnapshot = [ordered]@{
        Name = [string]$player.Name
        Location = [string]$player.LocationName
        Level = [int]$player.Level
        Hp = [int]$player.Hp
        HpMax = [int]$player.HpMax
        Resource = [int]$player.Resource
        ResourceMax = [int]$player.ResourceMax
        Combo = [int]$player.Combo
        PlanarMax = [int]$player.PlanarMax
        Coord = [ordered]@{
            X = [double]$player.Coord.X
            Y = [double]$player.Coord.Y
            Z = [double]$player.Coord.Z
        }
    }
    StateRecord = [ordered]@{
        Address = (Format-HexUInt64 -Value $stateRecordAddress)
        Length = $stateRecordBytes.Length
        PointerMatches = $stateRecordPointers
        PointerMatchCount = @($stateRecordPointers).Count
        IntMatches = [ordered]@{
            LevelOffsets = @(Find-Int32Offsets -Bytes $stateRecordBytes -Value ([int]$player.Level))
            HpOffsets = @(Find-Int32Offsets -Bytes $stateRecordBytes -Value ([int]$player.Hp))
            HpMaxOffsets = @(Find-Int32Offsets -Bytes $stateRecordBytes -Value ([int]$player.HpMax))
            ResourceOffsets = @(Find-Int32Offsets -Bytes $stateRecordBytes -Value ([int]$player.Resource))
            ResourceMaxOffsets = @(Find-Int32Offsets -Bytes $stateRecordBytes -Value ([int]$player.ResourceMax))
            ComboOffsets = @(Find-Int32Offsets -Bytes $stateRecordBytes -Value ([int]$player.Combo))
            PlanarMaxOffsets = @(Find-Int32Offsets -Bytes $stateRecordBytes -Value ([int]$player.PlanarMax))
        }
    }
    Slots = @($slotRecords.ToArray())
    PointerSubgraph = $pointerSubgraph
}

$outputDirectory = Split-Path -Path $resolvedOutputFile -Parent
if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

$jsonText = $document | ConvertTo-Json -Depth 24
Set-Content -LiteralPath $resolvedOutputFile -Value $jsonText -Encoding UTF8

$result = [ordered]@{
    Mode = 'owner-state-neighborhood-capture'
    OutputFile = $resolvedOutputFile
    SlotCount = $slotRecords.Count
    StateRecordPointerMatchCount = @($stateRecordPointers).Count
    SlotPointerMatchCount = (@($slotRecords | ForEach-Object { $_.PointerMatchCount } | Measure-Object -Sum).Sum)
    CoordMatchingSlotCount = (@($slotRecords | Where-Object { $_.ProjectorVector.MatchesPlayerCoords }).Count)
    PointerSubgraphNodeCount = [int]$pointerSubgraph.NodeCount
    PointerSubgraphEdgeCount = [int]$pointerSubgraph.EdgeCount
}

if ($Json) {
    $result | ConvertTo-Json -Depth 8
    exit 0
}

Write-Host "Owner-state neighborhood captured." -ForegroundColor Green
Write-Host ("Output:              {0}" -f $resolvedOutputFile)
Write-Host ("Slots:               {0}" -f $slotRecords.Count)
Write-Host ("State ptr matches:   {0}" -f @($stateRecordPointers).Count)
Write-Host ("Slot ptr matches:    {0}" -f $result['SlotPointerMatchCount'])
Write-Host ("Coord-matching slots:{0}" -f $result['CoordMatchingSlotCount'])
