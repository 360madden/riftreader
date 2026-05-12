# Stable static coord pointer-chain discovery handoff

Generated: 2026-05-12 19:33:21 -04:00 / 2026-05-12T23:33:21Z  
Repo: `C:\RIFT MODDING\RiftReader`  
Branch/HEAD: `main` @ `a2d3d35` (`origin/main` synced at inspection time)  
Purpose: resume discovery of a stable static pointer chain for player coordinate data.

## Verdict

No stable static coordinate pointer chain is promoted yet.

Best current evidence is an access-proven candidate from the approved live x64dbg
capture:

| Fact | Value |
|---|---|
| Live target used for capture | PID `63412`, HWND `0xB70082`, process `rift_x64` |
| Process start UTC | `2026-05-12T15:53:24.4410214Z` |
| Coordinate triplet candidate | `0x20005B30800` |
| Observed owner/base register | `rdi = 0x20005B304E0` |
| Coordinate fields under owner | `+0x320/+0x324/+0x328` |
| Module | `rift_x64.exe` |
| Module base in capture | `0x7FF796B50000` |
| Observed instruction RVAs | `0x579F88`, `0x579F96`, `0x579FA4`, `0x579FD5`, `0x579FE9` |
| Evidence level | `access-proven-candidate`, not static-chain truth |

Important accuracy note:
`docs/recovery/current-proof-anchor-readback.json` still names older target PID
`57656` / HWND `0x5417BC`. Do not treat that file as the current static-chain
target without refreshing it. At handoff creation time, Windows still showed a
live `rift_x64` process at PID `63412` / HWND decimal `11993218`
(`0xB70082`). Revalidate before any live/debugger action.

## Durable source files

| Path | Use |
|---|---|
| `docs/recovery/x64dbg-live-coordinate-access-capture-2026-05-12.md` | Latest approved live x64dbg access-capture summary and blocker list. |
| `docs/recovery/x64dbg-static-coord-chain-discovery-status-2026-05-12.md` | Static-chain readiness/progress status and next gate. |
| `docs/recovery/x64dbg-pointer-chain-workflow.md` | Safety boundary, planner/ingester/resolver workflow, promotion gates. |
| `docs/recovery/README.md` | Recovery index; x64dbg helper list starts near the x64dbg pointer-chain discovery note. |

## Key local artifacts

Ignored capture artifacts exist under:

| Artifact | Meaning |
|---|---|
| `scripts/captures/x64dbg-live-coord-access-20260512-approval-02/manual-access-events-enriched.json` | Best enriched x64dbg access events. |
| `scripts/captures/x64dbg-live-coord-access-20260512-approval-02/ingest/summary.json` | Ingest summary: `status=passed`, `eventCount=5`, `poseCount=1`. |
| `scripts/captures/x64dbg-live-coord-access-20260512-approval-02/ingest/x64dbg-coordinate-chain-candidate.json` | Candidate packet for follow-up chain work. |
| `scripts/captures/x64dbg-live-coord-access-20260512-approval-02/pointer-scan-owner-0x20005B304E0.json` | Read-only pointer scan for references to observed owner/base object. |

Candidate packet validation currently says:

| Gate | State |
|---|---|
| same target | `true` |
| API-now vs memory-now | `true` |
| API-now vs chain-now | `false` |
| multi-pose | `false` (`poseCountObserved=1`, `poseCountRequired=3`) |
| restart validated | `false` |
| runtime helper readback | `false` |
| proof-only passed | `false` |
| movement proof eligible | `false` |

Blockers:

- `not-multi-pose-validated`
- `not-restart-validated`
- `no-runtime-helper-readback`
- `not-promoted-through-api-now-vs-chain-now`
- `proofonly-not-passed`
- `not-module-relative-rooted`

## Repo-owned helper commands

Read-only/offline helpers already exist:

```powershell
python .\scripts\x64dbg_coord_chain_plan.py --help
python .\scripts\x64dbg_access_event_ingest.py --help
python .\scripts\x64dbg_static_chain_resolve.py --help
```

Useful self-tests from the current workflow:

```powershell
python .\scripts\test_x64dbg_access_event_ingest.py -v
python .\scripts\test_x64dbg_static_chain_resolve.py -v
python .\scripts\x64dbg_static_chain_resolve.py --self-test --json
```

The static resolver is intentionally offline-only right now. It fails closed
until a candidate packet has a real `derivedChain.rootRva` / static-owner path
plus module map and memory image/readback evidence.

## Safety boundary

- Do not attach x64dbg to `rift_x64.exe` unless the user explicitly approves a
  live-debugger session in the current conversation.
- Do not use Cheat Engine debugger/watchpoints at the same time as x64dbg on the
  same target.
- Do not send movement/input for this pointer-chain work.
- Do not patch/write process memory.
- Do not promote heap-only addresses.
- Do not promote anything until chain-now vs API-now, multi-pose, restart
  validation, runtime helper readback, and ProofOnly all pass.

## Exact next gate

Resume at owner/root discovery, not at re-proving the coordinate value.

1. Revalidate current target identity: PID/HWND/process start/module base.
2. Reconfirm candidate `0x20005B30800` and owner `0x20005B304E0` are still valid
   for the live target, or mark them stale after restart.
3. If user approves live x64dbg again, capture the same
   `rdi + 0x320/+0x324/+0x328` relationship across at least 3 displaced poses.
4. Mine `pointer-scan-owner-0x20005B304E0.json` and/or new pointer scans for
   module/RVA/static-owner roots that lead to `0x20005B304E0`.
5. Fill `derivedChain.rootRva`, `offsets`, and field offsets only from real
   evidence.
6. Run `scripts\x64dbg_static_chain_resolve.py` against the filled candidate
   packet and a module map/offline memory image.
7. Compare chain-now to fresh API-now across poses.
8. Restart/relog and validate the same chain shape again.
9. Only then attempt same-target ProofOnly promotion.

## Current worktree note

At creation time, the worktree also had unrelated uncommitted Context7
docs/policy changes:

- modified `agents.md`
- new `docs/workflow/context7-usage.md`

Keep those separate from static pointer-chain discovery unless explicitly
committing all docs together.

## Resume prompt

```text
Resume from `docs/handoffs/2026-05-12-193321-stable-static-coord-pointer-chain-handoff.md`.
Focus only on stable static pointer-chain discovery for coord data. First
revalidate target identity and read the listed x64dbg docs/artifacts. Do not
attach x64dbg, send input, or promote candidates without current-turn approval
and proof gates. Be accurate: current truth is access-proven candidate
`0x20005B30800` / owner `0x20005B304E0`, not stable chain truth.
```
