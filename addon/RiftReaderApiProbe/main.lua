--[[
===============================================================================================
RiftReaderApiProbe v0.2.0 — comprehensive live API truth source for navigation.

Publishes player, target, environment, and nearby unit data to live Lua globals
readable via ReadProcessMemory from the C# scanner or Python resolver.

No SavedVariables. All data is live runtime truth for the current session only.

Published globals:
  RiftReaderApiProbe_Live       — compact pipe-delimited coord string (backward compat)
  RiftReaderApiProbe_Player     — full player state (pipe-delimited)
  RiftReaderApiProbe_Target     — full target state (pipe-delimited)
  RiftReaderApiProbe_Environment — zone/location/shard (pipe-delimited)
  RiftReaderApiProbe_Nearby     — nearby units table (Lua serialized)
  RiftReaderApiProbe_State      — full structured table
===============================================================================================
]]

local addonInfo, privateVars = ...
privateVars = privateVars or {}

local addonIdentifier = (addonInfo and addonInfo.identifier) or "RiftReaderApiProbe"
local addonVersion = "0.2.0"

local Probe = {}
privateVars.Probe = Probe

local refreshIntervalSeconds = 0.10
local nearbyRefreshInterval = 0.50
local lastRefreshAt = 0
local lastNearbyRefreshAt = 0
local liveSequence = 0
local MAX_NEARBY_UNITS = 20

RiftReaderApiProbe_State = RiftReaderApiProbe_State or {}
RiftReaderApiProbe_Live = RiftReaderApiProbe_Live or "RRAPICOORD1|status=starting|savedVariablesUse=none"
RiftReaderApiProbe_Player = RiftReaderApiProbe_Player or ""
RiftReaderApiProbe_Target = RiftReaderApiProbe_Target or ""
RiftReaderApiProbe_Environment = RiftReaderApiProbe_Environment or ""
RiftReaderApiProbe_Nearby = RiftReaderApiProbe_Nearby or ""
RiftReaderApiProbe_Abilities = RiftReaderApiProbe_Abilities or ""
RiftReaderApiProbe_Stats = RiftReaderApiProbe_Stats or ""

-- ---------- helpers ----------

local function console(message, color)
  local text = tostring(message or "")
  local prefix = "<font color='" .. tostring(color or "#66CCFF") .. "'>[ApiProbe]</font> "
  Command.Console.Display("general", true, prefix .. text, true)
end

local function safeCall(fn, ...)
  if type(fn) ~= "function" then return nil end
  local ok, a, b, c, d = pcall(fn, ...)
  if ok then return a, b, c, d end
  return nil
end

local function now()
  if Inspect and Inspect.Time and Inspect.Time.Real then
    local t = safeCall(Inspect.Time.Real)
    if type(t) == "number" then return t end
  end
  return 0
end

local function s(value)
  if value == nil then return "" end
  return tostring(value):gsub("[|\r\n]", " ")
end

local function n(value)
  if type(value) == "number" then return value end
  return nil
end

local function b(value)
  if value == true then return 1 end
  return 0
end

local function fmtCoord(v)
  if type(v) == "number" then return string.format("%.2f", v) end
  return ""
end

local function fmtPct(cur, mx)
  if type(cur) ~= "number" or type(mx) ~= "number" or mx <= 0 then return "" end
  return string.format("%.0f", (cur / mx) * 100)
end

-- ---------- data readers ----------

local function readPlayer()
  local unitApi = Inspect and Inspect.Unit or nil
  local playerId = safeCall(unitApi and unitApi.Lookup, "player")
  if not playerId then return nil end

  local d = safeCall(unitApi and unitApi.Detail, playerId)
  if type(d) ~= "table" then return nil end

  return {
    id = s(d.id),
    name = s(d.name),
    level = n(d.level),
    calling = s(d.calling),
    role = s(d.role),
    guild = s(d.guild),
    shard = s(d.shard),
    zone = s(d.zone),
    locationName = s(d.locationName),
    coordX = n(d.coordX),
    coordY = n(d.coordY),
    coordZ = n(d.coordZ),
    health = n(d.health),
    healthMax = n(d.healthMax),
    mana = n(d.mana),
    manaMax = n(d.manaMax),
    power = n(d.power),
    charge = n(d.charge),
    chargeMax = n(d.chargeMax),
    planar = n(d.planar),
    planarMax = n(d.planarMax),
    combat = b(d.combat),
    mounted = b(d.mounted),
    pvp = b(d.pvp),
   dead = b(d.dead),
    life = n(d.life),
    lifeMax = n(d.lifeMax),
    endurance = n(d.endurance),
    enduranceMax = n(d.enduranceMax),
  }
end

local function readTarget()
  local unitApi = Inspect and Inspect.Unit or nil
  if not unitApi then return nil end

  -- "player.target" is the only specifier that resolves NPC targets
  local targetId = safeCall(unitApi.Lookup, "player.target")
  if not targetId or targetId == "" then return nil end

  local playerId = safeCall(unitApi.Lookup, "player")
  if targetId == playerId then return nil end

  local d = safeCall(unitApi.Detail, targetId)
  if type(d) ~= "table" then return nil end

  return {
    id = s(d.id),
    name = s(d.name),
    nameSecondary = s(d.nameSecondary),
    level = n(d.level),
    calling = s(d.calling),
    relation = s(d.relation),
    role = s(d.role),
    race = s(d.race),
    raceName = s(d.raceName),
    guild = s(d.guild),
    factionId = s(d.factionId),
    alliance = s(d.alliance),
    player = b(d.player),
    coordX = n(d.coordX),
    coordY = n(d.coordY),
    coordZ = n(d.coordZ),
    health = n(d.health),
    healthMax = n(d.healthMax),
    healthCap = n(d.healthCap),
    mana = n(d.mana),
    manaMax = n(d.manaMax),
    energy = n(d.energy),
    energyMax = n(d.energyMax),
    power = n(d.power),
    charge = n(d.charge),
    chargeMax = n(d.chargeMax),
    planar = n(d.planar),
    planarMax = n(d.planarMax),
    combat = b(d.combat),
    dead = b(d.dead),
    pvp = b(d.pvp),
    afk = b(d.afk),
    aggro = b(d.aggro),
    blocked = b(d.blocked),
    tagged = s(d.tagged),
    tier = s(d.tier),
    mark = n(d.mark),
    loot = s(d.loot),
    guaranteedLoot = b(d.guaranteedLoot),
    radius = n(d.radius),
    vitality = n(d.vitality),
    mentoring = b(d.mentoring),
    ready = b(d.ready),
    warfront = b(d.warfront),
    offline = b(d.offline),
    combo = n(d.combo),
    comboUnit = s(d.comboUnit),
    distance = n(d.distance),
  }
end

local function readEnvironment()
  local unitApi = Inspect and Inspect.Unit or nil
  local playerId = safeCall(unitApi and unitApi.Lookup, "player")
  if not playerId then return nil end

  local d = safeCall(unitApi and unitApi.Detail, playerId)
  if type(d) ~= "table" then return nil end

  return {
    shard = s(d.shard),
    zone = s(d.zone),
    locationName = s(d.locationName),
    secure = 0,
  }
end

local function readNearbyUnits(excludePlayerId, excludeTargetId)
  local unitApi = Inspect and Inspect.Unit or nil
  local list = safeCall(unitApi and unitApi.List)
  if type(list) ~= "table" then return nil end

  local result = {}
  for unitId, _ in pairs(list) do
    if type(unitId) == "string"
        and unitId ~= "player"
        and unitId ~= excludePlayerId
        and unitId ~= excludeTargetId then
      local d = safeCall(unitApi and unitApi.Detail, unitId)
      if type(d) == "table" then
        local coordX = n(d.coordX)
        local coordY = n(d.coordY)
        local coordZ = n(d.coordZ)
        if coordX and coordY and coordZ then
          table.insert(result, {
            id = s(d.id),
            name = s(d.name),
            level = n(d.level),
            calling = s(d.calling),
            relation = s(d.relation),
            coordX = coordX,
            coordY = coordY,
            coordZ = coordZ,
            health = n(d.health),
            healthMax = n(d.healthMax),
            combat = b(d.combat),
            dead = b(d.dead),
          })
        end
      end
      if #result >= MAX_NEARBY_UNITS then break end
    end
  end

  return #result > 0 and result or nil
end

local function readAbilities()
  local abilityApi = Inspect and Inspect.Ability and Inspect.Ability.New or nil
  if not abilityApi then return nil end

  local ids = safeCall(abilityApi.List)
  if type(ids) ~= "table" then return nil end

  local details = safeCall(abilityApi.Detail, ids)
  if type(details) ~= "table" then
    console("Ability.Detail failed for " .. tostring(#ids) .. " ids", "#FF0000")
    return nil
  end

  local result = {}
  for id, d in pairs(details) do
    if type(d) == "table" and d.name then
      result[#result + 1] = {
        id = s(d.id),
        name = s(d.name),
        cooldown = n(d.cooldown),
        castingTime = n(d.castingTime),
        rangeMax = n(d.rangeMax),
        rangeMin = n(d.rangeMin),
        costMana = n(d.costMana),
        costEnergy = n(d.costEnergy),
        costPower = n(d.costPower),
        costCharge = n(d.costCharge),
        costPlanarCharge = n(d.costPlanarCharge),
        channeled = b(d.channeled),
        passive = b(d.passive),
        autoattack = b(d.autoattack),
        weapon = s(d.weapon),
        currentCooldownRemaining = n(d.currentCooldownRemaining),
        unusable = b(d.unusable),
      }
    end
  end

  return #result > 0 and result or nil
end

local function readStats()
  if not (Inspect and Inspect.Stat) then return nil end
  local ok, stats = pcall(Inspect.Stat)
  if not ok or type(stats) ~= "table" then return nil end
  return stats
end

-- ---------- formatters ----------

local function formatLive(player)
  if not player then
    return "RRAPICOORD1|status=fail|reason=no-player|savedVariablesUse=none"
  end
  return table.concat({
    "RRAPICOORD1",
    "schema=1",
    "seq=" .. tostring(liveSequence),
    "sampledAt=" .. string.format("%.3f", now()),
    "source=rift-api",
    "view=Inspect.Unit.Detail(player)",
    "status=pass",
    "x=" .. fmtCoord(player.coordX),
    "y=" .. fmtCoord(player.coordY),
    "z=" .. fmtCoord(player.coordZ),
    "playerId=" .. player.id,
    "name=" .. player.name,
    "zone=" .. player.zone,
    "location=" .. player.locationName,
    "savedVariablesUse=none",
  }, "|")
end

local function formatPlayer(p)
  if not p then return "" end
  return table.concat({
    "version=2",
    "seq=" .. tostring(liveSequence),
    "sampledAt=" .. string.format("%.3f", now()),
    "id=" .. p.id,
    "name=" .. p.name,
    "level=" .. tostring(p.level or ""),
    "calling=" .. p.calling,
    "role=" .. p.role,
    "guild=" .. p.guild,
    "shard=" .. p.shard,
    "zone=" .. p.zone,
    "location=" .. p.locationName,
    "x=" .. fmtCoord(p.coordX),
    "y=" .. fmtCoord(p.coordY),
    "z=" .. fmtCoord(p.coordZ),
    "hp=" .. tostring(p.health or ""),
    "hpMax=" .. tostring(p.healthMax or ""),
    "hpPct=" .. fmtPct(p.health, p.healthMax),
    "mana=" .. tostring(p.mana or ""),
    "manaMax=" .. tostring(p.manaMax or ""),
    "power=" .. tostring(p.power or ""),
    "charge=" .. tostring(p.charge or ""),
    "chargeMax=" .. tostring(p.chargeMax or ""),
    "planar=" .. tostring(p.planar or ""),
    "planarMax=" .. tostring(p.planarMax or ""),
    "life=" .. tostring(p.life or ""),
    "lifeMax=" .. tostring(p.lifeMax or ""),
    "endurance=" .. tostring(p.endurance or ""),
    "enduranceMax=" .. tostring(p.enduranceMax or ""),
    "combat=" .. tostring(p.combat),
    "mounted=" .. tostring(p.mounted),
    "pvp=" .. tostring(p.pvp),
    "dead=" .. tostring(p.dead),
  }, "|")
end

local function formatTarget(t)
  if not t then return "version=2|present=0" end
  return table.concat({
    "version=2",
    "present=1",
    "sampledAt=" .. string.format("%.3f", now()),
    "id=" .. tostring(t.id or ""),
    "name=" .. tostring(t.name or ""),
    "nameSecondary=" .. tostring(t.nameSecondary or ""),
    "level=" .. tostring(t.level or ""),
    "calling=" .. tostring(t.calling or ""),
    "relation=" .. tostring(t.relation or ""),
    "role=" .. tostring(t.role or ""),
    "race=" .. tostring(t.race or ""),
    "raceName=" .. tostring(t.raceName or ""),
    "guild=" .. tostring(t.guild or ""),
    "factionId=" .. tostring(t.factionId or ""),
    "alliance=" .. tostring(t.alliance or ""),
    "player=" .. tostring(t.player or ""),
    "x=" .. fmtCoord(t.coordX),
    "y=" .. fmtCoord(t.coordY),
    "z=" .. fmtCoord(t.coordZ),
    "hp=" .. tostring(t.health or ""),
    "hpMax=" .. tostring(t.healthMax or ""),
    "hpCap=" .. tostring(t.healthCap or ""),
    "hpPct=" .. fmtPct(t.health, t.healthMax),
    "mana=" .. tostring(t.mana or ""),
    "manaMax=" .. tostring(t.manaMax or ""),
    "energy=" .. tostring(t.energy or ""),
    "energyMax=" .. tostring(t.energyMax or ""),
    "power=" .. tostring(t.power or ""),
    "charge=" .. tostring(t.charge or ""),
    "chargeMax=" .. tostring(t.chargeMax or ""),
    "planar=" .. tostring(t.planar or ""),
    "planarMax=" .. tostring(t.planarMax or ""),
    "combat=" .. tostring(t.combat or ""),
    "dead=" .. tostring(t.dead or ""),
    "pvp=" .. tostring(t.pvp or ""),
    "afk=" .. tostring(t.afk or ""),
    "aggro=" .. tostring(t.aggro or ""),
    "blocked=" .. tostring(t.blocked or ""),
    "tagged=" .. tostring(t.tagged or ""),
    "tier=" .. tostring(t.tier or ""),
    "mark=" .. tostring(t.mark or ""),
    "loot=" .. tostring(t.loot or ""),
    "guaranteedLoot=" .. tostring(t.guaranteedLoot or ""),
    "radius=" .. tostring(t.radius or ""),
    "vitality=" .. tostring(t.vitality or ""),
    "mentoring=" .. tostring(t.mentoring or ""),
    "ready=" .. tostring(t.ready or ""),
    "warfront=" .. tostring(t.warfront or ""),
    "offline=" .. tostring(t.offline or ""),
    "combo=" .. tostring(t.combo or ""),
    "comboUnit=" .. tostring(t.comboUnit or ""),
    "distance=" .. tostring(t.distance or ""),
  }, "|")
end

local function formatEnvironment(e)
  if not e then return "" end
  return table.concat({
    "version=2",
    "sampledAt=" .. string.format("%.3f", now()),
    "shard=" .. e.shard,
    "zone=" .. e.zone,
    "location=" .. e.locationName,
    "secure=" .. tostring(e.secure),
  }, "|")
end

local function formatNearby(units)
  if not units then return "" end
  local parts = {"version=2", "count=" .. #units}
  for i, u in ipairs(units) do
    table.insert(parts, string.format(
      "%d|%s|%s|%d|%s|%s|%.2f|%.2f|%.2f|%d|%d",
      i,
      u.id, u.name, u.level or 0, u.calling, u.relation,
      u.coordX, u.coordY, u.coordZ,
      u.health or 0, u.healthMax or 0
    ))
  end
  return table.concat(parts, "|")
end

local function formatAbilities(abilities)
  if not abilities then return "RRAPICAPABILITIES|count=0" end
  local parts = {"RRAPICAPABILITIES", "count=" .. #abilities}
  for i, a in ipairs(abilities) do
    table.insert(parts, string.format(
      "%d|%s|%s|%.1f|%.1f|%.0f|%.0f|%s|%s|%s|%s",
      i,
      a.id, a.name,
      a.cooldown or 0, a.castingTime or 0,
      a.rangeMax or 0, a.rangeMin or 0,
      a.weapon or "",
      a.channeled or "", a.passive or "", a.autoattack or "",
      a.currentCooldownRemaining or ""
    ))
  end
  return table.concat(parts, "|")
end

local function formatStats(stats)
  if not stats then return "RRAPISTATS|count=0" end
  local parts = {"RRAPISTATS"}
  local keys = {}
  for k in pairs(stats) do keys[#keys + 1] = k end
  table.sort(keys)
  for _, k in ipairs(keys) do
    parts[#parts + 1] = k .. "=" .. tostring(stats[k])
  end
  return table.concat(parts, "|")
end

-- ---------- refresh ----------

local function refreshAll(force)
  local currentTime = now()
  local doNearby = force or (currentTime - lastNearbyRefreshAt) >= nearbyRefreshInterval

  if not force and currentTime > 0 and (currentTime - lastRefreshAt) < refreshIntervalSeconds then
    return
  end

  lastRefreshAt = currentTime
  liveSequence = liveSequence + 1

  local player = readPlayer()
  local target = readTarget()
  local environment = readEnvironment()

  local nearby = nil
  if doNearby then
    lastNearbyRefreshAt = currentTime
    nearby = readNearbyUnits(player and player.id, target and target.id)
  end

  RiftReaderApiProbe_Live = formatLive(player)
  RiftReaderApiProbe_Player = formatPlayer(player)
  RiftReaderApiProbe_Target = formatTarget(target)
  RiftReaderApiProbe_Environment = formatEnvironment(environment)
  if doNearby then
    RiftReaderApiProbe_Nearby = formatNearby(nearby)
  end

  local abilities = readAbilities()
  RiftReaderApiProbe_Abilities = formatAbilities(abilities)

  local stats = readStats()
  RiftReaderApiProbe_Stats = formatStats(stats)

  RiftReaderApiProbe_State = {
    sequence = liveSequence,
    sampledAt = currentTime,
    player = player,
    target = target,
    environment = environment,
    nearby = nearby,
    abilities = abilities,
    stats = stats,
  }
end

-- ---------- probes (slash commands) ----------

local function probeCoords()
  refreshAll(true)
  local p = RiftReaderApiProbe_State.player
  if p then
    console(string.format(
      "Player seq=%d x=%.4f y=%.4f z=%.4f hp=%d/%d zone=%s",
      liveSequence, p.coordX or 0, p.coordY or 0, p.coordZ or 0,
      p.health or 0, p.healthMax or 0, p.zone or ""), "#00FF88")
  else
    console("Player not available", "#FF4444")
  end
  local t = RiftReaderApiProbe_State.target
  if t then
    console(string.format(
      "Target name=%s x=%.4f y=%.4f z=%.4f hp=%d/%d relation=%s",
      t.name, t.coordX or 0, t.coordY or 0, t.coordZ or 0,
      t.health or 0, t.healthMax or 0, t.relation or ""), "#00FF88")
  else
    console("No target", "#FFAA00")
  end
  local nearby = RiftReaderApiProbe_State.nearby
  if nearby then
    console(string.format("Nearby units: %d", #nearby), "#00FF88")
    for _, u in ipairs(nearby) do
      console(string.format("  %s [%s] L%d (%.1f, %.1f, %.1f) %s",
        u.name, u.calling, u.level or 0, u.coordX, u.coordY, u.coordZ, u.relation), "#CCCCCC")
    end
  else
    console("No nearby units found", "#FFAA00")
  end
end

local function inspectTable(tbl, indent, maxDepth)
  if type(tbl) ~= "table" then return tostring(tbl) end
  if maxDepth <= 0 then return "{...}" end
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
  if #lines == 0 then return "{}" end
  return "{\n" .. table.concat(lines, "\n") .. "\n" .. indent .. "}"
end

function Probe.OnSlashCommand(args)
  local command = string.match(args or "", "^(%S+)")
  if command then command = string.lower(command) end

  if not command or command == "help" then
    console("RiftReaderApiProbe v" .. addonVersion, "#FFFF00")
    console("  /rap status    - Show all live data (player + target + env + nearby)", "#CCCCCC")
    console("  /rap coord     - Show player + target coordinates", "#CCCCCC")
    console("  /rap player    - Dump full player state", "#CCCCCC")
    console("  /rap target    - Dump full target state", "#CCCCCC")
    console("  /rap env       - Show environment info", "#CCCCCC")
    console("  /rap nearby    - List nearby units", "#CCCCCC")
    console("  /rap detail    - Probe Inspect.Unit.Detail fields", "#CCCCCC")
    console("  /rap unitlist  - Probe Inspect.Unit.List", "#CCCCCC")
    console("  /rap buff      - Probe Inspect.Buff.List", "#CCCCCC")
    console("  /rap stat      - Probe Inspect.Stat", "#CCCCCC")
    console("  /rap all       - Run all probes", "#CCCCCC")
    return
  end

  if command == "status" or command == "coord" then
    probeCoords()
    return
  end

  if command == "player" then
    refreshAll(true)
    local p = RiftReaderApiProbe_State.player
    if p then
      console("=== Player State ===", "#FFFF00")
      console(inspectTable(p, "", 2), "#CCCCCC")
      console("Live string: " .. tostring(RiftReaderApiProbe_Player), "#CCCCCC")
    else
      console("Player not available", "#FF4444")
    end
    return
  end

  if command == "target" then
    refreshAll(true)
    local t = RiftReaderApiProbe_State.target
    if t then
      console("=== Target State ===", "#FFFF00")
      console(inspectTable(t, "", 2), "#CCCCCC")
      console("Live string: " .. tostring(RiftReaderApiProbe_Target), "#CCCCCC")
    else
      console("No target", "#FFAA00")
    end
    return
  end

  if command == "env" then
    refreshAll(true)
    local e = RiftReaderApiProbe_State.environment
    if e then
      console("=== Environment ===", "#FFFF00")
      console(inspectTable(e, "", 2), "#CCCCCC")
    end
    return
  end

  if command == "nearby" then
    refreshAll(true)
    local nearby = RiftReaderApiProbe_State.nearby
    if nearby then
      console("=== Nearby Units (" .. #nearby .. ") ===", "#FFFF00")
      for _, u in ipairs(nearby) do
        console(string.format("  %s [%s] L%d (%.1f, %.1f, %.1f) hp=%d/%d relation=%s",
          u.name, u.calling, u.level or 0, u.coordX, u.coordY, u.coordZ,
          u.health or 0, u.healthMax or 0, u.relation or ""), "#CCCCCC")
      end
    else
      console("No nearby units", "#FFAA00")
    end
    return
  end

  if command == "detail" then
    local unitApi = Inspect and Inspect.Unit or nil
    local playerId = safeCall(unitApi and unitApi.Lookup, "player")
    if not playerId then console("Player not available", "#FF4444"); return end
    local detail = safeCall(unitApi and unitApi.Detail, playerId)
    if type(detail) ~= "table" then console("Detail returned: " .. type(detail), "#FF4444"); return end
    console("=== Inspect.Unit.Detail(player) ===", "#FFFF00")
    local sortedKeys = {}
    for k in pairs(detail) do table.insert(sortedKeys, k) end
    table.sort(sortedKeys, function(a, b) return tostring(a) < tostring(b) end)
    for _, k in ipairs(sortedKeys) do
      local v = detail[k]
      local typeStr = type(v)
      local valStr
      if typeStr == "table" then valStr = "(table)"
      elseif typeStr == "string" then valStr = '"' .. v .. '"'
      elseif typeStr == "boolean" then valStr = v and "true" or "false"
      elseif typeStr == "number" then valStr = string.format("%.4f", v)
      else valStr = tostring(v) end
      console(string.format("  .%s [%s] = %s", tostring(k), typeStr, valStr), "#CCCCCC")
    end
    return
  end

  if command == "unitlist" then
    local unitApi = Inspect and Inspect.Unit or nil
    local list = safeCall(unitApi and unitApi.List)
    if type(list) ~= "table" then
      console("Inspect.Unit.List returned: " .. type(list), "#FF4444")
      return
    end
    console("=== Inspect.Unit.List ===", "#FFFF00")
    local count = 0
    for unitId, _ in pairs(list) do
      count = count + 1
      if count <= 30 then
        console("  " .. tostring(unitId), "#CCCCCC")
      end
    end
    console("Total units: " .. count, "#00FF88")
    return
  end

  if command == "buff" then
    local unitApi = Inspect and Inspect.Unit or nil
    local playerId = safeCall(unitApi and unitApi.Lookup, "player")
    if not playerId then console("Player not available", "#FF4444"); return end
    local buffApi = Inspect and Inspect.Buff or nil
    local buffList = safeCall(buffApi and buffApi.List, playerId)
    if type(buffList) ~= "table" then
      console("Inspect.Buff.List returned: " .. type(buffList), "#FF4444")
      return
    end
    console("=== Inspect.Buff.List(player) ===", "#FFFF00")
    local count = 0
    for buffId, _ in pairs(buffList) do
      count = count + 1
      if count <= 20 then console("  " .. tostring(buffId), "#CCCCCC") end
    end
    console("Total buffs: " .. count, "#00FF88")
    return
  end

  if command == "stat" then
    local stats = safeCall(Inspect.Stat)
    if type(stats) ~= "table" then
      console("Inspect.Stat returned: " .. type(stats), "#FF4444")
      return
    end
    console("=== Inspect.Stat ===", "#FFFF00")
    local sortedKeys = {}
    for k in pairs(stats) do table.insert(sortedKeys, k) end
    table.sort(sortedKeys, function(a, b) return tostring(a) < tostring(b) end)
    for _, k in ipairs(sortedKeys) do
      local v = stats[k]
      local valStr = type(v) == "number" and string.format("%.4f", v) or tostring(v)
      console(string.format("  .%s = %s", tostring(k), valStr), "#CCCCCC")
    end
    return
  end

  if command == "all" then
    probeCoords()
    local unitApi = Inspect and Inspect.Unit or nil
    local playerId = safeCall(unitApi and unitApi.Lookup, "player")
    if playerId then
      local detail = safeCall(unitApi and unitApi.Detail, playerId)
      if type(detail) == "table" then
        console("=== Inspect.Unit.Detail fields ===", "#FFFF00")
        local count = 0
        for k, v in pairs(detail) do
          count = count + 1
          if count <= 30 then
            console(string.format("  .%s = %s", tostring(k), tostring(v)), "#CCCCCC")
          end
        end
      end
    end
    return
  end

  if command == "diag" then
    runDiagnostics()
    return
  end

  console("Unknown command. Use /rap help", "#FF4444")
end

local function runDiagnostics()
  console("=== RIFT API DIAGNOSTICS ===", "#FFFF00")

  -- Check API availability
  local apiChecks = {
    {"Inspect", Inspect},
    {"Inspect.Ability", Inspect and Inspect.Ability},
    {"Inspect.Ability.New", Inspect and Inspect.Ability and Inspect.Ability.New},
    {"Inspect.Ability.New.List", Inspect and Inspect.Ability and Inspect.Ability.New and Inspect.Ability.New.List},
    {"Inspect.Ability.New.Detail", Inspect and Inspect.Ability and Inspect.Ability.New and Inspect.Ability.New.Detail},
    {"Inspect.Stat", Inspect and Inspect.Stat},
    {"Inspect.Unit", Inspect and Inspect.Unit},
    {"Inspect.Unit.Detail", Inspect and Inspect.Unit and Inspect.Unit.Detail},
    {"Inspect.Buff", Inspect and Inspect.Buff},
    {"Inspect.Buff.Detail", Inspect and Inspect.Buff and Inspect.Buff.Detail},
  }
  for _, check in ipairs(apiChecks) do
    local name, val = check[1], check[2]
    local status = type(val) == "function" and "FUNCTION" or type(val) == "table" and "TABLE" or "MISSING"
    local color = status == "MISSING" and "#FF4444" or "#00CC88"
    console(string.format("  %s: %s", name, status), color)
  end

  -- Test Ability.New.List
  if Inspect and Inspect.Ability and Inspect.Ability.New and Inspect.Ability.New.List then
    local ok, ids = pcall(Inspect.Ability.New.List)
    if ok and type(ids) == "table" then
      local count = 0
      for _ in pairs(ids) do count = count + 1 end
      console(string.format("  Ability.List: %d abilities found", count), "#00CC88")

      -- Test Detail on first ability
      for id, _ in pairs(ids) do
        local ok2, d = pcall(Inspect.Ability.New.Detail, id)
        if ok2 and type(d) == "table" then
          console(string.format("  First ability: %s (cooldown=%.1f, cast=%.1f)", tostring(d.name), d.cooldown or 0, d.castingTime or 0), "#CCCCCC")
        else
          console(string.format("  Ability.Detail(%s) failed: %s", tostring(id), tostring(d)), "#FF4444")
        end
        break
      end
    else
      console(string.format("  Ability.List failed: %s", tostring(ids)), "#FF4444")
    end
  end

  -- Test Inspect.Stat
  if Inspect and Inspect.Stat then
    local ok, stats = pcall(Inspect.Stat)
    if ok and type(stats) == "table" then
      local count = 0
      for _ in pairs(stats) do count = count + 1 end
      console(string.format("  Inspect.Stat: %d stats found", count), "#00CC88")
      for k, v in pairs(stats) do
        console(string.format("    %s = %s", tostring(k), tostring(v)), "#CCCCCC")
        count = count - 1
        if count < 0 then break end
      end
    else
      console(string.format("  Inspect.Stat failed: %s", tostring(stats)), "#FF4444")
    end
  end

  -- Check globals
  console("=== GLOBALS ===", "#FFFF00")
  local globals = {
    {"RiftReaderApiProbe_Live", RiftReaderApiProbe_Live},
    {"RiftReaderApiProbe_Player", RiftReaderApiProbe_Player},
    {"RiftReaderApiProbe_Target", RiftReaderApiProbe_Target},
    {"RiftReaderApiProbe_Environment", RiftReaderApiProbe_Environment},
    {"RiftReaderApiProbe_Nearby", RiftReaderApiProbe_Nearby},
    {"RiftReaderApiProbe_Abilities", RiftReaderApiProbe_Abilities},
    {"RiftReaderApiProbe_Stats", RiftReaderApiProbe_Stats},
  }
  for _, g in ipairs(globals) do
    local name, val = g[1], g[2]
    local len = val and #val or 0
    local preview = val and val:sub(1, 60) or "(nil)"
    console(string.format("  %s: len=%d preview=%s", name, len, preview), len > 0 and "#00CC88" or "#FF4444")
  end
end

function Probe.OnStartup()
  refreshAll(true)
  console("Loaded v" .. addonVersion .. ". Use /rap help for commands.", "#00CC88")
  console("Globals: RiftReaderApiProbe_Player, _Target, _Environment, _Nearby", "#00CC88")
end

table.insert(Command.Slash.Register("rap"), { Probe.OnSlashCommand, addonIdentifier, "RiftReaderApiProbe slash command" })
table.insert(Event.Addon.Startup.End, { Probe.OnStartup, addonIdentifier, "RiftReaderApiProbe startup" })
if Event and Event.System and Event.System.Update and Event.System.Update.Begin then
  table.insert(Event.System.Update.Begin, { function() refreshAll(false) end, addonIdentifier, "RiftReaderApiProbe live refresh" })
end
