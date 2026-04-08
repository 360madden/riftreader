if RiftReaderFloatScan == nil then
  RiftReaderFloatScan = {}
end

local state = {
  memscan = nil,
  foundlist = nil,
  processName = nil
}

local function rr_destroy_foundlist()
  if state.foundlist ~= nil then
    pcall(function() state.foundlist.deinitialize() end)
    pcall(function() state.foundlist.destroy() end)
    state.foundlist = nil
  end
end

local function rr_destroy_memscan()
  if state.memscan ~= nil then
    pcall(function() state.memscan.destroy() end)
    state.memscan = nil
  end
end

local function rr_format_float(value)
  return string.format("%.9f", tonumber(value) or 0)
end

function RiftReaderFloatScan.clear()
  rr_destroy_foundlist()
  rr_destroy_memscan()
  state.processName = nil
  return 1
end

function RiftReaderFloatScan.attach(processName)
  local pid = getProcessIDFromProcessName(processName)
  if pid == nil or pid == 0 then
    return 0
  end

  openProcess(pid)
  state.processName = processName
  return pid
end

function RiftReaderFloatScan.startExactFloat(processName, value)
  local pid = RiftReaderFloatScan.attach(processName)
  if pid == nil or pid == 0 then
    return 0
  end

  RiftReaderFloatScan.clear()
  state.processName = processName
  state.memscan = createMemScan()
  state.memscan.firstScan(
    soExactValue,
    vtSingle,
    rtRounded,
    rr_format_float(value),
    nil,
    0,
    0xffffffffffffffff,
    "",
    fsmAligned,
    "4",
    false,
    false,
    false,
    false
  )
  state.memscan.waitTillDone()

  state.foundlist = createFoundList(state.memscan)
  state.foundlist.initialize()
  return state.foundlist.Count
end

function RiftReaderFloatScan.nextExactFloat(value)
  if state.memscan == nil then
    return 0
  end

  if state.foundlist ~= nil then
    pcall(function() state.foundlist.deinitialize() end)
  end

  state.memscan.nextScan(
    soExactValue,
    rtRounded,
    rr_format_float(value),
    nil,
    false,
    false,
    false,
    false,
    false
  )
  state.memscan.waitTillDone()

  if state.foundlist == nil then
    state.foundlist = createFoundList(state.memscan)
  end

  state.foundlist.initialize()
  return state.foundlist.Count
end

function RiftReaderFloatScan.getCount()
  if state.foundlist == nil then
    return 0
  end

  return state.foundlist.Count
end

function RiftReaderFloatScan.getAddress(index)
  if state.foundlist == nil then
    return 0
  end

  if index < 0 or index >= state.foundlist.Count then
    return 0
  end

  local addressText = state.foundlist.Address[index]
  if addressText == nil then
    return 0
  end

  local addressValue = getAddressSafe(addressText)
  if addressValue == nil then
    return 0
  end

  return addressValue
end

function RiftReaderFloatScan.readScaledFloatAt(address, offset, scale)
  local value = readFloat(address + (offset or 0))
  if value == nil then
    return 0
  end

  scale = scale or 1000
  return math.floor((value * scale) + (value >= 0 and 0.5 or -0.5))
end

return RiftReaderFloatScan
