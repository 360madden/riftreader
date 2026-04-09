[CmdletBinding()]
param(
    [switch]$Json,
    [string]$Label,
    [switch]$SkipOwnerRefresh,
    [switch]$RefreshReaderBridge,
    [switch]$NoAhkFallback,
    [string]$ConfigFile = (Join-Path $env:APPDATA 'RIFT\rift.cfg'),
    [string]$OwnerComponentsFile = (Join-Path $PSScriptRoot 'captures\player-owner-components.json'),
    [string]$OutputFile = (Join-Path $PSScriptRoot 'captures\camera-state.json'),
    [string]$PreviousFile = (Join-Path $PSScriptRoot 'captures\camera-state.previous.json')
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

function Read-IniDocument {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Config file not found: $Path"
    }

    $sections = [ordered]@{}
    $currentSection = $null

    foreach ($rawLine in [System.IO.File]::ReadAllLines($Path)) {
        $line = $rawLine.Trim()
        if ([string]::IsNullOrWhiteSpace($line) -or $line.StartsWith(';') -or $line.StartsWith('#')) {
            continue
        }

        if ($line.StartsWith('[') -and $line.EndsWith(']')) {
            $currentSection = $line.Substring(1, $line.Length - 2)
            if (-not $sections.Contains($currentSection)) {
                $sections[$currentSection] = [ordered]@{}
            }

            continue
        }

        $separatorIndex = $line.IndexOf('=')
        if ($separatorIndex -lt 0 -or [string]::IsNullOrWhiteSpace($currentSection)) {
            continue
        }

        $key = $line.Substring(0, $separatorIndex).Trim()
        $value = $line.Substring($separatorIndex + 1).Trim()
        $sections[$currentSection][$key] = $value
    }

    return $sections
}

function Get-IniValue {
    param(
        [hashtable]$Document,
        [string]$Section,
        [string]$Key
    )

    if ($null -eq $Document -or -not $Document.Contains($Section)) {
        return $null
    }

    $section = $Document[$Section]
    if ($null -eq $section -or -not $section.Contains($Key)) {
        return $null
    }

    return [string]$section[$Key]
}

function Convert-ToNullableDouble {
    param([string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $null
    }

    $parsed = 0.0
    if ([double]::TryParse($Value, [System.Globalization.NumberStyles]::Float, [System.Globalization.CultureInfo]::InvariantCulture, [ref]$parsed)) {
        return $parsed
    }

    return $null
}

function Convert-ToNullableInt {
    param([string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $null
    }

    $parsed = 0
    if ([int]::TryParse($Value, [System.Globalization.NumberStyles]::Integer, [System.Globalization.CultureInfo]::InvariantCulture, [ref]$parsed)) {
        return $parsed
    }

    return $null
}

function Convert-ToNullableBool {
    param([string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $null
    }

    if ($Value.Equals('True', [System.StringComparison]::OrdinalIgnoreCase)) {
        return $true
    }

    if ($Value.Equals('False', [System.StringComparison]::OrdinalIgnoreCase)) {
        return $false
    }

    return $null
}

function Convert-RadiansToDegrees {
    param([double]$Radians)
    return $Radians * 180.0 / [Math]::PI
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

function New-AngleComparison {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [double]$SourceYawRadians,
        [double]$SourcePitchRadians,
        [Nullable[double]]$TargetYawRadians,
        [Nullable[double]]$TargetPitchRadians
    )

    if (-not $TargetYawRadians.HasValue -or -not $TargetPitchRadians.HasValue) {
        return [pscustomobject]@{
            Name = $Name
            SourceYawRadians = $SourceYawRadians
            SourceYawDegrees = (Convert-RadiansToDegrees -Radians $SourceYawRadians)
            SourcePitchRadians = $SourcePitchRadians
            SourcePitchDegrees = (Convert-RadiansToDegrees -Radians $SourcePitchRadians)
            TargetYawRadians = $TargetYawRadians
            TargetYawDegrees = $null
            TargetPitchRadians = $TargetPitchRadians
            TargetPitchDegrees = $null
            DeltaYawRadians = $null
            DeltaYawDegrees = $null
            DeltaPitchRadians = $null
            DeltaPitchDegrees = $null
        }
    }

    $deltaYaw = Normalize-AngleRadians -Radians ($SourceYawRadians - $TargetYawRadians.Value)
    $deltaPitch = Normalize-AngleRadians -Radians ($SourcePitchRadians - $TargetPitchRadians.Value)

    return [pscustomobject]@{
        Name = $Name
        SourceYawRadians = $SourceYawRadians
        SourceYawDegrees = (Convert-RadiansToDegrees -Radians $SourceYawRadians)
        SourcePitchRadians = $SourcePitchRadians
        SourcePitchDegrees = (Convert-RadiansToDegrees -Radians $SourcePitchRadians)
        TargetYawRadians = $TargetYawRadians.Value
        TargetYawDegrees = (Convert-RadiansToDegrees -Radians $TargetYawRadians.Value)
        TargetPitchRadians = $TargetPitchRadians.Value
        TargetPitchDegrees = (Convert-RadiansToDegrees -Radians $TargetPitchRadians.Value)
        DeltaYawRadians = $deltaYaw
        DeltaYawDegrees = (Convert-RadiansToDegrees -Radians $deltaYaw)
        DeltaPitchRadians = $deltaPitch
        DeltaPitchDegrees = (Convert-RadiansToDegrees -Radians $deltaPitch)
    }
}

function Get-VectorMagnitude {
    param($Coord)

    if ($null -eq $Coord -or $null -eq $Coord.X -or $null -eq $Coord.Y -or $null -eq $Coord.Z) {
        return $null
    }

    $x = [double]$Coord.X
    $y = [double]$Coord.Y
    $z = [double]$Coord.Z
    return [Math]::Sqrt(($x * $x) + ($y * $y) + ($z * $z))
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

    $currentCamera = $CurrentCapture.Camera
    $previousCamera = $PreviousCapture.Camera
    $currentWindow = $CurrentCapture.Window
    $previousWindow = $PreviousCapture.Window
    $currentPreferred = $CurrentCapture.ReaderOrientation.PreferredEstimate
    $previousPreferred = $PreviousCapture.ReaderOrientation.PreferredEstimate

    $coordDeltaMagnitude = $null
    if ($CurrentCapture.ReaderOrientation.PlayerCoord -and $PreviousCapture.ReaderOrientation.PlayerCoord) {
        $dx = [double]$CurrentCapture.ReaderOrientation.PlayerCoord.X - [double]$PreviousCapture.ReaderOrientation.PlayerCoord.X
        $dy = [double]$CurrentCapture.ReaderOrientation.PlayerCoord.Y - [double]$PreviousCapture.ReaderOrientation.PlayerCoord.Y
        $dz = [double]$CurrentCapture.ReaderOrientation.PlayerCoord.Z - [double]$PreviousCapture.ReaderOrientation.PlayerCoord.Z
        $coordDeltaMagnitude = [Math]::Sqrt(($dx * $dx) + ($dy * $dy) + ($dz * $dz))
    }

    return [pscustomobject]@{
        PreviousFile = $PreviousPath
        PreviousGeneratedAtUtc = $PreviousCapture.GeneratedAtUtc
        CameraYawDeltaDegrees = if ($currentCamera.YawRadians -ne $null -and $previousCamera.YawRadians -ne $null) { Convert-RadiansToDegrees -Radians (Normalize-AngleRadians -Radians ([double]$currentCamera.YawRadians - [double]$previousCamera.YawRadians)) } else { $null }
        CameraPitchDeltaDegrees = if ($currentCamera.PitchRadians -ne $null -and $previousCamera.PitchRadians -ne $null) { Convert-RadiansToDegrees -Radians (Normalize-AngleRadians -Radians ([double]$currentCamera.PitchRadians - [double]$previousCamera.PitchRadians)) } else { $null }
        WindowYawDeltaDegrees = if ($currentWindow.YawRadians -ne $null -and $previousWindow.YawRadians -ne $null) { Convert-RadiansToDegrees -Radians (Normalize-AngleRadians -Radians ([double]$currentWindow.YawRadians - [double]$previousWindow.YawRadians)) } else { $null }
        WindowPitchDeltaDegrees = if ($currentWindow.PitchRadians -ne $null -and $previousWindow.PitchRadians -ne $null) { Convert-RadiansToDegrees -Radians (Normalize-AngleRadians -Radians ([double]$currentWindow.PitchRadians - [double]$previousWindow.PitchRadians)) } else { $null }
        PreferredYawDeltaDegrees = if ($currentPreferred -and $previousPreferred -and $currentPreferred.YawRadians -ne $null -and $previousPreferred.YawRadians -ne $null) { Convert-RadiansToDegrees -Radians (Normalize-AngleRadians -Radians ([double]$currentPreferred.YawRadians - [double]$previousPreferred.YawRadians)) } else { $null }
        PreferredPitchDeltaDegrees = if ($currentPreferred -and $previousPreferred -and $currentPreferred.PitchRadians -ne $null -and $previousPreferred.PitchRadians -ne $null) { Convert-RadiansToDegrees -Radians (Normalize-AngleRadians -Radians ([double]$currentPreferred.PitchRadians - [double]$previousPreferred.PitchRadians)) } else { $null }
        CoordDeltaMagnitude = $coordDeltaMagnitude
    }
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

function Write-CameraStateText {
    param($Document)

    $cameraComparison = $Document.Comparisons | Where-Object { $_.Name -eq 'Preferred-vs-Camera' } | Select-Object -First 1
    $windowComparison = $Document.Comparisons | Where-Object { $_.Name -eq 'Preferred-vs-Window' } | Select-Object -First 1

    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add("Camera state capture")
    $lines.Add("Output file:                 $($Document.OutputFile)")
    $lines.Add("Generated (UTC):             $($Document.GeneratedAtUtc)")
    $lines.Add("Label:                       $(if ([string]::IsNullOrWhiteSpace([string]$Document.Label)) { 'n/a' } else { [string]$Document.Label })")
    $lines.Add("Config file:                 $($Document.ConfigFile)")
    $lines.Add("Config last write (UTC):     $($Document.ConfigLastWriteTimeUtc)")
    $lines.Add("Camera cfg yaw/pitch:        $(Format-Nullable $Document.Camera.YawRadians '0.000000') rad / $(Format-Nullable $Document.Camera.PitchRadians '0.000000') rad")
    $lines.Add("Camera cfg degrees:          $(Format-Nullable $Document.Camera.YawDegrees '0.000') deg / $(Format-Nullable $Document.Camera.PitchDegrees '0.000') deg")
    $lines.Add("Camera distance scale:       $(Format-Nullable $Document.Camera.DistanceScale '0.000000') (alt $(Format-Nullable $Document.Camera.DistanceScaleAlt '0.000000'))")
    $lines.Add("Window cfg yaw/pitch:        $(Format-Nullable $Document.Window.YawRadians '0.000000') rad / $(Format-Nullable $Document.Window.PitchRadians '0.000000') rad")
    $lines.Add("Window cfg degrees:          $(Format-Nullable $Document.Window.YawDegrees '0.000') deg / $(Format-Nullable $Document.Window.PitchDegrees '0.000') deg")
    $lines.Add("Video:                       $($Document.Video.ResolutionX)x$($Document.Video.ResolutionY) | renderer $($Document.Video.RendererMode) | window mode $($Document.Video.WindowMode)")
    $lines.Add("Player:                      $(if ($Document.ReaderOrientation.PlayerName) { $Document.ReaderOrientation.PlayerName } else { 'n/a' })")
    $lines.Add("Selected source:             $($Document.ReaderOrientation.SelectedSourceAddress)")
    $lines.Add("Preferred vector:            $(Format-Vector $Document.ReaderOrientation.PreferredEstimate.Vector)")
    $lines.Add("Preferred yaw/pitch:         $(Format-Nullable $Document.ReaderOrientation.PreferredEstimate.YawRadians '0.000000') rad / $(Format-Nullable $Document.ReaderOrientation.PreferredEstimate.PitchRadians '0.000000') rad")
    $lines.Add("Preferred degrees:           $(Format-Nullable $Document.ReaderOrientation.PreferredEstimate.YawDegrees '0.000') deg / $(Format-Nullable $Document.ReaderOrientation.PreferredEstimate.PitchDegrees '0.000') deg")

    if ($cameraComparison) {
        $lines.Add("Delta vs [Camera]:           yaw $(Format-Nullable $cameraComparison.DeltaYawDegrees '0.000') deg | pitch $(Format-Nullable $cameraComparison.DeltaPitchDegrees '0.000') deg")
    }

    if ($windowComparison) {
        $lines.Add("Delta vs [Window]:           yaw $(Format-Nullable $windowComparison.DeltaYawDegrees '0.000') deg | pitch $(Format-Nullable $windowComparison.DeltaPitchDegrees '0.000') deg")
    }

    if ($Document.ChangeFromPrevious) {
        $lines.Add("Prev capture:                $($Document.ChangeFromPrevious.PreviousFile)")
        $lines.Add("Prev deltas:                 cam yaw $(Format-Nullable $Document.ChangeFromPrevious.CameraYawDeltaDegrees '0.000') deg | cam pitch $(Format-Nullable $Document.ChangeFromPrevious.CameraPitchDeltaDegrees '0.000') deg | pref yaw $(Format-Nullable $Document.ChangeFromPrevious.PreferredYawDeltaDegrees '0.000') deg | pref pitch $(Format-Nullable $Document.ChangeFromPrevious.PreferredPitchDeltaDegrees '0.000') deg | coord Δ $(Format-Nullable $Document.ChangeFromPrevious.CoordDeltaMagnitude '0.000')")
    }

    if ($Document.Notes -and $Document.Notes.Count -gt 0) {
        $lines.Add("Notes:                       $([string]::Join('; ', $Document.Notes))")
    }

    return [string]::Join([Environment]::NewLine, $lines)
}

$resolvedConfigFile = [System.IO.Path]::GetFullPath($ConfigFile)
$resolvedOwnerComponentsFile = [System.IO.Path]::GetFullPath($OwnerComponentsFile)
$resolvedOutputFile = [System.IO.Path]::GetFullPath($OutputFile)
$resolvedPreviousFile = [System.IO.Path]::GetFullPath($PreviousFile)

if ($RefreshReaderBridge) {
    $refreshArguments = @{'NoReader' = $true}
    if ($NoAhkFallback) {
        $refreshArguments['NoAhkFallback'] = $true
    }

    & $refreshReaderBridgeScript @refreshArguments | Out-Null
}

if (-not $SkipOwnerRefresh -or -not (Test-Path -LiteralPath $resolvedOwnerComponentsFile)) {
    & $ownerComponentScript -OutputFile $resolvedOwnerComponentsFile -Json | Out-Null
}

$orientation = Invoke-ReaderJson -Arguments @(
    '--read-player-orientation',
    '--owner-components-file', $resolvedOwnerComponentsFile,
    '--json')

$ini = Read-IniDocument -Path $resolvedConfigFile
$configInfo = Get-Item -LiteralPath $resolvedConfigFile
$cameraYaw = Convert-ToNullableDouble (Get-IniValue -Document $ini -Section 'Camera' -Key 'yaw')
$cameraPitch = Convert-ToNullableDouble (Get-IniValue -Document $ini -Section 'Camera' -Key 'pitch')
$windowYaw = Convert-ToNullableDouble (Get-IniValue -Document $ini -Section 'Window' -Key 'yaw')
$windowPitch = Convert-ToNullableDouble (Get-IniValue -Document $ini -Section 'Window' -Key 'pitch')
$preferredEstimate = $orientation.PreferredEstimate

$comparisons = @()
if ($preferredEstimate -and $preferredEstimate.YawRadians -ne $null -and $preferredEstimate.PitchRadians -ne $null) {
    $comparisons += New-AngleComparison -Name 'Preferred-vs-Camera' -SourceYawRadians ([double]$preferredEstimate.YawRadians) -SourcePitchRadians ([double]$preferredEstimate.PitchRadians) -TargetYawRadians $cameraYaw -TargetPitchRadians $cameraPitch
    $comparisons += New-AngleComparison -Name 'Preferred-vs-Window' -SourceYawRadians ([double]$preferredEstimate.YawRadians) -SourcePitchRadians ([double]$preferredEstimate.PitchRadians) -TargetYawRadians $windowYaw -TargetPitchRadians $windowPitch
}

$notes = New-Object System.Collections.Generic.List[string]
$notes.Add('Reader orientation comes from the selected owner/source component and is most likely body or transform facing, not guaranteed live camera facing.')
$notes.Add('rift.cfg yaw/pitch values are persisted config values and may not update in real time.')

if ($orientation.Notes) {
    foreach ($note in $orientation.Notes) {
        $notes.Add([string]$note)
    }
}

$document = [pscustomobject]@{
    Mode = 'camera-state-capture'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
    Label = $Label
    ConfigFile = $resolvedConfigFile
    ConfigLastWriteTimeUtc = $configInfo.LastWriteTimeUtc.ToString('O')
    OutputFile = $resolvedOutputFile
    PreviousFile = $resolvedPreviousFile
    Camera = [pscustomobject]@{
        YawRadians = $cameraYaw
        YawDegrees = if ($cameraYaw -ne $null) { Convert-RadiansToDegrees -Radians $cameraYaw } else { $null }
        PitchRadians = $cameraPitch
        PitchDegrees = if ($cameraPitch -ne $null) { Convert-RadiansToDegrees -Radians $cameraPitch } else { $null }
        DistanceScale = Convert-ToNullableDouble (Get-IniValue -Document $ini -Section 'Camera' -Key 'distanceScale')
        DistanceScaleAlt = Convert-ToNullableDouble (Get-IniValue -Document $ini -Section 'Camera' -Key 'distanceScaleAlt')
        MaxDistanceScale = Convert-ToNullableDouble (Get-IniValue -Document $ini -Section 'Camera' -Key 'maxDistanceScale')
        MaxDistanceScaleAlt = Convert-ToNullableDouble (Get-IniValue -Document $ini -Section 'Camera' -Key 'maxDistanceScaleAlt')
        UseAltDistScale = Convert-ToNullableBool (Get-IniValue -Document $ini -Section 'Camera' -Key 'useAltDistScale')
    }
    Window = [pscustomobject]@{
        YawRadians = $windowYaw
        YawDegrees = if ($windowYaw -ne $null) { Convert-RadiansToDegrees -Radians $windowYaw } else { $null }
        PitchRadians = $windowPitch
        PitchDegrees = if ($windowPitch -ne $null) { Convert-RadiansToDegrees -Radians $windowPitch } else { $null }
        UseAltDistScale = Convert-ToNullableBool (Get-IniValue -Document $ini -Section 'Window' -Key 'useAltDistScale')
        TopX = Convert-ToNullableInt (Get-IniValue -Document $ini -Section 'Window' -Key 'TopX')
        TopY = Convert-ToNullableInt (Get-IniValue -Document $ini -Section 'Window' -Key 'TopY')
        Maximized = Convert-ToNullableBool (Get-IniValue -Document $ini -Section 'Window' -Key 'Maximized')
    }
    Video = [pscustomobject]@{
        ResolutionX = Convert-ToNullableInt (Get-IniValue -Document $ini -Section 'Video' -Key 'ResolutionX')
        ResolutionY = Convert-ToNullableInt (Get-IniValue -Document $ini -Section 'Video' -Key 'ResolutionY')
        RendererMode = Convert-ToNullableInt (Get-IniValue -Document $ini -Section 'Video' -Key 'RendererMode')
        WindowMode = Convert-ToNullableInt (Get-IniValue -Document $ini -Section 'Video' -Key 'WindowMode')
        ObjectDrawDistance = Convert-ToNullableInt (Get-IniValue -Document $ini -Section 'Video' -Key 'ObjectDrawDistance')
        TerrainDrawDistance = Convert-ToNullableInt (Get-IniValue -Document $ini -Section 'Video' -Key 'TerrainDrawDistance')
        Gamma = Convert-ToNullableDouble (Get-IniValue -Document $ini -Section 'Video' -Key 'Gamma')
    }
    ReaderOrientation = $orientation
    Comparisons = $comparisons
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

Write-Output (Write-CameraStateText -Document $document)
