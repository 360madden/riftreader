[CmdletBinding()]
param(
    [switch]$Json,
    [string]$Label,
    [string]$Command = '/rbx export',
    [string]$ReaderBridgeSnapshotFile,
    [switch]$NoTrigger,
    [switch]$NoAhkFallback,
    [switch]$SkipBackgroundFocus,
    [string]$OutputFile = (Join-Path $(if ($PSScriptRoot) { $PSScriptRoot } elseif ($PSCommandPath) { Split-Path -Parent $PSCommandPath } else { (Get-Location).Path }) 'captures\readerbridge-boundary.json')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptRoot = if ($PSScriptRoot) { $PSScriptRoot } elseif ($PSCommandPath) { Split-Path -Parent $PSCommandPath } else { (Get-Location).Path }

. (Join-Path $scriptRoot 'actor-facing-common.ps1')

$repoRoot = Get-RiftReaderRepoRoot -ScriptRoot $scriptRoot
$readerProject = Get-RiftReaderProjectPath -RepoRoot $repoRoot
$postCommandScript = Join-Path $scriptRoot 'post-rift-command.ps1'
$postCommandAhkScript = Join-Path $PSScriptRoot 'post-rift-command-ahk.ps1'
$resolvedOutputFile = [System.IO.Path]::GetFullPath($OutputFile)

function Invoke-ReaderBridgeSnapshotJson {
    $arguments = @('--readerbridge-snapshot', '--json')
    if (-not [string]::IsNullOrWhiteSpace($ReaderBridgeSnapshotFile)) {
        $arguments += @('--readerbridge-snapshot-file', $ReaderBridgeSnapshotFile)
    }

    return Invoke-RiftReaderJson -ReaderProject $readerProject -Arguments $arguments
}

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

function Format-Vector {
    param($Vector)

    if ($null -eq $Vector) {
        return 'n/a'
    }

    $x = Get-OptionalPropertyValue -InputObject $Vector -PropertyName 'X'
    $y = Get-OptionalPropertyValue -InputObject $Vector -PropertyName 'Y'
    $z = Get-OptionalPropertyValue -InputObject $Vector -PropertyName 'Z'
    if ($null -eq $x -or $null -eq $y -or $null -eq $z) {
        return 'n/a'
    }

    return '{0}, {1}, {2}' -f
        (Format-Nullable -Value $x -Format '0.00000'),
        (Format-Nullable -Value $y -Format '0.00000'),
        (Format-Nullable -Value $z -Format '0.00000')
}

function Write-BoundaryText {
    param($Document)

    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add('ReaderBridge boundary capture')
    $lines.Add("Output file:                 $($Document.OutputFile)")
    $lines.Add("Generated (UTC):             $($Document.GeneratedAtUtc)")
    $lines.Add("Label:                       $(if ([string]::IsNullOrWhiteSpace([string]$Document.Label)) { 'n/a' } else { [string]$Document.Label })")
    $lines.Add("Snapshot file:               $($Document.SourceFile)")
    $lines.Add("Command issued:              $(if ([string]::IsNullOrWhiteSpace([string]$Document.CommandIssued)) { 'none' } else { [string]$Document.CommandIssued })")
    $lines.Add("Export reason/count:         $(if ($Document.ExportReason) { $Document.ExportReason } else { 'n/a' }) / $(if ($null -ne $Document.ExportCount) { $Document.ExportCount } else { 'n/a' })")
    $lines.Add("Player:                      $(if ($Document.PlayerName) { $Document.PlayerName } else { 'n/a' })")
    $lines.Add("Player coords:               $(Format-Vector $Document.PlayerCoord)")
    $lines.Add("Player zone/location:        $(if ($Document.PlayerZone) { $Document.PlayerZone } else { 'n/a' }) / $(if ($Document.PlayerLocation) { $Document.PlayerLocation } else { 'n/a' })")
    if ($Document.Notes -and $Document.Notes.Count -gt 0) {
        $lines.Add("Notes:                       $([string]::Join('; ', $Document.Notes))")
    }

    return [string]::Join([Environment]::NewLine, $lines)
}

$baselineSnapshot = $null
try {
    $baselineSnapshot = Invoke-ReaderBridgeSnapshotJson
}
catch {
    $baselineSnapshot = $null
}

$verifyFilePath = $null
if (-not [string]::IsNullOrWhiteSpace($ReaderBridgeSnapshotFile)) {
    $verifyFilePath = [System.IO.Path]::GetFullPath($ReaderBridgeSnapshotFile)
}
elseif ($null -ne $baselineSnapshot) {
    $verifyFilePath = [string](Get-OptionalPropertyValue -InputObject $baselineSnapshot -PropertyName 'SourceFile')
}

if (-not $NoTrigger) {
    $nativeArgs = @{
        Command = $Command
    }
    if (-not [string]::IsNullOrWhiteSpace($verifyFilePath)) {
        $nativeArgs['VerifyFilePath'] = $verifyFilePath
    }
    if ($SkipBackgroundFocus) {
        $nativeArgs['SkipBackgroundFocus'] = $true
    }

    try {
        & $postCommandScript @nativeArgs *> $null
    }
    catch {
        if ($NoAhkFallback) {
            throw
        }

        $ahkArgs = @{
            Command = $Command
        }
        if (-not [string]::IsNullOrWhiteSpace($verifyFilePath)) {
            $ahkArgs['VerifyFilePath'] = $verifyFilePath
        }

        & $postCommandAhkScript @ahkArgs *> $null
    }
}

$snapshot = Invoke-ReaderBridgeSnapshotJson
$current = Get-OptionalPropertyValue -InputObject $snapshot -PropertyName 'Current'
$player = Get-OptionalPropertyValue -InputObject $current -PropertyName 'Player'
$playerCoord = Get-OptionalPropertyValue -InputObject $player -PropertyName 'Coord'

if ($null -eq $playerCoord) {
    throw 'The ReaderBridge snapshot did not include player coordinates.'
}

$notes = New-Object System.Collections.Generic.List[string]
$notes.Add('Boundary captures use addon-exported coordinates sampled immediately around the stimulus boundary.')
if ($NoTrigger) {
    $notes.Add('No explicit /rbx export was triggered; this boundary reflects the latest available snapshot.')
}
else {
    $notes.Add('The helper triggered /rbx export and then reloaded the ReaderBridge snapshot.')
}

$baselineCurrent = Get-OptionalPropertyValue -InputObject $baselineSnapshot -PropertyName 'Current'
$baselineExportCount = Get-OptionalPropertyValue -InputObject $baselineCurrent -PropertyName 'ExportCount'
$currentExportCount = Get-OptionalPropertyValue -InputObject $current -PropertyName 'ExportCount'
if ($null -ne $baselineExportCount -and $null -ne $currentExportCount -and [int]$currentExportCount -le [int]$baselineExportCount -and -not $NoTrigger) {
    $notes.Add('Snapshot file timestamp advanced, but exportCount did not increase. Verify addon-side export state during live testing.')
}

$document = [pscustomobject]@{
    Mode                        = 'readerbridge-boundary-capture'
    GeneratedAtUtc              = [DateTimeOffset]::UtcNow.ToString('O')
    Label                       = $Label
    OutputFile                  = $resolvedOutputFile
    CommandIssued               = if ($NoTrigger) { $null } else { $Command }
    SourceFile                  = Get-OptionalPropertyValue -InputObject $snapshot -PropertyName 'SourceFile'
    SourceLoadedAtUtc           = Get-OptionalPropertyValue -InputObject $snapshot -PropertyName 'LoadedAtUtc'
    SourceSchemaVersion         = Get-OptionalPropertyValue -InputObject $snapshot -PropertyName 'SchemaVersion'
    PreviousExportCount         = $baselineExportCount
    PreviousGeneratedAtRealtime = Get-OptionalPropertyValue -InputObject $baselineCurrent -PropertyName 'GeneratedAtRealtime'
    ExportCount                 = $currentExportCount
    GeneratedAtRealtime         = Get-OptionalPropertyValue -InputObject $current -PropertyName 'GeneratedAtRealtime'
    ExportReason                = Get-OptionalPropertyValue -InputObject $current -PropertyName 'ExportReason'
    PlayerName                  = Get-OptionalPropertyValue -InputObject $player -PropertyName 'Name'
    PlayerZone                  = Get-OptionalPropertyValue -InputObject $player -PropertyName 'Zone'
    PlayerLocation              = Get-OptionalPropertyValue -InputObject $player -PropertyName 'LocationName'
    PlayerCoord                 = $playerCoord
    Notes                       = $notes
}

$outputDirectory = Split-Path -Path $resolvedOutputFile -Parent
if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

$jsonText = $document | ConvertTo-Json -Depth 40
[System.IO.File]::WriteAllText($resolvedOutputFile, $jsonText)

if ($Json) {
    Write-Output $jsonText
    return
}

Write-Output (Write-BoundaryText -Document $document)
