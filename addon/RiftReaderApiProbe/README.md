# RiftReader API Probe

`RiftReaderApiProbe` is a small live addon probe for API-first coordinate
reacquisition after client updates.

## Purpose

- Read player coordinates from the in-game Rift API:
  `Inspect.Unit.Detail("player")`.
- Keep the result in live Lua runtime globals, not SavedVariables:
  - `RiftReaderApiProbe_State`
  - `RiftReaderApiProbe_Live`
- Provide a slash command for visual/manual confirmation:
  - `/rap coord`

## Live marker

`RiftReaderApiProbe_Live` is a compact marker string intended for future memory
scanning/parsing work:

```text
RRAPICOORD1|schema=1|seq=<n>|sampledAt=<Inspect.Time.Real>|source=rift-api|view=Inspect.Unit.Detail(player)|status=pass|x=<x>|y=<y>|z=<z>|...|savedVariablesUse=none
```

The marker includes a monotonically increasing `seq` and API timestamp so future
reader-side tooling can fail closed if the runtime payload is not advancing.

## Freshness boundary

This addon intentionally does **not** declare SavedVariables. Runtime globals are
live only while the addon is loaded in the current Rift session. Do not treat any
post-save file as live coordinate truth.

## Validation

From the RiftReader repo root:

```cmd
scripts\validate-addon.cmd
```

To load in a live Rift session, deploy the addon, then reload UI or restart the
client. Reloading UI is live game input and should be approved before an agent
sends it.
