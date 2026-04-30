[CmdletBinding()]
param(
    [switch]$Json,
    [string]$ProcessName = 'rift_x64',
    [int]$ProcessId,
    [string]$TargetWindowHandle,
    [string]$InputSummaryFile = (Join-Path $PSScriptRoot 'captures\coord-no-ce-scan-20260430-1501\no-ce-scan-summary.json'),
    [string]$OutputFile = (Join-Path $PSScriptRoot 'captures\coord-no-ce-neighborhood.json'),
    [int]$BeforeBytes = 256,
    [int]$AfterBytes = 512,
    [int]$MaxPointerSlotsPerWindow = 64,
    [int]$MaxSeedReferenceWindows = 24,
    [int]$NearSeedBytes = 4096,
    [double]$CoordTolerance = 0.25
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$resolvedInputSummaryFile = [System.IO.Path]::GetFullPath($InputSummaryFile)
$resolvedOutputFile = [System.IO.Path]::GetFullPath($OutputFile)

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public static class RiftNoCeCoordNeighborhoodTargetNative
{
    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool IsWindow(IntPtr hWnd);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
}
"@

function ConvertTo-WindowHandle {
    param([string]$HandleText)

    if ([string]::IsNullOrWhiteSpace($HandleText)) {
        return [IntPtr]::Zero
    }

    if ($HandleText.StartsWith('0x', [System.StringComparison]::OrdinalIgnoreCase)) {
        $raw = [UInt64]::Parse($HandleText.Substring(2), [System.Globalization.NumberStyles]::AllowHexSpecifier, [System.Globalization.CultureInfo]::InvariantCulture)
        return [IntPtr]([Int64]$raw)
    }

    return [IntPtr]([Int64]::Parse($HandleText, [System.Globalization.CultureInfo]::InvariantCulture))
}

function Get-EffectiveTargetProcessId {
    $handle = ConvertTo-WindowHandle -HandleText $TargetWindowHandle
    if ($handle -ne [IntPtr]::Zero) {
        if (-not [RiftNoCeCoordNeighborhoodTargetNative]::IsWindow($handle)) {
            throw "Target window handle '$TargetWindowHandle' is not a valid window."
        }

        $ownerProcessId = [uint32]0
        [void][RiftNoCeCoordNeighborhoodTargetNative]::GetWindowThreadProcessId($handle, [ref]$ownerProcessId)
        if ($ownerProcessId -eq 0) {
            throw "Target window handle '$TargetWindowHandle' did not resolve to a process id."
        }

        if ($ProcessId -gt 0 -and [int]$ownerProcessId -ne $ProcessId) {
            throw "Target window handle '$TargetWindowHandle' belongs to PID $ownerProcessId, not PID $ProcessId."
        }

        return [int]$ownerProcessId
    }

    if ($ProcessId -gt 0) {
        return $ProcessId
    }

    return $null
}

function Get-ReaderTargetArguments {
    $effectiveProcessId = Get-EffectiveTargetProcessId
    if ($null -ne $effectiveProcessId -and $effectiveProcessId -gt 0) {
        return @('--pid', $effectiveProcessId.ToString([System.Globalization.CultureInfo]::InvariantCulture))
    }

    return @('--process-name', $ProcessName)
}

function Invoke-ReaderJson {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $output = & dotnet run --project $readerProject -- @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    $text = $output -join [Environment]::NewLine
    if ($exitCode -ne 0) {
        throw "Reader command failed (`$LASTEXITCODE=$exitCode): $text"
    }

    return $text | ConvertFrom-Json -Depth 80
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
    param([Parameter(Mandatory = $true)][UInt64]$Value)

    return ('0x{0:X}' -f $Value)
}

function ConvertFrom-HexBytes {
    param([Parameter(Mandatory = $true)][string]$Hex)

    $normalized = ($Hex -replace '\s+', '').Trim()
    if (($normalized.Length % 2) -ne 0) {
        throw "Hex byte string has odd length."
    }

    $bytes = New-Object byte[] ($normalized.Length / 2)
    for ($index = 0; $index -lt $bytes.Length; $index++) {
        $bytes[$index] = [Convert]::ToByte($normalized.Substring($index * 2, 2), 16)
    }

    return $bytes
}

function Read-MemoryBytes {
    param(
        [Parameter(Mandatory = $true)]
        [UInt64]$Address,

        [Parameter(Mandatory = $true)]
        [int]$Length
    )

    $arguments = @(Get-ReaderTargetArguments) + @(
        '--address', (Format-HexUInt64 -Value $Address),
        '--length', $Length.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '--json')

    $result = Invoke-ReaderJson -Arguments $arguments
    return ConvertFrom-HexBytes -Hex ([string]$result.BytesHex)
}

function Read-UInt64At {
    param([byte[]]$Bytes, [int]$Offset)

    if ($Offset -lt 0 -or ($Offset + 8) -gt $Bytes.Length) {
        return $null
    }

    return [BitConverter]::ToUInt64($Bytes, $Offset)
}

function Read-FloatAt {
    param([byte[]]$Bytes, [int]$Offset)

    if ($Offset -lt 0 -or ($Offset + 4) -gt $Bytes.Length) {
        return $null
    }

    return [BitConverter]::ToSingle($Bytes, $Offset)
}

function Test-FiniteFloat {
    param($Value)

    if ($null -eq $Value) {
        return $false
    }

    return -not ([double]::IsNaN([double]$Value) -or [double]::IsInfinity([double]$Value))
}

function Get-SeedRelation {
    param(
        [Parameter(Mandatory = $true)]
        [UInt64]$Value,

        [Parameter(Mandatory = $true)]
        [object[]]$Seeds
    )

    $relations = New-Object System.Collections.Generic.List[object]
    foreach ($seed in $Seeds) {
        $seedAddress = [UInt64]$seed.Address
        $delta = if ($Value -ge $seedAddress) { $Value - $seedAddress } else { $seedAddress - $Value }
        if ($delta -eq 0) {
            $relations.Add([pscustomobject]@{
                    Kind = 'exact'
                    SeedLabel = [string]$seed.Label
                    SeedAddress = Format-HexUInt64 -Value $seedAddress
                    Delta = 0
                }) | Out-Null
        }
        elseif ($delta -le [UInt64]$NearSeedBytes) {
            $relations.Add([pscustomobject]@{
                    Kind = 'near'
                    SeedLabel = [string]$seed.Label
                    SeedAddress = Format-HexUInt64 -Value $seedAddress
                    Delta = [Int64]$delta
                }) | Out-Null
        }
    }

    return @($relations.ToArray())
}

function Get-PointerSlots {
    param(
        [Parameter(Mandatory = $true)]
        [byte[]]$Bytes,

        [Parameter(Mandatory = $true)]
        [UInt64]$WindowStart,

        [Parameter(Mandatory = $true)]
        [object[]]$Seeds
    )

    $slots = New-Object System.Collections.Generic.List[object]
    for ($offset = 0; $offset -le ($Bytes.Length - 8); $offset += 8) {
        $value = Read-UInt64At -Bytes $Bytes -Offset $offset
        if ($null -eq $value -or $value -le 0x100000000 -or $value -ge 0x0000800000000000) {
            continue
        }

        $relations = @(Get-SeedRelation -Value ([UInt64]$value) -Seeds $Seeds)
        $slots.Add([pscustomobject]@{
                Address = Format-HexUInt64 -Value ([UInt64]($WindowStart + [UInt64]$offset))
                OffsetHex = ('0x{0:X}' -f $offset)
                Value = Format-HexUInt64 -Value ([UInt64]$value)
                SeedRelations = $relations
            }) | Out-Null

        if ($slots.Count -ge $MaxPointerSlotsPerWindow) {
            break
        }
    }

    return @($slots.ToArray())
}

function Test-CoordMatch {
    param($ExpectedX, $ExpectedY, $ExpectedZ, $ActualX, $ActualY, $ActualZ)

    if (-not (Test-FiniteFloat $ActualX) -or -not (Test-FiniteFloat $ActualY) -or -not (Test-FiniteFloat $ActualZ)) {
        return $false
    }

    return ([Math]::Abs([double]$ActualX - [double]$ExpectedX) -le $CoordTolerance) -and
        ([Math]::Abs([double]$ActualY - [double]$ExpectedY) -le $CoordTolerance) -and
        ([Math]::Abs([double]$ActualZ - [double]$ExpectedZ) -le $CoordTolerance)
}

function Get-CoordTriplets {
    param(
        [Parameter(Mandatory = $true)]
        [byte[]]$Bytes,

        [Parameter(Mandatory = $true)]
        [UInt64]$WindowStart,

        [Parameter(Mandatory = $true)]
        $ExpectedCoord
    )

    $triplets = New-Object System.Collections.Generic.List[object]
    for ($offset = 0; $offset -le ($Bytes.Length - 12); $offset += 4) {
        $x = Read-FloatAt -Bytes $Bytes -Offset $offset
        $y = Read-FloatAt -Bytes $Bytes -Offset ($offset + 4)
        $z = Read-FloatAt -Bytes $Bytes -Offset ($offset + 8)
        if (-not (Test-CoordMatch -ExpectedX $ExpectedCoord.X -ExpectedY $ExpectedCoord.Y -ExpectedZ $ExpectedCoord.Z -ActualX $x -ActualY $y -ActualZ $z)) {
            continue
        }

        $triplets.Add([pscustomobject]@{
                Address = Format-HexUInt64 -Value ([UInt64]($WindowStart + [UInt64]$offset))
                OffsetHex = ('0x{0:X}' -f $offset)
                X = [double]$x
                Y = [double]$y
                Z = [double]$z
                DeltaX = [double]$x - [double]$ExpectedCoord.X
                DeltaY = [double]$y - [double]$ExpectedCoord.Y
                DeltaZ = [double]$z - [double]$ExpectedCoord.Z
            }) | Out-Null
    }

    return @($triplets.ToArray())
}

function Measure-Vector {
    param($X, $Y, $Z)

    if (-not (Test-FiniteFloat $X) -or -not (Test-FiniteFloat $Y) -or -not (Test-FiniteFloat $Z)) {
        return $null
    }

    return [Math]::Sqrt(([double]$X * [double]$X) + ([double]$Y * [double]$Y) + ([double]$Z * [double]$Z))
}

function Get-Dot {
    param($Ax, $Ay, $Az, $Bx, $By, $Bz)

    return ([double]$Ax * [double]$Bx) + ([double]$Ay * [double]$By) + ([double]$Az * [double]$Bz)
}

function Get-Determinant {
    param($Fx, $Fy, $Fz, $Ux, $Uy, $Uz, $Rx, $Ry, $Rz)

    return ([double]$Fx * (([double]$Uy * [double]$Rz) - ([double]$Uz * [double]$Ry))) -
        ([double]$Fy * (([double]$Ux * [double]$Rz) - ([double]$Uz * [double]$Rx))) +
        ([double]$Fz * (([double]$Ux * [double]$Ry) - ([double]$Uy * [double]$Rx)))
}

function Get-BasisCandidates {
    param(
        [Parameter(Mandatory = $true)]
        [byte[]]$Bytes,

        [Parameter(Mandatory = $true)]
        [UInt64]$WindowStart
    )

    $candidates = New-Object System.Collections.Generic.List[object]
    for ($offset = 0; $offset -le ($Bytes.Length - 36); $offset += 4) {
        $fx = Read-FloatAt -Bytes $Bytes -Offset $offset
        $fy = Read-FloatAt -Bytes $Bytes -Offset ($offset + 4)
        $fz = Read-FloatAt -Bytes $Bytes -Offset ($offset + 8)
        $ux = Read-FloatAt -Bytes $Bytes -Offset ($offset + 12)
        $uy = Read-FloatAt -Bytes $Bytes -Offset ($offset + 16)
        $uz = Read-FloatAt -Bytes $Bytes -Offset ($offset + 20)
        $rx = Read-FloatAt -Bytes $Bytes -Offset ($offset + 24)
        $ry = Read-FloatAt -Bytes $Bytes -Offset ($offset + 28)
        $rz = Read-FloatAt -Bytes $Bytes -Offset ($offset + 32)

        $forwardMag = Measure-Vector -X $fx -Y $fy -Z $fz
        $upMag = Measure-Vector -X $ux -Y $uy -Z $uz
        $rightMag = Measure-Vector -X $rx -Y $ry -Z $rz
        if ($null -eq $forwardMag -or $null -eq $upMag -or $null -eq $rightMag) {
            continue
        }

        if ($forwardMag -lt 0.85 -or $forwardMag -gt 1.15 -or
            $upMag -lt 0.85 -or $upMag -gt 1.15 -or
            $rightMag -lt 0.85 -or $rightMag -gt 1.15) {
            continue
        }

        $forwardDotUp = Get-Dot -Ax $fx -Ay $fy -Az $fz -Bx $ux -By $uy -Bz $uz
        $forwardDotRight = Get-Dot -Ax $fx -Ay $fy -Az $fz -Bx $rx -By $ry -Bz $rz
        $upDotRight = Get-Dot -Ax $ux -Ay $uy -Az $uz -Bx $rx -By $ry -Bz $rz
        if ([Math]::Abs($forwardDotUp) -gt 0.12 -or [Math]::Abs($forwardDotRight) -gt 0.12 -or [Math]::Abs($upDotRight) -gt 0.12) {
            continue
        }

        $determinant = Get-Determinant -Fx $fx -Fy $fy -Fz $fz -Ux $ux -Uy $uy -Uz $uz -Rx $rx -Ry $ry -Rz $rz
        $yaw = [Math]::Atan2([double]$fz, [double]$fx) * 180.0 / [Math]::PI
        $pitch = [Math]::Atan2([double]$fy, [Math]::Sqrt(([double]$fx * [double]$fx) + ([double]$fz * [double]$fz))) * 180.0 / [Math]::PI

        $candidates.Add([pscustomobject]@{
                Address = Format-HexUInt64 -Value ([UInt64]($WindowStart + [UInt64]$offset))
                OffsetHex = ('0x{0:X}' -f $offset)
                Forward = [pscustomobject]@{ X = [double]$fx; Y = [double]$fy; Z = [double]$fz; Magnitude = $forwardMag }
                Up = [pscustomobject]@{ X = [double]$ux; Y = [double]$uy; Z = [double]$uz; Magnitude = $upMag }
                Right = [pscustomobject]@{ X = [double]$rx; Y = [double]$ry; Z = [double]$rz; Magnitude = $rightMag }
                ForwardDotUp = $forwardDotUp
                ForwardDotRight = $forwardDotRight
                UpDotRight = $upDotRight
                Determinant = $determinant
                YawDegrees = $yaw
                PitchDegrees = $pitch
            }) | Out-Null
    }

    return @($candidates.ToArray())
}

function Get-AsciiSegments {
    param(
        [Parameter(Mandatory = $true)]
        [byte[]]$Bytes,

        [Parameter(Mandatory = $true)]
        [UInt64]$WindowStart
    )

    $segments = New-Object System.Collections.Generic.List[object]
    $start = -1
    $chars = New-Object System.Collections.Generic.List[char]

    for ($index = 0; $index -lt $Bytes.Length; $index++) {
        $byte = $Bytes[$index]
        $printable = $byte -ge 32 -and $byte -le 126
        if ($printable) {
            if ($start -lt 0) {
                $start = $index
            }

            $chars.Add([char]$byte) | Out-Null
            continue
        }

        if ($start -ge 0 -and $chars.Count -ge 4) {
            $segments.Add([pscustomobject]@{
                    Address = Format-HexUInt64 -Value ([UInt64]($WindowStart + [UInt64]$start))
                    OffsetHex = ('0x{0:X}' -f $start)
                    Text = -join $chars.ToArray()
                }) | Out-Null
        }

        $start = -1
        $chars.Clear()
    }

    if ($start -ge 0 -and $chars.Count -ge 4) {
        $segments.Add([pscustomobject]@{
                Address = Format-HexUInt64 -Value ([UInt64]($WindowStart + [UInt64]$start))
                OffsetHex = ('0x{0:X}' -f $start)
                Text = -join $chars.ToArray()
            }) | Out-Null
    }

    return @($segments.ToArray())
}

function New-Seed {
    param([string]$Label, [string]$AddressText, [string]$Kind)

    if ([string]::IsNullOrWhiteSpace($AddressText)) {
        return $null
    }

    return [pscustomobject]@{
        Label = $Label
        Kind = $Kind
        Address = Parse-HexUInt64 -Value $AddressText
        AddressHex = (Format-HexUInt64 -Value (Parse-HexUInt64 -Value $AddressText))
    }
}

if (-not (Test-Path -LiteralPath $resolvedInputSummaryFile -PathType Leaf)) {
    throw "Input summary file was not found: $resolvedInputSummaryFile"
}

$inputSummary = Get-Content -LiteralPath $resolvedInputSummaryFile -Raw | ConvertFrom-Json -Depth 80
$effectiveProcessId = Get-EffectiveTargetProcessId

$expectedCoord = [pscustomobject]@{
    X = [double]$inputSummary.readerBridge.coord.x
    Y = [double]$inputSummary.readerBridge.coord.y
    Z = [double]$inputSummary.readerBridge.coord.z
}

$seedList = New-Object System.Collections.Generic.List[object]
foreach ($hit in @($inputSummary.exactCoordScan.hits)) {
    $seed = New-Seed -Label ("coord-root:{0}" -f $hit.address) -AddressText ([string]$hit.address) -Kind 'coord-root'
    if ($null -ne $seed) { $seedList.Add($seed) | Out-Null }
}

$yawSeed = New-Seed -Label 'behavior-backed-yaw-source' -AddressText ([string]$inputSummary.currentBehaviorBackedYaw.sourceAddress) -Kind 'yaw-source'
if ($null -ne $yawSeed) { $seedList.Add($yawSeed) | Out-Null }

$pointerHopCandidates = @()
if ($inputSummary.orientationCandidateSearch.PSObject.Properties['pointerHopCandidates']) {
    $pointerHopCandidates = @($inputSummary.orientationCandidateSearch.pointerHopCandidates)
}
elseif ($null -ne $inputSummary.orientationCandidateSearch.bestPointerHopCandidate) {
    $pointerHopCandidates = @($inputSummary.orientationCandidateSearch.bestPointerHopCandidate)
}

for ($candidateIndex = 0; $candidateIndex -lt $pointerHopCandidates.Count; $candidateIndex++) {
    $candidate = $pointerHopCandidates[$candidateIndex]
    $prefix = if ($candidateIndex -eq 0) { 'best-pointer-hop' } else { 'pointer-hop-{0}' -f ($candidateIndex + 1) }
    foreach ($item in @(
            @{ Label = "$prefix-candidate"; Address = [string]$candidate.address; Kind = 'pointer-hop-candidate' },
            @{ Label = "$prefix-root"; Address = [string]$candidate.rootAddress; Kind = 'pointer-hop-root' },
            @{ Label = "$prefix-parent"; Address = [string]$candidate.parentAddress; Kind = 'pointer-hop-parent' })) {
        $seed = New-Seed -Label $item.Label -AddressText $item.Address -Kind $item.Kind
        if ($null -ne $seed) { $seedList.Add($seed) | Out-Null }
    }
}

$referenceWindows = New-Object System.Collections.Generic.List[object]
foreach ($seed in $seedList) {
    $referenceWindows.Add([pscustomobject]@{
            Label = $seed.Label
            Kind = $seed.Kind
            CenterAddress = $seed.Address
            CenterAddressHex = $seed.AddressHex
        }) | Out-Null
}

$refIndex = 0
foreach ($refAddress in @($inputSummary.pointerScans.yawSourcePointerRefs)) {
    if ($refIndex -ge $MaxSeedReferenceWindows) { break }
    $seed = New-Seed -Label ("yaw-source-ref:{0}" -f $refAddress) -AddressText ([string]$refAddress) -Kind 'yaw-source-ref'
    if ($null -ne $seed) {
        $referenceWindows.Add([pscustomobject]@{
                Label = $seed.Label
                Kind = $seed.Kind
                CenterAddress = $seed.Address
                CenterAddressHex = $seed.AddressHex
            }) | Out-Null
        $refIndex++
    }
}

foreach ($refAddress in @($inputSummary.pointerScans.bestPointerHopPointerRefs)) {
    if ($refIndex -ge $MaxSeedReferenceWindows) { break }
    $seed = New-Seed -Label ("best-pointer-hop-ref:{0}" -f $refAddress) -AddressText ([string]$refAddress) -Kind 'pointer-hop-ref'
    if ($null -ne $seed) {
        $referenceWindows.Add([pscustomobject]@{
                Label = $seed.Label
                Kind = $seed.Kind
                CenterAddress = $seed.Address
                CenterAddressHex = $seed.AddressHex
            }) | Out-Null
        $refIndex++
    }
}

$windowResults = New-Object System.Collections.Generic.List[object]
foreach ($window in $referenceWindows) {
    $center = [UInt64]$window.CenterAddress
    $rawStart = if ($center -gt [UInt64]$BeforeBytes) { $center - [UInt64]$BeforeBytes } else { [UInt64]0 }
    $alignedStart = $rawStart - ($rawStart % 8)
    $extraPrefix = [int]($rawStart - $alignedStart)
    $length = $BeforeBytes + $AfterBytes + $extraPrefix

    try {
        $bytes = Read-MemoryBytes -Address $alignedStart -Length $length
        $pointerSlots = @(Get-PointerSlots -Bytes $bytes -WindowStart $alignedStart -Seeds @($seedList.ToArray()))
        $coordTriplets = @(Get-CoordTriplets -Bytes $bytes -WindowStart $alignedStart -ExpectedCoord $expectedCoord)
        $basisCandidates = @(Get-BasisCandidates -Bytes $bytes -WindowStart $alignedStart)
        $asciiSegments = @(Get-AsciiSegments -Bytes $bytes -WindowStart $alignedStart)

        $windowResults.Add([pscustomobject]@{
                Label = [string]$window.Label
                Kind = [string]$window.Kind
                CenterAddress = [string]$window.CenterAddressHex
                WindowStart = Format-HexUInt64 -Value $alignedStart
                WindowLength = $bytes.Length
                ReadSucceeded = $true
                PointerSlotCount = $pointerSlots.Count
                PointerSlots = $pointerSlots
                CoordTripletCount = $coordTriplets.Count
                CoordTriplets = $coordTriplets
                BasisCandidateCount = $basisCandidates.Count
                BasisCandidates = $basisCandidates
                AsciiSegments = $asciiSegments
            }) | Out-Null
    }
    catch {
        $windowResults.Add([pscustomobject]@{
                Label = [string]$window.Label
                Kind = [string]$window.Kind
                CenterAddress = [string]$window.CenterAddressHex
                WindowStart = Format-HexUInt64 -Value $alignedStart
                WindowLength = $length
                ReadSucceeded = $false
                Error = $_.Exception.Message
            }) | Out-Null
    }
}

$localLinks = @(
    foreach ($window in $windowResults) {
        if ($window.PSObject.Properties['PointerSlots']) {
            foreach ($slot in @($window.PointerSlots)) {
                if (@($slot.SeedRelations).Count -gt 0) {
                    [pscustomobject]@{
                        WindowLabel = $window.Label
                        PointerAddress = $slot.Address
                        PointerOffset = $slot.OffsetHex
                        PointerValue = $slot.Value
                        Relations = $slot.SeedRelations
                    }
                }
            }
        }
    }
)

$coordWindows = @($windowResults | Where-Object { $_.PSObject.Properties['CoordTripletCount'] -and $_.CoordTripletCount -gt 0 } | Select-Object Label, Kind, CenterAddress, CoordTripletCount, CoordTriplets)
$basisWindows = @($windowResults | Where-Object { $_.PSObject.Properties['BasisCandidateCount'] -and $_.BasisCandidateCount -gt 0 } | Select-Object Label, Kind, CenterAddress, BasisCandidateCount, BasisCandidates)

$result = [ordered]@{
    schemaVersion = 1
    mode = 'coord-no-ce-neighborhood'
    generatedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    noCheatEngine = $true
    noLiveMovementInput = $true
    processName = $ProcessName
    processId = $effectiveProcessId
    targetWindowHandle = $TargetWindowHandle
    inputSummaryFile = $resolvedInputSummaryFile
    expectedCoord = $expectedCoord
    beforeBytes = $BeforeBytes
    afterBytes = $AfterBytes
    coordTolerance = $CoordTolerance
    seeds = @($seedList.ToArray() | ForEach-Object { [pscustomobject]@{ Label = $_.Label; Kind = $_.Kind; Address = $_.AddressHex } })
    windowCount = $windowResults.Count
    windows = @($windowResults.ToArray())
    linkSummary = [ordered]@{
        localPointerLinkCount = @($localLinks).Count
        localPointerLinks = @($localLinks)
        coordWindowCount = @($coordWindows).Count
        coordWindows = @($coordWindows)
        basisWindowCount = @($basisWindows).Count
        basisWindows = @($basisWindows)
    }
    conclusion = 'Read-only no-CE neighborhood report. Candidate links are structural only; they do not satisfy movement-grade coord-trace-coords proof by themselves.'
    outputFile = $resolvedOutputFile
}

$outputDirectory = Split-Path -Parent $resolvedOutputFile
if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

$jsonText = $result | ConvertTo-Json -Depth 80
Set-Content -LiteralPath $resolvedOutputFile -Value $jsonText -Encoding UTF8

if ($Json) {
    Write-Output $jsonText
}
else {
    Write-Host "No-CE neighborhood file: $resolvedOutputFile"
    Write-Host "Windows:                 $($windowResults.Count)"
    Write-Host "Local pointer links:     $(@($localLinks).Count)"
    Write-Host "Coord windows:           $(@($coordWindows).Count)"
    Write-Host "Basis windows:           $(@($basisWindows).Count)"
    Write-Host "Movement gate:           false"
}
