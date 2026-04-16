--[[
================================================================================
SCRIPT: ReaderBridge_UI.lua
VERSION: 1.0.0
TOTAL_CHARACTERS: 22256
PURPOSE:
    Polished segmented HUD renderer for ReaderBridge telemetry.

    This file owns:
      - all frame creation
      - centered movable window
      - segmented status bars
      - toolbar buttons
      - self/target overview panels
      - buff/debuff list panels

GOALS:
    - readable at a glance
    - clean hierarchy
    - strong separation between rendering and telemetry logic
================================================================================
]]

ReaderBridge = ReaderBridge or {}
local RB = ReaderBridge
RB.UI = RB.UI or {}

local UIModule = RB.UI
local Safe = RB.Safe
local Util = RB.Util
local Const = RB.Const

local hudCtx
local frames = {}

local COLORS = {
    panelBg = { 0.06, 0.06, 0.08, 0.95 },
    panelBorder = { 0.18, 0.18, 0.24, 0.98 },
    titleBg = { 0.10, 0.12, 0.16, 0.98 },
    sectionTitle = { 0.78, 0.86, 1.00, 1.00 },
    text = { 0.96, 0.96, 0.98, 1.00 },
    subText = { 0.78, 0.80, 0.86, 1.00 },
    hp = { 0.20, 0.72, 0.28, 0.96 },
    resource = { 0.24, 0.52, 0.94, 0.96 },
    charge = { 0.90, 0.58, 0.14, 0.96 },
    planar = { 0.65, 0.30, 0.90, 0.96 },
    cast = { 0.18, 0.70, 0.90, 0.96 },
    channel = { 0.92, 0.74, 0.22, 0.96 },
    uninterruptible = { 0.72, 0.26, 0.92, 0.96 },
    flagOn = { 0.18, 0.55, 0.24, 0.98 },
    flagOff = { 0.20, 0.20, 0.26, 0.98 },
    flagWarn = { 0.72, 0.20, 0.20, 0.98 },
    tickMajor = { 1.00, 1.00, 1.00, 0.28 },
    tickMinor = { 1.00, 1.00, 1.00, 0.12 },
}

local function SetColor(frame, rgba)
    frame:SetBackgroundColor(rgba[1], rgba[2], rgba[3], rgba[4])
end

local function SetTextColor(frame, rgba)
    frame:SetFontColor(rgba[1], rgba[2], rgba[3], rgba[4])
end

local function CurrentWindowHeight()
    local state = RB.State
    if state and state.hud and state.hud.showBuffPanel then
        return Const.WINDOW_HEIGHT_WITH_BUFFS
    end
    return Const.WINDOW_HEIGHT_NO_BUFFS
end

local function CreateBorderedPanel(name, parent, width, height)
    local border = UI.CreateFrame("Frame", name .. "Border", parent)
    border:SetWidth(width)
    border:SetHeight(height)
    SetColor(border, COLORS.panelBorder)

    local fill = UI.CreateFrame("Frame", name .. "Fill", border)
    fill:SetPoint("TOPLEFT", border, "TOPLEFT", 1, 1)
    fill:SetWidth(width - 2)
    fill:SetHeight(height - 2)
    SetColor(fill, COLORS.panelBg)

    return border, fill
end

local function CreateLabel(name, parent, x, y, width, text, fontSize, color)
    local label = UI.CreateFrame("Text", name, parent)
    label:SetPoint("TOPLEFT", parent, "TOPLEFT", x, y)
    label:SetWidth(width)
    label:SetHeight(fontSize + 6)
    label:SetFontSize(fontSize)
    label:SetWordwrap(false)
    SetTextColor(label, color or COLORS.text)
    label:SetText(text or "")
    return label
end

local function CreateButton(name, parent, width, height, text, onClick)
    local border = UI.CreateFrame("Frame", name .. "Border", parent)
    border:SetWidth(width)
    border:SetHeight(height)
    SetColor(border, COLORS.panelBorder)

    local fill = UI.CreateFrame("Frame", name .. "Fill", border)
    fill:SetPoint("TOPLEFT", border, "TOPLEFT", 1, 1)
    fill:SetWidth(width - 2)
    fill:SetHeight(height - 2)
    SetColor(fill, { 0.14, 0.16, 0.20, 0.98 })

    local label = UI.CreateFrame("Text", name .. "Text", fill)
    label:SetPoint("CENTER", fill, "CENTER", 0, 0)
    label:SetWidth(width - 4)
    label:SetHeight(height - 2)
    label:SetFontSize(13)
    label:SetWordwrap(false)
    SetTextColor(label, COLORS.text)
    label:SetText(text)

    border:EventAttach(Event.UI.Input.Mouse.Left.Click, function()
        if type(onClick) == "function" then
            onClick()
        end
    end, name .. ".Click")

    return {
        border = border,
        fill = fill,
        label = label,
    }
end

local function CreateFlagBadge(name, parent, x, y, width)
    local badge = UI.CreateFrame("Frame", name .. "Bg", parent)
    badge:SetPoint("TOPLEFT", parent, "TOPLEFT", x, y)
    badge:SetWidth(width)
    badge:SetHeight(20)
    SetColor(badge, COLORS.flagOff)

    local text = UI.CreateFrame("Text", name .. "Text", badge)
    text:SetPoint("CENTER", badge, "CENTER", 0, 0)
    text:SetWidth(width - 4)
    text:SetHeight(18)
    text:SetFontSize(12)
    text:SetWordwrap(false)
    SetTextColor(text, COLORS.text)
    text:SetText("-")

    return {
        bg = badge,
        text = text,
    }
end

local function SetFlagBadge(badge, label, stateKind)
    badge.text:SetText(label)

    if stateKind == "on" then
        SetColor(badge.bg, COLORS.flagOn)
    elseif stateKind == "warn" then
        SetColor(badge.bg, COLORS.flagWarn)
    else
        SetColor(badge.bg, COLORS.flagOff)
    end
end

local function CreateSegmentedBar(name, parent, x, y, width, height, labelText)
    local label = CreateLabel(name .. "Label", parent, x, y, width, labelText, 14, COLORS.sectionTitle)

    local bg = UI.CreateFrame("Frame", name .. "Bg", parent)
    bg:SetPoint("TOPLEFT", parent, "TOPLEFT", x, y + 20)
    bg:SetWidth(width)
    bg:SetHeight(height)
    SetColor(bg, { 0.14, 0.14, 0.18, 0.98 })

    local fill = UI.CreateFrame("Frame", name .. "Fill", bg)
    fill:SetPoint("TOPLEFT", bg, "TOPLEFT", 1, 1)
    fill:SetHeight(height - 2)
    fill:SetWidth(0)
    SetColor(fill, COLORS.resource)

    local ticks = {}
    for index = 1, 19 do
        local tick = UI.CreateFrame("Frame", name .. "Tick" .. tostring(index), bg)
        local xPos = math.floor((width - 2) * (index / 20))
        tick:SetPoint("TOPLEFT", bg, "TOPLEFT", xPos, 0)
        tick:SetWidth(1)
        tick:SetHeight(height)
        SetColor(tick, (index % 2 == 0) and COLORS.tickMajor or COLORS.tickMinor)
        table.insert(ticks, tick)
    end

    local text = UI.CreateFrame("Text", name .. "Text", bg)
    text:SetPoint("CENTER", bg, "CENTER", 0, 0)
    text:SetWidth(width - 6)
    text:SetHeight(height - 2)
    text:SetFontSize(13)
    text:SetWordwrap(false)
    SetTextColor(text, COLORS.text)
    text:SetText("-")

    return {
        label = label,
        bg = bg,
        fill = fill,
        ticks = ticks,
        text = text,
        width = width,
        height = height,
    }
end

local function SetBar(bar, labelText, current, maximum, pct, text, rgba, hideWhenEmpty)
    bar.label:SetText(labelText or "")

    local shouldHide = hideWhenEmpty and (type(maximum) ~= "number" or maximum <= 0)
    bar.bg:SetVisible(not shouldHide)
    bar.label:SetVisible(not shouldHide)

    if shouldHide then
        return
    end

    local clampedPct = Util.Clamp(tonumber(pct) or 0, 0, 100)
    local fillWidth = math.floor(((bar.width - 2) * clampedPct) / 100)

    bar.fill:SetWidth(fillWidth)
    SetColor(bar.fill, rgba or COLORS.resource)
    bar.text:SetText(text or "-")
    bar.text:SetVisible(true)
end

local function CreateBuffColumn(name, parent, x, y, width, height, title)
    local border, fill = CreateBorderedPanel(name, parent, width, height)
    border:SetPoint("TOPLEFT", parent, "TOPLEFT", x, y)

    local header = CreateLabel(name .. "Header", fill, 8, 6, width - 16, title, 15, COLORS.sectionTitle)

    local lines = {}
    for index = 1, Const.MAX_BUFF_ROWS do
        local line = CreateLabel(
            name .. "Line" .. tostring(index),
            fill,
            8,
            30 + ((index - 1) * 30),
            width - 16,
            "-",
            13,
            COLORS.text
        )
        table.insert(lines, line)
    end

    return {
        border = border,
        fill = fill,
        header = header,
        lines = lines,
    }
end

local function CreateTelemetryPanel(name, parent, x, y, width, height, title)
    local border, fill = CreateBorderedPanel(name, parent, width, height)
    border:SetPoint("TOPLEFT", parent, "TOPLEFT", x, y)

    local titleLabel = CreateLabel(name .. "Title", fill, 10, 8, width - 20, title, 17, COLORS.sectionTitle)
    local meta1 = CreateLabel(name .. "Meta1", fill, 10, 36, width - 20, "-", 14, COLORS.text)
    local meta2 = CreateLabel(name .. "Meta2", fill, 10, 56, width - 20, "-", 13, COLORS.subText)
    local meta3 = CreateLabel(name .. "Meta3", fill, 10, 76, width - 20, "-", 13, COLORS.subText)

    local hpBar = CreateSegmentedBar(name .. "HP", fill, 10, 100, width - 20, 22, "HP")
    local resourceBar = CreateSegmentedBar(name .. "Resource", fill, 10, 146, width - 20, 22, "Resource")
    local auxBar1 = CreateSegmentedBar(name .. "Aux1", fill, 10, 192, width - 20, 20, "Charge")
    local auxBar2 = CreateSegmentedBar(name .. "Aux2", fill, 10, 232, width - 20, 20, "Planar")
    local castBar = CreateSegmentedBar(name .. "Cast", fill, 10, 272, width - 20, 22, "Cast")

    local flagBadges = {
        CreateFlagBadge(name .. "Flag1", fill, 10, height - 32, 82),
        CreateFlagBadge(name .. "Flag2", fill, 98, height - 32, 82),
        CreateFlagBadge(name .. "Flag3", fill, 186, height - 32, 82),
        CreateFlagBadge(name .. "Flag4", fill, 274, height - 32, 82),
        CreateFlagBadge(name .. "Flag5", fill, 362, height - 32, 82),
        CreateFlagBadge(name .. "Flag6", fill, 450, height - 32, 82),
    }

    return {
        border = border,
        fill = fill,
        title = titleLabel,
        meta1 = meta1,
        meta2 = meta2,
        meta3 = meta3,
        hpBar = hpBar,
        resourceBar = resourceBar,
        auxBar1 = auxBar1,
        auxBar2 = auxBar2,
        castBar = castBar,
        flags = flagBadges,
        width = width,
        height = height,
    }
end

local function GetCenteredTopLeft(width, height)
    local parentWidth = Safe.FrameValue(UIParent, "GetWidth")
    local parentHeight = Safe.FrameValue(UIParent, "GetHeight")

    if type(parentWidth) == "number" and type(parentHeight) == "number"
        and parentWidth > 0 and parentHeight > 0 then
        local x = math.floor((parentWidth - width) / 2)
        local y = math.floor((parentHeight - height) / 2)
        return x, y, true
    end

    return 0, 0, false
end

local function BuildFrames()
    hudCtx = UI.CreateContext("ReaderBridgeTelemetryHUD")
    frames.window = UI.CreateFrame("Frame", "RBHudWindow", hudCtx)
    frames.window:SetWidth(Const.WINDOW_WIDTH)
    frames.window:SetHeight(CurrentWindowHeight())
    SetColor(frames.window, { 0.02, 0.02, 0.03, 0.90 })
    frames.window:SetLayer(10)

    frames.title = UI.CreateFrame("Frame", "RBHudTitle", frames.window)
    frames.title:SetPoint("TOPLEFT", frames.window, "TOPLEFT", 0, 0)
    frames.title:SetWidth(Const.WINDOW_WIDTH)
    frames.title:SetHeight(36)
    SetColor(frames.title, COLORS.titleBg)
    frames.title:SetLayer(11)

    frames.titleText = UI.CreateFrame("Text", "RBHudTitleText", frames.title)
    frames.titleText:SetPoint("TOPLEFT", frames.title, "TOPLEFT", 12, 8)
    frames.titleText:SetWidth(380)
    frames.titleText:SetHeight(20)
    frames.titleText:SetFontSize(18)
    frames.titleText:SetWordwrap(false)
    SetTextColor(frames.titleText, COLORS.text)
    frames.titleText:SetText("ReaderBridge Telemetry HUD")

    frames.subtitleText = UI.CreateFrame("Text", "RBHudSubtitleText", frames.title)
    frames.subtitleText:SetPoint("TOPLEFT", frames.title, "TOPLEFT", 350, 10)
    frames.subtitleText:SetWidth(440)
    frames.subtitleText:SetHeight(18)
    frames.subtitleText:SetFontSize(12)
    frames.subtitleText:SetWordwrap(false)
    SetTextColor(frames.subtitleText, COLORS.subText)
    frames.subtitleText:SetText("Self / target telemetry | casts | buffs | TTD")

    frames.body = UI.CreateFrame("Frame", "RBHudBody", frames.window)
    frames.body:SetPoint("TOPLEFT", frames.window, "TOPLEFT", 0, 36)
    frames.body:SetWidth(Const.WINDOW_WIDTH)
    frames.body:SetHeight(CurrentWindowHeight() - 36)
    frames.body:SetLayer(11)

    frames.buttonLock = CreateButton("RBHudButtonLock", frames.title, 76, 22, "Lock", function()
        if RB.Logic then RB.Logic:ToggleLock() end
        if UIModule.Refresh then UIModule:Refresh(true) end
    end)
    frames.buttonLock.border:SetPoint("TOPLEFT", frames.title, "TOPLEFT", 860, 7)

    frames.buttonCenter = CreateButton("RBHudButtonCenter", frames.title, 76, 22, "Center", function()
        UIModule:Center()
        UIModule:Refresh(true)
    end)
    frames.buttonCenter.border:SetPoint("TOPLEFT", frames.title, "TOPLEFT", 942, 7)

    frames.buttonBuffs = CreateButton("RBHudButtonBuffs", frames.title, 92, 22, "Buffs", function()
        if RB.Logic then RB.Logic:ToggleBuffPanel() end
        if UIModule.Refresh then UIModule:Refresh(true) end
    end)
    frames.buttonBuffs.border:SetPoint("TOPLEFT", frames.title, "TOPLEFT", 1024, 7)

    local innerWidth = Const.WINDOW_WIDTH - (Const.WINDOW_PADDING * 2)
    local topPanelWidth = math.floor((innerWidth - Const.PANEL_GAP) / 2)

    frames.playerPanel = CreateTelemetryPanel(
        "RBPlayerPanel",
        frames.body,
        Const.WINDOW_PADDING,
        Const.WINDOW_PADDING,
        topPanelWidth,
        Const.TOP_PANEL_HEIGHT,
        "Self"
    )

    frames.targetPanel = CreateTelemetryPanel(
        "RBTargetPanel",
        frames.body,
        Const.WINDOW_PADDING + topPanelWidth + Const.PANEL_GAP,
        Const.WINDOW_PADDING,
        topPanelWidth,
        Const.TOP_PANEL_HEIGHT,
        "Target"
    )

    frames.buffPanelBorder, frames.buffPanelFill = CreateBorderedPanel(
        "RBBuffPanel",
        frames.body,
        innerWidth,
        Const.BUFF_PANEL_HEIGHT
    )
    frames.buffPanelBorder:SetPoint(
        "TOPLEFT",
        frames.body,
        "TOPLEFT",
        Const.WINDOW_PADDING,
        Const.WINDOW_PADDING + Const.TOP_PANEL_HEIGHT + Const.PANEL_GAP
    )

    frames.buffHeader = CreateLabel("RBBuffHeader", frames.buffPanelFill, 10, 8, innerWidth - 20, "Buff and Debuff Tracking", 16, COLORS.sectionTitle)

    local buffInnerWidth = innerWidth - 20
    local buffColumnWidth = math.floor((buffInnerWidth - (Const.PANEL_GAP * 3)) / 4)

    frames.playerBuffs = CreateBuffColumn("RBPlayerBuffs", frames.buffPanelFill, 10, 34, buffColumnWidth, 180, "Self Buffs")
    frames.playerDebuffs = CreateBuffColumn("RBPlayerDebuffs", frames.buffPanelFill, 10 + buffColumnWidth + Const.PANEL_GAP, 34, buffColumnWidth, 180, "Self Debuffs")
    frames.targetBuffs = CreateBuffColumn("RBTargetBuffs", frames.buffPanelFill, 10 + ((buffColumnWidth + Const.PANEL_GAP) * 2), 34, buffColumnWidth, 180, "Target Buffs")
    frames.targetDebuffs = CreateBuffColumn("RBTargetDebuffs", frames.buffPanelFill, 10 + ((buffColumnWidth + Const.PANEL_GAP) * 3), 34, buffColumnWidth, 180, "Target Debuffs")

    frames.title:EventAttach(Event.UI.Input.Mouse.Left.Down, function(self)
        local state = RB.State
        if not state or not state.hud or state.hud.locked then
            return
        end

        local mouse = Safe.Mouse()
        if type(mouse) ~= "table" then
            return
        end

        self.drag = true
        self.dragOffsetX = mouse.x - frames.window:GetLeft()
        self.dragOffsetY = mouse.y - frames.window:GetTop()
    end, "RBHud.DragStart")

    frames.title:EventAttach(Event.UI.Input.Mouse.Cursor.Move, function(self)
        if not self.drag then
            return
        end

        local mouse = Safe.Mouse()
        if type(mouse) ~= "table" then
            return
        end

        frames.window:ClearAll()
        frames.window:SetPoint("TOPLEFT", UIParent, "TOPLEFT", mouse.x - self.dragOffsetX, mouse.y - self.dragOffsetY)
    end, "RBHud.DragMove")

    frames.title:EventAttach(Event.UI.Input.Mouse.Left.Up, function(self)
        self.drag = false
    end, "RBHud.DragStop")
end

local function ApplyLines(column, lines)
    if not column or type(column.lines) ~= "table" then
        return
    end

    for index, lineFrame in ipairs(column.lines) do
        lineFrame:SetText((type(lines) == "table" and lines[index]) or "-")
    end
end

local function SetCastBar(bar, cast)
    if not cast or not cast.active then
        SetBar(bar, "Cast", 0, 100, 0, "-", COLORS.cast, false)
        return
    end

    local rgba = COLORS.cast
    if cast.channeled then
        rgba = COLORS.channel
    end
    if cast.uninterruptible then
        rgba = COLORS.uninterruptible
    end

    SetBar(bar, cast.channeled and "Channel" or "Cast", 0, 100, cast.progressPct, cast.text, rgba, false)
end

local function UpdatePanel(panel, unit, isTarget)
    if not panel or not unit then
        return
    end

    local displayName = unit.name ~= "" and unit.name or "-"
    local roleBits = {}

    if unit.level ~= "" then table.insert(roleBits, "Lv" .. unit.level) end
    if unit.calling ~= "" then table.insert(roleBits, unit.calling) end
    if unit.role ~= "" then table.insert(roleBits, string.upper(unit.role)) end
    if unit.relation ~= "" then table.insert(roleBits, unit.relation) end

    panel.meta1:SetText(displayName)
    panel.meta2:SetText(#roleBits > 0 and table.concat(roleBits, " | ") or "-")

    local line3Parts = {}
    if unit.guild ~= "" then table.insert(line3Parts, "Guild: " .. unit.guild) end
    if type(unit.coordX) == "number" and type(unit.coordY) == "number" and type(unit.coordZ) == "number" then
        table.insert(line3Parts, "XYZ " .. Util.FormatCoords(unit.coordX, unit.coordY, unit.coordZ))
    end
    if isTarget and type(unit.distance) == "number" then
        table.insert(line3Parts, "Distance " .. Util.FormatFloat(unit.distance, 2))
    end
    if isTarget and unit.ttdText and unit.ttdText ~= "-" then
        table.insert(line3Parts, "TTD " .. unit.ttdText)
    end
    panel.meta3:SetText(#line3Parts > 0 and table.concat(line3Parts, " | ") or "-")

    local hpText = Util.FormatInteger(unit.hp) .. " / " .. Util.FormatInteger(unit.hpMax) .. " (" .. tostring(unit.hpPct or 0) .. "%)"
    if unit.absorb and unit.absorb > 0 then
        hpText = hpText .. " | Absorb " .. Util.FormatInteger(unit.absorb)
    end
    SetBar(panel.hpBar, "HP", unit.hp, unit.hpMax, unit.hpPct, hpText, COLORS.hp, false)

    local resourceLabel = unit.resourceKind ~= "" and unit.resourceKind or "Resource"
    local resourceText = Util.FormatInteger(unit.resource) .. " / " .. Util.FormatInteger(unit.resourceMax) .. " (" .. tostring(unit.resourcePct or 0) .. "%)"
    SetBar(panel.resourceBar, resourceLabel, unit.resource, unit.resourceMax, unit.resourcePct, resourceText, COLORS.resource, true)

    local chargeText = Util.FormatInteger(unit.charge) .. " / " .. Util.FormatInteger(unit.chargeMax) .. " (" .. tostring(unit.chargePct or 0) .. "%)"
    local auxChargeMax = (unit.resourceKind == "Charge") and 0 or unit.chargeMax
    SetBar(panel.auxBar1, "Charge", unit.charge, auxChargeMax, unit.chargePct, chargeText, COLORS.charge, true)

    local planarText = Util.FormatInteger(unit.planar) .. " / " .. Util.FormatInteger(unit.planarMax) .. " (" .. tostring(unit.planarPct or 0) .. "%)"
    if unit.vitality ~= nil then
        planarText = planarText .. " | Vitality " .. tostring(unit.vitality)
    end
    if unit.combo and unit.combo > 0 then
        planarText = planarText .. " | Combo " .. tostring(unit.combo)
    end
    SetBar(panel.auxBar2, "Planar", unit.planar, unit.planarMax, unit.planarPct, planarText, COLORS.planar, true)

    SetCastBar(panel.castBar, unit.cast)

    SetFlagBadge(panel.flags[1], "Combat", unit.combat and "on" or "off")

    if unit.aggro == nil then
        SetFlagBadge(panel.flags[2], "Aggro ?", "off")
    else
        SetFlagBadge(panel.flags[2], "Aggro", unit.aggro and "warn" or "off")
    end

    if unit.blocked == nil then
        SetFlagBadge(panel.flags[3], "LOS ?", "off")
    else
        SetFlagBadge(panel.flags[3], unit.blocked and "Blocked" or "LOS", unit.blocked and "warn" or "on")
    end

    local markLabel = unit.marked and ("Mark " .. tostring(unit.marked)) or "Mark -"
    SetFlagBadge(panel.flags[4], markLabel, unit.marked and "on" or "off")

    local tagged = unit.tagged
    local taggedLabel = tagged and ("Tagged " .. tostring(tagged)) or "Tagged"
    SetFlagBadge(panel.flags[5], taggedLabel, tagged and "on" or "off")

    SetFlagBadge(panel.flags[6], unit.pvp and "PvP" or "PvE", unit.pvp and "warn" or "off")
end

local function LayoutVisibility()
    local state = RB.State
    local showBuffs = state and state.hud and state.hud.showBuffPanel

    frames.window:SetHeight(CurrentWindowHeight())
    frames.body:SetHeight(CurrentWindowHeight() - 36)
    frames.buffPanelBorder:SetVisible(showBuffs and true or false)
    frames.buffPanelFill:SetVisible(showBuffs and true or false)

    frames.buttonLock.label:SetText((state and state.hud and state.hud.locked) and "Unlock" or "Lock")
    frames.buttonBuffs.label:SetText(showBuffs and "Buffs On" or "Buffs Off")
end

function UIModule:IsReady()
    return frames.window ~= nil
end

function UIModule:Initialize()
    if self:IsReady() then
        return
    end

    BuildFrames()
end

function UIModule:Center()
    if not self:IsReady() then
        return
    end

    local height = CurrentWindowHeight()
    local x, y, useTopLeft = GetCenteredTopLeft(Const.WINDOW_WIDTH, height)

    frames.window:ClearAll()
    if useTopLeft then
        frames.window:SetPoint("TOPLEFT", UIParent, "TOPLEFT", x, y)
    else
        frames.window:SetPoint("CENTER", UIParent, "CENTER", 0, 0)
    end
end

function UIModule:Refresh(force)
    if not self:IsReady() then
        return
    end

    local state = RB.State
    if not state then
        return
    end

    LayoutVisibility()

    frames.window:SetVisible(state.hud.visible and true or false)
    frames.titleText:SetText("ReaderBridge Telemetry HUD v" .. tostring(Const.VERSION))

    UpdatePanel(frames.playerPanel, state.player, false)
    UpdatePanel(frames.targetPanel, state.target, true)

    ApplyLines(frames.playerBuffs, state.playerBuffLines)
    ApplyLines(frames.playerDebuffs, state.playerDebuffLines)
    ApplyLines(frames.targetBuffs, state.targetBuffLines)
    ApplyLines(frames.targetDebuffs, state.targetDebuffLines)

    if force then
        frames.window:SetVisible(state.hud.visible and true or false)
    end
end

-- End of script
