[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$LeftPath,

    [Parameter(Mandatory = $true)]
    [string]$RightPath,

    [switch]$Json,

    [int]$PreviewCount = 8
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Resolve-OwnerStateNeighborhoodFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $resolvedPath = [System.IO.Path]::GetFullPath($Path)
    if (Test-Path -LiteralPath $resolvedPath -PathType Leaf) {
        return $resolvedPath
    }

    if (Test-Path -LiteralPath $resolvedPath -PathType Container) {
        $candidates = @(
            (Join-Path $resolvedPath 'owner-state-neighborhood.json'),
            (Join-Path $resolvedPath 'artifacts\owner-state-neighborhood.json'),
            (Join-Path $resolvedPath 'captures\owner-state-neighborhood.json')
        )

        foreach ($candidate in $candidates) {
            if (Test-Path -LiteralPath $candidate -PathType Leaf) {
                return [System.IO.Path]::GetFullPath($candidate)
            }
        }

        throw "Could not find owner-state-neighborhood.json under directory: $resolvedPath"
    }

    throw "Path not found: $resolvedPath"
}

function Read-JsonFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json -Depth 60
}

function Normalize-Hex {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    $normalized = $Value.Trim()
    if ($normalized.StartsWith('0x', [System.StringComparison]::OrdinalIgnoreCase)) {
        $normalized = $normalized.Substring(2)
    }

    if ([string]::IsNullOrWhiteSpace($normalized)) {
        return '0X0'
    }

    return ('0X{0}' -f $normalized.ToUpperInvariant())
}

function Get-StringValue {
    param(
        $Value
    )

    if ($null -eq $Value) {
        return $null
    }

    return [string]$Value
}

function Get-ListKeys {
    param(
        [object[]]$Items,
        [scriptblock]$KeySelector
    )

    $set = New-Object 'System.Collections.Generic.HashSet[string]'
    foreach ($item in @($Items)) {
        $key = & $KeySelector $item
        if ([string]::IsNullOrWhiteSpace([string]$key)) {
            continue
        }

        [void]$set.Add([string]$key)
    }

    return @($set | Sort-Object)
}

function Compare-StringLists {
    param(
        [string[]]$Left,
        [string[]]$Right
    )

    $leftSet = New-Object 'System.Collections.Generic.HashSet[string]'
    $rightSet = New-Object 'System.Collections.Generic.HashSet[string]'
    foreach ($item in @($Left)) { if (-not [string]::IsNullOrWhiteSpace($item)) { [void]$leftSet.Add($item) } }
    foreach ($item in @($Right)) { if (-not [string]::IsNullOrWhiteSpace($item)) { [void]$rightSet.Add($item) } }

    $added = New-Object System.Collections.Generic.List[string]
    $removed = New-Object System.Collections.Generic.List[string]

    foreach ($item in @($rightSet | Sort-Object)) {
        if (-not $leftSet.Contains($item)) {
            $added.Add($item) | Out-Null
        }
    }

    foreach ($item in @($leftSet | Sort-Object)) {
        if (-not $rightSet.Contains($item)) {
            $removed.Add($item) | Out-Null
        }
    }

    return [ordered]@{
        Added = @($added.ToArray())
        Removed = @($removed.ToArray())
        Changed = (($added.Count + $removed.Count) -gt 0)
    }
}

function Get-PointerMatchKey {
    param($Item)

    if ($null -eq $Item) { return $null }
    $labels = @()
    if ($null -ne $Item.Labels) {
        $labels = @($Item.Labels | ForEach-Object { [string]$_ } | Sort-Object)
    }

    return ('{0}|{1}|{2}' -f (Get-StringValue $Item.OffsetHex), (Get-StringValue $Item.Address), ($labels -join ','))
}

function Get-QwordPreviewKey {
    param($Item)

    if ($null -eq $Item) { return $null }
    $labels = @()
    if ($null -ne $Item.Labels) {
        $labels = @($Item.Labels | ForEach-Object { [string]$_ } | Sort-Object)
    }

    return ('{0}|{1}|{2}' -f (Get-StringValue $Item.OffsetHex), (Get-StringValue $Item.Value), ($labels -join ','))
}

function Compare-ArrayByKey {
    param(
        [object[]]$Left,
        [object[]]$Right,
        [scriptblock]$KeySelector
    )

    $leftMap = @{}
    $rightMap = @{}

    foreach ($item in @($Left)) {
        $key = & $KeySelector $item
        if ([string]::IsNullOrWhiteSpace([string]$key)) { continue }
        $leftMap[[string]$key] = $item
    }

    foreach ($item in @($Right)) {
        $key = & $KeySelector $item
        if ([string]::IsNullOrWhiteSpace([string]$key)) { continue }
        $rightMap[[string]$key] = $item
    }

    $allKeys = @(@($leftMap.Keys) + @($rightMap.Keys) | Sort-Object -Unique)
    $added = New-Object System.Collections.Generic.List[string]
    $removed = New-Object System.Collections.Generic.List[string]
    $changed = New-Object System.Collections.Generic.List[object]

    foreach ($key in $allKeys) {
        $hasLeft = $leftMap.ContainsKey($key)
        $hasRight = $rightMap.ContainsKey($key)
        if ($hasLeft -and -not $hasRight) {
            $removed.Add($key) | Out-Null
            continue
        }
        if (-not $hasLeft -and $hasRight) {
            $added.Add($key) | Out-Null
            continue
        }

        $leftItem = $leftMap[$key]
        $rightItem = $rightMap[$key]
        if ($null -ne $leftItem -and $null -ne $rightItem) {
            if ((ConvertTo-Json $leftItem -Depth 20 -Compress) -ne (ConvertTo-Json $rightItem -Depth 20 -Compress)) {
                $changed.Add([ordered]@{
                        Key = $key
                        Left = $leftItem
                        Right = $rightItem
                    }) | Out-Null
            }
        }
    }

    return [ordered]@{
        Added = @($added.ToArray())
        Removed = @($removed.ToArray())
        Changed = @($changed.ToArray())
    }
}

function Get-ComparableDocument {
    param(
        [Parameter(Mandatory = $true)]
        $Document
    )

    $slots = @($Document.Slots)
    $stateRecordPointerMatches = @($Document.StateRecord.PointerMatches)

    return [ordered]@{
        Owner = [ordered]@{
            Address = (Get-StringValue $Document.Owner.Address)
            SelectedSourceAddress = (Get-StringValue $Document.Owner.SelectedSourceAddress)
            StateRecordAddress = (Get-StringValue $Document.Owner.StateRecordAddress)
            StateSlot50 = (Get-StringValue $Document.Owner.StateSlot50)
            StateSlot58 = (Get-StringValue $Document.Owner.StateSlot58)
            StateSlot60 = (Get-StringValue $Document.Owner.StateSlot60)
        }
        StateRecord = [ordered]@{
            Address = (Get-StringValue $Document.StateRecord.Address)
            PointerMatches = @($stateRecordPointerMatches | ForEach-Object {
                    [ordered]@{
                        OffsetHex = (Get-StringValue $_.OffsetHex)
                        Address = (Get-StringValue $_.Address)
                        Labels = @($_.Labels | ForEach-Object { [string]$_ } | Sort-Object)
                    }
                })
            IntMatches = [ordered]@{
                LevelOffsets = @($Document.StateRecord.IntMatches.LevelOffsets)
                HpOffsets = @($Document.StateRecord.IntMatches.HpOffsets)
                HpMaxOffsets = @($Document.StateRecord.IntMatches.HpMaxOffsets)
                ResourceOffsets = @($Document.StateRecord.IntMatches.ResourceOffsets)
                ResourceMaxOffsets = @($Document.StateRecord.IntMatches.ResourceMaxOffsets)
                ComboOffsets = @($Document.StateRecord.IntMatches.ComboOffsets)
                PlanarMaxOffsets = @($Document.StateRecord.IntMatches.PlanarMaxOffsets)
            }
        }
        Slots = @($slots | ForEach-Object {
                $followPointers = @($_.FollowPointers)
                [ordered]@{
                    Label = (Get-StringValue $_.Label)
                    Address = (Get-StringValue $_.Address)
                    AsciiPreview = (Get-StringValue $_.AsciiPreview)
                    PointerMatchCount = [int]$_.PointerMatchCount
                    PointerMatches = @($_.PointerMatches | ForEach-Object {
                            [ordered]@{
                                OffsetHex = (Get-StringValue $_.OffsetHex)
                                Address = (Get-StringValue $_.Address)
                                Labels = @($_.Labels | ForEach-Object { [string]$_ } | Sort-Object)
                            }
                        })
                    QwordPreview = @($_.QwordPreview | Select-Object -First $PreviewCount | ForEach-Object {
                            [ordered]@{
                                OffsetHex = (Get-StringValue $_.OffsetHex)
                                Value = (Get-StringValue $_.Value)
                                Labels = @($_.Labels | ForEach-Object { [string]$_ } | Sort-Object)
                            }
                        })
                    ProjectorVector = [ordered]@{
                        B8 = $_.ProjectorVector.B8
                        BC = $_.ProjectorVector.BC
                        C0 = $_.ProjectorVector.C0
                        D0 = $_.ProjectorVector.D0
                        D4 = $_.ProjectorVector.D4
                        MatchesPlayerCoords = [bool]$_.ProjectorVector.MatchesPlayerCoords
                    }
                    FollowPointers = @($followPointers | ForEach-Object {
                            [ordered]@{
                                SourceOffsetHex = (Get-StringValue $_.SourceOffsetHex)
                                Address = (Get-StringValue $_.Address)
                                AsciiPreview = (Get-StringValue $_.AsciiPreview)
                                PointerMatchCount = [int]$_.PointerMatchCount
                                PointerMatches = @($_.PointerMatches | ForEach-Object {
                                        [ordered]@{
                                            OffsetHex = (Get-StringValue $_.OffsetHex)
                                            Address = (Get-StringValue $_.Address)
                                            Labels = @($_.Labels | ForEach-Object { [string]$_ } | Sort-Object)
                                        }
                                    })
                                QwordPreview = @($_.QwordPreview | Select-Object -First $PreviewCount | ForEach-Object {
                                        [ordered]@{
                                            OffsetHex = (Get-StringValue $_.OffsetHex)
                                            Value = (Get-StringValue $_.Value)
                                            Labels = @($_.Labels | ForEach-Object { [string]$_ } | Sort-Object)
                                        }
                                    })
                            }
                        })
                }
            } | Sort-Object Label, Address)
    }
}

function Compare-ComparableDocuments {
    param(
        [Parameter(Mandatory = $true)]
        $Left,

        [Parameter(Mandatory = $true)]
        $Right
    )

    function Add-Line {
        param(
            [Parameter(Mandatory = $true)]
            [string]$Path,

            [object]$Value
        )

        $text = if ($null -eq $Value) { '<null>' } else { [string]$Value }
        $script:ComparisonLines += ('{0}={1}' -f $Path, $text)
    }

    function Add-PointerMatchLines {
        param(
            [Parameter(Mandatory = $true)]
            [string]$PathPrefix,

            [object[]]$Items
        )

        foreach ($item in @($Items)) {
            if ($null -eq $item) {
                continue
            }

            $labels = @()
            if ($null -ne $item.Labels) {
                $labels = @($item.Labels | ForEach-Object { [string]$_ } | Sort-Object)
            }

            Add-Line -Path $PathPrefix -Value ('Offset={0}|Address={1}|Labels={2}' -f (Get-StringValue $item.OffsetHex), (Get-StringValue $item.Address), ($labels -join ','))
        }
    }

    function Add-QwordPreviewLines {
        param(
            [Parameter(Mandatory = $true)]
            [string]$PathPrefix,

            [object[]]$Items
        )

        foreach ($item in @($Items | Select-Object -First $PreviewCount)) {
            if ($null -eq $item) {
                continue
            }

            $labels = @()
            if ($null -ne $item.Labels) {
                $labels = @($item.Labels | ForEach-Object { [string]$_ } | Sort-Object)
            }

            Add-Line -Path $PathPrefix -Value ('Offset={0}|Value={1}|Labels={2}' -f (Get-StringValue $item.OffsetHex), (Get-StringValue $item.Value), ($labels -join ','))
        }
    }

    function Add-FollowPointerLines {
        param(
            [Parameter(Mandatory = $true)]
            [string]$PathPrefix,

            [object[]]$Items
        )

        foreach ($item in @($Items)) {
            if ($null -eq $item) {
                continue
            }

            $entryPath = '{0}.Follow|SourceOffset={1}|Address={2}' -f $PathPrefix, (Get-StringValue $item.SourceOffsetHex), (Get-StringValue $item.Address)
            Add-Line -Path $entryPath -Value ('Ascii={0}|PointerMatchCount={1}' -f (Get-StringValue $item.AsciiPreview), [int]$item.PointerMatchCount)
            Add-PointerMatchLines -PathPrefix ($entryPath + '.Pointer') -Items $item.PointerMatches
            Add-QwordPreviewLines -PathPrefix ($entryPath + '.Qword') -Items $item.QwordPreview
        }
    }

    function Get-ComparisonLines {
        param(
            [Parameter(Mandatory = $true)]
            $Document
        )

        $script:ComparisonLines = @()

        foreach ($field in @('Address', 'SelectedSourceAddress', 'StateRecordAddress', 'StateSlot50', 'StateSlot58', 'StateSlot60')) {
            Add-Line -Path ("Owner.{0}" -f $field) -Value $Document.Owner.$field
        }

        Add-Line -Path 'StateRecord.Address' -Value $Document.StateRecord.Address
        Add-PointerMatchLines -PathPrefix 'StateRecord.Pointer' -Items $Document.StateRecord.PointerMatches
        foreach ($field in @('LevelOffsets', 'HpOffsets', 'HpMaxOffsets', 'ResourceOffsets', 'ResourceMaxOffsets', 'ComboOffsets', 'PlanarMaxOffsets')) {
            Add-Line -Path ("StateRecord.IntMatches.{0}" -f $field) -Value (($Document.StateRecord.IntMatches.$field) -join ',')
        }

        foreach ($slot in @($Document.Slots)) {
            $slotKey = '{0}|{1}' -f (Get-StringValue $slot.Label), (Get-StringValue $slot.Address)
            Add-Line -Path ("Slot[{0}].Summary" -f $slotKey) -Value ('PointerMatchCount={0}|Ascii={1}|Projector=B8:{2};BC:{3};C0:{4};D0:{5};D4:{6};MatchesPlayerCoords:{7}' -f [int]$slot.PointerMatchCount, (Get-StringValue $slot.AsciiPreview), $slot.ProjectorVector.B8, $slot.ProjectorVector.BC, $slot.ProjectorVector.C0, $slot.ProjectorVector.D0, $slot.ProjectorVector.D4, $slot.ProjectorVector.MatchesPlayerCoords)
            Add-PointerMatchLines -PathPrefix ("Slot[{0}].Pointer" -f $slotKey) -Items $slot.PointerMatches
            Add-QwordPreviewLines -PathPrefix ("Slot[{0}].Qword" -f $slotKey) -Items $slot.QwordPreview
            Add-FollowPointerLines -PathPrefix ("Slot[{0}]" -f $slotKey) -Items $slot.FollowPointers
        }

        return @($script:ComparisonLines)
    }

    $leftLines = @(Get-ComparisonLines -Document $Left)
    $rightLines = @(Get-ComparisonLines -Document $Right)
    $comparison = @(Compare-Object -ReferenceObject $leftLines -DifferenceObject $rightLines)

    $addedLines = @($comparison | Where-Object SideIndicator -eq '=>' | ForEach-Object { [string]$_.InputObject })
    $removedLines = @($comparison | Where-Object SideIndicator -eq '<=' | ForEach-Object { [string]$_.InputObject })

    return [ordered]@{
        Mode = 'owner-state-neighborhood-diff'
        LeftFile = $script:LeftFileResolved
        RightFile = $script:RightFileResolved
        Summary = [ordered]@{
            AddedLineCount = @($addedLines).Count
            RemovedLineCount = @($removedLines).Count
            HasChanges = ((@($comparison).Count) -gt 0)
        }
        Changes = [ordered]@{
            AddedLines = @($addedLines)
            RemovedLines = @($removedLines)
        }
    }
}

$script:LeftFileResolved = Resolve-OwnerStateNeighborhoodFile -Path $LeftPath
$script:RightFileResolved = Resolve-OwnerStateNeighborhoodFile -Path $RightPath

$leftDocument = Get-ComparableDocument -Document (Read-JsonFile -Path $script:LeftFileResolved)
$rightDocument = Get-ComparableDocument -Document (Read-JsonFile -Path $script:RightFileResolved)
$diff = Compare-ComparableDocuments -Left $leftDocument -Right $rightDocument

if ($Json) {
    $diff | ConvertTo-Json -Depth 30
    exit 0
}

Write-Host "Owner-state neighborhood diff" -ForegroundColor Cyan
Write-Host ("Left:   {0}" -f $diff.LeftFile)
Write-Host ("Right:  {0}" -f $diff.RightFile)
Write-Host ("Owner fields changed:     {0}" -f $diff.Summary.OwnerFieldChangeCount)
Write-Host ("State-record ptr changes: {0}" -f $diff.Summary.StateRecordPointerChangeCount)
Write-Host ("Slots added/removed/changed: {0}/{1}/{2}" -f $diff.Summary.SlotAddedCount, $diff.Summary.SlotRemovedCount, $diff.Summary.SlotChangedCount)

if ($diff.Summary.HasChanges) {
    if (@($diff.Changes.Owner).Count -gt 0) {
        Write-Host "Owner changes:" -ForegroundColor Yellow
        foreach ($change in @($diff.Changes.Owner)) {
            Write-Host ("  {0}: {1} -> {2}" -f $change.Field, $change.Left, $change.Right)
        }
    }

    if (($diff.Summary.StateRecordPointerChangeCount -gt 0) -or ($diff.Summary.SlotAddedCount -gt 0) -or ($diff.Summary.SlotRemovedCount -gt 0) -or ($diff.Summary.SlotChangedCount -gt 0)) {
        Write-Host "State-record / slot changes:" -ForegroundColor Yellow
        if (@($diff.Changes.StateRecord.PointerMatches.Added).Count -gt 0) {
            Write-Host "  Added state-record pointers:"
            foreach ($item in @($diff.Changes.StateRecord.PointerMatches.Added)) { Write-Host ("    + {0}" -f $item) }
        }
        if (@($diff.Changes.StateRecord.PointerMatches.Removed).Count -gt 0) {
            Write-Host "  Removed state-record pointers:"
            foreach ($item in @($diff.Changes.StateRecord.PointerMatches.Removed)) { Write-Host ("    - {0}" -f $item) }
        }

        foreach ($slotKey in @($diff.Changes.Slots.Added)) { Write-Host ("  + slot {0}" -f $slotKey) }
        foreach ($slotKey in @($diff.Changes.Slots.Removed)) { Write-Host ("  - slot {0}" -f $slotKey) }

        foreach ($slotChange in @($diff.Changes.Slots.Changed)) {
            Write-Host ("  * slot {0}" -f $slotChange.Key)
        }
    }
}
else {
    Write-Host "No meaningful differences detected." -ForegroundColor Green
}
