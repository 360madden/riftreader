local addonInfo, privateVars = ...
privateVars = privateVars or {}

local addonIdentifier = (addonInfo and addonInfo.identifier) or "ReaderBridgeExport"
local addonVersion = (addonInfo and addonInfo.version) or "0.1.0"
local UPDATE_INTERVAL = 0.5
local MAX_BUFF_ROWS = 5
local MAX_NEARBY_UNITS = 10
local MAX_PARTY_SLOTS = 5

local Exporter = {}
privateVars.Exporter = Exporter

local state = nil
local runtime = {
  started = false,
  lastRefreshAt = 0,
  lastBridgeSeenAt = 0,
  targetTtdSamples = {},
  lastPlayerCoord = nil,
  lastPlayerCoordAt = 0,
}

local function now()
  if Inspect and Inspect.Time and Inspect.Time.Real then
    return Inspect.Time.Real() or 0
  end

  return 0
end

local function console(message, color)
  local text = tostring(message or "")
  local prefix = "<font color='" .. tostring(color or "#66CCFF") .. "'>[ReaderBridgeExport]</font> "
  Command.Console.Display("general", true, prefix .. text, true)
end

local function toNumber(value)
  local number = tonumber(value)
  return number
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

local function copyString(value)
  if value == nil then
    return nil
  end

  return tostring(value)
end

local function copyBoolean(value)
  if value == nil then
    return nil
  end

  return value and true or false
end

local function copyCoord(unit)
  if type(unit) ~= "table" then
    return nil
  end

  local x = toNumber(unit.coordX)
  local y = toNumber(unit.coordY)
  local z = toNumber(unit.coordZ)

  if x == nil and y == nil and z == nil then
    return nil
  end

  return {
    x = x,
    y = y,
    z = z,
  }
end

local function copyCast(cast)
  if type(cast) ~= "table" then
    return nil
  end

  return {
    active = copyBoolean(cast.active),
    abilityName = copyString(cast.abilityName),
    duration = toNumber(cast.duration),
    remaining = toNumber(cast.remaining),
    channeled = copyBoolean(cast.channeled),
    uninterruptible = copyBoolean(cast.uninterruptible),
    progressPct = toNumber(cast.progressPct),
    text = copyString(cast.text),
  }
end

local function copyList(lines)
  local result = {}

  if type(lines) ~= "table" then
    return result
  end

  for index, value in ipairs(lines) do
    result[index] = tostring(value or "")
  end

  return result
end

local function listCount(lines)
  if type(lines) ~= "table" then
    return 0
  end

  return #lines
end

local function percent(current, maximum)
  current = toNumber(current)
  maximum = toNumber(maximum)

  if current == nil or maximum == nil or maximum <= 0 then
    return 0
  end

  local value = math.floor(((current / maximum) * 100) + 0.5)
  if value < 0 then
    return 0
  end

  if value > 100 then
    return 100
  end

  return value
end

local function formatCompactSeconds(seconds)
  local value = toNumber(seconds)
  if value == nil then
    return "-"
  end

  if value < 0 then
    value = 0
  end

  if value >= 10 then
    return string.format("%.0fs", value)
  end

  return string.format("%.1fs", value)
end

local function distance3d(ax, ay, az, bx, by, bz)
  ax = toNumber(ax)
  ay = toNumber(ay)
  az = toNumber(az)
  bx = toNumber(bx)
  by = toNumber(by)
  bz = toNumber(bz)

  if ax == nil or ay == nil or az == nil or bx == nil or by == nil or bz == nil then
    return nil
  end

  local dx = ax - bx
  local dy = ay - by
  local dz = az - bz
  return math.sqrt((dx * dx) + (dy * dy) + (dz * dz))
end

local function safeStatRead()
  return safeCall(Inspect.Stat)
end

local function safeUnitList()
  -- NilRisk: Inspect.Unit.List is unverified in this RIFT version; safeCall returns nil on failure
  return safeCall(Inspect.Unit.List)
end

local function safeUnitLookup(unit)
  return safeCall(Inspect.Unit.Lookup, unit)
end

local function safeUnitDetail(unit)
  return safeCall(Inspect.Unit.Detail, unit)
end

local function safeUnitHeading(unit)
  if not Inspect or not Inspect.Unit then
    return nil
  end

  return safeCall(Inspect.Unit.Heading, unit)
end

local function safeUnitPitch(unit)
  if not Inspect or not Inspect.Unit then
    return nil
  end

  return safeCall(Inspect.Unit.Pitch, unit)
end

local function safeUnitCastbar(unit)
  return safeCall(Inspect.Unit.Castbar, unit)
end

local function safeBuffList(unit)
  return safeCall(Inspect.Buff.List, unit)
end

local function safeBuffDetail(unit, buffs)
  return safeCall(Inspect.Buff.Detail, unit, buffs)
end

local function buildCoord(detail)
  if type(detail) ~= "table" then
    return nil
  end

  local x = toNumber(detail.coordX)
  local y = toNumber(detail.coordY)
  local z = toNumber(detail.coordZ)

  if x == nil and y == nil and z == nil then
    return nil
  end

  return {
    x = x,
    y = y,
    z = z,
  }
end

local function readCast(unitSpecOrId)
  local cast = safeUnitCastbar(unitSpecOrId)
  if type(cast) ~= "table" or toNumber(cast.duration) == nil or toNumber(cast.duration) <= 0 then
    return {
      active = false,
      abilityName = nil,
      duration = nil,
      remaining = nil,
      channeled = false,
      uninterruptible = false,
      progressPct = 0,
      text = "-",
    }
  end

  local duration = toNumber(cast.duration) or 0
  local remaining = toNumber(cast.remaining) or 0
  local channeled = cast.channeled and true or false
  local progressPct = 0

  if duration > 0 then
    if channeled then
      progressPct = math.max(0, math.min(100, (remaining / duration) * 100))
    else
      progressPct = math.max(0, math.min(100, ((duration - remaining) / duration) * 100))
    end
  end

  return {
    active = true,
    abilityName = copyString(cast.abilityName),
    duration = duration,
    remaining = remaining,
    channeled = channeled,
    uninterruptible = cast.uninterruptible and true or false,
    progressPct = progressPct,
    text = (channeled and "Channel" or "Cast")
      .. ": " .. tostring(cast.abilityName or "-")
      .. " | " .. formatCompactSeconds(remaining)
      .. " / " .. formatCompactSeconds(duration),
  }
end

local function primaryResource(detail)
  if type(detail) ~= "table" then
    return "", 0, 0, 0
  end

  if toNumber(detail.manaMax) and toNumber(detail.manaMax) > 0 then
    return "Mana", toNumber(detail.mana) or 0, toNumber(detail.manaMax) or 0, percent(detail.mana, detail.manaMax)
  end

  if toNumber(detail.energyMax) and toNumber(detail.energyMax) > 0 then
    return "Energy", toNumber(detail.energy) or 0, toNumber(detail.energyMax) or 0, percent(detail.energy, detail.energyMax)
  end

  if detail.power ~= nil then
    local maxValue = toNumber(detail.powerMax) or 100
    local current = toNumber(detail.power) or 0
    return "Power", current, maxValue, percent(current, maxValue)
  end

  if toNumber(detail.chargeMax) and toNumber(detail.chargeMax) > 0 then
    return "Charge", toNumber(detail.charge) or 0, toNumber(detail.chargeMax) or 0, percent(detail.charge, detail.chargeMax)
  end

  return "", 0, 0, 0
end

local function normalizeBuffLine(detail)
  if type(detail) ~= "table" then
    return nil
  end

  local text = tostring(detail.name or "-")

  local stack = toNumber(detail.stack)
  if stack and stack > 1 then
    text = text .. " x" .. tostring(stack)
  end

  local remaining = toNumber(detail.remaining)
  if remaining then
    text = text .. " | " .. formatCompactSeconds(remaining)
  end

  return {
    text = text,
    remaining = remaining,
    debuff = detail.debuff and true or false,
    name = tostring(detail.name or ""),
  }
end

local function compareBuffLines(left, right)
  local leftRemaining = toNumber(left and left.remaining)
  local rightRemaining = toNumber(right and right.remaining)

  if leftRemaining and rightRemaining and leftRemaining ~= rightRemaining then
    return leftRemaining < rightRemaining
  end

  if leftRemaining ~= nil and rightRemaining == nil then
    return true
  end

  if leftRemaining == nil and rightRemaining ~= nil then
    return false
  end

  return tostring(left and left.name or "") < tostring(right and right.name or "")
end

local function buildBuffLines(unitSpecOrId, wantDebuffs)
  local buffIds = safeBuffList(unitSpecOrId)
  if type(buffIds) ~= "table" then
    return {}
  end

  local details = safeBuffDetail(unitSpecOrId, buffIds)
  if type(details) ~= "table" then
    return {}
  end

  local entries = {}

  for _, detail in pairs(details) do
    local entry = normalizeBuffLine(detail)
    if entry and ((wantDebuffs and entry.debuff) or ((not wantDebuffs) and (not entry.debuff))) then
      table.insert(entries, entry)
    end
  end

  table.sort(entries, compareBuffLines)

  local result = {}
  for index = 1, math.min(#entries, MAX_BUFF_ROWS) do
    result[index] = entries[index].text
  end

  return result
end

local function buildStatSnapshot()
  local stats = safeStatRead()
  if type(stats) ~= "table" then
    return nil
  end

  local result = {}
  for k, v in pairs(stats) do
    if type(k) == "string" and tonumber(v) ~= nil then
      result[k] = tonumber(v)
    end
  end

  return result
end

local function isOrientationKey(key)
  if type(key) ~= "string" then
    return false
  end

  local lower = string.lower(key)
  return lower == "heading"
    or lower == "pitch"
    or lower == "yaw"
    or lower == "face"
    or lower == "facing"
    or lower == "orient"
    or lower == "orientation"
    or lower == "rotation"
    or string.find(lower, "heading", 1, true) ~= nil
    or string.find(lower, "pitch", 1, true) ~= nil
    or string.find(lower, "yaw", 1, true) ~= nil
    or string.find(lower, "face", 1, true) ~= nil
    or string.find(lower, "orient", 1, true) ~= nil
    or string.find(lower, "rotation", 1, true) ~= nil
end

local function copyOrientationValue(value)
  local valueType = type(value)
  if valueType == "number" or valueType == "string" or valueType == "boolean" then
    return value
  end

  if value == nil then
    return nil
  end

  return tostring(value)
end

local function buildOrientationCandidates(source)
  if type(source) ~= "table" then
    return nil
  end

  local candidates = {}
  for key, value in pairs(source) do
    if isOrientationKey(key) then
      table.insert(candidates, {
        key = tostring(key),
        value = copyOrientationValue(value),
        valueType = type(value),
      })
    end
  end

  table.sort(candidates, function(a, b)
    return a.key < b.key
  end)

  return #candidates > 0 and candidates or nil
end

local function buildOrientationUnitProbe(source, label, sharedStatCandidates)
  local probe = {
    source = tostring(label or "unit"),
    directHeading = nil,
    directPitch = nil,
  }

  if type(source) == "table" then
    probe.detailCandidates = buildOrientationCandidates(source)
  end

  if type(sharedStatCandidates) == "table" and #sharedStatCandidates > 0 then
    probe.statCandidates = sharedStatCandidates
  end

  return probe
end

local function hasOrientationUnitProbeData(probe)
  if type(probe) ~= "table" then
    return false
  end

  if probe.directHeading ~= nil or probe.directPitch ~= nil then
    return true
  end

  if type(probe.detailCandidates) == "table" and #probe.detailCandidates > 0 then
    return true
  end

  if type(probe.stateCandidates) == "table" and #probe.stateCandidates > 0 then
    return true
  end

  if type(probe.statCandidates) == "table" and #probe.statCandidates > 0 then
    return true
  end

  if probe.yaw ~= nil or probe.facing ~= nil then
    return true
  end

  return false
end

local function pruneOrientationUnitProbe(probe)
  if not hasOrientationUnitProbeData(probe) then
    return nil
  end

  return probe
end

local function buildOrientationProbe(playerDetail, targetDetail, statSource, playerState, targetState, playerId, targetId)
  local sharedStatCandidates = buildOrientationCandidates(statSource)
  local probe = {
    player = buildOrientationUnitProbe(playerDetail, "player", sharedStatCandidates),
    target = buildOrientationUnitProbe(targetDetail, "target", sharedStatCandidates),
    statCandidates = sharedStatCandidates,
  }

  if probe.player then
    probe.player.directHeading = toNumber(safeUnitHeading(playerId)) or (type(playerDetail) == "table" and toNumber(playerDetail.heading) or nil)
    probe.player.directPitch = toNumber(safeUnitPitch(playerId)) or (type(playerDetail) == "table" and toNumber(playerDetail.pitch) or nil)
    probe.player.stateCandidates = buildOrientationCandidates(playerState)
  end

  if probe.target then
    probe.target.directHeading = toNumber(safeUnitHeading(targetId)) or (type(targetDetail) == "table" and toNumber(targetDetail.heading) or nil)
    probe.target.directPitch = toNumber(safeUnitPitch(targetId)) or (type(targetDetail) == "table" and toNumber(targetDetail.pitch) or nil)
    probe.target.stateCandidates = buildOrientationCandidates(targetState)
  end

  probe.player = pruneOrientationUnitProbe(probe.player)
  probe.target = pruneOrientationUnitProbe(probe.target)

  if not probe.player and not probe.target and not probe.statCandidates then
    return nil
  end

  return probe
end

local function buildCoordDelta(coord, currentTime)
  if type(coord) ~= "table" then
    runtime.lastPlayerCoord = nil
    runtime.lastPlayerCoordAt = 0
    return nil
  end

  local cx = toNumber(coord.x)
  local cy = toNumber(coord.y)
  local cz = toNumber(coord.z)

  if cx == nil or cy == nil or cz == nil then
    return nil
  end

  local delta = nil
  -- NilRisk: lastPlayerCoord may be nil on first call or after coord loss
  if type(runtime.lastPlayerCoord) == "table" then
    local px = toNumber(runtime.lastPlayerCoord.x)
    local py = toNumber(runtime.lastPlayerCoord.y)
    local pz = toNumber(runtime.lastPlayerCoord.z)
    local dt = (currentTime or 0) - (runtime.lastPlayerCoordAt or 0)

    if px ~= nil and py ~= nil and pz ~= nil and dt > 0 then
      local dx = cx - px
      local dy = cy - py
      local dz = cz - pz
      delta = {
        dx = dx,
        dy = dy,
        dz = dz,
        distance = math.sqrt((dx * dx) + (dy * dy) + (dz * dz)),
        dt = dt,
      }
    end
  end

  runtime.lastPlayerCoord = { x = cx, y = cy, z = cz }
  runtime.lastPlayerCoordAt = currentTime or 0

  return delta
end

local function readUnit(unitSpecOrId)
  local detail = safeUnitDetail(unitSpecOrId)
  if type(detail) ~= "table" then
    return nil
  end

  local resourceKind, resource, resourceMax, resourcePct = primaryResource(detail)
  local hp = toNumber(detail.health) or 0
  local hpMax = toNumber(detail.healthMax) or 0
  local charge = toNumber(detail.charge) or 0
  local chargeMax = toNumber(detail.chargeMax) or 0
  local planar = toNumber(detail.planar) or 0
  local planarMax = toNumber(detail.planarMax) or 0

  return {
    id = copyString(detail.id or unitSpecOrId),
    name = copyString(detail.name),
    level = toNumber(detail.level),
    calling = copyString(detail.calling),
    guild = copyString(detail.guild),
    relation = copyString(detail.relation),
    role = copyString(detail.role),
    player = copyBoolean(detail.player),
    combat = copyBoolean(detail.combat),
    pvp = copyBoolean(detail.pvp),
    hp = hp,
    hpMax = hpMax,
    hpPct = percent(hp, hpMax),
    absorb = toNumber(detail.absorb),
    vitality = toNumber(detail.vitality),
    resourceKind = resourceKind,
    resource = resource,
    resourceMax = resourceMax,
    resourcePct = resourcePct,
    mana = toNumber(detail.mana),
    manaMax = toNumber(detail.manaMax),
    energy = toNumber(detail.energy),
    energyMax = toNumber(detail.energyMax),
    power = toNumber(detail.power),
    charge = charge,
    chargeMax = chargeMax,
    chargePct = percent(charge, chargeMax),
    planar = planar,
    planarMax = planarMax,
    planarPct = percent(planar, planarMax),
    combo = toNumber(detail.combo),
    zone = copyString(detail.zone),
    locationName = copyString(detail.locationName),
    coord = buildCoord(detail),
    cast = readCast(unitSpecOrId),
  }
end

local function readNearbyUnits(excludePlayerId, excludeTargetId)
  local list = safeUnitList()
  if type(list) ~= "table" then
    return nil
  end

  local result = {}
  for unitId, _ in pairs(list) do
    if type(unitId) == "string"
        and unitId ~= "player"
        and unitId ~= excludePlayerId
        and unitId ~= excludeTargetId then
      local unit = readUnit(unitId)
      if unit then
        table.insert(result, unit)
      end
      if #result >= MAX_NEARBY_UNITS then
        break
      end
    end
  end

  return #result > 0 and result or nil
end

local function readPartyMembers()
  local result = {}
  for i = 1, MAX_PARTY_SLOTS do
    local spec = "group0" .. i
    local id = safeUnitLookup(spec)
    -- NilRisk: id may be nil if slot is empty or group specifier unsupported
    if id then
      local unit = readUnit(id)
      if unit then
        table.insert(result, unit)
      end
    end
  end

  return #result > 0 and result or nil
end

local function updateTargetTtd(target)
  if type(target) ~= "table" or toNumber(target.hp) == nil or toNumber(target.hp) <= 0 then
    runtime.targetTtdSamples = {}
    return
  end

  local currentTime = now()
  table.insert(runtime.targetTtdSamples, {
    hp = toNumber(target.hp) or 0,
    time = currentTime,
  })

  while #runtime.targetTtdSamples > 0 and (currentTime - runtime.targetTtdSamples[1].time) > 6 do
    table.remove(runtime.targetTtdSamples, 1)
  end

  if #runtime.targetTtdSamples < 2 then
    return
  end

  local first = runtime.targetTtdSamples[1]
  local last = runtime.targetTtdSamples[#runtime.targetTtdSamples]
  local deltaHp = (first.hp or 0) - (last.hp or 0)
  local deltaTime = (last.time or 0) - (first.time or 0)

  if deltaHp <= 0 or deltaTime <= 0 then
    return
  end

  local dps = deltaHp / deltaTime
  if dps <= 0 then
    return
  end

  target.ttd = (toNumber(target.hp) or 0) / dps
  target.ttdText = formatCompactSeconds(target.ttd)
end

local function buildDirectSnapshot(reason)
  local currentTime = now()
  local playerId = safeUnitLookup("player")
  local targetId = safeUnitLookup("player.target")
  local playerDetail = safeUnitDetail("player")
  local targetDetail = targetId and safeUnitDetail(targetId) or nil
  local player = readUnit("player")
  local target = targetId and readUnit(targetId) or nil
  local playerStats = buildStatSnapshot()

  if target and player and player.coord and target.coord then
    target.distance = distance3d(
      player.coord.x, player.coord.y, player.coord.z,
      target.coord.x, target.coord.y, target.coord.z)
  end

  if target then
    updateTargetTtd(target)
  else
    runtime.targetTtdSamples = {}
  end

  -- NilRisk: player may be nil before player unit is available
  local coordDelta = buildCoordDelta(player and player.coord, currentTime)

  return {
    schemaVersion = 1,
    status = player and "ready" or "waiting-for-player",
    exportReason = tostring(reason or "unspecified"),
    generatedAtRealtime = currentTime,
    sourceMode = "DirectAPI",
    sourceAddon = "RiftAPI",
    sourceVersion = nil,
    exportAddon = addonIdentifier,
    exportVersion = addonVersion,
    playerId = copyString(playerId),
    targetId = copyString(targetId),
    hud = nil,
    player = player,
    target = target,
    orientationProbe = buildOrientationProbe(playerDetail, targetDetail, playerStats, nil, nil, playerId, targetId),
    playerBuffLines = buildBuffLines("player", false),
    playerDebuffLines = buildBuffLines("player", true),
    targetBuffLines = targetId and buildBuffLines(targetId, false) or {},
    targetDebuffLines = targetId and buildBuffLines(targetId, true) or {},
    playerStats = playerStats,
    playerCoordDelta = coordDelta,
    nearbyUnits = readNearbyUnits(playerId, targetId),
    partyUnits = readPartyMembers(),
  }
end

local function copyUnit(unit)
  if type(unit) ~= "table" then
    return nil
  end

  return {
    id = copyString(unit.id),
    name = copyString(unit.name),
    level = toNumber(unit.level),
    calling = copyString(unit.calling),
    guild = copyString(unit.guild),
    relation = copyString(unit.relation),
    role = copyString(unit.role),
    player = copyBoolean(unit.player),
    combat = copyBoolean(unit.combat),
    pvp = copyBoolean(unit.pvp),
    hp = toNumber(unit.hp),
    hpMax = toNumber(unit.hpMax),
    hpPct = toNumber(unit.hpPct),
    absorb = toNumber(unit.absorb),
    vitality = toNumber(unit.vitality),
    resourceKind = copyString(unit.resourceKind),
    resource = toNumber(unit.resource),
    resourceMax = toNumber(unit.resourceMax),
    resourcePct = toNumber(unit.resourcePct),
    mana = toNumber(unit.mana),
    manaMax = toNumber(unit.manaMax),
    energy = toNumber(unit.energy),
    energyMax = toNumber(unit.energyMax),
    power = toNumber(unit.power),
    charge = toNumber(unit.charge),
    chargeMax = toNumber(unit.chargeMax),
    chargePct = toNumber(unit.chargePct),
    planar = toNumber(unit.planar),
    planarMax = toNumber(unit.planarMax),
    planarPct = toNumber(unit.planarPct),
    combo = toNumber(unit.combo),
    zone = copyString(unit.zone),
    locationName = copyString(unit.locationName),
    coord = copyCoord(unit),
    distance = toNumber(unit.distance),
    ttd = toNumber(unit.ttd),
    ttdText = copyString(unit.ttdText),
    cast = copyCast(unit.cast),
  }
end

local function copyHud(hud)
  if type(hud) ~= "table" then
    return nil
  end

  return {
    visible = copyBoolean(hud.visible),
    locked = copyBoolean(hud.locked),
    showBuffPanel = copyBoolean(hud.showBuffPanel),
  }
end

local function getReaderBridgeState()
  if type(ReaderBridge) ~= "table" then
    return nil, nil
  end

  local bridgeState = ReaderBridge.State
  if type(bridgeState) ~= "table" then
    return ReaderBridge, nil
  end

  return ReaderBridge, bridgeState
end

local function ensureState()
  if type(ReaderBridgeExport_State) ~= "table" then
    ReaderBridgeExport_State = {}
  end

  state = ReaderBridgeExport_State
  state.schemaVersion = 1
  state.session = type(state.session) == "table" and state.session or {}
  state.current = type(state.current) == "table" and state.current or {}
  state.session.exportCount = toNumber(state.session.exportCount) or 0
  state.session.lastReason = copyString(state.session.lastReason) or "none"
  state.session.exportVersion = addonVersion
  return state
end

local function buildSnapshot(reason)
  local bridge, bridgeState = getReaderBridgeState()
  local generatedAt = now()

  if bridgeState == nil then
    return buildDirectSnapshot(reason)
  end

  runtime.lastBridgeSeenAt = generatedAt

  -- NilRisk: bridgeState.player may be nil if bridge state not yet populated
  local player = copyUnit(bridgeState.player)
  local playerStats = buildStatSnapshot()
  local coordDelta = buildCoordDelta(player and player.coord, generatedAt)

  return {
    schemaVersion = 1,
    status = "ready",
    exportReason = tostring(reason or "unspecified"),
    generatedAtRealtime = generatedAt,
    sourceMode = "ReaderBridge",
    sourceAddon = "ReaderBridge",
    sourceVersion = bridge and bridge.Const and bridge.Const.VERSION or nil,
    exportAddon = addonIdentifier,
    exportVersion = addonVersion,
    hud = copyHud(bridgeState.hud),
    player = player,
    target = copyUnit(bridgeState.target),
    orientationProbe = buildOrientationProbe(bridgeState.player, bridgeState.target, playerStats, bridgeState.player, bridgeState.target, player and player.id or safeUnitLookup("player"), bridgeState.target and bridgeState.target.id or safeUnitLookup("player.target")),
    playerBuffLines = copyList(bridgeState.playerBuffLines),
    playerDebuffLines = copyList(bridgeState.playerDebuffLines),
    targetBuffLines = copyList(bridgeState.targetBuffLines),
    targetDebuffLines = copyList(bridgeState.targetDebuffLines),
    playerStats = playerStats,
    playerCoordDelta = coordDelta,
    nearbyUnits = nil,
    partyUnits = readPartyMembers(),
  }
end

function Exporter.Refresh(reason, incrementCount)
  ensureState()

  local snapshot = buildSnapshot(reason)
  snapshot.playerBuffLineCount = listCount(snapshot.playerBuffLines)
  snapshot.playerDebuffLineCount = listCount(snapshot.playerDebuffLines)
  snapshot.targetBuffLineCount = listCount(snapshot.targetBuffLines)
  snapshot.targetDebuffLineCount = listCount(snapshot.targetDebuffLines)

  if incrementCount then
    state.session.exportCount = (toNumber(state.session.exportCount) or 0) + 1
  end

  snapshot.exportCount = state.session.exportCount
  state.current = snapshot
  state.session.lastReason = snapshot.exportReason
  state.session.lastExportAt = snapshot.generatedAtRealtime
  runtime.lastRefreshAt = snapshot.generatedAtRealtime or now()

  return snapshot
end

function Exporter.PrintStatus()
  ensureState()

  local snapshot = state.current
  if type(snapshot) ~= "table" then
    console("No export snapshot is available yet.", "#FFAA44")
    return
  end

  snapshot.playerBuffLineCount = listCount(snapshot.playerBuffLines)
  snapshot.playerDebuffLineCount = listCount(snapshot.playerDebuffLines)
  snapshot.targetBuffLineCount = listCount(snapshot.targetBuffLines)
  snapshot.targetDebuffLineCount = listCount(snapshot.targetDebuffLines)

  if snapshot.status ~= "ready" then
    console("Export not ready yet: " .. tostring(snapshot.status or "unknown"), "#FFAA44")
    return
  end

  local player = type(snapshot.player) == "table" and snapshot.player or {}
  local target = type(snapshot.target) == "table" and snapshot.target or {}

  console(string.format(
    "status=%s mode=%s exports=%s player=%s Lv%s target=%s reason=%s",
    tostring(snapshot.status or "unknown"),
    tostring(snapshot.sourceMode or "?"),
    tostring(snapshot.exportCount or state.session.exportCount or 0),
    tostring(player.name or "?"),
    tostring(player.level or "?"),
    tostring(target.name or "-"),
    tostring(snapshot.exportReason or state.session.lastReason or "unknown")),
    "#00CC88")
end

function Exporter.OnSlashCommand(args)
  local command = string.match(args or "", "^(%S+)")
  if command then
    command = string.lower(command)
  end

  if not command or command == "export" then
    Exporter.Refresh("slash.export", true)
    Exporter.PrintStatus()
    return
  end

  if command == "status" then
    Exporter.Refresh("slash.status", false)
    Exporter.PrintStatus()
    return
  end

  console("Commands: /rbx | export | status | help", "#66CCFF")
end

function Exporter.OnSavedVariablesLoad(addon)
  if addon ~= addonIdentifier then
    return
  end

  ensureState()
end

function Exporter.OnSavedVariablesSave(addon)
  if addon ~= addonIdentifier then
    return
  end

  ensureState()
  Exporter.Refresh("save-begin", true)
  ReaderBridgeExport_State = state
end

function Exporter.OnStartup()
  ensureState()
  runtime.started = true
  Exporter.Refresh("startup", true)
  console("Loaded. Use /rbx status or /rbx export.", "#00CC88")
end

function Exporter.OnUpdateEnd()
  if not runtime.started then
    return
  end

  local currentTime = now()
  if (currentTime - runtime.lastRefreshAt) < UPDATE_INTERVAL then
    return
  end

  Exporter.Refresh("heartbeat", false)
end

table.insert(Command.Slash.Register("rbx"), { Exporter.OnSlashCommand, addonIdentifier, "ReaderBridgeExport slash command" })

table.insert(Event.Addon.SavedVariables.Load.End, { Exporter.OnSavedVariablesLoad, addonIdentifier, "ReaderBridgeExport load saved variables" })
table.insert(Event.Addon.SavedVariables.Save.Begin, { Exporter.OnSavedVariablesSave, addonIdentifier, "ReaderBridgeExport save saved variables" })
table.insert(Event.Addon.Startup.End, { Exporter.OnStartup, addonIdentifier, "ReaderBridgeExport startup" })
table.insert(Event.System.Update.End, { Exporter.OnUpdateEnd, addonIdentifier, "ReaderBridgeExport update" })
