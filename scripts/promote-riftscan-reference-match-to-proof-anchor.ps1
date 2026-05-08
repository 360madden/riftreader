[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string[]]$ReadbackSummaryFile,

    [Parameter(Mandatory = $true)]
    [string]$CandidateId,

    [string]$ProcessName = 'rift_x64',
    [int]$ProcessId,
    [string]$TargetWindowHandle,
    [string]$OutputFile = (Join-Path $PSScriptRoot 'captures\telemetry-proof-coord-anchor.json'),
    [int]$MinPoseCount = 2,
    [double]$MinReferenceDisplacement = 1.0,
    [double]$MaxDeltaError = 0.25,
    [int]$MaxEvidenceAgeSeconds = 120,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public static class RiftNoCeProofTargetNative
{
    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool IsWindow(IntPtr hWnd);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
}
"@

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

function Get-DocumentPropertyValue {
    param(
        $Document,
        [Parameter(Mandatory = $true)]
        [string]$Name,
        $Default = $null
    )

    if ($null -eq $Document) {
        return $Default
    }

    $property = $Document.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $Default
    }

    return $property.Value
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
        if (-not [RiftNoCeProofTargetNative]::IsWindow($handle)) {
            throw "Target window handle '$TargetWindowHandle' is not a valid window."
        }

        $ownerProcessId = [uint32]0
        [void][RiftNoCeProofTargetNative]::GetWindowThreadProcessId($handle, [ref]$ownerProcessId)
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

function Get-FirstDecodedSample {
    param($Candidate)

    $samples = @(Get-DocumentPropertyValue -Document $Candidate -Name 'DecodedSamples' -Default @())
    if ($samples.Count -eq 0) {
        return $null
    }

    return $samples[0]
}

function New-PointDelta {
    param(
        [Parameter(Mandatory = $true)]
        $A,
        [Parameter(Mandatory = $true)]
        $B
    )

    $dx = [double]$B.X - [double]$A.X
    $dy = [double]$B.Y - [double]$A.Y
    $dz = [double]$B.Z - [double]$A.Z

    return [pscustomobject][ordered]@{
        DeltaX = $dx
        DeltaY = $dy
        DeltaZ = $dz
        PlanarDistance = [Math]::Sqrt(($dx * $dx) + ($dz * $dz))
        SpatialDistance = [Math]::Sqrt(($dx * $dx) + ($dy * $dy) + ($dz * $dz))
    }
}

function New-DeltaError {
    param(
        [Parameter(Mandatory = $true)]
        $CandidateDelta,
        [Parameter(Mandatory = $true)]
        $ReferenceDelta
    )

    $errorX = [double]$CandidateDelta.DeltaX - [double]$ReferenceDelta.DeltaX
    $errorY = [double]$CandidateDelta.DeltaY - [double]$ReferenceDelta.DeltaY
    $errorZ = [double]$CandidateDelta.DeltaZ - [double]$ReferenceDelta.DeltaZ
    $maxAbsError = [Math]::Max([Math]::Abs($errorX), [Math]::Max([Math]::Abs($errorY), [Math]::Abs($errorZ)))

    return [pscustomobject][ordered]@{
        ErrorX = $errorX
        ErrorY = $errorY
        ErrorZ = $errorZ
        MaxAbsError = $maxAbsError
    }
}

if ($MinPoseCount -lt 2) {
    throw "MinPoseCount must be at least 2 for no-CE movement proof promotion."
}

if ($MinReferenceDisplacement -le 0) {
    throw "MinReferenceDisplacement must be greater than zero."
}

if ($MaxDeltaError -lt 0) {
    throw "MaxDeltaError must be zero or greater."
}

if ($MaxEvidenceAgeSeconds -lt 0) {
    throw "MaxEvidenceAgeSeconds must be zero or greater."
}

$target = Resolve-TargetProcess
$targetProcess = $target.Process
$targetProcessId = [int]$targetProcess.Id
$targetProcessName = $targetProcess.ProcessName
$targetHandleHex = Format-WindowHandle -Handle $target.Handle

$resolvedSummaryFiles = @($ReadbackSummaryFile | ForEach-Object { [System.IO.Path]::GetFullPath($_) })
if ($resolvedSummaryFiles.Count -lt $MinPoseCount) {
    throw "At least $MinPoseCount readback summary files are required; got $($resolvedSummaryFiles.Count)."
}

$poses = [System.Collections.Generic.List[object]]::new()
foreach ($summaryFile in $resolvedSummaryFiles) {
    if (-not (Test-Path -LiteralPath $summaryFile -PathType Leaf)) {
        throw "Readback summary file was not found: $summaryFile"
    }

    $summary = ConvertFrom-JsonCompat -Text (Get-Content -LiteralPath $summaryFile -Raw) -Depth 100
    if (-not [bool](Get-DocumentPropertyValue -Document $summary -Name 'NoCheatEngine' -Default $false)) {
        throw "Summary '$summaryFile' does not report NoCheatEngine=true."
    }

    if ([bool](Get-DocumentPropertyValue -Document $summary -Name 'MovementSent' -Default $true)) {
        throw "Summary '$summaryFile' reports MovementSent=true; refusing no-CE proof promotion."
    }

    $summaryProcessId = Get-DocumentPropertyValue -Document $summary -Name 'ProcessId'
    if ($null -eq $summaryProcessId -or [int]$summaryProcessId -ne $targetProcessId) {
        throw "Summary '$summaryFile' PID '$summaryProcessId' does not match target PID $targetProcessId."
    }

    $summaryProcessName = [string](Get-DocumentPropertyValue -Document $summary -Name 'ProcessName' -Default '')
    if ([string]::IsNullOrWhiteSpace($summaryProcessName)) {
        throw "Summary '$summaryFile' is missing ProcessName."
    }

    $expectedProcessName = Get-NormalizedProcessName -Name $targetProcessName
    $actualProcessName = Get-NormalizedProcessName -Name $summaryProcessName
    if (-not [string]::Equals($actualProcessName, $expectedProcessName, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Summary '$summaryFile' process name '$summaryProcessName' does not match target process '$targetProcessName'."
    }

    if (-not [string]::IsNullOrWhiteSpace($targetHandleHex)) {
        $summaryWindowHandle = [string](Get-DocumentPropertyValue -Document $summary -Name 'TargetWindowHandle' -Default '')
        if ([string]::IsNullOrWhiteSpace($summaryWindowHandle)) {
            throw "Summary '$summaryFile' is missing TargetWindowHandle while target HWND is '$targetHandleHex'."
        }

        $summaryWindowHandleHex = Format-WindowHandle -Handle (ConvertTo-WindowHandle -HandleText $summaryWindowHandle)
        if (-not [string]::Equals($summaryWindowHandleHex, $targetHandleHex, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Summary '$summaryFile' HWND '$summaryWindowHandle' does not match target HWND '$targetHandleHex'."
        }
    }

    $generatedAtValue = Get-DocumentPropertyValue -Document $summary -Name 'GeneratedAtUtc'
    $summaryAgeSeconds = $null
    if ($null -ne $generatedAtValue -and -not [string]::IsNullOrWhiteSpace([string]$generatedAtValue)) {
        $generatedAt = [DateTimeOffset]::Parse([string]$generatedAtValue, [System.Globalization.CultureInfo]::InvariantCulture).ToUniversalTime()
        $summaryAgeSeconds = ([DateTimeOffset]::UtcNow - $generatedAt).TotalSeconds
        if ($MaxEvidenceAgeSeconds -gt 0 -and ($summaryAgeSeconds -lt -5 -or $summaryAgeSeconds -gt $MaxEvidenceAgeSeconds)) {
            throw ("Summary '{0}' is outside evidence age window: ageSeconds={1:0.000}; maxEvidenceAgeSeconds={2}." -f $summaryFile, $summaryAgeSeconds, $MaxEvidenceAgeSeconds)
        }
    }
    elseif ($MaxEvidenceAgeSeconds -gt 0) {
        throw "Summary '$summaryFile' is missing GeneratedAtUtc while MaxEvidenceAgeSeconds is enforced."
    }

    $reference = Get-DocumentPropertyValue -Document $summary -Name 'ReferenceCoordinate'
    if ($null -eq $reference) {
        throw "Summary '$summaryFile' does not include ReferenceCoordinate."
    }

    foreach ($propertyName in @('X', 'Y', 'Z')) {
        if ($null -eq (Get-DocumentPropertyValue -Document $reference -Name $propertyName)) {
            throw "Summary '$summaryFile' reference coordinate is missing '$propertyName'."
        }
    }

    $candidate = @((Get-DocumentPropertyValue -Document $summary -Name 'CandidateReadbacks' -Default @()) |
        Where-Object { [string]::Equals([string]$_.CandidateId, $CandidateId, [System.StringComparison]::OrdinalIgnoreCase) } |
        Select-Object -First 1)
    if ($candidate.Count -eq 0) {
        throw "Candidate '$CandidateId' was not found in summary '$summaryFile'."
    }

    $candidate = $candidate[0]
    if (-not [bool](Get-DocumentPropertyValue -Document $candidate -Name 'ReferenceMatchesReadback' -Default $false)) {
        throw "Candidate '$CandidateId' in '$summaryFile' does not match the reference coordinate."
    }

    if (-not [bool](Get-DocumentPropertyValue -Document $candidate -Name 'StableAcrossReadbackSamples' -Default $false)) {
        throw "Candidate '$CandidateId' in '$summaryFile' is not stable across readback samples."
    }

    $sample = Get-FirstDecodedSample -Candidate $candidate
    if ($null -eq $sample) {
        throw "Candidate '$CandidateId' in '$summaryFile' has no decoded sample."
    }

    foreach ($propertyName in @('X', 'Y', 'Z')) {
        if ($null -eq (Get-DocumentPropertyValue -Document $sample -Name $propertyName)) {
            throw "Candidate '$CandidateId' in '$summaryFile' decoded sample is missing '$propertyName'."
        }
    }

    $poses.Add([pscustomobject][ordered]@{
        SummaryFile = $summaryFile
        SummaryAgeSeconds = if ($null -eq $summaryAgeSeconds) { $null } else { [Math]::Round([double]$summaryAgeSeconds, 3) }
        CandidateAddressHex = [string](Get-DocumentPropertyValue -Document $candidate -Name 'CandidateAddressHex')
        RegionAddressHex = [string](Get-DocumentPropertyValue -Document $candidate -Name 'RegionAddressHex')
        CandidateOffsetInRegion = [int](Get-DocumentPropertyValue -Document $candidate -Name 'CandidateOffsetInRegion' -Default 0)
        Reference = [pscustomobject][ordered]@{
            Source = [string](Get-DocumentPropertyValue -Document $reference -Name 'Source')
            X = [double](Get-DocumentPropertyValue -Document $reference -Name 'X')
            Y = [double](Get-DocumentPropertyValue -Document $reference -Name 'Y')
            Z = [double](Get-DocumentPropertyValue -Document $reference -Name 'Z')
            Tolerance = [double](Get-DocumentPropertyValue -Document $reference -Name 'Tolerance' -Default $MaxDeltaError)
            CapturedAtUtc = [string](Get-DocumentPropertyValue -Document $reference -Name 'CapturedAtUtc')
        }
        CandidateSample = [pscustomobject][ordered]@{
            SampleIndex = [int](Get-DocumentPropertyValue -Document $sample -Name 'SampleIndex' -Default 0)
            RecordedAtUtc = [string](Get-DocumentPropertyValue -Document $sample -Name 'RecordedAtUtc')
            X = [double](Get-DocumentPropertyValue -Document $sample -Name 'X')
            Y = [double](Get-DocumentPropertyValue -Document $sample -Name 'Y')
            Z = [double](Get-DocumentPropertyValue -Document $sample -Name 'Z')
        }
    }) | Out-Null
}

$poseArray = @($poses.ToArray())
$firstPose = $poseArray[0]
$candidateAddress = [string]$firstPose.CandidateAddressHex
$regionAddress = [string]$firstPose.RegionAddressHex
$candidateOffset = [int]$firstPose.CandidateOffsetInRegion

if ([string]::IsNullOrWhiteSpace($candidateAddress)) {
    throw "Candidate '$CandidateId' does not expose CandidateAddressHex."
}

foreach ($pose in $poseArray) {
    if (-not [string]::Equals([string]$pose.CandidateAddressHex, $candidateAddress, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Candidate '$CandidateId' address is not stable across poses: '$($pose.CandidateAddressHex)' != '$candidateAddress'."
    }

    if (-not [string]::Equals([string]$pose.RegionAddressHex, $regionAddress, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Candidate '$CandidateId' region address is not stable across poses: '$($pose.RegionAddressHex)' != '$regionAddress'."
    }

    if ([int]$pose.CandidateOffsetInRegion -ne $candidateOffset) {
        throw "Candidate '$CandidateId' region offset is not stable across poses: '$($pose.CandidateOffsetInRegion)' != '$candidateOffset'."
    }
}

$deltaEvidence = [System.Collections.Generic.List[object]]::new()
$maxReferenceDisplacement = 0.0
$observedMaxDeltaError = 0.0
for ($index = 1; $index -lt $poseArray.Count; $index++) {
    $referenceDelta = New-PointDelta -A $firstPose.Reference -B $poseArray[$index].Reference
    $candidateDelta = New-PointDelta -A $firstPose.CandidateSample -B $poseArray[$index].CandidateSample
    $deltaError = New-DeltaError -CandidateDelta $candidateDelta -ReferenceDelta $referenceDelta
    $maxReferenceDisplacement = [Math]::Max($maxReferenceDisplacement, [double]$referenceDelta.PlanarDistance)
    $observedMaxDeltaError = [Math]::Max($observedMaxDeltaError, [double]$deltaError.MaxAbsError)

    $deltaEvidence.Add([pscustomobject][ordered]@{
        PoseIndex = $index
        ReferenceDelta = $referenceDelta
        CandidateDelta = $candidateDelta
        DeltaError = $deltaError
    }) | Out-Null
}

if ($maxReferenceDisplacement -lt $MinReferenceDisplacement) {
    throw ("Reference displacement is too small for no-CE proof promotion: maxPlanarDisplacement={0:0.000000}; required={1:0.000000}." -f $maxReferenceDisplacement, $MinReferenceDisplacement)
}

if ($observedMaxDeltaError -gt $MaxDeltaError) {
    throw ("Candidate delta does not track reference movement closely enough: maxDeltaError={0:0.000000}; allowed={1:0.000000}." -f $observedMaxDeltaError, $MaxDeltaError)
}

$result = [pscustomobject][ordered]@{
    SchemaVersion = 1
    Mode = 'proof-coord-anchor'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
    ProcessName = $targetProcessName
    ProcessId = $targetProcessId
    TargetWindowHandle = $targetHandleHex
    CanonicalCoordSourceKind = 'riftscan-reference-validated-candidate'
    ProofMethod = 'no-ce-riftscan-reference-multisample'
    ProofValidationStatus = 'validated'
    ProofProcessMatchesProcess = $true
    NoCheatEngine = $true
    MovementSent = $false
    MatchSource = 'riftscan-reference-multisample'
    TraceMatchesProcess = $false
    ObjectBaseAddress = $candidateAddress
    CoordRegionAddress = $candidateAddress
    CoordXRelativeOffset = 0
    CoordYRelativeOffset = 4
    CoordZRelativeOffset = 8
    Match = [pscustomobject][ordered]@{
        CoordMatchesWithinTolerance = $true
        MaxDeltaError = $observedMaxDeltaError
        MaxReferencePlanarDisplacement = $maxReferenceDisplacement
        MinReferenceDisplacement = $MinReferenceDisplacement
        MaxAllowedDeltaError = $MaxDeltaError
    }
    Evidence = [pscustomobject][ordered]@{
        CandidateId = $CandidateId
        CandidateAddressHex = $candidateAddress
        RegionAddressHex = $regionAddress
        CandidateOffsetInRegion = $candidateOffset
        PoseCount = $poseArray.Count
        MaxReferencePlanarDisplacement = $maxReferenceDisplacement
        MaxDeltaError = $observedMaxDeltaError
        ReadbackSummaryFiles = @($resolvedSummaryFiles)
        Poses = @($poseArray)
        DeltaEvidence = @($deltaEvidence.ToArray())
    }
    Notes = @(
        'This proof anchor was promoted without Cheat Engine.',
        'Promotion required same-PID, same-address, multi-pose RiftReader readback candidates that tracked same-time external reference coordinates.',
        'RiftScan/RiftReader candidate proof is movement-grade only through this validated proof-anchor artifact and the preflight gate.'
    )
}

$resolvedOutputFile = [System.IO.Path]::GetFullPath($OutputFile)
$directory = Split-Path -Parent $resolvedOutputFile
if (-not [string]::IsNullOrWhiteSpace($directory)) {
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
}

$result | ConvertTo-Json -Depth 80 | Set-Content -LiteralPath $resolvedOutputFile -Encoding UTF8

if ($Json) {
    $result | ConvertTo-Json -Depth 80
    return
}

Write-Host 'No-CE RiftScan/RiftReader proof anchor promoted.' -ForegroundColor Green
Write-Host ("Output:          {0}" -f $resolvedOutputFile)
Write-Host ("PID/HWND:        {0} / {1}" -f $targetProcessId, $targetHandleHex)
Write-Host ("Candidate:       {0} @ {1}" -f $CandidateId, $candidateAddress)
Write-Host ("Pose count:      {0}" -f $poseArray.Count)
Write-Host ("Max ref move:    {0:0.000000}" -f $maxReferenceDisplacement)
Write-Host ("Max delta error: {0:0.000000}" -f $observedMaxDeltaError)
Write-Host 'CE usage:        none'
