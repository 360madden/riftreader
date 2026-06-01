# RiftReader compact handoff — camera/yaw proof pack refresh

Generated UTC: `2026-06-01T05:21:31Z`

# **✅ RESULT — LIVE VISUAL TARGET FIXED; CAMERA/YAW PROOF PACK PASSED**

This handoff supersedes `docs/handoffs/2026-06-01-0458-current-truth-ghidra-static-refresh-handoff.md` for the live-window visual preflight and the newest camera/yaw proof evidence. It preserves that handoff as the current target/truth and Ghidra-static baseline.

The promoted coordinate resolver remains:

`[rift_x64+0x32EBC80]+0x320/+0x324/+0x328`

The facing-target candidate remains candidate-only:

`[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314`

No facing/turn-rate/actor proof promotion, provider write, x64dbg/CE attach, target memory write, restart/relog, or route-forward movement was performed while creating this handoff.

## Current target

| Item | Current value |
|---|---|
| Target PID/HWND | PID `41808`, HWND `0x2B0A26`, process `rift_x64` |
| Process start UTC | `2026-06-01T01:50:50.903773Z` |
| Module base | `0x7FF6EE5D0000` |
| Owner root | `[rift_x64+0x32EBC80]` / owner `0x1E16E8706A0` |
| Promoted coordinate chain | `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328` |
| Current API-now status | `passed-current-pid-41808-api-now-vs-chain-now` from `scripts\captures\rift-api-reference-currentpid-41808-20260601-045534.json` |

## Live-window visual preflight

| Check | Result |
|---|---|
| Exact bind | Passed: PID `41808`, HWND `0x2B0A26`, title `RIFT` |
| Foreground state | Passed: `isForeground=true` after operator moved the Amazon browser page |
| Baseline capture | `tools\rift-game-mcp\.runtime\screenshots\capture-20260601-011842-185.png` showed the Rift frame |
| Post-stimulus frame changes | Passed: right proof changed `39.2917%`; left proof changed `40.2431%` |

## Camera/yaw proof pack

| Pose | Direction | Pixels | Result | Signed yaw delta | Artifact |
|---:|---|---:|---|---:|---|
| 1 | `right` | `40` | `visual-and-static-yaw-changed` | `+8.469205989610003°` | `scripts\captures\static-owner-camera-yaw-classification-20260601-051930-376376\summary.json` |
| 2 | `left` | `40` | `visual-and-static-yaw-changed` | `-8.469205989610003°` | `scripts\captures\static-owner-camera-yaw-classification-20260601-052001-963141\summary.json` |

Aggregate report:

| Field | Value |
|---|---|
| Status | `passed` |
| Verdict | `route-actionable-candidate-present-needs-proof` |
| Source count | `2` |
| Route-actionable pose count | `2` |
| Classification counts | `visual-and-static-yaw-changed=2` |
| Changed offset count | `5` |
| Summary JSON | `scripts\captures\static-owner-camera-yaw-multipose-report-20260601-052037-685312\summary.json` |
| Summary Markdown | `scripts\captures\static-owner-camera-yaw-multipose-report-20260601-052037-685312\summary.md` |

Changed focus offsets from the latest left pose included `owner+0x300`, `owner+0x304`, `owner+0x30C`, `owner+0x314`, and `owner+0x408`. This keeps camera/yaw route-control evidence actionable, but still candidate-only.

## Refreshed dashboards

| Command | Result |
|---|---|
| `cmd /c scripts\riftreader-navigation-pointer-discovery.cmd --json --write` | Passed; dashboard refreshed at `2026-06-01T05:20:54Z` |
| `cmd /c scripts\riftreader-workflow-status.cmd --compact-json --write` | Passed; compact sitrep refreshed at `2026-06-01T05:20:56Z` |

Dashboard still keeps facing/turn-rate candidate-only and requires restart/relog survival, static-root proof, and formal three-pose displacement validation before promotion.

## Safety boundary

| Boundary | State |
|---|---|
| Live input sent | Yes — two bounded exact-target mouse-look camera/yaw stimuli |
| Route-forward movement | Not sent |
| Target memory writes | None |
| x64dbg / Cheat Engine | Not used |
| Provider writes | None |
| Proof/facing/actor promotion | Not performed |
| Git mutation during proof pack | None |

## Remaining blockers / boundaries

| Blocker | Meaning |
|---|---|
| Facing target still candidate-only | `owner+0x30C/+0x310/+0x314` is route-actionable evidence, not promoted truth. |
| Restart/relog survival still not run | Need a bounded restart/relog packet before promotion. |
| Static-root/source-site proof still incomplete | Ghidra offset evidence exists but still needs source-site/root-specific review. |
| Formal three-pose displacement packaging still needed | Existing route-forward passes have not been converted into a dedicated facing promotion gate packet. |
| Current readback freshness decays | Refresh exact-target static/nav/API readbacks before any later movement, ProofOnly, or promotion claim. |

## Resume checklist

1. Refresh local status:
   ```powershell
   cd "C:\RIFT MODDING\RiftReader"
   git --no-pager status --short --branch
   cmd /c scripts\riftreader-decision-packet.cmd --compact-json --write
   ```
2. If continuing live route work, re-check exact PID/HWND foreground and capture first.
3. Refresh exact-target static coordinate/nav-state/API-now readbacks if the 30-minute freshness window has expired.
4. Keep `owner+0x30C/+0x310/+0x314` candidate-only until restart/relog survival, static-root proof, and formal three-pose displacement gates pass.
5. Do not promote actor/stat chains or facing/turn-rate chains from this handoff alone.

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Add a repo-owned visual foreground/capture guard before live helper input. | The earlier Amazon-page mismatch proves this should fail closed automatically. |
| 2 | Package existing route-forward passes into a formal three-pose gate artifact. | Turns route evidence into a repeatable promotion-gate input. |
| 3 | Run a bounded turn-forward proof only after refreshing static/nav/API readbacks. | Confirms current camera/yaw control still produces route progress. |
| 4 | Build a bounded facing-target restart/relog survival helper or packet. | Biggest remaining promotion blocker. |
| 5 | Review Ghidra writer/source sites around `owner+0x30C/+0x314/+0x320/+0x328`. | Strengthens static-root/subfield proof. |
| 6 | Refresh launcher inspection only if restart/relog automation becomes necessary. | Current launcher packet is stale and not button-safe. |
| 7 | Keep `0x304` support-only until dedicated turn-rate proof exists. | It correlates with turns but has ambiguous semantics. |
| 8 | Teach navigation discovery to consume the aggregate multipose camera/yaw report. | Current dashboard indexes the latest single pose, not the aggregate packet. |
| 9 | Preserve all proof-pack paths in the next promotion-readiness packet. | Keeps candidate provenance reviewable. |
| 10 | Promote only through a separate proof/promotion review artifact. | Avoids accidental candidate-to-truth promotion. |

## Handoff boundary

This file is a tracked resume artifact only. It does not promote facing, turn-rate, actor/stat chains, or any proof anchor, and it does not make ignored proof-pack artifacts tracked.
