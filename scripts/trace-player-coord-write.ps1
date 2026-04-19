[CmdletBinding()]
param(
    [switch]$Json,
    [switch]$SkipRefresh,
    [switch]$SkipCleanup,
    [switch]$TrustStimulusMode,
    [string]$ProcessName = 'rift_x64',
    [ValidateSet('Auto', 'SendInput', 'PostMessage', 'AutoHotkey')]
    [string]$StimulusMode = 'Auto',
    [string]$StimulusKey = 'w',
    [int]$MovementHoldMilliseconds = 1000,
    [int]$MovementVerificationDelayMilliseconds = 350,
    [double]$MinMovementCoordDelta = 0.01,
    [int]$TimeoutSeconds = 8,
    [int]$MaxCandidates = 8,
    [string]$ConfirmationFile = (Join-Path $(if ($PSScriptRoot) { $PSScriptRoot } elseif ($PSCommandPath) { Split-Path -Parent $PSCommandPath } else { (Get-Location).Path }) 'captures\ce-smart-player-family.json'),
    [string]$OutputFile = (Join-Path $(if ($PSScriptRoot) { $PSScriptRoot } elseif ($PSCommandPath) { Split-Path -Parent $PSCommandPath } else { (Get-Location).Path }) 'captures\player-coord-write-trace.json'),
    [string]$AttemptOutputFile = (Join-Path $(if ($PSScriptRoot) { $PSScriptRoot } elseif ($PSCommandPath) { Split-Path -Parent $PSCommandPath } else { (Get-Location).Path }) 'captures\player-coord-write-trace.last-attempt.json'),
    [string]$TraceStatusFile = (Join-Path $(if ($PSScriptRoot) { $PSScriptRoot } elseif ($PSCommandPath) { Split-Path -Parent $PSCommandPath } else { (Get-Location).Path }) 'captures\player-coord-write-trace.status.txt')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptRoot = if ($PSScriptRoot) { $PSScriptRoot } elseif ($PSCommandPath) { Split-Path -Parent $PSCommandPath } else { (Get-Location).Path }
$repoRoot = (Resolve-Path (Join-Path $scriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$refreshScript = Join-Path $scriptRoot 'refresh-readerbridge-export.ps1'
$smartCaptureScript = Join-Path $scriptRoot 'smart-capture-player-family.ps1'
$postKeyScript = Join-Path $scriptRoot 'post-rift-key.ps1'
$sendKeyScript = Join-Path $scriptRoot 'send-rift-key.ps1'
$sendKeyAhkScript = Join-Path $scriptRoot 'send-rift-key-ahk.ps1'
$ceExecScript = Join-Path $scriptRoot 'cheatengine-exec.ps1'
$traceLuaFile = Join-Path $scriptRoot 'cheat-engine\RiftReaderWriteTrace.lua'
$resolvedConfirmationFile = [System.IO.Path]::GetFullPath($ConfirmationFile)
$resolvedOutputFile = [System.IO.Path]::GetFullPath($OutputFile)
$resolvedAttemptOutputFile = [System.IO.Path]::GetFullPath($AttemptOutputFile)
$resolvedStatusFile = [System.IO.Path]::GetFullPath($TraceStatusFile)
$writeWorkflowHudStatusScript = Join-Path $scriptRoot 'write-workflow-hud-status.ps1'
$workflowHudStatusFile = Join-Path $repoRoot 'debug\workflow-hud-status.json'
$pwshPath = (Get-Command pwsh -ErrorAction Stop).Source

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

    return ($output -join [Environment]::NewLine) | ConvertFrom-Json
}

function Write-WorkflowHudStatus {
    param(
        [ValidateSet('active', 'waiting', 'blocked', 'idle')]
        [string]$State,

        [Parameter(Mandatory = $true)]
        [string]$Action,

        [int]$StaleAfterSeconds = 20
    )

    if (-not (Test-Path -LiteralPath $writeWorkflowHudStatusScript)) {
        return
    }

    try {
        & $pwshPath `
            -NoLogo `
            -NoProfile `
            -ExecutionPolicy Bypass `
            -File $writeWorkflowHudStatusScript `
            -State $State `
            -Action $Action `
            -StatusFile $workflowHudStatusFile `
            -StaleAfterSeconds $StaleAfterSeconds `
            -Quiet | Out-Null
    }
    catch {
        # HUD publishing is best-effort only and must never break the trace workflow.
    }
}

function Get-TargetProcessStartTimeUtc {
    try {
        $process = Get-Process -Name $ProcessName -ErrorAction Stop | Select-Object -First 1
        return $process.StartTime.ToUniversalTime()
    }
    catch {
        return $null
    }
}

function Test-ConfirmationMatchesCurrentProcess {
    param(
        [Parameter(Mandatory = $true)]
        [pscustomobject]$Confirmation
    )

    $processStartTimeUtc = Get-TargetProcessStartTimeUtc
    if ($null -eq $processStartTimeUtc) {
        return $true
    }

    $generatedAtText = [string](Get-ObjectValue -Object $Confirmation -Name 'GeneratedAtUtc')
    if ([string]::IsNullOrWhiteSpace($generatedAtText)) {
        return $true
    }

    $generatedAtUtc = $null
    try {
        $generatedAtUtc = [DateTimeOffset]::Parse($generatedAtText, [System.Globalization.CultureInfo]::InvariantCulture, [System.Globalization.DateTimeStyles]::RoundtripKind)
    }
    catch {
        return $true
    }

    return ($generatedAtUtc.UtcDateTime -ge $processStartTimeUtc)
}

function Invoke-PlayerCurrentJsonWithRetry {
    param(
        [int]$MaxAttempts = 8,
        [int]$RetryDelayMilliseconds = 250
    )

    $lastError = $null
    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        try {
            return Invoke-ReaderJson -Arguments @('--process-name', $ProcessName, '--read-player-current', '--json')
        }
        catch {
            $lastError = $_
            if ($attempt -lt $MaxAttempts) {
                Start-Sleep -Milliseconds $RetryDelayMilliseconds
                continue
            }
        }
    }

    throw $lastError
}

function Invoke-ReaderBridgeSnapshotJsonWithRetry {
    param(
        [int]$MaxAttempts = 8,
        [int]$RetryDelayMilliseconds = 250
    )

    $lastError = $null
    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        try {
            return Invoke-ReaderJson -Arguments @('--readerbridge-snapshot', '--json')
        }
        catch {
            $lastError = $_
            if ($attempt -lt $MaxAttempts) {
                Start-Sleep -Milliseconds $RetryDelayMilliseconds
                continue
            }
        }
    }

    throw $lastError
}

function Parse-HexAddress {
    param(
        [Parameter(Mandatory = $true)]
        [string]$AddressHex
    )

    $normalized = $AddressHex
    if ($normalized.StartsWith('0x', [System.StringComparison]::OrdinalIgnoreCase)) {
        $normalized = $normalized.Substring(2)
    }

    return [UInt64]::Parse($normalized, [System.Globalization.NumberStyles]::HexNumber, [System.Globalization.CultureInfo]::InvariantCulture)
}

function Get-PlayerCoordSnapshot {
    param(
        [Parameter(Mandatory = $true)]
        [pscustomobject]$PlayerRead
    )

    return [pscustomobject]@{
        AddressHex = [string]$PlayerRead.Memory.AddressHex
        X = [double]$PlayerRead.Memory.CoordX
        Y = [double]$PlayerRead.Memory.CoordY
        Z = [double]$PlayerRead.Memory.CoordZ
    }
}

function Get-PlayerCoordSnapshotFromReaderBridge {
    param(
        [Parameter(Mandatory = $true)]
        [pscustomobject]$Snapshot
    )

    $player = $Snapshot.Current.Player
    return [pscustomobject]@{
        AddressHex = $null
        X = [double]$player.Coord.X
        Y = [double]$player.Coord.Y
        Z = [double]$player.Coord.Z
    }
}

function Get-CoordDeltaSummary {
    param(
        [Parameter(Mandatory = $true)]
        [pscustomobject]$Before,

        [Parameter(Mandatory = $true)]
        [pscustomobject]$After
    )

    $deltaX = [double]$After.X - [double]$Before.X
    $deltaY = [double]$After.Y - [double]$Before.Y
    $deltaZ = [double]$After.Z - [double]$Before.Z

    return [pscustomobject]@{
        DeltaX = $deltaX
        DeltaY = $deltaY
        DeltaZ = $deltaZ
        Magnitude = [Math]::Sqrt(($deltaX * $deltaX) + ($deltaY * $deltaY) + ($deltaZ * $deltaZ))
    }
}

function Get-StimulusModeSequence {
    if ($StimulusMode -ne 'Auto') {
        return @($StimulusMode)
    }

    return @('PostMessage', 'SendInput')
}

function Invoke-StimulusByMode {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Mode
    )

    switch ($Mode) {
        'SendInput' {
            & $sendKeyScript -Key $StimulusKey -HoldMilliseconds $MovementHoldMilliseconds -NoRefocus | Out-Null
            if ($LASTEXITCODE -ne 0) {
                throw "SendInput stimulus failed for key '$StimulusKey'."
            }

            return
        }
        'PostMessage' {
            & $postKeyScript -Key $StimulusKey -HoldMilliseconds $MovementHoldMilliseconds | Out-Null
            if ($LASTEXITCODE -ne 0) {
                throw "PostMessage stimulus failed for key '$StimulusKey'."
            }

            return
        }
        'AutoHotkey' {
            & $sendKeyAhkScript -Key $StimulusKey -HoldMilliseconds $MovementHoldMilliseconds -NoRefocus | Out-Null
            if ($LASTEXITCODE -ne 0) {
                throw "AutoHotkey stimulus failed for key '$StimulusKey'."
            }

            return
        }
        default {
            throw "Unsupported stimulus mode '$Mode'."
        }
    }
}

function Test-StimulusMode {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Mode
    )

    $beforeSnapshot = $null
    $afterSnapshot = $null
    $beforePlayerRead = $null
    $afterPlayerRead = $null

    try {
        & $refreshScript -NoReader | Out-Null
        $beforeSnapshot = Invoke-ReaderBridgeSnapshotJsonWithRetry
        $beforeCoord = Get-PlayerCoordSnapshotFromReaderBridge -Snapshot $beforeSnapshot
        try {
            $beforePlayerRead = Invoke-PlayerCurrentJsonWithRetry
        }
        catch {
            $beforePlayerRead = $null
        }

        Invoke-StimulusByMode -Mode $Mode
        Start-Sleep -Milliseconds $MovementVerificationDelayMilliseconds
        & $refreshScript -NoReader | Out-Null

        $afterSnapshot = Invoke-ReaderBridgeSnapshotJsonWithRetry
        $afterCoord = Get-PlayerCoordSnapshotFromReaderBridge -Snapshot $afterSnapshot
        try {
            $afterPlayerRead = Invoke-PlayerCurrentJsonWithRetry
        }
        catch {
            $afterPlayerRead = $null
        }

        $snapshotDelta = Get-CoordDeltaSummary -Before $beforeCoord -After $afterCoord
        $selectedDelta = $snapshotDelta
        $verificationSource = 'readerbridge-snapshot'
        $motionObserved = ([double]$snapshotDelta.Magnitude -ge $MinMovementCoordDelta)

        if ($beforePlayerRead -and $afterPlayerRead) {
            $beforeDirectCoord = Get-PlayerCoordSnapshot -PlayerRead $beforePlayerRead
            $afterDirectCoord = Get-PlayerCoordSnapshot -PlayerRead $afterPlayerRead
            $directDelta = Get-CoordDeltaSummary -Before $beforeDirectCoord -After $afterDirectCoord
            if (-not $motionObserved -and [double]$directDelta.Magnitude -ge $MinMovementCoordDelta) {
                $selectedDelta = $directDelta
                $verificationSource = 'player-current'
                $motionObserved = $true
            }
        }

        return [pscustomobject]@{
            Mode = $Mode
            Key = $StimulusKey
            BeforeAddress = $beforeCoord.AddressHex
            AfterAddress = $afterCoord.AddressHex
            BeforeCoord = $beforeCoord
            AfterCoord = $afterCoord
            DeltaX = $selectedDelta.DeltaX
            DeltaY = $selectedDelta.DeltaY
            DeltaZ = $selectedDelta.DeltaZ
            DeltaMagnitude = $selectedDelta.Magnitude
            VerificationSource = $verificationSource
            MotionObserved = $motionObserved
            Error = $null
        }
    }
    catch {
        return [pscustomobject]@{
            Mode = $Mode
            Key = $StimulusKey
            BeforeAddress = $null
            AfterAddress = $null
            BeforeCoord = if ($beforeSnapshot) { Get-PlayerCoordSnapshotFromReaderBridge -Snapshot $beforeSnapshot } else { $null }
            AfterCoord = if ($afterSnapshot) { Get-PlayerCoordSnapshotFromReaderBridge -Snapshot $afterSnapshot } else { $null }
            DeltaX = $null
            DeltaY = $null
            DeltaZ = $null
            DeltaMagnitude = $null
            MotionObserved = $false
            Error = $_.Exception.Message
        }
    }
}

function Resolve-UsableStimulus {
    if ($TrustStimulusMode -and $StimulusMode -ne 'Auto') {
        return [pscustomobject]@{
            SelectedAttempt = [pscustomobject]@{
                Mode = $StimulusMode
                DeltaX = $null
                DeltaY = $null
                DeltaZ = $null
                DeltaMagnitude = $null
                MotionObserved = $true
                Error = $null
            }
            Attempts = @(
                [pscustomobject]@{
                    Mode = $StimulusMode
                    DeltaX = $null
                    DeltaY = $null
                    DeltaZ = $null
                    DeltaMagnitude = $null
                    MotionObserved = $true
                    Error = $null
                }
            )
        }
    }

    $attempts = New-Object System.Collections.Generic.List[object]

    foreach ($mode in @(Get-StimulusModeSequence)) {
        $attempt = Test-StimulusMode -Mode $mode
        $attempts.Add($attempt) | Out-Null

        if ($attempt.MotionObserved) {
            return [pscustomobject]@{
                SelectedAttempt = $attempt
                Attempts = @($attempts.ToArray())
            }
        }
    }

    return [pscustomobject]@{
        SelectedAttempt = $null
        Attempts = @($attempts.ToArray())
    }
}

function Convert-ToModulePattern {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ByteText
    )

    $hex = ($ByteText -replace '\s+', '').Trim()
    if ([string]::IsNullOrWhiteSpace($hex) -or ($hex.Length % 2) -ne 0) {
        return $null
    }

    if ($hex -notmatch '^[0-9A-Fa-f]+$') {
        return $null
    }

    $pairs = for ($index = 0; $index -lt $hex.Length; $index += 2) {
        $hex.Substring($index, 2).ToUpperInvariant()
    }

    return ($pairs -join ' ')
}

function Read-KeyValueFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $map = [ordered]@{}
    foreach ($line in [System.IO.File]::ReadAllLines($Path)) {
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }

        $separator = $line.IndexOf('=')
        if ($separator -lt 0) {
            continue
        }

        $key = $line.Substring(0, $separator)
        $value = $line.Substring($separator + 1)
        $map[$key] = $value
    }

    return [pscustomobject]$map
}

function Get-ObjectValue {
    param(
        [Parameter(Mandatory = $true)]
        [psobject]$Object,

        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $null
    }

    return $property.Value
}

function Convert-StatusToTraceAttempt {
    param(
        [Parameter(Mandatory = $true)]
        [pscustomobject]$Status,

        [Parameter(Mandatory = $true)]
        [string]$AddressHex,

        [Parameter(Mandatory = $true)]
        [string]$Source,

        [Parameter(Mandatory = $true)]
        [bool]$Success,

        [string]$StimulusExecutionMode = $null
    )

    return [pscustomobject]@{
        Success = $Success
        Status = [string](Get-ObjectValue -Object $Status -Name 'status')
        CandidateAddress = $AddressHex
        CandidateSource = $Source
        DebugAttachLabel = Get-ObjectValue -Object $Status -Name 'debugAttachLabel'
        BreakpointMethod = Get-ObjectValue -Object $Status -Name 'breakpointMethod'
        VerificationMethod = Get-ObjectValue -Object $Status -Name 'verificationMethod'
        TargetAddress = Get-ObjectValue -Object $Status -Name 'targetAddress'
        HitCount = if (Get-ObjectValue -Object $Status -Name 'hitCount') { [int](Get-ObjectValue -Object $Status -Name 'hitCount') } else { 0 }
        InstructionAddress = Get-ObjectValue -Object $Status -Name 'rip'
        InstructionSymbol = Get-ObjectValue -Object $Status -Name 'instructionSymbol'
        Instruction = Get-ObjectValue -Object $Status -Name 'instruction'
        InstructionBytes = Get-ObjectValue -Object $Status -Name 'instructionBytes'
        InstructionOpcode = Get-ObjectValue -Object $Status -Name 'instructionOpcode'
        InstructionExtra = Get-ObjectValue -Object $Status -Name 'instructionExtra'
        InstructionSize = Get-ObjectValue -Object $Status -Name 'instructionSize'
        WriteOperand = Get-ObjectValue -Object $Status -Name 'writeOperand'
        AccessOperand = Get-ObjectValue -Object $Status -Name 'accessOperand'
        AccessType = Get-ObjectValue -Object $Status -Name 'accessType'
        EffectiveAddress = Get-ObjectValue -Object $Status -Name 'effectiveAddress'
        AccessMatchesTarget = Get-ObjectValue -Object $Status -Name 'accessMatchesTarget'
        MatchedOffset = Get-ObjectValue -Object $Status -Name 'matchedOffset'
        ModuleName = Get-ObjectValue -Object $Status -Name 'moduleName'
        ModuleBase = Get-ObjectValue -Object $Status -Name 'moduleBase'
        ModuleOffset = Get-ObjectValue -Object $Status -Name 'moduleOffset'
        StimulusKey = $StimulusKey
        StimulusExecutionMode = $StimulusExecutionMode
        Error = Get-ObjectValue -Object $Status -Name 'error'
        Registers = [ordered]@{
            RAX = Get-ObjectValue -Object $Status -Name 'rax'
            RBX = Get-ObjectValue -Object $Status -Name 'rbx'
            RCX = Get-ObjectValue -Object $Status -Name 'rcx'
            RDX = Get-ObjectValue -Object $Status -Name 'rdx'
            RSI = Get-ObjectValue -Object $Status -Name 'rsi'
            RDI = Get-ObjectValue -Object $Status -Name 'rdi'
            RBP = Get-ObjectValue -Object $Status -Name 'rbp'
            RSP = Get-ObjectValue -Object $Status -Name 'rsp'
            R8 = Get-ObjectValue -Object $Status -Name 'r8'
            R9 = Get-ObjectValue -Object $Status -Name 'r9'
            R10 = Get-ObjectValue -Object $Status -Name 'r10'
            R11 = Get-ObjectValue -Object $Status -Name 'r11'
            R12 = Get-ObjectValue -Object $Status -Name 'r12'
            R13 = Get-ObjectValue -Object $Status -Name 'r13'
            R14 = Get-ObjectValue -Object $Status -Name 'r14'
            R15 = Get-ObjectValue -Object $Status -Name 'r15'
        }
    }
}

function Get-CoordTraceResult {
    param(
        [Parameter(Mandatory = $true)]
        [string]$AddressHex,

        [Parameter(Mandatory = $true)]
        [string]$Source,

        [Parameter(Mandatory = $true)]
        [string]$StimulusExecutionMode
    )

    $coordAddress = Parse-HexAddress -AddressHex $AddressHex
    $attachPreferences = @('interface-2', 'default', 'interface-1')
    $breakpointMethods = @('debug-register', 'page-exception')
    $lastAttempt = $null

    foreach ($attachPreference in $attachPreferences) {
        foreach ($breakpointMethod in $breakpointMethods) {
            $methodAttempt = $null

            if (Test-Path -LiteralPath $resolvedStatusFile) {
                Remove-Item -LiteralPath $resolvedStatusFile -Force
            }

            & $ceExecScript -LuaFile $traceLuaFile | Out-Null

            $luaCode = @"
return RiftReaderWriteTrace.arm('$ProcessName', $coordAddress, 4, [[$resolvedStatusFile]], '$breakpointMethod', '$attachPreference')
"@
            & $ceExecScript -Code $luaCode | Out-Null

            Invoke-StimulusByMode -Mode $StimulusExecutionMode

            $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
            $lastStatus = $null

            while ([DateTime]::UtcNow -lt $deadline) {
                if (Test-Path -LiteralPath $resolvedStatusFile) {
                    $status = Read-KeyValueFile -Path $resolvedStatusFile
                    $lastStatus = $status

                    if ($status.status -eq 'hit') {
                        return Convert-StatusToTraceAttempt -Status $status -AddressHex $AddressHex -Source $Source -Success $true -StimulusExecutionMode $StimulusExecutionMode
                    }

                    if ($status.status -eq 'error') {
                        $methodAttempt = Convert-StatusToTraceAttempt -Status $status -AddressHex $AddressHex -Source $Source -Success $false -StimulusExecutionMode $StimulusExecutionMode
                        break
                    }
                }

                Start-Sleep -Milliseconds 200
            }

            if ($null -eq $methodAttempt -and $lastStatus) {
                $methodAttempt = Convert-StatusToTraceAttempt -Status $lastStatus -AddressHex $AddressHex -Source $Source -Success $false -StimulusExecutionMode $StimulusExecutionMode
            }
            elseif ($null -eq $methodAttempt) {
                $methodAttempt = [pscustomobject]@{
                    Success = $false
                    Status = 'timeout'
                    CandidateAddress = $AddressHex
                    CandidateSource = $Source
                    DebugAttachLabel = $attachPreference
                    BreakpointMethod = $breakpointMethod
                    VerificationMethod = $null
                    TargetAddress = $AddressHex
                    HitCount = 0
                    InstructionAddress = $null
                    InstructionSymbol = $null
                    Instruction = $null
                    InstructionBytes = $null
                    InstructionOpcode = $null
                    InstructionExtra = $null
                    InstructionSize = $null
                    WriteOperand = $null
                    AccessOperand = $null
                    AccessType = $null
                    EffectiveAddress = $null
                    AccessMatchesTarget = $null
                    MatchedOffset = $null
                    ModuleName = $null
                    ModuleBase = $null
                    ModuleOffset = $null
                    StimulusKey = $StimulusKey
                    StimulusExecutionMode = $StimulusExecutionMode
                    Error = $null
                    Registers = [ordered]@{}
                }
            }

            $lastAttempt = $methodAttempt
            if ($methodAttempt.Status -notin @('armed', 'timeout')) {
                return $methodAttempt
            }
        }
    }

    return $lastAttempt
}

function Get-TraceCandidates {
    param(
        [pscustomobject]$PlayerRead
    )

    $candidates = New-Object System.Collections.Generic.List[object]
    $seen = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
    $playerCurrentCandidate = $null
    $preferPlayerCurrentFirst = $true

    if ($null -ne $PlayerRead -and $null -ne $PlayerRead.Memory) {
        $currentAddressHex = [string]$PlayerRead.Memory.AddressHex
        $selectionSource = [string](Get-ObjectValue -Object $PlayerRead -Name 'SelectionSource')
        if ($selectionSource -eq 'cached-anchor') {
            $preferPlayerCurrentFirst = $false
        }

        if (-not [string]::IsNullOrWhiteSpace($currentAddressHex)) {
            $playerCurrentCandidate = [pscustomobject]@{
                AddressHex = $currentAddressHex
                Source = 'player-current'
                FamilyId = [string]$PlayerRead.FamilyId
            }

            if ($preferPlayerCurrentFirst -and $seen.Add($currentAddressHex)) {
                $candidates.Add($playerCurrentCandidate) | Out-Null
            }
        }
    }

    if (Test-Path -LiteralPath $resolvedConfirmationFile) {
        try {
            $confirmation = Get-Content -Path $resolvedConfirmationFile -Raw | ConvertFrom-Json
            $winnerFamilyId = [string]$confirmation.WinnerFamilyId
            $candidateBuckets = @(
                [pscustomobject]@{
                    Source = 'ce-confirmed'
                    FamilyId = $winnerFamilyId
                    Addresses = @($confirmation.Winner.CeConfirmedSampleAddresses)
                },
                [pscustomobject]@{
                    Source = 'ce-triplet-confirmed'
                    FamilyId = $winnerFamilyId
                    Addresses = @($confirmation.TripletConfirmedAddresses)
                },
                [pscustomobject]@{
                    Source = 'ce-ranked-family'
                    FamilyId = $winnerFamilyId
                    Addresses = @($confirmation.Winner.SampleAddresses)
                }
            )

            foreach ($family in @($confirmation.Families)) {
                $candidateBuckets += [pscustomobject]@{
                    Source = 'ce-family-sample'
                    FamilyId = [string]$family.FamilyId
                    Addresses = @($family.SampleAddresses)
                }
            }

            foreach ($attempt in @($confirmation.Attempts | Where-Object { $_.MotionObserved })) {
                $candidateBuckets += [pscustomobject]@{
                    Source = ('ce-axis-{0}' -f ([string]$attempt.Axis).ToLowerInvariant())
                    FamilyId = $winnerFamilyId
                    Addresses = @($attempt.RetrievedCeAddresses)
                }
            }

            foreach ($bucket in $candidateBuckets) {
                foreach ($address in @($bucket.Addresses)) {
                    $addressHex = [string]$address
                    if ([string]::IsNullOrWhiteSpace($addressHex)) {
                        continue
                    }

                    if ($seen.Add($addressHex)) {
                        $candidates.Add([pscustomobject]@{
                                AddressHex = $addressHex
                                Source = [string]$bucket.Source
                                FamilyId = [string]$bucket.FamilyId
                            }) | Out-Null
                    }
                }
            }
        }
        catch {
            Write-Warning ("Unable to load CE confirmation candidates from '{0}': {1}" -f $resolvedConfirmationFile, $_.Exception.Message)
        }
    }

    if (-not $preferPlayerCurrentFirst -and $null -ne $playerCurrentCandidate -and $seen.Add([string]$playerCurrentCandidate.AddressHex)) {
        $candidates.Add($playerCurrentCandidate) | Out-Null
    }

    return @($candidates | Select-Object -First $MaxCandidates)
}

function Test-HasUsableConfirmation {
    if (-not (Test-Path -LiteralPath $resolvedConfirmationFile)) {
        return $false
    }

    try {
        $confirmation = Get-Content -LiteralPath $resolvedConfirmationFile -Raw | ConvertFrom-Json
        if (-not (Test-ConfirmationMatchesCurrentProcess -Confirmation $confirmation)) {
            Write-Warning ("Ignoring stale CE confirmation file '{0}' because it predates the current {1} process instance." -f $resolvedConfirmationFile, $ProcessName)
            return $false
        }

        if (@($confirmation.Winner.CeConfirmedSampleAddresses).Count -gt 0) {
            return $true
        }

        if (@($confirmation.TripletConfirmedAddresses).Count -gt 0) {
            return $true
        }

        if (@($confirmation.Winner.SampleAddresses).Count -gt 0) {
            return $true
        }

        foreach ($attempt in @($confirmation.Attempts)) {
            if ($attempt.MotionObserved -and @($attempt.RetrievedCeAddresses).Count -gt 0) {
                return $true
            }
        }

        return $false
    }
    catch {
        Write-Warning ("Unable to evaluate CE confirmation file '{0}': {1}" -f $resolvedConfirmationFile, $_.Exception.Message)
        return $false
    }
}

function Ensure-CeConfirmation {
    if (Test-HasUsableConfirmation) {
        return
    }

    try {
        Write-Host "[CoordTrace] No usable CE-confirmed family sample is available; attempting a fresh smart capture first..." -ForegroundColor Yellow
        & $smartCaptureScript -ProcessName $ProcessName -MovementHoldMilliseconds $MovementHoldMilliseconds | Out-Null
    }
    catch {
        Write-Warning ("CE-backed smart capture failed before trace; continuing with current-player candidates only. {0}" -f $_.Exception.Message)
    }
}

function Cleanup-Trace {
    if ($SkipCleanup) {
        return
    }

    try {
        & $ceExecScript -Code "return RiftReaderWriteTrace.cleanup()" | Out-Null
    }
    catch {
        Write-Warning ("Unable to clean up the CE trace helper cleanly: {0}" -f $_.Exception.Message)
    }
}

function Get-TraceResultDocument {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ModeName,

        [Parameter(Mandatory = $true)]
        [string]$Stage,

        [Parameter(Mandatory = $true)]
        [bool]$Succeeded,

        [string]$Error,

        [object]$StimulusResolution,

        [object]$SelectedStimulus,

        [object]$PlayerRead,

        [string]$PlayerReadError,

        [object[]]$TraceCandidates = @(),

        [System.Collections.Generic.List[object]]$Attempts,

        [object]$TraceStatus,

        [object]$ModulePattern,

        [string]$NormalizedPattern,

        [bool]$CanonicalOutputWritten
    )

    $attemptArray = if ($null -ne $Attempts) { @($Attempts.ToArray()) } else { @() }
    $selectedCandidateAddress = if ($null -ne $TraceStatus) { $TraceStatus.CandidateAddress } else { $null }
    $selectedCandidateSource = if ($null -ne $TraceStatus) { $TraceStatus.CandidateSource } else { $null }

    return [ordered]@{
        Mode = $ModeName
        GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
        ProcessName = $ProcessName
        Stage = $Stage
        Succeeded = $Succeeded
        Error = $Error
        TimeoutSeconds = $TimeoutSeconds
        SourceObjectRegisterValue = $(if ($null -ne $TraceStatus -and $null -ne $TraceStatus.Registers) { [string]$TraceStatus.Registers.RDI } else { $null })
        Stimulus = [ordered]@{
            RequestedMode = $StimulusMode
            SelectedMode = $(if ($null -ne $SelectedStimulus) { $SelectedStimulus.Mode } else { $null })
            Key = $StimulusKey
            MovementHoldMilliseconds = $MovementHoldMilliseconds
            MovementVerificationDelayMilliseconds = $MovementVerificationDelayMilliseconds
            MinMovementCoordDelta = $MinMovementCoordDelta
            Attempts = $(if ($null -ne $StimulusResolution) { @($StimulusResolution.Attempts) } else { @() })
        }
        ReaderError = $PlayerReadError
        Reader = $PlayerRead
        Candidates = [ordered]@{
            ConfirmationFile = $resolvedConfirmationFile
            Count = @($TraceCandidates).Count
            Items = @($TraceCandidates)
            Attempts = $attemptArray
            SelectedAddress = $selectedCandidateAddress
            SelectedSource = $selectedCandidateSource
        }
        Trace = [ordered]@{
            Status = $(if ($null -ne $TraceStatus) { $TraceStatus.Status } else { $null })
            DebugAttachLabel = $(if ($null -ne $TraceStatus) { $TraceStatus.DebugAttachLabel } else { $null })
            BreakpointMethod = $(if ($null -ne $TraceStatus) { $TraceStatus.BreakpointMethod } else { $null })
            VerificationMethod = $(if ($null -ne $TraceStatus) { $TraceStatus.VerificationMethod } else { $null })
            CandidateAddress = $selectedCandidateAddress
            CandidateSource = $selectedCandidateSource
            TargetAddress = $(if ($null -ne $TraceStatus) { $TraceStatus.TargetAddress } else { $null })
            HitCount = $(if ($null -ne $TraceStatus) { $TraceStatus.HitCount } else { 0 })
            InstructionAddress = $(if ($null -ne $TraceStatus) { $TraceStatus.InstructionAddress } else { $null })
            InstructionSymbol = $(if ($null -ne $TraceStatus) { $TraceStatus.InstructionSymbol } else { $null })
            Instruction = $(if ($null -ne $TraceStatus) { $TraceStatus.Instruction } else { $null })
            InstructionBytes = $(if ($null -ne $TraceStatus) { $TraceStatus.InstructionBytes } else { $null })
            NormalizedPattern = $NormalizedPattern
            InstructionOpcode = $(if ($null -ne $TraceStatus) { $TraceStatus.InstructionOpcode } else { $null })
            InstructionExtra = $(if ($null -ne $TraceStatus) { $TraceStatus.InstructionExtra } else { $null })
            InstructionSize = $(if ($null -ne $TraceStatus) { $TraceStatus.InstructionSize } else { $null })
            WriteOperand = $(if ($null -ne $TraceStatus) { $TraceStatus.WriteOperand } else { $null })
            AccessOperand = $(if ($null -ne $TraceStatus) { $TraceStatus.AccessOperand } else { $null })
            AccessType = $(if ($null -ne $TraceStatus) { $TraceStatus.AccessType } else { $null })
            EffectiveAddress = $(if ($null -ne $TraceStatus) { $TraceStatus.EffectiveAddress } else { $null })
            AccessMatchesTarget = $(if ($null -ne $TraceStatus) { $TraceStatus.AccessMatchesTarget } else { $null })
            MatchedOffset = $(if ($null -ne $TraceStatus) { $TraceStatus.MatchedOffset } else { $null })
            ModuleName = $(if ($null -ne $TraceStatus) { $TraceStatus.ModuleName } else { $null })
            ModuleBase = $(if ($null -ne $TraceStatus) { $TraceStatus.ModuleBase } else { $null })
            ModuleOffset = $(if ($null -ne $TraceStatus) { $TraceStatus.ModuleOffset } else { $null })
            StimulusKey = $(if ($null -ne $TraceStatus) { $TraceStatus.StimulusKey } else { $StimulusKey })
            StimulusExecutionMode = $(if ($null -ne $TraceStatus) { $TraceStatus.StimulusExecutionMode } else { $(if ($null -ne $SelectedStimulus) { $SelectedStimulus.Mode } else { $null }) })
            Registers = $(if ($null -ne $TraceStatus) { $TraceStatus.Registers } else { [ordered]@{} })
            Error = $(if ($null -ne $TraceStatus -and -not [string]::IsNullOrWhiteSpace([string]$TraceStatus.Error)) { $TraceStatus.Error } else { $Error })
        }
        ModulePattern = $ModulePattern
        CanonicalOutputFile = $resolvedOutputFile
        CanonicalOutputWritten = $CanonicalOutputWritten
        AttemptOutputFile = $resolvedAttemptOutputFile
        TraceStatusFile = $resolvedStatusFile
    }
}

function Write-TraceAttemptArtifact {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Document
    )

    $attemptDirectory = Split-Path -Parent $resolvedAttemptOutputFile
    if (-not [string]::IsNullOrWhiteSpace($attemptDirectory)) {
        New-Item -ItemType Directory -Path $attemptDirectory -Force | Out-Null
    }

    $json = $Document | ConvertTo-Json -Depth 12
    Set-Content -LiteralPath $resolvedAttemptOutputFile -Value $json -Encoding UTF8
}

$currentStage = 'startup'
$stimulusResolution = $null
$selectedStimulus = $null
$playerRead = $null
$playerReadError = $null
$traceCandidates = @()
$attempts = New-Object System.Collections.Generic.List[object]
$traceStatus = $null
$modulePattern = $null
$normalizedPattern = $null
$result = $null
$failureMessage = $null

try {
    if (-not $SkipRefresh) {
        $currentStage = 'readerbridge-refresh'
        Write-WorkflowHudStatus -State 'active' -Action 'coord trace refresh' -StaleAfterSeconds 30
        & $refreshScript -NoReader
    }

    $currentStage = 'stimulus-resolution'
    Write-WorkflowHudStatus -State 'active' -Action 'coord trace stimulus' -StaleAfterSeconds 30
    $stimulusResolution = Resolve-UsableStimulus
    $selectedStimulus = $stimulusResolution.SelectedAttempt
    if ($null -eq $selectedStimulus) {
        $stimulusSummary = @($stimulusResolution.Attempts) | ForEach-Object {
            if (-not [string]::IsNullOrWhiteSpace($_.Error)) {
                return ("{0}:error={1}" -f $_.Mode, $_.Error)
            }

            return ("{0}:delta={1:N6}" -f $_.Mode, [double]$_.DeltaMagnitude)
        }

        Write-WorkflowHudStatus -State 'blocked' -Action 'coord trace stimulus blocked' -StaleAfterSeconds 90
        throw ("No configured stimulus mode produced player coord motion for key '{0}'. {1}" -f $StimulusKey, ($stimulusSummary -join '; '))
    }

    $currentStage = 'ce-confirmation'
    Write-WorkflowHudStatus -State 'waiting' -Action 'coord trace candidates' -StaleAfterSeconds 30
    Ensure-CeConfirmation

    $currentStage = 'player-read'
    Write-WorkflowHudStatus -State 'active' -Action 'coord trace baseline' -StaleAfterSeconds 30
    try {
        $playerRead = Invoke-ReaderJson -Arguments @('--process-name', $ProcessName, '--read-player-current', '--json')
    }
    catch {
        $playerReadError = $_.Exception.Message
        Write-Warning ("Unable to refresh the current-player snapshot before trace; continuing with CE-derived candidates only. {0}" -f $playerReadError)
    }

    $currentStage = 'candidate-enumeration'
    Write-WorkflowHudStatus -State 'active' -Action 'coord trace select' -StaleAfterSeconds 30
    $traceCandidates = @(Get-TraceCandidates -PlayerRead $playerRead)
    if ($traceCandidates.Count -le 0) {
        Write-WorkflowHudStatus -State 'blocked' -Action 'coord trace no candidate' -StaleAfterSeconds 90
        if (-not [string]::IsNullOrWhiteSpace($playerReadError)) {
            throw "No coord trace candidates were available after the current-player snapshot failed. $playerReadError"
        }

        throw "No coord trace candidates were available."
    }

    foreach ($candidate in $traceCandidates) {
        $currentStage = ('trace-candidate:{0}' -f [string]$candidate.Source)
        Write-WorkflowHudStatus -State 'active' -Action ('coord trace {0}' -f ([string]$candidate.Source).ToLowerInvariant()) -StaleAfterSeconds 30
        Write-Host ("[CoordTrace] Attempting candidate {0} ({1})..." -f $candidate.AddressHex, $candidate.Source) -ForegroundColor Cyan
        $attempt = $null
        try {
            $attempt = Get-CoordTraceResult -AddressHex $candidate.AddressHex -Source $candidate.Source -StimulusExecutionMode $selectedStimulus.Mode
            $attempts.Add($attempt) | Out-Null
        }
        finally {
            Cleanup-Trace
        }

        if ($attempt.Success) {
            $traceStatus = $attempt
            break
        }
    }

    if ($null -eq $traceStatus) {
        $attemptSummary = $attempts | ForEach-Object {
            $instruction = Get-ObjectValue -Object $_ -Name 'Instruction'
            $accessOperand = Get-ObjectValue -Object $_ -Name 'AccessOperand'
            $accessType = Get-ObjectValue -Object $_ -Name 'AccessType'
            $effectiveAddress = Get-ObjectValue -Object $_ -Name 'EffectiveAddress'
            $matchedOffset = Get-ObjectValue -Object $_ -Name 'MatchedOffset'
            $breakpointMethod = Get-ObjectValue -Object $_ -Name 'BreakpointMethod'
            $debugAttachLabel = Get-ObjectValue -Object $_ -Name 'DebugAttachLabel'

            $summary = "{0}:{1}" -f $_.CandidateAddress, $_.Status
            if ($debugAttachLabel) {
                $summary += " [attach=$debugAttachLabel]"
            }
            if ($breakpointMethod) {
                $summary += " [bp=$breakpointMethod]"
            }
            if ($instruction) {
                $summary += " -> $instruction"
            }

            if ($accessOperand) {
                $summary += " [operand=$accessOperand"
                if ($accessType) {
                    $summary += ", type=$accessType"
                }
                $summary += "]"
            }

            if ($effectiveAddress) {
                $summary += " [ea=$effectiveAddress]"
            }

            if ($null -ne $matchedOffset -and $matchedOffset -ne '') {
                $summary += " [offset=$matchedOffset]"
            }

            $summary
        }

        Write-WorkflowHudStatus -State 'blocked' -Action 'coord trace unverified' -StaleAfterSeconds 90
        throw ("Timed out waiting for a verified coord write trace hit across {0} candidates. {1}" -f $traceCandidates.Count, ($attemptSummary -join '; '))
    }

    $currentStage = 'module-pattern'
    Write-WorkflowHudStatus -State 'waiting' -Action 'coord trace pattern' -StaleAfterSeconds 30
    if (-not [string]::IsNullOrWhiteSpace($traceStatus.ModuleName) -and -not [string]::IsNullOrWhiteSpace($traceStatus.InstructionBytes)) {
        $normalizedPattern = Convert-ToModulePattern -ByteText $traceStatus.InstructionBytes
        try {
            if ([string]::IsNullOrWhiteSpace($normalizedPattern)) {
                throw "Unable to normalize instruction bytes '$($traceStatus.InstructionBytes)' into an AOB pattern."
            }

            $modulePattern = Invoke-ReaderJson -Arguments @(
                '--process-name', $ProcessName,
                '--scan-module-pattern', $normalizedPattern,
                '--scan-module-name', $traceStatus.ModuleName,
                '--scan-context', '16',
                '--json')
        }
        catch {
            $modulePattern = [pscustomobject]@{
                Mode = 'module-pattern-scan'
                Error = $_.Exception.Message
            }
        }
    }

    $result = [ordered]@{
        Mode = 'player-coord-write-trace'
        GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
        ProcessName = $ProcessName
        SourceObjectRegisterValue = $(if ($null -ne $traceStatus.Registers) { [string]$traceStatus.Registers.RDI } else { $null })
        Stimulus = [ordered]@{
            RequestedMode = $StimulusMode
            SelectedMode = $selectedStimulus.Mode
            Key = $StimulusKey
            MovementHoldMilliseconds = $MovementHoldMilliseconds
            MovementVerificationDelayMilliseconds = $MovementVerificationDelayMilliseconds
            MinMovementCoordDelta = $MinMovementCoordDelta
            Attempts = @($stimulusResolution.Attempts)
        }
        ReaderError = $playerReadError
        Reader = $playerRead
        Candidates = [ordered]@{
            ConfirmationFile = $resolvedConfirmationFile
            Count = $traceCandidates.Count
            Attempts = @($attempts.ToArray())
            SelectedAddress = $traceStatus.CandidateAddress
            SelectedSource = $traceStatus.CandidateSource
        }
        Trace = [ordered]@{
            Status = $traceStatus.Status
            DebugAttachLabel = $traceStatus.DebugAttachLabel
            BreakpointMethod = $traceStatus.BreakpointMethod
            VerificationMethod = $traceStatus.VerificationMethod
            CandidateAddress = $traceStatus.CandidateAddress
            CandidateSource = $traceStatus.CandidateSource
            TargetAddress = $traceStatus.TargetAddress
            HitCount = $traceStatus.HitCount
            InstructionAddress = $traceStatus.InstructionAddress
            InstructionSymbol = $traceStatus.InstructionSymbol
            Instruction = $traceStatus.Instruction
            InstructionBytes = $traceStatus.InstructionBytes
            NormalizedPattern = $normalizedPattern
            InstructionOpcode = $traceStatus.InstructionOpcode
            InstructionExtra = $traceStatus.InstructionExtra
            InstructionSize = $traceStatus.InstructionSize
            WriteOperand = $traceStatus.WriteOperand
            AccessOperand = $traceStatus.AccessOperand
            AccessType = $traceStatus.AccessType
            EffectiveAddress = $traceStatus.EffectiveAddress
            AccessMatchesTarget = $traceStatus.AccessMatchesTarget
            MatchedOffset = $traceStatus.MatchedOffset
            ModuleName = $traceStatus.ModuleName
            ModuleBase = $traceStatus.ModuleBase
            ModuleOffset = $traceStatus.ModuleOffset
            StimulusKey = $traceStatus.StimulusKey
            StimulusExecutionMode = $traceStatus.StimulusExecutionMode
            Registers = $traceStatus.Registers
        }
        ModulePattern = $modulePattern
        OutputFile = $resolvedOutputFile
        AttemptOutputFile = $resolvedAttemptOutputFile
        TraceStatusFile = $resolvedStatusFile
    }

    $outputDirectory = Split-Path -Parent $resolvedOutputFile
    if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
        New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
    }

    $currentStage = 'write-output'
    Write-WorkflowHudStatus -State 'active' -Action 'coord trace save' -StaleAfterSeconds 30
    $jsonText = $result | ConvertTo-Json -Depth 10
    Set-Content -Path $resolvedOutputFile -Value $jsonText -Encoding UTF8

    $currentStage = 'completed'
    Write-WorkflowHudStatus -State 'active' -Action 'coord trace ready' -StaleAfterSeconds 30
    if ($Json) {
        Write-Output $jsonText
    }
    else {
        Write-Host "Trace file:           $resolvedOutputFile"
        Write-Host "Player sample:        $($playerRead.Memory.AddressHex)"
        Write-Host "Stimulus key:         $StimulusKey"
        Write-Host "Stimulus mode:        $($selectedStimulus.Mode)"
        Write-Host "Trace candidate:      $($traceStatus.CandidateAddress) [$($traceStatus.CandidateSource)]"
        Write-Host "Coord write target:   $($traceStatus.TargetAddress)"
        if ($traceStatus.DebugAttachLabel) {
            Write-Host "Debug attach:         $($traceStatus.DebugAttachLabel)"
        }
        if ($traceStatus.BreakpointMethod) {
            Write-Host "Breakpoint method:    $($traceStatus.BreakpointMethod)"
        }
        if ($traceStatus.VerificationMethod) {
            Write-Host "Verification:         $($traceStatus.VerificationMethod)"
        }
        Write-Host "Writer RIP:           $($traceStatus.InstructionAddress)"
        Write-Host "Writer symbol:        $($traceStatus.InstructionSymbol)"
        Write-Host "Instruction:          $($traceStatus.Instruction)"
        if ($traceStatus.WriteOperand) {
            Write-Host "Write operand:        $($traceStatus.WriteOperand)"
        }
        if ($traceStatus.AccessOperand) {
            Write-Host "Access operand:       $($traceStatus.AccessOperand)"
        }
        if ($traceStatus.AccessType) {
            Write-Host "Access type:          $($traceStatus.AccessType)"
        }
        if ($traceStatus.EffectiveAddress) {
            Write-Host "Effective address:    $($traceStatus.EffectiveAddress)"
        }
        if ($null -ne $traceStatus.MatchedOffset -and $traceStatus.MatchedOffset -ne '') {
            Write-Host "Matched offset:       $($traceStatus.MatchedOffset)"
        }
        Write-Host "Module pattern bytes: $($traceStatus.InstructionBytes)"
        if ($modulePattern -and $modulePattern.Found -eq $true) {
            Write-Host "Pattern match:        $($modulePattern.Address) in $($modulePattern.ModuleName)"
        }
    }
}
catch {
    $failureMessage = $_.Exception.Message
    if ([string]::IsNullOrWhiteSpace($currentStage)) {
        $currentStage = 'failed'
    }

    Write-WorkflowHudStatus -State 'blocked' -Action 'coord trace failed' -StaleAfterSeconds 90
    throw
}
finally {
    try {
        $attemptDocument = Get-TraceResultDocument `
            -ModeName 'player-coord-write-trace-attempt' `
            -Stage $currentStage `
            -Succeeded ($null -ne $result) `
            -Error $failureMessage `
            -StimulusResolution $stimulusResolution `
            -SelectedStimulus $selectedStimulus `
            -PlayerRead $playerRead `
            -PlayerReadError $playerReadError `
            -TraceCandidates $traceCandidates `
            -Attempts $attempts `
            -TraceStatus $traceStatus `
            -ModulePattern $modulePattern `
            -NormalizedPattern $normalizedPattern `
            -CanonicalOutputWritten ($null -ne $result)
        Write-TraceAttemptArtifact -Document $attemptDocument
    }
    catch {
        Write-Warning ("Unable to persist coord-trace attempt artifact '{0}': {1}" -f $resolvedAttemptOutputFile, $_.Exception.Message)
    }

    Cleanup-Trace
}

