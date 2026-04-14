[CmdletBinding()]
param(
    [string]$MovementKey = "w",
    [string[]]$FallbackMovementKeys = @("d", "a", "s"),
    [int]$MovementHoldMilliseconds = 500,
    [int]$MaxScanHits = 12,
    [int]$ScanContextBytes = 192,
    [int]$MaxCeAddresses = 256,
    [string]$OutputFile = (Join-Path $PSScriptRoot 'captures\ce-smart-player-family.json'),
    [int]$CoordScale = 1000,
    [int]$CoordToleranceUnits = 5,
    [string[]]$AxisPriority = @("X", "Z")
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$ceExecScript = Join-Path $PSScriptRoot 'cheatengine-exec.ps1'
$ceFloatScanLua = Join-Path $PSScriptRoot 'ce-float-scan.lua'
$refreshScript = Join-Path $PSScriptRoot 'refresh-readerbridge-export.ps1'
$sendKeyScript = Join-Path $PSScriptRoot 'send-rift-key.ps1'
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

    return ($output -join [Environment]::NewLine) | ConvertFrom-Json -Depth 20
}

function Invoke-CeNumeric {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Code,

        [switch]$Signed
    )

    $result = & $ceExecScript -Code $Code

    $valueText = [string]($result | Select-Object -Last 1)
    if ($Signed) {
        $unsignedValue = [UInt64]::Parse($valueText, [System.Globalization.CultureInfo]::InvariantCulture)
        return [BitConverter]::ToInt64([BitConverter]::GetBytes($unsignedValue), 0)
    }

    return [UInt64]::Parse($valueText, [System.Globalization.CultureInfo]::InvariantCulture)
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

function Next-CeDirectionalFloatScan {
    param(
        [Parameter(Mandatory = $true)]
        [double]$Delta
    )

    if ($Delta -gt 0.01) {
        return [pscustomobject]@{
            Mode = 'increased'
            Count = (Invoke-CeNumeric -Code "return RiftReaderFloatScan.nextIncreasedFloat()")
        }
    }

    if ($Delta -lt -0.01) {
        return [pscustomobject]@{
            Mode = 'decreased'
            Count = (Invoke-CeNumeric -Code "return RiftReaderFloatScan.nextDecreasedFloat()")
        }
    }

    return [pscustomobject]@{
        Mode = 'changed'
        Count = (Invoke-CeNumeric -Code "return RiftReaderFloatScan.nextChangedFloat()")
    }
}

function Get-CeAddresses {
    param(
        [int]$Count
    )

    if ($Count -le 0) {
        return @()
    }

    $addresses = New-Object System.Collections.Generic.HashSet[string]([System.StringComparer]::OrdinalIgnoreCase)

    $limit = [Math]::Min($Count, $MaxCeAddresses)
    for ($index = 0; $index -lt $limit; $index++) {
        $addressValue = Invoke-CeNumeric -Code "return RiftReaderFloatScan.getAddress(${index})"
        if ($addressValue -gt 0) {
            [void]$addresses.Add(('0x{0:X}' -f $addressValue))
        }
    }

    return @($addresses)
}

function Get-CeScaledFloatAt {
    param(
        [Parameter(Mandatory = $true)]
        [string]$AddressHex,

        [Parameter(Mandatory = $true)]
        [int]$Offset,

        [Parameter(Mandatory = $true)]
        [int]$Scale
    )

    $scaledValue = Invoke-CeNumeric -Code "return RiftReaderFloatScan.readScaledFloatAt(${AddressHex}, ${Offset}, ${Scale})" -Signed
    if ($scaledValue -lt [int]::MinValue -or $scaledValue -gt [int]::MaxValue) {
        return $null
    }

    return [int]$scaledValue
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

function Get-CoordValue {
    param(
        [Parameter(Mandatory = $true)]
        [pscustomobject]$Coord,

        [Parameter(Mandatory = $true)]
        [string]$Axis
    )

    switch ($Axis.ToUpperInvariant()) {
        'X' { return [double]$Coord.X }
        'Y' { return [double]$Coord.Y }
        'Z' { return [double]$Coord.Z }
        default { throw "Unsupported axis '$Axis'." }
    }
}

function Get-AxisBaseOffset {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Axis
    )

    switch ($Axis.ToUpperInvariant()) {
        'X' { return 0 }
        'Y' { return 4 }
        'Z' { return 8 }
        default { throw "Unsupported axis '$Axis'." }
    }
}

function Parse-HexAddress {
    param(
        [Parameter(Mandatory = $true)]
        [string]$AddressHex
    )

    $normalized = $AddressHex
    if ($normalized.StartsWith('0x', [System.StringComparison]::OrdinalIgnoreCase)) {
        $normalized = $normalized.Substring(2)
    }

    return [UInt64]::Parse($normalized, [System.Globalization.NumberStyles]::HexNumber, [System.Globalization.CultureInfo]::InvariantCulture)
}

function Format-HexAddress {
    param(
        [Parameter(Mandatory = $true)]
        [UInt64]$Address
    )

    return ('0x{0:X}' -f $Address)
}

function Get-MovementKeySequence {
    param(
        [string]$PrimaryKey,
        [string[]]$FallbackKeys
    )

    $seen = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
    $sequence = New-Object System.Collections.Generic.List[string]

    foreach ($key in @($PrimaryKey) + @($FallbackKeys)) {
        $normalizedKey = [string]$key
        if ([string]::IsNullOrWhiteSpace($normalizedKey)) {
            continue
        }

        $normalizedKey = $normalizedKey.Trim()
        if ($seen.Add($normalizedKey)) {
            $sequence.Add($normalizedKey) | Out-Null
        }
    }

    return @($sequence)
}

function Get-TripletConfirmedBaseAddresses {
    param(
        [AllowEmptyCollection()]
        [string[]]$CeAddresses,

        [Parameter(Mandatory = $true)]
        [string]$Axis,

        [Parameter(Mandatory = $true)]
        [double]$ExpectedX,

        [Parameter(Mandatory = $true)]
        [double]$ExpectedY,

        [Parameter(Mandatory = $true)]
        [double]$ExpectedZ
    )

    if ($null -eq $CeAddresses -or $CeAddresses.Count -eq 0) {
        return @()
    }

    $expectedXScaled = [int][Math]::Round($ExpectedX * $CoordScale, [MidpointRounding]::AwayFromZero)
    $expectedYScaled = [int][Math]::Round($ExpectedY * $CoordScale, [MidpointRounding]::AwayFromZero)
    $expectedZScaled = [int][Math]::Round($ExpectedZ * $CoordScale, [MidpointRounding]::AwayFromZero)
    $axisOffset = [UInt64](Get-AxisBaseOffset -Axis $Axis)

    $baseAddresses = New-Object System.Collections.Generic.HashSet[string]([System.StringComparer]::OrdinalIgnoreCase)

    foreach ($addressHex in $CeAddresses) {
        if ([string]::IsNullOrWhiteSpace($addressHex)) {
            continue
        }

        $rawAddress = Parse-HexAddress -AddressHex $addressHex
        if ($rawAddress -lt $axisOffset) {
            continue
        }

        $baseAddressHex = Format-HexAddress -Address ($rawAddress - $axisOffset)
        $xScaled = Get-CeScaledFloatAt -AddressHex $baseAddressHex -Offset 0 -Scale $CoordScale
        $yScaled = Get-CeScaledFloatAt -AddressHex $baseAddressHex -Offset 4 -Scale $CoordScale
        $zScaled = Get-CeScaledFloatAt -AddressHex $baseAddressHex -Offset 8 -Scale $CoordScale

        if ($null -eq $xScaled -or $null -eq $yScaled -or $null -eq $zScaled) {
            continue
        }

        if ([Math]::Abs($xScaled - $expectedXScaled) -le $CoordToleranceUnits -and
            [Math]::Abs($yScaled - $expectedYScaled) -le $CoordToleranceUnits -and
            [Math]::Abs($zScaled - $expectedZScaled) -le $CoordToleranceUnits) {
            [void]$baseAddresses.Add($baseAddressHex)
        }
    }

    return @($baseAddresses)
}

Write-Host "[SmartFamily] Loading Cheat Engine float scan helper..." -ForegroundColor Cyan
Load-CeHelper

$attemptResults = New-Object System.Collections.Generic.List[object]
$movementKeySequence = @(Get-MovementKeySequence -PrimaryKey $MovementKey -FallbackKeys $FallbackMovementKeys)

foreach ($axis in $AxisPriority) {
    $normalizedAxis = $axis.ToUpperInvariant()
    Write-Host "[SmartFamily] Refreshing baseline ReaderBridge export for axis $normalizedAxis..." -ForegroundColor Cyan
    & $refreshScript -NoReader

    $baselineSnapshot = Get-CurrentSnapshot
    $baselinePlayer = $baselineSnapshot.Current.Player
    $baselineX = [double]$baselinePlayer.Coord.X
    $baselineY = [double]$baselinePlayer.Coord.Y
    $baselineZ = [double]$baselinePlayer.Coord.Z
    $baselineAxisValue = Get-CoordValue -Coord $baselinePlayer.Coord -Axis $normalizedAxis

    Write-Host "[SmartFamily] Baseline coords: $(Format-Float $baselineX), $(Format-Float $baselineY), $(Format-Float $baselineZ)" -ForegroundColor DarkGray
    Write-Host "[SmartFamily] Starting CE exact-float scan for baseline $normalizedAxis..." -ForegroundColor Cyan
    $baselineCeCount = Start-CeExactFloatScan -Value $baselineAxisValue
    Write-Host "[SmartFamily] Baseline CE hit count for axis $normalizedAxis`: $baselineCeCount" -ForegroundColor DarkGray

    $stimulusAttempts = New-Object System.Collections.Generic.List[object]
    $movedSnapshot = $null
    $movedPlayer = $null
    $movedX = $baselineX
    $movedY = $baselineY
    $movedZ = $baselineZ
    $movedAxisValue = $baselineAxisValue
    $deltaX = 0.0
    $deltaY = 0.0
    $deltaZ = 0.0
    $selectedStimulusKey = $null
    $motionObserved = $false

    foreach ($movementStimulusKey in $movementKeySequence) {
        Write-Host "[SmartFamily] Applying movement stimulus key '$movementStimulusKey' via native Rift key helper..." -ForegroundColor Cyan
        & $sendKeyScript -ProcessName 'rift_x64' -Key $movementStimulusKey -HoldMilliseconds $MovementHoldMilliseconds -NoRefocus

        Write-Host "[SmartFamily] Refreshing post-move ReaderBridge export for axis $normalizedAxis..." -ForegroundColor Cyan
        & $refreshScript -NoReader

        $candidateSnapshot = Get-CurrentSnapshot
        $candidatePlayer = $candidateSnapshot.Current.Player
        $candidateX = [double]$candidatePlayer.Coord.X
        $candidateY = [double]$candidatePlayer.Coord.Y
        $candidateZ = [double]$candidatePlayer.Coord.Z
        $candidateAxisValue = Get-CoordValue -Coord $candidatePlayer.Coord -Axis $normalizedAxis

        $candidateDeltaX = $candidateX - $baselineX
        $candidateDeltaY = $candidateY - $baselineY
        $candidateDeltaZ = $candidateZ - $baselineZ
        $candidateMotionObserved = [Math]::Abs($candidateDeltaX) -ge 0.01 -or [Math]::Abs($candidateDeltaY) -ge 0.01 -or [Math]::Abs($candidateDeltaZ) -ge 0.01

        $stimulusAttempts.Add([pscustomobject]@{
                Key = $movementStimulusKey
                MovedCoords = [pscustomobject]@{ X = $candidateX; Y = $candidateY; Z = $candidateZ }
                Delta = [pscustomobject]@{ X = $candidateDeltaX; Y = $candidateDeltaY; Z = $candidateDeltaZ }
                MotionObserved = $candidateMotionObserved
            }) | Out-Null

        $movedSnapshot = $candidateSnapshot
        $movedPlayer = $candidatePlayer
        $movedX = $candidateX
        $movedY = $candidateY
        $movedZ = $candidateZ
        $movedAxisValue = $candidateAxisValue
        $deltaX = $candidateDeltaX
        $deltaY = $candidateDeltaY
        $deltaZ = $candidateDeltaZ

        if ($candidateMotionObserved) {
            $motionObserved = $true
            $selectedStimulusKey = $movementStimulusKey
            break
        }

        Write-Warning ("Movement stimulus key '{0}' did not change player coordinates enough; trying the next configured key." -f $movementStimulusKey)
    }

    if (-not $motionObserved) {
        $attemptResults.Add([pscustomobject]@{
                Axis = $normalizedAxis
                StimulusKey = $null
                MotionObserved = $false
                BaselineCoords = [pscustomobject]@{ X = $baselineX; Y = $baselineY; Z = $baselineZ }
                MovedCoords = [pscustomobject]@{ X = $movedX; Y = $movedY; Z = $movedZ }
                Delta = [pscustomobject]@{ X = $deltaX; Y = $deltaY; Z = $deltaZ }
                BaselineCeHitCount = [int]$baselineCeCount
                NextScanMode = $null
                MovedCeHitCount = 0
                RetrievedCeAddressCount = 0
                RetrievedCeAddresses = @()
                TripletConfirmedAddressCount = 0
                TripletConfirmedAddresses = @()
                StimulusAttempts = @($stimulusAttempts.ToArray())
            }) | Out-Null

        continue
    }

    Write-Host "[SmartFamily] Post-move coords: $(Format-Float $movedX), $(Format-Float $movedY), $(Format-Float $movedZ)" -ForegroundColor DarkGray
    Write-Host "[SmartFamily] Coordinate delta: dX=$(Format-Float $deltaX), dY=$(Format-Float $deltaY), dZ=$(Format-Float $deltaZ)" -ForegroundColor DarkGray

    Write-Host "[SmartFamily] Running CE directional next-scan for axis $normalizedAxis..." -ForegroundColor Cyan
    $nextScan = Next-CeDirectionalFloatScan -Delta (Get-CoordValue -Coord ([pscustomobject]@{ X = $deltaX; Y = $deltaY; Z = $deltaZ }) -Axis $normalizedAxis)
    $movedCeCount = [int]$nextScan.Count
    Write-Host "[SmartFamily] Post-move CE $($nextScan.Mode) hit count for axis $normalizedAxis`: $movedCeCount" -ForegroundColor DarkGray

    $ceAddresses = @(Get-CeAddresses -Count ([int]$movedCeCount))
    $tripletBaseAddresses = @(Get-TripletConfirmedBaseAddresses -CeAddresses $ceAddresses -Axis $normalizedAxis -ExpectedX $movedX -ExpectedY $movedY -ExpectedZ $movedZ)

    Write-Host "[SmartFamily] Retrieved $($ceAddresses.Count) CE address hits for axis $normalizedAxis." -ForegroundColor DarkGray
    Write-Host "[SmartFamily] Triplet-confirmed base address count after axis-$normalizedAxis normalization: $($tripletBaseAddresses.Count)" -ForegroundColor DarkGray

    $attempt = [pscustomobject]@{
        Axis = $normalizedAxis
        StimulusKey = $selectedStimulusKey
        MotionObserved = $true
        BaselineCoords = [pscustomobject]@{ X = $baselineX; Y = $baselineY; Z = $baselineZ }
        MovedCoords = [pscustomobject]@{ X = $movedX; Y = $movedY; Z = $movedZ }
        Delta = [pscustomobject]@{ X = $deltaX; Y = $deltaY; Z = $deltaZ }
        BaselineCeHitCount = [int]$baselineCeCount
        NextScanMode = [string]$nextScan.Mode
        MovedCeHitCount = [int]$movedCeCount
        RetrievedCeAddressCount = $ceAddresses.Count
        RetrievedCeAddresses = @($ceAddresses)
        TripletConfirmedAddressCount = $tripletBaseAddresses.Count
        TripletConfirmedAddresses = @($tripletBaseAddresses)
        StimulusAttempts = @($stimulusAttempts.ToArray())
    }

    $attemptResults.Add($attempt)

    if ($tripletBaseAddresses.Count -gt 0) {
        break
    }
}

if ($attemptResults.Count -eq 0) {
    throw "No CE-assisted movement attempts were recorded."
}

$selectedAttempt = $attemptResults |
    Sort-Object -Property @{ Expression = { if ($_.MotionObserved) { 1 } else { 0 } }; Descending = $true }, @{ Expression = 'TripletConfirmedAddressCount'; Descending = $true }, @{ Expression = 'MovedCeHitCount'; Descending = $true }, @{ Expression = 'BaselineCeHitCount'; Descending = $true } |
    Select-Object -First 1

if (-not $selectedAttempt.MotionObserved) {
    $attemptSummary = $attemptResults | ForEach-Object {
        $stimulusSummary = @($_.StimulusAttempts | ForEach-Object {
                "{0}:{1}" -f $_.Key, $(if ($_.MotionObserved) { 'moved' } else { 'static' })
            }) -join ', '
        "{0} [{1}]" -f $_.Axis, $stimulusSummary
    }

    throw ("No configured movement stimulus produced a coordinate delta across the CE narrowing attempts. {0}" -f ($attemptSummary -join '; '))
}

$baselineX = [double]$selectedAttempt.BaselineCoords.X
$baselineY = [double]$selectedAttempt.BaselineCoords.Y
$baselineZ = [double]$selectedAttempt.BaselineCoords.Z
$movedX = [double]$selectedAttempt.MovedCoords.X
$movedY = [double]$selectedAttempt.MovedCoords.Y
$movedZ = [double]$selectedAttempt.MovedCoords.Z
$deltaX = [double]$selectedAttempt.Delta.X
$deltaY = [double]$selectedAttempt.Delta.Y
$deltaZ = [double]$selectedAttempt.Delta.Z
$baselineCeCount = [int]$selectedAttempt.BaselineCeHitCount
$movedCeCount = [int]$selectedAttempt.MovedCeHitCount
$ceAddresses = @($selectedAttempt.RetrievedCeAddresses)
$tripletAddresses = New-Object System.Collections.Generic.HashSet[string]([System.StringComparer]::OrdinalIgnoreCase)
foreach ($tripletAddress in $selectedAttempt.TripletConfirmedAddresses) {
    [void]$tripletAddresses.Add([string]$tripletAddress)
}

Write-Host "[SmartFamily] Selected CE attempt axis: $($selectedAttempt.Axis)" -ForegroundColor Yellow
Write-Host "[SmartFamily] Selected attempt triplet-confirmed base address count: $($tripletAddresses.Count)" -ForegroundColor Yellow

Write-Host "[SmartFamily] Running fresh player-signature scan..." -ForegroundColor Cyan
$signatureScan = Get-PlayerSignatureScan

$familyResults = foreach ($family in $signatureScan.Families) {
    $confirmedSampleAddresses = New-Object System.Collections.Generic.List[string]
    foreach ($sampleAddress in $family.SampleAddresses) {
    if ($tripletAddresses.Contains($sampleAddress)) {
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
$rankedFamilyArray = @($rankedFamilies)
$tripletConfirmedAddressArray = @($tripletAddresses)
$attemptArray = $attemptResults.ToArray()

$result = [ordered]@{
    Mode = 'ce-smart-player-family'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    ProcessName = 'rift_x64'
    MovementKey = $MovementKey
    FallbackMovementKeys = @($FallbackMovementKeys)
    MovementKeySequence = @($movementKeySequence)
    MovementHoldMilliseconds = $MovementHoldMilliseconds
    SelectedAxis = $selectedAttempt.Axis
    SelectedStimulusKey = $selectedAttempt.StimulusKey
    AttemptCount = $attemptResults.Count
    BaselineCoords = [pscustomobject]@{ X = $baselineX; Y = $baselineY; Z = $baselineZ }
    MovedCoords = [pscustomobject]@{ X = $movedX; Y = $movedY; Z = $movedZ }
    Delta = [pscustomobject]@{ X = $deltaX; Y = $deltaY; Z = $deltaZ }
    BaselineCeHitCount = [int]$baselineCeCount
    NextScanMode = [string]$selectedAttempt.NextScanMode
    MovedCeHitCount = [int]$movedCeCount
    RetrievedCeAddressCount = $ceAddresses.Count
    TripletConfirmedAddressCount = $tripletAddresses.Count
    TripletConfirmedAddresses = $tripletConfirmedAddressArray
    Attempts = $attemptArray
    CandidateFamilyCount = @($signatureScan.Families).Count
    CeConfirmedFamilyCount = $ceConfirmedFamilies.Count
    PreCeTopFamilyId = $preCeTopFamily.FamilyId
    WinnerFamilyId = $winner.FamilyId
    Winner = $winner
    Families = $rankedFamilyArray
    ConfirmationFile = $resolvedOutputFile
}

Write-Host ""
Write-Host "[SmartFamily] Candidate families before CE narrowing: $($result['CandidateFamilyCount'])" -ForegroundColor Yellow
Write-Host "[SmartFamily] Families with direct CE-confirmed moved-axis sample hits: $($result['CeConfirmedFamilyCount'])" -ForegroundColor Yellow
Write-Host "[SmartFamily] Pre-CE top family: $($result['PreCeTopFamilyId'])" -ForegroundColor Yellow
Write-Host "[SmartFamily] CE-assisted winner: $($result['WinnerFamilyId'])" -ForegroundColor Green
Write-Host ""

foreach ($family in $rankedFamilies) {
    $confirmedText = if ($family.CeConfirmedSampleCount -gt 0) { $family.CeConfirmedSampleAddresses -join ', ' } else { 'none' }
    Write-Host ("[SmartFamily] {0} | CE matches={1} | hits={2} | score={3} | rep={4} | {5}" -f $family.FamilyId, $family.CeConfirmedSampleCount, $family.HitCount, $family.BestScore, $family.RepresentativeAddressHex, $family.Notes)
    Write-Host ("              CE sample addresses: {0}" -f $confirmedText) -ForegroundColor DarkGray
}

Write-Host ""
$json = $result | ConvertTo-Json -Depth 8
$outputDirectory = Split-Path -Parent $resolvedOutputFile
if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}
Set-Content -Path $resolvedOutputFile -Value $json -Encoding UTF8
Write-Host "[SmartFamily] Wrote CE confirmation file: $resolvedOutputFile" -ForegroundColor Cyan
Write-Host ""
Write-Output $json
