# RiftReader Current Truth

_Last updated: 2026-05-14T05:49:34Z._

## Verdict

**Movement is blocked.** The live `RRAPICOORD1` reference surface is usable again and the proof-pose wrapper now uses a wider RRAPICOORD scan window. Two consecutive robust read-only proof-pose runs selected **`family-snapshot-hit-000004` at `0x268D5A80730`** as the latest current-reference match. The no-attach x64dbg readiness packet now uses the **current-truth candidate** instead of hidden `latest/best` candidate fallback and passed preflight. The family-snapshot sequence helper now defaults to `RRAPICOORD1`, imports current-truth PID/HWND/start/module defaults, and prioritizes the current-truth candidate as the top family prior. Offline passive-stability analysis of the no-input sequence extracted **13 stable near-reference triplet candidates** for family-context seeding, and a fresh readback narrowed those to **3 current reference-matching heap copies** (`0x268D5A80730`, `0x268D5F6C8E0`, and `0x268D5FC52B0`). A grouped pointer/family scan ranks `0x268D5A80730` highest by segment-base pointer context (`22` heap refs), and owner-batch inspection found `9` module-RVA hints with top `0x2641E38`. I followed that lead with module-hint/root sweeps and an expanded no-input duplicate-prior family sequence: the sweeps stayed heap-only/no-static-root, while the expanded passive readback found **10 current reference-matching heap copies**. This remains **candidate-only** because there is no displaced-pose delta, no proven static root, no restart validation, and no same-target `ProofOnly` pass.

## Current target epoch

| Field | Value |
|---|---|
| Process | `rift_x64.exe` |
| PID | `2928` |
| HWND | `0xC0994` |
| Process start | `2026-05-13T16:17:56.208370Z` |
| Module base | `0x7FF71CD90000` |

## Live truth source

| Surface | Status | Notes |
|---|---|---|
| `ReaderBridge_RRAPICOORD1` | **current / usable for read-only proof** | Live `Inspect.Unit.Detail(player)`, `source=rift-api`, `savedVariablesUse=none`. Latest reference: `7403.4, 871.77, 3029.41` at `2026-05-14T03:19:00.9443165Z`. |
| ChromaLink world-state | stale / not authoritative | Still not the authority for coordinate proof in this lane. |
| SavedVariables | not live truth | Post-save snapshots only; never use as live movement truth. |

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
| `scripts/captures/native-screenshot-keybind-20260514-014933/native-screenshot-result.json` | Native screenshot keybind verification passed: exported local RIFT keybind is `NUM PAD *` / `VK_MULTIPLY`; exact target PID `2928`/HWND `0xC0994`; screenshot file `2026-05-14_014934.jpg` created; no movement/CE/x64dbg/reloadui. |
| `scripts/captures/riftscan-proof-pose-20260514-030047/pose-api-reference.json` | Latest RRAPICOORD reference used for readback scoring. |
| `scripts/captures/riftscan-proof-pose-20260514-030047/riftscan-riftreader-currentpid-2928-readback-wrapper-summary-20260513-230104.json` | Latest readback: `ReferenceMatchCount=1`, selected `family-snapshot-hit-000004`. |
| `scripts/captures/rrapicoord-reference-refresh-20260513-231853/rift-api-reference-currentpid-2928-20260514-031853.json` | Fresh RRAPICOORD reference used for no-attach x64dbg readiness. |
| `scripts/captures/x64dbg-no-attach-readiness-packet-20260514-031908-072876/summary.json` | Passed no-attach readiness: exact target, fresh API coordinate, current-truth candidate, no debugger attach started. |
| `scripts/captures/family-snapshot-sequence-currentpid-2928-20260514-032849-991117/summary.json` | Passive no-input family sequence now works with `RRAPICOORD1` and current-truth priors; blocked intentionally because no displaced pose was captured. |
| `scripts/captures/family-snapshot-sequence-currentpid-2928-20260514-033507-237928/summary.json` | Plan-only smoke: no PID/HWND/prior supplied; helper bootstrapped all target fields and `currentTruth=0x268D5A80730` from current truth. |
| `scripts/captures/family-snapshot-sequence-currentpid-2928-20260514-032849-991117/passive-stability-analysis/delta-summary.json` | Offline passive-stability analysis: `13` stable near-reference candidates extracted; still blocked with `blocked-no-displaced-pose` and not promotion-eligible. |
| `scripts/captures/riftscan-proof-pose-20260514-034648/riftscan-riftreader-currentpid-2928-readback-wrapper-summary-20260513-234714.json` | Latest read-only proof-pose confirmation: `family-snapshot-hit-000004`, `ReferenceMatchCount=1`, max abs delta `4.1503906231810106e-05`. |
| `scripts/captures/family-snapshot-sequence-currentpid-2928-20260514-032849-991117/passive-stability-analysis/readback-currentpid-2928-20260514-0355-top13-fixed-sort/riftscan-riftreader-currentpid-2928-readback-wrapper-summary-20260513-235522.json` | Passive candidate readback: importer-compatible candidates, `ReferenceMatchCount=3`; fixed NaN-safe ranking puts live duplicate heap copies first: `0x268D5A80730`, `0x268D5F6C8E0`, `0x268D5FC52B0`. |
| `scripts/captures/pointer-family-scan-20260514-035912-983112/summary.json` | Grouped duplicate-copy pointer scan: exact coordinate copies had `0` direct refs; segment base `0x268D5A80000` had `22` heap refs, `0` module refs. |
| `scripts/captures/coordinate-duplicate-disambiguation-20260514-040347-025295/summary.json` | Offline duplicate disambiguation packet ranks `0x268D5A80730` first, then `0x268D5FC52B0`, then `0x268D5F6C8E0`; candidate-only. |
| `scripts/captures/pointer-owner-batch-currentpid-2928-20260514-040413-052088/summary.json` | Owner batch inspected `36` owners and found `9` module-RVA hints, top `0x2641E38`; no static root proven. |
| `scripts/captures/family-snapshot-sequence-currentpid-2928-20260514-040711-152712/summary.json` | Plan-only family sequence now bootstraps ranked duplicate-copy priors from current truth: `currentTruth`, `duplicateCopy2`, `duplicateCopy3`; no memory read/input. |
| `scripts/captures/root-signature-module-hint-sweep-20260514-041048-549694/summary.json` | Top duplicate-owner module-RVA `0x2641E38` sweep: `567` module-pointer hits, `0` non-zero owner-field candidates, `236` non-zero parent-slot candidates; candidate-only/no root. |
| `scripts/captures/root-signature-batch-sweep-currentpid-2928-20260514-041136-003958/summary.json` | Batch swept `6` additional duplicate-owner RVAs; completed, but stayed heap-only/no static root. |
| `scripts/captures/family-snapshot-sequence-currentpid-2928-20260514-041256-974242/summary.json` | Expanded no-input duplicate-prior family sequence read target memory safely, captured baseline + passive poses, and remained blocked intentionally because there was no displaced pose. |
| `scripts/captures/family-snapshot-sequence-currentpid-2928-20260514-041256-974242/delta-analysis/readback-currentpid-2928-20260514-0416-top14-all/riftscan-riftreader-currentpid-2928-readback-wrapper-summary-20260514-001550.json` | Readback of all `14` expanded passive candidates: `10` current reference matches, `14` stable decoded candidates, no input/CE/movement; still candidate-only. |
| `scripts/captures/riftscan-milestone-review-20260514-041751.json` | Latest post-expanded-passive milestone gate: `ready-for-read-only-proof`; movement remains blocked. |
| `scripts/captures/rrapicoord-scan-diagnostics-20260514-030154-581879/summary.json` | Usable marker present after direct robust scan. |
| `scripts/captures/rrapicoord-addon-state-diagnostics-20260514-030154-988294/summary.json` | Addon installed and live marker observed. |

## Movement gate

| Gate | Status |
|---|---|
| Movement allowed | **No** |
| Reason | Candidate is read-only heap evidence only; no movement-grade proof anchor, no static pointer chain, no restart validation, and same-target `ProofOnly` has not passed. |
| Required before movement | Fresh API/runtime reference + current memory candidate agreement + current proof anchor/static chain + same-target `ProofOnly`. |

## Best current coordinate candidate

| Field | Value |
|---|---|
| Candidate | `family-snapshot-hit-000004` |
| Address | `0x268D5A80730` |
| Candidate file | `scripts/captures/coordinate-family-snapshot-currentpid-2928-20260514-024349/family-import-candidates.json` |
| Readback | `scripts/captures/riftscan-proof-pose-20260514-034648/riftscan-riftreader-currentpid-2928-readback-wrapper-summary-20260513-234714.json` |
| Reference | `scripts/captures/riftscan-proof-pose-20260514-034648/pose-api-reference.json` |
| Evidence | `ReferenceMatchCount=1`, `StableDecodedCandidateCount=10`, max abs delta `4.1503906231810106e-05`. |
| Truth status | **candidate-only, not movement proof** |
| Selection note | Multiple robust proof-pose/readback passes keep `000004` current; passive candidate readback also found duplicate live heap copy `0x268D5F6C8E0`. Prior `000003` remains family-context only. Duplicate coordinate copies still need multi-pose disambiguation. |

## Latest coordinate reacquisition evidence

| Step | Artifact | Result |
|---|---|---|
| Fresh broad family snapshot | `scripts/captures/coordinate-family-snapshot-currentpid-2928-20260514-024349/family-snapshot-summary.json` | Read-only scan captured `47,193` triplets / `12` near-reference triplets over `363,360,256` bytes. |
| Post-scan reference guard | `scripts/captures/coordinate-family-snapshot-currentpid-2928-20260514-024349/post-scan-reference/fresh-reference-coordinate.json` | Passed: pre/post RRAPICOORD stable with max abs drift `0.0`. |
| Passive sequence helper repair | `scripts/captures/family-snapshot-sequence-currentpid-2928-20260514-032849-991117/summary.json` | Read-only/no-input sequence captured two RRAPICOORD references and `33,554,432` bytes per pose from the current-truth family neighborhood; blocked with `blocked-no-displaced-pose` as expected. |
| Passive stability candidate extraction | `scripts/captures/family-snapshot-sequence-currentpid-2928-20260514-032849-991117/passive-stability-analysis/candidate-vec3.json` | Extracted `13` candidate-only stable near-reference triplets from the passive no-input sequence; best `snapshot-passive-stable-268D4B2A2A0-xyz` at `0x268D4B2A2A0`, `promotionEligible=false`. |
| Passive stability readback | `scripts/captures/family-snapshot-sequence-currentpid-2928-20260514-032849-991117/passive-stability-analysis/readback-currentpid-2928-20260514-0355-top13-fixed-sort/riftscan-riftreader-currentpid-2928-readback-wrapper-summary-20260513-235522.json` | Read-only readback imported the passive candidates successfully; `3` current reference matches remain after NaN-safe ranking: `0x268D5A80730`, `0x268D5F6C8E0`, and `0x268D5FC52B0`. |
| Expanded duplicate-prior passive sequence | `scripts/captures/family-snapshot-sequence-currentpid-2928-20260514-041256-974242/summary.json` | Baseline + passive no-input snapshots from current-truth/duplicate priors; `14` passive candidates / `7` families; blocked as expected with no displaced pose. |
| Expanded passive readback | `scripts/captures/family-snapshot-sequence-currentpid-2928-20260514-041256-974242/delta-analysis/readback-currentpid-2928-20260514-0416-top14-all/riftscan-riftreader-currentpid-2928-readback-wrapper-summary-20260514-001550.json` | `10` of `14` candidates still match current RRAPICOORD reference on readback; candidate-only heap copies, not proof. |
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

- Movement-grade proof anchor missing.
- Same-target `ProofOnly` not passing.
- Static pointer chain not proven.
- Candidate restart validation not done.
- Duplicate heap coordinate copies are not yet disambiguated across multiple poses; expanded passive readback now shows `10` current reference-matching heap copies.
- Module-RVA hints are candidate-only and not connected to a stable/static root; latest module-hint/root sweeps stayed heap-only/no-static-root.
- x64dbg access events have not been captured; any live debugger capture still requires explicit current-turn approval and the bounded attach policy.
- Displaced-pose or approved x64dbg/access evidence is still missing; passive stability candidates are family-context seeds only and not movement proof.
- Passive-stability readback found three current reference-matching heap copies after fixed NaN-safe ranking; displaced-pose/static-chain proof is still required to choose a movement-grade source.
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
| `scripts/captures/family-snapshot-sequence-currentpid-2928-20260514-041256-974242/delta-analysis/readback-currentpid-2928-20260514-0416-top14-all/riftscan-riftreader-currentpid-2928-readback-wrapper-summary-20260514-001550.json` | Latest expanded passive candidate readback; `10` current heap copies, candidate-only. |
| `scripts/captures/riftscan-milestone-review-20260514-041751.json` | Latest post-expanded-passive milestone review; read-only proof allowed, movement blocked. |
| `docs/recovery/native-rift-screenshot-backend.md` | Canonical native screenshot rule: this local RIFT installation uses `NUM PAD *`; live proof shows it works. |

## Next best action

Capture a displaced-pose family snapshot sequence when safe/manual displacement is available; otherwise use approved x64dbg/access-chain evidence. Do **not** repeat heap-only module-RVA sweeps without new evidence. Movement remains blocked until delta/static-chain proof and same-target `ProofOnly` pass.
