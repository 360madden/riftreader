# x64dbg live coordinate access capture

Status date: 2026-05-12

## Verdict

The approved live x64dbg session produced the first useful coordinate access
evidence for the current PID epoch, but it still did **not** discover a stable
static pointer chain.

Best current lead from this capture:

| Field | Value |
|---|---|
| Target PID/HWND | `63412` / `0xB70082` |
| Process start UTC | `2026-05-12T15:53:24.4410214Z` |
| Stronger watched coordinate address | `0x20005B30800` |
| Observed object/base register | `rdi = 0x20005B304E0` |
| Coordinate field offset | `+0x320/+0x324/+0x328` |
| Code module | `rift_x64.exe` |
| Code module base | `0x7FF796B50000` |
| Observed instruction RVAs | `0x579F88`, `0x579F96`, `0x579FA4`, `0x579FD5`, `0x579FE9` |
| Evidence level | `access-proven-candidate`, not static-chain truth |

## What was approved and used

The user approved x64dbg for offline and online use in this conversation. The
capture used x64dbg Automate against the exact live RIFT PID/HWND and then
detached.

Safety facts:

| Item | Result |
|---|---|
| x64dbg live attach | Used |
| Hardware read breakpoints | Used on coordinate lanes |
| Cheat Engine | Not used |
| Movement/input | Not sent |
| MCP config | Not changed |
| Process patching / memory writes | Not performed |

## Capture artifacts

Generated capture artifacts are under ignored `scripts\captures\` paths:

| Artifact | Meaning |
|---|---|
| `scripts\captures\x64dbg-live-coord-access-20260512-approval-01\manual-access-events.json` | First watch pass against `0x78BF4FE420`. |
| `scripts\captures\x64dbg-live-coord-access-20260512-approval-02\manual-access-events.json` | Better watch pass against `0x20005B30800`. |
| `scripts\captures\x64dbg-live-coord-access-20260512-approval-02\manual-access-events-enriched.json` | Same events enriched with module base/RVA/instruction bytes. |
| `scripts\captures\x64dbg-live-coord-access-20260512-approval-02\ingest\summary.json` | Ingest summary. |
| `scripts\captures\x64dbg-live-coord-access-20260512-approval-02\ingest\x64dbg-coordinate-chain-candidate.json` | Candidate-only normalized packet. |
| `scripts\captures\x64dbg-live-coord-access-20260512-approval-02\pointer-scan-owner-0x20005B304E0.json` | Read-only pointer scan for references to the observed owner/base object. |

## Candidate assessment

| Candidate | Result | Assessment |
|---|---|---|
| `0x78BF4FE420` | Hardware breakpoints hit stack/prologue/epilogue-like accesses such as `push`, `pop`, and stack-pointer-relative state. | Downrank. It may mirror coordinate bytes but is likely stack/scratch evidence, not stable owner truth. |
| `0x20005B30800` | Hardware breakpoints hit stable coordinate-like reads with memory matching ChromaLink API-now: `X=7376.4106`, `Y=863.7137`, `Z=2989.8760`. | Promote only to stronger access-proven candidate. |

The useful sequence around `rift_x64.exe+0x579F80` compares/loads the three
coordinate lanes. The first three hits show the watched triplet as fields under:

```text
rdi + 0x320 = X
rdi + 0x324 = Y
rdi + 0x328 = Z
```

with `rdi = 0x20005B304E0` in the captured pose.

## Ingest result

The enriched event file passed structural ingest:

```text
status = passed
candidate = x64dbg-live-access-candidate-0x20005B30800-20260512
```

Remaining blockers are expected and correct:

| Blocker | Meaning |
|---|---|
| `not-multi-pose-validated` | Only one pose was captured. |
| `not-restart-validated` | No restart/relog proof yet. |
| `no-runtime-helper-readback` | No repo-owned live/current chain resolver readback yet. |
| `not-promoted-through-api-now-vs-chain-now` | Static chain has not been read through a resolver and compared to API-now. |
| `proofonly-not-passed` | Not accepted by the existing movement proof gate. |
| `not-module-relative-rooted` | We have instruction RVAs and an object field offset, but not yet a module/RVA/static-owner root chain to the object. |

## Current missing piece

The key unresolved problem is now narrower:

> Find a stable module/RVA/static-owner path to the object at
> `0x20005B304E0`, whose coordinate fields live at `+0x320/+0x324/+0x328`.

The read-only pointer scan found references to `0x20005B304E0`, but that is
still candidate evidence. It needs clustering, multi-pose validation, and restart
validation before any static chain can be called stable.

## Next gate

Next work should focus on owner/root discovery, not on re-proving that
`0x20005B30800` contains the current coordinate triplet:

1. capture the same `rdi + 0x320` relationship across at least three displaced
   poses;
2. pointer-scan and cluster references to `0x20005B304E0`;
3. look for module/RVA/static-owner roots that survive pose changes;
4. run the offline static-chain resolver harness only after a real root chain is
   formed;
5. restart/relog and validate the same chain shape before promotion.
