# RIFT API Capabilities

This document lists **verified** RIFT API capabilities based on actual usage in the RiftReader addon layer.

**Last verified**: 2026-04-12 (via code audit of `addon/ReaderBridgeExport/main.lua` and `addon/RiftReaderValidator/main.lua`)

---

## Core Unit APIs

### Inspect.Unit.Lookup

```lua
local unitId = Inspect.Unit.Lookup("player")           -- Player unit ID
local unitId = Inspect.Unit.Lookup("player.target")    -- Current target unit ID
```

**Returns**: string unit ID, or `nil` if not available

---

### Inspect.Unit.Detail

```lua
local detail = Inspect.Unit.Detail(unitId)
```

**Returns**: Table with the following verified fields:

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unit ID string |
| `name` | string | Display name |
| `level` | number | Unit level |
| `calling` | string | Class archetype (e.g., "Warrior", "Mage") |
| `guild` | string | Guild name |
| `relation` | string | Relation to player ("ally", "enemy", etc.) |
| `role` | string | Combat role |
| `player` | boolean | True if player character |
| `combat` | boolean | True if in combat |
| `pvp` | boolean | True if in PvP |
| `health` | number | Current health |
| `healthMax` | number | Maximum health |
| `absorb` | number | Absorb shield value |
| `vitality` | number | Vitality stat |
| `mana` | number | Current mana |
| `manaMax` | number | Maximum mana |
| `energy` | number | Current energy |
| `energyMax` | number | Maximum energy |
| `power` | number | Power resource (some classes) |
| `charge` | number | Current charge |
| `chargeMax` | number | Maximum charge |
| `planar` | number | Planar attunement |
| `planarMax` | number | Maximum planar attunement |
| `combo` | number | Combo points |
| `zone` | string | Current zone name |
| `locationName` | string | Sub-zone/location name |
| `coordX` | number | X coordinate |
| `coordY` | number | Y coordinate |
| `coordZ` | number | Z coordinate |
| `dead` | boolean | True if dead |

---

### Inspect.Unit.List

```lua
local units = Inspect.Unit.List()
```

**Returns**: Table of visible unit IDs (keys only, values are `nil`)

Used for enumerating nearby units.

---

### Inspect.Unit.Castbar

```lua
local cast = Inspect.Unit.Castbar(unitId)
```

**Returns**: Table with cast information:

| Field | Type | Description |
|-------|------|-------------|
| `active` | boolean | True if casting |
| `abilityName` | string | Name of ability being cast |
| `duration` | number | Total cast duration (seconds) |
| `remaining` | number | Remaining cast time (seconds) |
| `channeled` | boolean | True if channeled cast |
| `uninterruptible` | boolean | True if cannot be interrupted |
| `progressPct` | number | Cast progress percentage |
| `text` | string | Formatted cast text |

---

## Buff APIs

### Inspect.Buff.List

```lua
local buffIds = Inspect.Buff.List(unitId)
```

**Returns**: Table of buff IDs (keys only)

---

### Inspect.Buff.Detail

```lua
local buffs = Inspect.Buff.Detail(unitId, buffIds)
```

**Returns**: Table keyed by buff ID with:

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Buff name |
| `stack` | number | Stack count |
| `remaining` | number | Remaining duration (seconds) |
| `debuff` | boolean | True if debuff |

---

## Stat API

### Inspect.Stat

```lua
local stats = Inspect.Stat()
```

**Returns**: Table keyed by stat name (string keys, number values)

**Note**: Fields vary by class/build. The addon captures raw stats but does not normalize specific field names.

---

## System APIs

### Inspect.Time.Real

```lua
local time = Inspect.Time.Real()
```

**Returns**: Float clock (seconds since session start)

---

### Inspect.System.Secure

```lua
local isSecure = Inspect.System.Secure()
```

**Returns**: Boolean - `true` if in secure instance (raid, dungeon)

---

### Inspect.Mouse

```lua
local mouse = Inspect.Mouse()
```

**Returns**: Table with:

| Field | Type | Description |
|-------|------|-------------|
| `x` | number | Screen X coordinate |
| `y` | number | Screen Y coordinate |

---

## Event APIs

### Event Registration

```lua
Command.Event.Attach(event, handler, name)
```

**Note**: `name` must be unique per handler.

### Verified Events

| Event | Fires When |
|-------|------------|
| `Event.System.Update.Begin` | Every frame (before update) |
| `Event.System.Update.End` | Every frame (after update) |
| `Event.System.Secure.Enter` | Entering secure instance |
| `Event.System.Secure.Leave` | Leaving secure instance |
| `Event.Unit.Detail.Zone` | Player zone changes |
| `Event.Unit.Detail.Role` | Player role changes |
| `Event.Unit.Detail.Level` | Player level changes |
| `Event.Addon.Startup.End` | Addon finishes loading |
| `Event.Addon.SavedVariables.Load.End` | Saved variables loaded |
| `Event.Addon.SavedVariables.Save.Begin` | Before saved variables save |

---

## UI APIs

### UI.CreateContext

```lua
local context = UI.CreateContext(name)
```

Creates a UI context for addon frames.

---

### UI.CreateFrame

```lua
local frame = UI.CreateFrame(type, name, parent)
```

**Types**: `"Text"`, `"Frame"`, `"RiftButton"`, `"RiftWindow"`, etc.

---

## Command APIs

### Command.Console.Display

```lua
Command.Console.Display(channel, showPrefix, message, showInChat)
```

Displays a message in the game console.

---

### Command.Slash.Register

```lua
local handlers = Command.Slash.Register(cmd)
```

Registers a slash command. Returns a table to insert handlers into.

**Usage**:
```lua
table.insert(Command.Slash.Register("mycmd"), { handlerFunction, addonId, "Description" })
```

---

## Not Exposed / Unverified

The following APIs are **NOT** verified in the current addon codebase:

| API | Status |
|-----|--------|
| `Inspect.Unit.Heading()` | Not used - facing derived from memory basis matrix |
| `Inspect.Unit.Pitch()` | Not used |
| `Inspect.Unit.Gear()` | Not used |
| `Inspect.Unit.GearScore()` | Not used |
| `Inspect.Zone.ID()` | Not used |
| `Inspect.Map.ID()` | Not used |
| `Inspect.Unit.Target()` | Not used |
| `Inspect.Unit.Cooldown()` | Not used |

---

## Addon Slash Commands

### RiftReaderValidator (`/rrv`)

| Command | Action |
|---------|--------|
| `/rrv snapshot` | Manual snapshot capture |
| `/rrv status` | Print status to console |
| `/rrv clear` | Clear sample history |
| `/rrv ui` | Toggle status window |
| `/rrv show` | Show status window |
| `/rrv hide` | Hide status window |
| `/rrv help` | Show help |

### ReaderBridgeExport (`/rbx`)

| Command | Action |
|---------|--------|
| `/rbx` or `/rbx export` | Force export refresh |
| `/rbx status` | Print export status |
| `/rbx help` | Show help |

---

## Saved Variable Tables

### RiftReaderValidator_State

```lua
RiftReaderValidator_State = {
  session = {
    startedAt = number,
    lastCaptureAt = number,
    lastReason = string,
  },
  settings = {
    maxSamples = number,       -- Default 64
    echoToConsole = boolean,
    showWindow = boolean,
    windowX = number,
    windowY = number,
  },
  current = { ... },           -- Latest snapshot
  samples = { ... },           -- Rolling history
  nextSequence = number,
}
```

### ReaderBridgeExport_State

```lua
ReaderBridgeExport_State = {
  schemaVersion = number,
  session = {
    exportCount = number,
    lastReason = string,
    lastExportAt = number,
    exportVersion = string,
  },
  current = { ... },           -- Latest export snapshot
}
```

---

## Export File Locations

Addons write to the RIFT saved variables folder:

```
<Rift Install>\Interface\SavedVariables\
├── RiftReaderValidator.lua
└── ReaderBridgeExport.lua
```

The C# reader loads these files to validate memory reads against API ground truth.
