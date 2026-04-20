[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('idle', 'turn-left', 'turn-right', 'move-forward')]
    [string]$Stimulus,
    [switch]$Json,
    [int]$RepeatCount = 1,
    [int]$HoldMilliseconds = 700,
    [int]$WaitMilliseconds = 250,
    [switch]$NoAhkFallback,
    [switch]$SkipBackgroundFocus,
    [switch]$UseAhkSendKey,
    [string]$TurnLeftKey = 'A',
    [string]$TurnRightKey = 'D',
    [string]$MoveForwardKey = 'W',
    [switch]$UseBackgroundPostKey,
    [switch]$NoBoundaryTrigger,
    [switch]$UsePlayerCurrentAnchorBoundary,
    [switch]$RefreshOwnerComponents,
    [switch]$AllowLegacyRecovery,
    [string]$PreferredLeadFile = 'actor-facing-behavior-backed-lead.json',
    [string]$PlayerCurrentAnchorFile = 'captures\player-current-anchor.json',
    [string]$OwnerComponentsFile,
    [string]$OutputFile = 'captures\actor-facing-validation.json',
    [string]$HistoryFile = 'captures\actor-facing-validation-history.ndjson'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptRoot = if ($PSScriptRoot) { $PSScriptRoot } elseif ($PSCommandPath) { Split-Path -Parent $PSCommandPath } else { (Get-Location).Path }

function Assert-PowerShell7 {
    if ($PSVersionTable.PSVersion.Major -lt 7) {
        throw "PowerShell 7+ (pwsh) is required for $PSCommandPath. Use C:\RIFT MODDING\RiftReader_facing\scripts\test-actor-facing-validation.cmd or run the script with pwsh.exe."
    }
}

function Resolve-ScriptRelativePath {
    param([Parameter(Mandatory = $true)][string]$Path)

    if ([System.IO.Path]::IsPathRooted($Path)) {
        return [System.IO.Path]::GetFullPath($Path)
    }

    return [System.IO.Path]::GetFullPath((Join-Path $scriptRoot $Path))
}

Assert-PowerShell7

. (Join-Path $scriptRoot 'actor-facing-common.ps1')

$repoRoot = Get-RiftReaderRepoRoot -ScriptRoot $scriptRoot
$readerProject = Get-RiftReaderProjectPath -RepoRoot $repoRoot
$boundaryCaptureScript = Join-Path $scriptRoot 'capture-readerbridge-boundary.ps1'
$facingCaptureScript = Join-Path $scriptRoot 'capture-actor-facing.ps1'
$keyScript = if ($UseAhkSendKey) {
    Join-Path $scriptRoot 'send-rift-key-ahk.ps1'
}
elseif ($UseBackgroundPostKey) {
    Join-Path $scriptRoot 'post-rift-key.ps1'
}
else {
    Join-Path $scriptRoot 'send-rift-key.ps1'
}
$resolvedOutputFile = Resolve-ScriptRelativePath -Path $OutputFile
$resolvedHistoryFile = Resolve-ScriptRelativePath -Path $HistoryFile
$resolvedPreferredLeadFile = Resolve-ScriptRelativePath -Path $PreferredLeadFile
$resolvedPlayerCurrentAnchorFile = Resolve-ScriptRelativePath -Path $PlayerCurrentAnchorFile
$resolvedOwnerComponentsFile = if (-not [string]::IsNullOrWhiteSpace($OwnerComponentsFile)) { Resolve-ScriptRelativePath -Path $OwnerComponentsFile } else { $null }
$thresholds = Get-ActorFacingThresholds
$tempPaths = New-Object System.Collections.Generic.List[string]

function Format-Nullable {
    param(
        $Value,
        [string]$Format = '0.000'
    )

    if ($null -eq $Value) {
        return 'n/a'
    }

    return ([double]$Value).ToString($Format, [System.Globalization.CultureInfo]::InvariantCulture)
}

function Get-StimulusKey {
    param([string]$StimulusType)

    switch ($StimulusType) {
        'turn-left' { return $TurnLeftKey }
        'turn-right' { return $TurnRightKey }
        'move-forward' { return $MoveForwardKey }
        default { return $null }
    }
}

function Get-TempPathForRun {
    param(
        [string]$Prefix,
        [int]$Iteration,
        [string]$Suffix
    )

    $path = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), ('rift-{0}-{1}-{2}.json' -f $Prefix, $Iteration, $Suffix))
    $tempPaths.Add($path)
    return $path
}

function Parse-UnsignedAddress {
    param(
        [Parameter(Mandatory = $true)]
        [string]$AddressText
    )

    $normalized = $AddressText.Trim()
    if ($normalized.StartsWith('0x', [System.StringComparison]::OrdinalIgnoreCase)) {
        $normalized = $normalized.Substring(2)
    }

    return [Convert]::ToUInt64($normalized, 16)
}

function Invoke-PlayerCurrentBoundaryCapture {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CaptureLabel,
        [Parameter(Mandatory = $true)]
        [string]$OutputPath
    )

    if (-not (Test-Path -LiteralPath $resolvedPlayerCurrentAnchorFile)) {
        throw "Player-current anchor file was not found: $resolvedPlayerCurrentAnchorFile"
    }

    $anchorDocument = Get-Content -LiteralPath $resolvedPlayerCurrentAnchorFile -Raw | ConvertFrom-Json -Depth 40
    $addressText = [string](Get-OptionalPropertyValue -InputObject $anchorDocument -PropertyName 'AddressHex')
    if ([string]::IsNullOrWhiteSpace($addressText)) {
        throw "Player-current anchor file did not contain AddressHex: $resolvedPlayerCurrentAnchorFile"
    }

    $processName = [string](Get-OptionalPropertyValue -InputObject $anchorDocument -PropertyName 'ProcessName')
    if ([string]::IsNullOrWhiteSpace($processName)) {
        $processName = 'rift_x64'
    }

    $coordXOffset = [int](Get-OptionalPropertyValue -InputObject $anchorDocument -PropertyName 'CoordXOffset')
    $coordYOffset = [int](Get-OptionalPropertyValue -InputObject $anchorDocument -PropertyName 'CoordYOffset')
    $coordZOffset = [int](Get-OptionalPropertyValue -InputObject $anchorDocument -PropertyName 'CoordZOffset')
    $offsets = @($coordXOffset, $coordYOffset, $coordZOffset)
    $minimumOffset = [int](($offsets | Measure-Object -Minimum).Minimum)
    $maximumOffset = [int](($offsets | Measure-Object -Maximum).Maximum)
    $baseAddress = Parse-UnsignedAddress -AddressText $addressText
    $readAddress = $baseAddress + [uint64]$minimumOffset
    $length = ($maximumOffset - $minimumOffset) + 4

    $memoryRead = Invoke-RiftReaderJson -ReaderProject $readerProject -Arguments @(
        '--process-name', $processName,
        '--address', ('0x{0:X}' -f $readAddress),
        '--length', $length.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '--json'
    )

    $bytesHex = [string](Get-OptionalPropertyValue -InputObject $memoryRead -PropertyName 'BytesHex')
    if ([string]::IsNullOrWhiteSpace($bytesHex)) {
        throw "Live player-current memory read returned no bytes for anchor $addressText."
    }

    $bytes = [Convert]::FromHexString($bytesHex)
    $coord = [pscustomobject]@{
        X = [BitConverter]::ToSingle($bytes, $coordXOffset - $minimumOffset)
        Y = [BitConverter]::ToSingle($bytes, $coordYOffset - $minimumOffset)
        Z = [BitConverter]::ToSingle($bytes, $coordZOffset - $minimumOffset)
    }

    $document = [pscustomobject]@{
        Mode            = 'player-current-boundary-capture'
        GeneratedAtUtc  = [DateTimeOffset]::UtcNow.ToString('O')
        Label           = $CaptureLabel
        OutputFile      = $OutputPath
        CommandIssued   = $null
        SourceFile      = $resolvedPlayerCurrentAnchorFile
        SourceAddress   = $addressText
        SourceSignature = Get-OptionalPropertyValue -InputObject $anchorDocument -PropertyName 'Signature'
        ProcessName     = $processName
        PlayerCoord     = $coord
        Notes           = @(
            'Boundary coords were read directly from the verified player-current anchor in live memory.',
            'This bypasses /rbx export and uses the cached player-current family offsets as the movement truth source.'
        )
    }

    [System.IO.File]::WriteAllText($OutputPath, ($document | ConvertTo-Json -Depth 40))
    return $document
}

function Invoke-BoundaryCapture {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CaptureLabel,
        [int]$Iteration,
        [string]$Phase
    )

    $outputPath = Get-TempPathForRun -Prefix 'actor-facing-boundary' -Iteration $Iteration -Suffix $Phase
    if ($UsePlayerCurrentAnchorBoundary) {
        return Invoke-PlayerCurrentBoundaryCapture -CaptureLabel $CaptureLabel -OutputPath $outputPath
    }

    $arguments = @{
        Json       = $true
        Label      = $CaptureLabel
        OutputFile = $outputPath
    }
    if ($NoBoundaryTrigger) {
        $arguments['NoTrigger'] = $true
    }
    if ($NoAhkFallback) {
        $arguments['NoAhkFallback'] = $true
    }
    if ($SkipBackgroundFocus) {
        $arguments['SkipBackgroundFocus'] = $true
    }

    $jsonText = & $boundaryCaptureScript @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "ReaderBridge boundary capture failed for '$CaptureLabel'."
    }

    return $jsonText | ConvertFrom-Json -Depth 80
}

function Invoke-FacingCapture {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CaptureLabel,
        [int]$Iteration,
        [string]$Phase
    )

    $outputPath = Get-TempPathForRun -Prefix 'actor-facing-sample' -Iteration $Iteration -Suffix $Phase
    $previousPath = Get-TempPathForRun -Prefix 'actor-facing-sample-prev' -Iteration $Iteration -Suffix $Phase
    $orientationOutputPath = Get-TempPathForRun -Prefix 'actor-orientation-sample' -Iteration $Iteration -Suffix $Phase
    $orientationPreviousPath = Get-TempPathForRun -Prefix 'actor-orientation-sample-prev' -Iteration $Iteration -Suffix $Phase

    $arguments = @{
        Json                    = $true
        Label                   = $CaptureLabel
        PreferredLeadFile       = $resolvedPreferredLeadFile
        OutputFile              = $outputPath
        PreviousFile            = $previousPath
        OrientationOutputFile   = $orientationOutputPath
        OrientationPreviousFile = $orientationPreviousPath
    }
    if ($RefreshOwnerComponents) {
        $arguments['RefreshOwnerComponents'] = $true
    }
    if (-not [string]::IsNullOrWhiteSpace($resolvedOwnerComponentsFile)) {
        $arguments['OwnerComponentsFile'] = $resolvedOwnerComponentsFile
    }
    if ($NoAhkFallback) {
        $arguments['NoAhkFallback'] = $true
    }
    if ($AllowLegacyRecovery) {
        $arguments['AllowLegacyRecovery'] = $true
    }

    $jsonText = & $facingCaptureScript @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Actor facing capture failed for '$CaptureLabel'."
    }

    return $jsonText | ConvertFrom-Json -Depth 80
}

function Get-ObservedHeadingRadians {
    param($BeforeCoord, $AfterCoord)

    if ($null -eq $BeforeCoord -or $null -eq $AfterCoord) {
        return $null
    }

    $beforeX = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $BeforeCoord -PropertyName 'X')
    $beforeZ = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $BeforeCoord -PropertyName 'Z')
    $afterX = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $AfterCoord -PropertyName 'X')
    $afterZ = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $AfterCoord -PropertyName 'Z')
    if ($null -eq $beforeX -or $null -eq $beforeZ -or $null -eq $afterX -or $null -eq $afterZ) {
        return $null
    }

    $deltaX = $afterX - $beforeX
    $deltaZ = $afterZ - $beforeZ
    if ((Get-PlanarMagnitude -ValueX $deltaX -ValueZ $deltaZ) -le [double]::Epsilon) {
        return $null
    }

    return [Math]::Atan2($deltaZ, $deltaX)
}

function Test-RunPass {
    param(
        [string]$StimulusType,
        [double]$PlanarDistance,
        $SignedAngularErrorDegrees,
        $YawDeltaDegrees,
        [bool]$IntegrityPass
    )

    $absoluteYawDelta = if ($null -eq $YawDeltaDegrees) { $null } else { [Math]::Abs([double]$YawDeltaDegrees) }
    $absoluteAngularError = if ($null -eq $SignedAngularErrorDegrees) { $null } else { [Math]::Abs([double]$SignedAngularErrorDegrees) }

    switch ($StimulusType) {
        'idle' {
            return $IntegrityPass -and $absoluteYawDelta -le $thresholds.IdleYawJitterDegrees -and $PlanarDistance -le $thresholds.IdlePlanarCoordDrift
        }
        'turn-left' {
            return $IntegrityPass -and $absoluteYawDelta -ge $thresholds.TurnYawDeltaDegrees -and $PlanarDistance -le $thresholds.TurnPlanarCoordDrift
        }
        'turn-right' {
            return $IntegrityPass -and $absoluteYawDelta -ge $thresholds.TurnYawDeltaDegrees -and $PlanarDistance -le $thresholds.TurnPlanarCoordDrift
        }
        'move-forward' {
            return $IntegrityPass -and $PlanarDistance -ge $thresholds.ForwardMovementDistance -and $absoluteAngularError -le $thresholds.ForwardAngularErrorDegrees
        }
        default {
            throw "Unsupported stimulus type '$StimulusType'."
        }
    }
}

function Invoke-Stimulus {
    param([string]$StimulusType)

    $key = Get-StimulusKey -StimulusType $StimulusType
    if ([string]::IsNullOrWhiteSpace($key)) {
        Start-Sleep -Milliseconds $HoldMilliseconds
        return
    }

    $keyArgs = @{
        Key              = $key
        HoldMilliseconds = $HoldMilliseconds
    }
    if ($UseAhkSendKey) {
        if ($SkipBackgroundFocus) {
            $keyArgs['NoRefocus'] = $true
        }
    }
    elseif ($UseBackgroundPostKey -and $SkipBackgroundFocus) {
        $keyArgs['SkipBackgroundFocus'] = $true
    }

    & $keyScript @keyArgs *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Stimulus key '$key' failed."
    }
}

function Write-ValidationText {
    param($Document)

    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add('Actor facing validation')
    $lines.Add("Output file:                 $($Document.OutputFile)")
    $lines.Add("Generated (UTC):             $($Document.GeneratedAtUtc)")
    $lines.Add("Stimulus:                    $($Document.StimulusType)")
    $lines.Add("Repeat count:                $($Document.RepeatCount)")
    $lines.Add("Hold/Wait ms:                $($Document.HoldMilliseconds) / $($Document.WaitMilliseconds)")
    $lines.Add("Summary verdict:             $($Document.Summary.OverallVerdict)")
    $lines.Add("Pass/fail count:             $($Document.Summary.PassCount) / $($Document.Summary.FailCount)")
    $lines.Add("Median angular error (deg):  $(Format-Nullable $Document.Summary.MedianAngularErrorDegrees '0.000')")
    $lines.Add("Max angular error (deg):     $(Format-Nullable $Document.Summary.MaxAngularErrorDegrees '0.000')")
    if ($null -ne $Document.Summary.StabilityPass) {
        $lines.Add("Repeated-forward stability:  $($Document.Summary.StabilityPass)")
    }
    $lines.Add('Results:')

    foreach ($entry in $Document.Results) {
        $lines.Add("  - run $($entry.Iteration): $($entry.Verdict) | yaw Δ $(Format-Nullable $entry.YawDeltaDegrees '0.000') deg | move $(Format-Nullable $entry.PlanarCoordDelta.Distance '0.000000') | angular error $(Format-Nullable $entry.SignedAngularErrorDegrees '0.000') | failure $(if ($entry.FailureShape) { $entry.FailureShape } else { 'n/a' })")
    }

    return [string]::Join([Environment]::NewLine, $lines)
}

$results = New-Object System.Collections.Generic.List[object]
$historyEntries = Get-ValidationHistoryEntries -HistoryFile $resolvedHistoryFile

try {
    for ($iteration = 1; $iteration -le $RepeatCount; $iteration++) {
        $runLabel = '{0}-{1}' -f $Stimulus, $iteration
        $beforeFacingDocument = Invoke-FacingCapture -CaptureLabel ('before-{0}' -f $runLabel) -Iteration $iteration -Phase 'before-facing'
        $beforeBoundaryDocument = Invoke-BoundaryCapture -CaptureLabel ('before-{0}' -f $runLabel) -Iteration $iteration -Phase 'before-boundary'

        Invoke-Stimulus -StimulusType $Stimulus
        Start-Sleep -Milliseconds $WaitMilliseconds

        $afterFacingDocument = Invoke-FacingCapture -CaptureLabel ('after-{0}' -f $runLabel) -Iteration $iteration -Phase 'after-facing'
        $afterBoundaryDocument = Invoke-BoundaryCapture -CaptureLabel ('after-{0}' -f $runLabel) -Iteration $iteration -Phase 'after-boundary'

        $beforeFacing = Get-OptionalPropertyValue -InputObject $beforeFacingDocument -PropertyName 'ActorFacingSample'
        $afterFacing = Get-OptionalPropertyValue -InputObject $afterFacingDocument -PropertyName 'ActorFacingSample'
        $beforeCoord = Get-OptionalPropertyValue -InputObject $beforeBoundaryDocument -PropertyName 'PlayerCoord'
        $afterCoord = Get-OptionalPropertyValue -InputObject $afterBoundaryDocument -PropertyName 'PlayerCoord'

        $beforeYaw = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $beforeFacing -PropertyName 'YawRadians')
        $afterYaw = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $afterFacing -PropertyName 'YawRadians')
        $beforePitch = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $beforeFacing -PropertyName 'PitchRadians')
        $afterPitch = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $afterFacing -PropertyName 'PitchRadians')
        $beforeX = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $beforeCoord -PropertyName 'X')
        $beforeZ = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $beforeCoord -PropertyName 'Z')
        $afterX = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $afterCoord -PropertyName 'X')
        $afterZ = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $afterCoord -PropertyName 'Z')

        $planarDelta = [pscustomobject]@{
            DeltaX   = if ($null -ne $beforeX -and $null -ne $afterX) { $afterX - $beforeX } else { $null }
            DeltaZ   = if ($null -ne $beforeZ -and $null -ne $afterZ) { $afterZ - $beforeZ } else { $null }
            Distance = Get-PlanarDistance -LeftCoord $beforeCoord -RightCoord $afterCoord
        }

        $observedHeadingRadians = Get-ObservedHeadingRadians -BeforeCoord $beforeCoord -AfterCoord $afterCoord
        $observedHeadingDegrees = if ($null -ne $observedHeadingRadians) { Convert-RadiansToDegrees -Radians $observedHeadingRadians } else { $null }
        $predictedHeadingRadians = $beforeYaw
        $predictedHeadingDegrees = if ($null -ne $predictedHeadingRadians) { Convert-RadiansToDegrees -Radians $predictedHeadingRadians } else { $null }
        $signedAngularErrorDegrees = if ($null -ne $predictedHeadingRadians -and $null -ne $observedHeadingRadians) { Get-SignedAngularErrorDegrees -PredictedHeadingRadians $predictedHeadingRadians -ObservedHeadingRadians $observedHeadingRadians } else { $null }
        $yawDeltaDegrees = if ($null -ne $beforeYaw -and $null -ne $afterYaw) { Convert-RadiansToDegrees -Radians (Normalize-AngleRadians -Radians ($afterYaw - $beforeYaw)) } else { $null }
        $pitchDeltaDegrees = if ($null -ne $beforePitch -and $null -ne $afterPitch) { Convert-RadiansToDegrees -Radians (Normalize-AngleRadians -Radians ($afterPitch - $beforePitch)) } else { $null }

        $beforeIntegrity = Get-OptionalPropertyValue -InputObject (Get-OptionalPropertyValue -InputObject $beforeFacing -PropertyName 'Integrity') -PropertyName 'Pass'
        $afterIntegrity = Get-OptionalPropertyValue -InputObject (Get-OptionalPropertyValue -InputObject $afterFacing -PropertyName 'Integrity') -PropertyName 'Pass'
        $integrityPass = ([bool]$beforeIntegrity) -and ([bool]$afterIntegrity)

        $sourceAddress = [string](Get-OptionalPropertyValue -InputObject $beforeFacing -PropertyName 'SourceAddress')
        $basisForwardOffset = [string](Get-OptionalPropertyValue -InputObject $beforeFacing -PropertyName 'BasisForwardOffset')
        $combinedHistoryEntries = @($historyEntries) + @($results.ToArray())
        $turnResponsive = Test-SourceTurnResponsive -HistoryEntries $combinedHistoryEntries -SourceAddress $sourceAddress -BasisForwardOffset $basisForwardOffset
        $failureShape = if ($Stimulus -eq 'move-forward') {
            Classify-ActorFacingFailureShape -SignedAngularErrorDegrees $signedAngularErrorDegrees -MovementDistance ([double]$planarDelta.Distance) -IntegrityPass $integrityPass -TurnResponsive $turnResponsive -Thresholds $thresholds
        }
        else {
            $null
        }

        $verdict = if (Test-RunPass -StimulusType $Stimulus -PlanarDistance ([double]$planarDelta.Distance) -SignedAngularErrorDegrees $signedAngularErrorDegrees -YawDeltaDegrees $yawDeltaDegrees -IntegrityPass $integrityPass) { 'pass' } else { 'fail' }
        if ($Stimulus -eq 'move-forward' -and $verdict -eq 'pass') {
            $failureShape = 'none'
        }

        $runResult = [pscustomobject]@{
            Mode                        = 'actor-facing-validation-run'
            GeneratedAtUtc              = [DateTimeOffset]::UtcNow.ToString('O')
            StimulusType                = $Stimulus
            Iteration                   = $iteration
            SourceAddress               = $sourceAddress
            BasisForwardOffset          = $basisForwardOffset
            SourceName                  = Get-OptionalPropertyValue -InputObject $beforeFacing -PropertyName 'SourceName'
            BeforeAddonCoords           = $beforeCoord
            AfterAddonCoords            = $afterCoord
            BeforeFacingSample          = $beforeFacing
            AfterFacingSample           = $afterFacing
            PlanarCoordDelta            = $planarDelta
            ObservedMovementHeadingRadians = $observedHeadingRadians
            ObservedMovementHeadingDegrees = $observedHeadingDegrees
            PredictedHeadingRadians     = $predictedHeadingRadians
            PredictedHeadingDegrees     = $predictedHeadingDegrees
            SignedAngularErrorDegrees   = $signedAngularErrorDegrees
            YawDeltaDegrees             = $yawDeltaDegrees
            PitchDeltaDegrees           = $pitchDeltaDegrees
            HoldMilliseconds            = $HoldMilliseconds
            WaitMilliseconds            = $WaitMilliseconds
            IntegrityGateResult         = [pscustomobject]@{
                BeforePass = [bool]$beforeIntegrity
                AfterPass  = [bool]$afterIntegrity
                Pass       = $integrityPass
            }
            FailureShape                = $failureShape
            Verdict                     = $verdict
            Notes                       = @(
                $(if ($UsePlayerCurrentAnchorBoundary) { 'Boundary coords were read directly from the verified player-current anchor in live memory.' } elseif ($NoBoundaryTrigger) { 'Addon boundary coords were read from the latest available ReaderBridge snapshot without issuing /rbx export.' } else { 'Addon boundary coords are captured through explicit /rbx export boundaries.' }),
                'Predicted heading is derived from the before-sample actor yaw using atan2(forwardZ, forwardX).'
            )
        }

        $results.Add($runResult)
        $historyEntries = @($historyEntries) + @($runResult)

        $historyDirectory = Split-Path -Path $resolvedHistoryFile -Parent
        if (-not [string]::IsNullOrWhiteSpace($historyDirectory)) {
            New-Item -ItemType Directory -Path $historyDirectory -Force | Out-Null
        }

        Add-Content -LiteralPath $resolvedHistoryFile -Value ($runResult | ConvertTo-Json -Depth 80 -Compress)
    }
}
finally {
    foreach ($path in $tempPaths) {
        Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
    }
}

$angularErrors = @($results | Where-Object { $null -ne $_.SignedAngularErrorDegrees } | ForEach-Object { [Math]::Abs([double]$_.SignedAngularErrorDegrees) })
$passCount = @($results | Where-Object { $_.Verdict -eq 'pass' }).Count
$failCount = $results.Count - $passCount
$stabilityPass = $null
if ($Stimulus -eq 'move-forward' -and $results.Count -ge 5) {
    $medianAngularError = Get-Median -Values $angularErrors
    $maxAngularError = Get-MaximumValue -Values $angularErrors
    $stabilityPass = $angularErrors.Count -ge 5 -and $medianAngularError -le $thresholds.RepeatedForwardMedianAngularErrorDegrees -and $maxAngularError -le $thresholds.RepeatedForwardSingleAngularErrorDegrees
}

$overallVerdict = if ($null -ne $stabilityPass) {
    if ($failCount -eq 0 -and $stabilityPass) { 'pass' } else { 'fail' }
}
else {
    if ($failCount -eq 0) { 'pass' } else { 'fail' }
}

$failureShapeCounts = @{}
foreach ($entry in @($results | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_.FailureShape) })) {
    if (-not $failureShapeCounts.ContainsKey([string]$entry.FailureShape)) {
        $failureShapeCounts[[string]$entry.FailureShape] = 0
    }

    $failureShapeCounts[[string]$entry.FailureShape]++
}

$document = [pscustomobject]@{
    Mode            = 'actor-facing-validation'
    GeneratedAtUtc  = [DateTimeOffset]::UtcNow.ToString('O')
    OutputFile      = $resolvedOutputFile
    HistoryFile     = $resolvedHistoryFile
    StimulusType    = $Stimulus
    RepeatCount     = $RepeatCount
    HoldMilliseconds = $HoldMilliseconds
    WaitMilliseconds = $WaitMilliseconds
    Results         = $results
    Summary         = [pscustomobject]@{
        OverallVerdict          = $overallVerdict
        PassCount               = $passCount
        FailCount               = $failCount
        MedianAngularErrorDegrees = Get-Median -Values $angularErrors
        MaxAngularErrorDegrees  = Get-MaximumValue -Values $angularErrors
        StabilityPass           = $stabilityPass
        FailureShapeCounts      = $failureShapeCounts
    }
    Notes           = @(
        $(if ($UsePlayerCurrentAnchorBoundary) { 'This validation used direct live memory reads from the verified player-current anchor for movement-boundary coordinates.' } elseif ($NoBoundaryTrigger) { 'This validation used read-only ReaderBridge snapshot reads and did not issue /rbx export during boundary capture.' } else { 'Boundary captures issued /rbx export to tighten stimulus-boundary timing.' }),
        'Use idle plus turn-left / turn-right validation before treating forward-move mismatch as authoritative source failure.',
        $(if ($UsePlayerCurrentAnchorBoundary) { 'Forward movement acceptance uses live player-current anchor coords sampled directly from memory.' } else { 'Forward movement acceptance uses addon boundary coords, not saved-variable heartbeat timing.' })
    )
}

$outputDirectory = Split-Path -Path $resolvedOutputFile -Parent
if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

$jsonText = $document | ConvertTo-Json -Depth 80
[System.IO.File]::WriteAllText($resolvedOutputFile, $jsonText)

if ($Json) {
    Write-Output $jsonText
    return
}

Write-Output (Write-ValidationText -Document $document)

