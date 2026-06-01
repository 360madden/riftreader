# RiftReader compact handoff — current-truth + Ghidra static refresh

Generated UTC: `2026-06-01T04:58Z`

# **✅ RESULT — CURRENT TARGET/TRUTH REFRESHED; OFFLINE STATIC EVIDENCE CAPTURED**

This handoff supersedes `docs/handoffs/2026-06-01-0147-facing-target-promotion-readiness-handoff.md` for current target identity and static/API-now freshness.

The promoted coordinate resolver remains:

`[rift_x64+0x32EBC80]+0x320/+0x324/+0x328`

The facing-target candidate remains candidate-only:

`[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314`

No facing/turn-rate/actor proof promotion, provider write, x64dbg/CE attach, target memory write, or Git mutation was performed while creating this handoff.

## Repo state before this handoff file

| Field | Value |
|---|---|
| Repo | `C:\RIFT MODDING\RiftReader` |
| Branch | `main` |
| Pre-handoff HEAD | `a5a1c54` — `Reintroduce Ghidra static evidence lane` |
| Remote state | `main...origin/main` before local commit |
| Worktree before handoff | Dirty with current-truth/code/test refresh paths |

## Current target and truth

| Item | Current value |
|---|---|
| Target PID/HWND | PID `41808`, HWND `0x2B0A26`, process `rift_x64` |
| Process start UTC | `2026-06-01T01:50:50.903773Z` |
| Module base | `0x7FF6EE5D0000` |
| Owner root | `[rift_x64+0x32EBC80]` / owner `0x1E16E8706A0` |
| Promoted coordinate chain | `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328` |
| Latest static coordinate readback | `7259.41650390625, 821.42431640625, 2993.230712890625` at `2026-06-01T04:55:07.535451+00:00` |
| Latest nav-state yaw | `75.17711284220054°` at `2026-06-01T04:55:19.287577+00:00` |
| Latest RRAPICOORD API-now | `7259.419922, 821.419983, 2993.229980` at `2026-06-01T04:55:56.620509Z` |
| API/chain agreement | max abs delta `0.004333406249998006` <= tolerance `0.25` |
| Movement gate in tracked truth | `allowed-with-current-pid-exact-target-fresh-static-readback-and-api-now-validation` |

## Current refresh artifacts

| Artifact | Path |
|---|---|
| Static coordinate readback | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-coordinate-chain-readback-20260601-045507-534569\summary.json` |
| Nav-state readback | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-nav-state-20260601-045519-286724\summary.json` |
| RRAPICOORD API-now reference | `C:\RIFT MODDING\RiftReader\scripts\captures\rift-api-reference-currentpid-41808-20260601-045534.json` |
| Navigation dashboard | `.riftreader-local\navigation-pointer-discovery\latest\summary.json` generated `2026-06-01T04:56:07Z` |
| Current-truth refresh plan | `.riftreader-local\current-truth-refresh-plan\latest\summary.json` generated `2026-06-01T04:56:16Z` |
| Tracked truth JSON | `docs/recovery/current-truth.json` updated to `2026-06-01T04:56:16Z` |
| Tracked truth Markdown | `docs/recovery/current-truth.md` updated to `2026-06-01T04:56:16Z` |

## Code/workflow fixes in this slice

| Area | Change |
|---|---|
| Navigation dashboard | Uses latest matching exact-target coordinate/nav-state readbacks to refresh target identity instead of stale `current-truth` PID. |
| API-now comparison | Ingests latest `rift-api-reference-currentpid-<pid>-*.json`, including normalized and PascalCase shapes, then computes API-now vs chain-now deltas. |
| Current-truth refresh planner | Updates target identity, latest readback/nav/API artifacts, current warnings, movement gate, stale-proof wording, and next action from refreshed dashboard evidence. |
| Tests | Added stale-target replacement and refreshed-target planner assertions; made current-truth consistency checks dynamic instead of hardcoded to PID `25668`. |

## Offline Ghidra static evidence lane

| Field | Value |
|---|---|
| Status | `passed` |
| Safety | Offline only; no live input, movement, debugger, CE, provider write, target memory read/write, or Git mutation |
| Binary | `C:\Program Files (x86)\Glyph\Games\RIFT\Live\rift_x64.exe` |
| Summary JSON | `scripts\captures\ghidra-static-analysis-20260601-043934\summary.json` |
| Summary Markdown | `scripts\captures\ghidra-static-analysis-20260601-043934\summary.md` |
| Pointer evidence JSON | `scripts\captures\ghidra-static-analysis-20260601-043934\pointer-evidence.json` |
| Warning | `ghidra-analysis-timeout-project-saved` |
| Instructions scanned | `4,852,736` |
| Root refs captured | `200` (`READ=101`, `WRITE=99`) |

Notable offset evidence captured by the Ghidra script:

| Offset | Hit count | Write-like count | Notable first write-like evidence |
|---:|---:|---:|---|
| `0x304` | `80` | `28` | `14003fa33: MOV dword ptr [RDI + 0x304],R13D` |
| `0x30C` | `65` | `26` | `14003fa41: MOV dword ptr [RDI + 0x30c],R13D` |
| `0x314` | `66` | `35` | `14003fa4f: MOV dword ptr [RDI + 0x314],0x3f800000` |
| `0x320` | `80` | `22` | `14003fa67: MOV dword ptr [RDI + 0x320],R13D` |
| `0x324` | `57` | `21` | `14003fa6e: MOV dword ptr [RDI + 0x324],R13D` |
| `0x328` | `80` | `19` | `14003fa75: MOV dword ptr [RDI + 0x328],0x3f800000` |

Interpretation: this is static/offline evidence only. It strengthens follow-up static-root/source-site review, but it does **not** by itself prove facing-target promotion readiness.

## Validation run

| Command | Result |
|---|---|
| `python -m unittest scripts.test_navigation_pointer_discovery scripts.test_current_truth_refresh_plan scripts.test_current_truth_consistency scripts.test_status_packet scripts.test_validate_current_truth` | Passed — `37` tests |
| `python scripts\validate_current_truth.py --json` | Passed — `artifactCount=72`, no warnings/errors |
| `python tools\riftreader_workflow\decision_packet.py --run-safe-checks --json` | Passed; safe validations passed; no blockers |
| `cmd /c scripts\riftreader-workflow-status.cmd --compact-json --write` | Passed; current target PID `41808`; warning only stale launcher inspection |
| `cmd /c scripts\riftreader-ghidra-static-evidence.cmd --run --binary-path "C:\Program Files (x86)\Glyph\Games\RIFT\Live\rift_x64.exe" --json` | Passed; ignored artifacts under `scripts\captures\ghidra-static-analysis-20260601-043934` |

## Remaining blockers / boundaries

| Blocker | Meaning |
|---|---|
| Facing target still candidate-only | `owner+0x30C/+0x310/+0x314` remains useful/readable but not promotion-ready. |
| Restart/relog survival not executed in this slice | No repo-owned bounded helper was found for an end-to-end facing-target restart/relog proof; do not claim survival from current-session readback. |
| Static-root/source-site proof still incomplete | Ghidra produced offset evidence, but follow-up source-site/root-specific review is still needed before promotion. |
| Formal three-pose displacement packaging still needed | Prior route-progress evidence exists, but it has not been converted into a dedicated promotion gate packet for facing. |
| Current-readback freshness decays | Refresh exact-target static/nav/API readbacks before any later live movement, ProofOnly, or promotion claim. |

## Resume checklist

1. Refresh local status:
   ```powershell
   cd "C:\RIFT MODDING\RiftReader"
   git --no-pager status --short --branch
   cmd /c scripts\riftreader-decision-packet.cmd --compact-json --write
   ```
2. If continuing facing promotion, start with the Ghidra static summary and current dashboard artifacts listed above.
3. Refresh no-input exact-target static coordinate/nav-state/API-now readbacks before any navigation movement or proof claim.
4. Keep `owner+0x30C/+0x310/+0x314` candidate-only until restart/relog survival, static-root proof, and formal three-pose displacement gates pass.
5. Do not promote actor/stat chains or facing/turn-rate chains from this handoff alone.

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Build a bounded facing-target restart/relog survival helper or packet. | This is the largest remaining promotion blocker and should be reproducible. |
| 2 | Review `ghidra-static-analysis-20260601-043934` for root-specific writer/source sites near `0x30C/0x314/0x320/0x328`. | Converts broad offset hits into stronger provenance. |
| 3 | Package the existing route-forward passes into a formal three-pose gate artifact. | Moves route evidence from anecdotal to promotion-gate format. |
| 4 | Refresh camera/yaw proof before any turn-dependent route movement. | Current camera/yaw evidence is candidate-only and age-sensitive. |
| 5 | Keep `0x304` support-only until dedicated turn-rate proof exists. | It has useful correlation but ambiguous semantics. |
| 6 | Add tests for current-truth stale-text replacement if future stale PID strings appear. | Prevents stale target instructions from reappearing. |
| 7 | Add a compact Ghidra evidence summarizer focused on owner-relative offsets. | Makes static evidence review faster after future binary updates. |
| 8 | Refresh launcher inspection only if restart/relog automation becomes necessary. | Current launcher packet is stale and not button-safe. |
| 9 | Preserve this current truth refresh before broad movement work. | Exact PID/HWND/API evidence is the safest base for later gates. |
| 10 | Promote only through a separate explicit proof/promotion review artifact. | Avoids accidental candidate-to-truth promotion. |

## Handoff boundary

This file is a tracked resume artifact only. It does not promote facing, turn-rate, actor/stat chains, or any proof anchor, and it does not make ignored Ghidra artifacts tracked.
