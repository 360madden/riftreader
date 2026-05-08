[CmdletBinding()]
param(
    [string]$PacketFile = (Join-Path $PSScriptRoot '..\docs\recovery\current-actor-yaw-restart-check.json'),
    [string]$LeadFile,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Test-Property {
    param(
        [Parameter(Mandatory = $true)]
        $Object,
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    return $null -ne $Object -and $null -ne $Object.PSObject.Properties[$Name]
}

function Get-PropertyValue {
    param(
        $Object,
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    if (-not (Test-Property -Object $Object -Name $Name)) {
        return $null
    }

    return $Object.PSObject.Properties[$Name].Value
}

function Test-HexString {
    param($Value)

    return -not [string]::IsNullOrWhiteSpace([string]$Value) -and
        [string]$Value -match '^0x[0-9A-Fa-f]+$'
}

function Add-Failure {
    param(
        [System.Collections.Generic.List[string]]$Failures,
        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    $Failures.Add($Message) | Out-Null
}

function Convert-ToInvariantString {
    param($Value)

    if ($null -eq $Value) {
        return $null
    }

    return [string]$Value
}

$resolvedPacketFile = [System.IO.Path]::GetFullPath($PacketFile)
$failures = [System.Collections.Generic.List[string]]::new()
$warnings = [System.Collections.Generic.List[string]]::new()

if (-not (Test-Path -LiteralPath $resolvedPacketFile)) {
    Add-Failure -Failures $failures -Message "Packet file not found: $resolvedPacketFile"
}

$packet = $null
if ($failures.Count -eq 0) {
    try {
        $packet = Get-Content -LiteralPath $resolvedPacketFile -Raw | ConvertFrom-Json -Depth 80
    }
    catch {
        Add-Failure -Failures $failures -Message "Packet file is not valid JSON: $($_.Exception.Message)"
    }
}

if ($null -ne $packet) {
    if ([int](Get-PropertyValue -Object $packet -Name 'schemaVersion') -ne 1) {
        Add-Failure -Failures $failures -Message "schemaVersion must be 1."
    }

    if ([string](Get-PropertyValue -Object $packet -Name 'mode') -ne 'current-actor-yaw-restart-check') {
        Add-Failure -Failures $failures -Message "mode must be 'current-actor-yaw-restart-check'."
    }

    if (-not [bool](Get-PropertyValue -Object $packet -Name 'sessionBound')) {
        Add-Failure -Failures $failures -Message "sessionBound must be true for restart-check packets."
    }

    $target = Get-PropertyValue -Object $packet -Name 'target'
    if ($null -eq $target) {
        Add-Failure -Failures $failures -Message "target section is required."
    }
    else {
        if ([string](Get-PropertyValue -Object $target -Name 'processName') -ne 'rift_x64') {
            Add-Failure -Failures $failures -Message "target.processName must be 'rift_x64'."
        }

        if ([int](Get-PropertyValue -Object $target -Name 'processId') -le 0) {
            Add-Failure -Failures $failures -Message "target.processId must be positive."
        }

        if (-not (Test-HexString -Value (Get-PropertyValue -Object $target -Name 'targetWindowHandle'))) {
            Add-Failure -Failures $failures -Message "target.targetWindowHandle must be a hex handle."
        }

        if ([string]::IsNullOrWhiteSpace([string](Get-PropertyValue -Object $target -Name 'processStartTimeUtc'))) {
            Add-Failure -Failures $failures -Message "target.processStartTimeUtc is required."
        }
    }

    $actorFacing = Get-PropertyValue -Object $packet -Name 'actorFacing'
    if ($null -eq $actorFacing) {
        Add-Failure -Failures $failures -Message "actorFacing section is required."
    }
    else {
        if ([string](Get-PropertyValue -Object $actorFacing -Name 'status') -ne 'behavior-backed-current-session') {
            Add-Failure -Failures $failures -Message "actorFacing.status must be 'behavior-backed-current-session'."
        }

        if (-not (Test-HexString -Value (Get-PropertyValue -Object $actorFacing -Name 'sourceAddress'))) {
            Add-Failure -Failures $failures -Message "actorFacing.sourceAddress must be a hex address."
        }

        if (-not (Test-HexString -Value (Get-PropertyValue -Object $actorFacing -Name 'basisForwardOffset'))) {
            Add-Failure -Failures $failures -Message "actorFacing.basisForwardOffset must be a hex offset."
        }

        if ([string](Get-PropertyValue -Object $actorFacing -Name 'yawFormula') -ne 'atan2(forwardZ, forwardX)') {
            Add-Failure -Failures $failures -Message "actorFacing.yawFormula must be the canonical yaw formula."
        }

        $validation = Get-PropertyValue -Object $actorFacing -Name 'validation'
        if ($null -eq $validation) {
            Add-Failure -Failures $failures -Message "actorFacing.validation section is required."
        }
        else {
            $validationMethod = [string](Get-PropertyValue -Object $validation -Name 'method')
            if ($validationMethod -eq 'isolated-disambiguation-survivor-plus-no-input-readback') {
                if (-not [bool](Get-PropertyValue -Object $validation -Name 'truthLike')) {
                    Add-Failure -Failures $failures -Message "actorFacing.validation.truthLike must be true for isolated disambiguation restart baselines."
                }

                if (-not [bool](Get-PropertyValue -Object $validation -Name 'candidateResponsive')) {
                    Add-Failure -Failures $failures -Message "actorFacing.validation.candidateResponsive must be true for isolated disambiguation restart baselines."
                }

                $reversibleCandidateCount = [int](Get-PropertyValue -Object $validation -Name 'reversibleCandidateCount')
                $reversibleCycleCount = [int](Get-PropertyValue -Object $validation -Name 'reversibleCycleCount')
                if ($reversibleCandidateCount -lt 1 -and $reversibleCycleCount -lt 1) {
                    Add-Failure -Failures $failures -Message "actorFacing.validation must record at least one reversible candidate/cycle."
                }

                if ([double](Get-PropertyValue -Object $validation -Name 'playerCoordDeltaMagnitude') -ne 0.0) {
                    Add-Failure -Failures $failures -Message "actorFacing.validation.playerCoordDeltaMagnitude must be 0.0 for turn-only proof."
                }

                if ([string](Get-PropertyValue -Object $validation -Name 'readPlayerOrientationStatus') -ne 'passed') {
                    Add-Failure -Failures $failures -Message "actorFacing.validation.readPlayerOrientationStatus must be 'passed'."
                }

                if ([string](Get-PropertyValue -Object $validation -Name 'captureActorOrientationStatus') -ne 'passed') {
                    Add-Failure -Failures $failures -Message "actorFacing.validation.captureActorOrientationStatus must be 'passed'."
                }

                if ([bool](Get-PropertyValue -Object $validation -Name 'movementSent')) {
                    Add-Failure -Failures $failures -Message "actorFacing.validation.movementSent must be false for restart baselines."
                }

                if (-not [bool](Get-PropertyValue -Object $validation -Name 'noCheatEngine')) {
                    Add-Failure -Failures $failures -Message "actorFacing.validation.noCheatEngine must be true."
                }

                if ([bool](Get-PropertyValue -Object $validation -Name 'writesToRiftScan')) {
                    Add-Failure -Failures $failures -Message "actorFacing.validation.writesToRiftScan must be false."
                }

                if ([bool](Get-PropertyValue -Object $validation -Name 'savedVariablesUsedAsLiveTruth')) {
                    Add-Failure -Failures $failures -Message "actorFacing.validation.savedVariablesUsedAsLiveTruth must be false."
                }
            }
            else {
                $forwardDelta = [double](Get-PropertyValue -Object $validation -Name 'forwardYawDeltaDegrees')
                $reverseDelta = [double](Get-PropertyValue -Object $validation -Name 'reverseYawDeltaDegrees')
                if ([Math]::Abs($forwardDelta) -lt 30.0) {
                    Add-Failure -Failures $failures -Message "actorFacing.validation.forwardYawDeltaDegrees is too small to prove behavior-backed yaw."
                }

                if ([Math]::Abs($reverseDelta) -lt 30.0) {
                    Add-Failure -Failures $failures -Message "actorFacing.validation.reverseYawDeltaDegrees is too small to prove behavior-backed yaw."
                }

                if ([Math]::Sign($forwardDelta) -eq [Math]::Sign($reverseDelta)) {
                    Add-Failure -Failures $failures -Message "actorFacing.validation yaw deltas must reverse direction."
                }

                if ([double](Get-PropertyValue -Object $validation -Name 'playerCoordDeltaMagnitude') -ne 0.0) {
                    Add-Failure -Failures $failures -Message "actorFacing.validation.playerCoordDeltaMagnitude must be 0.0 for turn-only proof."
                }
            }
        }
    }

    $coordinate = Get-PropertyValue -Object $packet -Name 'coordinate'
    $movementGate = Get-PropertyValue -Object $packet -Name 'movementGate'
    if ($null -eq $coordinate) {
        Add-Failure -Failures $failures -Message "coordinate section is required."
    }

    if ($null -eq $movementGate) {
        Add-Failure -Failures $failures -Message "movementGate section is required."
    }
    elseif ($null -ne $coordinate) {
        $coordStatus = [string](Get-PropertyValue -Object $coordinate -Name 'status')
        $activeMovementAllowed = [bool](Get-PropertyValue -Object $movementGate -Name 'activeMovementAllowed')
        if ($coordStatus -ne 'proof-grade-after-restart' -and $activeMovementAllowed) {
            Add-Failure -Failures $failures -Message "movementGate.activeMovementAllowed must be false unless coordinate.status is proof-grade-after-restart."
        }

        $packetStatus = [string](Get-PropertyValue -Object $packet -Name 'status')
        $allowedNonRestartProofStatuses = @(
            'yaw-current-coord-proof-blocked',
            'phase2-pre-restart-baseline-ready'
        )
        if ($coordStatus -ne 'proof-grade-after-restart' -and $packetStatus -notin $allowedNonRestartProofStatuses) {
            Add-Failure -Failures $failures -Message "packet.status must be an allowed non-restart-proof status while coordinates are not proof-grade-after-restart."
        }

        if ($coordStatus -eq 'proof-grade-before-restart') {
            if ([string](Get-PropertyValue -Object $coordinate -Name 'latestProofOnlyStatus') -ne 'passed-proof-only') {
                Add-Failure -Failures $failures -Message "coordinate.latestProofOnlyStatus must be 'passed-proof-only' for proof-grade-before-restart packets."
            }

            if ([bool](Get-PropertyValue -Object $coordinate -Name 'movementSent')) {
                Add-Failure -Failures $failures -Message "coordinate.movementSent must be false for proof-grade-before-restart packets."
            }

            if (-not [bool](Get-PropertyValue -Object $coordinate -Name 'noCheatEngine')) {
                Add-Failure -Failures $failures -Message "coordinate.noCheatEngine must be true for proof-grade-before-restart packets."
            }

            if ([bool](Get-PropertyValue -Object $coordinate -Name 'savedVariablesUsedAsLiveTruth')) {
                Add-Failure -Failures $failures -Message "coordinate.savedVariablesUsedAsLiveTruth must be false for proof-grade-before-restart packets."
            }
        }
    }

    $resolvedLeadFile = $LeadFile
    if ([string]::IsNullOrWhiteSpace($resolvedLeadFile) -and $null -ne $actorFacing) {
        $resolvedLeadFile = Convert-ToInvariantString -Value (Get-PropertyValue -Object $actorFacing -Name 'leadFile')
    }

    if ([string]::IsNullOrWhiteSpace($resolvedLeadFile)) {
        $resolvedLeadFile = Join-Path $PSScriptRoot 'actor-facing-behavior-backed-lead.json'
    }

    $resolvedLeadFile = [System.IO.Path]::GetFullPath($resolvedLeadFile)
    if (-not (Test-Path -LiteralPath $resolvedLeadFile)) {
        Add-Failure -Failures $failures -Message "Lead file not found: $resolvedLeadFile"
    }
    else {
        try {
            $lead = Get-Content -LiteralPath $resolvedLeadFile -Raw | ConvertFrom-Json -Depth 80
            if ($null -ne $actorFacing) {
                if (-not [string]::Equals([string]$lead.SourceAddress, [string](Get-PropertyValue -Object $actorFacing -Name 'sourceAddress'), [System.StringComparison]::OrdinalIgnoreCase)) {
                    Add-Failure -Failures $failures -Message "actorFacing.sourceAddress does not match lead SourceAddress."
                }

                if (-not [string]::Equals([string]$lead.BasisForwardOffset, [string](Get-PropertyValue -Object $actorFacing -Name 'basisForwardOffset'), [System.StringComparison]::OrdinalIgnoreCase)) {
                    Add-Failure -Failures $failures -Message "actorFacing.basisForwardOffset does not match lead BasisForwardOffset."
                }
            }

            $candidateDiagnostics = Get-PropertyValue -Object $lead -Name 'CandidateDiagnostics'
            if ($null -ne $target -and $null -ne $candidateDiagnostics) {
                $leadProcessId = [int](Get-PropertyValue -Object $candidateDiagnostics -Name 'ProcessId')
                $packetProcessId = [int](Get-PropertyValue -Object $target -Name 'processId')
                if ($leadProcessId -ne $packetProcessId) {
                    Add-Failure -Failures $failures -Message "target.processId does not match lead CandidateDiagnostics.ProcessId."
                }

                if (-not [string]::Equals([string](Get-PropertyValue -Object $candidateDiagnostics -Name 'TargetWindowHandle'), [string](Get-PropertyValue -Object $target -Name 'targetWindowHandle'), [System.StringComparison]::OrdinalIgnoreCase)) {
                    Add-Failure -Failures $failures -Message "target.targetWindowHandle does not match lead CandidateDiagnostics.TargetWindowHandle."
                }
            }
            else {
                $warnings.Add('Lead file does not expose CandidateDiagnostics; skipped target cross-check.') | Out-Null
            }
        }
        catch {
            Add-Failure -Failures $failures -Message "Lead file is not valid JSON: $($_.Exception.Message)"
        }
    }
}

$result = [ordered]@{
    mode = 'current-actor-yaw-restart-check-validation'
    packetFile = $resolvedPacketFile
    status = if ($failures.Count -eq 0) { 'pass' } else { 'fail' }
    failures = @($failures)
    warnings = @($warnings)
}

if ($Json) {
    $result | ConvertTo-Json -Depth 20
}
else {
    if ($failures.Count -eq 0) {
        Write-Host "Current actor-yaw restart packet validation passed: $resolvedPacketFile" -ForegroundColor Green
    }
    else {
        Write-Host "Current actor-yaw restart packet validation failed: $resolvedPacketFile" -ForegroundColor Red
        foreach ($failure in $failures) {
            Write-Host " - $failure" -ForegroundColor Red
        }
    }
}

if ($failures.Count -gt 0) {
    exit 1
}
