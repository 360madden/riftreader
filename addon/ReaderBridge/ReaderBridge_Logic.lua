--[[
================================================================================
SCRIPT: ReaderBridge_Logic.lua
VERSION: 1.0.2
TOTAL_CHARACTERS: 20063
PURPOSE:
    Telemetry cache / business logic for ReaderBridge.

    This file owns:
      - live player + target snapshot collection
      - castbar reads
      - buff/debuff tracking
      - target distance calculation
      - target time-to-death estimation
      - dirty-state management for ultra-low-latency UI refreshes

DESIGN:
    - Event driven where possible.
    - Lightweight heartbeat for countdowns, target polling, and fallback resync.
    - Avoids rebuilding large tables every frame.
================================================================================
]]

ReaderBridge = ReaderBridge or {}
local RB = ReaderBridge
RB.Logic = RB.Logic or {}

local Logic = RB.Logic
local Safe = RB.Safe
local Util = RB.Util
local Const = RB.Const

local function BlankCast()
    return {
        active = false,
        abilityName = "",
        duration = 0,
        remaining = 0,
        channeled = false,
        uninterruptible = false,
        progressPct = 0,
        text = "-",
    }
end

local function BlankBuffStore()
    return {
        byId = {},
        buffs = {},
        debuffs = {},
        lastResyncAt = 0,
    }
end

local function BlankUnit()
    return {
        id = nil,
        name = "",
        level = "",
        calling = "",
        guild = "",
        relation = "",
        role = "",
        player = false,
        combat = false,
        aggro = nil,
        blocked = nil,
        marked = nil,
        tagged = nil,
        pvp = false,
        hp = 0,
        hpMax = 0,
        hpCap = 0,
        hpPct = 0,
        absorb = 0,
        vitality = nil,
        resourceKind = "",
        resource = 0,
        resourceMax = 0,
        resourcePct = 0,
        mana = 0,
        manaMax = 0,
        energy = 0,
        energyMax = 0,
        power = 0,
        charge = 0,
        chargeMax = 0,
        chargePct = 0,
        planar = 0,
        planarMax = 0,
        planarPct = 0,
        combo = 0,
        comboUnit = nil,
        mark = nil,
        coordX = nil,
        coordY = nil,
        coordZ = nil,
        distance = nil,
        ttd = nil,
        ttdText = "-",
        cast = BlankCast(),
    }
end

local function BuildState()
    return {
        ready = false,
        hud = {
            visible = true,
            locked = false,
            showBuffPanel = true,
        },
        tracked = {
            playerId = nil,
            targetId = nil,
        },
        player = BlankUnit(),
        target = BlankUnit(),
        buffs = {
            player = BlankBuffStore(),
            target = BlankBuffStore(),
        },
        playerBuffLines = {},
        playerDebuffLines = {},
        targetBuffLines = {},
        targetDebuffLines = {},
        targetTtdSamples = {},
        nextHeartbeatAt = 0,
        nextTargetPollAt = 0,
        nextBuffResyncAt = 0,
        nextUiRefreshAt = 0,
        nextTtdSampleAt = 0,
        forceUiRefresh = false,
    }
end

local function PrimaryResource(detail)
    if detail.manaMax and detail.manaMax > 0 then
        return "Mana", detail.mana or 0, detail.manaMax, Util.Percent(detail.mana or 0, detail.manaMax)
    end

    if detail.energyMax and detail.energyMax > 0 then
        return "Energy", detail.energy or 0, detail.energyMax, Util.Percent(detail.energy or 0, detail.energyMax)
    end

    if detail.power ~= nil then
        local maxValue = detail.powerMax or 100
        return "Power", detail.power or 0, maxValue, Util.Percent(detail.power or 0, maxValue)
    end

    if detail.chargeMax and detail.chargeMax > 0 then
        return "Charge", detail.charge or 0, detail.chargeMax, Util.Percent(detail.charge or 0, detail.chargeMax)
    end

    return "", 0, 0, 0
end

local function ReadCast(unitSpecOrId)
    local cast = Safe.UnitCastbar(unitSpecOrId)
    if type(cast) ~= "table" or not cast.duration or cast.duration <= 0 then
        return BlankCast()
    end

    local remaining = type(cast.remaining) == "number" and cast.remaining or 0
    local duration = type(cast.duration) == "number" and cast.duration or 0
    local progressPct = 0

    if duration > 0 then
        if cast.channeled then
            progressPct = Util.Clamp((remaining / duration) * 100, 0, 100)
        else
            progressPct = Util.Clamp(((duration - remaining) / duration) * 100, 0, 100)
        end
    end

    local mode = cast.channeled and "Channel" or "Cast"
    local interruptText = cast.uninterruptible and "Uninterruptible" or "Interruptible"

    return {
        active = true,
        abilityName = Util.Clean(cast.abilityName),
        duration = duration,
        remaining = remaining,
        channeled = cast.channeled and true or false,
        uninterruptible = cast.uninterruptible and true or false,
        progressPct = progressPct,
        text = mode
            .. ": " .. (Util.Clean(cast.abilityName) ~= "" and Util.Clean(cast.abilityName) or "-")
            .. " | " .. Util.FormatCompactSeconds(remaining)
            .. " / " .. Util.FormatCompactSeconds(duration)
            .. " | " .. interruptText,
    }
end

local function ReadUnit(unitSpecOrId)
    local detail = Safe.UnitDetail(unitSpecOrId)
    if type(detail) ~= "table" then
        return BlankUnit()
    end

    local resourceKind, resource, resourceMax, resourcePct = PrimaryResource(detail)
    local hp = detail.health or 0
    local hpMax = detail.healthMax or 0
    local charge = detail.charge or 0
    local chargeMax = detail.chargeMax or 0
    local planar = detail.planar or 0
    local planarMax = detail.planarMax or 0

    local unit = BlankUnit()
    unit.id = detail.id or unitSpecOrId
    unit.name = Util.Clean(detail.name)
    unit.level = Util.Clean(detail.level)
    unit.calling = Util.Clean(detail.calling)
    unit.guild = Util.Clean(detail.guild)
    unit.relation = Util.Clean(detail.relation)
    unit.role = Util.Clean(detail.role)
    unit.player = detail.player and true or false
    unit.combat = detail.combat and true or false
    unit.aggro = detail.aggro
    unit.blocked = detail.blocked
    unit.marked = detail.mark
    unit.tagged = detail.tagged
    unit.pvp = detail.pvp and true or false
    unit.hp = hp
    unit.hpMax = hpMax
    unit.hpCap = detail.healthCap or hpMax
    unit.hpPct = Util.Percent(hp, hpMax)
    unit.absorb = detail.absorb or 0
    unit.vitality = detail.vitality
    unit.resourceKind = resourceKind
    unit.resource = resource
    unit.resourceMax = resourceMax
    unit.resourcePct = resourcePct
    unit.mana = detail.mana or 0
    unit.manaMax = detail.manaMax or 0
    unit.energy = detail.energy or 0
    unit.energyMax = detail.energyMax or 0
    unit.power = detail.power or 0
    unit.charge = charge
    unit.chargeMax = chargeMax
    unit.chargePct = Util.Percent(charge, chargeMax)
    unit.planar = planar
    unit.planarMax = planarMax
    unit.planarPct = Util.Percent(planar, planarMax)
    unit.combo = detail.combo or 0
    unit.comboUnit = detail.comboUnit
    unit.mark = detail.mark
    unit.coordX = detail.coordX
    unit.coordY = detail.coordY
    unit.coordZ = detail.coordZ
    unit.cast = ReadCast(unitSpecOrId)

    return unit
end

local function NormalizeBuff(buffDetail)
    if type(buffDetail) ~= "table" then
        return nil
    end

    local flags = {}

    if buffDetail.debuff then table.insert(flags, "Debuff") end
    if buffDetail.curse then table.insert(flags, "Curse") end
    if buffDetail.disease then table.insert(flags, "Disease") end
    if buffDetail.poison then table.insert(flags, "Poison") end

    return {
        id = buffDetail.id,
        name = Util.Clean(buffDetail.name),
        remaining = buffDetail.remaining,
        duration = buffDetail.duration,
        stack = buffDetail.stack or 0,
        debuff = buffDetail.debuff and true or false,
        flags = flags,
    }
end

local function CompareBuffs(a, b)
    local aHasRemaining = type(a.remaining) == "number"
    local bHasRemaining = type(b.remaining) == "number"

    if aHasRemaining and bHasRemaining then
        if a.remaining ~= b.remaining then
            return a.remaining < b.remaining
        end
    elseif aHasRemaining ~= bHasRemaining then
        return aHasRemaining
    end

    if a.stack ~= b.stack then
        return a.stack > b.stack
    end

    return (a.name or "") < (b.name or "")
end

local function RebuildBuffLists(store)
    store.buffs = {}
    store.debuffs = {}

    for _, entry in pairs(store.byId) do
        if entry.debuff then
            table.insert(store.debuffs, entry)
        else
            table.insert(store.buffs, entry)
        end
    end

    table.sort(store.buffs, CompareBuffs)
    table.sort(store.debuffs, CompareBuffs)
end

local function ResyncBuffStore(unitSpecOrId, store, now)
    local buffIds = Safe.BuffList(unitSpecOrId)
    store.byId = {}

    if type(buffIds) ~= "table" then
        store.lastResyncAt = now or 0
        RebuildBuffLists(store)
        return
    end

    local details = Safe.BuffDetail(unitSpecOrId, buffIds)
    if type(details) == "table" then
        for buffId, buffDetail in pairs(details) do
            local entry = NormalizeBuff(buffDetail)
            if entry then
                store.byId[buffId] = entry
            end
        end
    end

    store.lastResyncAt = now or 0
    RebuildBuffLists(store)
end

local function ApplyBuffDelta(unitSpecOrId, store, buffMap, removeOnly, now)
    if type(buffMap) ~= "table" then
        ResyncBuffStore(unitSpecOrId, store, now)
        return
    end

    if removeOnly then
        for buffId in pairs(buffMap) do
            store.byId[buffId] = nil
        end
        store.lastResyncAt = now or 0
        RebuildBuffLists(store)
        return
    end

    local requested = {}
    for buffId in pairs(buffMap) do
        table.insert(requested, buffId)
    end

    if #requested == 0 then
        store.lastResyncAt = now or 0
        RebuildBuffLists(store)
        return
    end

    local details = Safe.BuffDetail(unitSpecOrId, requested)
    if type(details) == "table" then
        for buffId, buffDetail in pairs(details) do
            local entry = NormalizeBuff(buffDetail)
            if entry then
                store.byId[buffId] = entry
            end
        end
    else
        ResyncBuffStore(unitSpecOrId, store, now)
        return
    end

    store.lastResyncAt = now or 0
    RebuildBuffLists(store)
end

local function TruncateBuffList(source)
    local result = {}
    local maxRows = Const.MAX_BUFF_ROWS or 5

    if type(source) ~= "table" then
        return result
    end

    for index = 1, math.min(#source, maxRows) do
        local entry = source[index]
        local line = entry.name ~= "" and entry.name or "-"
        if entry.stack and entry.stack > 1 then
            line = line .. " x" .. tostring(entry.stack)
        end
        if type(entry.remaining) == "number" then
            line = line .. " | " .. Util.FormatCompactSeconds(entry.remaining)
        end
        if type(entry.flags) == "table" and #entry.flags > 0 then
            line = line .. " | " .. table.concat(entry.flags, "/")
        end
        table.insert(result, line)
    end

    while #result < maxRows do
        table.insert(result, "-")
    end

    return result
end

local function RefreshBuffLineCaches()
    Logic.State.playerBuffLines = TruncateBuffList(Logic.State.buffs.player.buffs)
    Logic.State.playerDebuffLines = TruncateBuffList(Logic.State.buffs.player.debuffs)
    Logic.State.targetBuffLines = TruncateBuffList(Logic.State.buffs.target.buffs)
    Logic.State.targetDebuffLines = TruncateBuffList(Logic.State.buffs.target.debuffs)
end

local function ResetTargetTtd()
    Logic.State.targetTtdSamples = {}
    Logic.State.target.ttd = nil
    Logic.State.target.ttdText = "-"
end

local function PushTtdSample(now, hp)
    local samples = Logic.State.targetTtdSamples

    table.insert(samples, { time = now, hp = hp })

    local cutoff = now - Const.TTD_WINDOW_SECONDS
    local trimmed = {}
    for _, sample in ipairs(samples) do
        if sample.time >= cutoff then
            table.insert(trimmed, sample)
        end
    end

    Logic.State.targetTtdSamples = trimmed
end

local function UpdateTargetTtd(now)
    local target = Logic.State.target
    if not target or target.hpMax <= 0 or target.hp <= 0 then
        target.ttd = nil
        target.ttdText = "-"
        return
    end

    if now < Logic.State.nextTtdSampleAt then
        return
    end
    Logic.State.nextTtdSampleAt = now + Const.TTD_SAMPLE_INTERVAL

    PushTtdSample(now, target.hp)

    local samples = Logic.State.targetTtdSamples
    if #samples < 2 then
        target.ttd = nil
        target.ttdText = "-"
        return
    end

    local first = samples[1]
    local last = samples[#samples]
    local deltaHp = first.hp - last.hp
    local deltaTime = last.time - first.time

    if deltaHp <= 0 or deltaTime <= 0 then
        target.ttd = nil
        target.ttdText = "-"
        return
    end

    local dps = deltaHp / deltaTime
    if dps <= 0 then
        target.ttd = nil
        target.ttdText = "-"
        return
    end

    local ttd = target.hp / dps
    target.ttd = ttd
    target.ttdText = Util.FormatSeconds(ttd)
end

local function RefreshTrackedIds()
    Logic.State.tracked.playerId = Safe.UnitLookup("player") or nil
    Logic.State.tracked.targetId = Safe.UnitLookup("player.target") or nil
end

local function UpdateDistance()
    local player = Logic.State.player
    local target = Logic.State.target

    target.distance = Util.Distance3D(
        player.coordX, player.coordY, player.coordZ,
        target.coordX, target.coordY, target.coordZ
    )
end

local function RefreshUnits(now, fullBuffResync)
    local oldTargetId = Logic.State.tracked.targetId

    RefreshTrackedIds()

    Logic.State.player = ReadUnit("player")
    Logic.State.player.id = Logic.State.tracked.playerId or Logic.State.player.id

    if Logic.State.tracked.targetId ~= oldTargetId then
        Logic.State.target = Logic.State.tracked.targetId and ReadUnit(Logic.State.tracked.targetId) or BlankUnit()
        Logic.State.target.id = Logic.State.tracked.targetId
        Logic.State.buffs.target = BlankBuffStore()
        ResetTargetTtd()
        fullBuffResync = true
    else
        Logic.State.target = Logic.State.tracked.targetId and ReadUnit(Logic.State.tracked.targetId) or BlankUnit()
        Logic.State.target.id = Logic.State.tracked.targetId
    end

    UpdateDistance()
    UpdateTargetTtd(now)

    if fullBuffResync then
        ResyncBuffStore("player", Logic.State.buffs.player, now)
        if Logic.State.tracked.targetId then
            ResyncBuffStore(Logic.State.tracked.targetId, Logic.State.buffs.target, now)
        else
            Logic.State.buffs.target = BlankBuffStore()
        end
        Logic.State.nextBuffResyncAt = now + Const.BUFF_RESYNC_INTERVAL
    end

    RefreshBuffLineCaches()
    Logic.State.forceUiRefresh = true
end

function Logic:IsReady()
    return Logic.State and Logic.State.ready == true
end

function Logic:Initialize()
    EnsureState()
end

function Logic:MarkDirty()
    local state = EnsureState()
    state.forceUiRefresh = true
end

function Logic:ShouldRefreshUI()
    local state = EnsureState()

    local now = Safe.FrameTime()
    if not state.forceUiRefresh then
        return false
    end

    if now < state.nextUiRefreshAt then
        return false
    end

    state.nextUiRefreshAt = now + Const.UI_REFRESH_INTERVAL
    return true
end

function Logic:ClearUIRefreshFlag()
    local state = EnsureState()
    state.forceUiRefresh = false
end

function Logic:FullRefresh(fullBuffResync)
    EnsureState()
    local now = Safe.FrameTime()
    RefreshUnits(now, fullBuffResync and true or false)
end

function Logic:ToggleHUD()
    local state = EnsureState()
    state.hud.visible = not state.hud.visible
    self:MarkDirty()
    Util.Console("HUD " .. (state.hud.visible and "shown." or "hidden."))
end

function Logic:ToggleLock()
    local state = EnsureState()
    state.hud.locked = not state.hud.locked
    self:MarkDirty()
    Util.Console("HUD drag " .. (state.hud.locked and "locked." or "unlocked."))
end

function Logic:ToggleBuffPanel()
    local state = EnsureState()
    state.hud.showBuffPanel = not state.hud.showBuffPanel
    self:MarkDirty()
    Util.Console("Buff panel " .. (state.hud.showBuffPanel and "shown." or "hidden."))
end

function Logic:OnTrackedUnitsChanged(units, reason)
    if type(units) ~= "table" then
        return
    end

    local state = EnsureState()
    local playerId = state.tracked.playerId
    local targetId = state.tracked.targetId

    if (playerId and units[playerId] ~= nil) or (targetId and units[targetId] ~= nil) then
        local now = Safe.FrameTime()
        RefreshUnits(now, false)
        return
    end

    if reason == "coord" and targetId == nil and playerId and units[playerId] ~= nil then
        local now = Safe.FrameTime()
        RefreshUnits(now, false)
    end
end

function Logic:OnCastbarEvent(units)
    if type(units) ~= "table" then
        return
    end

    local state = EnsureState()
    local playerId = state.tracked.playerId
    local targetId = state.tracked.targetId
    local touched = false

    if playerId and units[playerId] ~= nil then
        state.player.cast = ReadCast("player")
        touched = true
    end

    if targetId and units[targetId] ~= nil then
        state.target.cast = ReadCast(targetId)
        touched = true
    end

    if touched then
        self:MarkDirty()
    end
end

function Logic:OnBuffEvent(unit, buffs, reason)
    if not unit then
        return
    end

    local state = EnsureState()
    local now = Safe.FrameTime()
    local removeOnly = reason == "remove"

    if state.tracked.playerId and unit == state.tracked.playerId then
        ApplyBuffDelta("player", state.buffs.player, buffs, removeOnly, now)
        RefreshBuffLineCaches()
        self:MarkDirty()
    end

    if state.tracked.targetId and unit == state.tracked.targetId then
        ApplyBuffDelta(state.tracked.targetId, state.buffs.target, buffs, removeOnly, now)
        RefreshBuffLineCaches()
        self:MarkDirty()
    end
end

function Logic:OnHeartbeat()
    local state = EnsureState()

    local now = Safe.FrameTime()
    if now < state.nextHeartbeatAt then
        return
    end
    state.nextHeartbeatAt = now + Const.HEARTBEAT_INTERVAL

    local targetPolled = false
    if now >= state.nextTargetPollAt then
        state.nextTargetPollAt = now + Const.TARGET_POLL_INTERVAL
        local newTargetId = Safe.UnitLookup("player.target")
        if newTargetId ~= state.tracked.targetId then
            RefreshUnits(now, true)
            targetPolled = true
        end
    end

    if not targetPolled then
        state.player = ReadUnit("player")
        state.player.id = state.tracked.playerId or state.player.id

        if state.tracked.targetId then
            state.target = ReadUnit(state.tracked.targetId)
            state.target.id = state.tracked.targetId
        else
            state.target = BlankUnit()
        end

        UpdateDistance()
        UpdateTargetTtd(now)

        if now >= state.nextBuffResyncAt then
            ResyncBuffStore("player", state.buffs.player, now)
            if state.tracked.targetId then
                ResyncBuffStore(state.tracked.targetId, state.buffs.target, now)
            end
            state.nextBuffResyncAt = now + Const.BUFF_RESYNC_INTERVAL
        end

        self:MarkDirty()
    end

    RefreshBuffLineCaches()
end

-- End of script

local function EnsureState()
    if Logic.State and Logic.State.ready then
        return Logic.State
    end

    Logic.State = BuildState()
    RB.State = Logic.State
    Logic.State.ready = true
    return Logic.State
end

