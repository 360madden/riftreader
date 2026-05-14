[CmdletBinding()]
param(
    [string]$ProcessName = 'rift_x64',
    [int]$ProcessId,
    [string]$TargetWindowHandle,
    [string]$RiftScanRoot = 'C:\RIFT MODDING\Riftscan',
    [string]$CandidateFile,
    [string]$OutputRoot = (Join-Path $PSScriptRoot 'captures'),
    [string]$ReaderSessionRoot = (Join-Path $PSScriptRoot 'sessions'),
    [int]$PassiveSamples = 3,
    [int]$PassiveIntervalMilliseconds = 100,
    [int]$PassiveMaxRegions = 16,
    [int]$PassiveMaxBytesPerRegion = 65536,
    [long]$PassiveMaxTotalBytes = 2097152,
    [int]$TopCount = 10,
    [int]$ContextBytes = 64,
    [int]$ReadbackSampleCount = 2,
    [int]$ReadbackIntervalMilliseconds = 100,
    [string]$DecodeOnlyWatchsetFile,
    [string]$DecodeOnlySamplesFile,
    [string]$DecodeOnlyOutputFile,
    [string]$ReferenceFile,
    [double]$ReferenceX,
    [double]$ReferenceY,
    [double]$ReferenceZ,
    [double]$ReferenceTolerance = 0.25,
    [string]$ReferenceSource = 'manual-or-overlay-reference',
    [int]$ReferenceMaxAgeSeconds = 0,
    [int]$ProofAnchorMaxAgeSeconds = 60,
    [int]$TopReferenceMatches = 5,
    [switch]$SkipProofAnchorCheck,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$importerScript = Join-Path $PSScriptRoot 'import-riftscan-coordinate-candidates.ps1'
$proofAnchorScript = Join-Path $PSScriptRoot 'assert-current-proof-coord-anchor.ps1'

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public static class RiftScanReadbackTargetNative
{
    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool IsWindow(IntPtr hWnd);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
}
"@

function Get-NormalizedProcessName {
    param([string]$Name)

    if ([string]::IsNullOrWhiteSpace($Name)) {
        return $Name
    }

    $trimmed = $Name.Trim()
    if ($trimmed.EndsWith('.exe', [System.StringComparison]::OrdinalIgnoreCase)) {
        return $trimmed.Substring(0, $trimmed.Length - 4)
    }

    return $trimmed
}

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

function Format-WindowHandle {
    param([IntPtr]$Handle)

    if ($Handle -eq [IntPtr]::Zero) {
        return $null
    }

    return ('0x{0:X}' -f $Handle.ToInt64())
}

function Resolve-TargetProcess {
    $normalizedName = Get-NormalizedProcessName -Name $ProcessName
    $handle = ConvertTo-WindowHandle -HandleText $TargetWindowHandle

    if ($handle -ne [IntPtr]::Zero) {
        if (-not [RiftScanReadbackTargetNative]::IsWindow($handle)) {
            throw "Target window handle '$TargetWindowHandle' is not a valid window."
        }

        $ownerProcessId = [uint32]0
        [void][RiftScanReadbackTargetNative]::GetWindowThreadProcessId($handle, [ref]$ownerProcessId)
        if ($ownerProcessId -eq 0) {
            throw "Target window handle '$TargetWindowHandle' did not resolve to an owning process."
        }

        if ($ProcessId -gt 0 -and [int]$ownerProcessId -ne $ProcessId) {
            throw "Target window handle '$TargetWindowHandle' belongs to PID $ownerProcessId, not PID $ProcessId."
        }

        $process = Get-Process -Id ([int]$ownerProcessId) -ErrorAction Stop
        if (-not [string]::IsNullOrWhiteSpace($normalizedName) -and
            -not [string]::Equals($process.ProcessName, $normalizedName, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Target window handle '$TargetWindowHandle' belongs to process '$($process.ProcessName)' [PID $ownerProcessId], not '$ProcessName'."
        }

        return [pscustomobject]@{
            Process = $process
            Handle = $handle
        }
    }

    if ($ProcessId -gt 0) {
        $process = Get-Process -Id $ProcessId -ErrorAction Stop
        if (-not [string]::IsNullOrWhiteSpace($normalizedName) -and
            -not [string]::Equals($process.ProcessName, $normalizedName, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Target PID $ProcessId is process '$($process.ProcessName)', not '$ProcessName'."
        }

        return [pscustomobject]@{
            Process = $process
            Handle = $process.MainWindowHandle
        }
    }

    $matches = @(Get-Process -Name $normalizedName -ErrorAction Stop | Sort-Object StartTime -Descending)
    if ($matches.Count -ne 1) {
        throw "Expected exactly one '$ProcessName' process when no PID/HWND is supplied; found $($matches.Count). Pass -ProcessId or -TargetWindowHandle."
    }

    return [pscustomobject]@{
        Process = $matches[0]
        Handle = $matches[0].MainWindowHandle
    }
}

function Invoke-ExternalCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        [string]$WorkingDirectory,

        [switch]$AllowFailure
    )

    $previousLocation = Get-Location
    try {
        if (-not [string]::IsNullOrWhiteSpace($WorkingDirectory)) {
            Set-Location -LiteralPath $WorkingDirectory
        }

        $output = & $FilePath @Arguments 2>&1
        $exitCode = $LASTEXITCODE
        $text = $output -join [Environment]::NewLine
        if ($exitCode -ne 0 -and -not $AllowFailure) {
            throw "Command failed (`$LASTEXITCODE=$exitCode): $FilePath $($Arguments -join ' ')`n$text"
        }

        return [pscustomobject]@{
            FilePath = $FilePath
            Arguments = @($Arguments)
            ExitCode = $exitCode
            Output = $text
        }
    }
    finally {
        Set-Location -LiteralPath $previousLocation
    }
}

function Invoke-PowerShellScript {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ScriptPath,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        [switch]$AllowFailure
    )

    return Invoke-ExternalCommand -FilePath 'powershell' -Arguments (@(
            '-NoLogo',
            '-NoProfile',
            '-ExecutionPolicy',
            'Bypass',
            '-File',
            $ScriptPath
        ) + $Arguments) -WorkingDirectory $repoRoot -AllowFailure:$AllowFailure
}

function ConvertFrom-JsonCompat {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Text,
        [int]$Depth = 80
    )

    $command = Get-Command -Name ConvertFrom-Json -CommandType Cmdlet
    if ($command.Parameters.ContainsKey('Depth')) {
        return $Text | ConvertFrom-Json -Depth $Depth
    }

    return $Text | ConvertFrom-Json
}

function Get-JsonPropertyValue {
    param(
        $InputObject,

        [Parameter(Mandatory = $true)]
        [string[]]$Names
    )

    if ($null -eq $InputObject) {
        return $null
    }

    if ($InputObject -is [System.Collections.IDictionary]) {
        foreach ($name in $Names) {
            foreach ($key in $InputObject.Keys) {
                if ([string]::Equals([string]$key, $name, [System.StringComparison]::OrdinalIgnoreCase)) {
                    return $InputObject[$key]
                }
            }
        }

        return $null
    }

    foreach ($name in $Names) {
        foreach ($property in @($InputObject.PSObject.Properties)) {
            if ([string]::Equals($property.Name, $name, [System.StringComparison]::OrdinalIgnoreCase)) {
                return $property.Value
            }
        }
    }

    return $null
}

function ConvertTo-UtcDateTimeOffset {
    param(
        $Value,

        [Parameter(Mandatory = $true)]
        [string]$Description
    )

    if ($null -eq $Value -or [string]::IsNullOrWhiteSpace([string]$Value)) {
        return $null
    }

    if ($Value -is [DateTimeOffset]) {
        return ([DateTimeOffset]$Value).ToUniversalTime()
    }

    if ($Value -is [DateTime]) {
        $dateTime = [DateTime]$Value
        if ($dateTime.Kind -eq [DateTimeKind]::Utc) {
            return ([DateTimeOffset]::new($dateTime)).ToUniversalTime()
        }

        if ($dateTime.Kind -eq [DateTimeKind]::Local) {
            return ([DateTimeOffset]::new($dateTime)).ToUniversalTime()
        }
    }

    try {
        return [DateTimeOffset]::Parse([string]$Value, [System.Globalization.CultureInfo]::InvariantCulture).ToUniversalTime()
    }
    catch {
        throw "Could not parse $Description timestamp '$Value': $($_.Exception.Message)"
    }
}

function ConvertTo-UtcTimestampString {
    param(
        $Value,

        [Parameter(Mandatory = $true)]
        [string]$Description
    )

    $timestamp = ConvertTo-UtcDateTimeOffset -Value $Value -Description $Description
    if ($null -eq $timestamp) {
        return $null
    }

    return $timestamp.UtcDateTime.ToString("yyyy-MM-dd'T'HH:mm:ss.fffffff'Z'", [System.Globalization.CultureInfo]::InvariantCulture)
}

function Parse-HexUInt64 {
    param([Parameter(Mandatory = $true)][string]$Value)

    $normalized = $Value.Trim()
    if ($normalized.StartsWith('0x', [System.StringComparison]::OrdinalIgnoreCase)) {
        $normalized = $normalized.Substring(2)
    }

    return [UInt64]::Parse($normalized, [System.Globalization.NumberStyles]::HexNumber, [System.Globalization.CultureInfo]::InvariantCulture)
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

function Read-Float32At {
    param(
        [Parameter(Mandatory = $true)]
        [byte[]]$Bytes,

        [Parameter(Mandatory = $true)]
        [int]$Offset
    )

    if ($Offset -lt 0 -or ($Offset + 4) -gt $Bytes.Length) {
        throw "Float32 offset $Offset is outside byte buffer length $($Bytes.Length)."
    }

    return [double][BitConverter]::ToSingle($Bytes, $Offset)
}

function Write-Utf8Json {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        $Value
    )

    $directory = Split-Path -Path $Path -Parent
    if (-not [string]::IsNullOrWhiteSpace($directory)) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }

    $Value | ConvertTo-Json -Depth 32 | Set-Content -LiteralPath $Path -Encoding UTF8
}

function Resolve-ReferenceCoordinate {
    $referenceKeys = @('ReferenceX', 'ReferenceY', 'ReferenceZ')
    $suppliedReferenceKeyCount = @($referenceKeys | Where-Object { $PSBoundParameters.ContainsKey($_) }).Count
    if ($suppliedReferenceKeyCount -ne 0 -and $suppliedReferenceKeyCount -ne 3) {
        throw "Reference comparison requires all of -ReferenceX, -ReferenceY, and -ReferenceZ, or none of them."
    }

    if (-not [string]::IsNullOrWhiteSpace($ReferenceFile) -and $suppliedReferenceKeyCount -ne 0) {
        throw "Use either -ReferenceFile or explicit -ReferenceX/-ReferenceY/-ReferenceZ, not both."
    }

    if ($ReferenceMaxAgeSeconds -lt 0) {
        throw "ReferenceMaxAgeSeconds must be zero or greater."
    }

    if ([string]::IsNullOrWhiteSpace($ReferenceFile) -and $suppliedReferenceKeyCount -eq 0) {
        if ($ReferenceTolerance -lt 0) {
            throw "ReferenceTolerance must be zero or greater."
        }

        return $null
    }

    $source = $ReferenceSource
    $tolerance = [double]$ReferenceTolerance
    $capturedAtUtc = $null
    $ageSeconds = $null
    $referenceFilePath = $null
    $x = $null
    $y = $null
    $z = $null

    if (-not [string]::IsNullOrWhiteSpace($ReferenceFile)) {
        $referenceFilePath = [System.IO.Path]::GetFullPath($ReferenceFile)
        if (-not (Test-Path -LiteralPath $referenceFilePath -PathType Leaf)) {
            throw "Reference coordinate file was not found: $referenceFilePath"
        }

        $document = ConvertFrom-JsonCompat -Text (Get-Content -LiteralPath $referenceFilePath -Raw) -Depth 40
        $coordinate = Get-JsonPropertyValue -InputObject $document -Names @('coordinate', 'position', 'player_coordinate', 'playerCoordinate')
        if ($null -eq $coordinate) {
            $coordinate = $document
        }

        $x = Get-JsonPropertyValue -InputObject $coordinate -Names @('x', 'coord_x', 'coordX')
        $y = Get-JsonPropertyValue -InputObject $coordinate -Names @('y', 'coord_y', 'coordY')
        $z = Get-JsonPropertyValue -InputObject $coordinate -Names @('z', 'coord_z', 'coordZ')

        if (-not $PSBoundParameters.ContainsKey('ReferenceSource')) {
            $fileSource = Get-JsonPropertyValue -InputObject $document -Names @('source', 'Source', 'reference_source', 'referenceSource')
            if (-not [string]::IsNullOrWhiteSpace([string]$fileSource)) {
                $source = [string]$fileSource
            }
        }

        if (-not $PSBoundParameters.ContainsKey('ReferenceTolerance')) {
            $fileTolerance = Get-JsonPropertyValue -InputObject $document -Names @('tolerance', 'Tolerance', 'reference_tolerance', 'referenceTolerance')
            if ($null -ne $fileTolerance -and -not [string]::IsNullOrWhiteSpace([string]$fileTolerance)) {
                $tolerance = [double]$fileTolerance
            }
        }

        $capturedAtValue = Get-JsonPropertyValue -InputObject $document -Names @('captured_at_utc', 'capturedAtUtc', 'timestamp_utc', 'timestampUtc', 'recorded_at_utc', 'recordedAtUtc')
        if ($null -ne $capturedAtValue -and -not [string]::IsNullOrWhiteSpace([string]$capturedAtValue)) {
            $capturedAt = ConvertTo-UtcDateTimeOffset -Value $capturedAtValue -Description 'reference coordinate'
            $capturedAtUtc = $capturedAt.ToString('O')
            $ageSeconds = ([DateTimeOffset]::UtcNow - $capturedAt).TotalSeconds
        }
        elseif ($ReferenceMaxAgeSeconds -gt 0) {
            throw "ReferenceMaxAgeSeconds was set, but reference file '$referenceFilePath' did not contain a captured_at_utc/capturedAtUtc timestamp."
        }
    }
    else {
        $x = $ReferenceX
        $y = $ReferenceY
        $z = $ReferenceZ
    }

    if ($tolerance -lt 0) {
        throw "ReferenceTolerance must be zero or greater."
    }

    if ($null -eq $x -or $null -eq $y -or $null -eq $z) {
        throw "Reference coordinate must expose X/Y/Z values."
    }

    if ($ReferenceMaxAgeSeconds -gt 0 -and $null -ne $ageSeconds) {
        if ($ageSeconds -lt -5 -or $ageSeconds -gt $ReferenceMaxAgeSeconds) {
            throw ("Reference coordinate timestamp is outside the allowed age window: ageSeconds={0:0.000}; maxAgeSeconds={1}." -f $ageSeconds, $ReferenceMaxAgeSeconds)
        }
    }

    return [pscustomobject][ordered]@{
        Source = $source
        X = [double]$x
        Y = [double]$y
        Z = [double]$z
        Tolerance = [double]$tolerance
        ReferenceFile = $referenceFilePath
        CapturedAtUtc = $capturedAtUtc
        AgeSeconds = if ($null -eq $ageSeconds) { $null } else { [Math]::Round([double]$ageSeconds, 3) }
        MaxAgeSeconds = if ($ReferenceMaxAgeSeconds -gt 0) { $ReferenceMaxAgeSeconds } else { $null }
        Notes = @(
            'Reference comparison is candidate scoring only.',
            'A reference match does not satisfy the RiftReader movement proof-anchor gate by itself.'
        )
    }
}

function New-ReferenceDelta {
    param(
        [Parameter(Mandatory = $true)]
        $Sample,

        [Parameter(Mandatory = $true)]
        $Reference
    )

    $dx = [double]$Sample.X - [double]$Reference.X
    $dy = [double]$Sample.Y - [double]$Reference.Y
    $dz = [double]$Sample.Z - [double]$Reference.Z
    $maxAbsDelta = [Math]::Max([Math]::Abs($dx), [Math]::Max([Math]::Abs($dy), [Math]::Abs($dz)))
    $planarDistance = [Math]::Sqrt(($dx * $dx) + ($dz * $dz))
    $spatialDistance = [Math]::Sqrt(($dx * $dx) + ($dy * $dy) + ($dz * $dz))

    return [pscustomobject][ordered]@{
        DeltaX = $dx
        DeltaY = $dy
        DeltaZ = $dz
        MaxAbsDelta = $maxAbsDelta
        PlanarDistance = $planarDistance
        SpatialDistance = $spatialDistance
    }
}

function New-CandidateReadbackSummary {
    param(
        [Parameter(Mandatory = $true)]
        $Watchset,

        [Parameter(Mandatory = $true)]
        [string]$SamplesFile,

        $ReferenceCoordinate = $null,

        [double]$ReferenceTolerance = 0.25,

        [double]$SourcePreviewTolerance = 0.0001
    )

    $candidateByRegionName = @{}
    foreach ($candidate in @($Watchset.Candidates)) {
        $safeId = ([string]$candidate.CandidateId) -replace '[^A-Za-z0-9_.-]', '-'
        $candidateByRegionName["riftscan-vec3-$safeId"] = $candidate
    }

    $entries = @{}
    foreach ($line in Get-Content -LiteralPath $SamplesFile) {
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }

        $sample = ConvertFrom-JsonCompat -Text $line -Depth 80
        foreach ($region in @($sample.Regions)) {
            $regionName = [string]$region.Name
            if (-not $candidateByRegionName.ContainsKey($regionName)) {
                continue
            }

            $candidate = $candidateByRegionName[$regionName]
            if (-not $entries.ContainsKey($regionName)) {
                $entries[$regionName] = [ordered]@{
                    CandidateId = [string]$candidate.CandidateId
                    RegionName = $regionName
                    CandidateAddressHex = [string]$candidate.AbsoluteAddressHex
                    RegionAddressHex = [string]$candidate.RegionAddressHex
                    RegionLength = [int]$candidate.RegionLength
                    CandidateOffsetInRegion = [int]((Parse-HexUInt64 -Value ([string]$candidate.AbsoluteAddressHex)) - (Parse-HexUInt64 -Value ([string]$candidate.RegionAddressHex)))
                    SourceValuePreview = @($candidate.ValuePreview)
                    SourceValueSequenceSummary = [string]$candidate.ValueSequenceSummary
                    DecodedSamples = [System.Collections.Generic.List[object]]::new()
                    DecodeIssues = [System.Collections.Generic.List[string]]::new()
                }
            }

            $entry = $entries[$regionName]
            if (-not [bool]$region.ReadSucceeded) {
                $entry.DecodeIssues.Add(("sample {0}: read failed" -f $sample.SampleIndex)) | Out-Null
                continue
            }

            try {
                $bytes = ConvertFrom-HexBytes -Hex ([string]$region.BytesHex)
                $offset = [int]$entry.CandidateOffsetInRegion
                $entry.DecodedSamples.Add([pscustomobject][ordered]@{
                        SampleIndex = [int]$sample.SampleIndex
                        RecordedAtUtc = ConvertTo-UtcTimestampString -Value $sample.RecordedAtUtc -Description ("readback sample {0}" -f $sample.SampleIndex)
                        X = Read-Float32At -Bytes $bytes -Offset $offset
                        Y = Read-Float32At -Bytes $bytes -Offset ($offset + 4)
                        Z = Read-Float32At -Bytes $bytes -Offset ($offset + 8)
                    }) | Out-Null
            }
            catch {
                $entry.DecodeIssues.Add(("sample {0}: {1}" -f $sample.SampleIndex, $_.Exception.Message)) | Out-Null
            }
        }
    }

    $results = [System.Collections.Generic.List[object]]::new()
    foreach ($name in ($entries.Keys | Sort-Object)) {
        $entry = $entries[$name]
        $decodedSamples = @($entry.DecodedSamples.ToArray())
        $maxAbsDelta = $null
        $previewMaxAbsDelta = $null
        $referenceDelta = $null

        if ($decodedSamples.Count -gt 0) {
            $first = $decodedSamples[0]
            $maxAbsDelta = 0.0
            foreach ($sample in $decodedSamples) {
                $maxAbsDelta = [Math]::Max($maxAbsDelta, [Math]::Abs([double]$sample.X - [double]$first.X))
                $maxAbsDelta = [Math]::Max($maxAbsDelta, [Math]::Abs([double]$sample.Y - [double]$first.Y))
                $maxAbsDelta = [Math]::Max($maxAbsDelta, [Math]::Abs([double]$sample.Z - [double]$first.Z))
            }

            $preview = @($entry.SourceValuePreview)
            if ($preview.Count -ge 3) {
                $previewMaxAbsDelta = 0.0
                $previewMaxAbsDelta = [Math]::Max($previewMaxAbsDelta, [Math]::Abs([double]$first.X - [double]$preview[0]))
                $previewMaxAbsDelta = [Math]::Max($previewMaxAbsDelta, [Math]::Abs([double]$first.Y - [double]$preview[1]))
                $previewMaxAbsDelta = [Math]::Max($previewMaxAbsDelta, [Math]::Abs([double]$first.Z - [double]$preview[2]))
            }

            if ($null -ne $ReferenceCoordinate) {
                $referenceDelta = New-ReferenceDelta -Sample $first -Reference $ReferenceCoordinate
            }
        }

        $results.Add([pscustomobject][ordered]@{
                CandidateId = [string]$entry.CandidateId
                RegionName = [string]$entry.RegionName
                CandidateAddressHex = [string]$entry.CandidateAddressHex
                RegionAddressHex = [string]$entry.RegionAddressHex
                RegionLength = [int]$entry.RegionLength
                CandidateOffsetInRegion = [int]$entry.CandidateOffsetInRegion
                SourceValuePreview = @($entry.SourceValuePreview)
                SourceValueSequenceSummary = [string]$entry.SourceValueSequenceSummary
                DecodedSampleCount = $decodedSamples.Count
                MaxAbsDeltaAcrossReadbackSamples = $maxAbsDelta
                MaxAbsDeltaFromSourcePreview = $previewMaxAbsDelta
                SourcePreviewTolerance = $SourcePreviewTolerance
                SourcePreviewComparisonKind = 'candidate_artifact_value_preview_exact_drift_check'
                StableAcrossReadbackSamples = ($decodedSamples.Count -gt 0 -and $null -ne $maxAbsDelta -and $maxAbsDelta -le 0.000001)
                SourcePreviewMatchesReadback = if ($null -eq $previewMaxAbsDelta) { $null } else { $previewMaxAbsDelta -le $SourcePreviewTolerance }
                ReferenceMaxAbsDelta = if ($null -eq $referenceDelta) { $null } else { [double]$referenceDelta.MaxAbsDelta }
                ReferencePlanarDistance = if ($null -eq $referenceDelta) { $null } else { [double]$referenceDelta.PlanarDistance }
                ReferenceSpatialDistance = if ($null -eq $referenceDelta) { $null } else { [double]$referenceDelta.SpatialDistance }
                ReferenceMatchesReadback = if ($null -eq $referenceDelta) { $null } else { [double]$referenceDelta.MaxAbsDelta -le $ReferenceTolerance }
                DecodeIssues = @($entry.DecodeIssues.ToArray())
                DecodedSamples = @($decodedSamples)
            }) | Out-Null
    }

    return @($results.ToArray())
}

function Convert-FiniteDoubleOrNull {
    param($Value)

    if ($null -eq $Value) {
        return $null
    }

    $number = [double]$Value
    if ([double]::IsNaN($number) -or [double]::IsInfinity($number)) {
        return $null
    }

    return $number
}

function Get-FiniteReferenceSortValue {
    param($Value)

    $number = Convert-FiniteDoubleOrNull -Value $Value
    if ($null -eq $number) {
        return [double]::PositiveInfinity
    }

    return [double]$number
}

function New-BestReferenceMatchSummary {
    param(
        [Parameter(Mandatory = $true)]
        [object[]]$CandidateReadbacks,

        [int]$TopCount = 5
    )

    if ($TopCount -le 0) {
        return @()
    }

    $rank = 0
    $sorted = @(
        $CandidateReadbacks |
            Where-Object { $null -ne $_.ReferenceMaxAbsDelta } |
            Sort-Object `
                @{ Expression = { if ($_.ReferenceMatchesReadback -eq $true) { 0 } else { 1 } }; Ascending = $true },
                @{ Expression = { Get-FiniteReferenceSortValue -Value $_.ReferenceMaxAbsDelta }; Ascending = $true },
                @{ Expression = { Get-FiniteReferenceSortValue -Value $_.ReferencePlanarDistance }; Ascending = $true },
                @{ Expression = { Get-FiniteReferenceSortValue -Value $_.ReferenceSpatialDistance }; Ascending = $true },
                @{ Expression = { [string]$_.CandidateId }; Ascending = $true } |
            Select-Object -First $TopCount
    )

    return @($sorted | ForEach-Object {
            $rank++
            $firstSample = @($_.DecodedSamples | Select-Object -First 1)
            [pscustomobject][ordered]@{
                Rank = $rank
                CandidateId = [string]$_.CandidateId
                CandidateAddressHex = [string]$_.CandidateAddressHex
                RegionAddressHex = [string]$_.RegionAddressHex
                CandidateOffsetInRegion = [int]$_.CandidateOffsetInRegion
                ReferenceMatchesReadback = if ($null -eq $_.ReferenceMatchesReadback) { $null } else { [bool]$_.ReferenceMatchesReadback }
                ReferenceMaxAbsDelta = Convert-FiniteDoubleOrNull -Value $_.ReferenceMaxAbsDelta
                ReferencePlanarDistance = Convert-FiniteDoubleOrNull -Value $_.ReferencePlanarDistance
                ReferenceSpatialDistance = Convert-FiniteDoubleOrNull -Value $_.ReferenceSpatialDistance
                StableAcrossReadbackSamples = [bool]$_.StableAcrossReadbackSamples
                MaxAbsDeltaFromSourcePreview = Convert-FiniteDoubleOrNull -Value $_.MaxAbsDeltaFromSourcePreview
                SourcePreviewTolerance = if ($null -eq $_.SourcePreviewTolerance) { $null } else { [double]$_.SourcePreviewTolerance }
                SourcePreviewComparisonKind = [string]$_.SourcePreviewComparisonKind
                SourcePreviewMatchesReadback = if ($null -eq $_.SourcePreviewMatchesReadback) { $null } else { [bool]$_.SourcePreviewMatchesReadback }
                DecodedSampleCount = [int]$_.DecodedSampleCount
                FirstDecodedSample = if ($firstSample.Count -eq 0) {
                    $null
                }
                else {
                    [pscustomobject][ordered]@{
                        SampleIndex = [int]$firstSample[0].SampleIndex
                        RecordedAtUtc = [string]$firstSample[0].RecordedAtUtc
                        X = Convert-FiniteDoubleOrNull -Value $firstSample[0].X
                        Y = Convert-FiniteDoubleOrNull -Value $firstSample[0].Y
                        Z = Convert-FiniteDoubleOrNull -Value $firstSample[0].Z
                    }
                }
            }
        })
}

function Get-CommandSummary {
    param($CommandResult)

    if ($null -eq $CommandResult) {
        return $null
    }

    return [pscustomobject][ordered]@{
        FilePath = $CommandResult.FilePath
        Arguments = @($CommandResult.Arguments)
        ExitCode = $CommandResult.ExitCode
        OutputPreview = if ([string]::IsNullOrWhiteSpace($CommandResult.Output)) { '' } else { $CommandResult.Output.Substring(0, [Math]::Min(2000, $CommandResult.Output.Length)) }
    }
}

if ($PassiveSamples -le 0) {
    throw "PassiveSamples must be greater than zero."
}

if ($PassiveIntervalMilliseconds -lt 0 -or $ReadbackIntervalMilliseconds -lt 0) {
    throw "Interval values must be zero or greater."
}

if ($PassiveMaxRegions -le 0 -or $PassiveMaxBytesPerRegion -le 0 -or $PassiveMaxTotalBytes -le 0) {
    throw "Passive capture limits must be greater than zero."
}

if ($TopCount -le 0 -or $ContextBytes -lt 0 -or $ReadbackSampleCount -le 0) {
    throw "TopCount and ReadbackSampleCount must be greater than zero; ContextBytes must be zero or greater."
}

if ($TopReferenceMatches -lt 0) {
    throw "TopReferenceMatches must be zero or greater."
}

if ($ProofAnchorMaxAgeSeconds -lt 0) {
    throw "ProofAnchorMaxAgeSeconds must be zero or greater."
}

$referenceCoordinate = Resolve-ReferenceCoordinate
$effectiveReferenceTolerance = if ($null -eq $referenceCoordinate) { [double]$ReferenceTolerance } else { [double]$referenceCoordinate.Tolerance }

$resolvedOutputRoot = [System.IO.Path]::GetFullPath($OutputRoot)
$resolvedReaderSessionRoot = [System.IO.Path]::GetFullPath($ReaderSessionRoot)
New-Item -ItemType Directory -Path $resolvedOutputRoot -Force | Out-Null
New-Item -ItemType Directory -Path $resolvedReaderSessionRoot -Force | Out-Null

if (-not [string]::IsNullOrWhiteSpace($DecodeOnlyWatchsetFile) -or -not [string]::IsNullOrWhiteSpace($DecodeOnlySamplesFile)) {
    if ([string]::IsNullOrWhiteSpace($DecodeOnlyWatchsetFile) -or [string]::IsNullOrWhiteSpace($DecodeOnlySamplesFile)) {
        throw "Decode-only mode requires both -DecodeOnlyWatchsetFile and -DecodeOnlySamplesFile."
    }

    $resolvedDecodeWatchsetFile = [System.IO.Path]::GetFullPath($DecodeOnlyWatchsetFile)
    $resolvedDecodeSamplesFile = [System.IO.Path]::GetFullPath($DecodeOnlySamplesFile)
    if (-not (Test-Path -LiteralPath $resolvedDecodeWatchsetFile)) {
        throw "Decode-only watchset file was not found: $resolvedDecodeWatchsetFile"
    }

    if (-not (Test-Path -LiteralPath $resolvedDecodeSamplesFile)) {
        throw "Decode-only samples file was not found: $resolvedDecodeSamplesFile"
    }

    $decodeWatchset = ConvertFrom-JsonCompat -Text (Get-Content -LiteralPath $resolvedDecodeWatchsetFile -Raw) -Depth 80
    $decodeCandidateReadbacks = @(New-CandidateReadbackSummary -Watchset $decodeWatchset -SamplesFile $resolvedDecodeSamplesFile -ReferenceCoordinate $referenceCoordinate -ReferenceTolerance $effectiveReferenceTolerance)
    $decodeBestReferenceMatches = @(New-BestReferenceMatchSummary -CandidateReadbacks $decodeCandidateReadbacks -TopCount $TopReferenceMatches)
    $decodeSourcePreviewMatchCount = @($decodeCandidateReadbacks | Where-Object { $null -ne $_.SourcePreviewMatchesReadback -and [bool]$_.SourcePreviewMatchesReadback }).Count
    $decodeReferenceMatchCount = @($decodeCandidateReadbacks | Where-Object { $null -ne $_.ReferenceMatchesReadback -and [bool]$_.ReferenceMatchesReadback }).Count
    $decodeWarnings = [System.Collections.Generic.List[string]]::new()
    if ($decodeReferenceMatchCount -gt 0 -and $decodeSourcePreviewMatchCount -eq 0) {
        $decodeWarnings.Add('SourcePreviewMatchesReadback compares against the historical candidate artifact value preview; false does not invalidate same-time ReferenceMatchesReadback=true evidence.') | Out-Null
    }

    $decodeSummary = [pscustomObject][ordered]@{
        SchemaVersion = 1
        Mode = 'riftscan-riftreader-readback-decode'
        GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
        ProcessName = [string](Get-JsonPropertyValue -InputObject $decodeWatchset -Names @('ProcessName', 'process_name'))
        ProcessId = Get-JsonPropertyValue -InputObject $decodeWatchset -Names @('ProcessId', 'process_id', 'pid')
        TargetWindowHandle = [string](Get-JsonPropertyValue -InputObject $decodeWatchset -Names @('TargetWindowHandle', 'target_window_handle', 'window_handle', 'hwnd'))
        NoCheatEngine = $true
        MovementSent = $false
        MovementAllowed = $false
        WatchsetFile = $resolvedDecodeWatchsetFile
        SamplesFile = $resolvedDecodeSamplesFile
        CandidateCount = [int]$decodeWatchset.CandidateCount
        DecodedCandidateCount = @($decodeCandidateReadbacks | Where-Object { $_.DecodedSampleCount -gt 0 }).Count
        StableDecodedCandidateCount = @($decodeCandidateReadbacks | Where-Object { [bool]$_.StableAcrossReadbackSamples }).Count
        SourcePreviewMatchCount = $decodeSourcePreviewMatchCount
        ReferenceCoordinate = $referenceCoordinate
        ReferenceMatchCount = $decodeReferenceMatchCount
        BestReferenceMatchLimit = $TopReferenceMatches
        BestReferenceMatchCount = $decodeBestReferenceMatches.Count
        BestReferenceMatches = @($decodeBestReferenceMatches)
        CandidateReadbacks = @($decodeCandidateReadbacks)
        CanonicalCoordSource = 'none-candidate-watchset-only'
        MovementGate = 'blocked_until_current_process_validated_coord_trace_anchor_or_equivalent_canonical_source'
        WarningCount = $decodeWarnings.Count
        Warnings = @($decodeWarnings.ToArray())
    }

    if (-not [string]::IsNullOrWhiteSpace($DecodeOnlyOutputFile)) {
        Write-Utf8Json -Path ([System.IO.Path]::GetFullPath($DecodeOnlyOutputFile)) -Value $decodeSummary
    }

    if ($Json) {
        $decodeSummary | ConvertTo-Json -Depth 32
        return
    }

    Write-Host 'RiftScan -> RiftReader readback decode complete.' -ForegroundColor Green
    Write-Host ("Candidates:      {0}" -f $decodeSummary.CandidateCount)
    Write-Host ("Decoded vec3:    {0}; stable={1}; source-preview-match={2}" -f $decodeSummary.DecodedCandidateCount, $decodeSummary.StableDecodedCandidateCount, $decodeSummary.SourcePreviewMatchCount)
    if ($null -ne $referenceCoordinate) {
        Write-Host ("Reference match: {0}; tolerance={1}" -f $decodeSummary.ReferenceMatchCount, $effectiveReferenceTolerance)
        if ($decodeSummary.BestReferenceMatchCount -gt 0) {
            $best = @($decodeSummary.BestReferenceMatches)[0]
            Write-Host ("Best reference:  {0}; max-delta={1:0.######}; match={2}" -f $best.CandidateId, [double]$best.ReferenceMaxAbsDelta, $best.ReferenceMatchesReadback)
        }
    }
    Write-Host 'Movement:        blocked'
    Write-Host 'CE usage:        none'
    return
}

$target = Resolve-TargetProcess
$targetProcess = $target.Process
$targetProcessId = [int]$targetProcess.Id
$targetHandleHex = Format-WindowHandle -Handle $target.Handle
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'

$riftScanCliProject = Join-Path $RiftScanRoot 'src\RiftScan.Cli\RiftScan.Cli.csproj'
if (-not (Test-Path -LiteralPath $riftScanCliProject) -and [string]::IsNullOrWhiteSpace($CandidateFile)) {
    throw "RiftScan CLI project was not found at '$riftScanCliProject'. Pass -RiftScanRoot or -CandidateFile."
}

$proofAnchorCommand = $null
$proofAnchorStatus = 'skipped'
$proofAnchorMovementAllowed = $false
$proofAnchorSource = $null
$proofAnchorIssues = @()
$proofAnchorWarnings = @()
$proofAnchorCandidateId = $null
$proofAnchorCandidateAddressHex = $null
$proofAnchorOutputPath = Join-Path $resolvedOutputRoot ("assert-current-proof-coord-anchor-currentpid-{0}-no-ce-wrapper-{1}.json" -f $targetProcessId, $stamp)
if (-not $SkipProofAnchorCheck) {
    $anchorArgs = @(
        '-ProcessId',
        $targetProcessId.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '-TargetWindowHandle',
        $targetHandleHex,
        '-MaxAgeSeconds',
        $ProofAnchorMaxAgeSeconds.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '-Json'
    )
    $proofAnchorCommand = Invoke-PowerShellScript -ScriptPath $proofAnchorScript -Arguments $anchorArgs -AllowFailure
    $proofAnchorCommand.Output | Set-Content -LiteralPath $proofAnchorOutputPath -Encoding UTF8
    $proofAnchor = $null
    try {
        $proofAnchor = ConvertFrom-JsonCompat -Text $proofAnchorCommand.Output
    }
    catch {
        $proofAnchorStatus = if ($proofAnchorCommand.ExitCode -eq 0) { 'unparseable' } else { 'failed' }
    }

    if ($null -ne $proofAnchor) {
        $statusValue = Get-JsonPropertyValue -InputObject $proofAnchor -Names @('Status')
        $proofAnchorStatus = [string]$statusValue
        if ([string]::IsNullOrWhiteSpace($proofAnchorStatus)) {
            $proofAnchorStatus = if ($proofAnchorCommand.ExitCode -eq 0) { 'unknown' } else { 'failed' }
        }

        $movementAllowedValue = Get-JsonPropertyValue -InputObject $proofAnchor -Names @('MovementAllowed')
        $proofAnchorMovementAllowed = $null -ne $movementAllowedValue -and [bool]$movementAllowedValue
        $proofAnchorSource = [string](Get-JsonPropertyValue -InputObject $proofAnchor -Names @('AnchorSource'))
        $issuesValue = Get-JsonPropertyValue -InputObject $proofAnchor -Names @('Issues')
        $proofAnchorIssues = if ($null -eq $issuesValue) { @() } else { @($issuesValue) }
        $warningsValue = Get-JsonPropertyValue -InputObject $proofAnchor -Names @('Warnings')
        $proofAnchorWarnings = if ($null -eq $warningsValue) { @() } else { @($warningsValue) }

        $proofAnchorDocument = Get-JsonPropertyValue -InputObject $proofAnchor -Names @('Anchor')
        $proofAnchorEvidence = Get-JsonPropertyValue -InputObject $proofAnchorDocument -Names @('Evidence')
        $proofAnchorCandidateId = [string](Get-JsonPropertyValue -InputObject $proofAnchorEvidence -Names @('CandidateId'))
        $proofAnchorCandidateAddressHex = [string](Get-JsonPropertyValue -InputObject $proofAnchorEvidence -Names @('CandidateAddressHex'))
    }
}

$captureCommand = $null
$verifyCommand = $null
$analyzeCommand = $null
$riftscanSessionPath = $null
$sourceCandidateFile = $CandidateFile

if ([string]::IsNullOrWhiteSpace($sourceCandidateFile)) {
    $riftscanSessionPath = Join-Path ([System.IO.Path]::GetFullPath((Join-Path $RiftScanRoot 'sessions'))) ("riftreader-currentpid-{0}-passive-noinput-{1}" -f $targetProcessId, $stamp)
    $captureArgs = @(
        'run',
        '--project',
        $riftScanCliProject,
        '--',
        'capture',
        'passive',
        '--pid',
        $targetProcessId.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '--process',
        $ProcessName,
        '--out',
        $riftscanSessionPath,
        '--samples',
        $PassiveSamples.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '--interval-ms',
        $PassiveIntervalMilliseconds.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '--max-regions',
        $PassiveMaxRegions.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '--max-bytes-per-region',
        $PassiveMaxBytesPerRegion.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '--max-total-bytes',
        $PassiveMaxTotalBytes.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '--stimulus',
        'passive_idle',
        '--stimulus-note',
        'riftreader_riftscan_readback_wrapper_no_ce_no_input'
    )
    $captureCommand = Invoke-ExternalCommand -FilePath 'dotnet' -Arguments $captureArgs -WorkingDirectory $RiftScanRoot

    $verifyCommand = Invoke-ExternalCommand -FilePath 'dotnet' -Arguments @(
        'run',
        '--project',
        $riftScanCliProject,
        '--',
        'verify',
        'session',
        $riftscanSessionPath
    ) -WorkingDirectory $RiftScanRoot

    $analyzeCommand = Invoke-ExternalCommand -FilePath 'dotnet' -Arguments @(
        'run',
        '--project',
        $riftScanCliProject,
        '--',
        'analyze',
        'session',
        $riftscanSessionPath,
        '--top',
        '100'
    ) -WorkingDirectory $RiftScanRoot

    $sourceCandidateFile = Join-Path $riftscanSessionPath 'vec3_candidates.jsonl'
}
else {
    $sourceCandidateFile = [System.IO.Path]::GetFullPath($sourceCandidateFile)
}

if (-not (Test-Path -LiteralPath $sourceCandidateFile)) {
    throw "RiftScan candidate file was not found: $sourceCandidateFile"
}

$watchsetPath = Join-Path $resolvedOutputRoot ("riftscan-currentpid-{0}-passive-vec3-watchset-{1}.json" -f $targetProcessId, $stamp)
$importCommand = Invoke-PowerShellScript -ScriptPath $importerScript -Arguments @(
    '-CandidateFile',
    $sourceCandidateFile,
    '-OutputFile',
    $watchsetPath,
    '-ProcessId',
    $targetProcessId.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '-TargetWindowHandle',
    $targetHandleHex,
    '-TopCount',
    $TopCount.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '-ContextBytes',
    $ContextBytes.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '-Json'
)

$watchset = ConvertFrom-JsonCompat -Text (Get-Content -LiteralPath $watchsetPath -Raw) -Depth 80
$readbackSessionPath = Join-Path $resolvedReaderSessionRoot ("riftscan-currentpid-{0}-passive-vec3-readback-{1}" -f $targetProcessId, $stamp)
$readbackCommand = Invoke-ExternalCommand -FilePath 'dotnet' -Arguments @(
    'run',
    '--project',
    $readerProject,
    '--',
    '--pid',
    $targetProcessId.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '--record-session',
    '--session-watchset-file',
    $watchsetPath,
    '--session-output-directory',
    $readbackSessionPath,
    '--session-sample-count',
    $ReadbackSampleCount.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '--session-interval-ms',
    $ReadbackIntervalMilliseconds.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '--session-label',
    'riftscan_currentpid_passive_vec3_no_input',
    '--json'
) -WorkingDirectory $repoRoot

$manifestPath = Join-Path $readbackSessionPath 'recording-manifest.json'
$manifest = ConvertFrom-JsonCompat -Text (Get-Content -LiteralPath $manifestPath -Raw) -Depth 80
$samplesPath = Join-Path $readbackSessionPath 'samples.ndjson'
$candidateReadbacks = @(New-CandidateReadbackSummary -Watchset $watchset -SamplesFile $samplesPath -ReferenceCoordinate $referenceCoordinate -ReferenceTolerance $effectiveReferenceTolerance)
$decodedCandidateCount = @($candidateReadbacks | Where-Object { $_.DecodedSampleCount -gt 0 }).Count
$stableDecodedCandidateCount = @($candidateReadbacks | Where-Object { [bool]$_.StableAcrossReadbackSamples }).Count
$sourcePreviewMatchCount = @($candidateReadbacks | Where-Object { $null -ne $_.SourcePreviewMatchesReadback -and [bool]$_.SourcePreviewMatchesReadback }).Count
$referenceMatchCount = @($candidateReadbacks | Where-Object { $null -ne $_.ReferenceMatchesReadback -and [bool]$_.ReferenceMatchesReadback }).Count
$bestReferenceMatches = @(New-BestReferenceMatchSummary -CandidateReadbacks $candidateReadbacks -TopCount $TopReferenceMatches)

$proofAnchorCandidateReadback = $null
if (-not [string]::IsNullOrWhiteSpace($proofAnchorCandidateId)) {
    $anchorCandidateReadback = @($candidateReadbacks | Where-Object { [string]::Equals([string]$_.CandidateId, $proofAnchorCandidateId, [System.StringComparison]::OrdinalIgnoreCase) } | Select-Object -First 1)
    $anchorReadbackIssues = [System.Collections.Generic.List[string]]::new()
    if ($anchorCandidateReadback.Count -eq 0) {
        $anchorReadbackIssues.Add('proof_anchor_candidate_not_found_in_current_readback') | Out-Null
    }

    $anchorCandidate = if ($anchorCandidateReadback.Count -eq 0) { $null } else { $anchorCandidateReadback[0] }
    $decodedSamples = if ($null -eq $anchorCandidate) { @() } else { @($anchorCandidate.DecodedSamples) }
    $decodedSamples = @($decodedSamples)
    $firstDecodedSample = if ($decodedSamples.Count -eq 0) { $null } else { $decodedSamples[0] }
    $addressMatches = $false
    if ($null -ne $anchorCandidate -and -not [string]::IsNullOrWhiteSpace($proofAnchorCandidateAddressHex)) {
        $addressMatches = [string]::Equals([string]$anchorCandidate.CandidateAddressHex, $proofAnchorCandidateAddressHex, [System.StringComparison]::OrdinalIgnoreCase)
        if (-not $addressMatches) {
            $anchorReadbackIssues.Add('proof_anchor_candidate_address_mismatch') | Out-Null
        }
    }

    if ($null -ne $anchorCandidate -and -not [bool]$anchorCandidate.StableAcrossReadbackSamples) {
        $anchorReadbackIssues.Add('proof_anchor_candidate_not_stable_across_current_readback_samples') | Out-Null
    }

    if ($null -ne $anchorCandidate -and $decodedSamples.Count -eq 0) {
        $anchorReadbackIssues.Add('proof_anchor_candidate_has_no_decoded_current_readback_sample') | Out-Null
    }

    if (-not [string]::Equals([string]$manifest.IntegrityStatus, 'ok', [System.StringComparison]::OrdinalIgnoreCase)) {
        $anchorReadbackIssues.Add('readback_integrity_not_ok') | Out-Null
    }

    if ([int]$manifest.TotalRegionReadFailures -ne 0) {
        $anchorReadbackIssues.Add('readback_region_failures_present') | Out-Null
    }

    $proofAnchorCandidateReadbackSupportsAnchor = (
        $proofAnchorMovementAllowed -and
        $null -ne $anchorCandidate -and
        $decodedSamples.Count -gt 0 -and
        [bool]$anchorCandidate.StableAcrossReadbackSamples -and
        $addressMatches -and
        [string]::Equals([string]$manifest.IntegrityStatus, 'ok', [System.StringComparison]::OrdinalIgnoreCase) -and
        [int]$manifest.TotalRegionReadFailures -eq 0
    )

    $proofAnchorCandidateReadback = [pscustomobject][ordered]@{
        CandidateId = $proofAnchorCandidateId
        CandidateFound = $null -ne $anchorCandidate
        ProofAnchorCandidateAddressHex = $proofAnchorCandidateAddressHex
        ReadbackCandidateAddressHex = if ($null -eq $anchorCandidate) { $null } else { [string]$anchorCandidate.CandidateAddressHex }
        AddressMatchesProofAnchor = $addressMatches
        StableAcrossReadbackSamples = if ($null -eq $anchorCandidate) { $null } else { [bool]$anchorCandidate.StableAcrossReadbackSamples }
        DecodedSampleCount = if ($null -eq $anchorCandidate) { 0 } else { [int]$anchorCandidate.DecodedSampleCount }
        MaxAbsDeltaAcrossReadbackSamples = if ($null -eq $anchorCandidate) { $null } else { $anchorCandidate.MaxAbsDeltaAcrossReadbackSamples }
        CurrentCoordinate = if ($null -eq $firstDecodedSample) {
            $null
        }
        else {
            [pscustomobject][ordered]@{
                X = [double]$firstDecodedSample.X
                Y = [double]$firstDecodedSample.Y
                Z = [double]$firstDecodedSample.Z
                RecordedAtUtc = [string]$firstDecodedSample.RecordedAtUtc
            }
        }
        ReadbackIntegrityStatus = [string]$manifest.IntegrityStatus
        ReadbackTotalRegionReadFailures = [int]$manifest.TotalRegionReadFailures
        SupportsProofAnchor = $proofAnchorCandidateReadbackSupportsAnchor
        Issues = @($anchorReadbackIssues.ToArray())
    }
}

$proofAnchorCandidateReadbackSupportsAnchor = $null -ne $proofAnchorCandidateReadback -and [bool]$proofAnchorCandidateReadback.SupportsProofAnchor
$canonicalCoordSource = if ($proofAnchorCandidateReadbackSupportsAnchor) { 'proof-anchor-preflight-validated-current-readback' } elseif ($proofAnchorMovementAllowed) { 'proof-anchor-preflight-validated' } else { 'none-candidate-watchset-only' }
$movementGate = if ($proofAnchorMovementAllowed) { 'satisfied_by_current_process_proof_coord_anchor_preflight' } else { 'blocked_until_current_process_validated_coord_trace_anchor_or_equivalent_canonical_source' }
$warnings = [System.Collections.Generic.List[string]]::new()
$warnings.Add('This wrapper uses no Cheat Engine path.') | Out-Null
$warnings.Add('This wrapper sends no input and performs no movement.') | Out-Null
$warnings.Add('RiftScan candidates are candidate evidence only unless the proof-anchor preflight is valid.') | Out-Null
if ($proofAnchorCandidateReadbackSupportsAnchor) {
    $warnings.Add('The proof-anchor candidate was found in the current readback and decoded as a stable coordinate triplet.') | Out-Null
}
if ($proofAnchorMovementAllowed) {
    $warnings.Add('Movement polling gate is satisfied by the current-process proof-anchor preflight; candidate readback remains supporting evidence.') | Out-Null
}
else {
    $warnings.Add('Fresh candidate readback does not satisfy RiftReader movement polling invariants by itself.') | Out-Null
    $warnings.Add('Movement remains blocked unless a current-process canonical coord-trace proof anchor or validated equivalent is separately validated.') | Out-Null
}
foreach ($proofAnchorWarning in @($proofAnchorWarnings)) {
    if (-not [string]::IsNullOrWhiteSpace([string]$proofAnchorWarning)) {
        $warnings.Add(("Proof anchor preflight: {0}" -f [string]$proofAnchorWarning)) | Out-Null
    }
}
if ($referenceMatchCount -gt 0 -and $sourcePreviewMatchCount -eq 0) {
    $warnings.Add('SourcePreviewMatchesReadback compares against the historical candidate artifact value preview; false does not invalidate same-time ReferenceMatchesReadback=true evidence.') | Out-Null
}

$summaryPath = Join-Path $resolvedOutputRoot ("riftscan-riftreader-currentpid-{0}-readback-wrapper-summary-{1}.json" -f $targetProcessId, $stamp)
$summary = [pscustomobject][ordered]@{
    SchemaVersion = 1
    Mode = 'riftscan-riftreader-coordinate-readback'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
    ProcessName = $ProcessName
    ProcessId = $targetProcessId
    TargetWindowHandle = $targetHandleHex
    NoCheatEngine = $true
    MovementSent = $false
    MovementAllowed = $proofAnchorMovementAllowed
    ProofAnchorStatus = $proofAnchorStatus
    ProofAnchorMovementAllowed = $proofAnchorMovementAllowed
    ProofAnchorSource = $proofAnchorSource
    ProofAnchorMaxAgeSeconds = $ProofAnchorMaxAgeSeconds
    ProofAnchorIssues = @($proofAnchorIssues)
    ProofAnchorWarnings = @($proofAnchorWarnings)
    ProofAnchorCandidateId = $proofAnchorCandidateId
    ProofAnchorCandidateAddressHex = $proofAnchorCandidateAddressHex
    ProofAnchorCandidateReadback = $proofAnchorCandidateReadback
    ProofAnchorFile = if ($SkipProofAnchorCheck) { $null } else { $proofAnchorOutputPath }
    SourceCandidateFile = $sourceCandidateFile
    RiftScanSessionPath = $riftscanSessionPath
    WatchsetFile = $watchsetPath
    ReadbackSessionPath = $readbackSessionPath
    ReadbackManifestFile = $manifestPath
    ReadbackSamplesFile = $samplesPath
    CandidateCount = [int]$watchset.CandidateCount
    ReadbackIntegrityStatus = [string]$manifest.IntegrityStatus
    ReadbackRecordedSampleCount = [int]$manifest.RecordedSampleCount
    ReadbackTotalBytesRead = [int64]$manifest.TotalBytesRead
    ReadbackTotalRegionReadFailures = [int]$manifest.TotalRegionReadFailures
    DecodedCandidateCount = $decodedCandidateCount
    StableDecodedCandidateCount = $stableDecodedCandidateCount
    SourcePreviewMatchCount = $sourcePreviewMatchCount
    ReferenceCoordinate = $referenceCoordinate
    ReferenceMatchCount = $referenceMatchCount
    BestReferenceMatchLimit = $TopReferenceMatches
    BestReferenceMatchCount = $bestReferenceMatches.Count
    BestReferenceMatches = @($bestReferenceMatches)
    CandidateReadbacks = @($candidateReadbacks)
    CanonicalCoordSource = $canonicalCoordSource
    MovementGate = $movementGate
    SummaryFile = $summaryPath
    WarningCount = $warnings.Count
    Warnings = @($warnings.ToArray())
    Commands = [pscustomobject][ordered]@{
        ProofAnchor = Get-CommandSummary -CommandResult $proofAnchorCommand
        RiftScanCapture = Get-CommandSummary -CommandResult $captureCommand
        RiftScanVerify = Get-CommandSummary -CommandResult $verifyCommand
        RiftScanAnalyze = Get-CommandSummary -CommandResult $analyzeCommand
        Import = Get-CommandSummary -CommandResult $importCommand
        Readback = Get-CommandSummary -CommandResult $readbackCommand
    }
}

Write-Utf8Json -Path $summaryPath -Value $summary

if ($Json) {
    Get-Content -LiteralPath $summaryPath -Raw
    return
}

Write-Host 'RiftScan -> RiftReader coordinate candidate readback complete.' -ForegroundColor Green
Write-Host ("PID/HWND:        {0} / {1}" -f $targetProcessId, $targetHandleHex)
Write-Host ("Proof anchor:    {0}" -f $proofAnchorStatus)
Write-Host ("Proof gate:      {0}" -f $(if ($proofAnchorMovementAllowed) { 'allowed' } else { 'blocked' }))
Write-Host ("Candidates:      {0}" -f $watchset.CandidateCount)
Write-Host ("Readback:        {0}; failures={1}; bytes={2}" -f $manifest.IntegrityStatus, $manifest.TotalRegionReadFailures, $manifest.TotalBytesRead)
Write-Host ("Decoded vec3:    {0}; stable={1}; source-preview-match={2}" -f $decodedCandidateCount, $stableDecodedCandidateCount, $sourcePreviewMatchCount)
if ($null -ne $referenceCoordinate) {
    Write-Host ("Reference match: {0}; tolerance={1}" -f $referenceMatchCount, $effectiveReferenceTolerance)
    if ($bestReferenceMatches.Count -gt 0) {
        $best = $bestReferenceMatches[0]
        Write-Host ("Best reference:  {0}; max-delta={1:0.######}; match={2}" -f $best.CandidateId, [double]$best.ReferenceMaxAbsDelta, $best.ReferenceMatchesReadback)
    }
}
Write-Host ("Summary:         {0}" -f $summaryPath)
Write-Host 'Movement:        no input sent'
Write-Host 'CE usage:        none'
