[CmdletBinding()]
param(
    [switch]$Json,
    [string]$Label,
    [switch]$RefreshOwnerComponents,
    [switch]$RefreshReaderBridge,
    [switch]$NoAhkFallback,
    [string]$OwnerComponentsFile = (Join-Path $PSScriptRoot 'captures\player-owner-components.json'),
    [string]$OutputFile = (Join-Path $PSScriptRoot 'captures\player-actor-orientation.json'),
    [string]$PreviousFile = (Join-Path $PSScriptRoot 'captures\player-actor-orientation.previous.json')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$ownerComponentScript = Join-Path $PSScriptRoot 'capture-player-owner-components.ps1'
$refreshReaderBridgeScript = Join-Path $PSScriptRoot 'refresh-readerbridge-export.ps1'

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

    return ($output -join [Environment]::NewLine) | ConvertFrom-Json -Depth 30
}

function Normalize-AngleRadians {
    param([double]$Radians)

    $normalized = $Radians
    while ($normalized -gt [Math]::PI) {
        $normalized -= 2.0 * [Math]::PI
    }

    while ($normalized -lt -[Math]::PI) {
        $normalized += 2.0 * [Math]::PI
    }

    return $normalized
}

function Convert-RadiansToDegrees {
    param([double]$Radians)
    return $Radians * 180.0 / [Math]::PI
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

    if ($null -eq $Vector -or $null -eq $Vector.X -or $null -eq $Vector.Y -or $null -eq $Vector.Z) {
        return 'n/a'
    }

    return '{0}, {1}, {2}' -f
        (Format-Nullable -Value $Vector.X -Format '0.00000'),
        (Format-Nullable -Value $Vector.Y -Format '0.00000'),
        (Format-Nullable -Value $Vector.Z -Format '0.00000')
}

function Get-VectorDeltaMagnitude {
    param(
        $CurrentVector,
        $PreviousVector
    )

    if ($null -eq $CurrentVector -or $null -eq $PreviousVector) {
        return $null
    }

    if ($null -eq $CurrentVector.X -or $null -eq $CurrentVector.Y -or $null -eq $CurrentVector.Z) {
        return $null
    }

    if ($null -eq $PreviousVector.X -or $null -eq $PreviousVector.Y -or $null -eq $PreviousVector.Z) {
        return $null
    }

    $dx = [double]$CurrentVector.X - [double]$PreviousVector.X
    $dy = [double]$CurrentVector.Y - [double]$PreviousVector.Y
    $dz = [double]$CurrentVector.Z - [double]$PreviousVector.Z

    return [Math]::Sqrt(($dx * $dx) + ($dy * $dy) + ($dz * $dz))
}

function Get-CoordDeltaMagnitude {
    param(
        $CurrentCoord,
        $PreviousCoord
    )

    if ($null -eq $CurrentCoord -or $null -eq $PreviousCoord) {
        return $null
    }

    if ($null -eq $CurrentCoord.X -or $null -eq $CurrentCoord.Y -or $null -eq $CurrentCoord.Z) {
        return $null
    }

    if ($null -eq $PreviousCoord.X -or $null -eq $PreviousCoord.Y -or $null -eq $PreviousCoord.Z) {
        return $null
    }

    $dx = [double]$CurrentCoord.X - [double]$PreviousCoord.X
    $dy = [double]$CurrentCoord.Y - [double]$PreviousCoord.Y
    $dz = [double]$CurrentCoord.Z - [double]$PreviousCoord.Z

    return [Math]::Sqrt(($dx * $dx) + ($dy * $dy) + ($dz * $dz))
}

function Get-PreviousCaptureDelta {
    param(
        $CurrentCapture,
        $PreviousCapture,
        [string]$PreviousPath
    )

    if ($null -eq $PreviousCapture) {
        return $null
    }

    $currentPreferred = $CurrentCapture.ReaderOrientation.PreferredEstimate
    $previousPreferred = $PreviousCapture.ReaderOrientation.PreferredEstimate

    $yawDeltaDegrees = $null
    if ($currentPreferred -and $previousPreferred -and $null -ne $currentPreferred.YawRadians -and $null -ne $previousPreferred.YawRadians) {
        $yawDeltaDegrees = Convert-RadiansToDegrees -Radians (Normalize-AngleRadians -Radians ([double]$currentPreferred.YawRadians - [double]$previousPreferred.YawRadians))
    }

    $pitchDeltaDegrees = $null
    if ($currentPreferred -and $previousPreferred -and $null -ne $currentPreferred.PitchRadians -and $null -ne $previousPreferred.PitchRadians) {
        $pitchDeltaDegrees = Convert-RadiansToDegrees -Radians (Normalize-AngleRadians -Radians ([double]$currentPreferred.PitchRadians - [double]$previousPreferred.PitchRadians))
    }

    return [pscustomobject]@{
        PreviousFile = $PreviousPath
        PreviousGeneratedAtUtc = $PreviousCapture.GeneratedAtUtc
        PreferredYawDeltaDegrees = $yawDeltaDegrees
        PreferredPitchDeltaDegrees = $pitchDeltaDegrees
        VectorDeltaMagnitude = Get-VectorDeltaMagnitude -CurrentVector $currentPreferred.Vector -PreviousVector $previousPreferred.Vector
        CoordDeltaMagnitude = Get-CoordDeltaMagnitude -CurrentCoord $CurrentCapture.ReaderOrientation.PlayerCoord -PreviousCoord $PreviousCapture.ReaderOrientation.PlayerCoord
    }
}

function Write-ActorOrientationText {
    param($Document)

    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add("Actor orientation capture")
    $lines.Add("Output file:                 $($Document.OutputFile)")
    $lines.Add("Generated (UTC):             $($Document.GeneratedAtUtc)")
    $lines.Add("Label:                       $(if ([string]::IsNullOrWhiteSpace([string]$Document.Label)) { 'n/a' } else { [string]$Document.Label })")
    $lines.Add("Artifact file:               $($Document.ReaderOrientation.ArtifactFile)")
    $lines.Add("Artifact generated (UTC):    $($Document.ReaderOrientation.ArtifactGeneratedAtUtc)")
    $lines.Add("Snapshot file:               $(if ($Document.ReaderOrientation.SnapshotFile) { $Document.ReaderOrientation.SnapshotFile } else { 'n/a' })")
    $lines.Add("Player:                      $(if ($Document.ReaderOrientation.PlayerName) { $Document.ReaderOrientation.PlayerName } else { 'n/a' })")
    $lines.Add("Player coords:               $(Format-Vector $Document.ReaderOrientation.PlayerCoord)")
    $lines.Add("Selected source:             $($Document.ReaderOrientation.SelectedSourceAddress)")
    $lines.Add("Selected entry:              index $($Document.ReaderOrientation.SelectedEntryIndex) | $($Document.ReaderOrientation.SelectedEntryAddress)")
    $lines.Add("Preferred vector:            $(Format-Vector $Document.ReaderOrientation.PreferredEstimate.Vector)")
    $lines.Add("Actor yaw/pitch (rad):       $(Format-Nullable $Document.ReaderOrientation.PreferredEstimate.YawRadians '0.000000') / $(Format-Nullable $Document.ReaderOrientation.PreferredEstimate.PitchRadians '0.000000')")
    $lines.Add("Actor yaw/pitch (deg):       $(Format-Nullable $Document.ReaderOrientation.PreferredEstimate.YawDegrees '0.000') / $(Format-Nullable $Document.ReaderOrientation.PreferredEstimate.PitchDegrees '0.000')")

    if ($Document.ChangeFromPrevious) {
        $lines.Add("Prev capture:                $($Document.ChangeFromPrevious.PreviousFile)")
        $lines.Add("Prev yaw/pitch delta (deg):  $(Format-Nullable $Document.ChangeFromPrevious.PreferredYawDeltaDegrees '0.000') / $(Format-Nullable $Document.ChangeFromPrevious.PreferredPitchDeltaDegrees '0.000')")
        $lines.Add("Prev vector delta:           $(Format-Nullable $Document.ChangeFromPrevious.VectorDeltaMagnitude '0.000000')")
        $lines.Add("Prev coord delta:            $(Format-Nullable $Document.ChangeFromPrevious.CoordDeltaMagnitude '0.000000')")
    }

    if ($Document.ReaderOrientation.Notes -and $Document.ReaderOrientation.Notes.Count -gt 0) {
        $lines.Add("Orientation notes:           $([string]::Join('; ', $Document.ReaderOrientation.Notes))")
    }

    if ($Document.Notes -and $Document.Notes.Count -gt 0) {
        $lines.Add("Capture notes:               $([string]::Join('; ', $Document.Notes))")
    }

    return [string]::Join([Environment]::NewLine, $lines)
}

$resolvedOwnerComponentsFile = [System.IO.Path]::GetFullPath($OwnerComponentsFile)
$resolvedOutputFile = [System.IO.Path]::GetFullPath($OutputFile)
$resolvedPreviousFile = [System.IO.Path]::GetFullPath($PreviousFile)

if ($RefreshReaderBridge) {
    $refreshArguments = @{ 'NoReader' = $true }
    if ($NoAhkFallback) {
        $refreshArguments['NoAhkFallback'] = $true
    }

    & $refreshReaderBridgeScript @refreshArguments | Out-Null
}

if ($RefreshOwnerComponents -or -not (Test-Path -LiteralPath $resolvedOwnerComponentsFile)) {
    & $ownerComponentScript -OutputFile $resolvedOwnerComponentsFile -Json | Out-Null
}

$orientation = Invoke-ReaderJson -Arguments @(
    '--read-player-orientation',
    '--owner-components-file', $resolvedOwnerComponentsFile,
    '--json')

$notes = New-Object System.Collections.Generic.List[string]
$notes.Add('This helper is actor-oriented: it reads the selected owner/source component and derives yaw/pitch from the live orientation vector snapshot.')
$notes.Add('Use -RefreshOwnerComponents when you want to recapture the owner/source component live before computing yaw/pitch.')
$notes.Add('For cleaner live tests, keep movement minimal and compare labeled captures before/after controlled facing changes.')

$document = [pscustomobject]@{
    Mode = 'player-actor-orientation-capture'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
    Label = $Label
    OutputFile = $resolvedOutputFile
    PreviousFile = $resolvedPreviousFile
    ReaderOrientation = $orientation
    Notes = $notes
}

$previousCapture = $null
if (Test-Path -LiteralPath $resolvedOutputFile) {
    $previousJson = Get-Content -LiteralPath $resolvedOutputFile -Raw
    if (-not [string]::IsNullOrWhiteSpace($previousJson)) {
        $previousCapture = $previousJson | ConvertFrom-Json -Depth 30
    }

    $previousDirectory = Split-Path -Path $resolvedPreviousFile -Parent
    if (-not [string]::IsNullOrWhiteSpace($previousDirectory)) {
        New-Item -ItemType Directory -Path $previousDirectory -Force | Out-Null
    }

    Copy-Item -LiteralPath $resolvedOutputFile -Destination $resolvedPreviousFile -Force
}

$document | Add-Member -NotePropertyName ChangeFromPrevious -NotePropertyValue (Get-PreviousCaptureDelta -CurrentCapture $document -PreviousCapture $previousCapture -PreviousPath $resolvedPreviousFile)

$outputDirectory = Split-Path -Path $resolvedOutputFile -Parent
if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

$jsonText = $document | ConvertTo-Json -Depth 30
[System.IO.File]::WriteAllText($resolvedOutputFile, $jsonText)

if ($Json) {
    Write-Output $jsonText
    exit 0
}

Write-Output (Write-ActorOrientationText -Document $document)
