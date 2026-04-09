[CmdletBinding()]
param(
    [switch]$Json,
    [switch]$RefreshOwnerComponents,
    [int]$ComponentReadLength = 0x180,
    [int]$HubReadLength = 0x340,
    [int]$MaxPointersPerComponent = 20,
    [string]$OwnerComponentsFile = (Join-Path $PSScriptRoot 'captures\player-owner-components.json'),
    [string]$OutputFile = (Join-Path $PSScriptRoot 'captures\player-stat-hub-graph.json')
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

function Try-Read-Bytes {
    param(
        [Parameter(Mandatory = $true)]
        [UInt64]$Address,

        [Parameter(Mandatory = $true)]
        [int]$Length
    )

    try {
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
    catch {
        return $null
    }
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

function Find-UInt64Offsets {
    param(
        [byte[]]$Bytes,
        [UInt64]$Value
    )

    $offsets = New-Object System.Collections.Generic.List[int]
    for ($offset = 0; $offset -le ($Bytes.Length - 8); $offset += 8) {
        if ([BitConverter]::ToUInt64($Bytes, $offset) -eq $Value) {
            $offsets.Add($offset)
        }
    }

    return $offsets.ToArray()
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

function Get-HeapPointerEntries {
    param(
        [byte[]]$Bytes,
        [int]$Limit
    )

    $entries = New-Object System.Collections.Generic.List[object]
    $seen = New-Object System.Collections.Generic.HashSet[UInt64]
    for ($offset = 0; $offset -le ($Bytes.Length - 8); $offset += 8) {
        $pointerValue = Read-UInt64At -Bytes $Bytes -Offset $offset
        if ($null -eq $pointerValue) {
            continue
        }

        if ($pointerValue -le 0x0000000100000000 -or $pointerValue -ge 0x0000700000000000) {
            continue
        }

        if (-not $seen.Add($pointerValue)) {
            continue
        }

        $entries.Add([pscustomobject][ordered]@{
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

if ($RefreshOwnerComponents -or -not (Test-Path -LiteralPath $resolvedOwnerComponentsFile)) {
    $ownerComponentArguments = @{
        Json = $true
    }

    if ($RefreshOwnerComponents) {
        $ownerComponentArguments['RefreshSelectorTrace'] = $true
    }

    & $ownerComponentsScript @ownerComponentArguments | Out-Null
}

if (-not (Test-Path -LiteralPath $resolvedOwnerComponentsFile)) {
    throw "Owner-components file not found: $resolvedOwnerComponentsFile"
}

$ownerComponents = Get-Content -LiteralPath $resolvedOwnerComponentsFile -Raw | ConvertFrom-Json -Depth 60
$snapshot = Invoke-ReaderJson -Arguments @('--readerbridge-snapshot', '--json')
$player = $snapshot.Current.Player

$ownerAddress = Parse-HexUInt64 -Value ([string]$ownerComponents.Owner.Address)
$selectedSourceAddress = Parse-HexUInt64 -Value ([string]$ownerComponents.Owner.SelectedSourceAddress)
$stateRecordAddress = Parse-HexUInt64 -Value ([string]$ownerComponents.Owner.StateRecordAddress)
$playerUnitIdHex = ([string]$player.Id).TrimStart('u', 'U')
$playerUnitIdValue = [UInt64]::Parse($playerUnitIdHex, [System.Globalization.NumberStyles]::HexNumber, [System.Globalization.CultureInfo]::InvariantCulture)

$componentDetails = New-Object System.Collections.Generic.List[object]
$hubReferenceMap = @{}

foreach ($component in $ownerComponents.Entries) {
    $componentAddress = Parse-HexUInt64 -Value ([string]$component.Address)
    $bytes = Try-Read-Bytes -Address $componentAddress -Length $ComponentReadLength
    if ($null -eq $bytes) {
        continue
    }

    $pointers = @(Get-HeapPointerEntries -Bytes $bytes -Limit $MaxPointersPerComponent)
    $unitIdOffsets = @(Find-UInt64Offsets -Bytes $bytes -Value $playerUnitIdValue)
    $ownerOffsets = @(Find-UInt64Offsets -Bytes $bytes -Value $ownerAddress)
    $stateOffsets = @(Find-UInt64Offsets -Bytes $bytes -Value $stateRecordAddress)
    $sourceOffsets = @(Find-UInt64Offsets -Bytes $bytes -Value $selectedSourceAddress)
    $levelOffsets = @(Find-Int32Offsets -Bytes $bytes -Value ([int]$player.Level))
    $hpOffsets = @(Find-Int32Offsets -Bytes $bytes -Value ([int]$player.Hp))
    $hpMaxOffsets = @(Find-Int32Offsets -Bytes $bytes -Value ([int]$player.HpMax))
    $resourceOffsets = @(Find-Int32Offsets -Bytes $bytes -Value ([int]$player.Resource))
    $resourceMaxOffsets = @(Find-Int32Offsets -Bytes $bytes -Value ([int]$player.ResourceMax))
    $comboOffsets = @(Find-Int32Offsets -Bytes $bytes -Value ([int]$player.Combo))
    $planarMaxOffsets = @(Find-Int32Offsets -Bytes $bytes -Value ([int]$player.PlanarMax))

    foreach ($pointer in $pointers) {
        if (-not $hubReferenceMap.ContainsKey($pointer.Address)) {
            $hubReferenceMap[$pointer.Address] = New-Object System.Collections.Generic.List[object]
        }

        $hubReferenceMap[$pointer.Address].Add([pscustomobject][ordered]@{
            ComponentIndex = [int]$component.Index
            ComponentAddress = [string]$component.Address
            Offset = $pointer.Offset
            OffsetHex = $pointer.OffsetHex
        })
    }

    $componentDetails.Add([pscustomobject][ordered]@{
        Index = [int]$component.Index
        Address = [string]$component.Address
        RoleHints = @($component.RoleHints)
        PointerTargets = $pointers
        UnitIdOffsets = $unitIdOffsets
        OwnerOffsets = $ownerOffsets
        StateOffsets = $stateOffsets
        SourceOffsets = $sourceOffsets
        LevelOffsets = $levelOffsets
        HpOffsets = $hpOffsets
        HpMaxOffsets = $hpMaxOffsets
        ResourceOffsets = $resourceOffsets
        ResourceMaxOffsets = $resourceMaxOffsets
        ComboOffsets = $comboOffsets
        PlanarMaxOffsets = $planarMaxOffsets
    })
}

$identityComponents = @(
    $componentDetails |
        Where-Object { $_.UnitIdOffsets.Count -gt 0 } |
        Sort-Object `
            @{ Expression = { $_.OwnerOffsets.Count }; Descending = $true }, `
            @{ Expression = { $_.PointerTargets.Count }; Descending = $true }, `
            @{ Expression = { $_.Index }; Descending = $false }
)

$hubCandidates = New-Object System.Collections.Generic.List[object]
foreach ($hubEntry in $hubReferenceMap.GetEnumerator()) {
    $hubAddressText = [string]$hubEntry.Key
    $references = @($hubEntry.Value.ToArray())
    if ($references.Count -lt 2) {
        continue
    }

    $hubAddress = Parse-HexUInt64 -Value $hubAddressText
    if ($hubAddress -eq $ownerAddress) {
        continue
    }
    $hubBytes = Try-Read-Bytes -Address $hubAddress -Length $HubReadLength
    if ($null -eq $hubBytes) {
        continue
    }

    $levelOffsets = @(Find-Int32Offsets -Bytes $hubBytes -Value ([int]$player.Level))
    $hpOffsets = @(Find-Int32Offsets -Bytes $hubBytes -Value ([int]$player.Hp))
    $hpMaxOffsets = @(Find-Int32Offsets -Bytes $hubBytes -Value ([int]$player.HpMax))
    $resourceOffsets = @(Find-Int32Offsets -Bytes $hubBytes -Value ([int]$player.Resource))
    $resourceMaxOffsets = @(Find-Int32Offsets -Bytes $hubBytes -Value ([int]$player.ResourceMax))
    $comboOffsets = @(Find-Int32Offsets -Bytes $hubBytes -Value ([int]$player.Combo))
    $planarMaxOffsets = @(Find-Int32Offsets -Bytes $hubBytes -Value ([int]$player.PlanarMax))
    $ownerOffsets = @(Find-UInt64Offsets -Bytes $hubBytes -Value $ownerAddress)
    $stateOffsets = @(Find-UInt64Offsets -Bytes $hubBytes -Value $stateRecordAddress)
    $sourceOffsets = @(Find-UInt64Offsets -Bytes $hubBytes -Value $selectedSourceAddress)

    $score = 0
    $reasons = New-Object System.Collections.Generic.List[string]

    if ($references.Count -gt 1) {
        $score += ($references.Count * 15)
        $reasons.Add("shared by $($references.Count) components")
    }
    if ($levelOffsets.Count -gt 0) {
        $score += 40
        $reasons.Add("contains level match at $((@($levelOffsets | ForEach-Object { '0x{0:X}' -f $_ }) -join ', '))")
    }
    if ($hpOffsets.Count -gt 0 -or $hpMaxOffsets.Count -gt 0) {
        $score += 70
        $reasons.Add('contains hp or hpMax match')
    }
    if ($resourceOffsets.Count -gt 0 -and $resourceMaxOffsets.Count -gt 0) {
        $score += 18
        $reasons.Add('contains resource/resourceMax pair')
    }
    if ($comboOffsets.Count -gt 0 -and $planarMaxOffsets.Count -gt 0) {
        $score += 8
        $reasons.Add('contains combo/planarMax pair')
    }
    if ($ownerOffsets.Count -gt 0) {
        $score += 24
        $reasons.Add("contains owner backref at $((@($ownerOffsets | ForEach-Object { '0x{0:X}' -f $_ }) -join ', '))")
    }
    if ($stateOffsets.Count -gt 0) {
        $score += 12
        $reasons.Add('contains state-record backref')
    }
    if ($sourceOffsets.Count -gt 0) {
        $score += 12
        $reasons.Add('contains selected-source backref')
    }

    $hubCandidates.Add([pscustomobject][ordered]@{
        Address = $hubAddressText
        Score = $score
        ComponentRefs = @($references | Sort-Object ComponentIndex, Offset)
        LevelOffsets = @($levelOffsets | ForEach-Object { '0x{0:X}' -f $_ })
        HpOffsets = @($hpOffsets | ForEach-Object { '0x{0:X}' -f $_ })
        HpMaxOffsets = @($hpMaxOffsets | ForEach-Object { '0x{0:X}' -f $_ })
        ResourceOffsets = @($resourceOffsets | ForEach-Object { '0x{0:X}' -f $_ })
        ResourceMaxOffsets = @($resourceMaxOffsets | ForEach-Object { '0x{0:X}' -f $_ })
        ComboOffsets = @($comboOffsets | ForEach-Object { '0x{0:X}' -f $_ })
        PlanarMaxOffsets = @($planarMaxOffsets | ForEach-Object { '0x{0:X}' -f $_ })
        OwnerOffsets = @($ownerOffsets | ForEach-Object { '0x{0:X}' -f $_ })
        StateOffsets = @($stateOffsets | ForEach-Object { '0x{0:X}' -f $_ })
        SourceOffsets = @($sourceOffsets | ForEach-Object { '0x{0:X}' -f $_ })
        Reasons = $reasons.ToArray()
    })
}

$rankedHubs = @(
    $hubCandidates |
        Sort-Object `
            @{ Expression = { [int]$_.Score }; Descending = $true }, `
            @{ Expression = { $_.Address }; Descending = $false }
)

$identityGraphLinks = New-Object System.Collections.Generic.List[object]
foreach ($identity in $identityComponents) {
    foreach ($pointerTarget in $identity.PointerTargets) {
        $matchingHub = $rankedHubs | Where-Object { $_.Address -eq $pointerTarget.Address } | Select-Object -First 1
        if ($null -eq $matchingHub) {
            continue
        }

        $identityGraphLinks.Add([pscustomobject][ordered]@{
            IdentityComponentIndex = $identity.Index
            IdentityComponentAddress = $identity.Address
            OffsetHex = $pointerTarget.OffsetHex
            HubAddress = $matchingHub.Address
            HubScore = $matchingHub.Score
        })
    }
}

$result = [ordered]@{
    Mode = 'player-stat-hub-graph'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    OwnerComponentsFile = $resolvedOwnerComponentsFile
    SnapshotFile = [string]$snapshot.SourceFile
    OwnerAddress = ('0x{0:X}' -f $ownerAddress)
    StateRecordAddress = ('0x{0:X}' -f $stateRecordAddress)
    SelectedSourceAddress = ('0x{0:X}' -f $selectedSourceAddress)
    PlayerUnitId = [string]$player.Id
    PlayerUnitIdRawHex = ('0x{0:X16}' -f $playerUnitIdValue)
    PlayerLevel = [int]$player.Level
    PlayerHp = [int]$player.Hp
    PlayerHpMax = [int]$player.HpMax
    PlayerResource = [int]$player.Resource
    PlayerResourceMax = [int]$player.ResourceMax
    PlayerCombo = [int]$player.Combo
    PlayerPlanarMax = [int]$player.PlanarMax
    IdentityComponents = $identityComponents
    RankedSharedHubs = $rankedHubs
    IdentityGraphLinks = $identityGraphLinks
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
    Write-Host "Stat hub graph file:     $resolvedOutputFile"
    Write-Host "Player unit id raw:      $('0x{0:X16}' -f $playerUnitIdValue)"
    foreach ($identity in ($identityComponents | Select-Object -First 3)) {
        Write-Host ("  identity [{0}] {1} unitIdOffsets={2} ownerOffsets={3}" -f $identity.Index, $identity.Address, (@($identity.UnitIdOffsets | ForEach-Object { '0x{0:X}' -f $_ }) -join ', '), (@($identity.OwnerOffsets | ForEach-Object { '0x{0:X}' -f $_ }) -join ', '))
    }

    foreach ($hub in ($rankedHubs | Select-Object -First 6)) {
        $refText = @($hub.ComponentRefs | ForEach-Object { "[{0}] {1}" -f $_.ComponentIndex, $_.OffsetHex }) -join ', '
        Write-Host ("  hub {0} score={1}" -f $hub.Address, $hub.Score)
        Write-Host ("      refs:    {0}" -f $refText)
        Write-Host ("      reasons: {0}" -f ($hub.Reasons -join '; '))
    }
}
