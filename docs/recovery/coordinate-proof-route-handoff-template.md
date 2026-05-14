# Coordinate Proof Route Handoff Template

Use this template whenever visual/capture artifacts, API-now references, memory
readbacks, or static-root candidates are handed off for coordinate-truth work.
It is intentionally proof-route first: screenshots and crops stay visible, but
they never become coordinate or movement truth by themselves.

## Required handoff fields

| Field | Value |
|---|---|
| Handoff timestamp UTC | `<YYYY-MM-DDTHH:MM:SSZ>` |
| Target process | `rift_x64` |
| Target PID | `<pid>` |
| Target HWND | `<0x...>` |
| Process start UTC | `<timestamp or unknown>` |
| Latest coordinate proof route JSON | `<scripts/captures/.../coordinate-proof-route.json>` |
| Latest coordinate proof route Markdown | `<scripts/captures/.../coordinate-proof-route.md>` |
| Latest coordinate proof route HTML | `<scripts/captures/.../coordinate-proof-route.html>` |
| Latest route pointer | `scripts/captures/latest-coordinate-proof-route.json` |
| Latest route status | `<api-memory-match \| candidate-only-stale-against-api-now \| reacquisition-no-current-hits \| ...>` |
| Latest API/runtime reference | `<scripts/captures/rift-api-reference-...json>` |
| Latest memory readback or reacquisition scan | `<scripts/captures/.../summary.json>` |
| Latest preflight using route | `<scripts/captures/coordinate-proof-preflight-.../summary.json>` |
| Latest milestone review using route | `<scripts/captures/riftscan-milestone-review-...json>` |
| Visual evidence manifest(s) | `<scripts/captures/.../manifest.json>` |
| Static-root summary candidates | `<scripts/captures/.../summary.json or none>` |
| Movement allowed | `false unless same-target proof gate passed and operator explicitly approved movement` |

## Verdict

- **Coordinate truth status:** `<current verdict>`
- **Movement status:** `<blocked / approved with proof gate>`
- **Main blocker(s):**
  - `<blocker>`
- **Important warning(s):**
  - `<warning>`

## Safety notes

- Visual capture, raw BGRA, crops, diffs, OCR, and screenshots are **sidecar
  evidence only**.
- SavedVariables files are **post-save snapshots only**, not live coordinate
  truth.
- A current target match is not enough: prove API-now versus memory-now deltas
  before promoting any coordinate candidate.
- No movement, input, CE, x64dbg attach, RiftScan provider write, or GitHub write
  is implied by this handoff.

## Recommended next action

`<one concrete next command or next safe proof step>`
