[CmdletBinding()]
param(
    [switch]$Json,
    [switch]$RefreshOwnerComponents,
    [string]$ProcessName = 'rift_x64',
    [string]$OwnerComponentsFile = (Join-Path $PSScriptRoot 'captures\player-owner-components.json')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$captureOrientationScript = Join-Path $PSScriptRoot 'capture-actor-orientation.ps1'

function Convert-CommandOutputToJson {
    param(
        [Parameter(Mandatory = $true)]
        [object[]]$OutputLines,
        [string]$CommandName = 'command'
    )

    $text = ($OutputLines |
        ForEach-Object { $_.ToString() } |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) }) -join [Environment]::NewLine

    $startIndex = $text.IndexOf('{')
    if ($startIndex -lt 0) {
        throw "$CommandName did not return JSON. Raw output: $text"
    }

    return ($text.Substring($startIndex) | ConvertFrom-Json -Depth 50)
}

function Parse-HexUInt64 {
    param([Parameter(Mandatory = $true)][string]$Value)

    $normalized = $Value.Trim()
    if ($normalized.StartsWith('0x', [System.StringComparison]::OrdinalIgnoreCase)) {
        $normalized = $normalized.Substring(2)
    }

    return [UInt64]::Parse($normalized, [System.Globalization.NumberStyles]::HexNumber, [System.Globalization.CultureInfo]::InvariantCulture)
}

function Read-MemoryBlock {
    param(
        [Parameter(Mandatory = $true)][string]$Address,
        [Parameter(Mandatory = $true)][int]$Length
    )

    $output = & dotnet run --project $readerProject --configuration Release -- `
        --process-name $ProcessName --address $Address --length $Length --json 2>&1
    $data = Convert-CommandOutputToJson -OutputLines $output -CommandName "memory read $Address"

    if (-not $data.PSObject.Properties['BytesHex']) {
        throw "Reader JSON for $Address did not include BytesHex."
    }

    $hex = ([string]$data.BytesHex -replace '\s+', '').Trim()
    if ([string]::IsNullOrWhiteSpace($hex)) {
        throw "Reader JSON for $Address returned empty BytesHex."
    }

    $bytes = New-Object byte[] ($hex.Length / 2)
    for ($index = 0; $index -lt $bytes.Length; $index++) {
        $bytes[$index] = [Convert]::ToByte($hex.Substring($index * 2, 2), 16)
    }

    return $bytes
}

function Get-EntryByIndex {
    param(
        [Parameter(Mandatory = $true)]$OwnerComponents,
        [Parameter(Mandatory = $true)][int]$Index
    )

    return $OwnerComponents.Entries | Where-Object { [int]$_.Index -eq $Index } | Select-Object -First 1
}

function Read-Entry15CameraCoord {
    param([Parameter(Mandatory = $true)][string]$Entry15Address)

    $entryBase = Parse-HexUInt64 -Value $Entry15Address
    $coordBytes = Read-MemoryBlock -Address ('0x{0:X}' -f ($entryBase + 0xA8)) -Length 24

    return [pscustomobject]@{
        Primary = [pscustomobject]@{
            X = [BitConverter]::ToSingle($coordBytes, 0)
            Y = [BitConverter]::ToSingle($coordBytes, 4)
            Z = [BitConverter]::ToSingle($coordBytes, 8)
        }
        Duplicate = [pscustomobject]@{
            X = [BitConverter]::ToSingle($coordBytes, 12)
            Y = [BitConverter]::ToSingle($coordBytes, 16)
            Z = [BitConverter]::ToSingle($coordBytes, 20)
        }
    }
}

function Get-MaxCoordDelta {
    param(
        [Parameter(Mandatory = $true)]$Primary,
        [Parameter(Mandatory = $true)]$Duplicate
    )

    $deltas = @(
        [Math]::Abs(([double]$Primary.X) - ([double]$Duplicate.X)),
        [Math]::Abs(([double]$Primary.Y) - ([double]$Duplicate.Y)),
        [Math]::Abs(([double]$Primary.Z) - ([double]$Duplicate.Z))
    )

    return ($deltas | Measure-Object -Maximum).Maximum
}

function Get-RelativeVectorAnalysis {
    param(
        [Parameter(Mandatory = $true)]$PlayerCoord,
        [Parameter(Mandatory = $true)]$CameraCoord
    )

    $dx = [double]$CameraCoord.X - [double]$PlayerCoord.X
    $dy = [double]$CameraCoord.Y - [double]$PlayerCoord.Y
    $dz = [double]$CameraCoord.Z - [double]$PlayerCoord.Z
    $horizontal = [Math]::Sqrt(($dx * $dx) + ($dz * $dz))

    return [pscustomobject]@{
        Dx = $dx
        Dy = $dy
        Dz = $dz
        HorizontalDistance = $horizontal
        Distance = [Math]::Sqrt(($dx * $dx) + ($dy * $dy) + ($dz * $dz))
        DerivedPitchDegrees = [Math]::Atan2($dy, $horizontal) * 180.0 / [Math]::PI
        DerivedYawDegreesFromOrbit = [Math]::Atan2($dz, $dx) * 180.0 / [Math]::PI
    }
}

function Invoke-OrientationCapture {
    if ($RefreshOwnerComponents) {
        $output = & $captureOrientationScript -Json -RefreshOwnerComponents 2>&1
    }
    else {
        $output = & $captureOrientationScript -Json 2>&1
    }

    if ($LASTEXITCODE -ne 0) {
        throw "capture-actor-orientation failed: $($output -join [Environment]::NewLine)"
    }

    return Convert-CommandOutputToJson -OutputLines $output -CommandName 'capture-actor-orientation'
}

$orientationCapture = Invoke-OrientationCapture
$ownerComponents = Get-Content -LiteralPath $OwnerComponentsFile -Raw | ConvertFrom-Json -Depth 40
$entry15 = Get-EntryByIndex -OwnerComponents $ownerComponents -Index 15
if ($null -eq $entry15) {
    throw 'Entry 15 was not present in the current owner-components capture.'
}

$entry15Camera = Read-Entry15CameraCoord -Entry15Address ([string]$entry15.Address)
$entry15DuplicateMaxDelta = Get-MaxCoordDelta -Primary $entry15Camera.Primary -Duplicate $entry15Camera.Duplicate
$relative = Get-RelativeVectorAnalysis -PlayerCoord $orientationCapture.ReaderOrientation.PlayerCoord -CameraCoord $entry15Camera.Primary

$document = [ordered]@{
    Mode = 'live-camera-yaw-pitch'
    GeneratedAtUtc = [DateTime]::UtcNow.ToString('o')
    ProcessName = $ProcessName
    OwnerComponentsFile = $OwnerComponentsFile
    SelectedSourceAddress = $orientationCapture.ReaderOrientation.SelectedSourceAddress
    SelectedEntryIndex = $orientationCapture.ReaderOrientation.SelectedEntryIndex
    PreferredYawSource = [ordered]@{
        Name = $orientationCapture.ReaderOrientation.PreferredEstimate.Name
        YawDegrees = $orientationCapture.ReaderOrientation.PreferredEstimate.YawDegrees
        PitchDegrees = $orientationCapture.ReaderOrientation.PreferredEstimate.PitchDegrees
        Vector = $orientationCapture.ReaderOrientation.PreferredEstimate.Vector
    }
    PlayerCoord = $orientationCapture.ReaderOrientation.PlayerCoord
    CameraOrbitSource = [ordered]@{
        EntryIndex = 15
        EntryAddress = $entry15.Address
        CoordPrimary = $entry15Camera.Primary
        CoordDuplicate = $entry15Camera.Duplicate
        DuplicateMaxDelta = $entry15DuplicateMaxDelta
        RelativeVector = $relative
    }
    Notes = @(
        'Yaw is read directly from the selected-source preferred orientation basis.'
        'Pitch is derived from entry15 duplicated camera-orbit coordinates relative to player coordinates.'
        'Preferred yaw source pitch remains flat in live tests; entry15 orbit coordinates are the stronger live pitch signal.'
    )
}

if ($Json) {
    $document | ConvertTo-Json -Depth 20
}
else {
    @(
        "Live camera yaw/pitch"
        "Selected source:           $($document.SelectedSourceAddress)"
        "Preferred yaw source:      $($document.PreferredYawSource.Name)"
        ("Actor yaw / pitch (deg):   {0:N3} / {1:N3}" -f ([double]$document.PreferredYawSource.YawDegrees), ([double]$document.PreferredYawSource.PitchDegrees))
        "Entry15 camera address:    $($document.CameraOrbitSource.EntryAddress)"
        ("Entry15 duplicate delta:   {0:N6}" -f ([double]$document.CameraOrbitSource.DuplicateMaxDelta))
        ("Derived camera pitch (deg): {0:N3}" -f ([double]$document.CameraOrbitSource.RelativeVector.DerivedPitchDegrees))
        ("Derived orbit yaw (deg):    {0:N3}" -f ([double]$document.CameraOrbitSource.RelativeVector.DerivedYawDegreesFromOrbit))
        ("Camera distance:            {0:N3}" -f ([double]$document.CameraOrbitSource.RelativeVector.Distance))
    ) -join [Environment]::NewLine
}
