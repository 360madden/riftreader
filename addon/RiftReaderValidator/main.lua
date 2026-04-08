local addonInfo, privateVars = ...

local addonIdentifier = (addonInfo and addonInfo.identifier) or "RiftReaderValidator"
local addonDisplayName = addonIdentifier
local DEFAULT_MAX_SAMPLES = 64

local Validator = {}
privateVars.Validator = Validator

local state = nil

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

function Validator.Log(message)
  print(string.format("[%s] %s", addonDisplayName, tostring(message)))
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

  if type(state.nextSequence) ~= "number" or state.nextSequence < 1 then
    state.nextSequence = #state.samples + 1
  end

  if type(state.session.startedAt) ~= "number" then
    state.session.startedAt = Inspect.Time.Real()
  end
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
    capturedAt = Inspect.Time.Real(),
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
    coord = shallowCopy(details.coord),
  }

  state.nextSequence = state.nextSequence + 1
  state.current = shallowCopy(snapshot)
  table.insert(state.samples, snapshot)
  Validator.TrimSamples()

  state.session.lastCaptureAt = snapshot.capturedAt
  state.session.lastReason = snapshot.reason

  if state.settings.echoToConsole then
    Validator.Log(Validator.FormatSnapshot(snapshot))
  end

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
  state.session.lastCaptureAt = Inspect.Time.Real()
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
    "PTS-only validator active. samples=%s lastSequence=%s maxSamples=%s",
    tostring(sampleCount),
    lastSequence,
    tostring(state.settings.maxSamples)
  ))
end

function Validator.PrintHelp()
  Validator.Log("Commands: /rrv snapshot | status | clear | help")
end

function Validator.OnSlashCommand(args)
  local command = string.match(args or "", "^(%S+)")

  if not command or command == "snapshot" then
    Validator.Capture("slash.snapshot")
    return
  end

  if command == "status" then
    Validator.PrintStatus()
    return
  end

  if command == "clear" then
    Validator.ClearSamples()
    return
  end

  Validator.PrintHelp()
end

function Validator.OnSavedVariablesLoad(addon)
  if addon ~= addonIdentifier then
    return
  end

  Validator.EnsureState()
  state.session.lastLoadedAt = Inspect.Time.Real()
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
  Validator.Log("Loaded. Use /rrv snapshot to capture a validation sample.")
  Validator.Capture("startup")
end

table.insert(Command.Slash.Register("rrv"), { Validator.OnSlashCommand, addonIdentifier, "RiftReaderValidator slash command" })

table.insert(Event.Addon.SavedVariables.Load.End, { Validator.OnSavedVariablesLoad, addonIdentifier, "RiftReaderValidator load saved variables" })
table.insert(Event.Addon.SavedVariables.Save.Begin, { Validator.OnSavedVariablesSave, addonIdentifier, "RiftReaderValidator save saved variables" })
table.insert(Event.Addon.Startup.End, { Validator.OnStartup, addonIdentifier, "RiftReaderValidator startup" })

table.insert(Event.Unit.Detail.Zone, { function(data) Validator.CaptureIfPlayerChanged("event.zone", data) end, addonIdentifier, "RiftReaderValidator zone change" })
table.insert(Event.Unit.Detail.Role, { function(data) Validator.CaptureIfPlayerChanged("event.role", data) end, addonIdentifier, "RiftReaderValidator role change" })
table.insert(Event.Unit.Detail.Level, { function(data) Validator.CaptureIfPlayerChanged("event.level", data) end, addonIdentifier, "RiftReaderValidator level change" })

table.insert(Event.System.Secure.Enter, { function() Validator.Capture("event.secure_enter") end, addonIdentifier, "RiftReaderValidator secure enter" })
table.insert(Event.System.Secure.Leave, { function() Validator.Capture("event.secure_leave") end, addonIdentifier, "RiftReaderValidator secure leave" })
