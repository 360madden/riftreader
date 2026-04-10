[CmdletBinding()]
param(
    [string]$SelectedSourceAddress = '0x1AEF0941250',
    [switch]$Json,
    [string]$OutputFile
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Parse the component address
$address = if ($SelectedSourceAddress -match '^0x([0-9A-Fa-f]+)$') {
    [UInt64]::Parse($Matches[1], [System.Globalization.NumberStyles]::HexNumber)
}
else {
    [UInt64]::Parse($SelectedSourceAddress, [System.Globalization.NumberStyles]::HexNumber)
}

# Camera likely resides after the actor basis matrix
# Known actor offsets: +0x60 (forward), +0x6C (up), +0x78 (right) = 12 bytes each = 36 bytes
# Duplicate basis: +0x94 (forward), +0xA0 (up), +0xAC (right) = 36 bytes
# Last actor basis ends at +0xB8 (+0xAC + 12)
# Camera search range: +0xB8 to +0x150 (88 bytes = 22 float32s or 11 float64s)

$cameraRangeStart = $address + 0xB8
$cameraRangeEnd = $address + 0x150
$cameraRangeSize = 0x150 - 0xB8

$ceScript = @"
-- Generated Camera Orientation Probe
-- Component Address: $SelectedSourceAddress
-- Camera search range: +0xB8 to +0x150 (88 bytes)
-- Expected candidates: camera forward vector (triplet), camera yaw/pitch, camera distance

function hexToDecimal(hex)
  return tonumber(hex, 16)
end

function decimalToHex(dec)
  return string.format('0x%X', dec)
end

-- Component address
local componentAddr = hexToDecimal('$([string]::Format("{0:X}", $address))')
print('Component address: ' .. decimalToHex(componentAddr))

-- Camera search region
local cameraStart = componentAddr + 0xB8
local cameraSize = 0x150 - 0xB8
print('Camera search region: ' .. decimalToHex(cameraStart) .. ' (88 bytes)')

-- Helper to read float32
function readFloat32(address)
  local bytes = readString(address, 4)
  if not bytes or #bytes < 4 then return nil end
  -- Convert bytes to float (little-endian)
  local b1, b2, b3, b4 = string.byte(bytes, 1, 4)
  local int32 = b1 + (b2 * 256) + (b3 * 65536) + (b4 * 16777216)
  if int32 >= 2147483648 then int32 = int32 - 4294967296 end
  local sign = (int32 < 0) and -1 or 1
  local exponent = math.floor(int32 / 8388608) % 256
  local mantissa = int32 % 8388608
  if exponent == 0 then return 0 end
  return sign * math.ldexp(1.0 + mantissa / 8388608, exponent - 127)
end

-- Helper to read triplet as 3 float32s
function readVectorTriplet(address)
  local x = readFloat32(address)
  local y = readFloat32(address + 4)
  local z = readFloat32(address + 8)
  if x and y and z then
    return { x = x, y = y, z = z }
  end
  return nil
end

-- Scan for camera candidates
print('\\nScanning for camera candidates...')

local candidates = {}
local offset = 0
while offset < cameraSize - 12 do
  local addr = cameraStart + offset
  local vec = readVectorTriplet(addr)
  if vec then
    local magnitude = math.sqrt(vec.x * vec.x + vec.y * vec.y + vec.z * vec.z)
    -- Camera forward vector should be normalized (~1.0)
    if magnitude > 0.8 and magnitude < 1.2 then
      table.insert(candidates, {
        offset = offset,
        address = addr,
        magnitude = magnitude,
        x = vec.x,
        y = vec.y,
        z = vec.z,
        type = 'possible-camera-vector'
      })
    end
    -- Camera distance scalar (5-100 units)
    local scalar = vec.x
    if scalar > 5 and scalar < 100 then
      table.insert(candidates, {
        offset = offset,
        address = addr,
        value = scalar,
        type = 'possible-camera-distance'
      })
    end
  end
  offset = offset + 4
end

print(string.format('Found %d candidates\\n', #candidates))

for i, candidate in ipairs(candidates) do
  if candidate.type == 'possible-camera-vector' then
    print(string.format('[%d] Offset +0x%X (addr %s): vector (%.3f, %.3f, %.3f), mag=%.3f',
      i, candidate.offset, decimalToHex(candidate.address), candidate.x, candidate.y, candidate.z, candidate.magnitude))
  elseif candidate.type == 'possible-camera-distance' then
    print(string.format('[%d] Offset +0x%X (addr %s): scalar=%.3f (possible distance)',
      i, candidate.offset, decimalToHex(candidate.address), candidate.value))
  end
end

print('\\nRecommendation: Use stimulus test to narrow candidates')
"@

$output = [ordered]@{
    Mode = 'generate-camera-probe'
    GeneratedAtUtc = [System.DateTime]::UtcNow.ToString('o')
    SelectedSourceAddress = $SelectedSourceAddress
    ComponentAddress = [string]::Format('0x{0:X}', $address)
    CameraSearchRange = @{
        Start = [string]::Format('0x{0:X}', $cameraRangeStart)
        End = [string]::Format('0x{0:X}', $cameraRangeEnd)
        SizeBytes = $cameraRangeSize
    }
    CheatEngineScript = $ceScript
    Notes = @(
        'Camera likely stored after actor basis matrix (+0xB8 onwards)'
        'Search for: normalized vectors (mag ~1.0), scalars (5-100 units)'
        'Use stimulus test to validate candidates against mouse input'
    )
}

if ($OutputFile) {
    $output | ConvertTo-Json -Depth 20 | Out-File -FilePath $OutputFile -Encoding UTF8
    Write-Host "Probe generated: $OutputFile" -ForegroundColor Green
    Write-Host "CheatEngine script location: $OutputFile (extract from JSON)" -ForegroundColor Yellow
}

if ($Json) {
    $output | ConvertTo-Json -Depth 20
}
else {
    $output | Format-List
    Write-Host "`n=== CheatEngine Script ===" -ForegroundColor Cyan
    Write-Host $ceScript
}
