# ReaderBridge Export

Helper addon that mirrors the live `ReaderBridge` telemetry state into
saved variables for the external `RiftReader` process.

## Purpose

`ReaderBridge` already maintains rich normalized player/target telemetry in
memory. This addon keeps a lightweight export snapshot in:

- `ReaderBridgeExport_State`

That snapshot can then be loaded by the C# reader from:

- `ReaderBridgeExport.lua`

## Slash commands

- `/rbx`
- `/rbx export`
- `/rbx status`
- `/rbx help`

## Notes

- This addon expects `ReaderBridge` to be installed and loaded.
- If `ReaderBridge` is missing, the export stays in a waiting state instead of
  throwing runtime errors.
- Like other Rift saved-variable workflows, disk persistence still depends on
  the game saving addon state.
