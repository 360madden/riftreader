[CmdletBinding()]
param(
    [switch]$Json,
    [switch]$RefreshConfirmation,
    [int]$MaxSamples = 6,
    [int]$NeighborhoodBytes = 384,
    [int]$TopHubs = 6,
    [int]$MovementHoldMilliseconds = 750,
    [string]$ConfirmationFile = (Join-Path $PSScriptRoot 'captures\ce-smart-player-family.json'),
    [string]$OwnerComponentsFile = (Join-Path $PSScriptRoot 'captures\player-owner-components.json'),
    [string]$StatHubGraphFile = (Join-Path $PSScriptRoot 'captures\player-stat-hub-graph.json'),
    [string]$ProjectorTraceFile = (Join-Path $PSScriptRoot 'captures\player-state-projector-trace.json'),
    [string]$CurrentAnchorFile = (Join-Path $PSScriptRoot 'captures\player-current-anchor.json'),
    [string]$OutputFile = (Join-Path $PSScriptRoot 'captures\ce-family-neighborhood.json')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$smartCaptureScript = Join-Path $PSScriptRoot 'smart-capture-player-family.ps1'
$resolvedConfirmationFile = [System.IO.Path]::GetFullPath($ConfirmationFile)
$resolvedOwnerComponentsFile = [System.IO.Path]::GetFullPath($OwnerComponentsFile)
$resolvedStatHubGraphFile = [System.IO.Path]::GetFullPath($StatHubGraphFile)
$resolvedProjectorTraceFile = [System.IO.Path]::GetFullPath($ProjectorTraceFile)
$resolvedCurrentAnchorFile = [System.IO.Path]::GetFullPath($CurrentAnchorFile)
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

    return ($output -join [Environment]::NewLine) | ConvertFrom-Json -Depth 30
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

    return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json -Depth 40
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

function Test-LikelyPointerValue {
    param(
        [Parameter(Mandatory = $true)]
        [UInt64]$Value
    )

    if ($Value -lt 0x10000) {
        return $false
    }

    if ($Value -eq [UInt64]::MaxValue) {
        return $false
    }

    if ($Value -gt 0x00007FFFFFFFFFFF) {
        return $false
    }

    return $true
}

function Get-AddressPrefix {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Address,

        [int]$Length = 3
    )

    $normalized = $Address.Trim().ToUpperInvariant()
    if ($normalized.StartsWith('0X')) {
        $normalized = $normalized.Substring(2)
    }

    if ($normalized.Length -lt $Length) {
        return $normalized
    }

    return $normalized.Substring(0, $Length)
}

function Test-LikelyPointerPrefix {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PointerHex,

        [Parameter(Mandatory = $true)]
        [string[]]$AllowedPrefixes
    )

    $normalized = Get-AddressPrefix -Address $PointerHex
    return $AllowedPrefixes -contains $normalized
}

if ($RefreshConfirmation -or -not (Test-Path -LiteralPath $resolvedConfirmationFile)) {
    & $smartCaptureScript -MovementHoldMilliseconds $MovementHoldMilliseconds | Out-Null
}

$confirmation = Read-JsonFile -Path $resolvedConfirmationFile
$ownerComponents = Read-JsonFile -Path $resolvedOwnerComponentsFile -Optional
$statHubGraph = Read-JsonFile -Path $resolvedStatHubGraphFile -Optional
$projectorTrace = Read-JsonFile -Path $resolvedProjectorTraceFile -Optional
$currentAnchor = Read-JsonFile -Path $resolvedCurrentAnchorFile -Optional

$winner = $confirmation.Winner
if ($null -eq $winner) {
    throw "Confirmation file '$resolvedConfirmationFile' did not contain a Winner record."
}

$knownAddressLabels = @{}
if ($ownerComponents) {
    Add-KnownAddress -Map $knownAddressLabels -Label 'owner-object' -Address ([string]$ownerComponents.Owner.Address)
    Add-KnownAddress -Map $knownAddressLabels -Label 'owner-container' -Address ([string]$ownerComponents.Owner.ContainerAddress)
    Add-KnownAddress -Map $knownAddressLabels -Label 'selected-source' -Address ([string]$ownerComponents.Owner.SelectedSourceAddress)
    Add-KnownAddress -Map $knownAddressLabels -Label 'owner-state-record' -Address ([string]$ownerComponents.Owner.StateRecordAddress)
}

if ($projectorTrace) {
    Add-KnownAddress -Map $knownAddressLabels -Label 'owner-state-slot-50' -Address ([string]$projectorTrace.Owner.StateSlot50)
    Add-KnownAddress -Map $knownAddressLabels -Label 'owner-state-slot-58' -Address ([string]$projectorTrace.Owner.StateSlot58)
    Add-KnownAddress -Map $knownAddressLabels -Label 'owner-state-slot-60' -Address ([string]$projectorTrace.Owner.StateSlot60)
}

if ($statHubGraph) {
    $hubRank = 0
    foreach ($hub in @($statHubGraph.RankedSharedHubs | Select-Object -First $TopHubs)) {
        if ($null -eq $hub -or [string]::IsNullOrWhiteSpace([string]$hub.Address)) {
            continue
        }

        $hubRank++
        Add-KnownAddress -Map $knownAddressLabels -Label ('shared-hub-{0}' -f $hubRank) -Address ([string]$hub.Address)
    }
}

if ($currentAnchor) {
    Add-KnownAddress -Map $knownAddressLabels -Label 'player-current-anchor' -Address ([string]$currentAnchor.AddressHex)
}

$sampleAddresses = New-Object System.Collections.Generic.List[string]
$seenSamples = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
foreach ($address in @($winner.CeConfirmedSampleAddresses) + @($confirmation.TripletConfirmedAddresses) + @($winner.SampleAddresses)) {
    $addressText = [string]$address
    if ([string]::IsNullOrWhiteSpace($addressText)) {
        continue
    }

    if ($seenSamples.Add($addressText)) {
        $sampleAddresses.Add($addressText) | Out-Null
    }

    if ($sampleAddresses.Count -ge $MaxSamples) {
        break
    }
}

if ($sampleAddresses.Count -le 0) {
    throw "No CE family sample addresses were available to inspect."
}

foreach ($sampleAddress in @($sampleAddresses)) {
    Add-KnownAddress -Map $knownAddressLabels -Label ('winner-sample:{0}' -f $sampleAddress) -Address $sampleAddress
}

$likelyPointerPrefixes = @(
    $knownAddressLabels.Keys |
        ForEach-Object { Get-AddressPrefix -Address $_ } |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
        Select-Object -Unique
)

$sampleRecords = New-Object System.Collections.Generic.List[object]
$sharedPointerBuckets = @{}
$warnings = New-Object System.Collections.Generic.List[string]

foreach ($sampleAddress in @($sampleAddresses)) {
    try {
        $baseAddress = Parse-HexUInt64 -Value $sampleAddress
        $bytes = Read-Bytes -Address $baseAddress -Length $NeighborhoodBytes
        if ($bytes.Length -lt 12) {
            throw "Only read $($bytes.Length) bytes."
        }

        $pointerMatches = New-Object System.Collections.Generic.List[object]
        for ($offset = 0; $offset -le ($bytes.Length - 8); $offset += 8) {
            $pointerValue = [BitConverter]::ToUInt64($bytes, $offset)
            if (-not (Test-LikelyPointerValue -Value $pointerValue)) {
                continue
            }

            $pointerHex = Format-HexUInt64 -Value $pointerValue
            if (-not (Test-LikelyPointerPrefix -PointerHex $pointerHex -AllowedPrefixes $likelyPointerPrefixes)) {
                continue
            }

            if (-not $sharedPointerBuckets.ContainsKey($offset)) {
                $sharedPointerBuckets[$offset] = New-Object System.Collections.Generic.List[string]
            }

            $sharedPointerBuckets[$offset].Add($pointerHex) | Out-Null

            $normalizedPointer = $pointerHex.ToUpperInvariant()
            if (-not $knownAddressLabels.ContainsKey($normalizedPointer)) {
                continue
            }

            $pointerMatches.Add([ordered]@{
                    Offset = $offset
                    OffsetHex = ('0x{0:X}' -f $offset)
                    Pointer = $pointerHex
                    Labels = @($knownAddressLabels[$normalizedPointer].ToArray())
                }) | Out-Null
        }

        $sampleRecords.Add([ordered]@{
                Address = $sampleAddress
                Coords = [ordered]@{
                    X = [BitConverter]::ToSingle($bytes, 0x0)
                    Y = [BitConverter]::ToSingle($bytes, 0x4)
                    Z = [BitConverter]::ToSingle($bytes, 0x8)
                }
                PointerMatchCount = $pointerMatches.Count
                PointerMatches = @($pointerMatches.ToArray())
            }) | Out-Null
    }
    catch {
        $warnings.Add(("Unable to inspect CE family sample '{0}': {1}" -f $sampleAddress, $_.Exception.Message)) | Out-Null
    }
}

$sharedPointers = New-Object System.Collections.Generic.List[object]
foreach ($offset in @($sharedPointerBuckets.Keys | Sort-Object)) {
    $values = @($sharedPointerBuckets[$offset])
    if ($values.Count -ne $sampleRecords.Count -or $values.Count -le 0) {
        continue
    }

    $uniqueValues = @($values | Select-Object -Unique)
    if ($uniqueValues.Count -ne 1) {
        continue
    }

    $pointerHex = [string]$uniqueValues[0]
    $labels = @()
    $normalizedPointer = $pointerHex.ToUpperInvariant()
    if ($knownAddressLabels.ContainsKey($normalizedPointer)) {
        $labels = @($knownAddressLabels[$normalizedPointer].ToArray())
    }

    $sharedPointers.Add([ordered]@{
            Offset = [int]$offset
            OffsetHex = ('0x{0:X}' -f [int]$offset)
            Pointer = $pointerHex
            Labels = $labels
        }) | Out-Null
}

$document = [ordered]@{
    Mode = 'ce-family-neighborhood'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    ConfirmationFile = $resolvedConfirmationFile
    ConfirmationGeneratedAtUtc = [string]$confirmation.GeneratedAtUtc
    SourceObjectAddress = if ($ownerComponents) { [string]$ownerComponents.Owner.SelectedSourceAddress } else { $null }
    SelectedSourceAddress = if ($ownerComponents) { [string]$ownerComponents.Owner.SelectedSourceAddress } else { $null }
    WinnerFamilyId = [string]$confirmation.WinnerFamilyId
    WinnerSignature = [string]$winner.Signature
    WinnerNotes = [string]$winner.Notes
    NeighborhoodBytes = $NeighborhoodBytes
    SampleCount = $sampleRecords.Count
    KnownAddresses = [ordered]@{
        OwnerObject = if ($ownerComponents) { [string]$ownerComponents.Owner.Address } else { $null }
        OwnerContainer = if ($ownerComponents) { [string]$ownerComponents.Owner.ContainerAddress } else { $null }
        SelectedSource = if ($ownerComponents) { [string]$ownerComponents.Owner.SelectedSourceAddress } else { $null }
        OwnerStateRecord = if ($ownerComponents) { [string]$ownerComponents.Owner.StateRecordAddress } else { $null }
        StateSlot50 = if ($projectorTrace) { [string]$projectorTrace.Owner.StateSlot50 } else { $null }
        StateSlot58 = if ($projectorTrace) { [string]$projectorTrace.Owner.StateSlot58 } else { $null }
        StateSlot60 = if ($projectorTrace) { [string]$projectorTrace.Owner.StateSlot60 } else { $null }
        CurrentAnchor = if ($currentAnchor) { [string]$currentAnchor.AddressHex } else { $null }
        SharedHubs = if ($statHubGraph) { @($statHubGraph.RankedSharedHubs | Select-Object -First $TopHubs | ForEach-Object { [string]$_.Address }) } else { @() }
    }
    Samples = @($sampleRecords.ToArray())
    SharedPointers = @($sharedPointers.ToArray())
    Warnings = @($warnings.ToArray())
}

$outputDirectory = Split-Path -Path $resolvedOutputFile -Parent
if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

$jsonText = $document | ConvertTo-Json -Depth 20
Set-Content -LiteralPath $resolvedOutputFile -Value $jsonText -Encoding UTF8

$result = [ordered]@{
    Mode = 'ce-family-neighborhood-capture'
    OutputFile = $resolvedOutputFile
    WinnerFamilyId = [string]$confirmation.WinnerFamilyId
    SampleCount = $sampleRecords.Count
    SharedPointerCount = $sharedPointers.Count
    WarningCount = $warnings.Count
}

if ($Json) {
    $result | ConvertTo-Json -Depth 10
    exit 0
}

Write-Host "CE family neighborhood captured." -ForegroundColor Green
Write-Host ("Output:              {0}" -f $resolvedOutputFile)
Write-Host ("Winner family:       {0}" -f [string]$confirmation.WinnerFamilyId)
Write-Host ("Samples:             {0}" -f $sampleRecords.Count)
Write-Host ("Shared pointers:     {0}" -f $sharedPointers.Count)
Write-Host ("Warnings:            {0}" -f $warnings.Count)
