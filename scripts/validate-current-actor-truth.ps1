[CmdletBinding()]
param(
    [string]$TruthFile,
    [switch]$RequireLiveTarget,
    [string]$LiveTargetSnapshotFile,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$TruthFile = if ([string]::IsNullOrWhiteSpace($TruthFile)) {
    Join-Path $repoRoot 'docs\recovery\current-actor-truth.json'
}
else {
    $TruthFile
}

$resolvedTruthFile = [System.IO.Path]::GetFullPath($TruthFile)
$failures = New-Object System.Collections.Generic.List[string]
$warnings = New-Object System.Collections.Generic.List[string]

function Add-Failure {
    param([Parameter(Mandatory = $true)][string]$Message)
    $failures.Add($Message) | Out-Null
}

function Get-Prop {
    param(
        $Object,
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    if ($null -eq $Object) {
        return $null
    }

    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $null
    }

    return $property.Value
}

function Assert-True {
    param(
        [Parameter(Mandatory = $true)]
        [bool]$Condition,
        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    if (-not $Condition) {
        Add-Failure -Message $Message
    }
}

function Assert-Equal {
    param(
        $Actual,
        $Expected,
        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    if ($Actual -ne $Expected) {
        Add-Failure -Message ("{0} Expected '{1}', got '{2}'." -f $Message, $Expected, $Actual)
    }
}

function Assert-NonBlank {
    param(
        $Value,
        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    Assert-True -Condition (-not [string]::IsNullOrWhiteSpace([string]$Value)) -Message $Message
}

function Assert-HexAddress {
    param(
        $Value,
        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    Assert-True -Condition (([string]$Value) -match '^0x[0-9A-Fa-f]+$') -Message $Message
}

function Convert-ToDoubleOrNull {
    param($Value)

    if ($null -eq $Value) {
        return $null
    }

    try {
        return [double]$Value
    }
    catch {
        return $null
    }
}

function Get-FirstProp {
    param(
        $Object,
        [Parameter(Mandatory = $true)]
        [string[]]$Names
    )

    foreach ($name in $Names) {
        $value = Get-Prop -Object $Object -Name $name
        if ($null -ne $value) {
            return $value
        }
    }

    return $null
}

function Convert-ToDateTimeOffsetOrNull {
    param($Value)

    if ($Value -is [DateTimeOffset]) {
        return $Value
    }

    if ($Value -is [DateTime]) {
        return [DateTimeOffset]$Value
    }

    if ([string]::IsNullOrWhiteSpace([string]$Value)) {
        return $null
    }

    try {
        return [DateTimeOffset]::Parse(
            [string]$Value,
            [System.Globalization.CultureInfo]::InvariantCulture,
            [System.Globalization.DateTimeStyles]::RoundtripKind)
    }
    catch {
        return $null
    }
}

function Convert-ToHexHandleOrNull {
    param($Value)

    if ($null -eq $Value -or [string]::IsNullOrWhiteSpace([string]$Value)) {
        return $null
    }

    $text = ([string]$Value).Trim()
    try {
        if ($text.StartsWith('0x', [System.StringComparison]::OrdinalIgnoreCase)) {
            $number = [Convert]::ToInt64($text.Substring(2), 16)
        }
        else {
            $number = [Convert]::ToInt64($text, [System.Globalization.CultureInfo]::InvariantCulture)
        }

        if ($number -eq 0) {
            return $null
        }

        return ('0x{0:X}' -f $number)
    }
    catch {
        return $text.ToUpperInvariant()
    }
}

function Convert-ToNormalizedProcessName {
    param($Value)

    if ([string]::IsNullOrWhiteSpace([string]$Value)) {
        return $null
    }

    $name = ([string]$Value).Trim()
    if ($name.EndsWith('.exe', [System.StringComparison]::OrdinalIgnoreCase)) {
        $name = $name.Substring(0, $name.Length - 4)
    }

    return $name.ToLowerInvariant()
}

function Test-LiveTarget {
    param(
        $Target,
        [string]$SnapshotFile,
        [switch]$Require
    )

    $enabled = $Require.IsPresent -or -not [string]::IsNullOrWhiteSpace($SnapshotFile)
    $result = [ordered]@{
        enabled = $enabled
        status = if ($enabled) { 'checked' } else { 'skipped' }
        snapshotFile = $null
        processId = $null
        processName = $null
        processStartTimeUtc = $null
        targetWindowHandle = $null
    }

    if (-not $enabled) {
        return $result
    }

    $failureStartCount = $failures.Count
    $snapshot = $null

    if (-not [string]::IsNullOrWhiteSpace($SnapshotFile)) {
        $resolvedSnapshotFile = [System.IO.Path]::GetFullPath($SnapshotFile)
        $result.snapshotFile = $resolvedSnapshotFile
        if (-not (Test-Path -LiteralPath $resolvedSnapshotFile)) {
            Add-Failure -Message "Live target snapshot file was not found: $resolvedSnapshotFile"
            $result.status = 'fail'
            return $result
        }

        try {
            $snapshot = Get-Content -LiteralPath $resolvedSnapshotFile -Raw | ConvertFrom-Json -Depth 20
        }
        catch {
            Add-Failure -Message "Live target snapshot file is not valid JSON: $($_.Exception.Message)"
            $result.status = 'fail'
            return $result
        }
    }
    else {
        try {
            $expectedProcessId = [int](Get-Prop -Object $Target -Name 'processId')
        }
        catch {
            Add-Failure -Message 'target.processId must be numeric for live target validation.'
            $result.status = 'fail'
            return $result
        }

        $process = Get-Process -Id $expectedProcessId -ErrorAction SilentlyContinue
        if ($null -eq $process) {
            Add-Failure -Message "Live target process was not found for target.processId '$expectedProcessId'."
            $result.status = 'fail'
            return $result
        }

        $snapshot = [pscustomobject]@{
            processName = $process.ProcessName
            processId = $process.Id
            processStartTimeUtc = $process.StartTime.ToUniversalTime().ToString('o', [System.Globalization.CultureInfo]::InvariantCulture)
            targetWindowHandle = ('0x{0:X}' -f $process.MainWindowHandle.ToInt64())
            mainWindowTitle = $process.MainWindowTitle
        }
    }

    $expectedProcessIdValue = [int](Get-Prop -Object $Target -Name 'processId')
    $actualProcessIdValue = [int](Get-FirstProp -Object $snapshot -Names @('processId', 'ProcessId', 'id', 'Id'))
    $expectedProcessName = Convert-ToNormalizedProcessName (Get-Prop -Object $Target -Name 'processName')
    $actualProcessName = Convert-ToNormalizedProcessName (Get-FirstProp -Object $snapshot -Names @('processName', 'ProcessName', 'name', 'Name'))
    $expectedStart = Convert-ToDateTimeOffsetOrNull (Get-Prop -Object $Target -Name 'processStartTimeUtc')
    $actualStart = Convert-ToDateTimeOffsetOrNull (Get-FirstProp -Object $snapshot -Names @('processStartTimeUtc', 'ProcessStartTimeUtc', 'startTimeUtc', 'StartTimeUtc'))
    $expectedHandle = Convert-ToHexHandleOrNull (Get-Prop -Object $Target -Name 'targetWindowHandle')
    $actualHandle = Convert-ToHexHandleOrNull (Get-FirstProp -Object $snapshot -Names @('targetWindowHandle', 'TargetWindowHandle', 'mainWindowHandle', 'MainWindowHandle', 'hwnd', 'Hwnd'))

    $result.processId = $actualProcessIdValue
    $result.processName = [string](Get-FirstProp -Object $snapshot -Names @('processName', 'ProcessName', 'name', 'Name'))
    $result.processStartTimeUtc = if ($null -ne $actualStart) { $actualStart.UtcDateTime.ToString('o', [System.Globalization.CultureInfo]::InvariantCulture) } else { $null }
    $result.targetWindowHandle = $actualHandle

    Assert-Equal -Actual $actualProcessIdValue -Expected $expectedProcessIdValue -Message 'live target processId mismatch.'
    Assert-Equal -Actual $actualProcessName -Expected $expectedProcessName -Message 'live target processName mismatch.'

    if ($null -eq $expectedStart) {
        Add-Failure -Message 'target.processStartTimeUtc must be parseable for live target validation.'
    }
    elseif ($null -eq $actualStart) {
        Add-Failure -Message 'live target processStartTimeUtc must be parseable.'
    }
    else {
        $startDeltaSeconds = [Math]::Abs(($actualStart.UtcDateTime - $expectedStart.UtcDateTime).TotalSeconds)
        if ($startDeltaSeconds -gt 2.0) {
            Add-Failure -Message ("live target processStartTimeUtc mismatch. Expected '{0}', got '{1}'." -f $expectedStart.UtcDateTime.ToString('o', [System.Globalization.CultureInfo]::InvariantCulture), $actualStart.UtcDateTime.ToString('o', [System.Globalization.CultureInfo]::InvariantCulture))
        }
    }

    if ($null -eq $expectedHandle) {
        Add-Failure -Message 'target.targetWindowHandle must be a non-zero hex HWND for live target validation.'
    }
    elseif ($null -eq $actualHandle) {
        Add-Failure -Message 'live target targetWindowHandle must be present and non-zero.'
    }
    else {
        Assert-Equal -Actual $actualHandle -Expected $expectedHandle -Message 'live target targetWindowHandle mismatch.'
    }

    $result.status = if ($failures.Count -eq $failureStartCount) { 'pass' } else { 'fail' }
    return $result
}

if (-not (Test-Path -LiteralPath $resolvedTruthFile)) {
    Add-Failure -Message "Truth file was not found: $resolvedTruthFile"
    $document = $null
}
else {
    try {
        $document = Get-Content -LiteralPath $resolvedTruthFile -Raw | ConvertFrom-Json -Depth 80
    }
    catch {
        Add-Failure -Message "Truth file is not valid JSON: $($_.Exception.Message)"
        $document = $null
    }
}

$target = Get-Prop -Object $document -Name 'target'
$coordinate = Get-Prop -Object $document -Name 'coordinate'
$watchsetRegion = Get-Prop -Object $coordinate -Name 'requiredWatchsetRegion'
$actorFacing = Get-Prop -Object $document -Name 'actorFacing'
$facingValidation = Get-Prop -Object $actorFacing -Name 'validation'
$autoTurn = Get-Prop -Object $document -Name 'autoTurn'
$activeMovement = Get-Prop -Object $document -Name 'activeMovement'
$postActiveTelemetry = Get-Prop -Object $activeMovement -Name 'postActiveTelemetry'
$postActiveNavigation = Get-Prop -Object $activeMovement -Name 'postActiveNavigation'
$staleOrHistorical = Get-Prop -Object $document -Name 'staleOrHistorical'
$caveats = @(Get-Prop -Object $document -Name 'caveats')

if ($null -ne $document) {
    Assert-Equal -Actual (Get-Prop -Object $document -Name 'schemaVersion') -Expected 1 -Message 'schemaVersion mismatch.'
    Assert-Equal -Actual ([string](Get-Prop -Object $document -Name 'mode')) -Expected 'current-actor-truth' -Message 'mode mismatch.'
    Assert-Equal -Actual ([string](Get-Prop -Object $document -Name 'status')) -Expected 'current-live-session-validated' -Message 'status mismatch.'
    Assert-True -Condition ([bool](Get-Prop -Object $document -Name 'sessionBound')) -Message 'sessionBound must be true for address-bearing current actor truth.'
    Assert-NonBlank -Value (Get-Prop -Object $document -Name 'lastUpdatedUtc') -Message 'lastUpdatedUtc is required.'
}

Assert-NonBlank -Value (Get-Prop -Object $target -Name 'processName') -Message 'target.processName is required.'
Assert-True -Condition ([int](Get-Prop -Object $target -Name 'processId') -gt 0) -Message 'target.processId must be positive.'
Assert-HexAddress -Value (Get-Prop -Object $target -Name 'targetWindowHandle') -Message 'target.targetWindowHandle must be a hex HWND.'
Assert-NonBlank -Value (Get-Prop -Object $target -Name 'processStartTimeUtc') -Message 'target.processStartTimeUtc is required.'
Assert-NonBlank -Value (Get-Prop -Object $target -Name 'character') -Message 'target.character is required.'
Assert-NonBlank -Value (Get-Prop -Object $target -Name 'location') -Message 'target.location is required.'

$liveTargetCheck = Test-LiveTarget -Target $target -SnapshotFile $LiveTargetSnapshotFile -Require:$RequireLiveTarget.IsPresent

Assert-Equal -Actual ([string](Get-Prop -Object $coordinate -Name 'status')) -Expected 'proof-grade-current-session' -Message 'coordinate.status mismatch.'
Assert-HexAddress -Value (Get-Prop -Object $coordinate -Name 'sourceObjectAddress') -Message 'coordinate.sourceObjectAddress must be a hex address.'
Assert-HexAddress -Value (Get-Prop -Object $coordinate -Name 'coordRegionAddress') -Message 'coordinate.coordRegionAddress must be a hex address.'
Assert-Equal -Actual ([int](Get-Prop -Object $coordinate -Name 'sourceCoordRelativeOffset')) -Expected 72 -Message 'coordinate.sourceCoordRelativeOffset should stay on the proven +0x48 actor coord surface.'
Assert-Equal -Actual ([string](Get-Prop -Object $coordinate -Name 'canonicalCoordSourceKind')) -Expected 'coord-trace-direct-region' -Message 'coordinate.canonicalCoordSourceKind mismatch.'
Assert-True -Condition ([bool](Get-Prop -Object $coordinate -Name 'coordMatchesWithinTolerance')) -Message 'coordinate.coordMatchesWithinTolerance must be true.'
Assert-Equal -Actual ([string](Get-Prop -Object $watchsetRegion -Name 'name')) -Expected 'coord-trace-coords' -Message 'requiredWatchsetRegion.name mismatch.'
Assert-Equal -Actual ([string](Get-Prop -Object $watchsetRegion -Name 'address')) -Expected ([string](Get-Prop -Object $coordinate -Name 'coordRegionAddress')) -Message 'requiredWatchsetRegion.address must match coordinate.coordRegionAddress.'
Assert-Equal -Actual ([int](Get-Prop -Object $watchsetRegion -Name 'length')) -Expected 12 -Message 'requiredWatchsetRegion.length must cover the 12-byte X/Y/Z triplet.'

Assert-Equal -Actual ([string](Get-Prop -Object $actorFacing -Name 'status')) -Expected 'behavior-backed-current-session' -Message 'actorFacing.status mismatch.'
Assert-HexAddress -Value (Get-Prop -Object $actorFacing -Name 'sourceAddress') -Message 'actorFacing.sourceAddress must be a hex address.'
Assert-Equal -Actual ([string](Get-Prop -Object $actorFacing -Name 'sourceAddress')) -Expected ([string](Get-Prop -Object $coordinate -Name 'sourceObjectAddress')) -Message 'actorFacing.sourceAddress must match coordinate.sourceObjectAddress for this current truth packet.'
Assert-Equal -Actual ([string](Get-Prop -Object $actorFacing -Name 'basisForwardOffset')) -Expected '0x60' -Message 'actorFacing.basisForwardOffset mismatch.'
Assert-Equal -Actual ([string](Get-Prop -Object $actorFacing -Name 'basisDuplicateForwardOffset')) -Expected '0x94' -Message 'actorFacing.basisDuplicateForwardOffset mismatch.'
Assert-True -Condition ([bool](Get-Prop -Object $actorFacing -Name 'duplicateAgreementStrong')) -Message 'actorFacing.duplicateAgreementStrong must be true.'
Assert-Equal -Actual ([string](Get-Prop -Object $actorFacing -Name 'yawFormula')) -Expected 'atan2(forwardZ, forwardX)' -Message 'actorFacing.yawFormula mismatch.'
Assert-Equal -Actual ([string](Get-Prop -Object $actorFacing -Name 'pitchFormula')) -Expected 'atan2(forwardY, sqrt(forwardX^2 + forwardZ^2))' -Message 'actorFacing.pitchFormula mismatch.'

$forwardDelta = Convert-ToDoubleOrNull (Get-Prop -Object $facingValidation -Name 'forwardYawDeltaDegrees')
$reverseDelta = Convert-ToDoubleOrNull (Get-Prop -Object $facingValidation -Name 'reverseYawDeltaDegrees')
$duplicateForwardDelta = Convert-ToDoubleOrNull (Get-Prop -Object $facingValidation -Name 'duplicateForwardYawDeltaDegrees')
$duplicateReverseDelta = Convert-ToDoubleOrNull (Get-Prop -Object $facingValidation -Name 'duplicateReverseYawDeltaDegrees')
$coordDelta = Convert-ToDoubleOrNull (Get-Prop -Object $facingValidation -Name 'playerCoordDeltaMagnitude')
Assert-True -Condition ($null -ne $forwardDelta -and [Math]::Abs($forwardDelta) -gt 30.0) -Message 'actorFacing.validation.forwardYawDeltaDegrees must show a meaningful yaw response.'
Assert-True -Condition ($null -ne $reverseDelta -and [Math]::Abs($reverseDelta) -gt 30.0) -Message 'actorFacing.validation.reverseYawDeltaDegrees must show a meaningful yaw response.'
Assert-True -Condition ($null -ne $forwardDelta -and $null -ne $reverseDelta -and [Math]::Sign($forwardDelta) -ne [Math]::Sign($reverseDelta)) -Message 'actorFacing.validation forward/reverse yaw deltas must be opposite signs.'
Assert-True -Condition ($null -ne $duplicateForwardDelta -and $null -ne $forwardDelta -and [Math]::Abs($duplicateForwardDelta - $forwardDelta) -lt 0.01) -Message 'actorFacing duplicate forward yaw delta must agree with the primary row.'
Assert-True -Condition ($null -ne $duplicateReverseDelta -and $null -ne $reverseDelta -and [Math]::Abs($duplicateReverseDelta - $reverseDelta) -lt 0.01) -Message 'actorFacing duplicate reverse yaw delta must agree with the primary row.'
Assert-True -Condition ($null -ne $coordDelta -and $coordDelta -lt 0.001) -Message 'actorFacing.validation.playerCoordDeltaMagnitude should remain effectively zero during D/A yaw validation.'
Assert-NonBlank -Value (Get-Prop -Object $facingValidation -Name 'validationArtifact') -Message 'actorFacing.validation.validationArtifact is required.'

Assert-Equal -Actual ([string](Get-Prop -Object $autoTurn -Name 'status')) -Expected 'preflight-green' -Message 'autoTurn.status mismatch.'
Assert-True -Condition ([double](Get-Prop -Object $autoTurn -Name 'startDeltaDegrees') -gt [double](Get-Prop -Object $autoTurn -Name 'finalDeltaDegrees')) -Message 'autoTurn final delta must improve from start delta.'
Assert-True -Condition ([int](Get-Prop -Object $autoTurn -Name 'pulses') -gt 0) -Message 'autoTurn.pulses must be positive.'
Assert-True -Condition (-not [bool](Get-Prop -Object $autoTurn -Name 'sentForwardMovement')) -Message 'autoTurn.sentForwardMovement must remain false for the preflight proof.'

Assert-Equal -Actual ([string](Get-Prop -Object $activeMovement -Name 'status')) -Expected 'success' -Message 'activeMovement.status mismatch.'
Assert-Equal -Actual ([string](Get-Prop -Object $activeMovement -Name 'stopReason')) -Expected 'arrived' -Message 'activeMovement.stopReason mismatch.'
Assert-Equal -Actual ([string](Get-Prop -Object $activeMovement -Name 'anchorSource')) -Expected 'coord-trace-anchor' -Message 'activeMovement.anchorSource mismatch.'
Assert-True -Condition ([int](Get-Prop -Object $activeMovement -Name 'pulseCount') -gt 0) -Message 'activeMovement.pulseCount must be positive.'
Assert-True -Condition ([double](Get-Prop -Object $activeMovement -Name 'initialPlanarDistance') -gt [double](Get-Prop -Object $activeMovement -Name 'finalPlanarDistance')) -Message 'activeMovement final planar distance must improve.'
Assert-True -Condition ([double](Get-Prop -Object $activeMovement -Name 'planarMoved') -gt 0.0) -Message 'activeMovement.planarMoved must be positive.'
Assert-True -Condition ([bool](Get-Prop -Object $postActiveTelemetry -Name 'memoryCoordValid')) -Message 'postActiveTelemetry.memoryCoordValid must be true.'
Assert-True -Condition ([bool](Get-Prop -Object $postActiveTelemetry -Name 'facingValid')) -Message 'postActiveTelemetry.facingValid must be true.'
Assert-Equal -Actual ([string](Get-Prop -Object $postActiveNavigation -Name 'currentAddress')) -Expected ([string](Get-Prop -Object $coordinate -Name 'coordRegionAddress')) -Message 'postActiveNavigation.currentAddress must match coordinate.coordRegionAddress.'
Assert-True -Condition ([bool](Get-Prop -Object $postActiveNavigation -Name 'withinArrivalRadius')) -Message 'postActiveNavigation.withinArrivalRadius must be true.'
Assert-Equal -Actual ([string](Get-Prop -Object $postActiveNavigation -Name 'facingSource')) -Expected ([string](Get-Prop -Object $actorFacing -Name 'sourceAddress')) -Message 'postActiveNavigation.facingSource must match actorFacing.sourceAddress.'
Assert-Equal -Actual ([string](Get-Prop -Object $postActiveNavigation -Name 'facingOffset')) -Expected ([string](Get-Prop -Object $actorFacing -Name 'basisForwardOffset')) -Message 'postActiveNavigation.facingOffset must match actorFacing.basisForwardOffset.'

Assert-NonBlank -Value (Get-Prop -Object $staleOrHistorical -Name 'previousBehaviorBackedLead') -Message 'staleOrHistorical.previousBehaviorBackedLead is required.'
Assert-True -Condition ($caveats.Count -gt 0) -Message 'At least one caveat is required for session-bound address truth.'

$status = if ($failures.Count -eq 0) { 'pass' } else { 'fail' }
$result = [ordered]@{
    mode = 'current-actor-truth-validation'
    truthFile = $resolvedTruthFile
    status = $status
    failureCount = $failures.Count
    failures = @($failures.ToArray())
    warnings = @($warnings.ToArray())
    liveTargetCheck = $liveTargetCheck
    coordRegionAddress = [string](Get-Prop -Object $coordinate -Name 'coordRegionAddress')
    sourceObjectAddress = [string](Get-Prop -Object $coordinate -Name 'sourceObjectAddress')
    actorFacingSourceAddress = [string](Get-Prop -Object $actorFacing -Name 'sourceAddress')
    actorFacingOffset = [string](Get-Prop -Object $actorFacing -Name 'basisForwardOffset')
    activeMovementStatus = [string](Get-Prop -Object $activeMovement -Name 'status')
    activeMovementStopReason = [string](Get-Prop -Object $activeMovement -Name 'stopReason')
}

if ($Json) {
    $result | ConvertTo-Json -Depth 12
}
elseif ($status -eq 'pass') {
    Write-Host ("current actor truth validation passed: {0} @ {1}; coords {2}" -f $result.actorFacingSourceAddress, $result.actorFacingOffset, $result.coordRegionAddress) -ForegroundColor Green
}
else {
    Write-Host "current actor truth validation failed:" -ForegroundColor Red
    foreach ($failure in $failures) {
        Write-Host ("- {0}" -f $failure) -ForegroundColor Red
    }
}

if ($status -ne 'pass') {
    exit 1
}
