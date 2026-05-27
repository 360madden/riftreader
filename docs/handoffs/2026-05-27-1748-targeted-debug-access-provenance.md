# Targeted Debug Access + Access-Provenance Capture — PID 12148

Generated: 2026-05-27T17:48:00Z

## Verdict

`candidate-only-debug-provenance-improved`, **not promoted**.

The current target accepted a bounded x64dbg attach/detach. A targeted hardware watch on the current proof anchor produced one access hit and captured call/context evidence, but this remains proof/API-buffer provenance evidence only. It does not solve or promote the actor/static pointer chain.

## Safety / mutation boundary

| Field | Result |
|---|---:|
| Cheat Engine used | false |
| x64dbg attached | true |
| DebugActiveProcessStop called | false |
| Breakpoint/watchpoint set | true, bounded hardware watch only |
| Targeted displacement/input attempted | true, one bounded W postmessage attempt and one MCP W window-message attempt |
| Visual frame change observed | false |
| Provider writes | false |
| Proof promotion | false |
| Actor/static-chain promotion | false |
| Git stage/commit/push | false |

## Target identity

| Field | Value |
|---|---|
| Process | `rift_x64.exe` |
| PID | `12148` |
| HWND | `0x640C0C` |
| Process start | `2026-05-27T01:17:01.265352Z` |
| Expected module base | `0x7FF77AF40000` |
| Proof anchor | `api-family-hit-000001 @ 0x23863A26E50` |

## Artifacts

| Artifact | Result |
|---|---|
| Attach viability | [`C:\RIFT MODDING\RiftReader\scripts\captures\x64dbg-live-access-capture-20260527-173817-084899\summary.json`](C:\RIFT%20MODDING\RiftReader\scripts\captures\x64dbg-live-access-capture-20260527-173817-084899\summary.json) — `captured`, detach succeeded |
| First hardware watch | [`C:\RIFT MODDING\RiftReader\scripts\captures\x64dbg-live-access-capture-20260527-173911-546819\summary.json`](C:\RIFT%20MODDING\RiftReader\scripts\captures\x64dbg-live-access-capture-20260527-173911-546819\summary.json) — event hit, original automated detach failed; manual x64dbg automation recovery detached successfully |
| Post-manual recovery probe | [`C:\RIFT MODDING\RiftReader\scripts\captures\x64dbg-target-recovery-20260527-173840-853560\summary.json`](C:\RIFT%20MODDING\RiftReader\scripts\captures\x64dbg-target-recovery-20260527-173840-853560\summary.json) — target responding, debugger not attached |
| Retry-hardened no-input watch | [`C:\RIFT MODDING\RiftReader\scripts\captures\x64dbg-live-access-capture-20260527-174406-311176\summary.json`](C:\RIFT%20MODDING\RiftReader\scripts\captures\x64dbg-live-access-capture-20260527-174406-311176\summary.json) — timed out, detach succeeded |
| Stimulus watch attempt | [`C:\RIFT MODDING\RiftReader\scripts\captures\x64dbg-live-access-capture-20260527-174525-823773\summary.json`](C:\RIFT%20MODDING\RiftReader\scripts\captures\x64dbg-live-access-capture-20260527-174525-823773\summary.json) — W postmessage sent, timed out, detach succeeded |
| Visual baseline | [`C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260527-134456-269.png`](C:\RIFT%20MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260527-134456-269.png) |
| Visual after postmessage stimulus | [`C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260527-134554-650.png`](C:\RIFT%20MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260527-134554-650.png) — no frame change |
| Visual after MCP W stimulus | [`C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260527-134632-023.png`](C:\RIFT%20MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260527-134632-023.png) — no frame change |

## Access hit details

First hardware watch hit:

| Field | Value |
|---|---|
| Candidate | `0x23863A26E50` |
| Event status | `hit` |
| RIP | `0x7FF83181121C` |
| Resolved module | `VCRUNTIME140.dll` at `0x7FF831800000` |
| Instruction | `mov dword ptr ds:[rax+0x08], ecx` |
| `rax` | `0x23863A26E50` |
| `rcx` | `0x453ACFC3` |
| Candidate triplet at hit | `X=7259.5908203125`, `Y=821.5345458984375`, `Z=2988.985107421875` |

Important stack/caller leads from the hit context, normalized against `rift_x64` base `0x7FF77AF40000`:

| Address | RVA | Role |
|---:|---:|---|
| `0x7FF77C0A29A4` | `0x11629A4` | return/caller lead |
| `0x7FF77C07837D` | `0x113837D` | return/caller lead |
| `0x7FF77B787518` | `0x0847518` | return/caller lead |
| `0x7FF77C0A23CD` | `0x11623CD` | nearby stack lead |
| `0x7FF77C07705C` | `0x113705C` | nearby stack lead |

Interpretation: the immediate RIP is a CRT copy/write helper and the stack contains `rift_x64` return-address leads. This is useful access provenance, but it still points to proof/API-buffer copy/update behavior unless linked back to an actor/static owner.

## Code hardening added

Updated [`C:\RIFT MODDING\RiftReader\scripts\rift_live_test\x64dbg_live_access_capture.py`](C:\RIFT%20MODDING\RiftReader\scripts\rift_live_test\x64dbg_live_access_capture.py):

- added a detach-failure recovery path;
- after first detach failure, it clears hardware/memory breakpoints, performs one explicit no-input resume-for-detach recovery, retries detach, then terminates the x64dbg session if detach succeeds;
- this prevents leaving the target stopped after a watchpoint event hit.

## Remaining blockers

| Blocker | Current state |
|---|---|
| `actor-static-chain-not-promoted` | still true |
| `no-static-resolver-promoted` | still true |
| `not-restart-validated-for-static-actor-chain` | still true |
| `proof-anchor-stale-for-movement` | still true in workflow status |
| debugger blocker in current-truth | stale relative to today’s successful attach; current truth not updated/promoted |
| displacement stimulus | input messages were sent, but no visual frame change was observed |

## Validation run

| Check | Result |
|---|---|
| `python -m py_compile scripts\rift_live_test\x64dbg_live_access_capture.py scripts\x64dbg_live_access_capture.py` | passed |
| `python -m pytest scripts\test_sysinternals_discovery_packet.py scripts\test_owner_layout_comparison_packet.py -q` | passed, 4 tests |
| `python tools\riftreader_workflow\policy_lint.py --json validate-repo --scope changed --no-write-summary` | passed |
| `git --no-pager diff --check` | passed; warning only about future LF→CRLF normalization |
| decision/workflow/actor/RiftScan gates | ran; actor/static remains blocked |

## Next single best command

Do **not** promote. Next best discovery step is offline/no-input analysis of the new caller RVAs and hit context:

```powershell
python .\scripts\owner_layout_comparison_packet.py --json
```

Then add a focused caller/RVA provenance packet that inspects `0x11629A4`, `0x113837D`, and `0x0847518` against existing root-signature/owner-window artifacts before any further live watchpoint or displacement attempt.

## Post-handoff owner-layout refresh

Ran the safe offline owner-layout packet after the live debugger evidence:

| Artifact | Verdict |
|---|---|
| [`C:\RIFT MODDING\RiftReader\scripts\captures\owner-layout-comparison-packet-20260527-174815-644455\summary.json`](C:\RIFT%20MODDING\RiftReader\scripts\captures\owner-layout-comparison-packet-20260527-174815-644455\summary.json) | `candidate-only-no-current-owner-layout-root` |

This confirms the new live provenance hit should be treated as a caller/RVA lead for focused offline analysis, not as actor/static-chain promotion evidence.
