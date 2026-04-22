[CmdletBinding()]
param(
    [switch]$Json,
    [string]$ProcessName = 'rift_x64',
    [string]$CandidateScreenFile = (Join-Path $PSScriptRoot 'captures\actor-orientation-candidate-screen.json'),
    [string]$OutputFile = (Join-Path $PSScriptRoot 'captures\actor-yaw-candidate-test.json'),
    [int]$TopCount = 4,
    [string]$StimulusKey = 'Right',
    [string]$ReverseStimulusKey = '',
    [ValidateSet('PostMessage', 'SendInput', 'AutoHotkey', 'Manual')]
    [string]$StimulusMode = 'PostMessage',
    [int]$HoldMilliseconds = 700,
    [int]$WaitMilliseconds = 250,
    [int]$RepeatCount = 1,
    [int]$PostStimulusSampleCount = 1,
    [int]$PostStimulusSampleIntervalMilliseconds = 0,
    [switch]$SampleDuringStimulus,
    [switch]$SkipStimulus,
    [int]$ManualWindowMilliseconds = 0,
    [double]$MinYawResponseDegrees = 1.0,
    [double]$MinReversibleYawResponseDegrees = 2.0,
    [double]$MaxCoordDrift = 0.35
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$readerDll = Join-Path $repoRoot 'reader\RiftReader.Reader\bin\Debug\net10.0-windows\RiftReader.Reader.dll'
$postKeyScript = Join-Path $PSScriptRoot 'post-rift-key.ps1'
$sendKeyScript = Join-Path $PSScriptRoot 'send-rift-key.ps1'
$sendKeyAhkScript = Join-Path $PSScriptRoot 'send-rift-key-ahk.ps1'
$resolvedCandidateScreenFile = [System.IO.Path]::GetFullPath($CandidateScreenFile)
$resolvedOutputFile = [System.IO.Path]::GetFullPath($OutputFile)

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
using System.Text;

public static class RiftWindowProbeNative
{
    [DllImport("user32.dll", SetLastError = true)]
    public static extern IntPtr GetForegroundWindow();

    [DllImport("user32.dll", SetLastError = true)]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);

    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int maxCount);
}
"@

function Invoke-ReaderJson {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    if (Test-Path -LiteralPath $readerDll) {
        $output = & dotnet $readerDll @Arguments 2>&1
    }
    else {
        $output = & dotnet run --project $readerProject -- @Arguments 2>&1
    }

    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "Reader command failed (`$LASTEXITCODE=$exitCode): $($output -join [Environment]::NewLine)"
    }

    return ($output -join [Environment]::NewLine) | ConvertFrom-Json -Depth 80
}

function Parse-HexUInt64 {
    param([Parameter(Mandatory = $true)][string]$Value)

    $normalized = $Value.Trim()
    if ($normalized.StartsWith('0x', [System.StringComparison]::OrdinalIgnoreCase)) {
        $normalized = $normalized.Substring(2)
    }

    return [UInt64]::Parse($normalized, [System.Globalization.NumberStyles]::HexNumber, [System.Globalization.CultureInfo]::InvariantCulture)
}

function Convert-HexToByteArray {
    param([Parameter(Mandatory = $true)][string]$Hex)

    $normalized = ($Hex -replace '\s+', '').Trim()
    $bytes = New-Object byte[] ($normalized.Length / 2)
    for ($index = 0; $index -lt $bytes.Length; $index++) {
        $bytes[$index] = [Convert]::ToByte($normalized.Substring($index * 2, 2), 16)
    }

    return $bytes
}

function Read-SingleAt {
    param(
        [Parameter(Mandatory = $true)][byte[]]$Bytes,
        [Parameter(Mandatory = $true)][int]$Offset
    )

    if (($Offset + 4) -gt $Bytes.Length) {
        return $null
    }

    $value = [BitConverter]::ToSingle($Bytes, $Offset)
    if ([single]::IsNaN($value) -or [single]::IsInfinity($value)) {
        return $null
    }

    return [double]$value
}

function Read-TripletAt {
    param(
        [Parameter(Mandatory = $true)][byte[]]$Bytes,
        [Parameter(Mandatory = $true)][int]$Offset
    )

    return [pscustomobject]@{
        X = Read-SingleAt -Bytes $Bytes -Offset $Offset
        Y = Read-SingleAt -Bytes $Bytes -Offset ($Offset + 4)
        Z = Read-SingleAt -Bytes $Bytes -Offset ($Offset + 8)
    }
}

function Normalize-AngleRadians {
    param([double]$Radians)

    $normalized = $Radians
    while ($normalized -gt [Math]::PI) {
        $normalized -= (2.0 * [Math]::PI)
    }

    while ($normalized -lt -[Math]::PI) {
        $normalized += (2.0 * [Math]::PI)
    }

    return $normalized
}

function Convert-RadiansToDegrees {
    param([double]$Radians)
    return $Radians * 180.0 / [Math]::PI
}

function Get-TargetProcessWindowInfo {
    $targetProcess = Get-Process -Name $ProcessName -ErrorAction SilentlyContinue |
        Where-Object { $_.MainWindowHandle -ne 0 } |
        Select-Object -First 1

    if ($null -eq $targetProcess) {
        return $null
    }

    return [pscustomobject]@{
        ProcessId = $targetProcess.Id
        ProcessName = $targetProcess.ProcessName
        MainWindowHandleHex = ('0x{0:X}' -f $targetProcess.MainWindowHandle)
        MainWindowTitle = $targetProcess.MainWindowTitle
    }
}

function Get-ForegroundWindowInfo {
    param($TargetWindowInfo)

    $hwnd = [RiftWindowProbeNative]::GetForegroundWindow()
    $processId = [uint32]0
    [void][RiftWindowProbeNative]::GetWindowThreadProcessId($hwnd, [ref]$processId)

    $titleBuilder = New-Object System.Text.StringBuilder 512
    [void][RiftWindowProbeNative]::GetWindowText($hwnd, $titleBuilder, $titleBuilder.Capacity)

    $process = $null
    try {
        if ($processId -ne 0) {
            $process = Get-Process -Id $processId -ErrorAction Stop
        }
    }
    catch {
        $process = $null
    }

    $foregroundHandleHex = if ($hwnd -ne [IntPtr]::Zero) { ('0x{0:X}' -f $hwnd.ToInt64()) } else { '0x0' }
    $processName = if ($null -ne $process) { $process.ProcessName } else { $null }
    $mainWindowHandleHex = if ($null -ne $process -and $process.MainWindowHandle -ne 0) { ('0x{0:X}' -f $process.MainWindowHandle) } else { $null }

    return [pscustomobject]@{
        HandleHex = $foregroundHandleHex
        ProcessId = if ($processId -ne 0) { [int]$processId } else { $null }
        ProcessName = $processName
        WindowTitle = $titleBuilder.ToString()
        MainWindowHandleHex = $mainWindowHandleHex
        MatchesTargetProcess = ($null -ne $TargetWindowInfo -and $null -ne $processName -and [string]::Equals($processName, [string]$TargetWindowInfo.ProcessName, [System.StringComparison]::OrdinalIgnoreCase))
        MatchesTargetMainWindow = ($null -ne $TargetWindowInfo -and $foregroundHandleHex -eq [string]$TargetWindowInfo.MainWindowHandleHex)
    }
}

function Get-VectorEstimate {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)]$Vector
    )

    if ($null -eq $Vector.X -or $null -eq $Vector.Y -or $null -eq $Vector.Z) {
        return [pscustomobject]@{
            Name = $Name
            Vector = $Vector
            YawRadians = $null
            YawDegrees = $null
            PitchRadians = $null
            PitchDegrees = $null
            Magnitude = $null
        }
    }

    $x = [double]$Vector.X
    $y = [double]$Vector.Y
    $z = [double]$Vector.Z
    $magnitude = [Math]::Sqrt(($x * $x) + ($y * $y) + ($z * $z))
    if ($magnitude -le [double]::Epsilon) {
        return [pscustomobject]@{
            Name = $Name
            Vector = $Vector
            YawRadians = $null
            YawDegrees = $null
            PitchRadians = $null
            PitchDegrees = $null
            Magnitude = $magnitude
        }
    }

    $yawRadians = [Math]::Atan2($z, $x)
    $pitchRadians = [Math]::Atan2($y, [Math]::Sqrt(($x * $x) + ($z * $z)))

    return [pscustomobject]@{
        Name = $Name
        Vector = $Vector
        YawRadians = $yawRadians
        YawDegrees = Convert-RadiansToDegrees -Radians $yawRadians
        PitchRadians = $pitchRadians
        PitchDegrees = Convert-RadiansToDegrees -Radians $pitchRadians
        Magnitude = $magnitude
    }
}

function Get-CoordDeltaMagnitude {
    param($BeforeCoord, $AfterCoord)

    if ($null -eq $BeforeCoord -or $null -eq $AfterCoord) {
        return $null
    }

    if ($null -eq $BeforeCoord.X -or $null -eq $BeforeCoord.Y -or $null -eq $BeforeCoord.Z) {
        return $null
    }

    if ($null -eq $AfterCoord.X -or $null -eq $AfterCoord.Y -or $null -eq $AfterCoord.Z) {
        return $null
    }

    $dx = [double]$AfterCoord.X - [double]$BeforeCoord.X
    $dy = [double]$AfterCoord.Y - [double]$BeforeCoord.Y
    $dz = [double]$AfterCoord.Z - [double]$BeforeCoord.Z
    return [Math]::Sqrt(($dx * $dx) + ($dy * $dy) + ($dz * $dz))
}

function Get-PlayerCurrent {
    try {
        return Invoke-ReaderJson -Arguments @(
            '--process-name', $ProcessName,
            '--read-player-current',
            '--json')
    }
    catch {
        $snapshot = Invoke-ReaderJson -Arguments @(
            '--readerbridge-snapshot',
            '--json')

        $current = $snapshot.Current
        $player = if ($null -ne $current) { $current.Player } else { $null }
        $coord = if ($null -ne $player) { $player.Coord } else { $null }

        return [pscustomobject]@{
            Mode = 'player-current-fallback-readerbridge-snapshot'
            FallbackReason = $_.Exception.Message
            SnapshotSourceFile = $snapshot.SourceFile
            SnapshotLoadedAtUtc = $snapshot.LoadedAtUtc
            Memory = [pscustomobject]@{
                CoordX = if ($null -ne $coord -and $coord.PSObject.Properties['X']) { [double]$coord.X } else { $null }
                CoordY = if ($null -ne $coord -and $coord.PSObject.Properties['Y']) { [double]$coord.Y } else { $null }
                CoordZ = if ($null -ne $coord -and $coord.PSObject.Properties['Z']) { [double]$coord.Z } else { $null }
            }
        }
    }
}

function Get-PlayerCoordSnapshot {
    param($PlayerCurrent)

    if ($null -eq $PlayerCurrent -or $null -eq $PlayerCurrent.Memory) {
        return $null
    }

    return [pscustomobject]@{
        X = if ($PlayerCurrent.Memory.PSObject.Properties['CoordX']) { [double]$PlayerCurrent.Memory.CoordX } else { $null }
        Y = if ($PlayerCurrent.Memory.PSObject.Properties['CoordY']) { [double]$PlayerCurrent.Memory.CoordY } else { $null }
        Z = if ($PlayerCurrent.Memory.PSObject.Properties['CoordZ']) { [double]$PlayerCurrent.Memory.CoordZ } else { $null }
    }
}

function Get-ComparableMagnitude {
    param($Value)

    if ($null -eq $Value) {
        return 0.0
    }

    return [Math]::Abs([double]$Value)
}

function Get-CandidateSnapshot {
    param(
        [Parameter(Mandatory = $true)][string]$AddressHex,
        [Parameter(Mandatory = $true)][string]$ForwardOffsetHex
    )

    $address = Parse-HexUInt64 -Value $AddressHex
    $forwardOffset = [int](Parse-HexUInt64 -Value $ForwardOffsetHex)

    $memoryRead = Invoke-ReaderJson -Arguments @(
        '--process-name', $ProcessName,
        '--address', ('0x{0:X}' -f $address),
        '--length', '384',
        '--json')

    $bytes = Convert-HexToByteArray -Hex ([string]$memoryRead.BytesHex)
    $forward = Read-TripletAt -Bytes $bytes -Offset $forwardOffset

    $upOffset = $forwardOffset + 0x0C
    $rightOffset = $forwardOffset + 0x18

    return [pscustomobject]@{
        Address = ('0x{0:X}' -f $address)
        ForwardOffset = ('0x{0:X}' -f $forwardOffset)
        Forward = $forward
        Up = Read-TripletAt -Bytes $bytes -Offset $upOffset
        Right = Read-TripletAt -Bytes $bytes -Offset $rightOffset
        Estimate = Get-VectorEstimate -Name ('Basis@0x{0:X}' -f $forwardOffset) -Vector $forward
    }
}

function Try-GetCandidateSnapshot {
    param(
        [Parameter(Mandatory = $true)][string]$AddressHex,
        [Parameter(Mandatory = $true)][string]$ForwardOffsetHex
    )

    try {
        return [pscustomobject]@{
            Success = $true
            Snapshot = Get-CandidateSnapshot -AddressHex $AddressHex -ForwardOffsetHex $ForwardOffsetHex
            Error = $null
        }
    }
    catch {
        return [pscustomobject]@{
            Success = $false
            Snapshot = $null
            Error = $_.Exception.Message
        }
    }
}

function Get-YawDeltaDegrees {
    param($BeforeSnapshotResult, $AfterSnapshotResult)

    if (-not $BeforeSnapshotResult.Success -or -not $AfterSnapshotResult.Success) {
        return $null
    }

    if ($null -eq $BeforeSnapshotResult.Snapshot -or $null -eq $AfterSnapshotResult.Snapshot) {
        return $null
    }

    if ($null -eq $BeforeSnapshotResult.Snapshot.Estimate.YawRadians -or $null -eq $AfterSnapshotResult.Snapshot.Estimate.YawRadians) {
        return $null
    }

    return Convert-RadiansToDegrees -Radians (Normalize-AngleRadians -Radians ([double]$AfterSnapshotResult.Snapshot.Estimate.YawRadians - [double]$BeforeSnapshotResult.Snapshot.Estimate.YawRadians))
}

function Get-PitchDeltaDegrees {
    param($BeforeSnapshotResult, $AfterSnapshotResult)

    if (-not $BeforeSnapshotResult.Success -or -not $AfterSnapshotResult.Success) {
        return $null
    }

    if ($null -eq $BeforeSnapshotResult.Snapshot -or $null -eq $AfterSnapshotResult.Snapshot) {
        return $null
    }

    if ($null -eq $BeforeSnapshotResult.Snapshot.Estimate.PitchRadians -or $null -eq $AfterSnapshotResult.Snapshot.Estimate.PitchRadians) {
        return $null
    }

    return Convert-RadiansToDegrees -Radians (Normalize-AngleRadians -Radians ([double]$AfterSnapshotResult.Snapshot.Estimate.PitchRadians - [double]$BeforeSnapshotResult.Snapshot.Estimate.PitchRadians))
}

function Get-CandidateSnapshotSet {
    param(
        [Parameter(Mandatory = $true)]
        [object[]]$Rows
    )

    $snapshotSet = @{}
    foreach ($row in $Rows) {
        $snapshotSet[[string]$row.SourceAddress] = Try-GetCandidateSnapshot -AddressHex ([string]$row.SourceAddress) -ForwardOffsetHex ([string]$row.BasisForwardOffset)
    }

    return $snapshotSet
}

function Start-StimulusProcess {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Key
    )

    if ($SkipStimulus -or $StimulusMode -eq 'Manual') {
        return $null
    }

    $scriptPath = $null
    $modeArguments = @()
    switch ($StimulusMode) {
        'PostMessage' {
            $scriptPath = $postKeyScript
            $modeArguments = @('-Key', $Key, '-HoldMilliseconds', $HoldMilliseconds.ToString([System.Globalization.CultureInfo]::InvariantCulture))
        }
        'SendInput' {
            $scriptPath = $sendKeyScript
            $modeArguments = @('-Key', $Key, '-HoldMilliseconds', $HoldMilliseconds.ToString([System.Globalization.CultureInfo]::InvariantCulture), '-NoRefocus')
        }
        'AutoHotkey' {
            $scriptPath = $sendKeyAhkScript
            $modeArguments = @('-Key', $Key, '-HoldMilliseconds', $HoldMilliseconds.ToString([System.Globalization.CultureInfo]::InvariantCulture), '-NoRefocus')
        }
        default {
            throw "Unsupported stimulus mode '$StimulusMode'."
        }
    }

    $argumentList = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"{0}"' -f $scriptPath)) + $modeArguments
    return Start-Process -FilePath 'powershell.exe' -ArgumentList $argumentList -PassThru -WindowStyle Hidden
}

function Wait-StimulusProcess {
    param($Process)

    if ($null -eq $Process) {
        return
    }

    try {
        if (-not $Process.HasExited) {
            Wait-Process -Id $Process.Id -ErrorAction Stop
        }
    }
    catch [System.InvalidOperationException] {
        # The process can finish before Wait-Process observes it; treat that as a normal completion path.
    }

    $Process.Refresh()
    if ($Process.ExitCode -ne 0) {
        throw "Stimulus process failed for mode '$StimulusMode' with exit code $($Process.ExitCode)."
    }
}

function Invoke-ValidationPhase {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Key,
        [Parameter(Mandatory = $true)]
        [object[]]$Rows,
        [Parameter(Mandatory = $true)]
        [int]$CycleIndex
    )

    $beforePlayer = Get-PlayerCurrent
    $beforePlayerCoord = Get-PlayerCoordSnapshot -PlayerCurrent $beforePlayer
    $baselineSnapshots = Get-CandidateSnapshotSet -Rows $Rows
    $sampleSeries = New-Object System.Collections.Generic.List[object]
    $targetWindowInfo = Get-TargetProcessWindowInfo
    $foregroundBeforeStimulus = Get-ForegroundWindowInfo -TargetWindowInfo $targetWindowInfo
    $foregroundAfterLaunch = $null

    if ($SkipStimulus -or $StimulusMode -eq 'Manual') {
        if ($ManualWindowMilliseconds -gt 0) {
            Write-Host ("Manual turn window ({0}, cycle {1}): {2} ms" -f $Key, $CycleIndex, $ManualWindowMilliseconds)
            Write-Host 'Turn the player manually now.' -ForegroundColor Yellow
            Start-Sleep -Milliseconds $ManualWindowMilliseconds
        }

        $manualSnapshots = Get-CandidateSnapshotSet -Rows $Rows
        $sampleSeries.Add([pscustomobject]@{
                SampleIndex = 1
                RelativeMilliseconds = $ManualWindowMilliseconds
                SamplePhase = 'manual-window'
                StimulusStillRunning = $null
                TargetWithinHold = $null
                ForegroundWindow = Get-ForegroundWindowInfo -TargetWindowInfo $targetWindowInfo
                Snapshots = $manualSnapshots
            }) | Out-Null
    }
    else {
        $effectiveSampleCount = [Math]::Max($PostStimulusSampleCount, 1)
        $sampleTargets = @(for ($sampleIndex = 1; $sampleIndex -le $effectiveSampleCount; $sampleIndex++) {
                if ($sampleIndex -eq 1) {
                    $WaitMilliseconds
                }
                else {
                    $WaitMilliseconds + (($sampleIndex - 1) * $PostStimulusSampleIntervalMilliseconds)
                }
            })

        if (($StimulusMode -eq 'SendInput') -and (-not $SampleDuringStimulus)) {
            & $sendKeyScript -Key $Key -HoldMilliseconds $HoldMilliseconds -NoRefocus *> $null
            if ($LASTEXITCODE -ne 0) {
                throw "Stimulus key '$Key' failed via mode '$StimulusMode'."
            }

            $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
            for ($sampleIndex = 0; $sampleIndex -lt $sampleTargets.Count; $sampleIndex++) {
                $targetMilliseconds = [int]$sampleTargets[$sampleIndex]
                while ($stopwatch.ElapsedMilliseconds -lt $targetMilliseconds) {
                    Start-Sleep -Milliseconds 15
                }

                $sampleSnapshots = Get-CandidateSnapshotSet -Rows $Rows
                $sampleSeries.Add([pscustomobject]@{
                        SampleIndex = ($sampleIndex + 1)
                        RelativeMilliseconds = $targetMilliseconds
                        SamplePhase = 'post-stimulus'
                        StimulusStillRunning = $false
                        TargetWithinHold = ($targetMilliseconds -le $HoldMilliseconds)
                        ForegroundWindow = Get-ForegroundWindowInfo -TargetWindowInfo $targetWindowInfo
                        Snapshots = $sampleSnapshots
                    }) | Out-Null
            }
        }
        else {
            $stimulusProcess = Start-StimulusProcess -Key $Key
            Start-Sleep -Milliseconds 35
            $foregroundAfterLaunch = Get-ForegroundWindowInfo -TargetWindowInfo $targetWindowInfo
            $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
            for ($sampleIndex = 0; $sampleIndex -lt $sampleTargets.Count; $sampleIndex++) {
                $targetMilliseconds = [int]$sampleTargets[$sampleIndex]
                while ($stopwatch.ElapsedMilliseconds -lt $targetMilliseconds) {
                    Start-Sleep -Milliseconds 15
                }

                $stimulusStillRunning = $false
                if ($null -ne $stimulusProcess) {
                    $stimulusProcess.Refresh()
                    $stimulusStillRunning = -not $stimulusProcess.HasExited
                }

                $sampleSnapshots = Get-CandidateSnapshotSet -Rows $Rows
                $sampleSeries.Add([pscustomobject]@{
                        SampleIndex = ($sampleIndex + 1)
                        RelativeMilliseconds = $targetMilliseconds
                        SamplePhase = if ($stimulusStillRunning -or ($targetMilliseconds -le $HoldMilliseconds)) { 'during-stimulus' } else { 'post-stimulus' }
                        StimulusStillRunning = $stimulusStillRunning
                        TargetWithinHold = ($targetMilliseconds -le $HoldMilliseconds)
                        ForegroundWindow = Get-ForegroundWindowInfo -TargetWindowInfo $targetWindowInfo
                        Snapshots = $sampleSnapshots
                    }) | Out-Null
            }

            Wait-StimulusProcess -Process $stimulusProcess
        }
    }

    $afterPlayer = Get-PlayerCurrent
    $afterPlayerCoord = Get-PlayerCoordSnapshot -PlayerCurrent $afterPlayer
    $foregroundAfterStimulus = Get-ForegroundWindowInfo -TargetWindowInfo $targetWindowInfo

    return [pscustomobject]@{
        Key = $Key
        CycleIndex = $CycleIndex
        BeforePlayer = $beforePlayer
        AfterPlayer = $afterPlayer
        BeforePlayerCoord = $beforePlayerCoord
        AfterPlayerCoord = $afterPlayerCoord
        PlayerCoordDeltaMagnitude = Get-CoordDeltaMagnitude -BeforeCoord $beforePlayerCoord -AfterCoord $afterPlayerCoord
        BaselineSnapshots = $baselineSnapshots
        TargetWindowInfo = $targetWindowInfo
        ForegroundBeforeStimulus = $foregroundBeforeStimulus
        ForegroundAfterLaunch = $foregroundAfterLaunch
        ForegroundAfterStimulus = $foregroundAfterStimulus
        Samples = $sampleSeries.ToArray()
    }
}

if (-not (Test-Path -LiteralPath $resolvedCandidateScreenFile)) {
    throw "Candidate screen file not found: $resolvedCandidateScreenFile"
}

$screen = Get-Content -LiteralPath $resolvedCandidateScreenFile -Raw | ConvertFrom-Json -Depth 40
$candidateRows = @()
if ($screen.PSObject.Properties['Mode'] -and [string]$screen.Mode -eq 'actor-orientation-candidate-screen') {
    $candidateRows = @(
        $screen.Results |
            Select-Object -First $TopCount |
            ForEach-Object {
                [pscustomobject]@{
                    Rank = $_.Rank
                    SourceAddress = [string]$_.SourceAddress
                    BasisForwardOffset = [string]$_.BasisForwardOffset
                    DiscoveryMode = [string]$_.DiscoveryMode
                    ParentAddress = [string]$_.ParentAddress
                    RootAddress = [string]$_.RootAddress
                    SearchScore = $_.SearchScore
                }
            })
}
elseif ($screen.PSObject.Properties['Mode'] -and [string]$screen.Mode -eq 'player-orientation-candidate-search') {
    $rank = 0
    $pointerHopCandidates = @($screen.PointerHopCandidates)
    $localCandidates = @($screen.Candidates)
    $normalizedCandidates = New-Object System.Collections.Generic.List[object]

    foreach ($candidate in $pointerHopCandidates) {
        $rank++
        $normalizedCandidates.Add([pscustomobject]@{
            Rank = $rank
            SourceAddress = [string]$candidate.Address
            BasisForwardOffset = [string]$candidate.BasisPrimaryForwardOffset
            DiscoveryMode = [string]$candidate.DiscoveryMode
            ParentAddress = [string]$candidate.ParentAddress
            RootAddress = [string]$candidate.RootAddress
            SearchScore = $candidate.Score
        }) | Out-Null
    }

    foreach ($candidate in $localCandidates) {
        if ($normalizedCandidates.Count -ge $TopCount) {
            break
        }

        $rank++
        $normalizedCandidates.Add([pscustomobject]@{
            Rank = $rank
            SourceAddress = [string]$candidate.Address
            BasisForwardOffset = [string]$candidate.BasisPrimaryForwardOffset
            DiscoveryMode = [string]$candidate.DiscoveryMode
            ParentAddress = [string]$candidate.ProbeRootAddress
            RootAddress = [string]$candidate.ProbeRootAddress
            SearchScore = $candidate.Score
        }) | Out-Null
    }

    $candidateRows = @($normalizedCandidates.ToArray() | Select-Object -First $TopCount)
}

if ($candidateRows.Count -le 0) {
    throw "Candidate input file did not contain any candidate rows."
}

$useAdvancedValidation = ($RepeatCount -gt 1) -or (-not [string]::IsNullOrWhiteSpace($ReverseStimulusKey)) -or ($PostStimulusSampleCount -gt 1)
$results = New-Object System.Collections.Generic.List[object]
$truthLikeResults = @()
$bestTruthLike = $null
$document = [ordered]@{}
$document.Mode = 'actor-yaw-candidate-test'
$document.GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
$document.CandidateScreenFile = $resolvedCandidateScreenFile
$document.ProcessName = $ProcessName
$document.StimulusKey = $StimulusKey
$document.ReverseStimulusKey = $ReverseStimulusKey
$document.StimulusMode = $StimulusMode
$document.SkipStimulus = ($SkipStimulus -or $StimulusMode -eq 'Manual')
$document.ManualWindowMilliseconds = $ManualWindowMilliseconds
$document.HoldMilliseconds = $HoldMilliseconds
$document.WaitMilliseconds = $WaitMilliseconds
$document.RepeatCount = $RepeatCount
$document.PostStimulusSampleCount = $PostStimulusSampleCount
$document.PostStimulusSampleIntervalMilliseconds = $PostStimulusSampleIntervalMilliseconds
$document.SampleDuringStimulus = $SampleDuringStimulus
$document.MinYawResponseDegrees = $MinYawResponseDegrees
$document.MinReversibleYawResponseDegrees = $MinReversibleYawResponseDegrees
$document.MaxCoordDrift = $MaxCoordDrift

if (-not $useAdvancedValidation) {
    $beforePlayer = Get-PlayerCurrent
    $beforePlayerCoord = Get-PlayerCoordSnapshot -PlayerCurrent $beforePlayer
    $beforeSnapshots = Get-CandidateSnapshotSet -Rows $candidateRows

    if ($SkipStimulus -or $StimulusMode -eq 'Manual') {
        if ($ManualWindowMilliseconds -gt 0) {
            Write-Host ("Manual turn window:         {0} ms" -f $ManualWindowMilliseconds)
            Write-Host 'Turn the player manually now.' -ForegroundColor Yellow
            Start-Sleep -Milliseconds $ManualWindowMilliseconds
        }
    }
    else {
        $stimulusProcess = Start-StimulusProcess -Key $StimulusKey
        Wait-StimulusProcess -Process $stimulusProcess
    }

    Start-Sleep -Milliseconds $WaitMilliseconds

    $afterPlayer = Get-PlayerCurrent
    $afterPlayerCoord = Get-PlayerCoordSnapshot -PlayerCurrent $afterPlayer

    foreach ($row in $candidateRows) {
        $address = [string]$row.SourceAddress
        $beforeSnapshotResult = $beforeSnapshots[$address]
        $afterSnapshotResult = Try-GetCandidateSnapshot -AddressHex $address -ForwardOffsetHex ([string]$row.BasisForwardOffset)
        $beforeSnapshot = $beforeSnapshotResult.Snapshot
        $afterSnapshot = $afterSnapshotResult.Snapshot
        $yawDeltaDegrees = Get-YawDeltaDegrees -BeforeSnapshotResult $beforeSnapshotResult -AfterSnapshotResult $afterSnapshotResult
        $pitchDeltaDegrees = Get-PitchDeltaDegrees -BeforeSnapshotResult $beforeSnapshotResult -AfterSnapshotResult $afterSnapshotResult
        $coordDeltaMagnitude = Get-CoordDeltaMagnitude -BeforeCoord $beforePlayerCoord -AfterCoord $afterPlayerCoord
        $candidateResponsive = ($null -ne $yawDeltaDegrees) -and ([Math]::Abs([double]$yawDeltaDegrees) -ge $MinYawResponseDegrees)
        $playerStayedMostlyStill = ($null -ne $coordDeltaMagnitude) -and ([double]$coordDeltaMagnitude -le $MaxCoordDrift)
        $truthLike = $candidateResponsive -and $playerStayedMostlyStill

        $results.Add([pscustomobject]@{
                Rank = $row.Rank
                SourceAddress = $address
                BasisForwardOffset = [string]$row.BasisForwardOffset
                DiscoveryMode = [string]$row.DiscoveryMode
                ParentAddress = [string]$row.ParentAddress
                RootAddress = [string]$row.RootAddress
                SearchScore = $row.SearchScore
                BeforeReadSucceeded = $beforeSnapshotResult.Success
                BeforeReadError = $beforeSnapshotResult.Error
                AfterReadSucceeded = $afterSnapshotResult.Success
                AfterReadError = $afterSnapshotResult.Error
                Before = $beforeSnapshot
                After = $afterSnapshot
                YawDeltaDegrees = $yawDeltaDegrees
                PitchDeltaDegrees = $pitchDeltaDegrees
                PlayerCoordDeltaMagnitude = $coordDeltaMagnitude
                CandidateResponsive = $candidateResponsive
                PlayerStayedMostlyStill = $playerStayedMostlyStill
                TruthLike = $truthLike
            }) | Out-Null
    }

    $bestTruthLike = $results |
        Sort-Object @{ Expression = { if ($_.TruthLike) { 0 } else { 1 } } }, @{ Expression = { -(Get-ComparableMagnitude -Value $_.YawDeltaDegrees) } } |
        Select-Object -First 1

    $truthLikeResults = @($results.ToArray() | Where-Object { $_.TruthLike })
    $document.PlayerBefore = $beforePlayer
    $document.PlayerAfter = $afterPlayer
    $document.CandidateCount = $results.Count
    $document.TruthLikeCandidateCount = $truthLikeResults.Count
    $document.BestTruthLikeCandidate = $bestTruthLike
    $document.Results = $results.ToArray()
}
else {
    $cycles = New-Object System.Collections.Generic.List[object]

    for ($cycleIndex = 1; $cycleIndex -le [Math]::Max($RepeatCount, 1); $cycleIndex++) {
        $forwardPhase = Invoke-ValidationPhase -Key $StimulusKey -Rows $candidateRows -CycleIndex $cycleIndex
        $reversePhase = $null
        if (-not [string]::IsNullOrWhiteSpace($ReverseStimulusKey)) {
            Start-Sleep -Milliseconds 400
            $reversePhase = Invoke-ValidationPhase -Key $ReverseStimulusKey -Rows $candidateRows -CycleIndex $cycleIndex
        }

        $cycles.Add([pscustomobject]@{
                CycleIndex = $cycleIndex
                ForwardPhase = $forwardPhase
                ReversePhase = $reversePhase
            }) | Out-Null

        if ($cycleIndex -lt $RepeatCount) {
            Start-Sleep -Milliseconds 600
        }
    }

    foreach ($row in $candidateRows) {
        $forwardPeaks = New-Object System.Collections.Generic.List[double]
        $reversePeaks = New-Object System.Collections.Generic.List[double]
        $forwardCoordDrifts = New-Object System.Collections.Generic.List[double]
        $reverseCoordDrifts = New-Object System.Collections.Generic.List[double]
        $cycleSummaries = New-Object System.Collections.Generic.List[object]

        foreach ($cycle in $cycles) {
            $address = [string]$row.SourceAddress
            $baselineResult = $cycle.ForwardPhase.BaselineSnapshots[$address]
            $forwardSamples = New-Object System.Collections.Generic.List[object]
            $forwardPeakYawDeltaDegrees = $null
            $forwardPeakPitchDeltaDegrees = $null

            foreach ($sample in @($cycle.ForwardPhase.Samples)) {
                $snapshotResult = $sample.Snapshots[$address]
                $yawDeltaDegrees = Get-YawDeltaDegrees -BeforeSnapshotResult $baselineResult -AfterSnapshotResult $snapshotResult
                $pitchDeltaDegrees = Get-PitchDeltaDegrees -BeforeSnapshotResult $baselineResult -AfterSnapshotResult $snapshotResult
                if ($null -ne $yawDeltaDegrees -and (($null -eq $forwardPeakYawDeltaDegrees) -or ([Math]::Abs([double]$yawDeltaDegrees) -gt [Math]::Abs([double]$forwardPeakYawDeltaDegrees)))) {
                    $forwardPeakYawDeltaDegrees = $yawDeltaDegrees
                    $forwardPeakPitchDeltaDegrees = $pitchDeltaDegrees
                }

                $forwardSamples.Add([pscustomobject]@{
                        SampleIndex = $sample.SampleIndex
                        RelativeMilliseconds = $sample.RelativeMilliseconds
                        SamplePhase = if ($sample.PSObject.Properties['SamplePhase']) { $sample.SamplePhase } else { $null }
                        StimulusStillRunning = if ($sample.PSObject.Properties['StimulusStillRunning']) { $sample.StimulusStillRunning } else { $null }
                        TargetWithinHold = if ($sample.PSObject.Properties['TargetWithinHold']) { $sample.TargetWithinHold } else { $null }
                        ForegroundWindow = if ($sample.PSObject.Properties['ForegroundWindow']) { $sample.ForegroundWindow } else { $null }
                        ReadSucceeded = $snapshotResult.Success
                        ReadError = $snapshotResult.Error
                        Snapshot = $snapshotResult.Snapshot
                        YawDeltaDegrees = $yawDeltaDegrees
                        PitchDeltaDegrees = $pitchDeltaDegrees
                    }) | Out-Null
            }

            $forwardPlayerDrift = $cycle.ForwardPhase.PlayerCoordDeltaMagnitude
            if ($null -ne $forwardPeakYawDeltaDegrees) {
                $forwardPeaks.Add([double]$forwardPeakYawDeltaDegrees) | Out-Null
            }
            if ($null -ne $forwardPlayerDrift) {
                $forwardCoordDrifts.Add([double]$forwardPlayerDrift) | Out-Null
            }

            $reversePeakYawDeltaDegrees = $null
            $reversePeakPitchDeltaDegrees = $null
            $reverseSamples = New-Object System.Collections.Generic.List[object]
            $reversePlayerDrift = $null

            if ($null -ne $cycle.ReversePhase) {
                $reverseBaselineResult = $cycle.ReversePhase.BaselineSnapshots[$address]
                foreach ($sample in @($cycle.ReversePhase.Samples)) {
                    $snapshotResult = $sample.Snapshots[$address]
                    $yawDeltaDegrees = Get-YawDeltaDegrees -BeforeSnapshotResult $reverseBaselineResult -AfterSnapshotResult $snapshotResult
                    $pitchDeltaDegrees = Get-PitchDeltaDegrees -BeforeSnapshotResult $reverseBaselineResult -AfterSnapshotResult $snapshotResult
                    if ($null -ne $yawDeltaDegrees -and (($null -eq $reversePeakYawDeltaDegrees) -or ([Math]::Abs([double]$yawDeltaDegrees) -gt [Math]::Abs([double]$reversePeakYawDeltaDegrees)))) {
                        $reversePeakYawDeltaDegrees = $yawDeltaDegrees
                        $reversePeakPitchDeltaDegrees = $pitchDeltaDegrees
                    }

                    $reverseSamples.Add([pscustomobject]@{
                            SampleIndex = $sample.SampleIndex
                            RelativeMilliseconds = $sample.RelativeMilliseconds
                            SamplePhase = if ($sample.PSObject.Properties['SamplePhase']) { $sample.SamplePhase } else { $null }
                            StimulusStillRunning = if ($sample.PSObject.Properties['StimulusStillRunning']) { $sample.StimulusStillRunning } else { $null }
                            TargetWithinHold = if ($sample.PSObject.Properties['TargetWithinHold']) { $sample.TargetWithinHold } else { $null }
                            ForegroundWindow = if ($sample.PSObject.Properties['ForegroundWindow']) { $sample.ForegroundWindow } else { $null }
                            ReadSucceeded = $snapshotResult.Success
                            ReadError = $snapshotResult.Error
                            Snapshot = $snapshotResult.Snapshot
                            YawDeltaDegrees = $yawDeltaDegrees
                            PitchDeltaDegrees = $pitchDeltaDegrees
                        }) | Out-Null
                }

                $reversePlayerDrift = $cycle.ReversePhase.PlayerCoordDeltaMagnitude
                if ($null -ne $reversePeakYawDeltaDegrees) {
                    $reversePeaks.Add([double]$reversePeakYawDeltaDegrees) | Out-Null
                }
                if ($null -ne $reversePlayerDrift) {
                    $reverseCoordDrifts.Add([double]$reversePlayerDrift) | Out-Null
                }
            }

            $playerStayedMostlyStill = ($null -ne $forwardPlayerDrift) -and ([double]$forwardPlayerDrift -le $MaxCoordDrift)
            if ($null -ne $cycle.ReversePhase) {
                $playerStayedMostlyStill = $playerStayedMostlyStill -and ($null -ne $reversePlayerDrift) -and ([double]$reversePlayerDrift -le $MaxCoordDrift)
            }

            $reversible = $false
            if (($null -ne $forwardPeakYawDeltaDegrees) -and ($null -ne $reversePeakYawDeltaDegrees)) {
                $reversible =
                    ([Math]::Abs([double]$forwardPeakYawDeltaDegrees) -ge $MinReversibleYawResponseDegrees) -and
                    ([Math]::Abs([double]$reversePeakYawDeltaDegrees) -ge $MinReversibleYawResponseDegrees) -and
                    ([Math]::Sign([double]$forwardPeakYawDeltaDegrees) -ne [Math]::Sign([double]$reversePeakYawDeltaDegrees))
            }

            $cycleSummaries.Add([pscustomobject]@{
                    CycleIndex = $cycle.CycleIndex
                    Forward = [pscustomobject]@{
                        Key = $cycle.ForwardPhase.Key
                        TargetWindowInfo = $cycle.ForwardPhase.TargetWindowInfo
                        ForegroundBeforeStimulus = $cycle.ForwardPhase.ForegroundBeforeStimulus
                        ForegroundAfterLaunch = $cycle.ForwardPhase.ForegroundAfterLaunch
                        ForegroundAfterStimulus = $cycle.ForwardPhase.ForegroundAfterStimulus
                        PlayerCoordDeltaMagnitude = $forwardPlayerDrift
                        PeakYawDeltaDegrees = $forwardPeakYawDeltaDegrees
                        PeakPitchDeltaDegrees = $forwardPeakPitchDeltaDegrees
                        Samples = $forwardSamples.ToArray()
                    }
                    Reverse = if ($null -ne $cycle.ReversePhase) {
                        [pscustomobject]@{
                            Key = $cycle.ReversePhase.Key
                            TargetWindowInfo = $cycle.ReversePhase.TargetWindowInfo
                            ForegroundBeforeStimulus = $cycle.ReversePhase.ForegroundBeforeStimulus
                            ForegroundAfterLaunch = $cycle.ReversePhase.ForegroundAfterLaunch
                            ForegroundAfterStimulus = $cycle.ReversePhase.ForegroundAfterStimulus
                            PlayerCoordDeltaMagnitude = $reversePlayerDrift
                            PeakYawDeltaDegrees = $reversePeakYawDeltaDegrees
                            PeakPitchDeltaDegrees = $reversePeakPitchDeltaDegrees
                            Samples = $reverseSamples.ToArray()
                        }
                    }
                    else {
                        $null
                    }
                    Reversible = $reversible
                    PlayerStayedMostlyStill = $playerStayedMostlyStill
                }) | Out-Null
        }

        $reversibleCycleCount = @($cycleSummaries | Where-Object { $_.Reversible -and $_.PlayerStayedMostlyStill }).Count
        $bestForwardPeak = if ($forwardPeaks.Count -gt 0) {
            $forwardPeaks | Sort-Object { -[Math]::Abs([double]$_) } | Select-Object -First 1
        }
        else {
            $null
        }
        $bestReversePeak = if ($reversePeaks.Count -gt 0) {
            $reversePeaks | Sort-Object { -[Math]::Abs([double]$_) } | Select-Object -First 1
        }
        else {
            $null
        }
        $candidateResponsive = ($null -ne $bestForwardPeak) -and ([Math]::Abs([double]$bestForwardPeak) -ge $MinYawResponseDegrees)
        $allCoordDrifts = @($forwardCoordDrifts.ToArray() + $reverseCoordDrifts.ToArray())
        $playerStayedMostlyStill = @($allCoordDrifts | Where-Object { $_ -gt $MaxCoordDrift }).Count -eq 0
        $truthLike = if (-not [string]::IsNullOrWhiteSpace($ReverseStimulusKey)) {
            $reversibleCycleCount -gt 0 -and $playerStayedMostlyStill
        }
        else {
            $candidateResponsive -and $playerStayedMostlyStill
        }

        $results.Add([pscustomobject]@{
                Rank = $row.Rank
                SourceAddress = [string]$row.SourceAddress
                BasisForwardOffset = [string]$row.BasisForwardOffset
                DiscoveryMode = [string]$row.DiscoveryMode
                ParentAddress = [string]$row.ParentAddress
                RootAddress = [string]$row.RootAddress
                SearchScore = $row.SearchScore
                RepeatCount = $RepeatCount
                ForwardPeakYawDeltas = $forwardPeaks.ToArray()
                ReversePeakYawDeltas = $reversePeaks.ToArray()
                ReversibleCycleCount = $reversibleCycleCount
                CycleSummaries = $cycleSummaries.ToArray()
                YawDeltaDegrees = $bestForwardPeak
                ReverseYawDeltaDegrees = $bestReversePeak
                PlayerCoordDeltaMagnitude = if ($forwardCoordDrifts.Count -gt 0) { ($forwardCoordDrifts | Measure-Object -Maximum).Maximum } else { $null }
                CandidateResponsive = $candidateResponsive
                PlayerStayedMostlyStill = $playerStayedMostlyStill
                TruthLike = $truthLike
            }) | Out-Null
    }

    $bestTruthLike = $results |
        Sort-Object @{ Expression = { if ($_.TruthLike) { 0 } else { 1 } } }, @{ Expression = { -[int]$_.ReversibleCycleCount } }, @{ Expression = { -(Get-ComparableMagnitude -Value $_.YawDeltaDegrees) } } |
        Select-Object -First 1

    $truthLikeResults = @($results.ToArray() | Where-Object { $_.TruthLike })
    $document.CandidateCount = $results.Count
    $document.TruthLikeCandidateCount = $truthLikeResults.Count
    $document.BestTruthLikeCandidate = $bestTruthLike
    $document.Results = $results.ToArray()
    $document.Cycles = $cycles.ToArray()
}

$document.Notes = @(
    $(if ($SkipStimulus -or $StimulusMode -eq 'Manual') { 'Read-only candidate validation using direct memory reads around a manual turn window.' } else { "Read-only candidate validation using direct memory reads plus a controlled $StimulusMode turn key stimulus." }),
    $(if ($useAdvancedValidation) {
            if (($StimulusMode -eq 'SendInput') -and $SampleDuringStimulus) {
                'Advanced mode samples candidate yaw during and after each turn and can score reversible sign-consistent D/A-style responses.'
            }
            else {
                'Advanced mode samples candidate yaw repeatedly after each turn and can score reversible sign-consistent D/A-style responses.'
            }
        }
        else { 'Single-pass mode performs one before/after comparison per candidate.' }),
    'No debugger attach, breakpoint tracing, or debug scanning was used.',
    'A candidate is marked truth-like when its yaw response clears the configured threshold while player coordinate drift stays under the configured limit.')

$outputDirectory = Split-Path -Parent $resolvedOutputFile
if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

$jsonText = $document | ConvertTo-Json -Depth 40
Set-Content -LiteralPath $resolvedOutputFile -Value $jsonText -Encoding UTF8

if ($Json) {
    Write-Output $jsonText
    return
}

Write-Host "Actor yaw candidate test"
Write-Host "Output file:              $resolvedOutputFile"
if ($SkipStimulus -or $StimulusMode -eq 'Manual') {
    Write-Host "Stimulus mode:            manual"
    Write-Host "Manual window (ms):       $ManualWindowMilliseconds"
}
else {
    Write-Host "Stimulus key:             $StimulusKey"
    Write-Host "Stimulus mode:            $StimulusMode"
}
Write-Host "Candidates tested:        $($results.Count)"
Write-Host "Truth-like candidates:    $(@($results | Where-Object { $_.TruthLike }).Count)"
foreach ($result in $results) {
    Write-Host ("  [{0}] {1} @ {2} | yaw {3:N3} deg | coord {4:N6} | responsive={5} | truthLike={6}" -f `
        $result.Rank,
        $result.SourceAddress,
        $result.BasisForwardOffset,
        (if ($null -eq $result.YawDeltaDegrees) { 0.0 } else { [double]$result.YawDeltaDegrees }),
        (if ($null -eq $result.PlayerCoordDeltaMagnitude) { 0.0 } else { [double]$result.PlayerCoordDeltaMagnitude }),
        $result.CandidateResponsive,
        $result.TruthLike)
}
