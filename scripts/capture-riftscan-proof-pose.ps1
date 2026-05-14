[CmdletBinding()]
param(
    [string]$ProcessName = 'rift_x64',
    [int]$ProcessId,
    [string]$TargetWindowHandle,
    [string]$CandidateFile,
    [string]$CurrentProofPointerFile = (Join-Path (Resolve-Path (Join-Path $PSScriptRoot '..')).Path 'docs\recovery\current-proof-anchor-readback.json'),
    [string]$ReferenceFile,
    [string]$OutputRoot = (Join-Path $PSScriptRoot 'captures'),
    [string]$PoseLabel = 'pose',
    [double]$ReferenceTolerance = 0.25,
    [int]$ReferenceMaxAgeSeconds = 120,
    [int]$ReferenceScanContextBytes = 4096,
    [int]$ReferenceMaxHits = 512,
    [int]$ReferenceScanAttempts = 5,
    [int]$ReferenceScanRetryDelayMilliseconds = 1500,
    [int]$ReadbackSampleCount = 4,
    [int]$ReadbackIntervalMilliseconds = 100,
    [int]$TopReferenceMatches = 5,
    [string]$ReferenceScript = (Join-Path $PSScriptRoot 'capture-rift-api-reference-coordinate.ps1'),
    [string]$ReadbackScript = (Join-Path $PSScriptRoot 'invoke-riftscan-coordinate-readback.ps1'),
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

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

function ConvertTo-JsonSafeValue {
    param($Value)

    if ($null -eq $Value) {
        return $null
    }

    if ($Value -is [DateTimeOffset]) {
        return ([DateTimeOffset]$Value).ToUniversalTime().UtcDateTime.ToString("yyyy-MM-dd'T'HH:mm:ss.fffffff'Z'", [System.Globalization.CultureInfo]::InvariantCulture)
    }

    if ($Value -is [DateTime]) {
        return ([DateTime]$Value).ToUniversalTime().ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    }

    if ($Value -is [string] -or $Value.GetType().IsPrimitive -or $Value -is [decimal]) {
        return $Value
    }

    if ($Value -is [System.Collections.IDictionary]) {
        $copy = [ordered]@{}
        foreach ($key in $Value.Keys) {
            $copy[[string]$key] = ConvertTo-JsonSafeValue -Value $Value[$key]
        }

        return [pscustomobject]$copy
    }

    if ($Value -is [System.Collections.IEnumerable]) {
        return @($Value | ForEach-Object { ConvertTo-JsonSafeValue -Value $_ })
    }

    $properties = @($Value.PSObject.Properties)
    if ($properties.Count -gt 0) {
        $copy = [ordered]@{}
        foreach ($property in $properties) {
            $copy[$property.Name] = ConvertTo-JsonSafeValue -Value $property.Value
        }

        return [pscustomobject]$copy
    }

    return $Value
}

function Get-PowerShellExecutable {
    if (Get-Command -Name pwsh -CommandType Application -ErrorAction SilentlyContinue) {
        return 'pwsh'
    }

    return 'powershell'
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

        $previousErrorActionPreference = $ErrorActionPreference
        try {
            # Windows PowerShell can promote redirected native stderr from a
            # child pwsh/powershell process into a terminating NativeCommandError
            # when the caller has ErrorActionPreference=Stop. This wrapper needs
            # to capture failing helper output so it can return a structured
            # blocker instead of aborting before summary generation.
            $ErrorActionPreference = 'Continue'
            $output = & $FilePath @Arguments 2>&1
            $exitCode = $LASTEXITCODE
        }
        finally {
            $ErrorActionPreference = $previousErrorActionPreference
        }
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

    Invoke-ExternalCommand -FilePath (Get-PowerShellExecutable) -Arguments (@(
            '-NoLogo',
            '-NoProfile',
            '-ExecutionPolicy',
            'Bypass',
            '-File',
            $ScriptPath
        ) + $Arguments) -WorkingDirectory $repoRoot -AllowFailure:$AllowFailure
}

function ConvertTo-WindowHandleInt64 {
    param([string]$HandleText)

    if ([string]::IsNullOrWhiteSpace($HandleText)) {
        return $null
    }

    if ($HandleText.StartsWith('0x', [System.StringComparison]::OrdinalIgnoreCase)) {
        return [Int64]([UInt64]::Parse($HandleText.Substring(2), [System.Globalization.NumberStyles]::AllowHexSpecifier, [System.Globalization.CultureInfo]::InvariantCulture))
    }

    return [Int64]::Parse($HandleText, [System.Globalization.CultureInfo]::InvariantCulture)
}

function Format-WindowHandleText {
    param($HandleText)

    $value = ConvertTo-WindowHandleInt64 -HandleText ([string]$HandleText)
    if ($null -eq $value) {
        return ''
    }

    return ('0x{0:X}' -f $value)
}

function Normalize-ProcessName {
    param([string]$Name)

    if ([string]::IsNullOrWhiteSpace($Name)) {
        return ''
    }

    $trimmed = $Name.Trim()
    if ($trimmed.EndsWith('.exe', [System.StringComparison]::OrdinalIgnoreCase)) {
        return $trimmed.Substring(0, $trimmed.Length - 4)
    }

    return $trimmed
}

function Assert-PointerTargetMatchesRequest {
    param(
        $Pointer,
        [Parameter(Mandatory = $true)]
        [string]$PointerPath
    )

    $target = Get-JsonPropertyValue -InputObject $Pointer -Names @('target')
    if ($null -eq $target) {
        throw "Current proof pointer '$PointerPath' is missing target metadata."
    }

    if ($ProcessId -gt 0) {
        $pointerProcessId = Get-JsonPropertyValue -InputObject $target -Names @('processId', 'ProcessId', 'pid')
        if ($null -eq $pointerProcessId -or [int]$pointerProcessId -ne $ProcessId) {
            throw "Current proof pointer '$PointerPath' target PID '$pointerProcessId' does not match requested PID $ProcessId."
        }
    }

    if (-not [string]::IsNullOrWhiteSpace($ProcessName)) {
        $pointerProcessName = [string](Get-JsonPropertyValue -InputObject $target -Names @('processName', 'ProcessName'))
        if ([string]::IsNullOrWhiteSpace($pointerProcessName)) {
            throw "Current proof pointer '$PointerPath' is missing target processName."
        }

        $expectedProcessName = Normalize-ProcessName -Name $ProcessName
        $actualProcessName = Normalize-ProcessName -Name $pointerProcessName
        if (-not [string]::Equals($actualProcessName, $expectedProcessName, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Current proof pointer '$PointerPath' target process '$pointerProcessName' does not match requested process '$ProcessName'."
        }
    }

    if (-not [string]::IsNullOrWhiteSpace($TargetWindowHandle)) {
        $pointerWindowHandle = [string](Get-JsonPropertyValue -InputObject $target -Names @('targetWindowHandle', 'TargetWindowHandle', 'hwnd'))
        if ([string]::IsNullOrWhiteSpace($pointerWindowHandle)) {
            throw "Current proof pointer '$PointerPath' is missing targetWindowHandle."
        }

        $expectedWindowHandle = Format-WindowHandleText -HandleText $TargetWindowHandle
        $actualWindowHandle = Format-WindowHandleText -HandleText $pointerWindowHandle
        if (-not [string]::Equals($actualWindowHandle, $expectedWindowHandle, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Current proof pointer '$PointerPath' target HWND '$pointerWindowHandle' does not match requested HWND '$TargetWindowHandle'."
        }
    }
}

function Resolve-CandidateFile {
    if (-not [string]::IsNullOrWhiteSpace($CandidateFile)) {
        $resolved = [System.IO.Path]::GetFullPath($CandidateFile)
        if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
            throw "Candidate file was not found: $resolved"
        }

        return [pscustomobject][ordered]@{
            CandidateFile = $resolved
            ResolvedFromPointer = $false
            CurrentProofPointerFile = $null
            CandidateSource = $null
        }
    }

    $pointerPath = [System.IO.Path]::GetFullPath($CurrentProofPointerFile)
    if (-not (Test-Path -LiteralPath $pointerPath -PathType Leaf)) {
        throw "CandidateFile was not supplied and current proof pointer was not found: $pointerPath"
    }

    $pointer = ConvertFrom-JsonCompat -Text (Get-Content -LiteralPath $pointerPath -Raw) -Depth 80
    Assert-PointerTargetMatchesRequest -Pointer $pointer -PointerPath $pointerPath
    $source = Get-JsonPropertyValue -InputObject $pointer -Names @('riftscanCandidateSource')
    if ($null -eq $source) {
        throw "CandidateFile was not supplied and '$pointerPath' does not contain riftscanCandidateSource."
    }

    $matchFile = [string](Get-JsonPropertyValue -InputObject $source -Names @('matchFile'))
    if ([string]::IsNullOrWhiteSpace($matchFile)) {
        throw "CandidateFile was not supplied and '$pointerPath' does not contain riftscanCandidateSource.matchFile."
    }

    $candidateId = [string](Get-JsonPropertyValue -InputObject $source -Names @('candidateId'))
    if ([string]::IsNullOrWhiteSpace($candidateId)) {
        throw "CandidateFile was not supplied and '$pointerPath' does not contain riftscanCandidateSource.candidateId."
    }

    $resolvedMatchFile = [System.IO.Path]::GetFullPath($matchFile)
    if (-not (Test-Path -LiteralPath $resolvedMatchFile -PathType Leaf)) {
        throw "Candidate file from '$pointerPath' was not found: $resolvedMatchFile"
    }

    return [pscustomobject][ordered]@{
        CandidateFile = $resolvedMatchFile
        ResolvedFromPointer = $true
        CurrentProofPointerFile = $pointerPath
        CandidateSource = ConvertTo-JsonSafeValue -Value $source
    }
}

function Test-TargetDriftMessage {
    param([string]$Message)

    $text = [string]$Message
    return ($text -like "Current proof pointer * target PID * does not match requested PID *" -or
        $text -like "Current proof pointer * target HWND * does not match requested HWND *" -or
        $text -like "Current proof pointer * target process * does not match requested process *" -or
        $text -like "Current proof pointer * is missing target metadata*" -or
        $text -like "Current proof pointer * is missing target processName*" -or
        $text -like "Current proof pointer * is missing targetWindowHandle*")
}

function Get-PreservedHistoricalPointerEvidence {
    param([string]$PointerPath)

    $evidence = [ordered]@{
        classification = 'historical-target-epoch-evidence'
        reusePolicy = 'do-not-use-as-current-proof; preserve for audit/reacquire hints only; candidate addresses and readbacks must be rescored against the current PID/HWND'
        pointerFile = $PointerPath
    }

    if (-not (Test-Path -LiteralPath $PointerPath -PathType Leaf)) {
        $evidence['readStatus'] = 'missing'
        return [pscustomobject]$evidence
    }

    try {
        $pointer = ConvertFrom-JsonCompat -Text (Get-Content -LiteralPath $PointerPath -Raw) -Depth 80
    }
    catch {
        $evidence['readStatus'] = 'unreadable'
        $evidence['readError'] = $_.Exception.Message
        return [pscustomobject]$evidence
    }

    $evidence['readStatus'] = 'read'
    foreach ($name in @('lastUpdatedUtc', 'status', 'target', 'riftscanCandidateSource', 'latestValidation', 'latestProofOnly', 'latestBaselineCapture', 'latestForward250', 'latestForwardSeries3x250')) {
        $value = Get-JsonPropertyValue -InputObject $pointer -Names @($name)
        if ($null -ne $value) {
            $evidence[$name] = ConvertTo-JsonSafeValue -Value $value
        }
    }

    $source = Get-JsonPropertyValue -InputObject $pointer -Names @('riftscanCandidateSource')
    if ($null -ne $source) {
        $hints = [ordered]@{}
        foreach ($name in @('candidateId', 'matchFile', 'truthSummaryFile', 'inventoryFile', 'sessionPath', 'sourceAbsoluteAddressHex', 'sourceBaseAddressHex', 'sourceOffsetHex')) {
            $value = Get-JsonPropertyValue -InputObject $source -Names @($name)
            if ($null -ne $value -and -not [string]::IsNullOrWhiteSpace([string]$value)) {
                $hints[$name] = [string]$value
            }
        }

        if ($hints.Count -gt 0) {
            $evidence['reacquireHints'] = [pscustomobject]$hints
        }
    }

    return [pscustomobject]$evidence
}

function ConvertTo-SafePathSegment {
    param([string]$Value)

    $safe = if ([string]::IsNullOrWhiteSpace($Value)) { 'pose' } else { $Value.Trim() }
    $safe = $safe -replace '[^A-Za-z0-9_.-]+', '-'
    $safe = $safe.Trim('-')
    if ([string]::IsNullOrWhiteSpace($safe)) {
        return 'pose'
    }

    return $safe
}

if ($ReferenceTolerance -lt 0) {
    throw "ReferenceTolerance must be zero or greater."
}

if ($ReferenceMaxAgeSeconds -lt 0 -or $ReadbackSampleCount -le 0 -or $ReadbackIntervalMilliseconds -lt 0 -or $TopReferenceMatches -le 0) {
    throw "ReferenceMaxAgeSeconds must be zero or greater; ReadbackSampleCount and TopReferenceMatches must be greater than zero; ReadbackIntervalMilliseconds must be zero or greater."
}

if ($ReferenceScanContextBytes -le 0 -or $ReferenceMaxHits -le 0 -or $ReferenceScanAttempts -le 0 -or $ReferenceScanRetryDelayMilliseconds -lt 0) {
    throw "ReferenceScanContextBytes, ReferenceMaxHits, and ReferenceScanAttempts must be greater than zero; ReferenceScanRetryDelayMilliseconds must be zero or greater."
}

$resolvedOutputRoot = [System.IO.Path]::GetFullPath($OutputRoot)
New-Item -ItemType Directory -Path $resolvedOutputRoot -Force | Out-Null

$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMdd-HHmmss', [System.Globalization.CultureInfo]::InvariantCulture)
$safePoseLabel = ConvertTo-SafePathSegment -Value $PoseLabel
$poseOutputRoot = Join-Path $resolvedOutputRoot ("riftscan-proof-{0}-{1}" -f $safePoseLabel, $stamp)
New-Item -ItemType Directory -Path $poseOutputRoot -Force | Out-Null

$referenceCommand = $null
$resolvedReferenceFile = $null
$referenceSummary = $null
$referenceCaptureError = $null
if ([string]::IsNullOrWhiteSpace($ReferenceFile)) {
    $referenceOutputFile = Join-Path $poseOutputRoot ("{0}-api-reference.json" -f $safePoseLabel)
    $referenceArgs = @(
        '-OutputRoot',
        $poseOutputRoot,
        '-OutputFile',
        $referenceOutputFile,
        '-ReferenceTolerance',
        $ReferenceTolerance.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '-ScanContextBytes',
        $ReferenceScanContextBytes.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '-MaxHits',
        $ReferenceMaxHits.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '-ScanAttempts',
        $ReferenceScanAttempts.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '-ScanRetryDelayMilliseconds',
        $ReferenceScanRetryDelayMilliseconds.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '-Json'
    )
    if ($ProcessId -gt 0) {
        $referenceArgs += @('-ProcessId', $ProcessId.ToString([System.Globalization.CultureInfo]::InvariantCulture))
    }
    if (-not [string]::IsNullOrWhiteSpace($TargetWindowHandle)) {
        $referenceArgs += @('-TargetWindowHandle', $TargetWindowHandle)
    }
    if (-not [string]::IsNullOrWhiteSpace($ProcessName)) {
        $referenceArgs += @('-ProcessName', $ProcessName)
    }

    $referenceCommand = Invoke-PowerShellScript -ScriptPath $referenceScript -Arguments $referenceArgs -AllowFailure
    if ($referenceCommand.ExitCode -eq 0) {
        $referenceSummary = ConvertFrom-JsonCompat -Text $referenceCommand.Output -Depth 80
        $resolvedReferenceFile = [string](Get-JsonPropertyValue -InputObject $referenceSummary -Names @('ReferenceFile'))
    }
    else {
        $referenceCaptureError = $referenceCommand.Output
    }
}
else {
    $resolvedReferenceFile = [System.IO.Path]::GetFullPath($ReferenceFile)
    if (-not (Test-Path -LiteralPath $resolvedReferenceFile -PathType Leaf)) {
        throw "Reference file was not found: $resolvedReferenceFile"
    }
}

$candidateResolution = $null
try {
    $candidateResolution = Resolve-CandidateFile
}
catch {
    if (-not (Test-TargetDriftMessage -Message $_.Exception.Message)) {
        throw
    }

    $pointerPath = [System.IO.Path]::GetFullPath($CurrentProofPointerFile)
    $targetDriftSummary = [pscustomobject][ordered]@{
        SchemaVersion = 1
        Mode = 'riftscan-proof-pose-capture'
        GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
        Status = 'blocked-target-drift'
        PoseLabel = $PoseLabel
        ProcessName = $ProcessName
        ProcessId = $ProcessId
        TargetWindowHandle = $TargetWindowHandle
        NoCheatEngine = $true
        MovementSent = $false
        MovementAllowed = $false
        CandidateFile = $null
        CandidateResolvedFromPointer = $false
        CurrentProofPointerFile = $pointerPath
        CandidateSource = $null
        ReferenceCaptured = (-not [string]::IsNullOrWhiteSpace($resolvedReferenceFile) -and (Test-Path -LiteralPath $resolvedReferenceFile -PathType Leaf))
        ReferenceFile = $resolvedReferenceFile
        ReferenceCaptureExitCode = if ($null -eq $referenceCommand) { $null } else { $referenceCommand.ExitCode }
        ReferenceCaptureError = $referenceCaptureError
        ReadbackSummaryFile = $null
        OutputRoot = $poseOutputRoot
        CurrentCoordinate = if ($null -eq $referenceSummary) {
            $null
        }
        else {
            ConvertTo-JsonSafeValue -Value (Get-JsonPropertyValue -InputObject $referenceSummary -Names @('Coordinate', 'CurrentCoordinate', 'coordinate'))
        }
        TargetDrift = [pscustomobject][ordered]@{
            source = 'current-proof-pointer-target-check'
            issues = @("target_drift:current_proof_pointer_target_mismatch:$($_.Exception.Message)")
            movementGate = 'blocked'
            proofAnchorPromoted = $false
            reason = 'Current proof pointer belongs to a different target epoch. Current API/reference state was reacquired when available, but movement remains blocked until candidates are rescored against the requested PID/HWND.'
        }
        PreservedHistoricalEvidence = Get-PreservedHistoricalPointerEvidence -PointerPath $pointerPath
        MovementGate = 'blocked_until_current_process_proof_anchor_is_rebuilt_after_target_drift'
        ReadbackWarningCount = 0
        ReadbackWarnings = @()
        WarningCount = 4
        Warnings = @(
            'This helper sends no input and uses no Cheat Engine path.',
            'SavedVariables are not used as live truth.',
            'The current proof pointer is historical for this target and cannot gate movement.',
            'Historical pointer data is preserved only as audit/reacquire hints.'
        )
        Commands = [pscustomobject][ordered]@{
            Reference = if ($null -eq $referenceCommand) {
                $null
            }
            else {
                [pscustomobject][ordered]@{
                    FilePath = $referenceCommand.FilePath
                    Arguments = @($referenceCommand.Arguments)
                    ExitCode = $referenceCommand.ExitCode
                }
            }
            Readback = $null
        }
    }

    if ($Json) {
        $targetDriftSummary | ConvertTo-Json -Depth 32
        exit 1
    }

    Write-Host 'RiftScan proof pose capture blocked by target drift.' -ForegroundColor Yellow
    Write-Host ("Status:       {0}" -f $targetDriftSummary.Status)
    Write-Host ("PID/HWND:     {0} / {1}" -f $targetDriftSummary.ProcessId, $targetDriftSummary.TargetWindowHandle)
    Write-Host ("Reference:    {0}" -f $targetDriftSummary.ReferenceFile)
    Write-Host ("Issue:        {0}" -f (($targetDriftSummary.TargetDrift.Issues) -join '; '))
    Write-Host 'Movement:     blocked; no input sent'
    Write-Host 'CE usage:     none'
    exit 1
}

$resolvedCandidateFile = [string]$candidateResolution.CandidateFile

$readbackArgs = @(
    '-CandidateFile',
    $resolvedCandidateFile,
    '-OutputRoot',
    $poseOutputRoot,
    '-ReadbackSampleCount',
    $ReadbackSampleCount.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '-ReadbackIntervalMilliseconds',
    $ReadbackIntervalMilliseconds.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '-Json'
)
if (-not [string]::IsNullOrWhiteSpace($resolvedReferenceFile) -and (Test-Path -LiteralPath $resolvedReferenceFile -PathType Leaf)) {
    $readbackArgs += @(
        '-ReferenceFile',
        $resolvedReferenceFile,
        '-ReferenceMaxAgeSeconds',
        $ReferenceMaxAgeSeconds.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '-ReferenceTolerance',
        $ReferenceTolerance.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '-TopReferenceMatches',
        $TopReferenceMatches.ToString([System.Globalization.CultureInfo]::InvariantCulture)
    )
}
if ($ProcessId -gt 0) {
    $readbackArgs += @('-ProcessId', $ProcessId.ToString([System.Globalization.CultureInfo]::InvariantCulture))
}
if (-not [string]::IsNullOrWhiteSpace($TargetWindowHandle)) {
    $readbackArgs += @('-TargetWindowHandle', $TargetWindowHandle)
}
if (-not [string]::IsNullOrWhiteSpace($ProcessName)) {
    $readbackArgs += @('-ProcessName', $ProcessName)
}

$readbackCommand = Invoke-PowerShellScript -ScriptPath $readbackScript -Arguments $readbackArgs -AllowFailure
$readbackSummary = ConvertFrom-JsonCompat -Text $readbackCommand.Output -Depth 80
$readbackSummaryFile = [string](Get-JsonPropertyValue -InputObject $readbackSummary -Names @('SummaryFile'))
if ([string]::IsNullOrWhiteSpace($readbackSummaryFile)) {
    $latestSummary = Get-ChildItem -LiteralPath $poseOutputRoot -Filter 'riftscan-riftreader-currentpid-*-readback-wrapper-summary-*.json' -File |
        Sort-Object LastWriteTimeUtc -Descending |
        Select-Object -First 1
    $readbackSummaryFile = if ($null -eq $latestSummary) { $null } else { $latestSummary.FullName }
}

$bestReferenceMatches = @(Get-JsonPropertyValue -InputObject $readbackSummary -Names @('BestReferenceMatches'))
$bestReferenceMatch = if ($bestReferenceMatches.Count -gt 0) { $bestReferenceMatches[0] } else { $null }
$referenceMatchCount = [int](Get-JsonPropertyValue -InputObject $readbackSummary -Names @('ReferenceMatchCount'))
$readbackFailures = [int](Get-JsonPropertyValue -InputObject $readbackSummary -Names @('ReadbackTotalRegionReadFailures'))
$stableDecodedCandidateCount = [int](Get-JsonPropertyValue -InputObject $readbackSummary -Names @('StableDecodedCandidateCount'))
$readbackWarnings = @(Get-JsonPropertyValue -InputObject $readbackSummary -Names @('Warnings') | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) } | ForEach-Object { [string]$_ })
$proofAnchorCandidateReadback = Get-JsonPropertyValue -InputObject $readbackSummary -Names @('ProofAnchorCandidateReadback')
$currentCoordinate = if ($null -eq $proofAnchorCandidateReadback) {
    $null
}
else {
    Get-JsonPropertyValue -InputObject $proofAnchorCandidateReadback -Names @('CurrentCoordinate')
}

$referenceCaptured = (-not [string]::IsNullOrWhiteSpace($resolvedReferenceFile) -and (Test-Path -LiteralPath $resolvedReferenceFile -PathType Leaf))
$status = if (-not $referenceCaptured) {
    'blocked-reference-unavailable'
}
elseif ($readbackCommand.ExitCode -eq 0 -and $referenceMatchCount -gt 0 -and $stableDecodedCandidateCount -gt 0 -and $readbackFailures -eq 0) {
    'captured'
}
else {
    'failed'
}

$wrapperWarnings = [System.Collections.Generic.List[string]]::new()
$wrapperWarnings.Add('This helper captures a same-time API reference and candidate readback only.') | Out-Null
$wrapperWarnings.Add('It sends no input and uses no Cheat Engine path.') | Out-Null
$wrapperWarnings.Add('A captured pose is not movement-grade by itself; promote at least two displaced poses before movement.') | Out-Null
foreach ($warning in $readbackWarnings) {
    $wrapperWarnings.Add(("Readback: {0}" -f $warning)) | Out-Null
}

$summary = [pscustomobject][ordered]@{
    SchemaVersion = 1
    Mode = 'riftscan-proof-pose-capture'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
    Status = $status
    PoseLabel = $PoseLabel
    ProcessName = [string](Get-JsonPropertyValue -InputObject $readbackSummary -Names @('ProcessName'))
    ProcessId = [int](Get-JsonPropertyValue -InputObject $readbackSummary -Names @('ProcessId'))
    TargetWindowHandle = [string](Get-JsonPropertyValue -InputObject $readbackSummary -Names @('TargetWindowHandle'))
    NoCheatEngine = $true
    MovementSent = $false
    MovementAllowed = [bool](Get-JsonPropertyValue -InputObject $readbackSummary -Names @('MovementAllowed'))
    CandidateFile = $resolvedCandidateFile
    CandidateResolvedFromPointer = [bool]$candidateResolution.ResolvedFromPointer
    CurrentProofPointerFile = $candidateResolution.CurrentProofPointerFile
    CandidateSource = $candidateResolution.CandidateSource
    ReferenceCaptured = $referenceCaptured
    ReferenceFile = $resolvedReferenceFile
    ReferenceCaptureExitCode = if ($null -eq $referenceCommand) { $null } else { $referenceCommand.ExitCode }
    ReferenceCaptureError = $referenceCaptureError
    ReadbackSummaryFile = $readbackSummaryFile
    OutputRoot = $poseOutputRoot
    ReferenceMatchCount = $referenceMatchCount
    StableDecodedCandidateCount = $stableDecodedCandidateCount
    ReadbackTotalRegionReadFailures = $readbackFailures
    BestReferenceMatch = ConvertTo-JsonSafeValue -Value $bestReferenceMatch
    CurrentCoordinate = ConvertTo-JsonSafeValue -Value $currentCoordinate
    ProofAnchorStatus = [string](Get-JsonPropertyValue -InputObject $readbackSummary -Names @('ProofAnchorStatus'))
    ProofAnchorIssues = @(Get-JsonPropertyValue -InputObject $readbackSummary -Names @('ProofAnchorIssues'))
    MovementGate = [string](Get-JsonPropertyValue -InputObject $readbackSummary -Names @('MovementGate'))
    ReadbackWarningCount = $readbackWarnings.Count
    ReadbackWarnings = @($readbackWarnings)
    WarningCount = $wrapperWarnings.Count
    Warnings = @($wrapperWarnings.ToArray())
    Commands = [pscustomobject][ordered]@{
        Reference = if ($null -eq $referenceCommand) {
            $null
        }
        else {
            [pscustomobject][ordered]@{
                FilePath = $referenceCommand.FilePath
                Arguments = @($referenceCommand.Arguments)
                ExitCode = $referenceCommand.ExitCode
            }
        }
        Readback = [pscustomobject][ordered]@{
            FilePath = $readbackCommand.FilePath
            Arguments = @($readbackCommand.Arguments)
            ExitCode = $readbackCommand.ExitCode
        }
    }
}

if ($Json) {
    $summary | ConvertTo-Json -Depth 32
    return
}

$color = if ([string]::Equals($status, 'captured', [System.StringComparison]::OrdinalIgnoreCase)) { 'Green' } else { 'Yellow' }
Write-Host 'RiftScan proof pose capture complete.' -ForegroundColor $color
Write-Host ("Status:       {0}" -f $status)
Write-Host ("Pose:         {0}" -f $PoseLabel)
Write-Host ("PID/HWND:     {0} / {1}" -f $summary.ProcessId, $summary.TargetWindowHandle)
Write-Host ("Reference:    {0}" -f $summary.ReferenceFile)
Write-Host ("Readback:     {0}" -f $summary.ReadbackSummaryFile)
Write-Host ("Matches:      {0}; stable decoded={1}; failures={2}" -f $summary.ReferenceMatchCount, $summary.StableDecodedCandidateCount, $summary.ReadbackTotalRegionReadFailures)
if ($null -ne $summary.CurrentCoordinate) {
    Write-Host ("Current coord: X={0:0.######} Y={1:0.######} Z={2:0.######}" -f [double]$summary.CurrentCoordinate.X, [double]$summary.CurrentCoordinate.Y, [double]$summary.CurrentCoordinate.Z)
}
Write-Host 'Movement:     no input sent'
Write-Host 'CE usage:     none'

if (-not [string]::Equals($status, 'captured', [System.StringComparison]::OrdinalIgnoreCase)) {
    exit 1
}
