local addonInfo, privateVars = ...
privateVars = privateVars or {}

local addonIdentifier = (addonInfo and addonInfo.identifier) or "RiftReaderValidator"
local addonDisplayName = addonIdentifier

local DEFAULT_MAX_SAMPLES = 64
local DEFAULT_SHOW_WINDOW = true
local LOG_LIMIT = 4
local UI_REFRESH_INTERVAL = 0.5
local WINDOW_WIDTH = 560
local WINDOW_HEIGHT = 420
local CONTENT_WIDTH = 520
local LEFT_COLUMN_WIDTH = 236
local RIGHT_COLUMN_WIDTH = 244
local COLUMN_GAP = 24
local BUTTON_WIDTH = 100
local HIDE_BUTTON_WIDTH = 84
local DEFAULT_WINDOW_X = 420
local DEFAULT_WINDOW_Y = 220

local STATUS_COLOR = {
  good = { 0.16, 0.74, 0.28, 1 },
  warn = { 0.94, 0.74, 0.18, 1 },
  bad = { 0.85, 0.22, 0.22, 1 },
  neutral = { 0.35, 0.35, 0.35, 1 },
}

local Validator = {}
privateVars.Validator = Validator

local state = nil
local runtime = {
  context = nil,
  window = nil,
  content = nil,
  dragBar = nil,
  indicatorRows = {},
  labels = {},
  logLines = {},
  logBuffer = {},
  started = false,
  lastUiUpdate = 0,
  lastAutoCaptureAttempt = 0,
}

local function now()
  return Inspect.Time.Real() or 0
end

local function shallowCopy(source)
  local target = {}

  if type(source) ~= "table" then
    return target
  end

  for key, value in pairs(source) do
    if type(value) == "table" then
      local nested = {}

      for nestedKey, nestedValue in pairs(value) do
        nested[nestedKey] = nestedValue
      end

      target[key] = nested
    else
      target[key] = value
    end
  end

  return target
end

local function trimMessage(message, maxLength)
  local text = tostring(message or "")

  if string.len(text) <= maxLength then
    return text
  end

  return string.sub(text, 1, maxLength - 3) .. "..."
end

local function formatNumber(value)
  if value == nil then
    return "?"
  end

  return tostring(value)
end

local function isNumber(value)
  return type(value) == "number"
end

local function formatAge(seconds)
  if seconds == nil then
    return "n/a"
  end

  if seconds < 1 then
    return "<1s"
  end

  if seconds < 60 then
    return string.format("%ds", math.floor(seconds))
  end

  return string.format("%dm", math.floor(seconds / 60))
end

local function setBackgroundColor(frame, color)
  frame:SetBackgroundColor(color[1], color[2], color[3], color[4])
end

local function buildCoordSnapshot(details)
  if not details then
    return nil
  end

  if isNumber(details.coordX) and isNumber(details.coordY) and isNumber(details.coordZ) then
    return {
      x = details.coordX,
      y = details.coordY,
      z = details.coordZ,
    }
  end

  if type(details.coord) == "table" then
    return shallowCopy(details.coord)
  end

  return nil
end

local function formatCoordText(coord)
  if type(coord) ~= "table" then
    return nil
  end

  if isNumber(coord.x) and isNumber(coord.y) and isNumber(coord.z) then
    return string.format("%.1f, %.1f, %.1f", coord.x, coord.y, coord.z)
  end

  if isNumber(coord[1]) and isNumber(coord[2]) and isNumber(coord[3]) then
    return string.format("%.1f, %.1f, %.1f", coord[1], coord[2], coord[3])
  end

  return nil
end

local function buildResourceSummary(snapshot)
  local parts = {}

  if snapshot.health or snapshot.healthMax then
    table.insert(parts, string.format("Health %s/%s", formatNumber(snapshot.health), formatNumber(snapshot.healthMax)))
  end

  if snapshot.mana or snapshot.manaMax then
    table.insert(parts, string.format("Mana %s/%s", formatNumber(snapshot.mana), formatNumber(snapshot.manaMax)))
  elseif snapshot.energy or snapshot.energyMax then
    table.insert(parts, string.format("Energy %s/%s", formatNumber(snapshot.energy), formatNumber(snapshot.energyMax)))
  elseif snapshot.power ~= nil then
    table.insert(parts, string.format("Power %s", formatNumber(snapshot.power)))
  end

  if snapshot.charge or snapshot.chargeMax then
    table.insert(parts, string.format("Charge %s/%s", formatNumber(snapshot.charge), formatNumber(snapshot.chargeMax)))
  elseif snapshot.combo ~= nil then
    table.insert(parts, string.format("Combo %s", formatNumber(snapshot.combo)))
  end

  if #parts == 0 then
    return "No resource fields"
  end

  return trimMessage(table.concat(parts, "  "), 48)
end

local function buildReasonSummary(snapshot)
  local parts = {}

  if snapshot.role then
    table.insert(parts, "Role " .. tostring(snapshot.role))
  end

  if snapshot.reason then
    table.insert(parts, "Reason " .. tostring(snapshot.reason))
  end

  if #parts == 0 then
    return "Reason: n/a"
  end

  return trimMessage(table.concat(parts, "  "), 48)
end

local function buildZoneSummary(snapshot)
  local zoneText = snapshot.locationName or snapshot.zone or "unknown"
  local coordText = formatCoordText(snapshot.coord)

  if coordText then
    return trimMessage(string.format("%s @ %s", zoneText, coordText), 48)
  end

  return trimMessage(zoneText, 48)
end

local function pushLogLine(message)
  table.insert(runtime.logBuffer, 1, {
    at = now(),
    text = trimMessage(message, 96),
  })

  while #runtime.logBuffer > LOG_LIMIT do
    table.remove(runtime.logBuffer)
  end
end

local function createText(parent, name, fontSize, width, height)
  local text = UI.CreateFrame("Text", name, parent)
  text:SetFontSize(fontSize or 12)
  text:SetFontColor(1, 1, 1, 1)
  text:SetWordwrap(false)

  if width then
    text:SetWidth(width)
  end

  if height then
    text:SetHeight(height)
  end

  return text
end

local function createIndicatorRow(parent, key, label, point, anchorTarget, anchorPoint, x, y)
  local row = UI.CreateFrame("Frame", key .. "Row", parent)
  row:SetPoint(point, anchorTarget, anchorPoint, x or 0, y or 0)
  row:SetWidth(LEFT_COLUMN_WIDTH)
  row:SetHeight(22)

  row.light = UI.CreateFrame("Frame", key .. "Light", row)
  row.light:SetPoint("CENTERLEFT", row, "CENTERLEFT", 0, 0)
  row.light:SetWidth(12)
  row.light:SetHeight(12)
  setBackgroundColor(row.light, STATUS_COLOR.neutral)

  row.label = createText(row, key .. "Label", 12, 64, 20)
  row.label:SetPoint("CENTERLEFT", row.light, "CENTERRIGHT", 8, 0)
  row.label:SetFontColor(0.87, 0.87, 0.87, 1)
  row.label:SetText(label)

  row.value = createText(row, key .. "Value", 12, 148, 20)
  row.value:SetPoint("CENTERLEFT", row.label, "CENTERRIGHT", 8, 0)
  row.value:SetFontColor(1, 1, 1, 1)

  return row
end

local function setIndicator(row, color, value)
  if not row then
    return
  end

  setBackgroundColor(row.light, color)
  row.value:SetText(trimMessage(value or "", 34))
end

function Validator.EnsureState()
  if type(RiftReaderValidator_State) ~= "table" then
    RiftReaderValidator_State = {}
  end

  state = RiftReaderValidator_State

  if type(state.session) ~= "table" then
    state.session = {}
  end

  if type(state.settings) ~= "table" then
    state.settings = {}
  end

  if type(state.current) ~= "table" then
    state.current = {}
  end

  if type(state.samples) ~= "table" then
    state.samples = {}
  end

  if type(state.settings.maxSamples) ~= "number" or state.settings.maxSamples < 1 then
    state.settings.maxSamples = DEFAULT_MAX_SAMPLES
  end

  if type(state.settings.echoToConsole) ~= "boolean" then
    state.settings.echoToConsole = true
  end

  if type(state.settings.showWindow) ~= "boolean" then
    state.settings.showWindow = DEFAULT_SHOW_WINDOW
  end

  if type(state.settings.windowX) ~= "number" then
    state.settings.windowX = DEFAULT_WINDOW_X
  end

  if type(state.settings.windowY) ~= "number" then
    state.settings.windowY = DEFAULT_WINDOW_Y
  end

  if type(state.nextSequence) ~= "number" or state.nextSequence < 1 then
    state.nextSequence = #state.samples + 1
  end

  if type(state.session.startedAt) ~= "number" then
    state.session.startedAt = now()
  end
end

function Validator.Log(message)
  Validator.EnsureState()

  local text = tostring(message or "")
  pushLogLine(text)

  if state.settings.echoToConsole then
    print(string.format("[%s] %s", addonDisplayName, text))
  end

  Validator.UpdateUi(true)
end

function Validator.GetPlayerDetails()
  local playerUnit = Inspect.Unit.Lookup("player")

  if not playerUnit then
    return nil, nil
  end

  local details = Inspect.Unit.Detail(playerUnit)

  if type(details) ~= "table" then
    return nil, playerUnit
  end

  return details, playerUnit
end

function Validator.TrimSamples()
  while #state.samples > state.settings.maxSamples do
    table.remove(state.samples, 1)
  end
end

function Validator.FormatSnapshot(snapshot)
  return string.format(
    "sample #%s reason=%s name=%s level=%s health=%s/%s mana=%s/%s zone=%s",
    tostring(snapshot.sequence),
    tostring(snapshot.reason),
    tostring(snapshot.name),
    tostring(snapshot.level),
    tostring(snapshot.health),
    tostring(snapshot.healthMax),
    tostring(snapshot.mana),
    tostring(snapshot.manaMax),
    tostring(snapshot.locationName or snapshot.zone)
  )
end

function Validator.Capture(reason)
  Validator.EnsureState()

  local details, playerUnit = Validator.GetPlayerDetails()

  if not details then
    Validator.Log("Player unit is not currently available; snapshot skipped.")
    return nil
  end

  local snapshot = {
    sequence = state.nextSequence,
    reason = reason or "manual",
    capturedAt = now(),
    playerUnit = playerUnit,
    name = details.name,
    level = details.level,
    health = details.health,
    healthMax = details.healthMax,
    mana = details.mana,
    manaMax = details.manaMax,
    energy = details.energy,
    energyMax = details.energyMax,
    power = details.power,
    charge = details.charge,
    chargeMax = details.chargeMax,
    combo = details.combo,
    role = details.role,
    combat = details.combat,
    zone = details.zone,
    locationName = details.locationName,
    coord = buildCoordSnapshot(details),
  }

  state.nextSequence = state.nextSequence + 1
  state.current = shallowCopy(snapshot)
  table.insert(state.samples, snapshot)
  Validator.TrimSamples()

  state.session.lastCaptureAt = snapshot.capturedAt
  state.session.lastReason = snapshot.reason

  Validator.Log("Captured " .. Validator.FormatSnapshot(snapshot))
  return snapshot
end

function Validator.PlayerEventMatches(data)
  if type(data) ~= "table" then
    return false
  end

  local playerUnit = Inspect.Unit.Lookup("player")

  if not playerUnit then
    return false
  end

  return data[playerUnit] ~= nil
end

function Validator.CaptureIfPlayerChanged(reason, data)
  if Validator.PlayerEventMatches(data) then
    Validator.Capture(reason)
  end
end

function Validator.ClearSamples()
  Validator.EnsureState()
  state.samples = {}
  state.current = {}
  state.nextSequence = 1
  state.session.lastReason = "clear"
  state.session.lastCaptureAt = now()
  Validator.Log("Cleared validation history.")
end

function Validator.PrintStatus()
  Validator.EnsureState()

  local lastSequence = "none"
  local sampleCount = #state.samples

  if sampleCount > 0 then
    lastSequence = tostring(state.samples[sampleCount].sequence)
  end

  Validator.Log(string.format(
    "Validator active. samples=%s lastSequence=%s maxSamples=%s window=%s",
    tostring(sampleCount),
    lastSequence,
    tostring(state.settings.maxSamples),
    tostring(state.settings.showWindow)
  ))
end

function Validator.PrintHelp()
  Validator.Log("Commands: /rrv snapshot | status | clear | ui | show | hide | help")
end

function Validator.SetWindowVisible(visible)
  Validator.EnsureState()
  state.settings.showWindow = visible and true or false

  if runtime.window then
    runtime.window:SetVisible(state.settings.showWindow)
  end

  Validator.UpdateUi(true)
end

function Validator.ToggleWindow()
  Validator.EnsureState()
  Validator.SetWindowVisible(not state.settings.showWindow)
  Validator.Log(state.settings.showWindow and "Status window shown." or "Status window hidden.")
end

local function beginDrag()
  local mouse = Inspect.Mouse()

  if not mouse or type(mouse.x) ~= "number" or type(mouse.y) ~= "number" then
    return
  end

  state.dragging = true
  state.dragOffsetX = mouse.x - runtime.window:GetLeft()
  state.dragOffsetY = mouse.y - runtime.window:GetTop()
end

local function endDrag()
  state.dragging = false
end

local function updateDrag()
  if not state.dragging or not runtime.window then
    return
  end

  local mouse = Inspect.Mouse()

  if not mouse or type(mouse.x) ~= "number" or type(mouse.y) ~= "number" then
    return
  end

  state.settings.windowX = mouse.x - state.dragOffsetX
  state.settings.windowY = mouse.y - state.dragOffsetY
  runtime.window:SetPoint("TOPLEFT", UIParent, "TOPLEFT", state.settings.windowX, state.settings.windowY)
end

function Validator.CreateUi()
  Validator.EnsureState()

  if runtime.window then
    return
  end

  runtime.context = UI.CreateContext("RiftReaderValidator")
  runtime.window = UI.CreateFrame("RiftWindow", "RiftReaderValidatorWindow", runtime.context)
  runtime.window:SetTitle("RiftReader Validator")
  runtime.window:SetPoint("TOPLEFT", UIParent, "TOPLEFT", state.settings.windowX, state.settings.windowY)
  runtime.window:SetWidth(WINDOW_WIDTH)
  runtime.window:SetHeight(WINDOW_HEIGHT)
  runtime.window:SetLayer(999999)
  runtime.window:SetVisible(state.settings.showWindow)

  runtime.dragBar = UI.CreateFrame("Frame", "RiftReaderValidatorDragBar", runtime.window)
  runtime.dragBar:SetPoint("TOPLEFT", runtime.window, "TOPLEFT", 14, 10)
  runtime.dragBar:SetWidth(WINDOW_WIDTH - 78)
  runtime.dragBar:SetHeight(34)
  runtime.dragBar:SetBackgroundColor(0, 0, 0, 0)

  runtime.dragBar:EventAttach(Event.UI.Input.Mouse.Left.Down, beginDrag, addonIdentifier .. "_DragStart")
  runtime.dragBar:EventAttach(Event.UI.Input.Mouse.Left.Up, endDrag, addonIdentifier .. "_DragStop")
  runtime.dragBar:EventAttach(Event.UI.Input.Mouse.Left.Upoutside, endDrag, addonIdentifier .. "_DragStopOutside")

  runtime.content = runtime.window:GetContent()
  runtime.content:SetBackgroundColor(0.05, 0.05, 0.05, 0.90)

  runtime.labels.subtitle = createText(runtime.content, "RiftReaderValidatorSubtitle", 12, CONTENT_WIDTH, 18)
  runtime.labels.subtitle:SetPoint("TOPLEFT", runtime.content, "TOPLEFT", 12, 12)
  runtime.labels.subtitle:SetFontColor(0.80, 0.86, 0.96, 1)

  runtime.labels.indicatorHeader = createText(runtime.content, "RiftReaderValidatorIndicatorHeader", 13, LEFT_COLUMN_WIDTH, 18)
  runtime.labels.indicatorHeader:SetPoint("TOPLEFT", runtime.labels.subtitle, "BOTTOMLEFT", 0, 12)
  runtime.labels.indicatorHeader:SetFontColor(1, 0.94, 0.60, 1)
  runtime.labels.indicatorHeader:SetText("Indicator lights")

  runtime.indicatorRows.addon = createIndicatorRow(runtime.content, "Addon", "Addon", "TOPLEFT", runtime.labels.indicatorHeader, "BOTTOMLEFT", 0, 10)
  runtime.indicatorRows.player = createIndicatorRow(runtime.content, "Player", "Player", "TOPLEFT", runtime.indicatorRows.addon, "BOTTOMLEFT", 0, 8)
  runtime.indicatorRows.capture = createIndicatorRow(runtime.content, "Capture", "Capture", "TOPLEFT", runtime.indicatorRows.player, "BOTTOMLEFT", 0, 8)
  runtime.indicatorRows.secure = createIndicatorRow(runtime.content, "Secure", "Secure", "TOPLEFT", runtime.indicatorRows.capture, "BOTTOMLEFT", 0, 8)

  runtime.labels.snapshotHeader = createText(runtime.content, "RiftReaderValidatorSnapshotHeader", 13, RIGHT_COLUMN_WIDTH, 18)
  runtime.labels.snapshotHeader:SetPoint("TOPLEFT", runtime.labels.indicatorHeader, "TOPRIGHT", COLUMN_GAP, 0)
  runtime.labels.snapshotHeader:SetFontColor(1, 0.94, 0.60, 1)
  runtime.labels.snapshotHeader:SetText("Current snapshot")

  runtime.labels.snapshotSummary = createText(runtime.content, "RiftReaderValidatorSnapshotSummary", 12, RIGHT_COLUMN_WIDTH, 20)
  runtime.labels.snapshotSummary:SetPoint("TOPLEFT", runtime.labels.snapshotHeader, "BOTTOMLEFT", 0, 10)

  runtime.labels.sampleCount = createText(runtime.content, "RiftReaderValidatorSampleCount", 12, RIGHT_COLUMN_WIDTH, 20)
  runtime.labels.sampleCount:SetPoint("TOPLEFT", runtime.labels.snapshotSummary, "BOTTOMLEFT", 0, 6)

  runtime.labels.zone = createText(runtime.content, "RiftReaderValidatorZone", 12, RIGHT_COLUMN_WIDTH, 20)
  runtime.labels.zone:SetPoint("TOPLEFT", runtime.labels.sampleCount, "BOTTOMLEFT", 0, 6)

  runtime.labels.resources = createText(runtime.content, "RiftReaderValidatorResources", 12, RIGHT_COLUMN_WIDTH, 20)
  runtime.labels.resources:SetPoint("TOPLEFT", runtime.labels.zone, "BOTTOMLEFT", 0, 6)

  runtime.labels.reason = createText(runtime.content, "RiftReaderValidatorReason", 12, RIGHT_COLUMN_WIDTH, 20)
  runtime.labels.reason:SetPoint("TOPLEFT", runtime.labels.resources, "BOTTOMLEFT", 0, 6)

  runtime.labels.activityHeader = createText(runtime.content, "RiftReaderValidatorActivityHeader", 13, CONTENT_WIDTH, 18)
  runtime.labels.activityHeader:SetPoint("TOPLEFT", runtime.indicatorRows.secure, "BOTTOMLEFT", 0, 26)
  runtime.labels.activityHeader:SetFontColor(1, 0.94, 0.60, 1)
  runtime.labels.activityHeader:SetText("Recent activity")

  local previous = runtime.labels.activityHeader

  for index = 1, LOG_LIMIT do
    local line = createText(runtime.content, "RiftReaderValidatorLog" .. index, 11, CONTENT_WIDTH, 18)
    line:SetPoint("TOPLEFT", previous, "BOTTOMLEFT", 0, 6)
    line:SetFontColor(0.86, 0.86, 0.86, 1)
    runtime.logLines[index] = line
    previous = line
  end

  runtime.snapshotButton = UI.CreateFrame("RiftButton", "RiftReaderValidatorSnapshotButton", runtime.window)
  runtime.snapshotButton:SetText("Snapshot")
  runtime.snapshotButton:SetWidth(BUTTON_WIDTH)
  runtime.snapshotButton:SetPoint("BOTTOMLEFT", runtime.content, "BOTTOMLEFT", 16, -4)

  function runtime.snapshotButton.Event:LeftPress()
    Validator.Capture("ui.snapshot")
  end

  runtime.refreshButton = UI.CreateFrame("RiftButton", "RiftReaderValidatorRefreshButton", runtime.window)
  runtime.refreshButton:SetText("Refresh")
  runtime.refreshButton:SetWidth(BUTTON_WIDTH)
  runtime.refreshButton:SetPoint("CENTERLEFT", runtime.snapshotButton, "CENTERRIGHT", 12, 0)

  function runtime.refreshButton.Event:LeftPress()
    Validator.Log("Manual refresh requested.")
    Validator.Capture("ui.refresh")
  end

  runtime.clearButton = UI.CreateFrame("RiftButton", "RiftReaderValidatorClearButton", runtime.window)
  runtime.clearButton:SetText("Clear")
  runtime.clearButton:SetWidth(BUTTON_WIDTH)
  runtime.clearButton:SetPoint("CENTERLEFT", runtime.refreshButton, "CENTERRIGHT", 12, 0)

  function runtime.clearButton.Event:LeftPress()
    Validator.ClearSamples()
  end

  runtime.hideButton = UI.CreateFrame("RiftButton", "RiftReaderValidatorHideButton", runtime.window)
  runtime.hideButton:SetText("Hide")
  runtime.hideButton:SetWidth(HIDE_BUTTON_WIDTH)
  runtime.hideButton:SetPoint("BOTTOMRIGHT", runtime.content, "BOTTOMRIGHT", -16, -4)

  function runtime.hideButton.Event:LeftPress()
    Validator.SetWindowVisible(false)
    Validator.Log("Status window hidden.")
  end
end

function Validator.UpdateUi(force)
  Validator.EnsureState()

  if not runtime.window then
    return
  end

  updateDrag()

  local currentTime = now()

  if not force and currentTime - runtime.lastUiUpdate < UI_REFRESH_INTERVAL then
    return
  end

  runtime.lastUiUpdate = currentTime
  runtime.window:SetVisible(state.settings.showWindow)

  local details, playerUnit = Validator.GetPlayerDetails()
  local latestSnapshot = state.current
  local snapshotExists = type(latestSnapshot) == "table" and latestSnapshot.sequence ~= nil
  local sampleCount = #state.samples
  local isSecure = Inspect.System.Secure and Inspect.System.Secure() or false

  runtime.labels.subtitle:SetText("Validator for the external memory reader")

  setIndicator(runtime.indicatorRows.addon, runtime.started and STATUS_COLOR.good or STATUS_COLOR.warn, runtime.started and "active" or "loading")

  if details then
    local playerText = string.format("%s Lv%s", trimMessage(details.name or playerUnit or "player", 15), formatNumber(details.level))
    setIndicator(runtime.indicatorRows.player, STATUS_COLOR.good, playerText)
  else
    setIndicator(runtime.indicatorRows.player, STATUS_COLOR.bad, "unavailable")
  end

  if details and not snapshotExists and (currentTime - runtime.lastAutoCaptureAttempt) >= 2 then
    runtime.lastAutoCaptureAttempt = currentTime
    Validator.Capture("auto.available")
    return
  end

  if snapshotExists then
    local captureAge = currentTime - (latestSnapshot.capturedAt or currentTime)
    local captureColor = STATUS_COLOR.good

    if captureAge >= 15 then
      captureColor = STATUS_COLOR.warn
    end

    if captureAge >= 60 then
      captureColor = STATUS_COLOR.bad
    end

    setIndicator(
      runtime.indicatorRows.capture,
      captureColor,
      string.format("#%s %s ago", tostring(latestSnapshot.sequence), formatAge(captureAge))
    )
  else
    setIndicator(runtime.indicatorRows.capture, STATUS_COLOR.bad, "no samples")
  end

  if isSecure then
    setIndicator(runtime.indicatorRows.secure, STATUS_COLOR.bad, "secure mode")
  else
    setIndicator(runtime.indicatorRows.secure, STATUS_COLOR.good, "normal mode")
  end

  if snapshotExists then
    runtime.labels.snapshotSummary:SetText(string.format(
      "Player: %s (Lv%s)",
      trimMessage(latestSnapshot.name or "?", 22),
      formatNumber(latestSnapshot.level)
    ))

    runtime.labels.sampleCount:SetText(string.format(
      "Samples: %s   Last: #%s",
      tostring(sampleCount),
      tostring(latestSnapshot.sequence)
    ))

    runtime.labels.zone:SetText(string.format(
      "Zone: %s",
      buildZoneSummary(latestSnapshot)
    ))

    runtime.labels.resources:SetText(string.format(
      "%s",
      buildResourceSummary(latestSnapshot)
    ))

    runtime.labels.reason:SetText(string.format(
      "%s",
      buildReasonSummary(latestSnapshot)
    ))
  else
    runtime.labels.snapshotSummary:SetText("Player: no snapshot yet")
    runtime.labels.sampleCount:SetText(string.format("Samples: %s", tostring(sampleCount)))
    runtime.labels.zone:SetText("Zone: n/a")
    runtime.labels.resources:SetText("Health n/a   Mana n/a")
    runtime.labels.reason:SetText("Reason: n/a")
  end

  for index = 1, LOG_LIMIT do
    local entry = runtime.logBuffer[index]

    if entry then
      runtime.logLines[index]:SetText(string.format("%s  %s", formatAge(currentTime - entry.at), entry.text))
    else
      runtime.logLines[index]:SetText("")
    end
  end
end

function Validator.OnSlashCommand(args)
  local command = string.match(args or "", "^(%S+)")

  if command then
    command = string.lower(command)
  end

  if not command or command == "snapshot" then
    Validator.Capture("slash.snapshot")
    return
  end

  if command == "status" or command == "refresh" then
    Validator.PrintStatus()
    Validator.UpdateUi(true)
    return
  end

  if command == "clear" then
    Validator.ClearSamples()
    return
  end

  if command == "ui" then
    Validator.ToggleWindow()
    return
  end

  if command == "show" then
    Validator.SetWindowVisible(true)
    Validator.Log("Status window shown.")
    return
  end

  if command == "hide" then
    Validator.SetWindowVisible(false)
    Validator.Log("Status window hidden.")
    return
  end

  Validator.PrintHelp()
end

function Validator.OnSavedVariablesLoad(addon)
  if addon ~= addonIdentifier then
    return
  end

  Validator.EnsureState()
  state.session.lastLoadedAt = now()
end

function Validator.OnSavedVariablesSave(addon)
  if addon ~= addonIdentifier then
    return
  end

  Validator.EnsureState()
  RiftReaderValidator_State = state
end

function Validator.OnStartup()
  Validator.EnsureState()
  Validator.CreateUi()
  runtime.started = true
  Validator.Log("Loaded. Use /rrv snapshot to capture a validation sample or /rrv ui to toggle the window.")
  Validator.UpdateUi(true)
end

function Validator.OnUpdateBegin()
  if runtime.window then
    Validator.UpdateUi(false)
  end
end

table.insert(Command.Slash.Register("rrv"), { Validator.OnSlashCommand, addonIdentifier, "RiftReaderValidator slash command" })

table.insert(Event.Addon.SavedVariables.Load.End, { Validator.OnSavedVariablesLoad, addonIdentifier, "RiftReaderValidator load saved variables" })
table.insert(Event.Addon.SavedVariables.Save.Begin, { Validator.OnSavedVariablesSave, addonIdentifier, "RiftReaderValidator save saved variables" })
table.insert(Event.Addon.Startup.End, { Validator.OnStartup, addonIdentifier, "RiftReaderValidator startup" })

table.insert(Event.System.Update.Begin, { Validator.OnUpdateBegin, addonIdentifier, "RiftReaderValidator UI refresh" })

table.insert(Event.Unit.Detail.Zone, { function(data) Validator.CaptureIfPlayerChanged("event.zone", data) end, addonIdentifier, "RiftReaderValidator zone change" })
table.insert(Event.Unit.Detail.Role, { function(data) Validator.CaptureIfPlayerChanged("event.role", data) end, addonIdentifier, "RiftReaderValidator role change" })
table.insert(Event.Unit.Detail.Level, { function(data) Validator.CaptureIfPlayerChanged("event.level", data) end, addonIdentifier, "RiftReaderValidator level change" })

table.insert(Event.System.Secure.Enter, { function() Validator.Capture("event.secure_enter") end, addonIdentifier, "RiftReaderValidator secure enter" })
table.insert(Event.System.Secure.Leave, { function() Validator.Capture("event.secure_leave") end, addonIdentifier, "RiftReaderValidator secure leave" })
