# Historical current truth archive — PID 2928 / HWND 0xC0994

> **Historical / stale target epoch.** This file preserves the previous `docs/recovery/current-truth.md` state for PID `2928` / HWND `0xC0994`. Do not use it as current coordinate proof or movement truth. The current coordinate proof pointer is PID `16536` / HWND `0x1E0D66`, candidate `snapshot-delta-21487DF8F64-xyz` at `0x21487DF8F64`.
>
> Archived at `2026-05-14T18:36:23Z` while promoting the PID `16536` proof pointer. Use this file only for audit or broad reacquisition-history context.

---

# RiftReader Current Truth

_Last updated: 2026-05-14T12:19:34Z._

## Verdict

**Read-only live testing is allowed; player-control testing remains blocked.** Candidate **`api-family-hit-000001` at `0x268E2BC09E0`** remains the latest API-memory-match lead, but the newest displacement-gated comparison is **blocked**: raw both-reference matches `2` are preserved for audit, while valid both-reference matches are `0` because the displaced reference moved only `5.59732083466666e-05` planar units. Promotion readiness is `blocked-promotion-readiness`, proof-anchor promotion allowed is `False`, and movement remains blocked.

## Current target epoch

| Field | Value |
|---|---|
| Process | `rift_x64.exe` |
| PID | `2928` |
| HWND | `0xC0994` |
| Process start | `2026-05-13T16:17:56.208370Z` |
| Module base | `0x7FF71CD90000` |

## Freshness invariant

PID/HWND/process-start matching is **targeting preflight only**; it is not
freshness proof. Current coordinate truth requires **API-now vs memory-now**
evidence: a fresh live API/runtime coordinate and an immediate same-target memory
coordinate read, with per-axis deltas inside tolerance. Latest recorded coordinate snapshot: `7399.1099, 871.77, 3029.96`; do not present this value as current-now unless it is refreshed and re-compared against same-target memory.

## Live truth source

| Surface | Status | Notes |
|---|---|---|
| `ReaderBridge_RRAPICOORD1` | **current / usable for read-only proof** | Fresh no-input reference: `7399.109863, 871.769958, 3029.959961` at `2026-05-14T12:08:49.0014728Z`; `savedVariablesUse=none`. |
| Same-target memory readback | **API-memory match, candidate-only** | `api-family-hit-000001` at `0x268E2BC09E0`, `ReferenceMatchCount=1`, max abs delta `4.960937758369255e-07`. |
| Displaced-pose readiness | **blocked** | Planar distance `5.59732083466666e-05`; blockers `['displaced-reference-age-exceeded:1363.884>300.0', 'displaced-reference-planar-distance-too-small:5.6e-05<1.0']`. |
| Static pointer/root proof | **not proven** | Direct pointer scan from current candidate found `None` hits. |
| ChromaLink world-state | stale / not authoritative | Still not the authority for coordinate proof in this lane. |
| SavedVariables | not live truth | Post-save snapshots only; never use as live movement truth. |

## Live testing boundary

| Lane | Status | Notes |
|---|---|---|
| Read-only API/runtime coordinate refresh | **Allowed** | No movement, no player input, no CE/x64dbg; used to refresh RRAPICOORD/API-now truth. |
| Same-target read-only memory candidate readback | **Allowed** | Candidate scoring only; does not promote movement truth by itself. |
| `ProofOnly` validation | **Allowed** | Read-only proof gate; movementSent must remain `false`. |
| Exact-HWND/window capture | **Allowed** | Visual evidence only; no player-control input. |
| Native screenshot key | **Ask / only when explicitly in scope** | It sends a key even if non-movement. |
| Movement / forward smoke / navigation / player-control keys | **Blocked** | Requires current proof promotion, same-target `ProofOnly`, and explicit movement approval. |
| CE/x64dbg attach/watchpoints | **Blocked without fresh explicit approval** | Crash/risk-sensitive lane. |

## Local native screenshot keybind

| Field | Value |
|---|---|
| Status | **Verified working for this local RIFT installation** |
| RIFT action | `Take Screenshot` |
| Current keybind | **`NUM PAD *` / `numpad_multiply` / `VK_MULTIPLY` / `0x6A`** |
| Keybind proof source | `C:\Program Files (x86)\Glyph\Games\RIFT\Live\mykeybindings` |
| Exported keybinding record | `02 6A 07 AA 9C 01` for action id `20010` |
| Default comparison | `02 2C 07 AA 9C 01` = default `PrintScreen`; local export overrides it to `NUM PAD *` |
| Live proof | A new native RIFT screenshot was created at `2026-05-14T05:49:34Z`: `C:\Users\mrkoo\OneDrive\Documents\RIFT\Screenshots\2026-05-14_014934.jpg` |
| Repo proof packet | `scripts/captures/native-screenshot-keybind-20260514-014933/native-screenshot-result.json` |
| Strong rule | Use only `NUM PAD *` for native RIFT screenshots on this machine. Do **not** use `Ctrl+P`, `Control+P`, `PrtSc`, or Snipping Tool automation. |
| Truth scope | Visual/screenshot evidence only; this is **not** coordinate or movement truth. |

Key proof artifacts:

| Artifact | Result |
|---|---|
| `scripts/captures/coordinate-proof-route-current-reacquire-20260514-074641-promotion-readiness-routing/coordinate-proof-route.json` | **Latest route:** API-memory match for `api-family-hit-000001` at `0x268E2BC09E0`; read-only candidate only, movement blocked. |
| `scripts/captures/riftscan-milestone-review-20260514-120033.json` | **Latest milestone gate:** route selection applied and selected `latest-coordinate-proof-route-memory-readback`; status `ready-for-read-only-proof`. |
| `scripts/captures/coordinate-proof-readiness-gate-20260514-080033-route-selection/summary.json` | **Latest readiness gate:** `passed` / `ready-for-read-only-proof`; `movementAllowed=false`; proof pointer warnings preserved. |
| `scripts/captures/rrapicoord-readonly-refresh-20260514-042156-095/rift-api-reference-currentpid-2928-20260514-082156.json` | Historical read-only API refresh: RRAPICOORD1 current API/runtime coordinate `7399.1099, 871.77, 3029.96` captured for PID `2928` / HWND `0xC0994`; `movementSent=false`, `noCheatEngine=true`, `savedVariablesUse=none`. |
| `scripts/captures/riftscan-readonly-currenttruth-compare-20260514-042242-452/riftscan-riftreader-currentpid-2928-readback-wrapper-summary-20260514-042242.json` | Historical same-target read-only memory readback: candidate file decoded successfully, `ReferenceMatchCount=0`; prior best `family-snapshot-hit-000004` stayed stable/source-preview-matching but stale against API-now by max abs delta `4.29000234374962`. |
| `scripts/captures/native-screenshot-keybind-20260514-014933/native-screenshot-result.json` | Native screenshot keybind verification passed: exported local RIFT keybind is `NUM PAD *` / `VK_MULTIPLY`; exact target PID `2928`/HWND `0xC0994`; screenshot file `2026-05-14_014934.jpg` created; no movement/CE/x64dbg/reloadui. |
| `scripts/captures/riftscan-proof-pose-20260514-030047/pose-api-reference.json` | Prior RRAPICOORD reference used for earlier readback scoring; superseded by the `08:22:23Z` read-only refresh above. |
| `scripts/captures/riftscan-proof-pose-20260514-030047/riftscan-riftreader-currentpid-2928-readback-wrapper-summary-20260513-230104.json` | Prior readback: `ReferenceMatchCount=1`, selected `family-snapshot-hit-000004`; superseded by the latest read-only comparison with `ReferenceMatchCount=0`. |
| `scripts/captures/rrapicoord-reference-refresh-20260513-231853/rift-api-reference-currentpid-2928-20260514-031853.json` | Fresh RRAPICOORD reference used for no-attach x64dbg readiness. |
| `scripts/captures/x64dbg-no-attach-readiness-packet-20260514-031908-072876/summary.json` | Passed no-attach readiness: exact target, fresh API coordinate, current-truth candidate, no debugger attach started. |
| `scripts/captures/family-snapshot-sequence-currentpid-2928-20260514-032849-991117/summary.json` | Passive no-input family sequence now works with `RRAPICOORD1` and current-truth priors; blocked intentionally because no displaced pose was captured. |
| `scripts/captures/family-snapshot-sequence-currentpid-2928-20260514-033507-237928/summary.json` | Plan-only smoke: no PID/HWND/prior supplied; helper bootstrapped all target fields and `currentTruth=0x268D5A80730` from current truth. |
| `scripts/captures/family-snapshot-sequence-currentpid-2928-20260514-032849-991117/passive-stability-analysis/delta-summary.json` | Offline passive-stability analysis: `13` stable near-reference candidates extracted; still blocked with `blocked-no-displaced-pose` and not promotion-eligible. |
| `scripts/captures/riftscan-proof-pose-20260514-034648/riftscan-riftreader-currentpid-2928-readback-wrapper-summary-20260513-234714.json` | Prior read-only proof-pose confirmation: `family-snapshot-hit-000004`, `ReferenceMatchCount=1`, max abs delta `4.1503906231810106e-05`; no longer current after the `08:22:23Z` API-now refresh. |
| `scripts/captures/family-snapshot-sequence-currentpid-2928-20260514-032849-991117/passive-stability-analysis/readback-currentpid-2928-20260514-0355-top13-fixed-sort/riftscan-riftreader-currentpid-2928-readback-wrapper-summary-20260513-235522.json` | Prior passive candidate readback: importer-compatible candidates, `ReferenceMatchCount=3`; fixed NaN-safe ranking put then-current duplicate heap copies first: `0x268D5A80730`, `0x268D5F6C8E0`, `0x268D5FC52B0`. |
| `scripts/captures/pointer-family-scan-20260514-035912-983112/summary.json` | Grouped duplicate-copy pointer scan: exact coordinate copies had `0` direct refs; segment base `0x268D5A80000` had `22` heap refs, `0` module refs. |
| `scripts/captures/coordinate-duplicate-disambiguation-20260514-040347-025295/summary.json` | Offline duplicate disambiguation packet ranks `0x268D5A80730` first, then `0x268D5FC52B0`, then `0x268D5F6C8E0`; candidate-only. |
| `scripts/captures/pointer-owner-batch-currentpid-2928-20260514-040413-052088/summary.json` | Owner batch inspected `36` owners and found `9` module-RVA hints, top `0x2641E38`; no static root proven. |
| `scripts/captures/family-snapshot-sequence-currentpid-2928-20260514-040711-152712/summary.json` | Plan-only family sequence now bootstraps ranked duplicate-copy priors from current truth: `currentTruth`, `duplicateCopy2`, `duplicateCopy3`; no memory read/input. |
| `scripts/captures/root-signature-module-hint-sweep-20260514-041048-549694/summary.json` | Top duplicate-owner module-RVA `0x2641E38` sweep: `567` module-pointer hits, `0` non-zero owner-field candidates, `236` non-zero parent-slot candidates; candidate-only/no root. |
| `scripts/captures/root-signature-batch-sweep-currentpid-2928-20260514-041136-003958/summary.json` | Batch swept `6` additional duplicate-owner RVAs; completed, but stayed heap-only/no static root. |
| `scripts/captures/family-snapshot-sequence-currentpid-2928-20260514-041256-974242/summary.json` | Expanded no-input duplicate-prior family sequence read target memory safely, captured baseline + passive poses, and remained blocked intentionally because there was no displaced pose. |
| `scripts/captures/family-snapshot-sequence-currentpid-2928-20260514-041256-974242/delta-analysis/readback-currentpid-2928-20260514-0416-top14-all/riftscan-riftreader-currentpid-2928-readback-wrapper-summary-20260514-001550.json` | Readback of all `14` expanded passive candidates: `10` current reference matches, `14` stable decoded candidates, no input/CE/movement; still candidate-only. |
| `scripts/captures/riftscan-milestone-review-20260514-041751.json` | Historical post-expanded-passive milestone gate: `ready-for-read-only-proof`; movement remains blocked. |
| `scripts/captures/rrapicoord-scan-diagnostics-20260514-030154-581879/summary.json` | Usable marker present after direct robust scan. |
| `scripts/captures/rrapicoord-addon-state-diagnostics-20260514-030154-988294/summary.json` | Addon installed and live marker observed. |

## Movement gate

| Gate | Status |
|---|---|
| Read-only live testing | **Allowed** |
| Player-control / movement allowed | **No** |
| Latest selected candidate | `api-family-hit-000001` at `0x268E2BC09E0` |
| Selection source | `latest-coordinate-proof-route-memory-readback` |
| Reason | Latest route has API-now/memory-now agreement for a read-only candidate, but promotion is blocked by missing fresh displaced/two-reference proof and no movement-grade proof anchor. |
| Required before movement | Fresh displaced/two-reference or static-chain proof + promotion readiness + same-target `ProofOnly` + explicit movement approval. |

## Latest memory candidate status

| Field | Value |
|---|---|
| Candidate | `api-family-hit-000001` |
| Address | `0x268E2BC09E0` |
| Latest status | **API-memory match candidate, not promoted** |
| Fresh API reference | `7399.1099, 871.77, 3029.96` at `2026-05-14T11:46:05.1378983Z` |
| Candidate file | `scripts/captures/family-scan-currentpid-2928-20260514-114535-319032/api-family-vec3-candidates.jsonl` |
| Readback summary | `scripts/captures/riftscan-proof-readonly-current-after-drift-best-1-20260514-114545/riftscan-riftreader-currentpid-2928-readback-wrapper-summary-20260514-074606.json` |
| ReferenceMatchCount | `2` |
| Max abs delta vs API-now | `4.1503906231810106e-05` |
| Source preview still matches readback | `True` |
| Stable across readback samples | `True` |
| Promotion readiness | `blocked-promotion-readiness` |
| Proof-anchor promotion allowed | `False` |
| Truth status | **candidate-only / current API-memory match / not movement proof** |
| Meaning | Use this candidate for read-only proof planning ahead of older family-import snapshots; do not use it as movement-grade coordinate truth until promotion gates pass. |

## Latest coordinate reacquisition evidence

| Step | Artifact | Result |
|---|---|---|
| Fresh broad family snapshot | `scripts/captures/coordinate-family-snapshot-currentpid-2928-20260514-024349/family-snapshot-summary.json` | Read-only scan captured `47,193` triplets / `12` near-reference triplets over `363,360,256` bytes. |
| Post-scan reference guard | `scripts/captures/coordinate-family-snapshot-currentpid-2928-20260514-024349/post-scan-reference/fresh-reference-coordinate.json` | Passed: pre/post RRAPICOORD stable with max abs drift `0.0`. |
| Passive sequence helper repair | `scripts/captures/family-snapshot-sequence-currentpid-2928-20260514-032849-991117/summary.json` | Read-only/no-input sequence captured two RRAPICOORD references and `33,554,432` bytes per pose from the current-truth family neighborhood; blocked with `blocked-no-displaced-pose` as expected. |
| Passive stability candidate extraction | `scripts/captures/family-snapshot-sequence-currentpid-2928-20260514-032849-991117/passive-stability-analysis/candidate-vec3.json` | Extracted `13` candidate-only stable near-reference triplets from the passive no-input sequence; best `snapshot-passive-stable-268D4B2A2A0-xyz` at `0x268D4B2A2A0`, `promotionEligible=false`. |
| Passive stability readback | `scripts/captures/family-snapshot-sequence-currentpid-2928-20260514-032849-991117/passive-stability-analysis/readback-currentpid-2928-20260514-0355-top13-fixed-sort/riftscan-riftreader-currentpid-2928-readback-wrapper-summary-20260513-235522.json` | Read-only readback imported the passive candidates successfully; `3` then-current reference matches remained after NaN-safe ranking: `0x268D5A80730`, `0x268D5F6C8E0`, and `0x268D5FC52B0`. |
| Expanded duplicate-prior passive sequence | `scripts/captures/family-snapshot-sequence-currentpid-2928-20260514-041256-974242/summary.json` | Baseline + passive no-input snapshots from current-truth/duplicate priors; `14` passive candidates / `7` families; blocked as expected with no displaced pose. |
| Expanded passive readback | `scripts/captures/family-snapshot-sequence-currentpid-2928-20260514-041256-974242/delta-analysis/readback-currentpid-2928-20260514-0416-top14-all/riftscan-riftreader-currentpid-2928-readback-wrapper-summary-20260514-001550.json` | `10` of `14` candidates matched the then-current RRAPICOORD reference on readback; candidate-only heap copies, not proof, and superseded by the latest API-now stale-candidate result. |
| Underpowered reference capture | `scripts/captures/riftscan-proof-pose-20260514-024955` | Blocked safely; no usable full marker from the narrow 512-byte context. Superseded, not proof evidence. |
| Proof-pose wrapper fix | `scripts/capture-riftscan-proof-pose.ps1` | Now passes `4096` context bytes, `512` max hits, `5` attempts, `1500ms` retry delay to the reference capture helper. |
| Repeat proof-pose confirmation | `scripts/captures/riftscan-proof-pose-20260514-030047/riftscan-riftreader-currentpid-2928-readback-wrapper-summary-20260513-230104.json` | Second robust pass again selected `family-snapshot-hit-000004`; read-only only. |
| Milestone strategy gate | `scripts/captures/riftscan-milestone-review-20260514-030120.json` | Ready for more read-only proof; movement still not allowed. |

## Static-chain / pointer status

| Evidence | Result |
|---|---|
| `scripts/captures/pointer-family-scan-20260514-030426-089234/summary.json` | Direct scan for `0x268D5A80730` found `0` exact pointer refs. |
| `scripts/captures/pointer-family-scan-20260514-030436-657736/summary.json` | Family-base scan for `0x268D5A80000` found `19` heap refs, `0` module/RIFT-module hits. |
| `scripts/captures/pointer-owner-batch-currentpid-2928-20260514-030612-600628/summary.json` | `19` owner windows inspected; `20` module-RVA hints found, top `0x263E5F8`, but candidate-only. |
| `scripts/captures/root-signature-batch-sweep-currentpid-2928-20260514-030832-821868/summary.json` | Manual top-RVA root sweep matched a self-derived owner signature only; no static root proven. |
| `scripts/captures/pointer-family-scan-20260514-030856-814392/summary.json` | Reverse pointer scan for self-derived owner base `0x26887C277C8` found `0` refs. |
| `scripts/captures/x64dbg-no-attach-readiness-packet-20260514-031908-072876/summary.json` | No-attach readiness passed with current-truth `family-snapshot-hit-000004`; stale hidden `latest/best` candidate fallback is now blocked by default. |
| `scripts/captures/x64dbg-coord-chain-plan-20260514-031908-113310/coord-chain-plan-summary.json` | Planned only; ready for current-turn approval, but no x64dbg attach/watchpoint/access event was executed. |
| `scripts/captures/pointer-family-scan-20260514-035912-983112/summary.json` | Duplicate-copy pointer scan: `0` direct refs to exact coordinate copies; heap/family base refs only, no module hits. |
| `scripts/captures/pointer-owner-batch-currentpid-2928-20260514-040413-052088/summary.json` | Candidate module-RVA hints only; top `0x2641E38`, not connected to a proven static root. |
| `scripts/captures/root-signature-module-hint-sweep-20260514-041048-549694/summary.json` | Top duplicate-owner RVA `0x2641E38` produced many candidate parent leads but `0` non-zero owner-field candidates; no static root. |
| `scripts/captures/root-signature-family-classifier-20260514-041059-384649/summary.json` | Classified `106` priority parent-slot leads from the `0x2641E38` sweep; all candidate-only, not movement-proof. |
| `scripts/captures/root-signature-batch-sweep-currentpid-2928-20260514-041136-003958/summary.json` | Additional duplicate-owner RVA batch completed; no selected sweep established a static owner/coord chain. |
| Static pointer chain | **not proven** |

## Explicitly stale / invalid / not current best

| Item | Why not current truth |
|---|---|
| PID `57656` / HWND `0x5417BC` proof-anchor cache | Old process epoch. |
| `0x268D506BC50` / `family-snapshot-hit-000003` | Previous readback lead; latest robust readback did not match current RRAPICOORD reference. Keep only as family-context evidence. |
| `riftscan-proof-pose-20260514-024955` reference capture | Blocked by underpowered RRAPICOORD context; superseded by robust capture and wrapper fix. |
| `0x268D1FA6120` / old `family-snapshot-hit-000001` | Repeat readback returned `ReferenceMatchCount=0` and decoded near-zero floats. |
| `0x268D1EF0870` / prior start-reference snapshot candidate | Matched only an older snapshot start reference; failed later current-reference readback after drift. |
| SavedVariables coordinates | Post-save snapshots only, not live IPC. |
| Old RRAPICOORD references | Timestamped scoring references only after age budget expires. |

## Current blockers

- Latest read-only memory readback found zero current-reference matches.
- Movement-grade proof anchor missing.
- Same-target `ProofOnly` not passing.
- Static pointer chain not proven.
- Candidate restart validation not done.
- Duplicate heap coordinate copies are not yet disambiguated across multiple poses; an earlier expanded passive readback showed `10` then-current reference-matching heap copies, but the latest API-now comparison invalidated the prior current-truth candidate file.
- Module-RVA hints are candidate-only and not connected to a stable/static root; latest module-hint/root sweeps stayed heap-only/no-static-root.
- x64dbg access events have not been captured; any live debugger capture still requires explicit current-turn approval and the bounded attach policy.
- Displaced-pose or approved x64dbg/access evidence is still missing; passive stability candidates are family-context seeds only and not movement proof.
- Passive-stability readback previously found three then-current reference-matching heap copies after fixed NaN-safe ranking; displaced-pose/static-chain proof is still required to choose a movement-grade source.
- Duplicate-copy pointer scan found heap/family owner hints but no module/static pointer hits; `0x2641E38` is candidate-only and not a proven static root.
- ChromaLink world-state stale/unhealthy.
- Do not keep repeating heap-only module-RVA sweeps without new evidence; next signal must come from displaced-pose delta or approved access-chain evidence.

## Canonical files

| File | Purpose |
|---|---|
| `docs/recovery/current-truth.md` | This concise human dashboard. |
| `docs/recovery/current-truth.json` | Small machine-readable canonical truth. |
| `docs/recovery/historical/current-truth-full-2026-05-14-0216-before-trim.md` | Historical full chronology; stale/audit only. |
| `docs/handoffs/2026-05-14-0226-static-chain-heap-only-followup.md` | Latest static-chain follow-up handoff. |
| `scripts/captures/x64dbg-no-attach-readiness-packet-20260514-031908-072876/summary.json` | Latest no-attach x64dbg readiness packet; current-truth candidate, no attach. |
| `scripts/captures/family-snapshot-sequence-currentpid-2928-20260514-032849-991117/summary.json` | Latest passive family-snapshot sequence; RRAPICOORD default, current-truth prior first, no input. |
| `scripts/captures/family-snapshot-sequence-currentpid-2928-20260514-033507-237928/summary.json` | Latest current-truth bootstrapped plan-only sequence; no manual PID/HWND/prior needed. |
| `scripts/captures/family-snapshot-sequence-currentpid-2928-20260514-032849-991117/passive-stability-analysis/candidate-vec3.json` | Candidate-only passive stable triplets from the latest no-input family sequence; family-context seeds only. |
| `scripts/captures/family-snapshot-sequence-currentpid-2928-20260514-032849-991117/passive-stability-analysis/readback-currentpid-2928-20260514-0355-top13-fixed-sort/riftscan-riftreader-currentpid-2928-readback-wrapper-summary-20260513-235522.json` | Latest passive candidate readback; narrows current live duplicate heap copies with fixed NaN-safe ranking but remains candidate-only. |
| `scripts/captures/pointer-family-scan-20260514-035912-983112/summary.json` | Latest grouped pointer scan around the three duplicate coordinate copies. |
| `scripts/captures/coordinate-duplicate-disambiguation-20260514-040347-025295/summary.json` | Latest offline duplicate-copy ranking packet. |
| `scripts/captures/pointer-owner-batch-currentpid-2928-20260514-040413-052088/summary.json` | Latest owner/ref-storage inspection from duplicate pointer scan. |
| `scripts/captures/family-snapshot-sequence-currentpid-2928-20260514-040711-152712/summary.json` | Latest plan-only sequence showing duplicate-copy current-truth priors are imported. |
| `scripts/captures/root-signature-module-hint-sweep-20260514-041048-549694/summary.json` | Latest top module-RVA sweep for duplicate-owner hint `0x2641E38`; candidate-only/no static root. |
| `scripts/captures/root-signature-family-classifier-20260514-041059-384649/summary.json` | Latest classifier output for `0x2641E38`; exports candidate parent leads only. |
| `scripts/captures/root-signature-batch-sweep-currentpid-2928-20260514-041136-003958/summary.json` | Latest batch module-hint sweep from duplicate owner batch. |
| `scripts/captures/family-snapshot-sequence-currentpid-2928-20260514-041256-974242/summary.json` | Latest expanded no-input duplicate-prior family sequence. |
| `scripts/captures/family-snapshot-sequence-currentpid-2928-20260514-041256-974242/delta-analysis/readback-currentpid-2928-20260514-0416-top14-all/riftscan-riftreader-currentpid-2928-readback-wrapper-summary-20260514-001550.json` | Prior expanded passive candidate readback; `10` then-current heap copies, candidate-only. |
| `scripts/captures/riftscan-milestone-review-20260514-041751.json` | Latest post-expanded-passive milestone review; read-only proof allowed, movement blocked. |
| `scripts/captures/rrapicoord-readonly-refresh-20260514-042156-095/rift-api-reference-currentpid-2928-20260514-082156.json` | Latest read-only API/runtime coordinate refresh; PID `2928`, HWND `0xC0994`, coordinate `7399.1099, 871.77, 3029.96`, no movement/CE/x64dbg/SavedVariables live truth. |
| `scripts/captures/riftscan-readonly-currenttruth-compare-20260514-042242-452/riftscan-riftreader-currentpid-2928-readback-wrapper-summary-20260514-042242.json` | Latest same-target read-only memory-candidate comparison; `ReferenceMatchCount=0`, prior best heap candidate stale against API-now. |
| `docs/recovery/coord-truth-readonly-actions-1-3-summary-2026-05-14-042849.html` | Human-readable timestamped summary for actions 1-3. |
| `docs/recovery/native-rift-screenshot-backend.md` | Canonical native screenshot rule: this local RIFT installation uses `NUM PAD *`; live proof shows it works. |

## Next best action

Capture a displaced-pose family snapshot sequence when safe/manual displacement is available; otherwise use approved x64dbg/access-chain evidence. Do **not** repeat heap-only module-RVA sweeps without new evidence. Movement remains blocked until delta/static-chain proof and same-target `ProofOnly` pass.

## Visual/capture proof-route policy — 2026-05-14T10:06:27Z

| Field | Value |
|---|---|
| Route generator | `scripts/coordinate_proof_route.py` |
| Latest route | `scripts/captures/coordinate-proof-route-current-reacquire-20260514-20260514-083422-raw-valid-html/coordinate-proof-route.json` |
| Latest route HTML | `scripts/captures/coordinate-proof-route-current-reacquire-20260514-20260514-083422-raw-valid-html/coordinate-proof-route.html` |
| Latest route pointer | `scripts/captures/latest-coordinate-proof-route.json` |
| Latest route status | `api-memory-match` |
| Latest action summary HTML | `docs/recovery/coordinate-proof-route-actions-1-10-summary-2026-05-14-123423-manual-displacement-runner.html` |
| Latest compact truth JSON | `docs/recovery/current-truth-compact-summary-20260514-123423.json` |
| Latest compact truth Markdown | `docs/recovery/current-truth-compact-summary-20260514-123423.md` |
| Latest compact truth HTML | `docs/recovery/current-truth-compact-summary-20260514-123423.html` |
| Latest scan-profile plan | `scripts/captures/coordinate-scan-profiles-currentpid-2928-20260514-063920-center-dryrun/summary.json` |
| Latest scan-profile plan HTML | `scripts/captures/coordinate-scan-profiles-currentpid-2928-20260514-063920-center-dryrun/summary.html` |
| Latest manual displacement blocker | `scripts/captures/coordinate-scan-profiles-currentpid-2928-20260514-1027-displaced-required/summary.json` |
| Latest manual displacement blocker HTML | `scripts/captures/coordinate-scan-profiles-currentpid-2928-20260514-1027-displaced-required/summary.html` |
| Latest candidate comparison | `scripts/captures/coordinate-candidate-comparison-currentpid-2928-20260514-081730-displacement-gated/summary.json` |
| Latest candidate comparison HTML | `scripts/captures/coordinate-candidate-comparison-currentpid-2928-20260514-081730-displacement-gated/summary.html` |
| Latest preflight with route | `scripts/captures/coordinate-proof-preflight-20260514-100345-771125/summary.json` |
| Latest read-only reacquisition | `scripts/captures/family-scan-currentpid-2928-20260514-110753-631012/family-scan-summary.json` |
| Latest milestone review with route | `scripts/captures/riftscan-milestone-review-20260514-114648.json` |
| Visual evidence role | `sidecar_only_not_coordinate_or_movement_truth` |
| Movement allowed by visual evidence | `false` |
| Latest generated center file | `scripts/captures/coordinate-center-file-currentpid-2928-20260514-063920/coordinate-scan-centers.json` |
| Latest generated center file summary | `scripts/captures/coordinate-center-file-currentpid-2928-20260514-063920/summary.json` |
| Latest generated center file HTML | `scripts/captures/coordinate-center-file-currentpid-2928-20260514-063920/summary.html` |
| Latest scan-profile run | `scripts/captures/coordinate-scan-profiles-currentpid-2928-20260514-074529-current-after-drift/summary.json` |
| Latest scan-profile run HTML | `scripts/captures/coordinate-scan-profiles-currentpid-2928-20260514-074529-current-after-drift/summary.html` |
| Latest scan-profile ranking | `scripts/captures/coordinate-scan-profiles-currentpid-2928-20260514-074529-current-after-drift/summary.json` |
| Latest candidate comparison status | `blocked` |
| Latest route with candidate routing | `scripts/captures/coordinate-proof-route-current-reacquire-20260514-20260514-083422-raw-valid-html/coordinate-proof-route.json` |
| Latest candidate routing status | `candidate-routing-ready` |
| Latest candidate routing center count | `16` |
| Latest displaced-reference readiness | `scripts/captures/coordinate-displaced-reference-readiness-currentpid-2928-20260514-080912-fresh-attempt/summary.json` |
| Latest displaced-reference readiness HTML | `scripts/captures/coordinate-displaced-reference-readiness-currentpid-2928-20260514-080912-fresh-attempt/summary.html` |
| Latest displaced-reference readiness status | `blocked` |
| Latest displaced readiness status | `blocked` |
| Latest displaced readiness summary | `scripts/captures/coordinate-displaced-reference-readiness-currentpid-2928-20260514-080912-fresh-attempt/summary.json` |
| Latest displaced readiness HTML | `scripts/captures/coordinate-displaced-reference-readiness-currentpid-2928-20260514-080912-fresh-attempt/summary.html` |
| Latest session action summary HTML | `docs/recovery/coordinate-proof-route-actions-1-10-summary-2026-05-14-123423-manual-displacement-runner.html` |
| Latest milestone review status | `ready-for-read-only-proof` |
| Latest promotion readiness status | `blocked-promotion-readiness` |
| Latest proof-anchor promotion allowed | `false` |
| Latest proof readiness gate | `scripts/captures/coordinate-proof-readiness-gate-20260514-074648-route/summary.json` |
| Latest proof readiness gate status | `passed` |

Rules:

- Exact-HWND capture, raw BGRA, crop, and diff artifacts are useful visual evidence, but they are **not coordinate proof**.
- Visual evidence cannot promote coordinate truth unless fresh API/runtime reference and same-target memory readback agree.
- The latest proof route attached visual capture and a fresh API reference, then blocked readiness because read-only current-PID reacquisition found `0` XYZ triplets near API-now after scanning `478150656` bytes in `76.006` seconds.
- Static-root work must start from current API/memory agreement; heap-copy, no-hit reacquisition, or visual evidence alone is not a static root.
- Movement remains blocked until the normal proof gate passes and explicit movement approval is granted.

## Route-selected candidate milestone — 2026-05-14T12:04:16Z

| Field | Value |
|---|---|
| Milestone review | `scripts/captures/riftscan-milestone-review-20260514-120033.json` |
| Review status | `ready-for-read-only-proof` |
| Route selection applied | `True` |
| Selected candidate source | `latest-coordinate-proof-route-memory-readback` |
| Candidate file | `scripts/captures/family-scan-currentpid-2928-20260514-114535-319032/api-family-vec3-candidates.jsonl` |
| Candidate ID | `api-family-hit-000001` |
| Candidate address | `0x268E2BC09E0` |
| Memory readback | `scripts/captures/riftscan-proof-readonly-current-after-drift-best-1-20260514-114545/riftscan-riftreader-currentpid-2928-readback-wrapper-summary-20260514-074606.json` |
| Readiness gate | `scripts/captures/coordinate-proof-readiness-gate-20260514-080033-route-selection/summary.json` |
| Readiness verdict | `ready-for-read-only-proof` |
| Movement allowed | `None` |
| HTML summary | `docs/recovery/coordinate-proof-route-actions-1-10-summary-2026-05-14-120416.html` |
| Handoff | `docs/handoffs/2026-05-14-120416-route-selection-candidate-gate.md` |

Blockers preserved: fresh displaced/two-reference match is missing, displaced readiness is `blocked`, proof-anchor promotion allowed is `False`, and movement remains blocked.

## Fresh no-displacement route milestone — 2026-05-14T12:12:52Z

| Field | Value |
|---|---|
| Route | `scripts/captures/coordinate-proof-route-current-reacquire-20260514-080919-fresh-no-displacement/coordinate-proof-route.json` |
| Route status | `api-memory-match` |
| Milestone review | `scripts/captures/riftscan-milestone-review-20260514-121022.json` |
| Review status | `ready-for-read-only-proof` |
| Readiness gate | `scripts/captures/coordinate-proof-readiness-gate-20260514-081022-fresh-no-displacement/summary.json` |
| Candidate | `api-family-hit-000001` |
| Address | `0x268E2BC09E0` |
| Candidate comparison status | `api-candidate-two-reference-match` |
| Both-reference match count | `2` |
| Displaced readiness | `blocked` |
| Displaced blockers | `['displaced-reference-age-exceeded:1363.884>300.0', 'displaced-reference-planar-distance-too-small:5.6e-05<1.0']` |
| Pointer scan | `scripts/captures/pointer-family-scan-route-selected-currentpid-2928-20260514-081030/summary.json` |
| Pointer scan direct hits | `None` |
| HTML summary | `docs/recovery/coordinate-proof-route-actions-1-10-summary-2026-05-14-121252.html` |
| Handoff | `docs/handoffs/2026-05-14-121252-fresh-no-displacement-route-gate.md` |

Conclusion: the candidate remains a strong same-pose read-only lead, but the new reference did not produce valid displaced proof. Do not promote or move from this evidence alone.

## Displacement-gated comparison milestone — 2026-05-14T12:19:34Z

| Field | Value |
|---|---|
| Route | `scripts/captures/coordinate-proof-route-current-reacquire-20260514-081737-displacement-gated/coordinate-proof-route.json` |
| Route status | `api-memory-match` |
| Candidate comparison | `scripts/captures/coordinate-candidate-comparison-currentpid-2928-20260514-081730-displacement-gated/summary.json` |
| Comparison status | `blocked` |
| Raw both-reference matches | `2` |
| Valid both-reference matches | `0` |
| Comparison blockers | `['displaced-api-reference-planar-distance-too-small:5.37587e-05<1.0']` |
| Displaced readiness | `blocked` |
| Displaced planar distance | `5.59732083466666e-05` |
| Promotion readiness | `blocked-promotion-readiness` |
| Handoff | `docs/handoffs/2026-05-14-121934-displacement-gated-comparison.md` |
| HTML summary | `docs/recovery/coordinate-proof-route-actions-1-10-summary-2026-05-14-121934.html` |

Conclusion: same-pose matches cannot be promoted. The valid two-reference count is now fail-closed to `0` until a real displaced pose is captured.
