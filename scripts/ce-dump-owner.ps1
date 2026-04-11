param([switch]$JsonOutput)

$lua = @"
local function dumpHex(address, size)
  local bytes = readBytes(address, size, true)
  local lines = {}
  for i=0,size-1,16 do
    local line = string.format('%08X:', address+i)
    local hex = ''
    local ascii = ''
    for j=0,15 do
      if i+j < size then
        local b = bytes[i+j]
        hex = hex .. string.format(' %02X', b)
        ascii = ascii .. (b>=32 and b<=126 and string.char(b) or '.')
      end
    end
    table.insert(lines, line .. '  ' .. hex .. '  ' .. ascii)
  end
  return table.concat(lines, '\n')
end

local function readPointer(address)
  return readInteger(address)
end

local function readFloat(address)
  return readFloat(address)
end

-- Find owner via known selected-source from previous session
-- Owner is typically at container+some offset from selected-source
local selectedSource = 0x1578D4F9910
if selectedSource == 0 then
  print('ERROR: No selected-source')
  return
end

print('Selected source: ' .. string.format('0x%X', selectedSource))

-- Try to find owner by backward scanning from selected-source
local owner = nil
for offset = -0x1000, 0, 4 do
  local candidate = selectedSource + offset
  local vtable = readPointer(candidate)
  if vtable > 0x7FF000000000 and vtable < 0x7FFFFFFFFFF then
    local firstPtr = readPointer(candidate + 8)
    if firstPtr == selectedSource then
      owner = candidate
      break
    end
  end
end

if owner then
  print('Owner found: ' .. string.format('0x%X', owner))
  print(dumpHex(owner, 256))
else
  print('Owner not found - scanning for container')
  -- Alternative: scan for container near selected-source
  for offset = 0, 0x2000, 8 do
    local candidate = selectedSource + offset
    local ptr = readPointer(candidate)
    if ptr > 0x157000000000 and ptr < 0x157900000000 then
      local entries = readPointer(candidate)
      local count = readInteger(candidate + 8)
      if count > 0 and count < 32 then
        print('Container candidate at +' .. offset .. ': ' .. string.format('0x%X', ptr) .. ' count=' .. count)
      end
    end
  end
end
"@

& $PSScriptRoot\cheatengine-exec.ps1 -Code $lua