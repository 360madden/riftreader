$outputFile = "$env:TEMP\ce_container.txt"

$lua = @"
local function readPtr(a) return readInteger(a) end
local function readFloat(a) return readFloat(a) end
local function readInt(a) return readInteger(a) end

local selectedSource = 0x1578D4F9910
local outFile = 'C:\\Users\\mrkoo\\AppData\\Local\\Temp\\ce_container.txt'

-- Scan backward from selected-source looking for container structure
for offset = -0x500, -8, -8 do
  local candidate = selectedSource + offset
  local entriesPtr = readPtr(candidate)
  local count = readInt(candidate + 8)
  local cap = readInt(candidate + 16)
  
  if count > 0 and count <= 32 and cap >= count then
    if entriesPtr > 0x150000000000 then
      local f = io.open(outFile, 'w')
      f:write('Container:0x' .. string.format('%X', entriesPtr) .. ' count=' .. count .. '\n')
      for i = 0, count - 1 do
        local entryAddr = entriesPtr + i * 8
        local entry = readPtr(entryAddr)
        if entry > 0x150000000000 then
          f:write(string.format('Entry[%d]=0x%X\n', i, entry))
        end
      end
      f:close()
      print('Wrote to ' .. outFile)
      return
    end
  end
end

print('Not found')
"@

& $PSScriptRoot\cheatengine-exec.ps1 -Code $lua

Start-Sleep -Milliseconds 500

if (Test-Path $outputFile) {
    Get-Content $outputFile
} else {
    Write-Host "Output file not found"
}