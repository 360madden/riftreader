[CmdletBinding()]
param(
    [string]$ProcessName = 'rift_x64',
    [int]$ProcessId,
    [int]$RefreshAttempts = 2,
    [int]$TraceReferenceMaxAgeSeconds = 15,
    [switch]$SkipRefresh,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$traceScript = Join-Path $PSScriptRoot 'trace-player-coord-write.ps1'

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

    return ($output -join [Environment]::NewLine) | ConvertFrom-Json -Depth 32
}

function Get-ReaderTargetArguments {
    param(
        [int]$ResolvedProcessId,
        [Parameter(Mandatory = $true)]
        [string]$ResolvedProcessName
    )

    if ($ResolvedProcessId -gt 0) {
        return @('--pid', $ResolvedProcessId.ToString([System.Globalization.CultureInfo]::InvariantCulture))
    }

    return @('--process-name', $ResolvedProcessName)
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

function Convert-HexStringToByteArray {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Hex
    )

    $normalized = ($Hex -replace '\s+', '').Trim()
    if ([string]::IsNullOrWhiteSpace($normalized) -or ($normalized.Length % 2) -ne 0) {
        return $null
    }

    $bytes = New-Object byte[] ($normalized.Length / 2)
    for ($index = 0; $index -lt $bytes.Length; $index++) {
        $bytes[$index] = [Convert]::ToByte($normalized.Substring($index * 2, 2), 16)
    }

    return $bytes
}

function Test-IsFiniteNumber {
    param(
        $Value
    )

    if ($null -eq $Value) {
        return $false
    }

    $doubleValue = [double]$Value
    return -not ([double]::IsNaN($doubleValue) -or [double]::IsInfinity($doubleValue))
}

function Test-IsUsableCoordSample {
    param(
        [Parameter(Mandatory = $true)]
        $Sample
    )

    if ($null -eq $Sample) {
        return $false
    }

    foreach ($coordName in @('CoordX', 'CoordY', 'CoordZ')) {
        if (-not (Test-IsFiniteNumber -Value $Sample.$coordName)) {
            return $false
        }
    }

    return $true
}

function New-ReferenceCoordMatch {
    param(
        [Parameter(Mandatory = $true)]
        $Sample,

        [Parameter(Mandatory = $true)]
        [double]$ReferenceCoordX,

        [Parameter(Mandatory = $true)]
        [double]$ReferenceCoordY,

        [Parameter(Mandatory = $true)]
        [double]$ReferenceCoordZ,

        [Parameter(Mandatory = $true)]
        [string]$ReferenceSource,

        [string]$ReferenceCapturedAtUtc,

        [double]$ReferenceAgeSeconds
    )

    if (-not (Test-IsUsableCoordSample -Sample $Sample)) {
        return $null
    }

    $deltaX = [double]$Sample.CoordX - $ReferenceCoordX
    $deltaY = [double]$Sample.CoordY - $ReferenceCoordY
    $deltaZ = [double]$Sample.CoordZ - $ReferenceCoordZ

    return [pscustomobject]@{
        CoordMatchesWithinTolerance = (
            [Math]::Abs($deltaX) -le 0.25 -and
            [Math]::Abs($deltaY) -le 0.25 -and
            [Math]::Abs($deltaZ) -le 0.25
        )
        DeltaX = [float]$deltaX
        DeltaY = [float]$deltaY
        DeltaZ = [float]$deltaZ
        ReferenceSource = $ReferenceSource
        ReferenceCapturedAtUtc = $ReferenceCapturedAtUtc
        ReferenceAgeSeconds = $ReferenceAgeSeconds
    }
}

function Parse-DateTimeOffsetOrNull {
    param(
        $Value
    )

    if ([string]::IsNullOrWhiteSpace([string]$Value)) {
        return $null
    }

    try {
        return [DateTimeOffset]::Parse([string]$Value, [System.Globalization.CultureInfo]::InvariantCulture)
    }
    catch {
        return $null
    }
}

function Get-TraceEpochReference {
    param(
        [string]$TraceSourceFile
    )

    if ([string]::IsNullOrWhiteSpace($TraceSourceFile) -or -not (Test-Path -LiteralPath $TraceSourceFile)) {
        return $null
    }

    try {
        $traceDocument = Get-Content -LiteralPath $TraceSourceFile -Raw | ConvertFrom-Json -Depth 40
    }
    catch {
        return $null
    }

    $referenceCandidates = @(
        [pscustomobject]@{
            Source = 'post-trace-reader'
            CapturedAtUtc = $traceDocument.PostTraceReaderCapturedAtUtc
            Snapshot = $traceDocument.PostTraceReader
        },
        [pscustomobject]@{
            Source = 'trace-reader'
            CapturedAtUtc = $traceDocument.GeneratedAtUtc
            Snapshot = $traceDocument.Reader
        }
    )

    foreach ($candidate in $referenceCandidates) {
        if ($null -eq $candidate.Snapshot) {
            continue
        }

        $capturedAt = Parse-DateTimeOffsetOrNull -Value $candidate.CapturedAtUtc
        if ($null -eq $capturedAt) {
            continue
        }

        $ageSeconds = [Math]::Abs(([DateTimeOffset]::UtcNow - $capturedAt.ToUniversalTime()).TotalSeconds)
        if ($ageSeconds -gt $TraceReferenceMaxAgeSeconds) {
            continue
        }

        $referenceSample = $null
        $referenceAddressHex = $null
        if ($candidate.Snapshot.PSObject.Properties['Memory']) {
            $referenceSample = $candidate.Snapshot.Memory
            if ($candidate.Snapshot.Memory.PSObject.Properties['AddressHex']) {
                $referenceAddressHex = [string]$candidate.Snapshot.Memory.AddressHex
            }
        }

        if (-not (Test-IsUsableCoordSample -Sample $referenceSample) -and $candidate.Snapshot.PSObject.Properties['Expected']) {
            $referenceSample = $candidate.Snapshot.Expected
        }

        if (-not (Test-IsUsableCoordSample -Sample $referenceSample)) {
            continue
        }

        return [pscustomobject]@{
            Source = [string]$candidate.Source
            CapturedAtUtc = $capturedAt.ToString('O')
            AgeSeconds = $ageSeconds
            CoordX = [double]$referenceSample.CoordX
            CoordY = [double]$referenceSample.CoordY
            CoordZ = [double]$referenceSample.CoordZ
            AddressHex = $referenceAddressHex
            TraceSourceFile = $TraceSourceFile
        }
    }

    return $null
}

function New-TraceEpochMatch {
    param(
        [Parameter(Mandatory = $true)]
        $Sample,

        $TraceReference
    )

    if (-not (Test-IsUsableCoordSample -Sample $Sample) -or $null -eq $TraceReference) {
        return $null
    }

    return New-ReferenceCoordMatch `
        -Sample $Sample `
        -ReferenceCoordX ([double]$TraceReference.CoordX) `
        -ReferenceCoordY ([double]$TraceReference.CoordY) `
        -ReferenceCoordZ ([double]$TraceReference.CoordZ) `
        -ReferenceSource ([string]$TraceReference.Source) `
        -ReferenceCapturedAtUtc ([string]$TraceReference.CapturedAtUtc) `
        -ReferenceAgeSeconds ([double]$TraceReference.AgeSeconds)
}

function New-LiveReaderMatch {
    param(
        [Parameter(Mandatory = $true)]
        $Sample,

        $Expected
    )

    if ($null -eq $Expected) {
        return $null
    }

    foreach ($coordName in @('CoordX', 'CoordY', 'CoordZ')) {
        if (-not (Test-IsFiniteNumber -Value $Expected.$coordName)) {
            return $null
        }
    }

    return New-ReferenceCoordMatch `
        -Sample $Sample `
        -ReferenceCoordX ([double]$Expected.CoordX) `
        -ReferenceCoordY ([double]$Expected.CoordY) `
        -ReferenceCoordZ ([double]$Expected.CoordZ) `
        -ReferenceSource 'readerbridge-live' `
        -ReferenceCapturedAtUtc $null `
        -ReferenceAgeSeconds 0
}

function Read-DirectCoordRegionSample {
    param(
        [Parameter(Mandatory = $true)]
        [string]$AddressHex
    )

    $memoryRead = Invoke-ReaderJson -Arguments @(
        (Get-ReaderTargetArguments -ResolvedProcessId $ProcessId -ResolvedProcessName $ProcessName) +
        @('--address', $AddressHex, '--length', '12', '--json')
    )

    if ($null -eq $memoryRead -or [string]::IsNullOrWhiteSpace([string]$memoryRead.BytesHex)) {
        return $null
    }

    $bytes = Convert-HexStringToByteArray -Hex ([string]$memoryRead.BytesHex)
    if ($null -eq $bytes -or $bytes.Length -lt 12) {
        return $null
    }

    return [pscustomobject]@{
        AddressHex = $AddressHex
        CoordX = [BitConverter]::ToSingle($bytes, 0)
        CoordY = [BitConverter]::ToSingle($bytes, 4)
        CoordZ = [BitConverter]::ToSingle($bytes, 8)
    }
}

function Resolve-ProofCoordSelection {
    param(
        [Parameter(Mandatory = $true)]
        $Anchor,

        $TraceReference,

        [ref]$Reason
    )

    $Reason.Value = $null

    if ($null -eq $Anchor) {
        $Reason.Value = 'Anchor result was null.'
        return $null
    }

    if (-not $Anchor.TraceMatchesProcess) {
        $Reason.Value = 'Coord-trace anchor does not match the current live process.'
        return $null
    }

    $directReason = $null
    $primaryReason = $null
    $sourceReason = $null

    $traceEpochRegionReason = $null
    if ($null -ne $TraceReference -and -not [string]::IsNullOrWhiteSpace([string]$TraceReference.AddressHex)) {
        try {
            $traceEpochRegionSample = Read-DirectCoordRegionSample -AddressHex ([string]$TraceReference.AddressHex)
            $traceEpochRegionMatch = New-TraceEpochMatch -Sample $traceEpochRegionSample -TraceReference $TraceReference

            if (-not (Test-IsUsableCoordSample -Sample $traceEpochRegionSample)) {
                $traceEpochRegionReason = 'Trace-epoch current-player region did not expose a finite live coord sample.'
            }
            elseif ($null -ne $traceEpochRegionMatch -and $traceEpochRegionMatch.CoordMatchesWithinTolerance) {
                return [ordered]@{
                    CoordSourceKind = 'trace-epoch-current-player-region'
                    ObjectBaseAddress = [string]$TraceReference.AddressHex
                    CoordXRelativeOffset = 0
                    CoordYRelativeOffset = 4
                    CoordZRelativeOffset = 8
                    LevelRelativeOffset = $null
                    HealthRelativeOffset = $null
                    MemorySample = $traceEpochRegionSample
                    Match = $traceEpochRegionMatch
                    MatchSource = 'trace-epoch'
                }
            }
            else {
                $traceEpochRegionReason = 'Trace-epoch current-player region does not still match the fresh trace-epoch snapshot within tolerance.'
            }
        }
        catch {
            $traceEpochRegionReason = "Trace-epoch current-player region read failed: $($_.Exception.Message)"
        }
    }
    else {
        $traceEpochRegionReason = 'Trace-epoch snapshot did not expose a reusable current-player region address.'
    }

    $directRegionAddress = $null
    if (-not [string]::IsNullOrWhiteSpace([string]$Anchor.TargetAddress)) {
        $directRegionAddress = [string]$Anchor.TargetAddress
    }
    elseif (-not [string]::IsNullOrWhiteSpace([string]$Anchor.CandidateAddress)) {
        $directRegionAddress = [string]$Anchor.CandidateAddress
    }

    if (-not [string]::IsNullOrWhiteSpace($directRegionAddress)) {
        try {
            $directSample = Read-DirectCoordRegionSample -AddressHex $directRegionAddress
            $directLiveMatch = New-LiveReaderMatch -Sample $directSample -Expected $Anchor.Expected
            $directTraceEpochMatch = New-TraceEpochMatch -Sample $directSample -TraceReference $TraceReference

            if (-not (Test-IsUsableCoordSample -Sample $directSample)) {
                $directReason = 'Direct traced coord region did not expose a finite live coord sample.'
            }
            elseif ($null -ne $directLiveMatch -and $directLiveMatch.CoordMatchesWithinTolerance) {
                return [ordered]@{
                    CoordSourceKind = 'coord-trace-direct-region'
                    ObjectBaseAddress = $directRegionAddress
                    CoordXRelativeOffset = 0
                    CoordYRelativeOffset = 4
                    CoordZRelativeOffset = 8
                    LevelRelativeOffset = $null
                    HealthRelativeOffset = $null
                    MemorySample = $directSample
                    Match = $directLiveMatch
                    MatchSource = 'readerbridge-live'
                }
            }
            elseif ($null -ne $directTraceEpochMatch -and $directTraceEpochMatch.CoordMatchesWithinTolerance) {
                return [ordered]@{
                    CoordSourceKind = 'coord-trace-direct-region'
                    ObjectBaseAddress = $directRegionAddress
                    CoordXRelativeOffset = 0
                    CoordYRelativeOffset = 4
                    CoordZRelativeOffset = 8
                    LevelRelativeOffset = $null
                    HealthRelativeOffset = $null
                    MemorySample = $directSample
                    Match = $directTraceEpochMatch
                    MatchSource = 'trace-epoch'
                }
            }
            else {
                $directReason = 'Direct traced coord region does not match either live ReaderBridge coords or the fresh trace-epoch snapshot within tolerance.'
            }
        }
        catch {
            $directReason = "Direct traced coord region read failed: $($_.Exception.Message)"
        }
    }
    else {
        $directReason = 'Coord-trace anchor did not expose a direct traced region address.'
    }

    if ([string]::IsNullOrWhiteSpace([string]$Anchor.ObjectBaseAddress)) {
        $primaryReason = 'Coord-trace anchor did not expose an object base address.'
    }
    elseif ($null -eq $Anchor.CoordXRelativeOffset -or $null -eq $Anchor.CoordYRelativeOffset -or $null -eq $Anchor.CoordZRelativeOffset) {
        $primaryReason = 'Coord-trace anchor did not expose a full coord offset triplet.'
    }
    else {
        $coordXOffset = [int]$Anchor.CoordXRelativeOffset
        $coordYOffset = [int]$Anchor.CoordYRelativeOffset
        $coordZOffset = [int]$Anchor.CoordZRelativeOffset
        $primaryTraceEpochMatch = New-TraceEpochMatch -Sample $Anchor.MemorySample -TraceReference $TraceReference
        if ((($coordYOffset - $coordXOffset) -ne 4) -or (($coordZOffset - $coordYOffset) -ne 4)) {
            $primaryReason = "Coord-trace anchor offsets are not a contiguous float triplet: [$coordXOffset, $coordYOffset, $coordZOffset]."
        }
        elseif (-not (Test-IsUsableCoordSample -Sample $Anchor.MemorySample)) {
            $primaryReason = 'Coord-trace anchor did not expose a finite live memory sample.'
        }
        elseif ($null -ne $Anchor.Match -and $Anchor.Match.CoordMatchesWithinTolerance) {
            return [ordered]@{
                CoordSourceKind = 'coord-trace-object'
                ObjectBaseAddress = [string]$Anchor.ObjectBaseAddress
                CoordXRelativeOffset = $coordXOffset
                CoordYRelativeOffset = $coordYOffset
                CoordZRelativeOffset = $coordZOffset
                LevelRelativeOffset = $Anchor.LevelRelativeOffset
                HealthRelativeOffset = $Anchor.HealthRelativeOffset
                MemorySample = $Anchor.MemorySample
                Match = $Anchor.Match
                MatchSource = 'readerbridge-live'
            }
        }
        elseif ($null -ne $primaryTraceEpochMatch -and $primaryTraceEpochMatch.CoordMatchesWithinTolerance) {
            return [ordered]@{
                CoordSourceKind = 'coord-trace-object'
                ObjectBaseAddress = [string]$Anchor.ObjectBaseAddress
                CoordXRelativeOffset = $coordXOffset
                CoordYRelativeOffset = $coordYOffset
                CoordZRelativeOffset = $coordZOffset
                LevelRelativeOffset = $Anchor.LevelRelativeOffset
                HealthRelativeOffset = $Anchor.HealthRelativeOffset
                MemorySample = $Anchor.MemorySample
                Match = $primaryTraceEpochMatch
                MatchSource = 'trace-epoch'
            }
        }
        else {
            $primaryReason = 'Coord-trace anchor does not match either live ReaderBridge coords or the fresh trace-epoch snapshot within tolerance.'
        }
    }

    if ([string]::IsNullOrWhiteSpace([string]$Anchor.SourceObjectAddress)) {
        $sourceReason = 'Coord-trace anchor did not expose a source object address.'
    }
    elseif ($null -eq $Anchor.SourceCoordRelativeOffset) {
        $sourceReason = 'Coord-trace anchor did not expose a source coord relative offset.'
    }
    else {
        $sourceCoordXOffset = [int]$Anchor.SourceCoordRelativeOffset
        $sourceCoordYOffset = $sourceCoordXOffset + 4
        $sourceCoordZOffset = $sourceCoordXOffset + 8
        $sourceTraceEpochMatch = New-TraceEpochMatch -Sample $Anchor.SourceObjectSample -TraceReference $TraceReference

        if (-not (Test-IsUsableCoordSample -Sample $Anchor.SourceObjectSample)) {
            $sourceReason = 'Coord-trace source object did not expose a finite live coord sample.'
        }
        elseif ($null -ne $Anchor.SourceObjectMatch -and $Anchor.SourceObjectMatch.CoordMatchesWithinTolerance) {
            return [ordered]@{
                CoordSourceKind = 'coord-trace-source-object'
                ObjectBaseAddress = [string]$Anchor.SourceObjectAddress
                CoordXRelativeOffset = $sourceCoordXOffset
                CoordYRelativeOffset = $sourceCoordYOffset
                CoordZRelativeOffset = $sourceCoordZOffset
                LevelRelativeOffset = $null
                HealthRelativeOffset = $null
                MemorySample = $Anchor.SourceObjectSample
                Match = $Anchor.SourceObjectMatch
                MatchSource = 'readerbridge-live'
            }
        }
        elseif ($null -ne $sourceTraceEpochMatch -and $sourceTraceEpochMatch.CoordMatchesWithinTolerance) {
            return [ordered]@{
                CoordSourceKind = 'coord-trace-source-object'
                ObjectBaseAddress = [string]$Anchor.SourceObjectAddress
                CoordXRelativeOffset = $sourceCoordXOffset
                CoordYRelativeOffset = $sourceCoordYOffset
                CoordZRelativeOffset = $sourceCoordZOffset
                LevelRelativeOffset = $null
                HealthRelativeOffset = $null
                MemorySample = $Anchor.SourceObjectSample
                Match = $sourceTraceEpochMatch
                MatchSource = 'trace-epoch'
            }
        }
        else {
            $sourceReason = 'Coord-trace source object does not match either live ReaderBridge coords or the fresh trace-epoch snapshot within tolerance.'
        }
    }

    $Reason.Value = 'Unable to validate any proof-grade coord source from the coord trace.'
    if (-not [string]::IsNullOrWhiteSpace($traceEpochRegionReason) -or -not [string]::IsNullOrWhiteSpace($directReason) -or -not [string]::IsNullOrWhiteSpace($primaryReason) -or -not [string]::IsNullOrWhiteSpace($sourceReason)) {
        $traceEpochRegionReasonText = if ([string]::IsNullOrWhiteSpace($traceEpochRegionReason)) { 'n/a' } else { $traceEpochRegionReason }
        $directReasonText = if ([string]::IsNullOrWhiteSpace($directReason)) { 'n/a' } else { $directReason }
        $primaryReasonText = if ([string]::IsNullOrWhiteSpace($primaryReason)) { 'n/a' } else { $primaryReason }
        $sourceReasonText = if ([string]::IsNullOrWhiteSpace($sourceReason)) { 'n/a' } else { $sourceReason }
        $Reason.Value = "{0} Trace-epoch-region: {1} Direct: {2} Primary: {3} Source-object: {4}" -f $Reason.Value, $traceEpochRegionReasonText, $directReasonText, $primaryReasonText, $sourceReasonText
    }

    return $null
}

function Get-ResolvedProofCoordAnchor {
    param(
        [Parameter(Mandatory = $true)]
        $Anchor,

        [Parameter(Mandatory = $true)]
        $Selection
    )

    $objectBaseAddress = Parse-HexUInt64 -Value ([string]$Selection.ObjectBaseAddress)
    $coordXOffset = [int]$Selection.CoordXRelativeOffset
    $coordRegionAddress = [UInt64]([long]$objectBaseAddress + [long]$coordXOffset)

    return [ordered]@{
        Mode = 'proof-coord-anchor'
        GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
        ProcessName = $ProcessName
        ProcessId = $Anchor.ProcessId
        CanonicalCoordSourceKind = [string]$Selection.CoordSourceKind
        MatchSource = [string]$Selection.MatchSource
        TraceSourceFile = [string]$Anchor.SourceFile
        VerificationMethod = [string]$Anchor.VerificationMethod
        TraceMatchesProcess = [bool]$Anchor.TraceMatchesProcess
        TraceTargetAddress = [string]$Anchor.TargetAddress
        TraceCandidateAddress = [string]$Anchor.CandidateAddress
        TraceObjectBaseAddress = [string]$Anchor.ObjectBaseAddress
        ObjectBaseAddress = [string]$Selection.ObjectBaseAddress
        CoordRegionAddress = ('0x{0:X}' -f $coordRegionAddress)
        CoordXRelativeOffset = [int]$Selection.CoordXRelativeOffset
        CoordYRelativeOffset = [int]$Selection.CoordYRelativeOffset
        CoordZRelativeOffset = [int]$Selection.CoordZRelativeOffset
        LevelRelativeOffset = $Selection.LevelRelativeOffset
        HealthRelativeOffset = $Selection.HealthRelativeOffset
        SourceObjectAddress = [string]$Anchor.SourceObjectAddress
        SourceCoordRelativeOffset = $Anchor.SourceCoordRelativeOffset
        Match = $Selection.Match
        MemorySample = $Selection.MemorySample
        Expected = $Anchor.Expected
        TraceMatch = $Anchor.Match
        TraceMemorySample = $Anchor.MemorySample
        SourceObjectMatch = $Anchor.SourceObjectMatch
        SourceObjectSample = $Anchor.SourceObjectSample
        Notes = @(
            'This is the proof-grade movement coord source.',
            'Use this validated coord-trace anchor for movement polling and navigation proof.',
            'Do not substitute heuristic player-current anchors for proof runs.'
        )
    }
}

$lastAnchor = $null
$lastFailureReason = $null

for ($attempt = 0; $attempt -le $RefreshAttempts; $attempt++) {
    $lastAnchor = Invoke-ReaderJson -Arguments @((Get-ReaderTargetArguments -ResolvedProcessId $ProcessId -ResolvedProcessName $ProcessName) + @('--read-player-coord-anchor', '--json'))
    $traceReference = Get-TraceEpochReference -TraceSourceFile ([string]$lastAnchor.SourceFile)
    $selection = Resolve-ProofCoordSelection -Anchor $lastAnchor -TraceReference $traceReference -Reason ([ref]$lastFailureReason)
    if ($null -ne $selection) {
        $result = Get-ResolvedProofCoordAnchor -Anchor $lastAnchor -Selection $selection
        if ($Json) {
            $result | ConvertTo-Json -Depth 16
            exit 0
        }

        Write-Host 'Proof coord anchor resolved.' -ForegroundColor Green
        Write-Host ("Object base:          {0}" -f $result.ObjectBaseAddress)
        Write-Host ("Coord region:         {0}" -f $result.CoordRegionAddress)
        Write-Host ("Trace source:         {0}" -f $result.TraceSourceFile)
        exit 0
    }

    if ($SkipRefresh -or $attempt -ge $RefreshAttempts) {
        break
    }

    Write-Warning ("Proof coord anchor validation failed: {0} Refreshing coord trace with proof-safe non-heuristic seeds first (attempt {1}/{2})..." -f $lastFailureReason, ($attempt + 1), $RefreshAttempts)
    try {
        & $traceScript -Json -ProofReacquisition -MaxCandidates 4 -WatchMode access -StimulusMode AutoHotkey | Out-Null
    }
    catch {
        $lastFailureReason = "Coord-trace refresh failed: $($_.Exception.Message)"
    }
}

$message = if ([string]::IsNullOrWhiteSpace($lastFailureReason)) {
    'Unable to resolve a validated proof coord anchor.'
}
else {
    "Unable to resolve a validated proof coord anchor. $lastFailureReason"
}

if ($Json) {
    [ordered]@{
        Mode = 'proof-coord-anchor'
        GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
        ProcessName = $ProcessName
        Status = 'failed'
        Error = $message
        LastAnchor = $lastAnchor
    } | ConvertTo-Json -Depth 16
    exit 1
}

throw $message
