[CmdletBinding()]
param(
    [switch]$Json,
    [string]$ProcessName = 'rift_x64',
    [string]$CandidateScreenFile = (Join-Path $PSScriptRoot 'captures\actor-orientation-candidate-screen.json'),
    [string]$OutputFile = (Join-Path $PSScriptRoot 'captures\actor-yaw-candidate-test.json'),
    [int]$TopCount = 4,
    [string]$StimulusKey = 'Right',
    [int]$HoldMilliseconds = 700,
    [int]$WaitMilliseconds = 250,
    [double]$MinYawResponseDegrees = 1.0,
    [double]$MaxCoordDrift = 0.35
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$postKeyScript = Join-Path $PSScriptRoot 'post-rift-key.ps1'
$resolvedCandidateScreenFile = [System.IO.Path]::GetFullPath($CandidateScreenFile)
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

function Parse-HexUInt64 {
    param([Parameter(Mandatory = $true)][string]$Value)

    $normalized = $Value.Trim()
    if ($normalized.StartsWith('0x', [System.StringComparison]::OrdinalIgnoreCase)) {
        $normalized = $normalized.Substring(2)
    }

    return [UInt64]::Parse($normalized, [System.Globalization.NumberStyles]::HexNumber, [System.Globalization.CultureInfo]::InvariantCulture)
}

function Convert-HexToByteArray {
    param([Parameter(Mandatory = $true)][string]$Hex)

    $normalized = ($Hex -replace '\s+', '').Trim()
    $bytes = New-Object byte[] ($normalized.Length / 2)
    for ($index = 0; $index -lt $bytes.Length; $index++) {
        $bytes[$index] = [Convert]::ToByte($normalized.Substring($index * 2, 2), 16)
    }

    return $bytes
}

function Read-SingleAt {
    param(
        [Parameter(Mandatory = $true)][byte[]]$Bytes,
        [Parameter(Mandatory = $true)][int]$Offset
    )

    if (($Offset + 4) -gt $Bytes.Length) {
        return $null
    }

    $value = [BitConverter]::ToSingle($Bytes, $Offset)
    if ([single]::IsNaN($value) -or [single]::IsInfinity($value)) {
        return $null
    }

    return [double]$value
}

function Read-TripletAt {
    param(
        [Parameter(Mandatory = $true)][byte[]]$Bytes,
        [Parameter(Mandatory = $true)][int]$Offset
    )

    return [pscustomobject]@{
        X = Read-SingleAt -Bytes $Bytes -Offset $Offset
        Y = Read-SingleAt -Bytes $Bytes -Offset ($Offset + 4)
        Z = Read-SingleAt -Bytes $Bytes -Offset ($Offset + 8)
    }
}

function Normalize-AngleRadians {
    param([double]$Radians)

    $normalized = $Radians
    while ($normalized -gt [Math]::PI) {
        $normalized -= (2.0 * [Math]::PI)
    }

    while ($normalized -lt -[Math]::PI) {
        $normalized += (2.0 * [Math]::PI)
    }

    return $normalized
}

function Convert-RadiansToDegrees {
    param([double]$Radians)
    return $Radians * 180.0 / [Math]::PI
}

function Get-VectorEstimate {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)]$Vector
    )

    if ($null -eq $Vector.X -or $null -eq $Vector.Y -or $null -eq $Vector.Z) {
        return [pscustomobject]@{
            Name = $Name
            Vector = $Vector
            YawRadians = $null
            YawDegrees = $null
            PitchRadians = $null
            PitchDegrees = $null
            Magnitude = $null
        }
    }

    $x = [double]$Vector.X
    $y = [double]$Vector.Y
    $z = [double]$Vector.Z
    $magnitude = [Math]::Sqrt(($x * $x) + ($y * $y) + ($z * $z))
    if ($magnitude -le [double]::Epsilon) {
        return [pscustomobject]@{
            Name = $Name
            Vector = $Vector
            YawRadians = $null
            YawDegrees = $null
            PitchRadians = $null
            PitchDegrees = $null
            Magnitude = $magnitude
        }
    }

    $yawRadians = [Math]::Atan2($z, $x)
    $pitchRadians = [Math]::Atan2($y, [Math]::Sqrt(($x * $x) + ($z * $z)))

    return [pscustomobject]@{
        Name = $Name
        Vector = $Vector
        YawRadians = $yawRadians
        YawDegrees = Convert-RadiansToDegrees -Radians $yawRadians
        PitchRadians = $pitchRadians
        PitchDegrees = Convert-RadiansToDegrees -Radians $pitchRadians
        Magnitude = $magnitude
    }
}

function Get-CoordDeltaMagnitude {
    param($BeforeCoord, $AfterCoord)

    if ($null -eq $BeforeCoord -or $null -eq $AfterCoord) {
        return $null
    }

    if ($null -eq $BeforeCoord.X -or $null -eq $BeforeCoord.Y -or $null -eq $BeforeCoord.Z) {
        return $null
    }

    if ($null -eq $AfterCoord.X -or $null -eq $AfterCoord.Y -or $null -eq $AfterCoord.Z) {
        return $null
    }

    $dx = [double]$AfterCoord.X - [double]$BeforeCoord.X
    $dy = [double]$AfterCoord.Y - [double]$BeforeCoord.Y
    $dz = [double]$AfterCoord.Z - [double]$BeforeCoord.Z
    return [Math]::Sqrt(($dx * $dx) + ($dy * $dy) + ($dz * $dz))
}

function Get-PlayerCurrent {
    return Invoke-ReaderJson -Arguments @(
        '--process-name', $ProcessName,
        '--read-player-current',
        '--json')
}

function Get-PlayerCoordSnapshot {
    param($PlayerCurrent)

    if ($null -eq $PlayerCurrent -or $null -eq $PlayerCurrent.Memory) {
        return $null
    }

    return [pscustomobject]@{
        X = if ($PlayerCurrent.Memory.PSObject.Properties['CoordX']) { [double]$PlayerCurrent.Memory.CoordX } else { $null }
        Y = if ($PlayerCurrent.Memory.PSObject.Properties['CoordY']) { [double]$PlayerCurrent.Memory.CoordY } else { $null }
        Z = if ($PlayerCurrent.Memory.PSObject.Properties['CoordZ']) { [double]$PlayerCurrent.Memory.CoordZ } else { $null }
    }
}

function Get-ComparableMagnitude {
    param($Value)

    if ($null -eq $Value) {
        return 0.0
    }

    return [Math]::Abs([double]$Value)
}

function Get-CandidateSnapshot {
    param(
        [Parameter(Mandatory = $true)][string]$AddressHex,
        [Parameter(Mandatory = $true)][string]$ForwardOffsetHex
    )

    $address = Parse-HexUInt64 -Value $AddressHex
    $forwardOffset = [int](Parse-HexUInt64 -Value $ForwardOffsetHex)

    $memoryRead = Invoke-ReaderJson -Arguments @(
        '--process-name', $ProcessName,
        '--address', ('0x{0:X}' -f $address),
        '--length', '384',
        '--json')

    $bytes = Convert-HexToByteArray -Hex ([string]$memoryRead.BytesHex)
    $forward = Read-TripletAt -Bytes $bytes -Offset $forwardOffset

    $upOffset = $forwardOffset + 0x0C
    $rightOffset = $forwardOffset + 0x18

    return [pscustomobject]@{
        Address = ('0x{0:X}' -f $address)
        ForwardOffset = ('0x{0:X}' -f $forwardOffset)
        Forward = $forward
        Up = Read-TripletAt -Bytes $bytes -Offset $upOffset
        Right = Read-TripletAt -Bytes $bytes -Offset $rightOffset
        Estimate = Get-VectorEstimate -Name ('Basis@0x{0:X}' -f $forwardOffset) -Vector $forward
    }
}

function Try-GetCandidateSnapshot {
    param(
        [Parameter(Mandatory = $true)][string]$AddressHex,
        [Parameter(Mandatory = $true)][string]$ForwardOffsetHex
    )

    try {
        return [pscustomobject]@{
            Success = $true
            Snapshot = Get-CandidateSnapshot -AddressHex $AddressHex -ForwardOffsetHex $ForwardOffsetHex
            Error = $null
        }
    }
    catch {
        return [pscustomobject]@{
            Success = $false
            Snapshot = $null
            Error = $_.Exception.Message
        }
    }
}

if (-not (Test-Path -LiteralPath $resolvedCandidateScreenFile)) {
    throw "Candidate screen file not found: $resolvedCandidateScreenFile"
}

$screen = Get-Content -LiteralPath $resolvedCandidateScreenFile -Raw | ConvertFrom-Json -Depth 40
$candidateRows = @($screen.Results | Select-Object -First $TopCount)
if ($candidateRows.Count -le 0) {
    throw "Candidate screen file did not contain any candidate rows."
}

$beforePlayer = Get-PlayerCurrent
$beforePlayerCoord = Get-PlayerCoordSnapshot -PlayerCurrent $beforePlayer

$beforeSnapshots = @{}
foreach ($row in $candidateRows) {
    $beforeSnapshots[$row.SourceAddress] = Try-GetCandidateSnapshot -AddressHex ([string]$row.SourceAddress) -ForwardOffsetHex ([string]$row.BasisForwardOffset)
}

& $postKeyScript -Key $StimulusKey -HoldMilliseconds $HoldMilliseconds *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Stimulus key '$StimulusKey' failed."
}

Start-Sleep -Milliseconds $WaitMilliseconds

$afterPlayer = Get-PlayerCurrent
$afterPlayerCoord = Get-PlayerCoordSnapshot -PlayerCurrent $afterPlayer

$results = New-Object System.Collections.Generic.List[object]
foreach ($row in $candidateRows) {
    $address = [string]$row.SourceAddress
    $beforeSnapshotResult = $beforeSnapshots[$address]
    $afterSnapshotResult = Try-GetCandidateSnapshot -AddressHex $address -ForwardOffsetHex ([string]$row.BasisForwardOffset)

    $beforeSnapshot = $beforeSnapshotResult.Snapshot
    $afterSnapshot = $afterSnapshotResult.Snapshot

    $yawDeltaDegrees = $null
    if ($beforeSnapshotResult.Success -and $afterSnapshotResult.Success -and $null -ne $beforeSnapshot.Estimate.YawRadians -and $null -ne $afterSnapshot.Estimate.YawRadians) {
        $yawDeltaDegrees = Convert-RadiansToDegrees -Radians (Normalize-AngleRadians -Radians ([double]$afterSnapshot.Estimate.YawRadians - [double]$beforeSnapshot.Estimate.YawRadians))
    }

    $pitchDeltaDegrees = $null
    if ($beforeSnapshotResult.Success -and $afterSnapshotResult.Success -and $null -ne $beforeSnapshot.Estimate.PitchRadians -and $null -ne $afterSnapshot.Estimate.PitchRadians) {
        $pitchDeltaDegrees = Convert-RadiansToDegrees -Radians (Normalize-AngleRadians -Radians ([double]$afterSnapshot.Estimate.PitchRadians - [double]$beforeSnapshot.Estimate.PitchRadians))
    }

    $coordDeltaMagnitude = Get-CoordDeltaMagnitude -BeforeCoord $beforePlayerCoord -AfterCoord $afterPlayerCoord
    $candidateResponsive = ($null -ne $yawDeltaDegrees) -and ([Math]::Abs([double]$yawDeltaDegrees) -ge $MinYawResponseDegrees)
    $playerStayedMostlyStill = ($null -ne $coordDeltaMagnitude) -and ([double]$coordDeltaMagnitude -le $MaxCoordDrift)
    $truthLike = $candidateResponsive -and $playerStayedMostlyStill

    $results.Add([pscustomobject]@{
        Rank = $row.Rank
        SourceAddress = $address
        BasisForwardOffset = [string]$row.BasisForwardOffset
        DiscoveryMode = [string]$row.DiscoveryMode
        ParentAddress = [string]$row.ParentAddress
        RootAddress = [string]$row.RootAddress
        SearchScore = $row.SearchScore
        BeforeReadSucceeded = $beforeSnapshotResult.Success
        BeforeReadError = $beforeSnapshotResult.Error
        AfterReadSucceeded = $afterSnapshotResult.Success
        AfterReadError = $afterSnapshotResult.Error
        Before = $beforeSnapshot
        After = $afterSnapshot
        YawDeltaDegrees = $yawDeltaDegrees
        PitchDeltaDegrees = $pitchDeltaDegrees
        PlayerCoordDeltaMagnitude = $coordDeltaMagnitude
        CandidateResponsive = $candidateResponsive
        PlayerStayedMostlyStill = $playerStayedMostlyStill
        TruthLike = $truthLike
    }) | Out-Null
}

$bestTruthLike = $results |
    Sort-Object @{ Expression = { if ($_.TruthLike) { 0 } else { 1 } } }, @{ Expression = { -(Get-ComparableMagnitude -Value $_.YawDeltaDegrees) } } |
    Select-Object -First 1

$truthLikeResults = @($results.ToArray() | Where-Object { $_.TruthLike })

$document = [ordered]@{}
$document.Mode = 'actor-yaw-candidate-test'
$document.GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
$document.CandidateScreenFile = $resolvedCandidateScreenFile
$document.ProcessName = $ProcessName
$document.StimulusKey = $StimulusKey
$document.HoldMilliseconds = $HoldMilliseconds
$document.WaitMilliseconds = $WaitMilliseconds
$document.MinYawResponseDegrees = $MinYawResponseDegrees
$document.MaxCoordDrift = $MaxCoordDrift
$document.PlayerBefore = $beforePlayer
$document.PlayerAfter = $afterPlayer
$document.CandidateCount = $results.Count
$document.TruthLikeCandidateCount = $truthLikeResults.Count
$document.BestTruthLikeCandidate = $bestTruthLike
$document.Results = $results.ToArray()
$document.Notes = @(
    'Read-only candidate validation using direct memory reads plus a controlled turn key stimulus.',
    'No debugger attach, breakpoint tracing, or debug scanning was used.',
    'A candidate is marked truth-like when its yaw changes beyond the configured threshold while player coordinate drift stays under the configured limit.')

$outputDirectory = Split-Path -Parent $resolvedOutputFile
if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

$jsonText = $document | ConvertTo-Json -Depth 40
Set-Content -LiteralPath $resolvedOutputFile -Value $jsonText -Encoding UTF8

if ($Json) {
    Write-Output $jsonText
    return
}

Write-Host "Actor yaw candidate test"
Write-Host "Output file:              $resolvedOutputFile"
Write-Host "Stimulus key:             $StimulusKey"
Write-Host "Candidates tested:        $($results.Count)"
Write-Host "Truth-like candidates:    $(@($results | Where-Object { $_.TruthLike }).Count)"
foreach ($result in $results) {
    Write-Host ("  [{0}] {1} @ {2} | yaw {3:N3} deg | coord {4:N6} | responsive={5} | truthLike={6}" -f `
        $result.Rank,
        $result.SourceAddress,
        $result.BasisForwardOffset,
        (if ($null -eq $result.YawDeltaDegrees) { 0.0 } else { [double]$result.YawDeltaDegrees }),
        (if ($null -eq $result.PlayerCoordDeltaMagnitude) { 0.0 } else { [double]$result.PlayerCoordDeltaMagnitude }),
        $result.CandidateResponsive,
        $result.TruthLike)
}
