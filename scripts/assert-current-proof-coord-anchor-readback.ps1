[CmdletBinding()]
param(
    [string]$ProcessName = 'rift_x64',
    [int]$ProcessId,
    [string]$TargetWindowHandle,
    [string]$ProofCoordAnchorFile,
    [string]$OutputRoot = (Join-Path $PSScriptRoot 'captures'),
    [string]$ReaderSessionRoot = (Join-Path $PSScriptRoot 'sessions'),
    [int]$ProofAnchorMaxAgeSeconds = 60,
    [int]$ReadbackSampleCount = 3,
    [int]$ReadbackIntervalMilliseconds = 100,
    [int]$RegionLength = 140,
    [double]$StableTolerance = 0.000001,
    [switch]$UseCacheOnly,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$proofAnchorScript = Join-Path $PSScriptRoot 'assert-current-proof-coord-anchor.ps1'

if (-not ([System.Management.Automation.PSTypeName]'RiftProofCoordReadbackTargetNative').Type) {
    Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public static class RiftProofCoordReadbackTargetNative
{
    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool IsWindow(IntPtr hWnd);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
}
"@
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
        if (-not [RiftProofCoordReadbackTargetNative]::IsWindow($handle)) {
            throw "Target window handle '$TargetWindowHandle' is not a valid window."
        }

        $ownerProcessId = [uint32]0
        [void][RiftProofCoordReadbackTargetNative]::GetWindowThreadProcessId($handle, [ref]$ownerProcessId)
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

function Get-PowerShellExecutable {
    if (Get-Command -Name pwsh -CommandType Application -ErrorAction SilentlyContinue) {
        return 'pwsh'
    }

    return 'powershell'
}

function Invoke-PowerShellScript {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ScriptPath,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        [switch]$AllowFailure
    )

    return Invoke-ExternalCommand -FilePath (Get-PowerShellExecutable) -Arguments (@(
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

function ConvertTo-BoolCompat {
    param($Value)

    if ($null -eq $Value) {
        return $false
    }

    if ($Value -is [bool]) {
        return [bool]$Value
    }

    return [System.Convert]::ToBoolean($Value, [System.Globalization.CultureInfo]::InvariantCulture)
}

function ConvertTo-IsoTimestampString {
    param($Value)

    if ($null -eq $Value) {
        return $null
    }

    if ($Value -is [DateTimeOffset]) {
        return ([DateTimeOffset]$Value).ToUniversalTime().ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    }

    if ($Value -is [DateTime]) {
        return ([DateTime]$Value).ToUniversalTime().ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    }

    return [string]$Value
}

function Parse-HexUInt64 {
    param([string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) {
        throw 'Address value is empty.'
    }

    $trimmed = $Value.Trim()
    if ($trimmed.StartsWith('0x', [System.StringComparison]::OrdinalIgnoreCase)) {
        return [UInt64]::Parse($trimmed.Substring(2), [System.Globalization.NumberStyles]::AllowHexSpecifier, [System.Globalization.CultureInfo]::InvariantCulture)
    }

    return [UInt64]::Parse($trimmed, [System.Globalization.CultureInfo]::InvariantCulture)
}

function Format-HexUInt64 {
    param([UInt64]$Value)

    return ('0x{0:X}' -f $Value)
}

function ConvertFrom-HexBytes {
    param([string]$Hex)

    if ([string]::IsNullOrWhiteSpace($Hex)) {
        return [byte[]]::new(0)
    }

    $normalized = $Hex -replace '[^0-9A-Fa-f]', ''
    if (($normalized.Length % 2) -ne 0) {
        throw "Hex byte string has odd nibble count: $($normalized.Length)."
    }

    $bytes = [byte[]]::new($normalized.Length / 2)
    for ($i = 0; $i -lt $bytes.Length; $i++) {
        $bytes[$i] = [Convert]::ToByte($normalized.Substring($i * 2, 2), 16)
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

    if ($Offset -lt 0 -or $Offset + 4 -gt $Bytes.Length) {
        throw "Float32 offset $Offset is outside byte buffer length $($Bytes.Length)."
    }

    return [double][BitConverter]::ToSingle($Bytes, $Offset)
}

function Write-Utf8Json {
    param(
        [Parameter(Mandatory = $true)]
        $Document,

        [Parameter(Mandatory = $true)]
        [string]$Path,

        [int]$Depth = 80
    )

    $jsonText = $Document | ConvertTo-Json -Depth $Depth
    $utf8NoBom = [System.Text.UTF8Encoding]::new($false)
    [System.IO.File]::WriteAllText($Path, $jsonText, $utf8NoBom)
}

function Get-CommandSummary {
    param($CommandResult)

    if ($null -eq $CommandResult) {
        return $null
    }

    return [pscustomobject][ordered]@{
        FilePath = [string]$CommandResult.FilePath
        Arguments = @($CommandResult.Arguments)
        ExitCode = [int]$CommandResult.ExitCode
        OutputPreview = if ([string]::IsNullOrWhiteSpace([string]$CommandResult.Output)) {
            ''
        }
        elseif (([string]$CommandResult.Output).Length -gt 4000) {
            ([string]$CommandResult.Output).Substring(0, 4000)
        }
        else {
            [string]$CommandResult.Output
        }
    }
}

function New-ProofAnchorWatchset {
    param(
        [Parameter(Mandatory = $true)]
        [string]$TargetProcessName,

        [Parameter(Mandatory = $true)]
        [int]$TargetProcessId,

        [Parameter(Mandatory = $true)]
        [string]$RegionName,

        [Parameter(Mandatory = $true)]
        [string]$CandidateId,

        [Parameter(Mandatory = $true)]
        [string]$CandidateAddressHex,

        [Parameter(Mandatory = $true)]
        [string]$RegionAddressHex,

        [Parameter(Mandatory = $true)]
        [int]$CandidateOffsetInRegion,

        [Parameter(Mandatory = $true)]
        [int]$EffectiveRegionLength,

        [Parameter(Mandatory = $true)]
        [string]$AnchorFile
    )

    $candidateAddress = Parse-HexUInt64 -Value $CandidateAddressHex

    return [pscustomobject][ordered]@{
        SchemaVersion = 1
        Mode = 'proof-anchor-current-readback-watchset'
        GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
        ProcessName = $TargetProcessName
        ProcessId = $TargetProcessId
        CandidateCount = 1
        ProofCoordAnchorFile = $AnchorFile
        CandidateId = $CandidateId
        CandidateAddressHex = $CandidateAddressHex
        RegionAddressHex = $RegionAddressHex
        CandidateOffsetInRegion = $CandidateOffsetInRegion
        Regions = @(
            [pscustomobject][ordered]@{
                Name = $RegionName
                Address = $RegionAddressHex
                Length = $EffectiveRegionLength
                Category = 'proof-anchor-coordinate-triplet'
                Required = $true
                Priority = 0
                Notes = 'Generated from a valid current proof-anchor preflight; read-only, no movement, no Cheat Engine.'
            }
        )
        Candidates = @(
            [pscustomobject][ordered]@{
                CandidateId = $CandidateId
                AbsoluteAddressHex = $CandidateAddressHex
                RegionAddressHex = $RegionAddressHex
                CandidateOffsetInRegion = $CandidateOffsetInRegion
                XAddressHex = Format-HexUInt64 -Value $candidateAddress
                YAddressHex = Format-HexUInt64 -Value ($candidateAddress + [UInt64]4)
                ZAddressHex = Format-HexUInt64 -Value ($candidateAddress + [UInt64]8)
            }
        )
        Warnings = @(
            'No Cheat Engine path is used by this watchset.',
            'No input is sent; this proves current readback only.',
            'Movement remains controlled by the proof-anchor gate and must not be sent by this script.'
        )
    }
}

function New-AnchorReadbackSummary {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SamplesFile,

        [Parameter(Mandatory = $true)]
        [string]$RegionName,

        [Parameter(Mandatory = $true)]
        [string]$RegionAddressHex,

        [Parameter(Mandatory = $true)]
        [int]$CandidateOffsetInRegion,

        [Parameter(Mandatory = $true)]
        [double]$Tolerance
    )

    $decodedSamples = [System.Collections.Generic.List[object]]::new()
    $issues = [System.Collections.Generic.List[string]]::new()
    $readFailures = 0
    $regionAddressMatches = $true

    if (-not (Test-Path -LiteralPath $SamplesFile)) {
        $issues.Add("samples_file_missing:$SamplesFile") | Out-Null
        return [pscustomobject][ordered]@{
            DecodedSampleCount = 0
            MaxAbsDeltaAcrossReadbackSamples = $null
            StableAcrossReadbackSamples = $false
            RegionReadFailures = 0
            RegionAddressMatchesWatchset = $false
            CurrentCoordinate = $null
            FirstCoordinate = $null
            LastCoordinate = $null
            DecodedSamples = @()
            Issues = @($issues.ToArray())
        }
    }

    foreach ($line in Get-Content -LiteralPath $SamplesFile) {
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }

        $sample = ConvertFrom-JsonCompat -Text $line -Depth 80
        $sampleIndex = Get-JsonPropertyValue -InputObject $sample -Names @('SampleIndex')
        $regions = @(Get-JsonPropertyValue -InputObject $sample -Names @('Regions'))
        $regionMatches = @($regions | Where-Object {
                $regionNameValue = [string](Get-JsonPropertyValue -InputObject $_ -Names @('Name'))
                [string]::Equals($regionNameValue, $RegionName, [System.StringComparison]::OrdinalIgnoreCase)
            } | Select-Object -First 1)

        if ($regionMatches.Count -eq 0) {
            $issues.Add(("sample {0}: proof-anchor region '{1}' missing" -f $sampleIndex, $RegionName)) | Out-Null
            continue
        }

        $region = $regionMatches[0]
        $sampleRegionAddress = [string](Get-JsonPropertyValue -InputObject $region -Names @('Address'))
        if (-not [string]::Equals($sampleRegionAddress, $RegionAddressHex, [System.StringComparison]::OrdinalIgnoreCase)) {
            $regionAddressMatches = $false
            $issues.Add(("sample {0}: region address mismatch readback={1};expected={2}" -f $sampleIndex, $sampleRegionAddress, $RegionAddressHex)) | Out-Null
        }

        if (-not (ConvertTo-BoolCompat -Value (Get-JsonPropertyValue -InputObject $region -Names @('ReadSucceeded')))) {
            $readFailures++
            $issues.Add(("sample {0}: read failed" -f $sampleIndex)) | Out-Null
            continue
        }

        try {
            $bytes = ConvertFrom-HexBytes -Hex ([string](Get-JsonPropertyValue -InputObject $region -Names @('BytesHex')))
            $decodedSamples.Add([pscustomobject][ordered]@{
                    SampleIndex = [int]$sampleIndex
                    RecordedAtUtc = ConvertTo-IsoTimestampString -Value (Get-JsonPropertyValue -InputObject $sample -Names @('RecordedAtUtc'))
                    X = Read-Float32At -Bytes $bytes -Offset $CandidateOffsetInRegion
                    Y = Read-Float32At -Bytes $bytes -Offset ($CandidateOffsetInRegion + 4)
                    Z = Read-Float32At -Bytes $bytes -Offset ($CandidateOffsetInRegion + 8)
                }) | Out-Null
        }
        catch {
            $issues.Add(("sample {0}: {1}" -f $sampleIndex, $_.Exception.Message)) | Out-Null
        }
    }

    $decoded = @($decodedSamples.ToArray())
    $maxAbsDelta = $null
    if ($decoded.Count -gt 0) {
        $first = $decoded[0]
        $maxAbsDelta = 0.0
        foreach ($sample in $decoded) {
            $maxAbsDelta = [Math]::Max($maxAbsDelta, [Math]::Abs([double]$sample.X - [double]$first.X))
            $maxAbsDelta = [Math]::Max($maxAbsDelta, [Math]::Abs([double]$sample.Y - [double]$first.Y))
            $maxAbsDelta = [Math]::Max($maxAbsDelta, [Math]::Abs([double]$sample.Z - [double]$first.Z))
        }
    }

    $firstCoordinate = if ($decoded.Count -eq 0) {
        $null
    }
    else {
        [pscustomobject][ordered]@{
            X = [double]$decoded[0].X
            Y = [double]$decoded[0].Y
            Z = [double]$decoded[0].Z
            RecordedAtUtc = [string]$decoded[0].RecordedAtUtc
        }
    }

    $lastCoordinate = if ($decoded.Count -eq 0) {
        $null
    }
    else {
        $last = $decoded[$decoded.Count - 1]
        [pscustomobject][ordered]@{
            X = [double]$last.X
            Y = [double]$last.Y
            Z = [double]$last.Z
            RecordedAtUtc = [string]$last.RecordedAtUtc
        }
    }

    return [pscustomobject][ordered]@{
        DecodedSampleCount = $decoded.Count
        MaxAbsDeltaAcrossReadbackSamples = $maxAbsDelta
        StableAcrossReadbackSamples = ($decoded.Count -gt 0 -and $null -ne $maxAbsDelta -and [double]$maxAbsDelta -le $Tolerance)
        RegionReadFailures = $readFailures
        RegionAddressMatchesWatchset = $regionAddressMatches
        CurrentCoordinate = $lastCoordinate
        FirstCoordinate = $firstCoordinate
        LastCoordinate = $lastCoordinate
        DecodedSamples = @($decoded)
        Issues = @($issues.ToArray())
    }
}

function New-BlockedSummary {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Status,

        [Parameter(Mandatory = $true)]
        [string[]]$Issues,

        [int]$TargetProcessId = 0,
        [string]$TargetProcessName = '',
        [string]$TargetHandleHex = $null,
        [string]$SummaryPath = $null,
        $ProofPreflight = $null,
        [string]$ProofPreflightFile = $null
    )

    return [pscustomobject][ordered]@{
        SchemaVersion = 1
        Mode = 'proof-coord-anchor-current-readback'
        GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
        Status = $Status
        MovementAllowed = $false
        NoCheatEngine = $true
        MovementSent = $false
        ProcessName = $TargetProcessName
        ProcessId = if ($TargetProcessId -gt 0) { $TargetProcessId } else { $null }
        TargetWindowHandle = $TargetHandleHex
        ProofAnchorStatus = if ($null -eq $ProofPreflight) { $null } else { [string](Get-JsonPropertyValue -InputObject $ProofPreflight -Names @('Status')) }
        ProofAnchorMovementAllowed = if ($null -eq $ProofPreflight) { $false } else { ConvertTo-BoolCompat -Value (Get-JsonPropertyValue -InputObject $ProofPreflight -Names @('MovementAllowed')) }
        ProofAnchorSource = if ($null -eq $ProofPreflight) { $null } else { [string](Get-JsonPropertyValue -InputObject $ProofPreflight -Names @('AnchorSource')) }
        ProofAnchorMaxAgeSeconds = $ProofAnchorMaxAgeSeconds
        ProofAnchorFile = $ProofPreflightFile
        SummaryFile = $SummaryPath
        CanonicalCoordSource = 'none'
        MovementGate = 'blocked_until_current_process_proof_anchor_current_readback_is_valid'
        Issues = @($Issues)
        Warnings = @(
            'No movement was sent.',
            'No Cheat Engine path was used.',
            'This script fails closed when proof preflight or current readback does not validate.'
        )
    }
}

function Write-HumanSummary {
    param($Summary)

    $status = [string](Get-JsonPropertyValue -InputObject $Summary -Names @('Status'))
    $processIdValue = Get-JsonPropertyValue -InputObject $Summary -Names @('ProcessId')
    $targetHandleValue = Get-JsonPropertyValue -InputObject $Summary -Names @('TargetWindowHandle')
    $proofAnchorStatusValue = Get-JsonPropertyValue -InputObject $Summary -Names @('ProofAnchorStatus')
    $candidateIdValue = Get-JsonPropertyValue -InputObject $Summary -Names @('ProofAnchorCandidateId')
    $candidateAddressValue = Get-JsonPropertyValue -InputObject $Summary -Names @('ProofAnchorCandidateAddressHex')
    $readbackStatusValue = Get-JsonPropertyValue -InputObject $Summary -Names @('ReadbackIntegrityStatus')
    $readbackFailureValue = Get-JsonPropertyValue -InputObject $Summary -Names @('ReadbackTotalRegionReadFailures')
    $readbackSampleValue = Get-JsonPropertyValue -InputObject $Summary -Names @('ReadbackRecordedSampleCount')
    $currentCoordinateValue = Get-JsonPropertyValue -InputObject $Summary -Names @('CurrentCoordinate')
    $summaryFileValue = Get-JsonPropertyValue -InputObject $Summary -Names @('SummaryFile')
    $color = if ([string]::Equals($status, 'valid', [System.StringComparison]::OrdinalIgnoreCase)) { 'Green' } else { 'Yellow' }
    Write-Host 'Proof coord anchor current readback complete.' -ForegroundColor $color
    Write-Host ("PID/HWND:        {0} / {1}" -f $processIdValue, $targetHandleValue)
    Write-Host ("Proof anchor:    {0}" -f $proofAnchorStatusValue)
    Write-Host ("Proof gate:      {0}" -f $(if ([bool]$Summary.MovementAllowed) { 'allowed' } else { 'blocked' }))

    if (-not [string]::IsNullOrWhiteSpace([string]$candidateIdValue)) {
        Write-Host ("Candidate:       {0} @ {1}" -f $candidateIdValue, $candidateAddressValue)
    }

    if (-not [string]::IsNullOrWhiteSpace([string]$readbackStatusValue)) {
        Write-Host ("Readback:        {0}; failures={1}; samples={2}" -f $readbackStatusValue, $readbackFailureValue, $readbackSampleValue)
    }

    if ($null -ne $currentCoordinateValue) {
        Write-Host ("Current coord:   X={0:0.######} Y={1:0.######} Z={2:0.######}" -f [double]$currentCoordinateValue.X, [double]$currentCoordinateValue.Y, [double]$currentCoordinateValue.Z)
    }

    Write-Host ("Summary:         {0}" -f $summaryFileValue)
    Write-Host 'Movement:        no input sent'
    Write-Host 'CE usage:        none'

    $issues = @(Get-JsonPropertyValue -InputObject $Summary -Names @('Issues'))
    if ($issues.Count -gt 0) {
        Write-Host ("Issues:          {0}" -f ($issues -join '; ')) -ForegroundColor Yellow
    }
}

$resolvedOutputRoot = [System.IO.Path]::GetFullPath($OutputRoot)
$resolvedReaderSessionRoot = [System.IO.Path]::GetFullPath($ReaderSessionRoot)
New-Item -ItemType Directory -Path $resolvedOutputRoot -Force | Out-Null
New-Item -ItemType Directory -Path $resolvedReaderSessionRoot -Force | Out-Null

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$summaryPath = $null
$proofPreflight = $null
$proofPreflightPath = $null
$proofAnchorCommand = $null
$readbackCommand = $null

try {
    if (-not (Test-Path -LiteralPath $proofAnchorScript)) {
        throw "Proof anchor preflight script not found: $proofAnchorScript"
    }

    if ([string]::IsNullOrWhiteSpace($ProofCoordAnchorFile)) {
        $ProofCoordAnchorFile = Join-Path $PSScriptRoot 'captures\telemetry-proof-coord-anchor.json'
    }

    $resolvedProofCoordAnchorFile = [System.IO.Path]::GetFullPath($ProofCoordAnchorFile)
    $target = Resolve-TargetProcess
    $targetProcess = $target.Process
    $targetProcessId = [int]$targetProcess.Id
    $targetProcessName = $targetProcess.ProcessName
    $targetHandleHex = Format-WindowHandle -Handle $target.Handle
    $summaryPath = Join-Path $resolvedOutputRoot ("proof-anchor-currentpid-{0}-readback-summary-{1}.json" -f $targetProcessId, $stamp)
    $proofPreflightPath = Join-Path $resolvedOutputRoot ("assert-current-proof-coord-anchor-currentpid-{0}-readback-preflight-{1}.json" -f $targetProcessId, $stamp)

    $proofArgs = @(
        '-ProcessName',
        $targetProcessName,
        '-ProcessId',
        $targetProcessId.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '-ProofCoordAnchorFile',
        $resolvedProofCoordAnchorFile,
        '-MaxAgeSeconds',
        $ProofAnchorMaxAgeSeconds.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '-Json'
    )

    if (-not [string]::IsNullOrWhiteSpace($targetHandleHex)) {
        $proofArgs += @('-TargetWindowHandle', $targetHandleHex)
    }

    if ($UseCacheOnly) {
        $proofArgs += '-UseCacheOnly'
    }

    $proofAnchorCommand = Invoke-PowerShellScript -ScriptPath $proofAnchorScript -Arguments $proofArgs -AllowFailure
    $proofOutput = ([string]$proofAnchorCommand.Output).Trim()
    if ([string]::IsNullOrWhiteSpace($proofOutput)) {
        throw "Proof anchor preflight produced no JSON. ExitCode=$($proofAnchorCommand.ExitCode)"
    }

    $proofPreflight = ConvertFrom-JsonCompat -Text $proofOutput -Depth 80
    Write-Utf8Json -Document $proofPreflight -Path $proofPreflightPath -Depth 80

    $proofStatus = [string](Get-JsonPropertyValue -InputObject $proofPreflight -Names @('Status'))
    $proofMovementAllowed = ConvertTo-BoolCompat -Value (Get-JsonPropertyValue -InputObject $proofPreflight -Names @('MovementAllowed'))
    $proofIssues = @(Get-JsonPropertyValue -InputObject $proofPreflight -Names @('Issues'))
    if ($proofAnchorCommand.ExitCode -ne 0 -or
        -not [string]::Equals($proofStatus, 'valid', [System.StringComparison]::OrdinalIgnoreCase) -or
        -not $proofMovementAllowed) {
        $issues = [System.Collections.Generic.List[string]]::new()
        $issues.Add(("proof_anchor_preflight_not_valid:status={0};movementAllowed={1};exitCode={2}" -f $proofStatus, $proofMovementAllowed, $proofAnchorCommand.ExitCode)) | Out-Null
        foreach ($issue in $proofIssues) {
            $issues.Add([string]$issue) | Out-Null
        }

        $blocked = New-BlockedSummary `
            -Status 'failed' `
            -Issues @($issues.ToArray()) `
            -TargetProcessId $targetProcessId `
            -TargetProcessName $targetProcessName `
            -TargetHandleHex $targetHandleHex `
            -SummaryPath $summaryPath `
            -ProofPreflight $proofPreflight `
            -ProofPreflightFile $proofPreflightPath
        Write-Utf8Json -Document $blocked -Path $summaryPath -Depth 80

        if ($Json) {
            $blocked | ConvertTo-Json -Depth 80
        }
        else {
            Write-HumanSummary -Summary $blocked
        }

        exit 1
    }

    $anchor = Get-JsonPropertyValue -InputObject $proofPreflight -Names @('Anchor')
    $evidence = Get-JsonPropertyValue -InputObject $anchor -Names @('Evidence')
    $candidateId = [string](Get-JsonPropertyValue -InputObject $evidence -Names @('CandidateId'))
    if ([string]::IsNullOrWhiteSpace($candidateId)) {
        $candidateId = 'proof-anchor-coordinate-triplet'
    }

    $candidateAddressHex = [string](Get-JsonPropertyValue -InputObject $evidence -Names @('CandidateAddressHex'))
    if ([string]::IsNullOrWhiteSpace($candidateAddressHex)) {
        $candidateAddressHex = [string](Get-JsonPropertyValue -InputObject $anchor -Names @('CoordRegionAddress', 'ObjectBaseAddress'))
    }

    $regionAddressHex = [string](Get-JsonPropertyValue -InputObject $evidence -Names @('RegionAddressHex'))
    if ([string]::IsNullOrWhiteSpace($regionAddressHex)) {
        $regionAddressHex = $candidateAddressHex
    }

    if ([string]::IsNullOrWhiteSpace($candidateAddressHex) -or [string]::IsNullOrWhiteSpace($regionAddressHex)) {
        throw 'Proof anchor did not expose a candidate/region address to read.'
    }

    $candidateAddress = Parse-HexUInt64 -Value $candidateAddressHex
    $regionAddress = Parse-HexUInt64 -Value $regionAddressHex
    if ($candidateAddress -lt $regionAddress) {
        throw "Proof anchor candidate address $candidateAddressHex is before region address $regionAddressHex."
    }

    $candidateOffsetValue = Get-JsonPropertyValue -InputObject $evidence -Names @('CandidateOffsetInRegion')
    $candidateOffset = if ($null -ne $candidateOffsetValue) {
        [int]$candidateOffsetValue
    }
    else {
        [int]($candidateAddress - $regionAddress)
    }

    if ($candidateOffset -lt 0) {
        throw "Proof anchor candidate offset is negative: $candidateOffset"
    }

    $expectedCandidateAddress = $regionAddress + [UInt64]$candidateOffset
    $addressMatchesProofAnchor = $expectedCandidateAddress -eq $candidateAddress
    $minRegionLength = $candidateOffset + 12
    $effectiveRegionLength = [Math]::Max($RegionLength, $minRegionLength)
    $safeCandidateId = $candidateId -replace '[^A-Za-z0-9_.-]', '-'
    $regionName = "proof-anchor-vec3-$safeCandidateId"
    $watchsetPath = Join-Path $resolvedOutputRoot ("proof-anchor-currentpid-{0}-watchset-{1}.json" -f $targetProcessId, $stamp)
    $readbackSessionPath = Join-Path $resolvedReaderSessionRoot ("proof-anchor-currentpid-{0}-readback-{1}" -f $targetProcessId, $stamp)

    $watchset = New-ProofAnchorWatchset `
        -TargetProcessName $targetProcessName `
        -TargetProcessId $targetProcessId `
        -RegionName $regionName `
        -CandidateId $candidateId `
        -CandidateAddressHex (Format-HexUInt64 -Value $candidateAddress) `
        -RegionAddressHex (Format-HexUInt64 -Value $regionAddress) `
        -CandidateOffsetInRegion $candidateOffset `
        -EffectiveRegionLength $effectiveRegionLength `
        -AnchorFile $resolvedProofCoordAnchorFile
    Write-Utf8Json -Document $watchset -Path $watchsetPath -Depth 80

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
        'proof_anchor_current_readback_no_input',
        '--json'
    ) -WorkingDirectory $repoRoot

    $manifestPath = Join-Path $readbackSessionPath 'recording-manifest.json'
    $samplesPath = Join-Path $readbackSessionPath 'samples.ndjson'
    $manifest = ConvertFrom-JsonCompat -Text (Get-Content -LiteralPath $manifestPath -Raw) -Depth 80
    $anchorReadback = New-AnchorReadbackSummary `
        -SamplesFile $samplesPath `
        -RegionName $regionName `
        -RegionAddressHex (Format-HexUInt64 -Value $regionAddress) `
        -CandidateOffsetInRegion $candidateOffset `
        -Tolerance $StableTolerance

    $integrityStatus = [string](Get-JsonPropertyValue -InputObject $manifest -Names @('IntegrityStatus'))
    $totalRegionReadFailuresValue = Get-JsonPropertyValue -InputObject $manifest -Names @('TotalRegionReadFailures')
    $totalRegionReadFailures = if ($null -eq $totalRegionReadFailuresValue) { 0 } else { [int]$totalRegionReadFailuresValue }
    $recordedSampleCountValue = Get-JsonPropertyValue -InputObject $manifest -Names @('RecordedSampleCount')
    $recordedSampleCount = if ($null -eq $recordedSampleCountValue) { 0 } else { [int]$recordedSampleCountValue }
    $totalBytesReadValue = Get-JsonPropertyValue -InputObject $manifest -Names @('TotalBytesRead')
    $totalBytesRead = if ($null -eq $totalBytesReadValue) { 0 } else { [int64]$totalBytesReadValue }

    $issues = [System.Collections.Generic.List[string]]::new()
    if (-not $addressMatchesProofAnchor) {
        $issues.Add('proof_anchor_candidate_address_mismatch') | Out-Null
    }

    if (-not [string]::Equals($integrityStatus, 'ok', [System.StringComparison]::OrdinalIgnoreCase)) {
        $issues.Add("readback_integrity_not_ok:$integrityStatus") | Out-Null
    }

    if ($totalRegionReadFailures -ne 0) {
        $issues.Add("readback_region_failures_present:$totalRegionReadFailures") | Out-Null
    }

    if ([int]$anchorReadback.DecodedSampleCount -le 0) {
        $issues.Add('proof_anchor_candidate_has_no_decoded_current_readback_sample') | Out-Null
    }

    if (-not [bool]$anchorReadback.StableAcrossReadbackSamples) {
        $issues.Add('proof_anchor_candidate_not_stable_across_current_readback_samples') | Out-Null
    }

    if (-not [bool]$anchorReadback.RegionAddressMatchesWatchset) {
        $issues.Add('proof_anchor_readback_region_address_mismatch') | Out-Null
    }

    foreach ($issue in @($anchorReadback.Issues)) {
        $issues.Add([string]$issue) | Out-Null
    }

    $supportsProofAnchor = (
        $proofMovementAllowed -and
        $addressMatchesProofAnchor -and
        [string]::Equals($integrityStatus, 'ok', [System.StringComparison]::OrdinalIgnoreCase) -and
        $totalRegionReadFailures -eq 0 -and
        [int]$anchorReadback.DecodedSampleCount -gt 0 -and
        [bool]$anchorReadback.StableAcrossReadbackSamples -and
        [bool]$anchorReadback.RegionAddressMatchesWatchset
    )

    $summary = [pscustomobject][ordered]@{
        SchemaVersion = 1
        Mode = 'proof-coord-anchor-current-readback'
        GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
        Status = if ($supportsProofAnchor) { 'valid' } else { 'failed' }
        MovementAllowed = $supportsProofAnchor
        NoCheatEngine = $true
        MovementSent = $false
        ProcessName = $targetProcessName
        ProcessId = $targetProcessId
        TargetWindowHandle = $targetHandleHex
        ProofAnchorStatus = $proofStatus
        ProofAnchorMovementAllowed = $proofMovementAllowed
        ProofAnchorSource = [string](Get-JsonPropertyValue -InputObject $proofPreflight -Names @('AnchorSource'))
        ProofAnchorMaxAgeSeconds = $ProofAnchorMaxAgeSeconds
        ProofAnchorFile = $proofPreflightPath
        ProofCoordAnchorCacheFile = $resolvedProofCoordAnchorFile
        ProofAnchorCandidateId = $candidateId
        ProofAnchorCandidateAddressHex = Format-HexUInt64 -Value $candidateAddress
        RegionAddressHex = Format-HexUInt64 -Value $regionAddress
        CandidateOffsetInRegion = $candidateOffset
        CandidateAddressMatchesProofAnchor = $addressMatchesProofAnchor
        WatchsetFile = $watchsetPath
        ReadbackSessionPath = $readbackSessionPath
        ReadbackManifestFile = $manifestPath
        ReadbackSamplesFile = $samplesPath
        ReadbackIntegrityStatus = $integrityStatus
        ReadbackRecordedSampleCount = $recordedSampleCount
        ReadbackTotalBytesRead = $totalBytesRead
        ReadbackTotalRegionReadFailures = $totalRegionReadFailures
        DecodedSampleCount = [int]$anchorReadback.DecodedSampleCount
        StableAcrossReadbackSamples = [bool]$anchorReadback.StableAcrossReadbackSamples
        MaxAbsDeltaAcrossReadbackSamples = $anchorReadback.MaxAbsDeltaAcrossReadbackSamples
        CurrentCoordinate = $anchorReadback.CurrentCoordinate
        FirstCoordinate = $anchorReadback.FirstCoordinate
        LastCoordinate = $anchorReadback.LastCoordinate
        AnchorReadback = $anchorReadback
        CanonicalCoordSource = if ($supportsProofAnchor) { 'proof-anchor-current-readback' } else { 'none' }
        MovementGate = if ($supportsProofAnchor) { 'satisfied_by_current_process_proof_anchor_current_readback' } else { 'blocked_until_current_process_proof_anchor_current_readback_is_valid' }
        SummaryFile = $summaryPath
        Issues = @($issues.ToArray())
        Warnings = @(
            'This script sends no input and performs no movement.',
            'This script uses no Cheat Engine path.',
            'SavedVariables are not used as live truth.',
            'MovementAllowed means the proof-anchor/current-readback gate is satisfied; this script still sends no movement.'
        )
        Commands = [pscustomobject][ordered]@{
            ProofAnchor = Get-CommandSummary -CommandResult $proofAnchorCommand
            Readback = Get-CommandSummary -CommandResult $readbackCommand
        }
    }

    Write-Utf8Json -Document $summary -Path $summaryPath -Depth 80

    if ($Json) {
        $summary | ConvertTo-Json -Depth 80
    }
    else {
        Write-HumanSummary -Summary $summary
    }

    if (-not $supportsProofAnchor) {
        exit 1
    }
}
catch {
    $caughtMessage = $_.Exception.Message
    if ([string]::IsNullOrWhiteSpace($summaryPath)) {
        $summaryPath = Join-Path $resolvedOutputRoot ("proof-anchor-currentpid-unknown-readback-summary-{0}.json" -f $stamp)
    }

    $targetProcessId = 0
    $targetProcessName = ''
    $targetHandleHex = $null
    try {
        $target = Resolve-TargetProcess
        $targetProcessId = [int]$target.Process.Id
        $targetProcessName = $target.Process.ProcessName
        $targetHandleHex = Format-WindowHandle -Handle $target.Handle
    }
    catch {
        # Preserve the original failure; target resolution may be what failed.
    }

    $failed = New-BlockedSummary `
        -Status 'failed' `
        -Issues @($caughtMessage) `
        -TargetProcessId $targetProcessId `
        -TargetProcessName $targetProcessName `
        -TargetHandleHex $targetHandleHex `
        -SummaryPath $summaryPath `
        -ProofPreflight $proofPreflight `
        -ProofPreflightFile $proofPreflightPath
    Write-Utf8Json -Document $failed -Path $summaryPath -Depth 80

    if ($Json) {
        $failed | ConvertTo-Json -Depth 80
        exit 1
    }

    Write-HumanSummary -Summary $failed
    exit 1
}
