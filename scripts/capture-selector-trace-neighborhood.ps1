[CmdletBinding()]
param(
    [switch]$Json,
    [switch]$RefreshSelectorTrace,
    [int]$ReadLength = 512,
    [double]$CoordTolerance = 0.25,
    [double]$BasisAbsMax = 1.25,
    [double]$BasisMagnitudeMin = 0.70,
    [double]$BasisMagnitudeMax = 1.30,
    [int]$MaxCoordMatches = 32,
    [int]$MaxBasisMatches = 48,
    [string]$SelectorTraceFile = (Join-Path $PSScriptRoot 'captures\player-selector-owner-trace.json'),
    [string]$OutputFile = (Join-Path $PSScriptRoot 'captures\selector-trace-neighborhood.json')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$selectorTraceScript = Join-Path $PSScriptRoot 'trace-player-selector-owner.ps1'
$resolvedSelectorTraceFile = [System.IO.Path]::GetFullPath($SelectorTraceFile)
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

function Read-SingleAt {
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

function Convert-ToFiniteDouble {
    param($Value)

    if ($null -eq $Value) {
        return $null
    }

    $doubleValue = [double]$Value
    if ([double]::IsNaN($doubleValue) -or [double]::IsInfinity($doubleValue)) {
        return $null
    }

    return $doubleValue
}

function Test-PlausiblePointer {
    param(
        [Parameter(Mandatory = $true)]
        [UInt64]$Value
    )

    return ($Value -ge 0x0000010000000000UL) -and ($Value -le 0x00007FFFFFFFFFFFUL)
}

function Get-CoordTripletMatches {
    param(
        [Parameter(Mandatory = $true)]
        [byte[]]$Bytes,

        [Parameter(Mandatory = $true)]
        [double]$ExpectedX,

        [Parameter(Mandatory = $true)]
        [double]$ExpectedY,

        [Parameter(Mandatory = $true)]
        [double]$ExpectedZ
    )

    $matches = New-Object System.Collections.Generic.List[object]
    for ($offset = 0; ($offset + 12) -le $Bytes.Length; $offset += 4) {
        $x = Convert-ToFiniteDouble (Read-SingleAt -Bytes $Bytes -Offset $offset)
        $y = Convert-ToFiniteDouble (Read-SingleAt -Bytes $Bytes -Offset ($offset + 4))
        $z = Convert-ToFiniteDouble (Read-SingleAt -Bytes $Bytes -Offset ($offset + 8))
        if ($null -eq $x -or $null -eq $y -or $null -eq $z) {
            continue
        }

        $deltaX = [math]::Abs($x - $ExpectedX)
        $deltaY = [math]::Abs($y - $ExpectedY)
        $deltaZ = [math]::Abs($z - $ExpectedZ)
        if ($deltaX -le $CoordTolerance -and $deltaY -le $CoordTolerance -and $deltaZ -le $CoordTolerance) {
            $matches.Add([ordered]@{
                Offset = $offset
                OffsetHex = ('0x{0:X}' -f $offset)
                X = $x
                Y = $y
                Z = $z
                DeltaX = [math]::Round(($x - $ExpectedX), 6)
                DeltaY = [math]::Round(($y - $ExpectedY), 6)
                DeltaZ = [math]::Round(($z - $ExpectedZ), 6)
            }) | Out-Null
        }
    }

    return $matches
}

function Get-BasisTripletCandidates {
    param(
        [Parameter(Mandatory = $true)]
        [byte[]]$Bytes
    )

    $matches = New-Object System.Collections.Generic.List[object]
    for ($offset = 0; ($offset + 12) -le $Bytes.Length; $offset += 4) {
        $x = Convert-ToFiniteDouble (Read-SingleAt -Bytes $Bytes -Offset $offset)
        $y = Convert-ToFiniteDouble (Read-SingleAt -Bytes $Bytes -Offset ($offset + 4))
        $z = Convert-ToFiniteDouble (Read-SingleAt -Bytes $Bytes -Offset ($offset + 8))
        if ($null -eq $x -or $null -eq $y -or $null -eq $z) {
            continue
        }

        if ([math]::Abs($x) -gt $BasisAbsMax -or [math]::Abs($y) -gt $BasisAbsMax -or [math]::Abs($z) -gt $BasisAbsMax) {
            continue
        }

        $magnitude = [math]::Sqrt(($x * $x) + ($y * $y) + ($z * $z))
        if ($magnitude -lt $BasisMagnitudeMin -or $magnitude -gt $BasisMagnitudeMax) {
            continue
        }

        $matches.Add([ordered]@{
            Offset = $offset
            OffsetHex = ('0x{0:X}' -f $offset)
            X = [math]::Round($x, 6)
            Y = [math]::Round($y, 6)
            Z = [math]::Round($z, 6)
            Magnitude = [math]::Round($magnitude, 6)
        }) | Out-Null
    }

    return $matches
}

function Get-PointerFields {
    param(
        [Parameter(Mandatory = $true)]
        [byte[]]$Bytes
    )

    $matches = New-Object System.Collections.Generic.List[object]
    for ($offset = 0; ($offset + 8) -le $Bytes.Length; $offset += 8) {
        $value = Read-UInt64At -Bytes $Bytes -Offset $offset
        if ($null -eq $value -or -not (Test-PlausiblePointer -Value $value)) {
            continue
        }

        $matches.Add([ordered]@{
            Offset = $offset
            OffsetHex = ('0x{0:X}' -f $offset)
            Address = ('0x{0:X}' -f $value)
        }) | Out-Null
    }

    return $matches
}

function Get-DirectOffsets {
    param(
        [Parameter(Mandatory = $true)]
        [byte[]]$Bytes,

        [Parameter(Mandatory = $true)]
        [int[]]$Offsets
    )

    $rows = New-Object System.Collections.Generic.List[object]
    foreach ($offset in $Offsets) {
        if (($offset + 12) -gt $Bytes.Length) {
            continue
        }

        $x = Convert-ToFiniteDouble (Read-SingleAt -Bytes $Bytes -Offset $offset)
        $y = Convert-ToFiniteDouble (Read-SingleAt -Bytes $Bytes -Offset ($offset + 4))
        $z = Convert-ToFiniteDouble (Read-SingleAt -Bytes $Bytes -Offset ($offset + 8))
        $rows.Add([ordered]@{
            Offset = $offset
            OffsetHex = ('0x{0:X}' -f $offset)
            X = $x
            Y = $y
            Z = $z
        }) | Out-Null
    }

    return $rows
}

if ($RefreshSelectorTrace -or -not (Test-Path -LiteralPath $resolvedSelectorTraceFile)) {
    & $selectorTraceScript -Json | Out-Null
}

if (-not (Test-Path -LiteralPath $resolvedSelectorTraceFile)) {
    throw "Selector trace file not found: $resolvedSelectorTraceFile"
}

$selectorTrace = Get-Content -LiteralPath $resolvedSelectorTraceFile -Raw | ConvertFrom-Json -Depth 30
$selectedSourceAddress = Parse-HexUInt64 -Value ([string]$selectorTrace.SelectedSource.Address)
$ownerAddress = Parse-HexUInt64 -Value ([string]$selectorTrace.Owner.ObjectAddress)
$expectedX = [double]$selectorTrace.SelectedSource.Coord48.X
$expectedY = [double]$selectorTrace.SelectedSource.Coord48.Y
$expectedZ = [double]$selectorTrace.SelectedSource.Coord48.Z

$selectedSourceBytes = Read-Bytes -Address $selectedSourceAddress -Length $ReadLength
$ownerBytes = Read-Bytes -Address $ownerAddress -Length $ReadLength

$result = [ordered]@{
    Mode = 'selector-trace-neighborhood'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    SelectorTraceFile = $resolvedSelectorTraceFile
    ExpectedCoords = [ordered]@{
        X = $expectedX
        Y = $expectedY
        Z = $expectedZ
        Tolerance = $CoordTolerance
    }
    SelectedSource = [ordered]@{
        Address = ('0x{0:X}' -f $selectedSourceAddress)
        DirectOffsets = Get-DirectOffsets -Bytes $selectedSourceBytes -Offsets @(0x48, 0x60, 0x88, 0x94, 0xD4, 0x140)
        CoordTripletMatches = @((Get-CoordTripletMatches -Bytes $selectedSourceBytes -ExpectedX $expectedX -ExpectedY $expectedY -ExpectedZ $expectedZ) | Select-Object -First $MaxCoordMatches)
        BasisTripletCandidates = @((Get-BasisTripletCandidates -Bytes $selectedSourceBytes) | Select-Object -First $MaxBasisMatches)
        PointerFields = @((Get-PointerFields -Bytes $selectedSourceBytes) | Select-Object -First 32)
    }
    OwnerObject = [ordered]@{
        Address = ('0x{0:X}' -f $ownerAddress)
        DirectOffsets = Get-DirectOffsets -Bytes $ownerBytes -Offsets @(0x48, 0x60, 0x88, 0x94, 0xD4, 0x140)
        CoordTripletMatches = @((Get-CoordTripletMatches -Bytes $ownerBytes -ExpectedX $expectedX -ExpectedY $expectedY -ExpectedZ $expectedZ) | Select-Object -First $MaxCoordMatches)
        BasisTripletCandidates = @((Get-BasisTripletCandidates -Bytes $ownerBytes) | Select-Object -First $MaxBasisMatches)
        PointerFields = @((Get-PointerFields -Bytes $ownerBytes) | Select-Object -First 32)
    }
}

$outputDirectory = Split-Path -Parent $resolvedOutputFile
if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

$jsonText = $result | ConvertTo-Json -Depth 20
Set-Content -LiteralPath $resolvedOutputFile -Value $jsonText -Encoding UTF8

if ($Json) {
    $jsonText
}
else {
    Write-Host ("Selected source address : {0}" -f $result.SelectedSource.Address)
    Write-Host ("Owner object address    : {0}" -f $result.OwnerObject.Address)
    Write-Host ("Selected coord matches  : {0}" -f $result.SelectedSource.CoordTripletMatches.Count)
    Write-Host ("Owner coord matches     : {0}" -f $result.OwnerObject.CoordTripletMatches.Count)
    Write-Host ("Selected basis hits     : {0}" -f $result.SelectedSource.BasisTripletCandidates.Count)
    Write-Host ("Owner basis hits        : {0}" -f $result.OwnerObject.BasisTripletCandidates.Count)
    Write-Host ("Wrote neighborhood scan to {0}" -f $resolvedOutputFile)
}
