local addonInfo, privateVars = ...
privateVars = privateVars or {}

local addonIdentifier = (addonInfo and addonInfo.identifier) or "RiftReaderApiProbe"
local addonVersion = "0.1.0"

local Probe = {}
privateVars.Probe = Probe

local function console(message, color)
  local text = tostring(message or "")
  local prefix = "<font color='" .. tostring(color or "#66CCFF") .. "'>[ApiProbe]</font> "
  Command.Console.Display("general", true, prefix .. text, true)
end

local function safeCall(fn, ...)
  if type(fn) ~= "function" then
    return nil
  end
  local ok, a, b, c, d = pcall(fn, ...)
  if not ok then
    return nil
  end
  return a, b, c, d
end

local function inspectTable(tbl, indent, maxDepth)
  if type(tbl) ~= "table" then
    return tostring(tbl)
  end
  if maxDepth <= 0 then
    return "{...}"
  end
  indent = indent or ""
  local lines = {}
  local count = 0
  for k, v in pairs(tbl) do
    count = count + 1
    if count > 50 then
      table.insert(lines, indent .. "  ... (truncated)")
      break
    end
    local keyStr = type(k) == "string" and k or tostring(k)
    if type(v) == "table" then
      table.insert(lines, indent .. "  " .. keyStr .. " = " .. inspectTable(v, indent .. "  ", maxDepth - 1))
    else
      local valStr = type(v) == "string" and '"' .. v .. '"' or tostring(v)
      table.insert(lines, indent .. "  " .. keyStr .. " = " .. valStr)
    end
  end
  if #lines == 0 then
    return "{}"
  end
  return "{\n" .. table.concat(lines, "\n") .. "\n" .. indent .. "}"
end

local function probeInspectUnitDetail()
  console("=== Probing Inspect.Unit.Detail ===", "#FFFF00")
  
  local playerId = safeCall(Inspect.Unit.Lookup, "player")
  if not playerId then
    console("Inspect.Unit.Lookup('player') returned nil", "#FF4444")
    return
  end
  console("Player unit ID: " .. tostring(playerId), "#00FF88")
  
  local detail = safeCall(Inspect.Unit.Detail, playerId)
  if type(detail) ~= "table" then
    console("Inspect.Unit.Detail returned: " .. type(detail), "#FF4444")
    return
  end
  
  console("Inspect.Unit.Detail fields:", "#00FF88")
  local sortedKeys = {}
  for k in pairs(detail) do
    table.insert(sortedKeys, k)
  end
  table.sort(sortedKeys, function(a, b) return tostring(a) < tostring(b) end)
  
  for _, k in ipairs(sortedKeys) do
    local v = detail[k]
    local typeStr = type(v)
    local valStr
    if typeStr == "table" then
      valStr = "(table)"
    elseif typeStr == "string" then
      valStr = '"' .. v .. '"'
    elseif typeStr == "boolean" then
      valStr = v and "true" or "false"
    elseif typeStr == "number" then
      valStr = string.format("%.4f", v)
    else
      valStr = tostring(v)
    end
    console(string.format("  .%s [%s] = %s", tostring(k), typeStr, valStr), "#CCCCCC")
  end
end

local function probeInspectStat()
  console("=== Probing Inspect.Stat ===", "#FFFF00")
  
  local stats = safeCall(Inspect.Stat)
  if type(stats) ~= "table" then
    console("Inspect.Stat returned: " .. type(stats), "#FF4444")
    return
  end
  
  console("Inspect.Stat fields:", "#00FF88")
  local sortedKeys = {}
  for k in pairs(stats) do
    table.insert(sortedKeys, k)
  end
  table.sort(sortedKeys, function(a, b) return tostring(a) < tostring(b) end)
  
  for _, k in ipairs(sortedKeys) do
    local v = stats[k]
    local typeStr = type(v)
    local valStr
    if typeStr == "number" then
      valStr = string.format("%.4f", v)
    else
      valStr = tostring(v)
    end
    console(string.format("  .%s [%s] = %s", tostring(k), typeStr, valStr), "#CCCCCC")
  end
end

local function probeInspectUnitCastbar()
  console("=== Probing Inspect.Unit.Castbar ===", "#FFFF00")
  
  local playerId = safeCall(Inspect.Unit.Lookup, "player")
  if not playerId then
    console("Player not available", "#FF4444")
    return
  end
  
  local castbar = safeCall(Inspect.Unit.Castbar, playerId)
  if castbar == nil then
    console("Inspect.Unit.Castbar returned nil (no active cast)", "#FFAA00")
    return
  end
  if type(castbar) ~= "table" then
    console("Inspect.Unit.Castbar returned: " .. type(castbar), "#FF4444")
    return
  end
  
  console("Inspect.Unit.Castbar fields:", "#00FF88")
  local sortedKeys = {}
  for k in pairs(castbar) do
    table.insert(sortedKeys, k)
  end
  table.sort(sortedKeys, function(a, b) return tostring(a) < tostring(b) end)
  
  for _, k in ipairs(sortedKeys) do
    local v = castbar[k]
    local typeStr = type(v)
    local valStr
    if typeStr == "table" then
      valStr = "(table)"
    elseif typeStr == "string" then
      valStr = '"' .. v .. '"'
    elseif typeStr == "boolean" then
      valStr = v and "true" or "false"
    elseif typeStr == "number" then
      valStr = string.format("%.4f", v)
    else
      valStr = tostring(v)
    end
    console(string.format("  .%s [%s] = %s", tostring(k), typeStr, valStr), "#CCCCCC")
  end
end

local function probeInspectBuffList()
  console("=== Probing Inspect.Buff.List ===", "#FFFF00")
  
  local playerId = safeCall(Inspect.Unit.Lookup, "player")
  if not playerId then
    console("Player not available", "#FF4444")
    return
  end
  
  local buffIds = safeCall(Inspect.Buff.List, playerId)
  if type(buffIds) ~= "table" then
    console("Inspect.Buff.List returned: " .. type(buffIds), "#FF4444")
    return
  end
  
  local buffCount = 0
  for _ in pairs(buffIds) do
    buffCount = buffCount + 1
  end
  console("Buff count: " .. tostring(buffCount), "#00FF88")
  
  if buffCount > 0 then
    local firstBuffId = next(buffIds)
    if firstBuffId then
      local buffDetail = safeCall(Inspect.Buff.Detail, playerId, buffIds)
      if type(buffDetail) == "table" then
        console("First buff structure:", "#00FF88")
        for k, v in pairs(buffDetail) do
          if type(v) == "table" then
            for k2, v2 in pairs(v) do
              local typeStr = type(v2)
              local valStr = typeStr == "string" and '"' .. v2 .. '"' or tostring(v2)
              console(string.format("  [%s].%s [%s] = %s", tostring(k), tostring(k2), typeStr, valStr), "#CCCCCC")
            end
            break
          end
        end
      end
    end
  end
end

local function probeInspectUnitList()
  console("=== Probing Inspect.Unit.List ===", "#FFFF00")
  
  local unitList = safeCall(Inspect.Unit.List)
  if type(unitList) ~= "table" then
    console("Inspect.Unit.List returned: " .. type(unitList), "#FF4444")
    return
  end
  
  local unitCount = 0
  local firstUnitId = nil
  for uid, _ in pairs(unitList) do
    unitCount = unitCount + 1
    if not firstUnitId then
      firstUnitId = uid
    end
  end
  console("Unit list count: " .. tostring(unitCount), "#00FF88")
  
  if firstUnitId then
    console("Sample unit ID: " .. tostring(firstUnitId), "#CCCCCC")
    local detail = safeCall(Inspect.Unit.Detail, firstUnitId)
    if type(detail) == "table" then
      console("Sample unit has .name: " .. tostring(detail.name), "#CCCCCC")
      console("Sample unit has .level: " .. tostring(detail.level), "#CCCCCC")
    end
  end
end

local function probeInspectSystemSecure()
  console("=== Probing Inspect.System.Secure ===", "#FFFF00")
  
  local isSecure = safeCall(Inspect.System.Secure)
  console("Inspect.System.Secure() = " .. tostring(isSecure), isSecure and "#FF4444" or "#00FF88")
end

local function probeInspectMouse()
  console("=== Probing Inspect.Mouse ===", "#FFFF00")
  
  local mouse = safeCall(Inspect.Mouse)
  if type(mouse) ~= "table" then
    console("Inspect.Mouse returned: " .. type(mouse), "#FF4444")
    return
  end
  
  console("Inspect.Mouse fields:", "#00FF88")
  for k, v in pairs(mouse) do
    console(string.format("  .%s = %s", tostring(k), tostring(v)), "#CCCCCC")
  end
end

local function probeInspectTime()
  console("=== Probing Inspect.Time ===", "#FFFF00")
  
  if Inspect.Time and Inspect.Time.Real then
    local timeVal = safeCall(Inspect.Time.Real)
    console("Inspect.Time.Real() = " .. tostring(timeVal), "#00FF88")
  else
    console("Inspect.Time.Real not available", "#FF4444")
  end
end

function Probe.OnSlashCommand(args)
  local command = string.match(args or "", "^(%S+)")
  if command then
    command = string.lower(command)
  end
  
  if not command or command == "help" then
    console("Commands:", "#FFFF00")
    console("  /rap detail     - Probe Inspect.Unit.Detail", "#CCCCCC")
    console("  /rap stat       - Probe Inspect.Stat", "#CCCCCC")
    console("  /rap castbar    - Probe Inspect.Unit.Castbar", "#CCCCCC")
    console("  /rap buff       - Probe Inspect.Buff.List", "#CCCCCC")
    console("  /rap unitlist   - Probe Inspect.Unit.List", "#CCCCCC")
    console("  /rap secure     - Probe Inspect.System.Secure", "#CCCCCC")
    console("  /rap mouse      - Probe Inspect.Mouse", "#CCCCCC")
    console("  /rap time       - Probe Inspect.Time.Real", "#CCCCCC")
    console("  /rap all        - Run all probes", "#CCCCCC")
    return
  end
  
  if command == "detail" then
    probeInspectUnitDetail()
    return
  end
  
  if command == "stat" then
    probeInspectStat()
    return
  end
  
  if command == "castbar" then
    probeInspectUnitCastbar()
    return
  end
  
  if command == "buff" then
    probeInspectBuffList()
    return
  end
  
  if command == "unitlist" then
    probeInspectUnitList()
    return
  end
  
  if command == "secure" then
    probeInspectSystemSecure()
    return
  end
  
  if command == "mouse" then
    probeInspectMouse()
    return
  end
  
  if command == "time" then
    probeInspectTime()
    return
  end
  
  if command == "all" then
    probeInspectTime()
    probeInspectSystemSecure()
    probeInspectUnitDetail()
    probeInspectStat()
    probeInspectUnitCastbar()
    probeInspectBuffList()
    probeInspectUnitList()
    probeInspectMouse()
    return
  end
  
  console("Unknown command. Use /rap help", "#FF4444")
end

function Probe.OnStartup()
  console("Loaded. Use /rap help for commands.", "#00CC88")
end

table.insert(Command.Slash.Register("rap"), { Probe.OnSlashCommand, addonIdentifier, "RiftReaderApiProbe slash command" })
table.insert(Event.Addon.Startup.End, { Probe.OnStartup, addonIdentifier, "RiftReaderApiProbe startup" })
