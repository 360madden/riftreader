[CmdletBinding()]
param(
    [string]$ProcessName = 'rift_x64',
    [int]$ProcessId,
    [int]$RefreshAttempts = 2,
    [int]$TraceReferenceMaxAgeSeconds = 15,
    [string]$PlayerCoordTraceFile,
    [string]$ProofCoordAnchorFile,
    [string]$TargetWindowHandle,
    [switch]$SkipRefresh,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$traceScript = Join-Path $PSScriptRoot 'trace-player-coord-write.ps1'
$defaultProofCoordAnchorFile = Join-Path $repoRoot 'scripts\captures\telemetry-proof-coord-anchor.json'
$script:EffectiveProcessId = 0
$script:NormalizedProcessName = $null

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public static class RiftProofAnchorTargetNative
{
    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool IsWindow(IntPtr hWnd);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
}
"@

if ([string]::IsNullOrWhiteSpace($ProofCoordAnchorFile)) {
    $ProofCoordAnchorFile = $defaultProofCoordAnchorFile
}
else {
    $ProofCoordAnchorFile = [System.IO.Path]::GetFullPath($ProofCoordAnchorFile)
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

    return ($output -join [Environment]::NewLine) | ConvertFrom-Json -Depth 32
}

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
    param([Parameter(Mandatory = $true)][string]$HandleText)

    if ([string]::IsNullOrWhiteSpace($HandleText)) {
        return [IntPtr]::Zero
    }

    if ($HandleText.StartsWith('0x', [System.StringComparison]::OrdinalIgnoreCase)) {
        $raw = [UInt64]::Parse($HandleText.Substring(2), [System.Globalization.NumberStyles]::AllowHexSpecifier, [System.Globalization.CultureInfo]::InvariantCulture)
        return [IntPtr]([Int64]$raw)
    }

    return [IntPtr]([Int64]::Parse($HandleText, [System.Globalization.CultureInfo]::InvariantCulture))
}

function Resolve-EffectiveTargetProcessId {
    $normalizedName = Get-NormalizedProcessName -Name $ProcessName

    if (-not [string]::IsNullOrWhiteSpace($TargetWindowHandle)) {
        $handle = ConvertTo-WindowHandle -HandleText $TargetWindowHandle
        if ($handle -eq [IntPtr]::Zero -or -not [RiftProofAnchorTargetNative]::IsWindow($handle)) {
            throw "Target window handle '$TargetWindowHandle' is not a valid window."
        }

        $ownerProcessId = [uint32]0
        [void][RiftProofAnchorTargetNative]::GetWindowThreadProcessId($handle, [ref]$ownerProcessId)
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

        return [int]$ownerProcessId
    }

    if ($ProcessId -gt 0) {
        $process = Get-Process -Id $ProcessId -ErrorAction Stop
        if (-not [string]::IsNullOrWhiteSpace($normalizedName) -and
            -not [string]::Equals($process.ProcessName, $normalizedName, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Target PID $ProcessId is process '$($process.ProcessName)', not '$ProcessName'."
        }

        return $process.Id
    }

    return 0
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

function Get-CoordAnchorArguments {
    param(
        [int]$ResolvedProcessId,
        [Parameter(Mandatory = $true)]
        [string]$ResolvedProcessName,
        [string]$ResolvedTraceFile
    )

    $arguments = @((Get-ReaderTargetArguments -ResolvedProcessId $ResolvedProcessId -ResolvedProcessName $ResolvedProcessName) + @('--read-player-coord-anchor', '--json'))
    if (-not [string]::IsNullOrWhiteSpace($ResolvedTraceFile)) {
        $arguments += @('--player-coord-trace-file', $ResolvedTraceFile)
    }

    return $arguments
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

function Get-ObjectMemberValue {
    param(
        [Parameter(Mandatory = $true)]
        $InputObject,

        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    if ($null -eq $InputObject) {
        return $null
    }

    if ($InputObject -is [System.Collections.IDictionary]) {
        if ($InputObject.Contains($Name)) {
            return $InputObject[$Name]
        }

        return $null
    }

    $property = $InputObject.PSObject.Properties[$Name]
    if ($null -ne $property) {
        return $property.Value
    }

    return $null
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
        (Get-ReaderTargetArguments -ResolvedProcessId $script:EffectiveProcessId -ResolvedProcessName $script:NormalizedProcessName) +
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

    $anchorTraceMatchesProcess = Get-ObjectMemberValue -InputObject $Anchor -Name 'TraceMatchesProcess'
    $anchorTargetAddress = [string](Get-ObjectMemberValue -InputObject $Anchor -Name 'TargetAddress')
    $anchorCandidateAddress = [string](Get-ObjectMemberValue -InputObject $Anchor -Name 'CandidateAddress')
    $anchorObjectBaseAddress = [string](Get-ObjectMemberValue -InputObject $Anchor -Name 'ObjectBaseAddress')
    $anchorCoordXRelativeOffset = Get-ObjectMemberValue -InputObject $Anchor -Name 'CoordXRelativeOffset'
    $anchorCoordYRelativeOffset = Get-ObjectMemberValue -InputObject $Anchor -Name 'CoordYRelativeOffset'
    $anchorCoordZRelativeOffset = Get-ObjectMemberValue -InputObject $Anchor -Name 'CoordZRelativeOffset'
    $anchorLevelRelativeOffset = Get-ObjectMemberValue -InputObject $Anchor -Name 'LevelRelativeOffset'
    $anchorHealthRelativeOffset = Get-ObjectMemberValue -InputObject $Anchor -Name 'HealthRelativeOffset'
    $anchorMemorySample = Get-ObjectMemberValue -InputObject $Anchor -Name 'MemorySample'
    $anchorMatch = Get-ObjectMemberValue -InputObject $Anchor -Name 'Match'
    $anchorExpected = Get-ObjectMemberValue -InputObject $Anchor -Name 'Expected'
    $anchorSourceObjectAddress = [string](Get-ObjectMemberValue -InputObject $Anchor -Name 'SourceObjectAddress')
    $anchorSourceCoordRelativeOffset = Get-ObjectMemberValue -InputObject $Anchor -Name 'SourceCoordRelativeOffset'
    $anchorSourceObjectSample = Get-ObjectMemberValue -InputObject $Anchor -Name 'SourceObjectSample'
    $anchorSourceObjectMatch = Get-ObjectMemberValue -InputObject $Anchor -Name 'SourceObjectMatch'

    if (-not $anchorTraceMatchesProcess) {
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
    if (-not [string]::IsNullOrWhiteSpace($anchorTargetAddress)) {
        $directRegionAddress = $anchorTargetAddress
    }
    elseif (-not [string]::IsNullOrWhiteSpace($anchorCandidateAddress)) {
        $directRegionAddress = $anchorCandidateAddress
    }

    if (-not [string]::IsNullOrWhiteSpace($directRegionAddress)) {
        try {
            $directSample = Read-DirectCoordRegionSample -AddressHex $directRegionAddress
            $directLiveMatch = New-LiveReaderMatch -Sample $directSample -Expected $anchorExpected
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

    if ([string]::IsNullOrWhiteSpace($anchorObjectBaseAddress)) {
        $primaryReason = 'Coord-trace anchor did not expose an object base address.'
    }
    elseif ($null -eq $anchorCoordXRelativeOffset -or $null -eq $anchorCoordYRelativeOffset -or $null -eq $anchorCoordZRelativeOffset) {
        $primaryReason = 'Coord-trace anchor did not expose a full coord offset triplet.'
    }
    else {
        $coordXOffset = [int]$anchorCoordXRelativeOffset
        $coordYOffset = [int]$anchorCoordYRelativeOffset
        $coordZOffset = [int]$anchorCoordZRelativeOffset
        $primaryTraceEpochMatch = New-TraceEpochMatch -Sample $anchorMemorySample -TraceReference $TraceReference
        if ((($coordYOffset - $coordXOffset) -ne 4) -or (($coordZOffset - $coordYOffset) -ne 4)) {
            $primaryReason = "Coord-trace anchor offsets are not a contiguous float triplet: [$coordXOffset, $coordYOffset, $coordZOffset]."
        }
        elseif (-not (Test-IsUsableCoordSample -Sample $anchorMemorySample)) {
            $primaryReason = 'Coord-trace anchor did not expose a finite live memory sample.'
        }
        elseif ($null -ne $anchorMatch -and $anchorMatch.CoordMatchesWithinTolerance) {
            return [ordered]@{
                CoordSourceKind = 'coord-trace-object'
                ObjectBaseAddress = $anchorObjectBaseAddress
                CoordXRelativeOffset = $coordXOffset
                CoordYRelativeOffset = $coordYOffset
                CoordZRelativeOffset = $coordZOffset
                LevelRelativeOffset = $anchorLevelRelativeOffset
                HealthRelativeOffset = $anchorHealthRelativeOffset
                MemorySample = $anchorMemorySample
                Match = $anchorMatch
                MatchSource = 'readerbridge-live'
            }
        }
        elseif ($null -ne $primaryTraceEpochMatch -and $primaryTraceEpochMatch.CoordMatchesWithinTolerance) {
            return [ordered]@{
                CoordSourceKind = 'coord-trace-object'
                ObjectBaseAddress = $anchorObjectBaseAddress
                CoordXRelativeOffset = $coordXOffset
                CoordYRelativeOffset = $coordYOffset
                CoordZRelativeOffset = $coordZOffset
                LevelRelativeOffset = $anchorLevelRelativeOffset
                HealthRelativeOffset = $anchorHealthRelativeOffset
                MemorySample = $anchorMemorySample
                Match = $primaryTraceEpochMatch
                MatchSource = 'trace-epoch'
            }
        }
        else {
            $primaryReason = 'Coord-trace anchor does not match either live ReaderBridge coords or the fresh trace-epoch snapshot within tolerance.'
        }
    }

    if ([string]::IsNullOrWhiteSpace($anchorSourceObjectAddress)) {
        $sourceReason = 'Coord-trace anchor did not expose a source object address.'
    }
    elseif ($null -eq $anchorSourceCoordRelativeOffset) {
        $sourceReason = 'Coord-trace anchor did not expose a source coord relative offset.'
    }
    else {
        $sourceObjectSample = $anchorSourceObjectSample
        $sourceObjectMatch = $anchorSourceObjectMatch
        $sourceCoordXOffset = [int]$anchorSourceCoordRelativeOffset
        $sourceCoordYOffset = $sourceCoordXOffset + 4
        $sourceCoordZOffset = $sourceCoordXOffset + 8
        $sourceTraceEpochMatch = New-TraceEpochMatch -Sample $sourceObjectSample -TraceReference $TraceReference

        if (-not (Test-IsUsableCoordSample -Sample $sourceObjectSample)) {
            $sourceReason = 'Coord-trace source object did not expose a finite live coord sample.'
        }
        elseif ($null -ne $sourceObjectMatch -and $sourceObjectMatch.CoordMatchesWithinTolerance) {
            return [ordered]@{
                CoordSourceKind = 'coord-trace-source-object'
                ObjectBaseAddress = $anchorSourceObjectAddress
                CoordXRelativeOffset = $sourceCoordXOffset
                CoordYRelativeOffset = $sourceCoordYOffset
                CoordZRelativeOffset = $sourceCoordZOffset
                LevelRelativeOffset = $null
                HealthRelativeOffset = $null
                MemorySample = $sourceObjectSample
                Match = $sourceObjectMatch
                MatchSource = 'readerbridge-live'
            }
        }
        elseif ($null -ne $sourceTraceEpochMatch -and $sourceTraceEpochMatch.CoordMatchesWithinTolerance) {
            return [ordered]@{
                CoordSourceKind = 'coord-trace-source-object'
                ObjectBaseAddress = $anchorSourceObjectAddress
                CoordXRelativeOffset = $sourceCoordXOffset
                CoordYRelativeOffset = $sourceCoordYOffset
                CoordZRelativeOffset = $sourceCoordZOffset
                LevelRelativeOffset = $null
                HealthRelativeOffset = $null
                MemorySample = $sourceObjectSample
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

    $selectionObjectBaseAddress = [string](Get-ObjectMemberValue -InputObject $Selection -Name 'ObjectBaseAddress')
    $selectionCoordSourceKind = [string](Get-ObjectMemberValue -InputObject $Selection -Name 'CoordSourceKind')
    $selectionMatchSource = [string](Get-ObjectMemberValue -InputObject $Selection -Name 'MatchSource')
    $selectionCoordXOffset = Get-ObjectMemberValue -InputObject $Selection -Name 'CoordXRelativeOffset'
    $selectionCoordYOffset = Get-ObjectMemberValue -InputObject $Selection -Name 'CoordYRelativeOffset'
    $selectionCoordZOffset = Get-ObjectMemberValue -InputObject $Selection -Name 'CoordZRelativeOffset'
    $selectionLevelRelativeOffset = Get-ObjectMemberValue -InputObject $Selection -Name 'LevelRelativeOffset'
    $selectionHealthRelativeOffset = Get-ObjectMemberValue -InputObject $Selection -Name 'HealthRelativeOffset'
    $selectionMatch = Get-ObjectMemberValue -InputObject $Selection -Name 'Match'
    $selectionMemorySample = Get-ObjectMemberValue -InputObject $Selection -Name 'MemorySample'

    if ([string]::IsNullOrWhiteSpace($selectionObjectBaseAddress)) {
        throw 'Proof coord anchor selection did not expose an ObjectBaseAddress.'
    }

    if ($null -eq $selectionCoordXOffset -or $null -eq $selectionCoordYOffset -or $null -eq $selectionCoordZOffset) {
        throw 'Proof coord anchor selection did not expose a full coord offset triplet.'
    }

    $objectBaseAddress = Parse-HexUInt64 -Value $selectionObjectBaseAddress
    $coordXOffset = [int]$selectionCoordXOffset
    $coordYOffset = [int]$selectionCoordYOffset
    $coordZOffset = [int]$selectionCoordZOffset
    $coordRegionAddress = [UInt64]([long]$objectBaseAddress + [long]$coordXOffset)
    $coordYRegionOffset = $coordYOffset - $coordXOffset
    $coordZRegionOffset = $coordZOffset - $coordXOffset
    if ($coordYRegionOffset -lt 0 -or $coordZRegionOffset -lt 0) {
        throw 'Proof coord anchor selection produced offsets before the selected coord region.'
    }

    $normalizedMemorySample = if ($null -ne $selectionMemorySample) {
        [pscustomobject]@{
            AddressHex = ('0x{0:X}' -f $coordRegionAddress)
            CoordX = Get-ObjectMemberValue -InputObject $selectionMemorySample -Name 'CoordX'
            CoordY = Get-ObjectMemberValue -InputObject $selectionMemorySample -Name 'CoordY'
            CoordZ = Get-ObjectMemberValue -InputObject $selectionMemorySample -Name 'CoordZ'
        }
    }
    else {
        $null
    }
    $traceSourceFile = [string](Get-ObjectMemberValue -InputObject $Anchor -Name 'SourceFile')
    $traceVerificationMethod = [string](Get-ObjectMemberValue -InputObject $Anchor -Name 'VerificationMethod')
    $traceMatchesProcess = Get-ObjectMemberValue -InputObject $Anchor -Name 'TraceMatchesProcess'
    $traceTargetAddress = [string](Get-ObjectMemberValue -InputObject $Anchor -Name 'TargetAddress')
    $traceCandidateAddress = [string](Get-ObjectMemberValue -InputObject $Anchor -Name 'CandidateAddress')
    $traceObjectBaseAddress = [string](Get-ObjectMemberValue -InputObject $Anchor -Name 'ObjectBaseAddress')
    $sourceObjectMatch = if ($Anchor.PSObject.Properties['SourceObjectMatch']) { $Anchor.SourceObjectMatch } else { $null }
    $sourceObjectSample = if ($Anchor.PSObject.Properties['SourceObjectSample']) { $Anchor.SourceObjectSample } else { $null }
    $sourceObjectAddress = if ($Anchor.PSObject.Properties['SourceObjectAddress']) { [string]$Anchor.SourceObjectAddress } else { $null }
    $sourceCoordRelativeOffset = if ($Anchor.PSObject.Properties['SourceCoordRelativeOffset']) { $Anchor.SourceCoordRelativeOffset } else { $null }

    return [pscustomobject][ordered]@{
        Mode = 'proof-coord-anchor'
        GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
        ProcessName = $ProcessName
        ProcessId = $Anchor.ProcessId
        CanonicalCoordSourceKind = $selectionCoordSourceKind
        MatchSource = $selectionMatchSource
        TraceSourceFile = $traceSourceFile
        VerificationMethod = $traceVerificationMethod
        TraceMatchesProcess = if ($null -eq $traceMatchesProcess) { $false } else { [bool]$traceMatchesProcess }
        TraceTargetAddress = $traceTargetAddress
        TraceCandidateAddress = $traceCandidateAddress
        TraceObjectBaseAddress = $traceObjectBaseAddress
        ObjectBaseAddress = $selectionObjectBaseAddress
        CoordRegionAddress = ('0x{0:X}' -f $coordRegionAddress)
        CoordXRelativeOffset = 0
        CoordYRelativeOffset = $coordYRegionOffset
        CoordZRelativeOffset = $coordZRegionOffset
        LevelRelativeOffset = $selectionLevelRelativeOffset
        HealthRelativeOffset = $selectionHealthRelativeOffset
        SourceObjectAddress = $sourceObjectAddress
        SourceCoordRelativeOffset = $sourceCoordRelativeOffset
        Match = $selectionMatch
        MemorySample = $normalizedMemorySample
        Expected = $Anchor.Expected
        TraceMatch = $Anchor.Match
        TraceMemorySample = $Anchor.MemorySample
        SourceObjectMatch = $sourceObjectMatch
        SourceObjectSample = $sourceObjectSample
        Notes = @(
            'This is the proof-grade movement coord source.',
            'Use this validated coord-trace anchor for movement polling and navigation proof.',
            'Do not substitute heuristic player-current anchors for proof runs.'
        )
    }
}

function Save-ResolvedProofCoordAnchor {
    param(
        [Parameter(Mandatory = $true)]
        $AnchorDocument,
        [Parameter(Mandatory = $true)]
        [string]$OutputFile
    )

    $directory = Split-Path -Parent $OutputFile
    if (-not [string]::IsNullOrWhiteSpace($directory)) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }

    $AnchorDocument | ConvertTo-Json -Depth 16 | Set-Content -LiteralPath $OutputFile -Encoding UTF8
}

$lastAnchor = $null
$lastFailureReason = $null
$lastRefreshFailureReason = $null
$resolvedPlayerCoordTraceFile = $null
if (-not [string]::IsNullOrWhiteSpace($PlayerCoordTraceFile)) {
    $resolvedPlayerCoordTraceFile = [System.IO.Path]::GetFullPath($PlayerCoordTraceFile)
}

$script:NormalizedProcessName = Get-NormalizedProcessName -Name $ProcessName
$script:EffectiveProcessId = Resolve-EffectiveTargetProcessId

for ($attempt = 0; $attempt -le $RefreshAttempts; $attempt++) {
    $lastAnchor = Invoke-ReaderJson -Arguments (Get-CoordAnchorArguments -ResolvedProcessId $script:EffectiveProcessId -ResolvedProcessName $script:NormalizedProcessName -ResolvedTraceFile $resolvedPlayerCoordTraceFile)
    $traceReference = Get-TraceEpochReference -TraceSourceFile ([string]$lastAnchor.SourceFile)
    $selection = Resolve-ProofCoordSelection -Anchor $lastAnchor -TraceReference $traceReference -Reason ([ref]$lastFailureReason)
    if ($null -ne $selection) {
        $result = Get-ResolvedProofCoordAnchor -Anchor $lastAnchor -Selection $selection
        Save-ResolvedProofCoordAnchor -AnchorDocument $result -OutputFile $ProofCoordAnchorFile
        if ($Json) {
            $result | ConvertTo-Json -Depth 16
            exit 0
        }

        Write-Host 'Proof coord anchor resolved.' -ForegroundColor Green
        Write-Host ("Object base:          {0}" -f $result.ObjectBaseAddress)
        Write-Host ("Coord region:         {0}" -f $result.CoordRegionAddress)
        Write-Host ("Trace source:         {0}" -f $result.TraceSourceFile)
        Write-Host ("Cached proof anchor:  {0}" -f $ProofCoordAnchorFile)
        exit 0
    }

    if ($SkipRefresh -or $attempt -ge $RefreshAttempts) {
        break
    }

    Write-Warning ("Proof coord anchor validation failed: {0} Refreshing coord trace with proof-safe non-heuristic seeds first (attempt {1}/{2})..." -f $lastFailureReason, ($attempt + 1), $RefreshAttempts)
    try {
        $traceArguments = @{
            Json = $true
            ProofReacquisition = $true
            MaxCandidates = 4
            WatchMode = 'access'
            StimulusMode = 'AutoHotkey'
            ProcessName = $script:NormalizedProcessName
        }
        if ($script:EffectiveProcessId -gt 0) {
            $traceArguments['ProcessId'] = $script:EffectiveProcessId
        }
        if (-not [string]::IsNullOrWhiteSpace($TargetWindowHandle)) {
            $traceArguments['TargetWindowHandle'] = $TargetWindowHandle
        }
        if (-not [string]::IsNullOrWhiteSpace($resolvedPlayerCoordTraceFile)) {
            $traceArguments['OutputFile'] = $resolvedPlayerCoordTraceFile
        }

        & $traceScript @traceArguments | Out-Null
    }
    catch {
        $lastRefreshFailureReason = "Coord-trace refresh failed: $($_.Exception.Message)"
        $lastFailureReason = $lastRefreshFailureReason
        break
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
        LastRefreshError = $lastRefreshFailureReason
        LastAnchor = $lastAnchor
    } | ConvertTo-Json -Depth 16
    exit 1
}

throw $message
