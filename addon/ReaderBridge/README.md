# ReaderBridge

Primary in-game bridge addon for the `RiftReader` project.

## Purpose

`ReaderBridge` publishes a fixed-size v3 payload into the Rift Lua heap:

- `ReaderBridge_v3`

The external reader scans that payload directly from the game process instead
of relying on saved variables. `ReaderBridgeExport` can still mirror the live
bridge state into `ReaderBridgeExport.lua` for offline inspection and
comparison workflows.

## Source of truth

This repo copy is intended to be the canonical tracked source for the live
`ReaderBridge` addon deployed into the Rift `Interface\AddOns` folder.

## Notes

- `RiftAddon.toc` currently loads `ReaderBridge.lua`.
- `ReaderBridge_Logic.lua` and `ReaderBridge_UI.lua` are preserved from the
  live addon folder as auxiliary source files, but they are not listed in the
  current startup manifest.
- Keep `RiftAddon.toc` and `ReaderBridge.lua` in sync with the deployed addon.
- Do not reorder protocol fields or change fixed-width sections casually; the
  external parser is offset-based.
- After Lua changes, run:
  - `C:\RIFT MODDING\RiftReader\scripts\validate-addon.cmd`
  - `C:\RIFT MODDING\RiftReader\scripts\deploy-addon.cmd`
