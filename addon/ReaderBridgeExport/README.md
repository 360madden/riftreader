# ReaderBridge Export

Helper addon that mirrors the live `ReaderBridge` telemetry state into
saved variables for the external `RiftReader` process.

## Purpose

`ReaderBridge` already maintains rich normalized player/target telemetry in
memory. This addon keeps a lightweight export snapshot in:

- `ReaderBridgeExport_State`

That snapshot can then be loaded by the C# reader from:

- `ReaderBridgeExport.lua`

The export also includes a few narrow down helpers such as buff/debuff line
counts, which can help the external reader rank or compare candidate memory
components against the live API-visible state.

## Slash commands

- `/rbx`
- `/rbx export`
- `/rbx status`
- `/rbx help`

## Notes

- This addon expects `ReaderBridge` to be installed and loaded.
- If `ReaderBridge` is missing, the addon falls back to a direct API snapshot
  built from the live `player` / `player.target` units. That fallback can still
  report a waiting status such as `waiting-for-player`, but it does not stay
  completely idle.
- Like other Rift saved-variable workflows, disk persistence still depends on
  the game saving addon state.
