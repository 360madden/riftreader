[CmdletBinding()]
param(
    [switch]$Json,
    [switch]$RefreshOwnerComponents,
    [int]$MaxPointersPerNode = 8,
    [int]$MaxNodesPerComponent = 18,
    [int]$MaxDepth = 2,
    [int]$ChildReadLength = 0x280,
    [int]$ComponentReadLength = 0x1C0,
    [string]$OwnerComponentsFile = (Join-Path $PSScriptRoot 'captures\player-owner-components.json'),
    [string]$OutputFile = (Join-Path $PSScriptRoot 'captures\player-stat-component-candidates.json')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$readerExe = Join-Path $repoRoot 'reader\RiftReader.Reader\bin\Debug\net10.0-windows\RiftReader.Reader.exe'
$ownerComponentsScript = Join-Path $PSScriptRoot 'capture-player-owner-components.ps1'
$resolvedOwnerComponentsFile = [System.IO.Path]::GetFullPath($OwnerComponentsFile)
$resolvedOutputFile = [System.IO.Path]::GetFullPath($OutputFile)

function Invoke-ReaderJson {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $commandOutput = $null
    if (Test-Path -LiteralPath $readerExe) {
        $commandOutput = & $readerExe @Arguments 2>&1
    }
    else {
        $commandOutput = & dotnet run --project $readerProject -- @Arguments 2>&1
    }

    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "Reader command failed (`$LASTEXITCODE=$exitCode): $($commandOutput -join [Environment]::NewLine)"
    }

    return ($commandOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 40
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

function Try-Parse-HeapPointer {
    param(
        [AllowNull()]
        [object]$Value
    )

    if ($null -eq $Value) {
        return $null
    }

    $text = [string]$Value
    if ([string]::IsNullOrWhiteSpace($text)) {
        return $null
    }

    $number = $null
    try {
        $number = Parse-HexUInt64 -Value $text
    }
    catch {
        return $null
    }

    if ($number -le 0x0000000100000000) {
        return $null
    }

    if ($number -ge 0x0000700000000000) {
        return $null
    }

    return $number
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
        '--address', ('0x{0:X}' -f $Address),
        '--length', $Length.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '--json')

    $hex = ([string]$result.BytesHex -replace '\s+', '').Trim()
    $bytes = New-Object byte[] ($hex.Length / 2)
    for ($index = 0; $index -lt $bytes.Length; $index++) {
        $bytes[$index] = [Convert]::ToByte($hex.Substring($index * 2, 2), 16)
    }

    return $bytes
}

function Try-Read-Bytes {
    param(
        [Parameter(Mandatory = $true)]
        [UInt64]$Address,

        [Parameter(Mandatory = $true)]
        [int]$Length
    )

    try {
        return Read-Bytes -Address $Address -Length $Length
    }
    catch {
        return $null
    }
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

function Convert-ToAscii {
    param([byte[]]$Bytes)
    return [System.Text.Encoding]::ASCII.GetString($Bytes)
}

function Convert-ToUnicode {
    param([byte[]]$Bytes)
    return [System.Text.Encoding]::Unicode.GetString($Bytes)
}

function Find-Int32Offsets {
    param(
        [byte[]]$Bytes,
        [int]$Value
    )

    $offsets = New-Object System.Collections.Generic.List[int]
    for ($offset = 0; $offset -le ($Bytes.Length - 4); $offset += 4) {
        if ([BitConverter]::ToInt32($Bytes, $offset) -eq $Value) {
            $offsets.Add($offset)
        }
    }

    return $offsets.ToArray()
}

function Test-ContainsText {
    param(
        [byte[]]$Bytes,
        [string]$Text
    )

    if ([string]::IsNullOrWhiteSpace($Text)) {
        return $false
    }

    $ascii = Convert-ToAscii -Bytes $Bytes
    if ($ascii.Contains($Text, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $true
    }

    $unicode = Convert-ToUnicode -Bytes $Bytes
    return $unicode.Contains($Text, [System.StringComparison]::OrdinalIgnoreCase)
}

function Get-HeapPointerEntries {
    param(
        [byte[]]$Bytes,
        [int]$Limit,
        [System.Collections.Generic.HashSet[UInt64]]$SeenPointers
    )

    $entries = New-Object System.Collections.Generic.List[object]
    for ($offset = 0; $offset -le ($Bytes.Length - 8); $offset += 8) {
        $pointerValue = Read-UInt64At -Bytes $Bytes -Offset $offset
        if ($null -eq $pointerValue) {
            continue
        }

        if ($pointerValue -le 0x0000000100000000 -or $pointerValue -ge 0x0000700000000000) {
            continue
        }

        if ($SeenPointers.Contains($pointerValue)) {
            continue
        }

        $entries.Add([ordered]@{
            Offset = $offset
            OffsetHex = ('0x{0:X}' -f $offset)
            Address = ('0x{0:X}' -f $pointerValue)
            Value = $pointerValue
        })

        if ($entries.Count -ge $Limit) {
            break
        }
    }

    return $entries.ToArray()
}

function Get-SignalSummary {
    param(
        [byte[]]$Bytes,
        [hashtable]$Expected
    )

    $levelOffsets = @(Find-Int32Offsets -Bytes $Bytes -Value $Expected.Level)
    $hpOffsets = @(Find-Int32Offsets -Bytes $Bytes -Value $Expected.Hp)
    $hpMaxOffsets = @(Find-Int32Offsets -Bytes $Bytes -Value $Expected.HpMax)
    $resourceOffsets = @(Find-Int32Offsets -Bytes $Bytes -Value $Expected.Resource)
    $resourceMaxOffsets = @(Find-Int32Offsets -Bytes $Bytes -Value $Expected.ResourceMax)
    $comboOffsets = @(Find-Int32Offsets -Bytes $Bytes -Value $Expected.Combo)
    $planarOffsets = @(Find-Int32Offsets -Bytes $Bytes -Value $Expected.Planar)
    $planarMaxOffsets = @(Find-Int32Offsets -Bytes $Bytes -Value $Expected.PlanarMax)
    $vitalityOffsets = @(Find-Int32Offsets -Bytes $Bytes -Value $Expected.Vitality)

    $nameHit = Test-ContainsText -Bytes $Bytes -Text $Expected.Name
    $guildHit = Test-ContainsText -Bytes $Bytes -Text $Expected.Guild
    $unitIdHit = Test-ContainsText -Bytes $Bytes -Text $Expected.UnitId

    $hasLevel = $levelOffsets.Count -gt 0
    $hasHp = $hpOffsets.Count -gt 0
    $hasHpMax = $hpMaxOffsets.Count -gt 0
    $hasResource = $resourceOffsets.Count -gt 0
    $hasResourceMax = $resourceMaxOffsets.Count -gt 0
    $hasCombo = $comboOffsets.Count -gt 0
    $hasPlanar = $planarOffsets.Count -gt 0
    $hasPlanarMax = $planarMaxOffsets.Count -gt 0
    $hasVitality = $vitalityOffsets.Count -gt 0

    $hasHealthPair = $hasHp -and $hasHpMax
    $hasResourcePair = $hasResource -and $hasResourceMax
    $hasIdentity = $nameHit -or $guildHit -or $unitIdHit
    $strongSignalCount = @($hasLevel, $hasHp, $hasHpMax, $nameHit, $guildHit, $unitIdHit | Where-Object { $_ }).Count
    $weakSignalOnly = ($strongSignalCount -eq 0) -and ($hasResource -or $hasResourceMax -or $hasCombo -or $hasPlanar -or $hasPlanarMax -or $hasVitality)

    return [ordered]@{
        LevelOffsets = $levelOffsets
        HpOffsets = $hpOffsets
        HpMaxOffsets = $hpMaxOffsets
        ResourceOffsets = $resourceOffsets
        ResourceMaxOffsets = $resourceMaxOffsets
        ComboOffsets = $comboOffsets
        PlanarOffsets = $planarOffsets
        PlanarMaxOffsets = $planarMaxOffsets
        VitalityOffsets = $vitalityOffsets
        NameHit = $nameHit
        GuildHit = $guildHit
        UnitIdHit = $unitIdHit
        HasLevel = $hasLevel
        HasHp = $hasHp
        HasHpMax = $hasHpMax
        HasResource = $hasResource
        HasResourceMax = $hasResourceMax
        HasCombo = $hasCombo
        HasPlanar = $hasPlanar
        HasPlanarMax = $hasPlanarMax
        HasVitality = $hasVitality
        HasHealthPair = $hasHealthPair
        HasResourcePair = $hasResourcePair
        HasIdentity = $hasIdentity
        StrongSignalCount = $strongSignalCount
        WeakSignalOnly = $weakSignalOnly
    }
}

function Get-FeatureCount {
    param(
        [object[]]$Nodes,
        [string]$PropertyName
    )

    return @($Nodes | Where-Object { $_.Signals.$PropertyName }).Count
}

function Get-NodeScore {
    param(
        [object]$Node,
        [hashtable]$FeatureCounts,
        [bool]$IsTransformLike
    )

    $signals = $Node.Signals
    $score = 0.0
    $reasons = New-Object System.Collections.Generic.List[string]

    function Add-FeatureScore {
        param(
            [ref]$RunningScore,
            [System.Collections.Generic.List[string]]$ReasonList,
            [bool]$Condition,
            [string]$FeatureKey,
            [double]$BaseWeight,
            [string]$Reason
        )

        if (-not $Condition) {
            return
        }

        $count = [int]($FeatureCounts[$FeatureKey] ?? 0)
        if ($count -le 0) {
            $count = 1
        }

        $value = [math]::Round($BaseWeight / $count, 2)
        $RunningScore.Value += $value
        $ReasonList.Add("$Reason (+$value)")
    }

    Add-FeatureScore -RunningScore ([ref]$score) -ReasonList $reasons -Condition $signals.UnitIdHit -FeatureKey 'UnitIdHit' -BaseWeight 160 -Reason 'unit id text'
    Add-FeatureScore -RunningScore ([ref]$score) -ReasonList $reasons -Condition $signals.NameHit -FeatureKey 'NameHit' -BaseWeight 90 -Reason 'player name text'
    Add-FeatureScore -RunningScore ([ref]$score) -ReasonList $reasons -Condition $signals.GuildHit -FeatureKey 'GuildHit' -BaseWeight 55 -Reason 'guild text'
    Add-FeatureScore -RunningScore ([ref]$score) -ReasonList $reasons -Condition $signals.HasHp -FeatureKey 'HasHp' -BaseWeight 120 -Reason 'hp match'
    Add-FeatureScore -RunningScore ([ref]$score) -ReasonList $reasons -Condition $signals.HasHpMax -FeatureKey 'HasHpMax' -BaseWeight 100 -Reason 'hp max match'
    Add-FeatureScore -RunningScore ([ref]$score) -ReasonList $reasons -Condition $signals.HasLevel -FeatureKey 'HasLevel' -BaseWeight 45 -Reason 'level match'
    Add-FeatureScore -RunningScore ([ref]$score) -ReasonList $reasons -Condition $signals.HasHealthPair -FeatureKey 'HasHealthPair' -BaseWeight 150 -Reason 'hp/hpmax pair'
    Add-FeatureScore -RunningScore ([ref]$score) -ReasonList $reasons -Condition ($signals.HasLevel -and $signals.HasHealthPair) -FeatureKey 'LevelHealthPair' -BaseWeight 90 -Reason 'level with health pair'
    Add-FeatureScore -RunningScore ([ref]$score) -ReasonList $reasons -Condition $signals.HasResourcePair -FeatureKey 'HasResourcePair' -BaseWeight 18 -Reason 'resource/resourceMax pair'
    Add-FeatureScore -RunningScore ([ref]$score) -ReasonList $reasons -Condition ($signals.HasCombo -and $signals.HasHealthPair) -FeatureKey 'ComboHealthPair' -BaseWeight 8 -Reason 'combo with health pair'
    Add-FeatureScore -RunningScore ([ref]$score) -ReasonList $reasons -Condition ($signals.HasPlanarMax -and $signals.HasHealthPair) -FeatureKey 'PlanarHealthPair' -BaseWeight 8 -Reason 'planarMax with health pair'

    if ($signals.WeakSignalOnly) {
        $penalty = [math]::Min(18, $signals.PlanarOffsets.Count + [math]::Floor($signals.ResourceOffsets.Count / 2))
        if ($penalty -gt 0) {
            $score -= $penalty
            $reasons.Add("weak/common scalar noise (-$penalty)")
        }
    }

    if ($signals.HasPlanar -and -not $signals.HasHealthPair -and -not $signals.HasIdentity -and -not $signals.HasLevel) {
        $penalty = [math]::Min(12, [math]::Ceiling($signals.PlanarOffsets.Count / 4.0))
        $score -= $penalty
        $reasons.Add("planar=0 noise (-$penalty)")
    }

    if ($IsTransformLike) {
        $score -= 120
        $reasons.Add('transform/source component penalty (-120)')
    }

    if ($Node.Depth -gt 0 -and $signals.StrongSignalCount -gt 0) {
        $bonus = [math]::Round(8.0 / ($Node.Depth + 1), 2)
        $score += $bonus
        $reasons.Add("reachable child with strong signal (+$bonus)")
    }

    return [ordered]@{
        Score = [math]::Round($score, 2)
        Reasons = $reasons.ToArray()
    }
}

function Get-ComponentSeedPointers {
    param(
        [object]$Component
    )

    $entries = New-Object System.Collections.Generic.List[object]
    foreach ($fieldName in @('Q8', 'Q68', 'Q100')) {
        $pointerValue = Try-Parse-HeapPointer -Value $Component.$fieldName
        if ($null -eq $pointerValue) {
            continue
        }

        $entries.Add([ordered]@{
            Label = $fieldName
            Address = $pointerValue
        })
    }

    return $entries.ToArray()
}

function Expand-ComponentNodes {
    param(
        [object]$Component,
        [hashtable]$ExpectedSignals
    )

    $componentAddress = Parse-HexUInt64 -Value ([string]$Component.Address)
    $queue = New-Object System.Collections.Generic.Queue[object]
    $seenAddresses = New-Object System.Collections.Generic.HashSet[UInt64]
    $nodes = New-Object System.Collections.Generic.List[object]

    $queue.Enqueue([ordered]@{
        Address = $componentAddress
        Path = 'self'
        Depth = 0
    })

    foreach ($seed in (Get-ComponentSeedPointers -Component $Component)) {
        if ($seenAddresses.Contains([UInt64]$seed.Address)) {
            continue
        }

        $queue.Enqueue([ordered]@{
            Address = [UInt64]$seed.Address
            Path = "seed:$($seed.Label)"
            Depth = 1
        })
    }

    while ($queue.Count -gt 0 -and $nodes.Count -lt $MaxNodesPerComponent) {
        $candidate = $queue.Dequeue()
        $address = [UInt64]$candidate.Address
        if (-not $seenAddresses.Add($address)) {
            continue
        }

        $readLength = if ($candidate.Depth -eq 0) { $ComponentReadLength } else { $ChildReadLength }
        $bytes = Try-Read-Bytes -Address $address -Length $readLength
        if ($null -eq $bytes) {
            continue
        }

        $signals = Get-SignalSummary -Bytes $bytes -Expected $ExpectedSignals
        $pointerEntries = @(Get-HeapPointerEntries -Bytes $bytes -Limit $MaxPointersPerNode -SeenPointers $seenAddresses)

        $node = [pscustomobject][ordered]@{
            Address = ('0x{0:X}' -f $address)
            AddressValue = $address
            Path = [string]$candidate.Path
            Depth = [int]$candidate.Depth
            Signals = $signals
            PointerCount = $pointerEntries.Count
            PointerTargets = @($pointerEntries | Select-Object -First 5)
        }
        $nodes.Add($node)

        if ($candidate.Depth -ge $MaxDepth) {
            continue
        }

        foreach ($pointerEntry in $pointerEntries) {
            $queue.Enqueue([ordered]@{
                Address = [UInt64]$pointerEntry.Value
                Path = ("{0}->{1}" -f $candidate.Path, $pointerEntry.OffsetHex)
                Depth = ($candidate.Depth + 1)
            })
        }
    }

    return $nodes.ToArray()
}

if ($RefreshOwnerComponents -or -not (Test-Path -LiteralPath $resolvedOwnerComponentsFile)) {
    & $ownerComponentsScript -Json | Out-Null
}

if (-not (Test-Path -LiteralPath $resolvedOwnerComponentsFile)) {
    throw "Owner-components file not found: $resolvedOwnerComponentsFile"
}

$ownerComponents = Get-Content -LiteralPath $resolvedOwnerComponentsFile -Raw | ConvertFrom-Json -Depth 60
$snapshot = Invoke-ReaderJson -Arguments @('--readerbridge-snapshot', '--json')
$player = $snapshot.Current.Player

$expectedSignals = @{
    Name = [string]$player.Name
    Guild = [string]$player.Guild
    UnitId = [string]$player.Id
    Level = [int]$player.Level
    Hp = [int]$player.Hp
    HpMax = [int]$player.HpMax
    Resource = [int]$player.Resource
    ResourceMax = [int]$player.ResourceMax
    Combo = [int]$player.Combo
    Planar = [int]$player.Planar
    PlanarMax = [int]$player.PlanarMax
    Vitality = [int]$player.Vitality
}

$componentExplorations = New-Object System.Collections.Generic.List[object]
$allNodes = New-Object System.Collections.Generic.List[object]

foreach ($component in $ownerComponents.Entries) {
    $nodes = @(Expand-ComponentNodes -Component $component -ExpectedSignals $expectedSignals)
    foreach ($node in $nodes) {
        $allNodes.Add($node)
    }

    $componentExplorations.Add([pscustomobject][ordered]@{
        Index = [int]$component.Index
        Address = [string]$component.Address
        RoleHints = @($component.RoleHints)
        Nodes = $nodes
    })
}

$featureCounts = @{
    UnitIdHit = Get-FeatureCount -Nodes $allNodes -PropertyName 'UnitIdHit'
    NameHit = Get-FeatureCount -Nodes $allNodes -PropertyName 'NameHit'
    GuildHit = Get-FeatureCount -Nodes $allNodes -PropertyName 'GuildHit'
    HasHp = Get-FeatureCount -Nodes $allNodes -PropertyName 'HasHp'
    HasHpMax = Get-FeatureCount -Nodes $allNodes -PropertyName 'HasHpMax'
    HasLevel = Get-FeatureCount -Nodes $allNodes -PropertyName 'HasLevel'
    HasHealthPair = Get-FeatureCount -Nodes $allNodes -PropertyName 'HasHealthPair'
    LevelHealthPair = @($allNodes | Where-Object { $_.Signals.HasLevel -and $_.Signals.HasHealthPair }).Count
    HasResourcePair = Get-FeatureCount -Nodes $allNodes -PropertyName 'HasResourcePair'
    ComboHealthPair = @($allNodes | Where-Object { $_.Signals.HasCombo -and $_.Signals.HasHealthPair }).Count
    PlanarHealthPair = @($allNodes | Where-Object { $_.Signals.HasPlanarMax -and $_.Signals.HasHealthPair }).Count
}

$candidates = New-Object System.Collections.Generic.List[object]
foreach ($componentData in $componentExplorations) {
    $scoredNodes = New-Object System.Collections.Generic.List[object]
    $isTransformLikeComponent = @($componentData.RoleHints | Where-Object { $_ -match 'selected-source|coord|orientation|transform' }).Count -gt 0

    foreach ($node in $componentData.Nodes) {
        $isTransformLikeNode = $isTransformLikeComponent -and ($node.Path -eq 'self')
        $nodeScore = Get-NodeScore -Node $node -FeatureCounts $featureCounts -IsTransformLike:$isTransformLikeNode
        $scoredNodes.Add([pscustomobject][ordered]@{
            Address = $node.Address
            Path = $node.Path
            Depth = $node.Depth
            Score = $nodeScore.Score
            Reasons = $nodeScore.Reasons
            PointerCount = $node.PointerCount
            Signals = $node.Signals
        })
    }

    $rankedNodes = @($scoredNodes | Sort-Object `
        @{ Expression = { [double]$_.Score }; Descending = $true }, `
        @{ Expression = { [int]$_.Depth }; Descending = $false }, `
        @{ Expression = { [string]$_.Address }; Descending = $false })

    $bestNode = $rankedNodes | Select-Object -First 1
    $candidates.Add([pscustomobject][ordered]@{
        Index = [int]$componentData.Index
        Address = [string]$componentData.Address
        RoleHints = @($componentData.RoleHints)
        BestNode = $bestNode
        EffectiveScore = if ($bestNode) { $bestNode.Score } else { [double]::NegativeInfinity }
        TopNodes = @($rankedNodes | Select-Object -First 5)
        NodeCount = $componentData.Nodes.Count
    })
}

$rankedCandidates = @(
    $candidates | Sort-Object `
        @{ Expression = { [double]$_.EffectiveScore }; Descending = $true }, `
        @{ Expression = { [int]$_.Index }; Descending = $false }
)

$result = [ordered]@{
    Mode = 'player-stat-component-candidates'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    OwnerComponentsFile = $resolvedOwnerComponentsFile
    SnapshotFile = [string]$snapshot.SourceFile
    ExpectedSignals = $expectedSignals
    FeatureCounts = $featureCounts
    CandidateCount = $rankedCandidates.Count
    Candidates = $rankedCandidates
}

$outputDirectory = Split-Path -Parent $resolvedOutputFile
if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

$jsonText = $result | ConvertTo-Json -Depth 40
Set-Content -LiteralPath $resolvedOutputFile -Value $jsonText -Encoding UTF8

if ($Json) {
    Write-Output $jsonText
}
else {
    Write-Host "Stat candidate file:     $resolvedOutputFile"
    Write-Host "Expected HP/HPMax:       $($expectedSignals.Hp) / $($expectedSignals.HpMax)"
    Write-Host "Expected resource pair:  $($expectedSignals.Resource) / $($expectedSignals.ResourceMax)"
    Write-Host "Rare strong hits across all nodes:"
    Write-Host "  hp=$($featureCounts.HasHp) hpMax=$($featureCounts.HasHpMax) level=$($featureCounts.HasLevel) unitId=$($featureCounts.UnitIdHit) name=$($featureCounts.NameHit) guild=$($featureCounts.GuildHit)"
    foreach ($candidate in ($rankedCandidates | Select-Object -First 8)) {
        $hintText = if ($candidate.RoleHints.Count -gt 0) { $candidate.RoleHints -join ', ' } else { 'unclassified' }
        $bestNodeText = if ($candidate.BestNode) { "$($candidate.BestNode.Address) path=$($candidate.BestNode.Path) score=$($candidate.BestNode.Score)" } else { '-' }
        Write-Host ("  [{0}] {1} score={2} hints={3}" -f $candidate.Index, $candidate.Address, $candidate.EffectiveScore, $hintText)
        Write-Host ("      best-node: {0}" -f $bestNodeText)
        if ($candidate.BestNode) {
            Write-Host ("      reasons:   {0}" -f ($candidate.BestNode.Reasons -join '; '))
        }
    }
}
