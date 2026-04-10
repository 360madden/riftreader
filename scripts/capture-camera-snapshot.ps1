[CmdletBinding()]
param(
    [string]$Label = '',
    [string]$OutputFile,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$readerProject = Join-Path $PSScriptRoot '..' 'reader' 'RiftReader.Reader' 'RiftReader.Reader.csproj'

# Step 1: Get component address from orientation reader
$orientJson = & dotnet run --project $readerProject --configuration Release -- --read-player-orientation --json 2>&1
$orient = $orientJson | ConvertFrom-Json -Depth 30

$componentAddr = $orient.SelectedSourceAddress
$componentUint = [UInt64]::Parse($componentAddr.TrimStart('0x'), [System.Globalization.NumberStyles]::HexNumber)

# Step 2: Read 2048 bytes from component
$dumpJson = & dotnet run --project $readerProject --configuration Release -- --process-name rift_x64 --address $componentAddr --length 2048 --json 2>&1
$dump = $dumpJson | ConvertFrom-Json -Depth 30

$hex = $dump.BytesHex -replace ' ', ''
$bytes = [byte[]]::new($hex.Length / 2)
for ($i = 0; $i -lt $bytes.Length; $i++) {
    $bytes[$i] = [Convert]::ToByte($hex.Substring($i * 2, 2), 16)
}

function Read-Float($offset) {
    if ($offset + 4 -le $bytes.Length) {
        return [BitConverter]::ToSingle($bytes, $offset)
    }
    return [float]::NaN
}

function Read-Vector3($offset) {
    return [ordered]@{
        X = Read-Float $offset
        Y = Read-Float ($offset + 4)
        Z = Read-Float ($offset + 8)
    }
}

function Get-VectorMagnitude($v) {
    return [Math]::Sqrt([double]$v.X * [double]$v.X + [double]$v.Y * [double]$v.Y + [double]$v.Z * [double]$v.Z)
}

# Step 3: Extract known actor data
$actorCoord48 = Read-Vector3 0x48
$actorCoord88 = Read-Vector3 0x88
$actorForward60 = Read-Vector3 0x60
$actorForward94 = Read-Vector3 0x94

# Step 4: Extract camera candidates
$cameraPosition = Read-Vector3 0xE4
$cameraCoordD8 = Read-Vector3 0xD8

# Camera basis at +0x7D0
$cameraBasisForward = Read-Vector3 0x7D0
$cameraBasisUp = Read-Vector3 0x7DC
$cameraBasisRight = Read-Vector3 0x7E8

# Step 5: Compute yaw/pitch
$actorYawRad = [Math]::Atan2([double]$actorForward60.Z, [double]$actorForward60.X)
$actorPitchRad = [Math]::Atan2([double]$actorForward60.Y, [Math]::Sqrt([double]$actorForward60.X * [double]$actorForward60.X + [double]$actorForward60.Z * [double]$actorForward60.Z))

$cameraYawRad = [Math]::Atan2([double]$cameraBasisForward.Z, [double]$cameraBasisForward.X)
$cameraPitchRad = [Math]::Atan2([double]$cameraBasisForward.Y, [Math]::Sqrt([double]$cameraBasisForward.X * [double]$cameraBasisForward.X + [double]$cameraBasisForward.Z * [double]$cameraBasisForward.Z))

$actorYawDeg = $actorYawRad * 180.0 / [Math]::PI
$actorPitchDeg = $actorPitchRad * 180.0 / [Math]::PI
$cameraYawDeg = $cameraYawRad * 180.0 / [Math]::PI
$cameraPitchDeg = $cameraPitchRad * 180.0 / [Math]::PI

# Camera-to-player distance
$dx = [double]$cameraPosition.X - [double]$actorCoord48.X
$dy = [double]$cameraPosition.Y - [double]$actorCoord48.Y
$dz = [double]$cameraPosition.Z - [double]$actorCoord48.Z
$cameraDistance = [Math]::Sqrt($dx * $dx + $dy * $dy + $dz * $dz)

# Basis determinant
$f = $cameraBasisForward; $u = $cameraBasisUp; $r = $cameraBasisRight
$det = [double]$f.X * ([double]$u.Y * [double]$r.Z - [double]$u.Z * [double]$r.Y) - [double]$f.Y * ([double]$u.X * [double]$r.Z - [double]$u.Z * [double]$r.X) + [double]$f.Z * ([double]$u.X * [double]$r.Y - [double]$u.Y * [double]$r.X)

# Also check for a second possible camera basis at +0x7A0
$cameraBasis2Forward = Read-Vector3 0x7A0
$cameraBasis2Up = Read-Vector3 0x7AC
$cameraBasis2Right = Read-Vector3 0x7B8

$result = [ordered]@{
    Mode = 'camera-orientation-snapshot'
    GeneratedAtUtc = [DateTime]::UtcNow.ToString('o')
    Label = $Label
    ComponentAddress = $componentAddr
    ActorCoord = $actorCoord48
    ActorForward = $actorForward60
    ActorYaw = [ordered]@{ Degrees = [Math]::Round($actorYawDeg, 4); Radians = [Math]::Round($actorYawRad, 6) }
    ActorPitch = [ordered]@{ Degrees = [Math]::Round($actorPitchDeg, 4); Radians = [Math]::Round($actorPitchRad, 6) }
    CameraPosition = $cameraPosition
    CameraDistance = [Math]::Round($cameraDistance, 3)
    CameraHeightOffset = [Math]::Round($dy, 3)
    CameraBasisForward = $cameraBasisForward
    CameraBasisUp = $cameraBasisUp
    CameraBasisRight = $cameraBasisRight
    CameraBasisDeterminant = [Math]::Round($det, 6)
    CameraYaw = [ordered]@{ Degrees = [Math]::Round($cameraYawDeg, 4); Radians = [Math]::Round($cameraYawRad, 6) }
    CameraPitch = [ordered]@{ Degrees = [Math]::Round($cameraPitchDeg, 4); Radians = [Math]::Round($cameraPitchRad, 6) }
    CameraActorYawDelta = [Math]::Round($cameraYawDeg - $actorYawDeg, 4)
    CameraBasis2Forward = $cameraBasis2Forward
    CameraBasis2Up = $cameraBasis2Up
    CameraBasis2Right = $cameraBasis2Right
    Offsets = [ordered]@{
        ActorCoord48 = '+0x048'
        ActorCoord88 = '+0x088'
        ActorForward60 = '+0x060'
        ActorForward94 = '+0x094'
        CameraCoordD8 = '+0x0D8'
        CameraPosition = '+0x0E4'
        CameraBasisForward = '+0x7D0'
        CameraBasisUp = '+0x7DC'
        CameraBasisRight = '+0x7E8'
    }
}

if (-not $Json) {
    Write-Host '=== Camera Orientation Snapshot ===' -ForegroundColor Cyan
    Write-Host "Component: $componentAddr" -ForegroundColor Green
    Write-Host "Label: $Label" -ForegroundColor Green
    Write-Host ''
    Write-Host "Actor Position:  $([Math]::Round($actorCoord48.X, 2)), $([Math]::Round($actorCoord48.Y, 2)), $([Math]::Round($actorCoord48.Z, 2))"
    Write-Host "Camera Position: $([Math]::Round($cameraPosition.X, 2)), $([Math]::Round($cameraPosition.Y, 2)), $([Math]::Round($cameraPosition.Z, 2))"
    Write-Host "Camera Distance: $([Math]::Round($cameraDistance, 2)) units"
    Write-Host "Camera Height:   +$([Math]::Round($dy, 2)) units above player"
    Write-Host ''
    Write-Host "Actor Yaw:  $([Math]::Round($actorYawDeg, 2)) deg"
    Write-Host "Camera Yaw: $([Math]::Round($cameraYawDeg, 2)) deg"
    Write-Host "Yaw Delta:  $([Math]::Round($cameraYawDeg - $actorYawDeg, 2)) deg"
    Write-Host ''
    Write-Host "Actor Pitch:  $([Math]::Round($actorPitchDeg, 2)) deg"
    Write-Host "Camera Pitch: $([Math]::Round($cameraPitchDeg, 2)) deg"
    Write-Host ''
    Write-Host "Basis Determinant: $([Math]::Round($det, 6)) (should be ~1.0)"
}

if ($OutputFile) {
    $result | ConvertTo-Json -Depth 20 | Out-File -FilePath $OutputFile -Encoding UTF8
    Write-Host "Saved to: $OutputFile" -ForegroundColor Green
}

if ($Json) {
    $result | ConvertTo-Json -Depth 20
}
