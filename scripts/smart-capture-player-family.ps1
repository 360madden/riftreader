[CmdletBinding()]
param(
    [string]$MovementKey = "w",
    [int]$MovementHoldMilliseconds = 500,
    [int]$MaxScanHits = 12,
    [int]$ScanContextBytes = 192,
    [int]$MaxCeAddresses = 256
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$ceExecScript = Join-Path $PSScriptRoot 'cheatengine-exec.ps1'
$ceFloatScanLua = Join-Path $PSScriptRoot 'ce-float-scan.lua'
$refreshScript = Join-Path $PSScriptRoot 'refresh-readerbridge-export.ps1'
$postKeyScript = Join-Path $PSScriptRoot 'post-rift-key.ps1'

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

function Invoke-CeNumeric {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Code
    )

    $result = & $ceExecScript -Code $Code

    return [UInt64]($result | Select-Object -Last 1)
}

function Load-CeHelper {
    $result = & $ceExecScript -LuaFile $ceFloatScanLua

    $loaded = [UInt64]($result | Select-Object -Last 1)
    if ($loaded -ne 1) {
        throw "Unexpected CE helper load result: $loaded"
    }
}

function Format-Float([double]$Value) {
    return $Value.ToString("R", [System.Globalization.CultureInfo]::InvariantCulture)
}

function Get-CurrentSnapshot {
    return Invoke-ReaderJson -Arguments @('--readerbridge-snapshot', '--json')
}

function Start-CeExactFloatScan {
    param(
        [Parameter(Mandatory = $true)]
        [double]$Value
    )

    return Invoke-CeNumeric -Code "return RiftReaderFloatScan.startExactFloat('rift_x64', ${Value})"
}

function Next-CeExactFloatScan {
    param(
        [Parameter(Mandatory = $true)]
        [double]$Value
    )

    return Invoke-CeNumeric -Code "return RiftReaderFloatScan.nextExactFloat(${Value})"
}

function Get-CeAddresses {
    param(
        [int]$Count
    )

    $addresses = New-Object System.Collections.Generic.HashSet[string]([System.StringComparer]::OrdinalIgnoreCase)

    $limit = [Math]::Min($Count, $MaxCeAddresses)
    for ($index = 0; $index -lt $limit; $index++) {
        $addressValue = Invoke-CeNumeric -Code "return RiftReaderFloatScan.getAddress(${index})"
        if ($addressValue -gt 0) {
            [void]$addresses.Add(('0x{0:X}' -f $addressValue))
        }
    }

    return $addresses
}

function Get-PlayerSignatureScan {
    return Invoke-ReaderJson -Arguments @(
        '--process-name', 'rift_x64',
        '--scan-readerbridge-player-signature',
        '--scan-context', $ScanContextBytes.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '--max-hits', $MaxScanHits.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '--json'
    )
}

Write-Host "[SmartFamily] Loading Cheat Engine float scan helper..." -ForegroundColor Cyan
Load-CeHelper

Write-Host "[SmartFamily] Refreshing baseline ReaderBridge export..." -ForegroundColor Cyan
& $refreshScript -NoReader

$baselineSnapshot = Get-CurrentSnapshot
$baselinePlayer = $baselineSnapshot.Current.Player
$baselineX = [double]$baselinePlayer.Coord.X
$baselineY = [double]$baselinePlayer.Coord.Y
$baselineZ = [double]$baselinePlayer.Coord.Z

Write-Host "[SmartFamily] Baseline coords: $(Format-Float $baselineX), $(Format-Float $baselineY), $(Format-Float $baselineZ)" -ForegroundColor DarkGray
Write-Host "[SmartFamily] Starting CE exact-float scan for baseline X..." -ForegroundColor Cyan
$baselineCeCount = Start-CeExactFloatScan -Value $baselineX
Write-Host "[SmartFamily] Baseline CE hit count: $baselineCeCount" -ForegroundColor DarkGray

Write-Host "[SmartFamily] Applying movement stimulus via native Rift key helper..." -ForegroundColor Cyan
& $postKeyScript -Key $MovementKey -HoldMilliseconds $MovementHoldMilliseconds

Write-Host "[SmartFamily] Refreshing post-move ReaderBridge export..." -ForegroundColor Cyan
& $refreshScript -NoReader

$movedSnapshot = Get-CurrentSnapshot
$movedPlayer = $movedSnapshot.Current.Player
$movedX = [double]$movedPlayer.Coord.X
$movedY = [double]$movedPlayer.Coord.Y
$movedZ = [double]$movedPlayer.Coord.Z

$deltaX = $movedX - $baselineX
$deltaY = $movedY - $baselineY
$deltaZ = $movedZ - $baselineZ

if ([Math]::Abs($deltaX) -lt 0.01 -and [Math]::Abs($deltaY) -lt 0.01 -and [Math]::Abs($deltaZ) -lt 0.01) {
    throw "Movement stimulus did not change player coordinates enough to validate candidate families."
}

Write-Host "[SmartFamily] Post-move coords: $(Format-Float $movedX), $(Format-Float $movedY), $(Format-Float $movedZ)" -ForegroundColor DarkGray
Write-Host "[SmartFamily] Coordinate delta: dX=$(Format-Float $deltaX), dY=$(Format-Float $deltaY), dZ=$(Format-Float $deltaZ)" -ForegroundColor DarkGray

Write-Host "[SmartFamily] Running CE next exact-float scan for moved X..." -ForegroundColor Cyan
$movedCeCount = Next-CeExactFloatScan -Value $movedX
Write-Host "[SmartFamily] Post-move CE hit count: $movedCeCount" -ForegroundColor DarkGray

$ceAddresses = Get-CeAddresses -Count ([int]$movedCeCount)
Write-Host "[SmartFamily] Retrieved $($ceAddresses.Count) CE address hits for the moved X value." -ForegroundColor DarkGray

Write-Host "[SmartFamily] Running fresh player-signature scan..." -ForegroundColor Cyan
$signatureScan = Get-PlayerSignatureScan

$familyResults = foreach ($family in $signatureScan.Families) {
    $confirmedSampleAddresses = New-Object System.Collections.Generic.List[string]
    foreach ($sampleAddress in $family.SampleAddresses) {
        if ($ceAddresses.Contains($sampleAddress)) {
            [void]$confirmedSampleAddresses.Add($sampleAddress)
        }
    }

    [pscustomobject]@{
        FamilyId = $family.FamilyId
        Signature = $family.Signature
        Notes = $family.Notes
        BestScore = [int]$family.BestScore
        HitCount = [int]$family.HitCount
        RepresentativeAddressHex = $family.RepresentativeAddressHex
        SampleAddresses = @($family.SampleAddresses)
        CeConfirmedSampleCount = $confirmedSampleAddresses.Count
        CeConfirmedSampleAddresses = @($confirmedSampleAddresses)
    }
}

$rankedFamilies = $familyResults |
    Sort-Object -Property @{ Expression = 'CeConfirmedSampleCount'; Descending = $true }, @{ Expression = 'BestScore'; Descending = $true }, @{ Expression = 'HitCount'; Descending = $true }, @{ Expression = 'RepresentativeAddressHex'; Descending = $false }

$ceConfirmedFamilies = @($rankedFamilies | Where-Object { $_.CeConfirmedSampleCount -gt 0 })
$winner = $rankedFamilies | Select-Object -First 1
$preCeTopFamily = ($signatureScan.Families | Sort-Object -Property @{ Expression = 'BestScore'; Descending = $true }, @{ Expression = 'HitCount'; Descending = $true }, @{ Expression = 'RepresentativeAddressHex'; Descending = $false } | Select-Object -First 1)

$result = [pscustomobject]@{
    Mode = 'ce-smart-player-family'
    MovementKey = $MovementKey
    MovementHoldMilliseconds = $MovementHoldMilliseconds
    BaselineCoords = [pscustomobject]@{ X = $baselineX; Y = $baselineY; Z = $baselineZ }
    MovedCoords = [pscustomobject]@{ X = $movedX; Y = $movedY; Z = $movedZ }
    Delta = [pscustomobject]@{ X = $deltaX; Y = $deltaY; Z = $deltaZ }
    BaselineCeHitCount = [int]$baselineCeCount
    MovedCeHitCount = [int]$movedCeCount
    RetrievedCeAddressCount = $ceAddresses.Count
    CandidateFamilyCount = @($signatureScan.Families).Count
    CeConfirmedFamilyCount = $ceConfirmedFamilies.Count
    PreCeTopFamilyId = $preCeTopFamily.FamilyId
    WinnerFamilyId = $winner.FamilyId
    Winner = $winner
    Families = @($rankedFamilies)
}

Write-Host ""
Write-Host "[SmartFamily] Candidate families before CE narrowing: $($result.CandidateFamilyCount)" -ForegroundColor Yellow
Write-Host "[SmartFamily] Families with direct CE-confirmed moved-X sample hits: $($result.CeConfirmedFamilyCount)" -ForegroundColor Yellow
Write-Host "[SmartFamily] Pre-CE top family: $($result.PreCeTopFamilyId)" -ForegroundColor Yellow
Write-Host "[SmartFamily] CE-assisted winner: $($result.WinnerFamilyId)" -ForegroundColor Green
Write-Host ""

foreach ($family in $rankedFamilies) {
    $confirmedText = if ($family.CeConfirmedSampleCount -gt 0) { $family.CeConfirmedSampleAddresses -join ', ' } else { 'none' }
    Write-Host ("[SmartFamily] {0} | CE matches={1} | hits={2} | score={3} | rep={4} | {5}" -f $family.FamilyId, $family.CeConfirmedSampleCount, $family.HitCount, $family.BestScore, $family.RepresentativeAddressHex, $family.Notes)
    Write-Host ("              CE sample addresses: {0}" -f $confirmedText) -ForegroundColor DarkGray
}

Write-Host ""
Write-Output ($result | ConvertTo-Json -Depth 8)
