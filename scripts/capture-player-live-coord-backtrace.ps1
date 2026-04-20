[CmdletBinding()]
param(
    [string]$ProcessName = 'rift_x64',
    [switch]$SkipRefresh,
    [switch]$NoPointerScan,
    [switch]$NoNeighborhoodRead,
    [switch]$NoAhkFallback,
    [switch]$Json,
    [int]$ScanContextBytes = 192,
    [int]$MaxHits = 12,
    [int]$PointerWidth = 8,
    [int]$PointerScanContextBytes = 32,
    [int]$MaxPointerHits = 24,
    [int]$NeighborhoodBytesBefore = 64,
    [int]$NeighborhoodBytesAfter = 192,
    [string]$OutputFile = (Join-Path $PSScriptRoot 'captures\player-live-coord-backtrace.json')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$refreshScript = Join-Path $PSScriptRoot 'refresh-readerbridge-export.ps1'
$resolvedOutputFile = [System.IO.Path]::GetFullPath($OutputFile)

if ($ScanContextBytes -lt 0) {
    throw 'ScanContextBytes must be zero or greater.'
}

if ($MaxHits -le 0) {
    throw 'MaxHits must be greater than zero.'
}

if ($PointerWidth -notin 4, 8) {
    throw 'PointerWidth must be 4 or 8.'
}

if ($PointerScanContextBytes -lt 0) {
    throw 'PointerScanContextBytes must be zero or greater.'
}

if ($MaxPointerHits -le 0) {
    throw 'MaxPointerHits must be greater than zero.'
}

if ($NeighborhoodBytesBefore -lt 0 -or $NeighborhoodBytesAfter -lt 0) {
    throw 'Neighborhood byte counts must be zero or greater.'
}

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

    return ($output -join [Environment]::NewLine) | ConvertFrom-Json -Depth 20
}

function Parse-HexInt64 {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    $normalized = $Value.Trim()
    if ($normalized.StartsWith('0x', [System.StringComparison]::OrdinalIgnoreCase)) {
        $normalized = $normalized.Substring(2)
    }

    return [Int64]::Parse($normalized, [System.Globalization.NumberStyles]::HexNumber, [System.Globalization.CultureInfo]::InvariantCulture)
}

function Convert-BytesHexToFloatTriplet {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BytesHex
    )

    $bytes = [Convert]::FromHexString($BytesHex)
    if ($bytes.Length -lt 12) {
        throw "Expected at least 12 bytes for a float triplet, got $($bytes.Length)."
    }

    return [ordered]@{
        X = [BitConverter]::ToSingle($bytes, 0)
        Y = [BitConverter]::ToSingle($bytes, 4)
        Z = [BitConverter]::ToSingle($bytes, 8)
    }
}

function Get-RawMemoryRead {
    param(
        [Parameter(Mandatory = $true)]
        [Int64]$Address,

        [Parameter(Mandatory = $true)]
        [int]$Length
    )

    return Invoke-ReaderJson -Arguments @(
        '--process-name', $ProcessName,
        '--address', ('0x{0:X}' -f $Address),
        '--length', $Length.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '--json')
}

function Convert-SignalSummary {
    param(
        [Parameter(Mandatory = $true)]
        [psobject]$Signal
    )

    return [ordered]@{
        Name = [string]$Signal.Name
        Value = [string]$Signal.Value
        RelativeOffset = $Signal.RelativeOffset
    }
}

function Convert-HitSummary {
    param(
        [Parameter(Mandatory = $true)]
        [psobject]$Hit
    )

    return [ordered]@{
        AddressHex = [string]$Hit.AddressHex
        Score = $Hit.Score
        FamilyId = [string]$Hit.FamilyId
        FamilyHitCount = $Hit.FamilyHitCount
        RegionBaseHex = [string]$Hit.RegionBaseHex
        RegionSize = $Hit.RegionSize
        Signals = @($Hit.Signals | ForEach-Object { Convert-SignalSummary -Signal $_ })
    }
}

function Convert-FamilySummary {
    param(
        [Parameter(Mandatory = $true)]
        [psobject]$Family
    )

    return [ordered]@{
        FamilyId = [string]$Family.FamilyId
        Signature = [string]$Family.Signature
        HitCount = $Family.HitCount
        BestScore = $Family.BestScore
        Notes = [string]$Family.Notes
        RepresentativeAddressHex = [string]$Family.RepresentativeAddressHex
        SampleAddresses = @($Family.SampleAddresses)
    }
}

$warnings = [System.Collections.Generic.List[string]]::new()

if (-not $SkipRefresh) {
    $refreshArguments = @{
        NoReader = $true
    }

    if ($NoAhkFallback) {
        $refreshArguments['NoAhkFallback'] = $true
    }

    & $refreshScript @refreshArguments
}

$snapshot = Invoke-ReaderJson -Arguments @('--readerbridge-snapshot', '--json')
$player = $snapshot.Current.Player
if ($null -eq $player) {
    throw 'ReaderBridge snapshot did not contain a current player snapshot.'
}

if ($null -eq $player.Coord -or $null -eq $player.Coord.X -or $null -eq $player.Coord.Y -or $null -eq $player.Coord.Z) {
    throw 'ReaderBridge snapshot did not contain a complete player coordinate triplet.'
}

$scan = Invoke-ReaderJson -Arguments @(
    '--process-name', $ProcessName,
    '--scan-readerbridge-player-signature',
    '--scan-context', $ScanContextBytes.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '--max-hits', $MaxHits.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '--json')

$scanHits = @($scan.Hits)
$scanFamilies = @($scan.Families)
if ($scanHits.Count -le 0 -or $scanFamilies.Count -le 0) {
    throw 'No grouped player-signature hits were found for the current ReaderBridge coordinates.'
}

$selectedHit = $scanHits[0]
$selectedFamily = $scanFamilies | Where-Object { $_.FamilyId -eq $selectedHit.FamilyId } | Select-Object -First 1
if ($null -eq $selectedFamily) {
    throw "Unable to resolve the selected family '$($selectedHit.FamilyId)' from the scan results."
}

$selectedFamilyHits = @($scanHits | Where-Object { $_.FamilyId -eq $selectedHit.FamilyId })
$alternativeSampleAddresses = @($selectedFamily.SampleAddresses | Where-Object { $_ -ne $selectedHit.AddressHex })
if ($selectedFamily.HitCount -gt 1) {
    $warnings.Add(("Selected family '{0}' has {1} matching sample addresses in memory; the chosen hit is the current top-ranked candidate, not yet uniquely movement-confirmed." -f $selectedHit.FamilyId, $selectedFamily.HitCount)) | Out-Null
}

$selectedAddress = Parse-HexInt64 -Value ([string]$selectedHit.AddressHex)
$rawTripletRead = Get-RawMemoryRead -Address $selectedAddress -Length 12
$rawTriplet = Convert-BytesHexToFloatTriplet -BytesHex ([string]$rawTripletRead.BytesHex)

$neighborhoodRead = $null
if (-not $NoNeighborhoodRead) {
    $neighborhoodStart = $selectedAddress - $NeighborhoodBytesBefore
    if ($neighborhoodStart -lt 0) {
        $neighborhoodStart = 0
    }

    $neighborhoodLength = $NeighborhoodBytesBefore + 12 + $NeighborhoodBytesAfter
    $neighborhoodRead = Get-RawMemoryRead -Address $neighborhoodStart -Length $neighborhoodLength
}

$pointerScan = $null
if (-not $NoPointerScan) {
    $pointerScan = Invoke-ReaderJson -Arguments @(
        '--process-name', $ProcessName,
        '--scan-pointer', ('0x{0:X}' -f $selectedAddress),
        '--pointer-width', $PointerWidth.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '--scan-context', $PointerScanContextBytes.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '--max-hits', $MaxPointerHits.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '--json')
}

$result = [ordered]@{
    Mode = 'player-live-coord-backtrace'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    ProcessName = $ProcessName
    Snapshot = [ordered]@{
        SourceFile = [string]$snapshot.SourceFile
        LoadedAtUtc = [string]$snapshot.LoadedAtUtc
        ExportCount = $snapshot.ExportCount
        ExportReason = [string]$snapshot.Current.ExportReason
        Player = [ordered]@{
            Name = [string]$player.Name
            Level = $player.Level
            Health = $player.Hp
            HealthMax = $player.HpMax
            Location = [string]$player.LocationName
            Coord = [ordered]@{
                X = $player.Coord.X
                Y = $player.Coord.Y
                Z = $player.Coord.Z
            }
        }
    }
    SignatureScan = [ordered]@{
        SearchLabel = [string]$scan.SearchLabel
        InspectionRadius = $scan.InspectionRadius
        CandidateCount = $scan.CandidateCount
        RawHitCount = $scan.RawHitCount
        FamilyCount = $scan.FamilyCount
        HitCount = $scan.HitCount
        TopFamilies = @($scanFamilies | Select-Object -First 5 | ForEach-Object { Convert-FamilySummary -Family $_ })
        TopHits = @($scanHits | Select-Object -First 5 | ForEach-Object { Convert-HitSummary -Hit $_ })
    }
    Selected = [ordered]@{
        Family = Convert-FamilySummary -Family $selectedFamily
        Hit = Convert-HitSummary -Hit $selectedHit
        FamilyHits = @($selectedFamilyHits | Select-Object -First 5 | ForEach-Object { Convert-HitSummary -Hit $_ })
        AlternativeSampleAddresses = $alternativeSampleAddresses
        RawTripletRead = [ordered]@{
            Address = [string]$rawTripletRead.Address
            Length = $rawTripletRead.Length
            BytesHex = [string]$rawTripletRead.BytesHex
        }
        Triplet = $rawTriplet
        NeighborhoodRead = if ($neighborhoodRead) {
            [ordered]@{
                Address = [string]$neighborhoodRead.Address
                Length = $neighborhoodRead.Length
                BytesHex = [string]$neighborhoodRead.BytesHex
            }
        } else {
            $null
        }
    }
    PointerBacktrace = $pointerScan
    Warnings = @($warnings)
    OutputFile = $resolvedOutputFile
}

$outputDirectory = Split-Path -Parent $resolvedOutputFile
if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

$jsonText = $result | ConvertTo-Json -Depth 10
[System.IO.File]::WriteAllText($resolvedOutputFile, $jsonText, [System.Text.UTF8Encoding]::new($false))

if ($Json) {
    Write-Output $jsonText
    exit 0
}

Write-Host "Backtrace file:        $resolvedOutputFile"
Write-Host "Snapshot source:       $($snapshot.SourceFile)"
Write-Host "Player:                $($player.Name) Lv$($player.Level) @ $($player.LocationName)"
Write-Host "Addon coords:          $($player.Coord.X), $($player.Coord.Y), $($player.Coord.Z)"
Write-Host "Selected family:       $($selectedHit.FamilyId)"
Write-Host "Selected address:      $($selectedHit.AddressHex)"
Write-Host "Selected memory xyz:   $($rawTriplet.X), $($rawTriplet.Y), $($rawTriplet.Z)"
Write-Host "Family hit count:      $($selectedFamilyHits.Count)"

if ($pointerScan) {
    Write-Host "Pointer backrefs:      $($pointerScan.HitCount)"
}

if ($warnings.Count -gt 0) {
    Write-Host ""
    foreach ($warning in $warnings) {
        Write-Warning $warning
    }
}
