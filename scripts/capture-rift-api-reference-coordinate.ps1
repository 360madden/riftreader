[CmdletBinding()]
param(
    [string]$ProcessName = 'rift_x64',
    [int]$ProcessId,
    [string]$TargetWindowHandle,
    [string]$ReaderProject = (Join-Path (Resolve-Path (Join-Path $PSScriptRoot '..')).Path 'reader\RiftReader.Reader\RiftReader.Reader.csproj'),
    [string]$OutputRoot = (Join-Path $PSScriptRoot 'captures'),
    [string]$OutputFile,
    [string]$ScanResultFile,
    [int]$ScanContextBytes = 512,
    [int]$MaxHits = 64,
    [int]$ScanAttempts = 3,
    [int]$ScanRetryDelayMilliseconds = 1000,
    [double]$ReferenceTolerance = 0.25,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (-not ([System.Management.Automation.PSTypeName]'RiftApiReferenceTargetNative').Type) {
    Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public static class RiftApiReferenceTargetNative
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

function ConvertTo-InvariantDouble {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value,

        [Parameter(Mandatory = $true)]
        [string]$FieldName
    )

    try {
        return [double]::Parse($Value, [System.Globalization.NumberStyles]::Float, [System.Globalization.CultureInfo]::InvariantCulture)
    }
    catch {
        throw "Could not parse marker field '$FieldName' as a number: '$Value'."
    }
}

function ConvertTo-InvariantInt64 {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value,

        [Parameter(Mandatory = $true)]
        [string]$FieldName
    )

    try {
        return [Int64]::Parse($Value, [System.Globalization.NumberStyles]::Integer, [System.Globalization.CultureInfo]::InvariantCulture)
    }
    catch {
        throw "Could not parse marker field '$FieldName' as an integer: '$Value'."
    }
}

function ConvertFrom-HexBytes {
    param([string]$Hex)

    if ([string]::IsNullOrWhiteSpace($Hex)) {
        return @()
    }

    $normalized = ($Hex -replace '\s+', '').Trim()
    if (($normalized.Length % 2) -ne 0) {
        throw "Hex byte string has odd length."
    }

    $bytes = New-Object byte[] ($normalized.Length / 2)
    for ($i = 0; $i -lt $bytes.Length; $i++) {
        $bytes[$i] = [Convert]::ToByte($normalized.Substring($i * 2, 2), 16)
    }

    return $bytes
}

function ConvertTo-UtcStamp {
    return [DateTimeOffset]::UtcNow.UtcDateTime.ToString("yyyy-MM-dd'T'HH:mm:ss.fffffff'Z'", [System.Globalization.CultureInfo]::InvariantCulture)
}

function Invoke-ExternalCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        [string]$WorkingDirectory
    )

    $previousLocation = Get-Location
    try {
        if (-not [string]::IsNullOrWhiteSpace($WorkingDirectory)) {
            Set-Location -LiteralPath $WorkingDirectory
        }

        $output = & $FilePath @Arguments 2>&1
        $exitCode = $LASTEXITCODE
        $text = $output -join [Environment]::NewLine
        if ($exitCode -ne 0) {
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

function Resolve-LiveTargetProcess {
    $normalizedName = Get-NormalizedProcessName -Name $ProcessName
    $handle = ConvertTo-WindowHandle -HandleText $TargetWindowHandle

    if ($handle -ne [IntPtr]::Zero) {
        if (-not [RiftApiReferenceTargetNative]::IsWindow($handle)) {
            throw "Target window handle '$TargetWindowHandle' is not a valid window."
        }

        $ownerProcessId = [uint32]0
        [void][RiftApiReferenceTargetNative]::GetWindowThreadProcessId($handle, [ref]$ownerProcessId)
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
            ProcessId = [int]$ownerProcessId
            ProcessName = $process.ProcessName
            TargetWindowHandle = Format-WindowHandle -Handle $handle
        }
    }

    if ($ProcessId -gt 0) {
        $process = Get-Process -Id $ProcessId -ErrorAction Stop
        if (-not [string]::IsNullOrWhiteSpace($normalizedName) -and
            -not [string]::Equals($process.ProcessName, $normalizedName, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Target PID $ProcessId is process '$($process.ProcessName)', not '$ProcessName'."
        }

        return [pscustomobject]@{
            ProcessId = $process.Id
            ProcessName = $process.ProcessName
            TargetWindowHandle = Format-WindowHandle -Handle $process.MainWindowHandle
        }
    }

    $matches = @(Get-Process -Name $normalizedName -ErrorAction Stop | Sort-Object StartTime -Descending)
    if ($matches.Count -ne 1) {
        throw "Expected exactly one '$ProcessName' process when no PID/HWND is supplied; found $($matches.Count). Pass -ProcessId or -TargetWindowHandle."
    }

    return [pscustomobject]@{
        ProcessId = $matches[0].Id
        ProcessName = $matches[0].ProcessName
        TargetWindowHandle = Format-WindowHandle -Handle $matches[0].MainWindowHandle
    }
}

function Split-RiftApiMarker {
    param([Parameter(Mandatory = $true)][string]$Marker)

    $fields = @{}
    foreach ($part in $Marker -split '\|') {
        $separatorIndex = $part.IndexOf('=')
        if ($separatorIndex -gt 0) {
            $fields[$part.Substring(0, $separatorIndex)] = $part.Substring($separatorIndex + 1)
        }
    }

    foreach ($required in @('schema', 'seq', 'sampledAt', 'source', 'view', 'status', 'x', 'y', 'z', 'savedVariablesUse')) {
        if (-not $fields.ContainsKey($required) -or [string]::IsNullOrWhiteSpace([string]$fields[$required])) {
            throw "Rift API marker is missing required field '$required': $Marker"
        }
    }

    return $fields
}

function Get-RiftApiProbeMarkers {
    param([Parameter(Mandatory = $true)]$Scan)

    $seenMarkers = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    $textRecords = [System.Collections.Generic.List[object]]::new()
    foreach ($hit in @($Scan.Hits)) {
        $context = Get-JsonPropertyValue -InputObject $hit -Names @('Context')
        $preview = [string](Get-JsonPropertyValue -InputObject $context -Names @('AsciiPreview'))
        $bytesHex = [string](Get-JsonPropertyValue -InputObject $context -Names @('BytesHex'))
        if (-not [string]::IsNullOrWhiteSpace($preview)) {
            $textRecords.Add([pscustomobject]@{
                    Hit = $hit
                    Text = $preview
                }) | Out-Null
        }

        if (-not [string]::IsNullOrWhiteSpace($bytesHex)) {
            $bytes = ConvertFrom-HexBytes -Hex $bytesHex
            if ($bytes.Count -gt 0) {
                $textRecords.Add([pscustomobject]@{
                        Hit = $hit
                        Text = [System.Text.Encoding]::ASCII.GetString($bytes)
                    }) | Out-Null
            }
        }
    }

    $hasLiveRiftApiProbeContext = $false
    foreach ($record in $textRecords) {
        $text = [string]$record.Text
        if ($text.Contains('RRAPICOORD1') -and
            $text.Contains('source=rift-api') -and
            $text.Contains('view=Inspect.Unit.Detail(player)')) {
            $hasLiveRiftApiProbeContext = $true
            break
        }
    }

    foreach ($record in $textRecords) {
        $hit = $record.Hit
        $text = [string]$record.Text
        foreach ($match in [regex]::Matches($text, 'RRAPICOORD1\|[^\x00\r\n]+?savedVariablesUse=none')) {
            $marker = $match.Value
            if (-not $seenMarkers.Add($marker)) {
                continue
            }

            $fields = Split-RiftApiMarker -Marker $marker
            $status = [string]$fields['status']
            $source = [string]$fields['source']
            $savedVariablesUse = [string]$fields['savedVariablesUse']

            [pscustomobject][ordered]@{
                Marker = $marker
                ReferenceKind = 'rrapicoord1-marker'
                Schema = [string]$fields['schema']
                Seq = ConvertTo-InvariantInt64 -Value ([string]$fields['seq']) -FieldName 'seq'
                SampledAt = ConvertTo-InvariantDouble -Value ([string]$fields['sampledAt']) -FieldName 'sampledAt'
                Source = $source
                View = [string]$fields['view']
                Status = $status
                X = ConvertTo-InvariantDouble -Value ([string]$fields['x']) -FieldName 'x'
                Y = ConvertTo-InvariantDouble -Value ([string]$fields['y']) -FieldName 'y'
                Z = ConvertTo-InvariantDouble -Value ([string]$fields['z']) -FieldName 'z'
                PlayerId = if ($fields.ContainsKey('playerId')) { [string]$fields['playerId'] } else { $null }
                Name = if ($fields.ContainsKey('name')) { [string]$fields['name'] } else { $null }
                Zone = if ($fields.ContainsKey('zone')) { [string]$fields['zone'] } else { $null }
                Location = if ($fields.ContainsKey('location')) { [string]$fields['location'] } else { $null }
                SavedVariablesUse = $savedVariablesUse
                HitAddressHex = [string](Get-JsonPropertyValue -InputObject $hit -Names @('AddressHex'))
                HitEncoding = [string](Get-JsonPropertyValue -InputObject $hit -Names @('Encoding'))
                Classification = [string](Get-JsonPropertyValue -InputObject $hit -Names @('Classification'))
                IsUsableReference = (
                    [string]::Equals($status, 'pass', [System.StringComparison]::OrdinalIgnoreCase) -and
                    [string]::Equals($source, 'rift-api', [System.StringComparison]::OrdinalIgnoreCase) -and
                    [string]::Equals($savedVariablesUse, 'none', [System.StringComparison]::OrdinalIgnoreCase)
                )
            }
        }

        if (-not $hasLiveRiftApiProbeContext) {
            continue
        }

        $payloadPattern = 'P[0-9A-Fa-f]{8}name=(?<nameLen>\d+):(?<name>[^;\x00\r\n]+);(?<body>[^\x00\r\n]{0,1200}?);x=(?<x>-?\d+(?:\.\d+)?);y=(?<y>-?\d+(?:\.\d+)?);z=(?<z>-?\d+(?:\.\d+)?)'
        foreach ($match in [regex]::Matches($text, $payloadPattern)) {
            $marker = $match.Value
            if (-not $seenMarkers.Add($marker)) {
                continue
            }

            [pscustomobject][ordered]@{
                Marker = $marker
                ReferenceKind = 'rift-api-unit-payload-companion'
                Schema = '1'
                Seq = 0
                SampledAt = 0.0
                Source = 'rift-api'
                View = 'Inspect.Unit.Detail(player)'
                Status = 'pass'
                X = ConvertTo-InvariantDouble -Value $match.Groups['x'].Value -FieldName 'x'
                Y = ConvertTo-InvariantDouble -Value $match.Groups['y'].Value -FieldName 'y'
                Z = ConvertTo-InvariantDouble -Value $match.Groups['z'].Value -FieldName 'z'
                PlayerId = $null
                Name = $match.Groups['name'].Value
                Zone = $null
                Location = $null
                SavedVariablesUse = 'none'
                HitAddressHex = [string](Get-JsonPropertyValue -InputObject $hit -Names @('AddressHex'))
                HitEncoding = [string](Get-JsonPropertyValue -InputObject $hit -Names @('Encoding'))
                Classification = [string](Get-JsonPropertyValue -InputObject $hit -Names @('Classification'))
                IsUsableReference = $true
            }
        }
    }
}

if ($ScanContextBytes -le 0 -or $MaxHits -le 0 -or $ScanAttempts -le 0 -or $ScanRetryDelayMilliseconds -lt 0) {
    throw "ScanContextBytes, MaxHits, and ScanAttempts must be greater than zero; ScanRetryDelayMilliseconds must be zero or greater."
}

if ($ReferenceTolerance -lt 0) {
    throw "ReferenceTolerance must be zero or greater."
}

$resolvedOutputRoot = [System.IO.Path]::GetFullPath($OutputRoot)
New-Item -ItemType Directory -Path $resolvedOutputRoot -Force | Out-Null

$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMdd-HHmmss', [System.Globalization.CultureInfo]::InvariantCulture)
$scan = $null
$scanPath = $null
$target = $null
$scanCommand = $null

if (-not [string]::IsNullOrWhiteSpace($ScanResultFile)) {
    $scanPath = [System.IO.Path]::GetFullPath($ScanResultFile)
    if (-not (Test-Path -LiteralPath $scanPath -PathType Leaf)) {
        throw "Scan result file was not found: $scanPath"
    }

    $scan = ConvertFrom-JsonCompat -Text (Get-Content -LiteralPath $scanPath -Raw) -Depth 80
    $target = [pscustomobject]@{
        ProcessId = if ($ProcessId -gt 0) { $ProcessId } else { [int](Get-JsonPropertyValue -InputObject $scan -Names @('ProcessId', 'process_id', 'pid')) }
        ProcessName = if ([string]::IsNullOrWhiteSpace($ProcessName)) { [string](Get-JsonPropertyValue -InputObject $scan -Names @('ProcessName', 'process_name')) } else { Get-NormalizedProcessName -Name $ProcessName }
        TargetWindowHandle = if ([string]::IsNullOrWhiteSpace($TargetWindowHandle)) { $null } else { Format-WindowHandle -Handle (ConvertTo-WindowHandle -HandleText $TargetWindowHandle) }
    }
}
else {
    $target = Resolve-LiveTargetProcess
    $scanPath = Join-Path $resolvedOutputRoot ("rift-api-reference-scan-currentpid-{0}-{1}.json" -f $target.ProcessId, $stamp)
    $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
    $scanCommand = Invoke-ExternalCommand -FilePath 'dotnet' -Arguments @(
        'run',
        '--project',
        ([System.IO.Path]::GetFullPath($ReaderProject)),
        '--',
        '--pid',
        ([string]$target.ProcessId),
        '--scan-string',
        'RRAPICOORD1',
        '--scan-encoding',
        'both',
        '--scan-context',
        ([string]$ScanContextBytes),
        '--max-hits',
        ([string]$MaxHits),
        '--json'
    ) -WorkingDirectory $repoRoot
    $scanCommand.Output | Set-Content -LiteralPath $scanPath -Encoding UTF8
    $scan = ConvertFrom-JsonCompat -Text $scanCommand.Output -Depth 80
}

if ($null -eq $scan) {
    throw "No scan result was available."
}

$allMarkers = @(Get-RiftApiProbeMarkers -Scan $scan)
$usableMarkers = @($allMarkers | Where-Object { [bool]$_.IsUsableReference } | Sort-Object Seq -Descending)
if ($usableMarkers.Count -eq 0 -and [string]::IsNullOrWhiteSpace($ScanResultFile) -and $ScanAttempts -gt 1) {
    for ($attempt = 2; $attempt -le $ScanAttempts; $attempt++) {
        if ($ScanRetryDelayMilliseconds -gt 0) {
            Start-Sleep -Milliseconds $ScanRetryDelayMilliseconds
        }

        $attemptStamp = (Get-Date).ToUniversalTime().ToString('yyyyMMdd-HHmmss', [System.Globalization.CultureInfo]::InvariantCulture)
        $scanPath = Join-Path $resolvedOutputRoot ("rift-api-reference-scan-currentpid-{0}-{1}-attempt{2}.json" -f $target.ProcessId, $attemptStamp, $attempt)
        $scanCommand = Invoke-ExternalCommand -FilePath 'dotnet' -Arguments @(
            'run',
            '--project',
            ([System.IO.Path]::GetFullPath($ReaderProject)),
            '--',
            '--pid',
            ([string]$target.ProcessId),
            '--scan-string',
            'RRAPICOORD1',
            '--scan-encoding',
            'both',
            '--scan-context',
            ([string]$ScanContextBytes),
            '--max-hits',
            ([string]$MaxHits),
            '--json'
        ) -WorkingDirectory $repoRoot
        $scanCommand.Output | Set-Content -LiteralPath $scanPath -Encoding UTF8
        $scan = ConvertFrom-JsonCompat -Text $scanCommand.Output -Depth 80
        $allMarkers = @(Get-RiftApiProbeMarkers -Scan $scan)
        $usableMarkers = @($allMarkers | Where-Object { [bool]$_.IsUsableReference } | Sort-Object Seq -Descending)
        if ($usableMarkers.Count -gt 0) {
            break
        }
    }
}
if ($usableMarkers.Count -eq 0) {
    throw "No usable RRAPICOORD1 marker was found in '$scanPath'. Required fields: status=pass, source=rift-api, savedVariablesUse=none, numeric x/y/z."
}

$best = $usableMarkers[0]
$capturedAtUtc = ConvertTo-UtcStamp
if ([string]::IsNullOrWhiteSpace($OutputFile)) {
    $OutputFile = Join-Path $resolvedOutputRoot ("rift-api-reference-currentpid-{0}-{1}.json" -f $target.ProcessId, $stamp)
}

$resolvedOutputFile = [System.IO.Path]::GetFullPath($OutputFile)
$reference = [pscustomobject][ordered]@{
    source = 'rrapicoord1-memory-scan'
    captured_at_utc = $capturedAtUtc
    tolerance = $ReferenceTolerance
    coordinate = [pscustomobject][ordered]@{
        x = [double]$best.X
        y = [double]$best.Y
        z = [double]$best.Z
    }
    marker = [pscustomobject][ordered]@{
        referenceKind = [string]$best.ReferenceKind
        schema = [string]$best.Schema
        seq = [Int64]$best.Seq
        sampledAt = [double]$best.SampledAt
        status = [string]$best.Status
        source = [string]$best.Source
        view = [string]$best.View
        playerId = [string]$best.PlayerId
        name = [string]$best.Name
        zone = [string]$best.Zone
        location = [string]$best.Location
        hitAddressHex = [string]$best.HitAddressHex
        hitEncoding = [string]$best.HitEncoding
        classification = [string]$best.Classification
        raw = [string]$best.Marker
    }
    scanFile = $scanPath
    processId = [int]$target.ProcessId
    processName = [string]$target.ProcessName
    targetWindowHandle = [string]$target.TargetWindowHandle
    noCheatEngine = $true
    movementSent = $false
    savedVariablesUse = 'none'
}

$reference | ConvertTo-Json -Depth 16 | Set-Content -LiteralPath $resolvedOutputFile -Encoding UTF8

$summary = [pscustomobject][ordered]@{
    SchemaVersion = 1
    Mode = 'rift-api-reference-coordinate-capture'
    GeneratedAtUtc = (ConvertTo-UtcStamp)
    Status = 'captured'
    ProcessName = [string]$target.ProcessName
    ProcessId = [int]$target.ProcessId
    TargetWindowHandle = [string]$target.TargetWindowHandle
    NoCheatEngine = $true
    MovementSent = $false
    SavedVariablesUsedAsLiveTruth = $false
    ReferenceFile = $resolvedOutputFile
    ScanFile = $scanPath
    MarkerCount = $allMarkers.Count
    UsableMarkerCount = $usableMarkers.Count
    SelectedReferenceKind = [string]$best.ReferenceKind
    SelectedMarkerSeq = [Int64]$best.Seq
    SelectedMarkerSampledAt = [double]$best.SampledAt
    Coordinate = [pscustomobject][ordered]@{
        X = [double]$best.X
        Y = [double]$best.Y
        Z = [double]$best.Z
        CapturedAtUtc = $capturedAtUtc
    }
    ReferenceTolerance = $ReferenceTolerance
    Warnings = @(
        'This script scans memory read-only and sends no input.',
        'This script uses no Cheat Engine path.',
        'The output reference is for candidate scoring/proof promotion; it does not satisfy movement proof by itself.'
    )
    Command = if ($null -eq $scanCommand) {
        $null
    }
    else {
        [pscustomobject][ordered]@{
            FilePath = $scanCommand.FilePath
            Arguments = @($scanCommand.Arguments)
            ExitCode = $scanCommand.ExitCode
        }
    }
}

if ($Json) {
    $summary | ConvertTo-Json -Depth 16
    return
}

Write-Host 'Rift API reference coordinate captured.' -ForegroundColor Green
Write-Host ("PID/HWND:      {0} / {1}" -f $summary.ProcessId, $summary.TargetWindowHandle)
Write-Host ("Marker seq:    {0}" -f $summary.SelectedMarkerSeq)
Write-Host ("Coordinate:    X={0:0.######} Y={1:0.######} Z={2:0.######}" -f $summary.Coordinate.X, $summary.Coordinate.Y, $summary.Coordinate.Z)
Write-Host ("Reference:     {0}" -f $summary.ReferenceFile)
Write-Host ("Scan:          {0}" -f $summary.ScanFile)
Write-Host 'Movement:      no input sent'
Write-Host 'CE usage:      none'
