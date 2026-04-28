RiftReaderFacingInstructionTrace = RiftReaderFacingInstructionTrace or {}

local function sanitize(value)
  if value == nil then
    return ""
  end

  value = tostring(value)
  value = value:gsub("[\r\n]", " ")
  return value
end

local function sanitizeTsv(value)
  if value == nil then
    return ""
  end

  value = sanitize(value)
  value = value:gsub("\t", " ")
  return value
end

local function tohex(value)
  if value == nil then
    return ""
  end

  return string.format("0x%X", value)
end

local function formatNumber(value)
  if value == nil or value ~= value or value == math.huge or value == -math.huge then
    return ""
  end

  return string.format("%.9f", value)
end

local function writeStatus(state)
  local handle, err = io.open(state.outputFile, "w")
  if not handle then
    return false, err
  end

  local function writePair(key, value)
    handle:write(key, "=", sanitize(value), "\n")
  end

  writePair("status", state.status)
  writePair("stage", state.stage)
  writePair("processName", state.processName)
  writePair("targetAddress", tohex(state.targetAddress))
  writePair("basisOffset", tohex(state.basisOffset))
  writePair("maxHits", state.maxHits or 0)
  writePair("stopOnPlausible", tostring(state.stopOnPlausible == true))
  writePair("hitCount", state.hitCount or 0)
  writePair("plausibleHitCount", state.plausibleHitCount or 0)
  writePair("error", state.error)
  writePair("lastSourceBase", state.lastSourceBase)
  writePair("lastRip", state.lastRip)
  writePair("lastInstruction", state.lastInstruction)
  writePair("lastModuleName", state.lastModuleName)
  writePair("lastModuleOffset", state.lastModuleOffset)
  writePair("lastBasisPass", state.lastBasisPass)
  writePair("savedAtUtc", os.date("!%Y-%m-%dT%H:%M:%SZ"))
  handle:close()
  return true
end

local function writeHitsHeader(hitsFile)
  local handle, err = io.open(hitsFile, "w")
  if not handle then
    return false, err
  end

  handle:write("SavedAtUtc\tHitIndex\tRip\tInstruction\tModuleName\tModuleOffset\tRCX\tSourceBase\tR12\tRSI\tRDI\tForwardX\tForwardY\tForwardZ\tUpX\tUpY\tUpZ\tRightX\tRightY\tRightZ\tForwardMagnitude\tUpMagnitude\tRightMagnitude\tDotForwardUp\tDotForwardRight\tDotUpRight\tDeterminant\tBasisPass\n")
  handle:close()
  return true
end

local function appendHit(state, hit)
  local handle, err = io.open(state.hitsFile, "a")
  if not handle then
    return false, err
  end

  local values = {
    hit.SavedAtUtc,
    hit.HitIndex,
    hit.Rip,
    hit.Instruction,
    hit.ModuleName,
    hit.ModuleOffset,
    hit.RCX,
    hit.SourceBase,
    hit.R12,
    hit.RSI,
    hit.RDI,
    hit.ForwardX,
    hit.ForwardY,
    hit.ForwardZ,
    hit.UpX,
    hit.UpY,
    hit.UpZ,
    hit.RightX,
    hit.RightY,
    hit.RightZ,
    hit.ForwardMagnitude,
    hit.UpMagnitude,
    hit.RightMagnitude,
    hit.DotForwardUp,
    hit.DotForwardRight,
    hit.DotUpRight,
    hit.Determinant,
    hit.BasisPass
  }

  for index, value in ipairs(values) do
    if index > 1 then
      handle:write("\t")
    end

    handle:write(sanitizeTsv(value))
  end

  handle:write("\n")
  handle:close()
  return true
end

local function parseDisassembly(text)
  if text == nil then
    return nil, nil, nil, nil
  end

  local addressText, bytesText, opcodeAndExtra = text:match("^(.-)%s+%-%s+(.-)%s+%-%s+(.*)$")
  if addressText == nil then
    return nil, nil, text, nil
  end

  local opcodeText, extraText = opcodeAndExtra:match("^(.-)%s+:%s+(.*)$")
  if opcodeText == nil then
    opcodeText = opcodeAndExtra
  end

  return addressText, bytesText, opcodeText, extraText
end

local function resolveModule(address)
  local modules = enumModules()
  if modules == nil then
    return nil, nil, nil
  end

  for _, module in ipairs(modules) do
    local base = module.Address
    local size = module.Size or 0
    if base ~= nil and size ~= nil and address >= base and address < (base + size) then
      return module.Name, base, address - base
    end
  end

  return nil, nil, nil
end

local function waitForDebuggerReady(state, iterations)
  state.stage = "debug-ready"
  writeStatus(state)

  for _ = 1, iterations do
    if debug_canBreak() then
      return true
    end

    sleep(100)
  end

  return false
end

local function cleanupBreakpoint(state)
  if state ~= nil and state.breakpointSet and state.targetAddress ~= nil then
    pcall(function()
      debug_removeBreakpoint(state.targetAddress)
    end)
    state.breakpointSet = false
  end
end

local function finalizeState(state, status, stage)
  if state == nil then
    return 0
  end

  state.status = status or state.status or "collected"
  state.stage = stage or state.stage or "completed"
  writeStatus(state)
  cleanupBreakpoint(state)

  return 1
end

function RiftReaderFacingInstructionTrace.cleanup()
  local state = RiftReaderFacingInstructionTrace.state

  cleanupBreakpoint(state)

  if debug_isDebugging() then
    pcall(function()
      detachIfPossible()
    end)
  end

  RiftReaderFacingInstructionTrace.state = nil
  return 1
end

local function fail(state, stage, message)
  if state == nil then
    return 0
  end

  state.status = "error"
  state.stage = stage
  state.error = message
  writeStatus(state)
  cleanupBreakpoint(state)

  if debug_isDebugging() then
    pcall(function()
      detachIfPossible()
    end)
  end

  RiftReaderFacingInstructionTrace.state = nil
  return 0
end

local function readBasisTriplet(baseAddress, offset)
  if baseAddress == nil or baseAddress == 0 then
    return nil, nil, nil
  end

  return readFloat(baseAddress + offset), readFloat(baseAddress + offset + 4), readFloat(baseAddress + offset + 8)
end

local function computeMagnitude(x, y, z)
  if x == nil or y == nil or z == nil then
    return nil
  end

  return math.sqrt((x * x) + (y * y) + (z * z))
end

local function computeDot(ax, ay, az, bx, by, bz)
  if ax == nil or ay == nil or az == nil or bx == nil or by == nil or bz == nil then
    return nil
  end

  return (ax * bx) + (ay * by) + (az * bz)
end

local function computeDeterminant(fx, fy, fz, ux, uy, uz, rx, ry, rz)
  if fx == nil or fy == nil or fz == nil or ux == nil or uy == nil or uz == nil or rx == nil or ry == nil or rz == nil then
    return nil
  end

  return
    (fx * ((uy * rz) - (uz * ry))) -
    (fy * ((ux * rz) - (uz * rx))) +
    (fz * ((ux * ry) - (uy * rx)))
end

local function isBasisPlausible(forwardMagnitude, upMagnitude, rightMagnitude, dotForwardUp, dotForwardRight, dotUpRight, determinant)
  if forwardMagnitude == nil or upMagnitude == nil or rightMagnitude == nil or determinant == nil then
    return false
  end

  if forwardMagnitude < 0.80 or forwardMagnitude > 1.20 then
    return false
  end

  if upMagnitude < 0.80 or upMagnitude > 1.20 then
    return false
  end

  if rightMagnitude < 0.80 or rightMagnitude > 1.20 then
    return false
  end

  if dotForwardUp == nil or math.abs(dotForwardUp) > 0.15 then
    return false
  end

  if dotForwardRight == nil or math.abs(dotForwardRight) > 0.15 then
    return false
  end

  if dotUpRight == nil or math.abs(dotUpRight) > 0.15 then
    return false
  end

  return math.abs(math.abs(determinant) - 1.0) <= 0.20
end

function RiftReaderFacingInstructionTrace.arm(processTarget, targetAddress, outputFile, hitsFile, basisOffset, maxHits, stopOnPlausible)
  RiftReaderFacingInstructionTrace.cleanup()

  local state = {
    status = "armed",
    stage = "initializing",
    processName = tostring(processTarget),
    targetAddress = targetAddress,
    outputFile = outputFile,
    hitsFile = hitsFile,
    basisOffset = basisOffset or 0x60,
    maxHits = maxHits or 12,
    stopOnPlausible = stopOnPlausible == true,
    hitCount = 0,
    plausibleHitCount = 0,
    breakpointSet = false,
    error = ""
  }

  RiftReaderFacingInstructionTrace.state = state

  local headerOk, headerError = writeHitsHeader(state.hitsFile)
  if not headerOk then
    return fail(state, "prepare-hits", "Unable to write hits file: " .. tostring(headerError))
  end

  writeStatus(state)

  state.onBreakpoint = function()
    local current = RiftReaderFacingInstructionTrace.state
    if current == nil then
      debug_continueFromBreakpoint(co_run)
      return 1
    end

    if not current.breakpointSet then
      debug_continueFromBreakpoint(co_run)
      return 1
    end

    current.hitCount = (current.hitCount or 0) + 1

    local rip = RIP
    local instruction = disassemble(rip)
    local _, _, _, _ = parseDisassembly(instruction)
    local moduleName, _, moduleOffset = resolveModule(rip)

    local sourceBase = RCX
    local forwardX, forwardY, forwardZ = readBasisTriplet(sourceBase, current.basisOffset)
    local upX, upY, upZ = readBasisTriplet(sourceBase, current.basisOffset + 0x0C)
    local rightX, rightY, rightZ = readBasisTriplet(sourceBase, current.basisOffset + 0x18)

    local forwardMagnitude = computeMagnitude(forwardX, forwardY, forwardZ)
    local upMagnitude = computeMagnitude(upX, upY, upZ)
    local rightMagnitude = computeMagnitude(rightX, rightY, rightZ)
    local dotForwardUp = computeDot(forwardX, forwardY, forwardZ, upX, upY, upZ)
    local dotForwardRight = computeDot(forwardX, forwardY, forwardZ, rightX, rightY, rightZ)
    local dotUpRight = computeDot(upX, upY, upZ, rightX, rightY, rightZ)
    local determinant = computeDeterminant(forwardX, forwardY, forwardZ, upX, upY, upZ, rightX, rightY, rightZ)
    local basisPass = isBasisPlausible(forwardMagnitude, upMagnitude, rightMagnitude, dotForwardUp, dotForwardRight, dotUpRight, determinant)

    if basisPass then
      current.plausibleHitCount = (current.plausibleHitCount or 0) + 1
    end

    local hit = {
      SavedAtUtc = os.date("!%Y-%m-%dT%H:%M:%SZ"),
      HitIndex = current.hitCount,
      Rip = tohex(rip),
      Instruction = instruction,
      ModuleName = moduleName or "",
      ModuleOffset = moduleOffset and tohex(moduleOffset) or "",
      RCX = tohex(RCX),
      SourceBase = tohex(sourceBase),
      R12 = tohex(R12),
      RSI = tohex(RSI),
      RDI = tohex(RDI),
      ForwardX = formatNumber(forwardX),
      ForwardY = formatNumber(forwardY),
      ForwardZ = formatNumber(forwardZ),
      UpX = formatNumber(upX),
      UpY = formatNumber(upY),
      UpZ = formatNumber(upZ),
      RightX = formatNumber(rightX),
      RightY = formatNumber(rightY),
      RightZ = formatNumber(rightZ),
      ForwardMagnitude = formatNumber(forwardMagnitude),
      UpMagnitude = formatNumber(upMagnitude),
      RightMagnitude = formatNumber(rightMagnitude),
      DotForwardUp = formatNumber(dotForwardUp),
      DotForwardRight = formatNumber(dotForwardRight),
      DotUpRight = formatNumber(dotUpRight),
      Determinant = formatNumber(determinant),
      BasisPass = basisPass and "true" or "false"
    }

    local appendOk, appendError = appendHit(current, hit)
    if not appendOk then
      return fail(current, "append-hit", "Unable to append hit: " .. tostring(appendError))
    end

    current.lastSourceBase = hit.SourceBase
    current.lastRip = hit.Rip
    current.lastInstruction = hit.Instruction
    current.lastModuleName = hit.ModuleName
    current.lastModuleOffset = hit.ModuleOffset
    current.lastBasisPass = hit.BasisPass

    local terminalStatus = nil
    local terminalStage = nil
    if basisPass and current.stopOnPlausible then
      terminalStatus = "hit"
      terminalStage = "plausible-hit"
    elseif current.hitCount >= current.maxHits then
      terminalStatus = "collected"
      terminalStage = "max-hits"
    else
      current.stage = "collecting"
      writeStatus(current)
      debug_continueFromBreakpoint(co_run)
      return 1
    end

    finalizeState(current, terminalStatus, terminalStage)
    RiftReaderFacingInstructionTrace.state = nil
    debug_continueFromBreakpoint(co_run)
    return 1
  end

  local pid = processTarget
  if type(pid) ~= "number" then
    pid = getProcessIDFromProcessName(tostring(processTarget))
  end

  if pid == nil or pid == 0 then
    return fail(state, "resolve-process", "Unable to resolve process target: " .. tostring(processTarget))
  end

  local openOk, openError = pcall(openProcess, pid)
  if not openOk then
    return fail(state, "open-process", "openProcess failed: " .. tostring(openError))
  end

  if not debug_isDebugging() then
    local attachAttempts = {
      { label = "interface-2", invoke = function() return debugProcess(2) end },
      { label = "default", invoke = function() return debugProcess() end },
      { label = "interface-1", invoke = function() return debugProcess(1) end }
    }
    local attachErrors = {}
    local debuggerReady = false

    for _, attachAttempt in ipairs(attachAttempts) do
      state.stage = "debug-attach"
      writeStatus(state)
      local attachOk, attachError = pcall(attachAttempt.invoke)
      if not attachOk then
        table.insert(attachErrors, attachAttempt.label .. ": " .. tostring(attachError))
      elseif waitForDebuggerReady(state, 100) then
        debuggerReady = true
        break
      else
        table.insert(attachErrors, attachAttempt.label .. ": debugger not ready after 10000ms")
      end
    end

    if not debuggerReady then
      return fail(state, "debug-ready", "Debugger attach did not become ready. Attempts: " .. table.concat(attachErrors, "; "))
    end
  elseif not waitForDebuggerReady(state, 100) then
    return fail(state, "debug-ready", "Debugger was already active but did not become break-ready after 10000ms.")
  end

  state.stage = "breakpoint-set"
  local breakpointOk, breakpointError = pcall(function()
    debug_setBreakpoint(targetAddress, 1, bptExecute, bpmInt3, state.onBreakpoint)
  end)
  if not breakpointOk then
    return fail(state, "breakpoint-set", "debug_setBreakpoint failed: " .. tostring(breakpointError))
  end

  state.breakpointSet = true
  writeStatus(state)
  return 1
end

function RiftReaderFacingInstructionTrace.armAsync(processTarget, targetAddress, outputFile, hitsFile, basisOffset, maxHits, stopOnPlausible)
  createThread(function()
    local ok, err = pcall(RiftReaderFacingInstructionTrace.arm, processTarget, targetAddress, outputFile, hitsFile, basisOffset, maxHits, stopOnPlausible)
    if not ok then
      local state = {
        status = "error",
        stage = "exception",
        processName = tostring(processTarget),
        targetAddress = targetAddress,
        outputFile = outputFile,
        hitsFile = hitsFile,
        basisOffset = basisOffset,
        error = tostring(err)
      }

      writeStatus(state)
    end
  end)

  return 1
end
