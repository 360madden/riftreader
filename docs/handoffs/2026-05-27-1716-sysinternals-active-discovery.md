# Sysinternals Active Discovery Handoff — PID 12148

## Verdict

Status: **blocked-safe / candidate-only**.

Sysinternals accelerated current no-debug evidence collection, but did not produce a static resolver/root. The actor/static pointer chain remains **not solved and not promoted**.

## Current target

| Field | Value |
|---|---|
| Process | `rift_x64.exe` |
| PID | `12148` |
| HWND | `0x640C0C` |
| Process start | `2026-05-27T01:17:01.265352Z` |
| Module base authority | `0x7FF77AF40000` from RiftReader target epoch |

## Key artifacts

| Artifact | Path |
|---|---|
| Sysinternals packet | `C:\RIFT MODDING\RiftReader\scripts\captures\sysinternals-discovery-packet-20260527-171348-285877\summary.json` |
| Active discovery merge packet | `C:\RIFT MODDING\RiftReader\scripts\captures\active-discovery-sysinternals-merge-12148-20260527-171449-920008\summary.json` |
| Current root signature | `C:\RIFT MODDING\RiftReader\scripts\captures\current-root-signature-from-owner-batch-12148-20260527-171112-137861\root-signature.json` |
| Root sweep batch | `C:\RIFT MODDING\RiftReader\scripts\captures\root-signature-batch-sweep-currentpid-12148-20260527-171144-735343\summary.json` |
| Latest owner-layout packet | `C:\RIFT MODDING\RiftReader\scripts\captures\owner-layout-comparison-packet-20260527-171505-737610\summary.json` |
| Owner batch source | `C:\RIFT MODDING\RiftReader\scripts\captures\pointer-owner-batch-currentpid-12148-20260527-150333-936569\summary.json` |

## Sysinternals findings

- Tools used from `C:\RIFT MODDING\Tools\SysinternalsSuite` with explicit absolute paths.
- `Listdlls64.exe` collected module inventory and found 101 modules, but reports the RIFT base as a low-32-bit/truncated value (`0x000000007af40000`), so it is supporting evidence only; the RiftReader target epoch module base remains authoritative.
- `handle64.exe` collected handle evidence and observed `\Sessions\1\BaseNamedObjects\Trion.Rift.DebugSection-12148`.
- `vmmap64.exe` was not run because non-interactive export behavior was not verified as safe/non-invasive.
- No handles were closed, no dumps were created, no process was suspended, and no debugger was attached.

## Discovery findings

- Current proof anchor: `0x23863A26E50`, candidate `api-family-hit-000001`; proof/API buffer evidence only.
- Ref-storage: `0x23863A1D400 -> 0x23863A26E50`; heap-local candidate only.
- Owner-batch module RVA hints: `0x26F1DF0`, `0x26EF170`, `0x26E95E0`, `0x26F11E0`, `0x26F11D8`; candidate-only owner-window hints.
- Root-signature sweep completed for all 5 hints, but evidence remains heap/resource/string-heavy and candidate-only.
- Latest owner-layout packet still reports no current owner `+0x320/+0x324/+0x328` shape.

## Current blockers

- `actor-static-chain-not-promoted`
- `no-static-resolver-promoted`
- `not-restart-validated-for-static-actor-chain`
- `proof-anchor-stale-for-movement`
- `module-rva-hints-are-not-static-resolver`
- `current-owner-plus-0x320-shape-not-found`
- `sysinternals-listdlls-module-base-low32-truncated`
- `vmmap-export-skipped-noninvasive-cli-not-confirmed`
- `blocked-no-debugger-access-provenance`
- `x64dbg-attach-blocked-existing-debug-object`
- `debugactiveprocessstop-access-denied-winerr-5`

## Safety ledger

| Field | Value |
|---|---:|
| movementSent | false |
| inputSent | false |
| reloaduiSent | false |
| screenshotKeySent | false |
| noCheatEngine | true |
| x64dbgAttach | false |
| debuggerAttached | false |
| debugActiveProcessStopCalled | false |
| providerWrites | false |
| proofPromotion | false |
| actorChainPromotion | false |
| dumpCreated | false |
| processSuspended | false |
| procmonCaptureStarted | false |

## Next single best step

No-debug discovery is now **blocked unless a new non-heap root hypothesis appears**. The next practical step is to prepare a separate, risk-reviewed debugger/process-owner access-provenance tactic for explicit approval. Do not retry the prior failed x64dbg attach or `DebugActiveProcessStop` sequence unchanged.
