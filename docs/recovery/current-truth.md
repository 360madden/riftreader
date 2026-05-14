# Current Truth

_Last updated: 2026-05-14 00:26 UTC. Current live target remains `rift_x64` PID `2928`, HWND `0xC0994`, process start `2026-05-13T16:17:56.208370Z`, module base `0x7FF71CD90000`. Movement/navigation remains **blocked**. Coordinate proof readiness gate `scripts/captures/coordinate-proof-readiness-gate-20260514-002618-599647/summary.json` now fail-closes read-only proof and movement because the reference watchdog is blocked (`blocked-fresh-reference-unavailable`). The clean priority root-family lane remains exhausted (`15` exported leads, `49` scanned target/ref-storage addresses, `35` heap hits, `0` module/RIFT-module hits). The selected same-target candidate remains `same-target-268DF21ED30-xyz` and is candidate-only until fresh API-now/reference and memory-now proof pass. The stale runtime proof-anchor cache is historical only and must not shadow current PID `2928`._

**May 13 focus pivot:** RiftReader's active product focus is now **RIFT MMO
navigation**, not a full standalone reverse-engineering product. The candidate
coordinate-family/static-chain artifacts above remain useful supporting
evidence, but they are paused unless needed to unblock navigation proof gates.
For navigation work, movement remains blocked until fresh exact-target visual
gate, API-now vs memory-now/current-anchor proof, and same-target `ProofOnly`
pass.

**May 13 navigation reacquisition update:** no-input target-control preflight
`scripts/captures/target-control-currenttarget-20260513-171236/target-control-status.json`
blocked with `target-process-missing` and `target-window-missing` for
`rift_x64` / title `RIFT`. Do not run visual-gate, `ProofOnly`, route, or
movement work until the game target/window resolves again. If proof-anchor
recovery later blocks after the target returns, use broad family-group
sequential snapshots plus offline delta comparison rather than narrow
stale-address probing.

**May 13 21:26 UTC correction / current navigation gate:** direct process/window
enumeration proved `rift_x64.exe` was present as PID `2928`, HWND `0xC0994`,
title `RIFT`, responding. The earlier target-control miss was a helper bug when
called without exact `--pid`; `scripts/rift_live_test/target_control.py` now
enumerates process-name/title candidates instead of reporting a false
`target-process-missing`. Exact target-control passed at
`scripts/captures/target-control-currentpid-2928-20260513-171853/target-control-status.json`
and process-name/title target-control passed at
`scripts/captures/target-control-currenttarget-20260513-172535/target-control-status.json`.
Visual gate passed for exact PID/HWND at
`scripts/captures/visual-gate-currentpid-2928-20260513-171907/visual-gate-status.json`.
Same-target `ProofOnly` still blocked at
`scripts/captures/live-test-ProofOnly-20260513-225230/run-summary.json`; the
runner captured fresh API coordinate `7402.5898, 871.78, 3028.45`, detected the
old PID `57656` / HWND `0x5417BC` proof pointer mismatch, archived the old
pointer, and rewrote `current-proof-anchor-readback.json` as a
`blocked-target-drift` blocker for PID `2928` / HWND `0xC0994`.
Movement/navigation remains blocked.

**May 13 22:57 UTC repeat ProofOnly after stale-pointer invalidation:** a second
no-input `ProofOnly` at
`scripts/captures/live-test-ProofOnly-20260513-225716/run-summary.json` verified
the code no longer pulls `candidateId`/`matchFile` from the stale PID `57656`
pointer. It reacquired fresh API coordinate `7402.5898, 871.78, 3028.45` and
blocked cleanly with
`target_drift:current_proof_pointer_has_no_current_candidate:status=blocked-target-drift;candidateId=False;matchFile=False`.
No movement/input/CE was used.

**May 13 22:47 UTC current-PID broad scan:** after confirming target PID `2928`
/ HWND `0xC0994`, `scripts/scan_current_pid_coordinate_family.py` ran a
read-only broad scan with fresh RRAPICOORD reference
`7402.5898, 871.78, 3028.45`, tolerance `0.25`, `--scan-stride 1`, and
`--max-seconds 300`. Artifact:
`scripts/captures/family-scan-currentpid-2928-20260513-224733-693410/family-scan-summary.json`.
Result was **blocked** with `no_xyz_triplets_near_reference_found` after scanning
`339,738,624` bytes. This is negative current-PID evidence, not movement truth;
next recovery should widen strategy/window/tolerance or use the stronger
family snapshot/owner-chain artifacts rather than reverting to stale PID
`57656`.

Following the broad-family rule, a 39-range prior-first family snapshot sequence
with one bounded exact-HWND `w` discovery stimulus passed:
`scripts/captures/family-snapshot-sequence-currentpid-2928-20260513-212104-107039/summary.json`.
It used `20` current-PID scan-plan ranges plus prior exact/family ranges and
found `1000` candidates, `489` clean candidates, and `2` families. The top
delta candidate remained the known offset-copy family `0x268DF200000` /
`0x268DF21ED30`, but readback at
`scripts/captures/candidate-readback-currentpid-2928-20260513-212405-624415/candidate-readback-summary.json`
ranked a new lower-offset candidate `0x268BEF2C6A8` best by fresh API
offset-corrected readback. All readbacks remain
`candidate_only_not_movement_proof`; do not promote or navigate from them yet.

**May 13 21:33 UTC family comparison:** read-only neighborhood comparison
confirmed that the new `0x268BEF2C*` family is dense (`111` offset-corrected
hits in a 32 KiB window at
`scripts/captures/current-pid-family-neighborhood-inspector-20260513-212916-187601/summary.json`),
while the known `0x268DF21E*` family remains narrow (`3` hits at
`scripts/captures/current-pid-family-neighborhood-inspector-20260513-212916-188498/summary.json`).
Pointer scans of the new dense family found `0` refs/module hits; the known
family still has exactly one heap owner/ref-storage pointer to `0x268DF21ED20`
at `0x268D753AE40`
(`scripts/captures/pointer-family-scan-20260513-212916-310670/summary.json` and
`scripts/captures/pointer-family-scan-20260513-213041-143216/summary.json`).
The new committed helper `scripts/pointer_owner_neighborhood_inspector.py`
inspected that owner region at
`scripts/captures/pointer-owner-neighborhood-inspector-20260513-213230-349204/summary.json`;
it found the exact `0x268DF21ED20` pointer once and nearby module-pointer hints
at RVAs `0x26AAE70`, `0x272DBC0`, `0x263E950`, and `0x2662900`. These are
owner/source clues only. There is still no module/static root, no restart proof,
and no movement permission.

**May 13 21:40 UTC repeat-readback stability:** a third read-only Top 100
candidate readback at
`scripts/captures/candidate-readback-currentpid-2928-20260513-213805-490589/candidate-readback-summary.json`
still kept the narrow `0x268DF21E000` candidates stable, but the dense
`0x268BEF2C000` family fell to mismatch. New offline helper
`scripts/compare_candidate_readback_stability.py` compared the Top 20, Top 100,
and repeat Top 100 summaries at
`scripts/captures/candidate-readback-stability-20260513-214028-928580/summary.json`.
Result: `0x268DF21E000` had `3` stable repeat-match addresses
(`0x268DF21ED20`, `0x268DF21ED30`, `0x268DF21E6F0`); `0x268BEF2C000`
had `92` addresses, `0` stable repeat matches, `84` intermittent/dropped
matches, and `8` repeat mismatches. Treat the dense family as de-prioritized
until another movement-vector snapshot proves otherwise. Keep using the narrow
family as candidate seed evidence only; it is still not movement truth.

**May 13 23:05-23:14 UTC same-target candidate synthesis + stale-cache guard:**
current-PID readback
`scripts/captures/candidate-readback-currentpid-2928-20260513-213805-490589/candidate-readback-summary.json`
was converted into an importable RiftReader-owned candidate packet at
`scripts/captures/same-target-candidate-synth-20260513-230531-602926/same-target-candidates.json`.
It contains `3` current-PID, same-HWND candidates. The selected candidate is
`same-target-268DF21ED30-xyz` at `0x268DF21ED30`; it is offset-corrected within
`0.0024121093747453415` but direct delta is about `5.0027`, so it remains
candidate-only.

Milestone review
`scripts/captures/riftscan-milestone-review-20260513-231429.json` is now
`ready-for-read-only-proof` and selected source
`latest-riftreader-same-target-candidate-file`. It still explicitly sets
`movementAllowedByReview=false`.

A read-only proof-pose attempt at
`scripts/captures/riftscan-proof-pose-20260513-230600/` stayed blocked because
fresh RRAPICOORD reference capture was unavailable (`blocked-reference-unavailable`).
A later explicit candidate readback
`scripts/captures/riftscan-riftreader-currentpid-2928-readback-wrapper-summary-20260513-191349.json`
read all `3` candidates stably with `0` region failures and no input/CE, but
still had `ReferenceCoordinate=null` and `MovementAllowed=false`. The proof-anchor
preflight no longer reused the stale `telemetry-proof-coord-anchor.json`; it
reported:

- `proof_anchor_cache_pid_mismatch:anchor=57656;target=2928:ignored_stale_cache`
- `proof_anchor_cache_hwnd_mismatch:anchor=0x5417BC;target=0xC0994:ignored_stale_cache`

Remaining blocker: rebuild/promote a fresh same-target proof anchor from fresh
API-now/reference evidence before `ProofOnly` or movement can pass.

**May 13 23:19-23:27 UTC reference freshness recheck + root-signature packet:**
current target identity remains PID `2928` / HWND `0xC0994`, but both live
reference surfaces are currently blocked for proof promotion. Fresh RRAPICOORD
scan `scripts/captures/reference-currentpid-2928-manual-20260513-keepgoing/rift-api-reference-scan-currentpid-2928-20260513-231902.json`
found only partial/static `RRAPICOORD1` text and no usable
`status=pass|source=rift-api|savedVariablesUse=none` marker. ChromaLink
world-state capture
`scripts/captures/chromalink-world-state-reference-20260513-232015-658921/summary.json`
was reachable but blocked with stale `player.position` at
`2026-05-13T22:55:23.0397648+00:00`; endpoint freshness alone is not
coordinate freshness. Do **not** promote candidates or move from these stale
reference values.

Because proof promotion is blocked on fresh reference truth, the safe next work
pivoted to offline/static-chain prep. New helper
`scripts/parent_slot_root_signature_packet.py` generated
`scripts/captures/parent-slot-root-signature-packet-20260513-232733-606293/summary.json`
from existing parent-slot/container and owner-signature evidence. It packages
the current root-search predicate set: selected module hint
`0x268D75396C0 = rift_x64.exe+0x263E950` (`-0x40` from parent slot), parent
slot `0x268D7539700 -> 0x268D753AE30`, owner coord-pointer storage
`0x268D753AE40 -> 0x268DF21ED20`, owner module fields
`+0x0=0x26AAE70`, `+0x8=0x272DBC0`, `+0xE0=0x263E950`, and
`+0x110=0x2657C80`. The packet status is `passed` but
`candidateOnly=true` and `movementProofEligible=false`; it is a root-search
artifact only, not movement truth. Post-slice milestone review
`scripts/captures/riftscan-milestone-review-20260513-232903.json` remained
`ready-for-read-only-proof` with `movementAllowedByReview=false`; it does not
override the fresh-reference blocker.

**May 13 23:31-23:37 UTC grouped root-sweep follow-up:**
read-only grouped pointer sweep
`scripts/captures/pointer-family-scan-20260513-233157-559293/summary.json`
confirmed the current parent slot still has no parent-of-parent ref in the
scanned target set: `0x268D753AE30` is referenced once by `0x268D7539700`, and
`0x268DF21ED20` is referenced once by `0x268D753AE40`; no new module/static
parent was found.

New helper `scripts/root_signature_module_hint_sweep.py` then ran a broader
current-PID sweep of all live `rift_x64.exe+0x263E950` module-pointer
occurrences using the root-signature packet. Artifact:
`scripts/captures/root-signature-module-hint-sweep-20260513-233734-920187/summary.json`.
It scanned `575` module-pointer hits and ranked the known owner/parent-slot
relations highest: top owner-field candidate `0x268D753AF10 -> owner
0x268D753AE30 -> coord pointer 0x268DF21ED20`, and top parent-slot candidate
`0x268D75396C0 -> parent slot 0x268D7539700 -> owner 0x268D753AE30`. This is
useful broad-family confirmation but still candidate-only. The sweep also
exposed a stale/volatile signature field: expected owner field `+0x110` was
`0x2657C80` in older offline packet evidence, but live readback now shows
`0x264C688`. Treat `+0x110` as a weak/volatile clue until revalidated; do not
make it a hard root-search predicate. Post-sweep milestone review
`scripts/captures/riftscan-milestone-review-20260513-233744.json` remains
`ready-for-read-only-proof` with `movementAllowedByReview=false`.

**May 13 23:42-23:44 UTC root-family classification:** new offline
helper `scripts/root_signature_family_classifier.py` classified the `575`
module-hint sweep hits at
`scripts/captures/root-signature-family-classifier-20260513-234241-403707/summary.json`.
It found `5` owner-field families, `5` parent-slot families, `205`
owner-pointer region clusters, and `114` non-player parent-slot leads. The
known player chain remains the only high-confidence family: owner family
`matched=0x0,0x8,0xE0|coord=known` count `1`, parent-slot family
`offset=-0x40|ownerPointer=known` count `1`. The broad non-player family
`offset=-0x40|ownerPointer=heap-like` has `114` candidate leads but low score
(`15`) and no movement/proof eligibility.

Follow-up grouped pointer scan of the largest non-player heap-like cluster
`0x268E2A30000` wrote
`scripts/captures/pointer-family-scan-20260513-234327-662584/summary.json`.
It scanned `23` target/ref-storage addresses and found no module/static hits;
ASCII context includes UI/event/mail-style strings such as `Event.Buff.Add`,
`Event.Currency`, `Layout.Update`, and `Mail_Read_Auction`. De-prioritize this
cluster as likely UI/addon/event data unless later evidence links it to player
coordinate ownership. Latest milestone review
`scripts/captures/riftscan-milestone-review-20260513-234615.json` remains
`ready-for-read-only-proof` with `movementAllowedByReview=false`. Movement
remains blocked.

**May 13 23:50-23:56 UTC adaptive context triage + bounded priority scan:**
`root_signature_family_classifier.py` now annotates sweep hits with sanitized
ASCII/context kinds, writes reusable lead target exports, filters out obvious
UI/addon/asset/path/string-heavy leads for the priority lane, and demotes
tagged/unaligned heap-like values such as `0x26800000002`. Bounded classifier
artifact:
`scripts/captures/root-signature-family-classifier-20260513-235458-178863/summary.json`.
It still sees `575` module-pointer hits, but priority parent leads dropped to
`22` after excluding obvious non-entity contexts and tagged/unaligned pointers.
Reusable exports were written at
`scripts/captures/root-signature-family-classifier-20260513-235458-178863/priority-parent-lead-targets.json`
and `non-player-parent-lead-targets.json`.

A small priority follow-up pointer scan wrote
`scripts/captures/pointer-family-scan-20260513-235504-655292/summary.json`.
It scanned `23` target/ref-storage addresses from the top `8` priority leads,
found no module/static hits, and remained candidate-only. Top target
`0x2688C193360` had `2` heap hits; context included string/resource/UI-like
clues such as `Sanctuary`, `star_09.dds`, and `FRIENDS`. This does not reveal a
static root, but it confirms the triage/export path works and keeps follow-up
scans bounded instead of burning time on all `114` non-player leads. Milestone
review `scripts/captures/riftscan-milestone-review-20260513-235622.json` remains
`ready-for-read-only-proof` with `movementAllowedByReview=false`. Movement
remains blocked.

**May 14 00:02-00:04 UTC priority-offset context triage pass:**
`root_signature_family_classifier.py` now treats dotted UTF-16-like zone/game
labels such as `S.a.n.c.t.u.a.r.y` as `game-label-string` and marks them
`obviousNonEntity=true`, matching the existing UI/addon/asset/path/string-heavy
exclusions. Regenerated classifier artifact:
`scripts/captures/root-signature-family-classifier-20260514-000240-826658/summary.json`.
Counts stayed at `575` module-pointer hits, `6` owner families, `6` parent-slot
families, and `205` owner-pointer region clusters, but the clean priority lane
is now only `15` parent leads after demoting UI/addon/asset/path/string-heavy,
game-label, and tagged/unaligned pseudo-pointer noise. The `--priority-offset 8`
window exported the remaining `7` parent leads as `14` parent/owner targets at
`scripts/captures/root-signature-family-classifier-20260514-000240-826658/priority-parent-lead-targets.json`.

Read-only pointer scan
`scripts/captures/pointer-family-scan-20260514-000246-569593/summary.json`
scanned `24` queued target/ref-storage addresses from that remaining priority
batch with depth `1`. It found no module/static roots: top hits were heap-local
only, with `moduleHitCount=0` and `riftModuleHitCount=0` for the ranked targets.
Milestone review
`scripts/captures/riftscan-milestone-review-20260514-000430.json` remains
`ready-for-read-only-proof` with `movementAllowedByReview=false`. This pass
covered the offset-8 priority window; the next slice regenerated and scanned the
offset-0 window under the same improved rules before declaring the lane
exhausted. Movement remains blocked.

**May 14 00:09-00:14 UTC fresh-reference recheck + priority-lane exhaustion report:**
No-input ChromaLink world-state reference capture
`scripts/captures/chromalink-world-state-reference-20260514-000940-897289/summary.json`
was reachable but blocked: `world-state-not-healthy`,
`world-state-player-position-not-fresh`, `world-state-player-position-stale`,
and `world-state-navigation-player-position-unavailable`. It reported the last
player position at `2026-05-13T22:55:23.0397648+00:00` with newest frame age
about `4,457,665 ms`, so this is stale telemetry and not current proof.
RRAPICOORD marker scan via `capture-rift-api-reference-coordinate.ps1` also
blocked: attempts found `8`, `6`, and `13` `RRAPICOORD1` string hits, but no
usable marker with `status=pass`, `source=rift-api`, `savedVariablesUse=none`,
and numeric `x/y/z`; latest scan file:
`scripts/captures/rift-api-reference-scan-currentpid-2928-20260514-001004-attempt3.json`.

Because fresh reference stayed blocked, the safe local-PC work was to finish the
current clean priority lane accurately. Regenerated offset-0 classifier artifact
`scripts/captures/root-signature-family-classifier-20260514-001031-007727/summary.json`
exported `8` of `15` clean priority parent leads, and read-only pointer scan
`scripts/captures/pointer-family-scan-20260514-001038-968924/summary.json`
scanned `25` queued target/ref-storage addresses with `0` module/RIFT-module
hits. Combined with the offset-8 scan
`scripts/captures/pointer-family-scan-20260514-000246-569593/summary.json`, new
aggregate report
`scripts/captures/priority-scan-exhaustion-report-20260514-001700-212349/summary.json`
verdict is `priority-lane-exhausted-no-static-root`: `15` exported priority
leads, `49` scanned targets, `35` heap hits, `0` module hits, and `0`
RIFT-module hits. Latest milestone review
`scripts/captures/riftscan-milestone-review-20260514-001411.json` remains
`ready-for-read-only-proof` with `movementAllowedByReview=false`. Movement
remains blocked.

**May 14 00:20 UTC reference freshness watchdog:** new helper
`scripts/reference_freshness_watchdog.py` summarizes the latest ChromaLink and
RRAPICOORD reference artifacts without sending input, attaching a debugger,
reading target memory, or using SavedVariables as live truth. First artifact:
`scripts/captures/reference-freshness-watchdog-20260514-002036-448433/summary.json`.
Verdict is `blocked-fresh-reference-unavailable`. It reuses latest ChromaLink
summary `scripts/captures/chromalink-world-state-reference-20260514-000940-897289/summary.json`
with blockers `world-state-not-healthy`, `world-state-player-position-not-fresh`,
`world-state-player-position-stale`, and
`world-state-navigation-player-position-unavailable`; latest RRAPICOORD scan
`scripts/captures/rift-api-reference-scan-currentpid-2928-20260514-001004-attempt3.json`
has `13` string hits but `0` usable markers. Use this watchdog as the first gate
before future proof/readback/movement attempts so stale reference surfaces stop
the workflow early. Post-watchdog milestone review
`scripts/captures/riftscan-milestone-review-20260514-002147.json` remains
`ready-for-read-only-proof` with `movementAllowedByReview=false`; this is still
a strategy/read-only gate, not movement permission.

**May 14 00:26 UTC coordinate proof readiness gate:** new helper
`scripts/coordinate_proof_readiness_gate.py` composes the reference watchdog and
latest milestone review into one fail-closed proof gate. First artifact:
`scripts/captures/coordinate-proof-readiness-gate-20260514-002618-599647/summary.json`.
It correctly blocks with verdict `blocked-coordinate-proof-readiness`, sets
`readOnlyProofAllowed=false` and `movementAllowed=false`, and records blockers
from the reference watchdog: stale/not-healthy ChromaLink plus no usable
RRAPICOORD marker. This closes the ambiguity where the milestone review alone
can be `ready-for-read-only-proof` because a same-target candidate exists, while
fresh API/reference truth is still unavailable. Use this readiness gate before
any future proof/readback or movement step.

**May 13 21:53 UTC owner/type source-chain lead:** read-only pointer scan
`scripts/captures/pointer-family-scan-20260513-214606-072853/summary.json`
seeded the only heap owner plus module-pointer hints. The low-noise type marker
`rift_x64.exe+0x26AAE70` (`0x7FF71F43AE70`) had only `3` instance hits, and
`scripts/captures/owner-type-instance-inspector-20260513-215227-155967/summary.json`
proved exactly one of those instances owns the stable coord candidate:
owner base `0x268D753AE30` has `[+0x10] = 0x268DF21ED20`, with the read vec3
`7397.59228515625,866.78271484375,3023.4453125`. Other type-marker
instances had non-player/zero or different coord-like targets. Follow-up
pointer scan
`scripts/captures/pointer-family-scan-20260513-215245-916937/summary.json`
found exactly one heap ref to the owner base at `0x268D7539700`; owner-neighborhood
inspection
`scripts/captures/pointer-owner-neighborhood-inspector-20260513-215307-379484/summary.json`
confirmed `0x268D7539700 -> 0x268D753AE30` and repeated the direct
`0x268DF21ED20` candidate relation in the same heap region. This is a stronger
source-chain lead (`type marker -> owner base -> coord pointer`) but still not
a static root or movement proof.

**May 13 22:00 UTC owner parent-graph comparison:** sibling owner scan
`scripts/captures/pointer-family-scan-20260513-215713-171510/summary.json`
scanned all `3` low-noise `rift_x64.exe+0x26AAE70` type instances. Each owner
had exactly `1` heap parent ref and each parent ref had `0` parent refs:
`0x268923AF610 <- 0x268E2A78628`,
`0x268C6A10EA0 <- 0x268B0DD1168`, and player-candidate
`0x268D753AE30 <- 0x268D7539700`. New offline summarizer
`scripts/owner_type_parent_graph.py` generated
`scripts/captures/owner-type-parent-graph-20260513-215906-263575/summary.json`,
classifying `0x268D753AE30` as `candidate-owner-heap-terminal`. This improves
the source-chain map and confirms the current chain still stops in heap; no
module/static parent was found.

**May 13 22:03 UTC parent-slot neighborhood summary:** new offline/read-only
helper `scripts/parent_slot_neighborhood_summary.py` summarized the three
parent-slot neighborhood inspections at
`scripts/captures/parent-slot-neighborhood-summary-20260513-220334-136540/summary.json`.
All three slots still have exactly one exact owner reference. Two parent slots
carry owner-window module-pointer hints: player-candidate slot
`0x268D7539700 -> 0x268D753AE30` has `rift_x64.exe+0x263E950` at slot offset
`-0x40`, and sibling slot `0x268E2A78628 -> 0x268923AF610` has
`rift_x64.exe+0x2691A88` and `rift_x64.exe+0x2647AC0`; sibling slot
`0x268B0DD1168 -> 0x268C6A10EA0` is heap-only in the owner window. This is a
better source-chain map and gives the next static-owner clue set, but it does
not promote coordinate truth, does not prove a static root, and does not permit
movement.

**May 13 22:11 UTC parent-slot module-hint rank:** new offline helper
`scripts/parent_slot_module_hint_rank.py` ranked the module hints from the
parent-slot summary at
`scripts/captures/parent-slot-module-hint-rank-20260513-221249-080403/summary.json`.
It found `3` hints, `3` unique RVAs, and `1` player-candidate hint. The top
ranked static-owner clue is `rift_x64.exe+0x263E950` in player-candidate parent
slot `0x268D7539700`, at offset `-0x40` from the owner slot, score `180`.
Sibling hints ranked lower: `rift_x64.exe+0x2647AC0` at `-0x150` and
`rift_x64.exe+0x2691A88` at `-0x3A8`. This ranking is the next offline search
priority only; it is not static-chain proof and not movement permission.

**May 13 22:18 UTC module-hint occurrence packet:** new offline helper
`scripts/module_hint_occurrence_packet.py` scanned existing `scripts/captures`
summary artifacts for `0x263E950`, `0x2647AC0`, `0x2691A88`, and absolute
module address `0x7FF71F3CE950`. It wrote
`scripts/captures/module-hint-occurrence-packet-20260513-222030-779335/summary.json`.
The packet scanned `359` summary JSON files, selected `59` occurrences, and
ranked `0x263E950` far above the sibling hints: `57` occurrences, `6` artifacts,
`4` owners, `4` owner-window hits, and `2` near-owner hits, score `962`.
`0x2647AC0` and `0x2691A88` each had only `1` selected occurrence. This confirms
`0x263E950` is the next best static-owner search seed from existing artifacts,
but it remains an offline source-chain clue only.

**May 13 22:26 UTC module-hint graph packet:** new offline helper
`scripts/module_hint_graph_packet.py` converted the `0x263E950` occurrence,
parent-slot, owner-parent graph, and owner-instance evidence into an explicit
candidate chain graph at
`scripts/captures/module-hint-graph-packet-20260513-222832-918691/summary.json`.
The graph has `9` nodes and `10` edges and resolves this candidate path:
`rift_x64.exe+0x263E950 -> 0x268D75396C0` (`-0x40` from parent slot)
`-> parent slot 0x268D7539700 -> owner 0x268D753AE30 -> coord-pointer storage
0x268D753AE40 -> coord pointer 0x268DF21ED20`. It also records owner module
fields on `0x268D753AE30`: `+0x0 = rift_x64.exe+0x26AAE70`,
`+0x8 = rift_x64.exe+0x272DBC0`, `+0xE0 = rift_x64.exe+0x263E950`, and
`+0x110 = rift_x64.exe+0x2657C80`. This is the clearest current source-chain
map, but the static/module root above `0x268D7539700` is still unresolved and
movement remains blocked.

**May 13 22:32 UTC owner structural-signature packet:** new offline helper
`scripts/owner_structural_signature_packet.py` ranked all `3` low-noise type
instances by the combined owner signature at
`scripts/captures/owner-structural-signature-packet-20260513-223357-049150/summary.json`.
Only owner `0x268D753AE30` has the complete requested signature: module RVAs
`0x26AAE70`, `0x272DBC0`, `0x263E950`, and `0x2657C80`; `0x263E950` specifically
at owner offset `+0xE0`; coord pointer at `+0x10`; stable coord-candidate
pointer `0x268DF21ED20`; readable vec3; single parent ref; and parent-slot
module hint. It scored `270`. Siblings `0x268C6A10EA0` and `0x268923AF610`
matched only `0x26AAE70` and `0x272DBC0`, missed `0x263E950`/`0x2657C80`, and
were not stable coord candidates. This makes `0x268D753AE30` the best structural
owner candidate but still not a static/restart chain or movement truth.

**May 13 22:43 UTC parent-slot container rank:** new offline helper
`scripts/parent_slot_container_rank.py` ranked the three parent slots as
container/root-search seeds at
`scripts/captures/parent-slot-container-rank-20260513-224240-201501/summary.json`
and wrote a CSV companion for local review. Top slot is `0x268D7539700` with
score `285`: it points to exact owner `0x268D753AE30`, inherits owner structural
score `270`, has selected `0x263E950` at `-0x40`, has near-owner internal pointer
offsets `0x0`, `0x10`, `0x18`, `0x40`, `0x48`, `0x50`, `0x58`, `0x60`, and
keeps coord-pointer storage `0x268D753AE40 -> 0x268DF21ED20`. Sibling parent
slots ranked much lower: `0x268E2A78628` score `80`, `0x268B0DD1168` score
`73`. The root gap is now narrowed to finding a static/container owner above
`0x268D7539700`; this remains candidate-only.

**May 13 22:57 UTC milestone review:** `scripts/riftscan_milestone_review.py`
wrote `scripts/captures/riftscan-milestone-review-20260513-225757.json` and
`.md`. Verdict remains **blocked**: the current proof pointer now correctly
targets PID `2928` / HWND `0xC0994` as `blocked-target-drift`, but no selected
same-target RiftScan candidate/match file exists. This blocks movement, memory
readback promotion, and provider-derived coordinate truth.

Freshness note: PID/HWND/process-start/module matches are **targeting preflight
only**, not coordinate freshness proof. Promotion still requires fresh
API-now vs memory-now agreement. Latest recorded coordinate snapshot:
ChromaLink/RRAPI marker coordinate `X=7401.9897`, `Y=871.78`, `Z=3028.3899` from
`2026-05-13T19:47:09.7052356+00:00`; do not present this value as current-now
without a new API-now sample and matching memory-now readback. Latest candidate
readback is offset-corrected candidate evidence, not direct movement truth.

## May 13 PID 2928 post-freeze recovery status (not promoted)

| Fact | Current truth |
|---|---|
| Live target | `rift_x64` PID `2928`, HWND `0xC0994`, process start `2026-05-13T16:17:56.208370Z`, module base `0x7FF71CD90000` |
| Exact-target preflight | Passed with `responding=true`, `windowVisible=true`, and debugger process count `0`: initial exact check `scripts/captures/x64dbg-target-preflight-20260513-165343-990550/summary.json`; latest post-scan exact check `scripts/captures/x64dbg-target-preflight-20260513-174411-430727/summary.json`. |
| API/runtime coordinate | Fresh ChromaLink world-state references passed before/after the Top 20 batches: `scripts/captures/chromalink-world-state-reference-20260513-173130-422208/summary.json` and `scripts/captures/chromalink-world-state-reference-20260513-174411-565652/summary.json`. Latest current API sample in this lane is from post-attach-diagnostic candidate readback `scripts/captures/candidate-readback-currentpid-2928-20260513-194659-756235/fresh-reference-coordinate.json`: `X=7401.9897`, `Y=871.78`, `Z=3028.3899`, captured `2026-05-13T19:47:09.7052356Z`. |
| Earlier low-order grouped scans | Previous bounded scans still have no hits: `scripts/captures/family-scan-currentpid-2928-20260513-165436-907290/family-scan-summary.json` (`45s`, stride-4, `hitCount=0`); `scripts/captures/family-scan-currentpid-2928-20260513-170101-859202/family-scan-summary.json` (`90s`, stride-4, `hitCount=0`); `scripts/captures/family-scan-currentpid-2928-20260513-170252-761030/family-scan-summary.json` (`60s`, stride-1, `hitCount=0`). |
| Memory-region inventory | New read-only planner `scripts/current_pid_memory_region_inventory.py` generated `scripts/captures/memory-region-inventory-currentpid-2928-20260513-173130-344326/summary.json`; `15197` regions inventoried, `13623` readable committed regions, `2955.969` readable committed MiB, `20` scan-plan ranges. The inventory used VirtualQueryEx metadata only and read no target memory bytes. |
| Prior-first family snapshot sequence | New primary workflow helpers `scripts/current_pid_family_snapshot_sequence.py` and `scripts/family_snapshot_delta_analyzer.py` now put documented prior truth/candidate families first, then current-PID scan-plan ranges. Safe bounded run `scripts/captures/family-snapshot-sequence-currentpid-2928-20260513-183255-599472/summary.json` captured baseline/passive snapshots only (`64MiB` per pose cap, `104` segments each), sent no input, used no CE/x64dbg, and blocked correctly with `blocked-no-displaced-pose` because no displaced pose was captured. |
| Broad snapshot-delta candidate | Auto-displacement run `scripts/captures/family-snapshot-sequence-currentpid-2928-20260513-184450-797475/summary.json` used exact target PID/HWND and one bounded `w` WindowMessage displacement. It captured `3` poses, selected `20` ranges (`12` prior exact, `7` prior neighborhood, `1` current scan-plan), and offline delta analysis found `3` clean candidates in family `0x268DF200000`; best broad candidate `0x268DF21ED20`, tracking-error max abs `0.16851562499959982`, passive-noise overlap `0`. |
| Candidate readback after broad run | `scripts/captures/candidate-readback-currentpid-2928-20260513-184751-502648/candidate-readback-summary.json` read back the `3` broad-run candidates against fresh API coordinate `7400.46,871.78,3028.25`. All `3` were offset-corrected current-coordinate candidates; best `0x268DF21ED20` had direct max delta about `5.0022` but offset-corrected max delta `0.0857421874998181`. |
| Focused live-delta family re-snapshot | Focused prior run `scripts/captures/family-snapshot-sequence-currentpid-2928-20260513-184837-252853/summary.json` disabled default priors and targeted `live-delta-lead=0x268DF21ED20` plus its family neighborhood. Offline delta analysis again found `3` clean candidates in `0x268DF200000`; best focused candidate `0x268DF21ED30`, tracking-error max abs `0.0060742187497453415`, passive-noise overlap `0`. |
| Focused candidate readback | `scripts/captures/candidate-readback-currentpid-2928-20260513-184849-042270/candidate-readback-summary.json` read back focused candidates against fresh API coordinate `7401.9297,871.78,3028.3899`. All `3` were offset-corrected current-coordinate candidates. Best `0x268DF21ED30` had direct max delta about `5.00487`, offset-corrected max delta `0.0033371093750247383`, and offset spread max abs `0.0060742187497453415`. Follow-up post-attach-diagnostic readback `scripts/captures/candidate-readback-currentpid-2928-20260513-194659-756235/candidate-readback-summary.json` again passed all `3` candidates against fresh reference `7401.9897,871.78,3028.3899`; best `0x268DF21ED30` offset-corrected max delta `0.0037083984370838152`. Treat this as high-signal candidate-family evidence only, not direct/current movement truth. |
| x64dbg static-chain readiness / attach attempt | No-attach readiness packet `scripts/captures/x64dbg-no-attach-readiness-packet-20260513-191946-104673/summary.json` passed with `readinessStatus=ready-for-current-turn-approval`, fresh ChromaLink reference, planner `scripts/captures/x64dbg-coord-chain-plan-20260513-191947-707381/coord-chain-plan-summary.json`, and access template `scripts/captures/x64dbg-no-attach-readiness-packet-20260513-191946-104673/access-event-template/x64dbg-manual-access-events-template.json`. A bounded hardware-write access capture was then attempted against `0x268DF21ED30`, but `scripts/captures/x64dbg-live-access-capture-20260513-192154-488416/summary.json` failed before attach with `RuntimeError:Failed to attach to process`; no access event was captured. Immediate post-attempt preflight `scripts/captures/x64dbg-target-preflight-20260513-192213-789102/summary.json` passed and reported debugger process count `0`. Follow-up environment probe `scripts/captures/x64dbg-attach-environment-probe-20260513-193707-533343/summary.json` passed: x64dbg automate launched minimized without a debuggee, automation connected, the session terminated, install/plugin/libzmq checks passed, and target handle-access/elevation checks passed; only warning was `current-process-SeDebugPrivilege-not-enabled`. A second bounded minimized attach retry `scripts/captures/x64dbg-live-access-capture-20260513-193853-021766/summary.json` also failed before attach; no session started, detach was correctly skipped, and no stimulus/input was sent. Post-attempt preflight `scripts/captures/x64dbg-target-preflight-20260513-193906-401189/summary.json` passed with debugger process count `0`. Treat current-PID attach as blocked until a new attach tactic exists; do not loop more identical attach attempts. Watch window remains the 12-byte triplet at `0x268DF21ED30`; evidence remains candidate-only until access events are ingested and a module/static-owner chain is proven. |
| Historical x64dbg hit RVA stability | Read-only current-PID code check `scripts/captures/historical-x64dbg-hit-rva-check-20260513-194042-075604/summary.json` compared prior PID `60628` x64dbg hit code windows against current PID `2928` at the same module RVAs. Both 96-byte windows matched exactly: historical memory-breakpoint hit from `scripts/captures/x64dbg-live-access-capture-20260513-072035-091117/summary.json` at RVA `0x57C2A5` now reads at `0x7FF71D30C2A5`, and hit from `scripts/captures/x64dbg-live-access-capture-20260513-061404-684022/summary.json` at RVA `0x47D555` now reads at `0x7FF71D20D555`. Disassembly artifact `scripts/captures/historical-x64dbg-hit-rva-disasm-20260513-194417-078605/summary.md` shows the strongest stable lead at current hit RIP `0x7FF71D30C2B5`: `cmp qword ptr [rcx + 0x10], 0`, followed by `lea rbx, [rcx + 0x10]`. This gives stable code-provenance leads for offline static-chain work, but it is not a resolved pointer chain or movement truth. |
| Static lead packet | New offline helper `scripts/x64dbg_static_lead_packet.py` generated `scripts/captures/x64dbg-static-lead-packet-20260513-195348-651818/summary.json` and `static-lead-work-packet.json`. It combines candidate family `0x268DF200000`, latest readback, stable hit RVAs, and disassembly into a candidate-only work packet. Important alignment: candidate spacing `0x268DF21ED20 -> +0x10 -> 0x268DF21ED30` matches the stable code lead `cmp qword ptr [rcx + 0x10], 0`. Blockers remain `not-resolved-static-chain`, `no-current-pid-register-object-pointer`, `missing-module-rva-root-pointer`, `not-restart-validated`, and `proofonly-not-passed`. |
| Family neighborhood inspector | New read-only helper `scripts/current_pid_family_neighborhood_inspector.py` scanned a 24 KiB current-PID window around `0x268DF21E000`: `scripts/captures/current-pid-family-neighborhood-inspector-20260513-195638-785343/summary.json`. It read target memory only, sent no input, used no x64dbg/CE, and found exactly `3` offset-corrected hits: `0x268DF21ED20`, `0x268DF21ED30`, and `0x268DF21E6F0`. This strengthens the interpretation that the high-signal coordinate-copy cluster is narrow and page-local, but still does not prove a static root. |
| Pointer-family scan | Read-only pointer scan `scripts/captures/pointer-family-scan-20260513-195912-166777/summary.json` seeded `0x268DF21ED20`, `0x268DF21ED30`, `0x268DF21E6F0`, and family base `0x268DF200000` with depth `1`. Only `0x268DF21ED20` had a pointer hit: heap ref storage `0x268D753AE40` in region `0x268D7530000`. Recursive scan of `0x268D753AE40` found `0` refs and there were `0` module/RIFT-module hits, so this supports `0x268DF21ED20` as a plausible object/base candidate for the `[rcx + 0x10]` relationship but does **not** resolve a static root. |
| Top 20 stride-4 scan batch | New batch runner `scripts/current_pid_coordinate_scan_plan_batch.py` scanned all `20` planned ranges with stride-4 XYZ matching, tolerance `2.0`: `scripts/captures/coordinate-scan-plan-batch-currentpid-2928-20260513-173357-355969/summary.json`; `rangesCompleted=20`, `totalHits=0`, blocker `no_xyz_triplets_found_in_scan_plan_ranges`. |
| Top 20 stride-1 scan batch | The same Top 20 planned ranges were scanned again with stride-1 XYZ matching, tolerance `2.0`: `scripts/captures/coordinate-scan-plan-batch-currentpid-2928-20260513-173613-643790/summary.json`; `rangesCompleted=20`, `totalHits=0`, blocker `no_xyz_triplets_found_in_scan_plan_ranges`. |
| RiftScan milestone review | Earlier `scripts/captures/riftscan-milestone-review-20260513-174512.json` blocked on stale PID `57656` / HWND `0x5417BC`; latest `scripts/captures/riftscan-milestone-review-20260513-225757.json` now has target-pointer-match passing but still blocks because no selected same-target candidate exists for PID `2928`. |
| Current proof status | **Not promoted**. PID `2928` now has a high-signal current-PID candidate family (`0x268DF200000`) with repeated offset-corrected live readback (`0x268DF21ED30` best focused address), but still has no static/restart chain or same-target `ProofOnly` promotion. Direct candidate values are offset from API by about `5` units, so this is not direct coordinate truth. |
| x64dbg status | No successful current-PID attach. One minimized no-debuggee automation self-check passed and two bounded current-PID attach attempts failed before attach. If another x64dbg tactic is used, keep x64dbg/dependent windows minimized unless visibility is required and avoid repeating the same attach attempt without new evidence. |
| Evidence labels | Current target/API evidence is `responsive-candidate`; there is no `live-proof` chain. Any future debugger-paused scan must be labeled `frozen-snapshot`. |
| Latest report | Professional HTML summary: `docs/recovery/static-chain-pointer-reacquisition-summary-2026-05-13.html`. Newest markdown handoff: `docs/handoffs/2026-05-13-2026-coordinate-proof-readiness-gate.md`; prior handoff: `docs/handoffs/2026-05-13-2020-reference-watchdog.md`. |
| Safety boundary | No Cheat Engine; no memory writes/patches; no static pointer promotion; no movement/nav proof. Bounded exact-HWND input is allowed only for discovery snapshots in this approved chat lane and remains candidate evidence. x64dbg/watchpoints should wait until the focused candidate family needs static-chain provenance and must stay minimized unless visibility is required. |

## May 13 prior PID 60628 candidate status (candidate-only; not authoritative proof)

| Fact | Current truth |
|---|---|
| Live target | `rift_x64` PID `60628`, HWND `0xCE0FCE`, process start `2026-05-13T04:53:58.081190Z`, module base `0x7FF796B50000` |
| Current proof status | **Not promoted**. PID `60628` evidence is still candidate-only and does not update `current-proof-anchor-readback.json`. The latest fully validated proof anchor remains stale PID `57656` from May 12. |
| Latest responsive preflight | `scripts/captures/x64dbg-target-preflight-20260513-072034-846093/summary.json` passed for exact PID/HWND/start/module before the final x64dbg memory-access capture. |
| Current blocker | After `scripts/captures/x64dbg-live-access-capture-20260513-072035-091117/summary.json`, target preflights report `responding=false` with debugger process count `0`; latest blocker artifact `scripts/captures/x64dbg-target-preflight-20260513-072327-946499/summary.json`. WGC visual capture also timed out at `scripts/captures/post-x64dbg-nonresponsive-visual-20260513-032345-187/wgc-result.json`. Do **not** run movement, x64dbg, or watchpoint work while this is true. |
| Movement/input finding | C# SendInput `VirtualKey` `w` moved the character; C# `ScanCode` `w` did not provide a useful displacement in the earlier clean test. Confirmed displacements: `scripts/captures/csharp-sendinput-current-virtualkey-w-currentpid-60628-20260513-025312/measured-result.json` planar `0.4616189445850858`; `scripts/captures/csharp-sendinput-current-virtualkey-w-thirdpose-currentpid-60628-20260513-031727/measured-result.json` planar `0.37082363732641205`. |
| Ranking improvement | `scripts/rift_live_test/coordinate_family_rank.py` now scores displacement tracking error so stationary midpoint false positives are demoted and families with moving slots can rank correctly. |
| Run-directory collision fix | `scripts/scan_current_pid_coordinate_family.py` now stamps capture directories with microseconds (`%Y%m%d-%H%M%S-%f`) so rapid grouped family scans cannot overwrite same-second artifacts. |
| Three-pose ranking artifact | `scripts/captures/coordinate-family-rank-currentpid-60628-threepose-tracking-20260513-032001-311/coordinate-family-rankings.json`. |
| Best exact address candidate | `0x1FF08502BC8`; support `3`; displacement track max error `0.004333593749834108`; avg delta `0.003232356770846915`. Observed values: pose1 `[7406.1318359375, 871.7725830078125, 3028.77099609375]`, pose2 `[7406.58740234375, 871.7725830078125, 3028.8134765625]`, pose3 `[7407.099609375, 871.7734375, 3028.86181640625]`. Candidate-only heap address; not a pointer chain. |
| Best family-level candidate | `0x1FF94EC0000`; support `3`; displacement track max error `6.0937500165891834e-05`; avg delta `4.225260424088143e-05`; slot moved across poses (`0x1FF94EC8B80` -> `0x1FF94EC8DC0` -> `0x1FF94EC93D0`). Treat as a high-signal moving family, not an exact stable address. |
| Destination-page family | `0x1FF07570000` still supports `3` but uses moving/unaligned slots; latest third-pose unaligned destination artifact `scripts/captures/family-scan-currentpid-60628-20260513-071936-092676/family-scan-summary.json` best `0x1FF07574839`. Continue using grouped snapshots and `--scan-stride 1` for this family. |
| Demoted transient families | Earlier high-heap leads `0x1FF392C0000`, `0x1FF40660000`, and `0x1FF841D0000` only supported two poses after the third-pose targeted scans; their third-pose scan artifacts had no hits, so do not prioritize them above the 3-pose candidates. |
| x64dbg evidence on best exact candidate | `scripts/captures/x64dbg-live-access-capture-20260513-072035-091117/summary.json` hit memory access on `0x1FF08502BC8`; RIP `0x7FF7970CC2B5` (`rift_x64.exe+0x57C2B5`), instruction `cmp qword ptr ds:[rcx+0x10], 0x00`, with candidate at `rcx+0x2F8`. Nearby bytes/string context looked like UI/scene-object metadata, so this is candidate-only and not static player-coordinate truth. Detach succeeded. |
| Earlier x64dbg source-copy lead | `rdx=0x1FF6D600020`, coordinate offset `rdx+0x28`, and copy routine `rift_x64.exe+0x47D408` remain useful historical source-copy evidence for this PID, but still heap-local and not restart-stable. |
| Pointer-chain status | Latest broader pointer-family scan `scripts/captures/pointer-family-scan-20260513-070942-089639/summary.json` scanned `67` target/recursive refs. Total module hits `0`; total `rift_x64.exe` hits `0`. Heap refs exist for family bases and storage, but no static/restart-stable chain. |
| Non-promotion list | Do not promote `0x1FF08502BC8`, `0x1FF94EC0000`, `0x1FF94EC93D0`, `0x1FF07574839`, `0x1FF07575346`, `0x1FF6D600020`, `0x1FF65FADE88`, or older transient `0x1FF392*` / `0x1FF406*` / `0x1FF841*` leads. |
| Latest handoff | `docs/handoffs/2026-05-13-1231-compact-static-pointer-chain-resume.md`; supporting detailed blocker handoff `docs/handoffs/2026-05-13-0729-currentpid-60628-threepose-candidate-blocker.md`. |
| Safety boundary | No Cheat Engine; no memory writes/patches; no static pointer promotion; no movement/nav proof; no further x64dbg until target responsiveness is restored and exact-target preflight passes. Frozen/debugger-paused evidence must be labeled `frozen-snapshot`; only responsive API/runtime/current-memory evidence can be labeled `live-proof`. |

## Latest fully validated proof status (authoritative; stale for PID 60628)

| Fact | Current truth |
|---|---|
| Live target | `rift_x64` PID `57656`, HWND `0x5417BC` |
| Current proof status | Same-target `ProofOnly` passed; current proof pointer was updated. |
| Current proof anchor | Candidate `api-family-hit-000001` at `0xCC080EC30C`; proof anchor file `C:\RIFT MODDING\RiftReader\scripts\captures\telemetry-proof-coord-anchor.json`. |
| Latest ProofOnly | Status `passed-proof-only`; summary `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-57656-readback-summary-20260512-071051.json`; `movementSent=false`; `movementAttempted=false`. |
| Latest coordinate snapshot | `X=7407.42919921875`, `Y=871.8069458007812`, `Z=3030.127685546875` at `2026-05-12T11:10:56.4345281Z` |
| Stage 1 reacquisition | `C:\RIFT MODDING\RiftReader\scripts\captures\postupdate-proof-reacquire-stage1-python-20260512T103220Z\stage1-python-summary.json` |
| Promotion batch | `C:\RIFT MODDING\RiftReader\scripts\captures\postupdate-proof-reacquire-stage1-python-20260512T103220Z\coordinate-anchor-batch\coordinate-anchor-batch-summary.json` |
| Current proof pointer | `C:\RIFT MODDING\RiftReader\docs\recovery\current-proof-anchor-readback.json` |
| Archived stale pointer | `C:\RIFT MODDING\RiftReader\docs\recovery\historical\current-proof-anchor-readback-2026-05-12-pid30992-hwndD1008-historical.json` |
| Coordinate freshness rule | This proof is current for the exact PID/HWND above. Current-now coordinate use still requires fresh readback/API-now checks before movement or navigation. |
| Safety boundary | No Cheat Engine; no SavedVariables as live truth; route/yaw/actor-facing/auto-turn remain unpromoted after the maintenance return. |
| Remaining blocker | Post-maintenance coordinate proof is green, but route smoke, actor-facing, yaw, auto-turn, and navigation truth still need separate gated revalidation. |

## May 12 continuation: post-maintenance proof-anchor reacquisition passed

| Fact | Value |
|---|---|
| Scope | Post-maintenance current-PID coordinate proof-anchor reacquisition and same-target ProofOnly. |
| Target | `rift_x64` PID `57656`, HWND `0x5417BC` |
| Stage 1 result | `promotion-candidate-found`; bounded movement stimulus sent for coordinate evidence; visual gate passed; family scan passed. |
| Candidate | `api-family-hit-000001` |
| Anchor address | `0xCC080EC30C` |
| Promotion status | `validated` |
| Assert status | `valid`; movement gate `True` |
| ProofOnly status | `passed-proof-only`; `ok=True` |
| ProofOnly coordinate | `X=7407.42919921875`, `Y=871.8069458007812`, `Z=3030.127685546875` at `2026-05-12T11:10:56.4345281Z` |
| No-CE status | `noCheatEngine=true` |
| Non-promotion | This does not promote actor-facing, yaw, auto-turn, route execution, or navigation. |

## May 10 continuation: restarted-client proof-anchor reacquisition passed

| Fact | Value |
|---|---|
| Scope | Current-PID proof-anchor reacquisition after RIFT client restart; no automated movement/input, no `/reloadui`, no screenshot-key input, and no Cheat Engine. The user manually displaced the character between proof poses. |
| Target | `rift_x64` PID `30992`, HWND `0xD1008`. |
| Reacquisition path | Target-control and visual gate passed for the restarted client; the old PID `49504` proof pointer was rejected as target drift; a broad current-PID coordinate-family scan found current XYZ candidates; two no-CE displaced readback poses promoted `api-family-hit-000001`; fresh `ProofOnly` then passed and refreshed the tracked pointer. |
| Current candidate | `api-family-hit-000001` at `0x1E804B53C18`; source candidate file `C:\RIFT MODDING\RiftReader\scripts\captures\family-scan-currentpid-30992-20260510-082207\api-family-vec3-candidates.jsonl`. |
| Promotion proof | `C:\RIFT MODDING\RiftReader\scripts\captures\telemetry-proof-coord-anchor.json`; proof method `no-ce-riftscan-reference-multisample`; reference displacement `2.7734974400561336`; max delta error `0.005424609375040745`. |
| Latest ProofOnly | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260510-095259\run-summary.json`; status `passed-proof-only`; `movementSent=false`; `movementAttempted=false`; `currentProofPointerUpdate.updated=true`. |
| Latest readback | `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-30992-readback-summary-20260510-055339.json`; status `valid`; candidate `api-family-hit-000001`; address `0x1E804B53C18`. |
| Recorded coordinate | `X=7402.0341796875`, `Y=871.7628173828125`, `Z=3026.4580078125` at `2026-05-10T09:53:43.5120419Z`; do not present this as current-now unless a fresh API-now vs memory-now check passes. |
| Historical archive | Superseded PID `49504` / HWND `0x5121A` pointer archived to `C:\RIFT MODDING\RiftReader\docs\recovery\historical\current-proof-anchor-readback-2026-05-10-pid49504-hwnd5121A-historical.json`. |
| Non-promotion | This update does not promote actor-facing, yaw, auto-turn, or route execution truth. |
| Movement boundary | The proof anchor is current for PID `30992`, but there has been no post-restart automated movement/route smoke. Any movement still requires explicit fresh target-control, visual gate, proof preflight, and a bounded command. |

## May 9 continuation: post-handoff ProofOnly pointer refresh

| Fact | Value |
|---|---|
| Scope | Documentation truth update for the newer same-target `ProofOnly` / proof-anchor pointer refresh; no movement, yaw, turn, screenshot-key input, slash command, `/reloadui`, live capture, or Cheat Engine was run in this update. |
| Target | `rift_x64` PID `49504`, HWND `0x5121A`; target epoch remained the same as the prior visual-gate blocker handoff. |
| Newest pointer proof | `C:\RIFT MODDING\RiftReader\docs\recovery\current-proof-anchor-readback.json` now points at the 12:04Z same-target proof refresh. |
| Latest ProofOnly | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260509-120255\run-summary.json`; status `passed-proof-only`; `movementSent=false`; `movementAttempted=false`. |
| Latest readback | `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-49504-readback-summary-20260509-080414.json`; proof anchor remains `telemetry-proof-coord-anchor.json`; candidate remains `api-coord-hit-000005` at `0x24A01358880`. |
| Recorded coordinate | `X=7406.2783203125`, `Y=871.7720336914062`, `Z=3027.971923828125` at `2026-05-09T12:04:17.6493776Z`; do not present this as current-now unless a fresh API-now vs memory-now check passes. |
| Live-input boundary | Visual gate / live input remains blocked unless target-control, visual gate, and fresh `ProofOnly` pass again for the exact target. |
| Non-promotion | This update does not promote actor-facing, yaw, auto-turn, or route execution truth. |

## May 9 continuation: visual-gate focus confirmation hardened

| Fact | Value |
|---|---|
| Scope | No-input visual-gate focus safety hardening; no movement/yaw/turn/screenshot-key input sent. |
| Root cause found | The focus helper could return exit `0` while its returned window JSON still had `isForeground=false`, so the visual gate was treating a non-foreground window as focus-ok. |
| Code hardening | `scripts\rift_live_test\visual_gate_status.py` now requires the focus envelope to confirm `isForeground=true`; otherwise it emits blocker `focus-window-not-foreground` and keeps `readyForLiveInput=false`. |
| Fresh visual gate | `C:\RIFT MODDING\RiftReader\scripts\captures\visual-gate-currentpid-49504-20260509-010348\visual-gate-status.json`; `blocked-visual-baseline`; `readyForLiveInput=false`; `focusConfirmedForeground=false`; `movementSent=false`; `inputSent=false`. |
| Blockers | `focus-window-not-foreground`, `desktop-capture-access-denied`, `desktop-copyfromscreen-invalid-handle`, `capture-methods-return-black-or-flat-content`. |
| Validation | `python .\scripts\test_visual_gate_status.py` passed `9` tests; `python -m py_compile .\scripts\rift_live_test\visual_gate_status.py .\scripts\test_visual_gate_status.py` passed. |
| Strategy checkpoint | `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-milestone-review-20260509-0105-visual-gate-focus-hardened.json`; status `ready-for-read-only-proof`; review is not movement permission. |
| Remaining blocker | Restore foreground focus/capture, rerun full visual gate, then rerun fresh `ProofOnly` before any live input. |

## May 9 continuation: visual-gate blocker retry diagnostics hardened

| Fact | Value |
|---|---|
| Scope | No-input visual-gate retry plus offline diagnostics/reporting hardening; no movement/yaw/turn stimulus sent. |
| Fresh visual gate | `C:\RIFT MODDING\RiftReader\scripts\captures\visual-gate-currentpid-49504-20260509-005541\visual-gate-status.json`; `blocked-visual-baseline`; `readyForLiveInput=false`; `movementSent=false`; `inputSent=false`. |
| Failure classes | `desktop-capture-access-denied`, `desktop-copyfromscreen-invalid-handle`, `capture-methods-return-black-or-flat-content`. |
| Recovery recommendations | JSON/Markdown now recommend `restore-interactive-desktop-capture`, `restore-visible-window-content`, and `keep-live-input-blocked`. |
| Code hardening | `scripts\rift_live_test\visual_gate_status.py` now preserves multiple capture failure classifications instead of collapsing to a single blocker, and writes recovery recommendations. |
| Validation | `python .\scripts\test_visual_gate_status.py` passed `6` tests; `python -m py_compile .\scripts\rift_live_test\visual_gate_status.py .\scripts\test_visual_gate_status.py` passed. |
| Strategy checkpoint | `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-milestone-review-20260509-0057-visual-gate-blocker-hardened.json`; status `ready-for-read-only-proof`; review is not movement permission. |
| Remaining blocker | Restore capture access, rerun full visual gate, then rerun fresh `ProofOnly` before any live input. |

## May 9 continuation: actor-yaw proof-coordinate gate hardened; visual baseline blocked yaw stimulus

| Fact | Value |
|---|---|
| Scope | Isolated actor-facing/turn-backend prep; no route execution and no yaw/turn stimulus after the visual blocker. |
| No-input current actor-yaw status | `python .\scripts\actor_yaw_current_truth_status.py --json` still reports the promoted actor-yaw lead as session-bound to old PID `33912` / HWND `0xE0DB2`; it is not current for PID `49504`. |
| No-input current-PID readback | `C:\RIFT MODDING\RiftReader\scripts\captures\actor-yaw-readback-smoke-currentpid-49504-20260509-043414\run-summary.json` failed safely: both reader and capture orientation paths rejected the stale behavior-backed lead because it predates current process start. |
| Root cause found | Fresh actor-yaw candidate search initially reused stale ReaderBridge/bootstrap coordinates (`7389.3896484375,872.92999267578,3050.9899902344`) instead of the current post-ProofOnly proof coordinate (`7395.18603515625,876.5137939453125,3050.689453125`). |
| Code hardening | `--find-player-orientation-candidate` now prefers `telemetry-proof-coord-anchor.json` current memory coordinates when available for the requested process, and records a `Player coordinate override source` note in JSON. `scripts\test-actor-yaw-candidates.ps1` now prefers the proof anchor for player coord drift when exact PID/HWND is supplied. |
| Fresh candidate search after hardening | `C:\RIFT MODDING\RiftReader\scripts\captures\actor-yaw-currentpid-49504-20260509-0035\player-orientation-candidate-search-proofcoord.json`; `PlayerCoord=7395.18603515625,876.5137939453125,3050.689453125`, note `telemetry-proof-coord-anchor-current-memory`, best pointer-hop candidate `0x24A26F40DC0 @ 0xD4`. |
| Live input blocker | `find_game_window` resolved exact PID/HWND, but `capture_game_window` failed with `The handle is invalid`; `C:\RIFT MODDING\RiftReader\scripts\captures\visual-gate-currentpid-49504-20260509-004400\visual-gate-status.json` is `blocked-visual-baseline`, `readyForLiveInput=false`, `desktop-capture-access-denied`. |
| Strategy checkpoint | `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-milestone-review-20260509-0045-actor-yaw-proofcoord-gate.json`; status `ready-for-read-only-proof`; review is not movement permission. |
| Remaining blocker | Restore desktop/window capture, rerun visual gate and fresh `ProofOnly`, then run the bounded yaw candidate stimulus against the proof-coordinate candidate screen. |

## May 9 continuation: backend metadata live confirmation passed

| Fact | Value |
|---|---|
| Scope | Live no-turn observed-forward waypoint smoke to confirm real persisted navigation JSON includes first-class backend metadata. |
| Target | `rift_x64` PID `49504`, HWND `0x5121A`; bound/focused through `rift-window-control` before input. |
| Visual preflight | `C:\RIFT MODDING\RiftReader\scripts\captures\visual-gate-currentpid-49504-20260509-002611\visual-gate-status.json`; `passed-visual-baseline`, `readyForLiveInput=true`. |
| Pre-movement proof | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260509-042651\run-summary.json`; `passed-proof-only`, `movementSent=false`, coordinate `7393.87255859375,875.7035522460938,3050.758056640625`. |
| Route | `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-backend-metadata-live-currentpid-49504-20260509-0028\smoke-test-waypoints-2m-observed-forward.json`; generated from fresh `ProofOnly` plus current-session observed `ForwardSeries3x250` displacement, not actor-facing truth. |
| Pre-navigation read | `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-backend-metadata-live-currentpid-49504-20260509-0028\pre-navigation-read-current.json`; `AnchorSource=coord-trace-anchor`, initial planar `1.9999999999996247m`, `WithinArrivalRadius=false`. |
| Live waypoint result | `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-backend-metadata-live-currentpid-49504-20260509-0028\navigate-waypoints-run-summary.json`; `Status=success`, `MovementBackend=native-window-message`, `PulseCount=4`, `StopReason=arrived`, final planar `0.6847331308384343m` inside the `0.75m` arrival radius. |
| Visual change after input | Baseline `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260509-002832-404.png`; changed capture `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260509-002904-063.png`; `changePercent=62.0927`; final capture `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260509-002909-506.png`. |
| Post-movement proof | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260509-042916\run-summary.json`; `passed-proof-only`, coordinate `7395.18603515625,876.5137939453125,3050.689453125`, `movementSent=false`, pointer updated. |
| Strategy checkpoint | `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-milestone-review-20260509-0030-backend-metadata-live-confirmation.json`; status `ready-for-read-only-proof`; review is not movement permission. |
| Remaining blocker | Auto-turn remains blocked; actor-facing/turn-backend truth was not promoted in this slice. |

## May 9 continuation: navigation backend metadata recorded

| Fact | Value |
|---|---|
| Scope | Code-only metadata milestone; no live input was sent in this slice. |
| Implementation | `NavigationRunResult` and `NavigationRouteRunResult` now include `MovementBackend`; text formatters print it, and JSON summaries persist it. |
| Backend labels | Exact-HWND native backend reports `native-window-message`; PowerShell HWND fallback reports `powershell-window-message`; foreground/no-HWND fallback reports `powershell-sendinput-foreground`; pre-backend failures use `not-created`; legacy/defaults use `unknown`. |
| Route behavior | Route summaries propagate the first segment backend, so multi-segment artifacts show the actual movement surface used. Failures before backend creation remain explicit as `not-created`. |
| Validation | Targeted C# tests passed `26/26`; full reader test project passed `102/102`; `dotnet format .\RiftReader.slnx --verify-no-changes --no-restore` passed; milestone review `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-milestone-review-20260509-0018-backend-metadata.json` returned `ready-for-read-only-proof`. |
| Live truth boundary | Last live movement truth remains `C:\RIFT MODDING\RiftReader\scripts\captures\native-backend-smoke-currentpid-49504-20260509-0006\navigate-waypoints-run-summary.json`; rerun visual gate and fresh `ProofOnly` before any new input. |

## May 9 continuation: native exact-HWND backend live smoke passed

| Fact | Value |
|---|---|
| Scope | Live no-turn observed-forward waypoint smoke for the new native C# exact-HWND backend; no auto-turn, no CE, no SavedVariables live truth. |
| Target | `rift_x64` PID `49504`, HWND `0x5121A`; bound/focused through `rift-window-control` before input. |
| Visual preflight | `C:\RIFT MODDING\RiftReader\scripts\captures\visual-gate-currentpid-49504-20260508-235535\visual-gate-status.json`; `passed-visual-baseline`, `readyForLiveInput=true`. |
| Pre-movement proof | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260509-040515\run-summary.json`; `passed-proof-only`, `movementSent=false`, coordinate `7392.33203125,874.7553100585938,3050.837646484375`. |
| Route | `C:\RIFT MODDING\RiftReader\scripts\captures\native-backend-smoke-currentpid-49504-20260509-0006\smoke-test-waypoints-2m-observed-forward.json`; generated from fresh `ProofOnly` plus current-session observed `ForwardSeries3x250` displacement, not actor-facing truth. |
| Live waypoint result | `C:\RIFT MODDING\RiftReader\scripts\captures\native-backend-smoke-currentpid-49504-20260509-0006\navigate-waypoints-run-summary.json`; `Status=success`, `PulseCount=5`, `StopReason=arrived`, final planar `0.45741853055044995m` inside the `0.75m` arrival radius. |
| Native backend evidence | Navigation stderr reported `Using native exact-HWND window-message input for 0x5121A`; the command used the new `MovementBackendFactory` exact-HWND route. |
| Visual change after input | Baseline `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260509-000630-039.png`; changed capture `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260509-000704-904.png`; `changePercent=43.7149`; final capture `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260509-000711-522.png`. |
| Post-movement proof | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260509-040722\run-summary.json`; `passed-proof-only`, coordinate `7393.87255859375,875.7035522460938,3050.758056640625`, `movementSent=false`, pointer updated. |
| Strategy checkpoint | `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-milestone-review-20260509-0008-native-live-smoke.json`; status `ready-for-read-only-proof`; review is not movement permission. |
| Remaining blocker | Auto-turn remains blocked; actor-facing/turn-backend truth was not promoted in this slice. |

## May 8 continuation: native exact-HWND movement backend

| Fact | Value |
|---|---|
| Scope | Code-only local/native movement backend milestone; no live input was sent after this patch. |
| Implementation | `reader/RiftReader.Reader/Navigation/MovementBackend.cs` now adds `MovementBackendFactory` and `WindowMessageMovementBackend`. Exact-HWND targets use native C# window-message input; no-HWND targets keep the previous PowerShell fallback. |
| Native safety checks | The native backend parses the requested HWND, verifies `IsWindow`, checks owner PID with `GetWindowThreadProcessId`, verifies process name, resolves the focused child target through `GetGUIThreadInfo`, and fails closed on mismatch before posting input. |
| Key delivery | The native path mirrors the proven helper semantics with `VkKeyScanW`, `MapVirtualKeyW`, `WM_KEYDOWN`, `WM_KEYUP`, modifier down/up handling, and per-command hold timing. |
| Waypoint wiring | `reader/RiftReader.Reader/Program.cs` now creates movement backends through the factory for `--navigate-waypoints` and `--navigate-waypoint-route`; exact PID/HWND waypoint pulses no longer spawn `pwsh` for window-message input. |
| Validation | `dotnet test .\reader\RiftReader.Reader.Tests\RiftReader.Reader.Tests.csproj --no-restore` passed `102/102`; `dotnet format .\RiftReader.slnx --verify-no-changes --no-restore` passed; `git diff --check` passed with only CRLF warnings; milestone review `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-milestone-review-20260509-034200-native-window-message-backend-final.json` returned `ready-for-read-only-proof`. |
| Remaining live truth | Last live movement truth is still the 23:12 EDT durable-summary observed-forward waypoint run; rerun visual gate and fresh `ProofOnly` before any new live input. |
| Auto-turn | Still blocked; this backend milestone does not promote actor-facing truth or any turn backend. |

## May 8 continuation: durable navigation summary live pass

| Fact | Value |
|---|---|
| Visual gate before movement | `C:\RIFT MODDING\RiftReader\scripts\captures\visual-gate-currentpid-49504-20260508-231046\visual-gate-status.json`; status `passed-visual-baseline`; `readyForLiveInput=true`. |
| MCP baseline | `find_game_window` and `focus_game_window` bound the exact PID/HWND foreground; `capture_game_window` saved `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260508-231130-399.png`. |
| Pre-movement proof | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260509-031137\run-summary.json`; coordinate `7390.728515625,873.7625732421875,3050.921630859375`; `movementSent=false`. |
| Route | `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-summary-currentpid-49504-20260508-2312\smoke-test-waypoints-2m-observed-forward.json`; generated from pre-movement ProofOnly plus current-session ForwardSeries displacement. |
| Plan/read precheck | `plan-navigation-route.json` total planar distance `1.9999999999996247m`; `pre-navigation-read-current.json` reported `AnchorSource=coord-trace-anchor`, `WithinArrivalRadius=false`, initial planar `1.9999999999996247m`. |
| Live waypoint result | `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-summary-currentpid-49504-20260508-2312\navigate-waypoints-run-summary.json`; status `success`; `PulseCount=5`; `StopReason=arrived`; final planar `0.3942869934100385m` inside `0.75m` arrival radius. |
| Visual change after input | `wait_for_frame_change` from the baseline screenshot saved `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260508-231323-029.png`; `changePercent=34.2978`; final capture `capture-20260508-231327-998.png`. |
| Post-movement proof | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260509-031334\run-summary.json`; coordinate `7392.33203125,874.7553100585938,3050.837646484375`; `movementSent=false`; pointer updated. |
| Post-movement read | `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-summary-currentpid-49504-20260508-2312\post-navigation-read-current.json`; `WithinArrivalRadius=true`; planar distance `0.3942869934100385m`. |
| Strategy checkpoint | `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-milestone-review-20260509-031702.json`; status `ready-for-read-only-proof`; review is not movement permission. |

## May 8 continuation: transient visual-baseline gate blocker (resolved)

| Fact | Value |
|---|---|
| Current status | Historical/resolved blocker. The later visual gate at `C:\RIFT MODDING\RiftReader\scripts\captures\visual-gate-currentpid-49504-20260508-231046\visual-gate-status.json` passed. |
| Purpose | Determine whether it was safe to continue live testing after the successful observed-forward waypoint smoke. No game input was sent during the blocked diagnostic slice. |
| Target | `rift_x64` PID `49504`, HWND `0x5121A`; window still resolves as visible and not minimized, client rect `639x354`. |
| New reusable preflight | `python .\scripts\check_live_visual_gate.py --pid 49504 --hwnd 0x5121A --process-name rift_x64 --title-contains RIFT --full` |
| Latest visual gate summary | `C:\RIFT MODDING\RiftReader\scripts\captures\visual-gate-currentpid-49504-20260508-230651\visual-gate-status.json`; Markdown companion `visual-gate-status.md`. |
| Gate verdict | `blocked-visual-baseline`; `readyForLiveInput=false`; blocker `desktop-capture-access-denied`; `movementSent=false`; `inputSent=false`; `noCheatEngine=true`; `savedVariablesUsedAsLiveTruth=false`. |
| CopyFromScreen evidence | Desktop 1x1 and RIFT client sanity captures both failed with `Exception calling "CopyFromScreen" ... "The handle is invalid."`; Rift MCP `capture_game_window` fails the same way. |
| PrintWindow / WGC evidence | PrintWindow wrote a diagnostic sidecar but failed usable quality; WGC window and monitor captures completed mechanically but returned black/flat content; DXGI Desktop Duplication failed with `E_ACCESSDENIED / Access is denied`. |
| Blocker interpretation | This is not a coordinate-proof blocker and not a target-resolution blocker. The current Windows/session capture path is not producing a usable visual baseline, so live input is blocked by policy until the desktop/capture state is restored. |
| Operator recovery | Wake/unlock/reconnect the desktop or otherwise restore an interactive visible display, then rerun the visual gate before any fresh `ProofOnly` or movement run. |

## May 8 continuation: observed-forward 2m waypoint smoke passed

| Fact | Value |
|---|---|
| Route source | `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-smoke-currentpid-49504-20260508-2218-2m\smoke-test-waypoints-2m-fixed-bearing.json`; generated from latest ProofOnly current coordinate plus observed current-session `ForwardSeries3x250` displacement, not actor-facing truth. |
| Code fix before live run | `reader/RiftReader.Reader/Program.cs` now passes the resolved main window handle into waypoint navigation; `reader/RiftReader.Reader/Navigation/MovementBackend.cs` uses exact-HWND `-UseWindowMessage` and only falls back to `-RequireTargetForeground` when no HWND is available. |
| Route-builder helper | `python .\scripts\build_observed_forward_smoke_route.py --proof-summary <ProofOnly> --forward-series-summary <ForwardSeries3x250> --output-file <route>` builds a current-session route while rejecting low-signal or mismatched target evidence. |
| Durable navigation summaries | `--navigation-run-summary-file <path>` is now available on `--navigate-waypoints` and `--navigate-waypoint-route`; a no-input smoke wrote `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-smoke-currentpid-49504-20260508-2218-2m\navigation-run-summary-file-smoke.json` with `PulseCount=0`, `StopReason=start-mismatch`. |
| Pre-movement proof | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260509-023425\run-summary.json`; coordinate `X=7389.39111328125`, `Y=872.928466796875`, `Z=3050.994140625`; no movement. |
| Live waypoint result | `--navigate-waypoints` succeeded using exact-HWND window-message input; `PulseCount=4`, `StopReason=arrived`, initial planar distance `1.9999999999996247m`, final planar distance `0.6606430399933529m`, arrival radius `0.75m`. Transcript-derived summary: `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-smoke-currentpid-49504-20260508-2218-2m\navigate-waypoints-result-transcript.json`. |
| Post-movement proof | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260509-023644\run-summary.json`; coordinate `X=7390.728515625`, `Y=873.7625732421875`, `Z=3050.921630859375`; no movement. |
| Post-movement navigation read | After patching navigation reads to ignore default SavedVariables, `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-smoke-currentpid-49504-20260508-2218-2m\post-waypoint-read-navigation-current.json` reports `AnchorSource=coord-trace-anchor`, `WithinArrivalRadius=true`, and final planar distance `0.6606430399933529m`. |
| Visual evidence | Baseline `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260508-223415-608.png`; frame change `capture-20260508-223628-326.png` (`changePercent=51.0323`); final capture `capture-20260508-223634-616.png`. |
| Remaining blocker | `Facing.Status=fallback-candidate`; behavior-backed actor-facing lead is stale for PID `49504`, so auto-turn and actor-facing-driven route generation remain blocked. |
| Strategy checkpoint | `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-milestone-review-20260509-024109.json`; status `ready-for-read-only-proof`, movement permission still requires fresh proof immediately before any new movement. |

## May 8 continuation: ForwardSeries refresh-budget fix and live pass

| Fact | Value |
|---|---|
| Root cause fixed | `ForwardSeries3x250` needed more than one proof refresh because each proof/readback-gated pulse consumes much of the 60s proof-anchor budget. With `maxAutoRefreshAttempts=1`, pulse 3 blocked safely before input. |
| Config fix | `C:\RIFT MODDING\RiftReader\configs\live-test-profiles.json` sets `ForwardSeries3x250.maxAutoRefreshAttempts` to `3`. |
| Failed-safe evidence before fix | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ForwardSeries3x250-20260509-020234\run-summary.json`; status `partial-series-stopped`; completed `2/3`; issue `proof_anchor_remaining_age_budget_too_low:remainingSeconds=13.455;requiredSeconds=20`; pulse 3 sent no input. |
| Passed evidence after fix | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ForwardSeries3x250-20260509-020624\run-summary.json`; status `passed`; completed `3/3`; total planar movement `1.0194439320789634m`; auto-refresh attempts used `2/3`. |
| Validation | `python .\scripts\live_test.py --validate-profiles`; `python .\scripts\test_live_test_orchestrator.py` passed `75/75`; live run used exact PID/HWND, no CE, no SavedVariables live truth. |
| Visual checkpoint | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260508-221004-971.png` |
| Handoff | `C:\RIFT MODDING\RiftReader\docs\handoffs\2026-05-08-221056-forwardseries-refresh-budget-passed-handoff.md` |
| Remaining blocker | Auto-turn remains blocked by stale actor-facing truth for PID `49504`; observed-forward waypoint smoke is now green, but auto-turn/facing promotion still needs current-session behavior-backed proof. |

## Historical/mixed prior status snapshot

| Fact | Current truth |
|---|---|
| Live target | `rift_x64` PID `33912`, HWND `0xE0DB2` |
| Latest no-input proof | Post-native-smoke `ProofOnly` passed on PID `49504` / HWND `0x5121A`; run `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260509-040722\run-summary.json`; readback `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-49504-readback-summary-20260509-000753.json`; `movementSent=false`; `currentProofPointerUpdate.updated=true` |
| Latest current-session candidate | `rift-addon-coordinate-candidate-000001` at `0x202FEA3E180` from `C:\RIFT MODDING\Riftscan\reports\generated\currentpid-33912-reacquire-exact16m-20260508-042613-addon-coordinate-matches.json` |
| Latest actor-facing truth | **Promoted current-session behavior-backed lead**: `0x202CA5D23E0 @ +0xD4`; isolated survivor of the May 8 disambiguation run; post-promotion readbacks resolved via live memory; previous lead `0X202E570DB20 @ +0xD4` is preserved as `PreviousLead` because same-slice control validation was responsive-only/non-reversible. |
| Latest runtime progress | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260508-103043\run-progress.json`; status `passed-proof-only`; `movementSent=false` |
| Latest runtime pointer | `C:\RIFT MODDING\RiftReader\scripts\captures\latest-live-test-run.json` points to on-demand coord-anchor `ProofOnly` run `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260508-103043\run-summary.json` |
| Latest movement truth | Native exact-HWND C# backend no-turn `--navigate-waypoints` smoke passed at `C:\RIFT MODDING\RiftReader\scripts\captures\native-backend-smoke-currentpid-49504-20260509-0006\navigate-waypoints-run-summary.json` with `Status=success`, `PulseCount=5`, `StopReason=arrived`, final planar `0.45741853055044995m`; previous durable-summary run remains `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-summary-currentpid-49504-20260508-2312\navigate-waypoints-run-summary.json`. |
| Latest waypoint smoke | 2m `run-a-to-b-prototype` succeeded with route `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-smoke-currentpid-33912-20260508-0622-2m\smoke-test-waypoints-2m-fixed-bearing.json`; 4 pulses, stop reason `arrived`, distance `2.000000000000236m -> 0.6994920167255987m` |
| Current coordinate | On-demand coord-anchor `ProofOnly` coordinate `X=7436.64013671875`, `Y=885.2191772460938`, `Z=3055.749267578125` at `2026-05-08T10:31:43.1860758Z` |
| Latest proof anchor | Current PID `33912` movement gate was satisfied at latest on-demand `ProofOnly`; proof is age-gated, so re-bind exact target and run fresh preflight before later movement |
| Latest live validation | May 8 06:31 EDT: visible-HUD `ProofOnly` passed on current PID/HWND; coordinate `7436.64013671875,885.2191772460938,3055.749267578125`; `movementSent=false`; no CE and no SavedVariables live truth. Auto-turn remains blocked because no turn backend is promoted. |
| Latest offline validation | May 8 07:35 EDT: RiftScan coordination, feedback packet, milestone review, aggregate validation latest pointer, proof-pose pointer guard, promotion/import hardening regressions passed; no live input, no CE, and no RiftScan repo writes. |
| Latest actor-yaw discovery hardening | May 8 08:24 EDT: yaw candidate output now emits explicit `ValidationSummary`, stable `CandidateKey`, same-source multi-offset grouping, best-candidate summary, and `FacingPromotionAttempted=false`; `OrientationCandidateLedgerLoaderTests` cover ledger loading/penalties; `PlayerOrientationCandidateFinderLedgerTests` verify matching ledger penalties are applied to pointer-hop candidates, non-matching offsets are not penalized, and over-penalties clamp candidate score to zero; parser tests cover `--orientation-candidate-ledger-file` wiring and misuse rejection; `PlayerOrientationCandidateSearchJsonOutputTests` verifies `RawScore`, `LedgerPenalty`, ledger reason/counts, and ledger notes are visible in JSON output; `docs\player-actor-yaw-candidate-ledger.md` records the ledger evidence contract and recovery README links it; `scripts\summarize_actor_yaw_discovery.py` now emits an offline readiness gate that never authorizes movement or actor-facing promotion, changes status to `stale-artifacts-refresh-required` when session-bound input artifacts exceed the configured age budget, supports `--require-fresh` to exit nonzero when stale artifacts are present, and can persist a durable summary/Markdown/latest pointer while refusing output paths inside `C:\RIFT MODDING\Riftscan`; `scripts\summarize-actor-yaw-discovery.cmd` is a dumb pass-through launcher for the Python reporter; latest local checkpoint `scripts\captures\latest-actor-yaw-discovery-readiness.json` points to stale-artifact status and requires refresh before any promotion work; full C# test suite passed 92/92; shared actor-facing proof suite passes without forcing a new facing promotion. |
| Latest fresh actor-yaw truth gate | May 8 09:15 EDT: isolated disambiguation survivor `0x202CA5D23E0 @ +0xD4` was promoted to `scripts\actor-facing-behavior-backed-lead.json`; `read-player-orientation` and `capture-actor-orientation` resolved it live; `validate_current_actor_yaw_disambiguation.py`, actor-facing proof suite, and targeted C# tests passed; movement remains `false` pending a separate fresh movement gate. |
| Actor-yaw status command | `python C:\RIFT MODDING\RiftReader\scripts\actor_yaw_current_truth_status.py --json` reports `status=current`, lead `0x202CA5D23E0 @ +0xD4`, previous rejected control `0X202E570DB20 @ +0xD4`, and `movementAllowed=false`. |
| Actor-yaw readback smoke | May 8 09:39 EDT: `python C:\RIFT MODDING\RiftReader\scripts\actor_yaw_readback_smoke.py --pid 33912 --hwnd 0xE0DB2 --process-name rift_x64 --json` passed; latest pointer `C:\RIFT MODDING\RiftReader\scripts\captures\latest-actor-yaw-readback-smoke.json`; summary `C:\RIFT MODDING\RiftReader\scripts\captures\actor-yaw-readback-smoke-currentpid-33912-20260508-133911\run-summary.json`; both readback paths resolved `0x202CA5D23E0 @ +0xD4`; `movementSent=false`, no CE, no RiftScan writes, no SavedVariables live truth. |
| Interruption recovery surface | If a run is interrupted, inspect `scripts\captures\latest-live-test-run.json` then `runProgressFile`; for the latest navigation smoke inspect `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-smoke-currentpid-33912-20260508-0622-2m\a-to-b-prototype-2m-fixed-bearing.ndjson` |
| Python live-test orchestrator | Run-progress checkpoint validated; plan `C:\RIFT MODDING\RiftReader\docs\live-testing-python-orchestrator-plan.md`; turn-key profiler `C:\RIFT MODDING\RiftReader\scripts\profile_turn_keys.py` added and live-tested; offline hardening added `--proof-refresh-retries`; candidate ID now defaults from `docs\recovery\current-proof-anchor-readback.json` instead of stale profile config |
| RiftScan coordination checkpoint | `C:\RIFT MODDING\RiftReader\scripts\riftscan_coordination.py` creates a read-only coordination plan, selects the current proof-pointer candidate source, emits `-CandidateFile` command arrays, and refuses to write inside `C:\RIFT MODDING\Riftscan` |
| RiftScan feedback packet | `C:\RIFT MODDING\RiftReader\scripts\riftscan_feedback.py` emits a RiftReader-owned feedback packet for provider review without writing into RiftScan; latest smoke `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-feedback-packet-20260508-111607.json` status `ready-for-read-only-proof` |
| RiftScan milestone review | `C:\RIFT MODDING\RiftReader\scripts\riftscan_milestone_review.py` combines coordination + feedback into a strategy gate after major milestones; latest smoke `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-milestone-review-20260508-133712.json` status `ready-for-read-only-proof`, decision `proceed-read-only-proof-first`, `movementAllowedByReview=false`, `readOnlyProofAllowedByReview=true` |
| RiftScan validation runner | `C:\RIFT MODDING\RiftReader\scripts\validate_riftscan_coordination.py` reruns the no-CE/read-only coordination validation suite and checks RiftScan provider git status from one Python entry point; latest persisted summary `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-validation-20260508-113526.json`, latest pointer `C:\RIFT MODDING\RiftReader\scripts\captures\latest-riftscan-validation.json` |
| Auto-turn code gate | `C:\RIFT MODDING\RiftReader\scripts\navigation\run-a-to-b-prototype.ps1` now requires promoted backend evidence before pulsing an auto-turn key; current compact evidence has zero promoted candidates, so misaligned `-AutoTurnBeforeMove` fails closed before turn input |
| Turn backend promotion checklist | `C:\RIFT MODDING\RiftReader\docs\navigation-turn-backend-promotion.md`; documents the exact criteria needed before any future keyboard/message turn surface can feed navigation auto-turn |
| Compact turn-key evidence report | `C:\RIFT MODDING\RiftReader\docs\recovery\turn-key-profile-evidence.md` and `.json`; generated by `C:\RIFT MODDING\RiftReader\scripts\summarize_turn_key_profiles.py`; latest report shows zero promoted candidates across the newest 12 current-PID profile summaries, including retry-enabled `Right` and post-message `Left/Right` arrow runs |
| CE / SavedVariables | no CE; no SavedVariables live truth; `/reloadui` refresh was an intentional post-save snapshot before route generation |
| Latest tracked pointer | `C:\RIFT MODDING\RiftReader\docs\recovery\current-proof-anchor-readback.json` |
| Latest handoff | `C:\RIFT MODDING\RiftReader\docs\handoffs\2026-05-09-004500-actor-yaw-proofcoord-gate-handoff.md` |



## May 8 continuation: fresh player actor-yaw truth gate

| Fact | Value |
|---|---|
| Scope | Current-PID live yaw validation with exact window binding; no CE, no SavedVariables live truth, no RiftScan writes, and no movement/navigation promotion |
| Target | `rift_x64` PID `33912`, HWND `0xE0DB2`; `rift_game` binding/focus/capture confirmed the exact RIFT window before stimulus |
| Candidate search | `scripts\find-player-orientation-candidate.ps1 -ProcessId 33912 -MaxHits 16 -OrientationCandidateLedgerFile scripts\captures\actor-orientation-candidate-ledger.ndjson` refreshed `scripts\captures\player-orientation-candidate-search.json`; local candidate count `0`, pointer-hop candidate count `7`, best pointer-hop `0x202CA5D23E0 @ +0xD4` |
| Script fix | `scripts\find-player-orientation-candidate.ps1` no longer crashes while printing human-readable output when `BestCandidate` is absent but `BestPointerHopCandidate` exists |
| Yaw validation | `scripts\test-actor-yaw-candidates.ps1` used exact-HWND `PostMessage` `Right` then `Left`, 500ms holds, 3 post samples; output `scripts\captures\actor-yaw-candidate-test.json` |
| Fresh yaw truth-like candidate | `0x202CA5D23E0 @ +0xD4`, `CandidateKey=0x202CA5D23E0|0xD4`, `DiscoveryMode=second-hop-pointer-hop`, `TruthLike=true`, `Reversible=true`, `CandidateResponsive=true`, `PlayerStayedMostlyStill=true`, `PlayerCoordDeltaMagnitude=0.0` |
| Observed yaw response | `Right` peak yaw delta `+2.48997591133079°`; `Left` peak yaw delta `-7.447409137750857°`; one reversible cycle passed |
| Readiness gate | Initial single-cycle summary reached `yaw-ready-for-facing-proof-suite`, but the stronger repeat run exposed ambiguity; latest pointer status is now `yaw-ambiguous-needs-disambiguation`; summary `scripts\captures\actor-yaw-discovery-readiness-20260508-124900.json` |
| Downstream promotion | Completed for actor-facing only: `scripts\actor-facing-behavior-backed-lead.json` now points to `0x202CA5D23E0 @ +0xD4`; `movementAllowed=false` and auto-turn remains blocked. |
| Post-refresh validation | After promotion, `read-player-orientation-currentpid-33912-after-202ca5d23e0-promotion.json` and `capture-actor-orientation-currentpid-33912-after-202ca5d23e0-promotion.json` resolved `0x202CA5D23E0 @ +0xD4`; actor-facing proof suite passed; targeted C# filter passed 22/22. |
| Visual/input safety | Bound/focused exact window before live yaw stimulus; post-stimulus `wait_for_frame_change` observed `changed=true`, `changePercent=29.2697`; screenshots under `tools\rift-game-mcp\.runtime\screenshots` |
| Stronger repeat validation | `RepeatCount=2`, 4 samples per phase, exact-HWND `PostMessage Right/Left`; output `scripts\captures\actor-yaw-candidate-test.json`; result is useful evidence but **ambiguous**, not promotion truth. |
| Candidate-isolated disambiguation | `scripts\captures\actor-yaw-disambiguation-currentpid-33912-20260508-085406`; single truth-like survivor `0x202CA5D23E0 @ +0xD4`; controls `0x202CA5DC430`, `0x202CA5B6260`, and prior lead `0X202E570DB20` were responsive-only/non-reversible; tracked packet `docs\recovery\current-actor-yaw-disambiguation.json` now records promotion validation. |

## May 8 continuation: player actor-yaw discovery hardening

| Fact | Value |
|---|---|
| Scope | Offline yaw-first hardening; no CE, no live input, and no RiftScan repo modifications |
| Primary target | Player actor-yaw discovery evidence and candidate ranking, before any actor-facing promotion |
| Yaw wrapper hardening | `scripts\test-actor-yaw-candidates.ps1` now emits `ValidationFocus=player-actor-yaw-discovery`, stable per-result `CandidateKey`, explicit `FacingPromotionAttempted=false`, `BestCandidate`, same-source multi-offset grouping, and a top-level `ValidationSummary` |
| Regression fixture | `scripts\test-actor-yaw-candidates-reversible-output.ps1` now covers two same-source yaw offsets, candidate keys, same-source grouping, best-candidate output, and confirms the script does not promote actor-facing |
| Restart-check test isolation | `scripts\test-current-actor-yaw-restart-check-validator.ps1` now builds temporary coherent packet/lead fixtures instead of requiring the historical `docs\recovery\current-actor-yaw-restart-check.json` to match the newest live-session lead artifact |
| Validator behavior | `scripts\validate-current-actor-yaw-restart-check.ps1` was not changed; only its regression test was isolated from stale session-bound artifacts |
| Ledger coverage | `reader\RiftReader.Reader.Tests\Models\OrientationCandidateLedgerLoaderTests.cs` added tests for hex candidate-key normalization, missing ledger files, malformed NDJSON load errors, stable/nonresponsive penalties, idle-drift penalties, and responsive-later penalty clearing |
| Facing impact | Shared proof-suite stability improved, but no new actor-facing promotion was forced; actor-facing remains downstream of a behavior-backed yaw lead |
| Validation | `pwsh -File .\scripts\test-current-actor-yaw-restart-check-validator.ps1`; `pwsh -File .\scripts\test-actor-yaw-candidates-reversible-output.ps1`; `pwsh -File .\scripts\test-actor-facing-proof-suite.ps1`; `dotnet test .\RiftReader.slnx --configuration Debug --no-restore --filter "FullyQualifiedName~OrientationCandidateLedgerLoaderTests"` passed 7/7; targeted orientation/facing/navigation/parser C# filter passed 27/27; `python .\scripts\validate_riftscan_coordination.py --repo-root . --riftscan-root 'C:\RIFT MODDING\Riftscan' --pid 33912 --hwnd 0xE0DB2 --process-name rift_x64 --timeout-seconds 240 --compact-json` passed with `stepCount=19`, `failedStepCount=0`, `writesToRiftScan=false` |
| Remaining blocker | Auto-turn remains blocked; this pass improves yaw discovery evidence handling and proof-suite durability only |

## May 8 continuation: actor-yaw candidate-finder ledger gate hardening

| Fact | Value |
|---|---|
| Scope | Offline yaw-first C# test hardening; no CE, no live input, and no RiftScan repo modifications |
| Primary target | Ensure ledger evidence is not only parsed, but applied to actual pointer-hop yaw candidates before ranking |
| Candidate-finder coverage | `reader\RiftReader.Reader.Tests\Models\PlayerOrientationCandidateFinderLedgerTests.cs` verifies matching ledger evidence subtracts the score penalty and preserves ledger metadata, different basis offsets are not penalized, and penalties clamp at zero instead of producing negative scores |
| CLI coverage | `reader\RiftReader.Reader.Tests\Cli\ReaderOptionsParserTests.cs` now covers accepted `--find-player-orientation-candidate --orientation-candidate-ledger-file ...` wiring and rejects `--orientation-candidate-ledger-file` outside candidate-search mode |
| JSON output contract | `reader\RiftReader.Reader.Tests\Formatting\PlayerOrientationCandidateSearchJsonOutputTests.cs` verifies pointer-hop candidates expose `RawScore`, `Score`, `LedgerPenalty`, `LedgerRejectionReason`, ledger count/timestamp metadata, and notes describing penalized pointer-hop candidates |
| Docs contract | `docs\player-actor-yaw-candidate-ledger.md` defines candidate-key normalization, penalty semantics, JSON output fields, no-CE/no-movement/no-facing-promotion boundaries, and validation coverage; `docs\recovery\README.md` links it for future actor-yaw discovery work |
| Readiness report | `scripts\summarize_actor_yaw_discovery.py` summarizes candidate-search and yaw-validation artifacts into statuses such as `missing-evidence`, `candidate-search-only`, `yaw-responsive-needs-truth-like-proof`, and `yaw-ready-for-facing-proof-suite`; it always emits `movementAllowed=false`, `facingPromotionAllowed=false`, `noCheatEngine=true`, and `writesToRiftScan=false`; stale artifacts now fail closed to `stale-artifacts-refresh-required` while preserving the pre-freshness evidence status in `evidenceStatusBeforeFreshnessGate`; `--require-fresh` returns exit code `2` after printing/writing the report when `artifactFreshness.freshnessGatePassed=false`; `--write-summary --write-markdown --update-latest-pointer` creates a resumable checkpoint under `scripts\captures` and refuses paths under `C:\RIFT MODDING\Riftscan` |
| Facing impact | None forced; this is upstream actor-yaw discovery ranking hardening only |
| Validation | `dotnet test .\RiftReader.slnx --configuration Debug --no-restore --filter "FullyQualifiedName~PlayerOrientationCandidateSearchJsonOutputTests|FullyQualifiedName~PlayerOrientationCandidateFinderLedgerTests|FullyQualifiedName~OrientationCandidateLedgerLoaderTests|FullyQualifiedName~ReaderOptionsParserTests"` passed 29/29; broader targeted filter including orientation formatting, navigation, actor-facing lead validation, parser, yaw ledger tests, and yaw JSON-output contract passed 33/33; full `dotnet test .\RiftReader.slnx --configuration Debug --no-restore` passed 92/92; `pwsh -File .\scripts\test-actor-facing-proof-suite.ps1` passed; `python .\scripts\test_summarize_actor_yaw_discovery.py` passed 9/9; `python -m py_compile .\scripts\summarize_actor_yaw_discovery.py .\scripts\test_summarize_actor_yaw_discovery.py` passed |
| Remaining blocker | Auto-turn remains blocked; no new live yaw/facing truth was captured in this offline slice |

## May 8 continuation: read-only RiftScan coordination hardening

| Fact | Value |
|---|---|
| Scope | Offline RiftReader-only hardening; no CE, no live input, no RiftScan repo modifications |
| Boundary | `C:\RIFT MODDING\Riftscan` is a read-only provider/reference repo unless explicitly authorized in the current conversation |
| New checkpoint | `C:\RIFT MODDING\RiftReader\scripts\riftscan_coordination.py` plus `scripts\rift_live_test\riftscan_coordination.py` |
| Coordination output | Latest local smoke wrote `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-coordination-plan-20260508-105911.json` with `status=ok`, `writeAllowed=false`, and selected source `current-proof-pointer` |
| Feedback packet | Latest local smoke wrote `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-feedback-packet-20260508-111607.json` with `status=ready-for-read-only-proof`, `feedbackWritesToRiftScan=false`, and selected source `current-proof-pointer` |
| Milestone review | Latest local smoke wrote `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-milestone-review-20260508-112220.json` and `.md`; status `ready-for-read-only-proof`, strategy decision `proceed-read-only-proof-first`, `movementAllowedByReview=false` |
| Aggregate validation runner | `scripts\validate_riftscan_coordination.py` added as the one-command validation entry point for this no-CE/read-only RiftScan lane; latest persisted summary `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-validation-20260508-113526.json`, latest pointer `C:\RIFT MODDING\RiftReader\scripts\captures\latest-riftscan-validation.json`, Markdown `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-validation-20260508-113526.md`, status `passed`, `stepCount=19`, `failedStepCount=0`; dry-run emits the command list without sending input or writing RiftScan |
| Promotion fix | `scripts\promote-riftscan-reference-match-to-proof-anchor.ps1` now preserves configured `-MaxDeltaError`, enforces observed candidate/reference delta against that threshold, and checks summary process name plus HWND when an exact target HWND is available |
| Importer hardening | `scripts\import-riftscan-coordinate-candidates.ps1` preserves addon-match fields, ranks tied candidates with `support_count`, `observation_support_count`, and `best_max_abs_distance`, and fails closed for unsupported non-`xyz` axis order |
| Orchestrator hardening | `scripts\rift_live_test\runner.py` derives the promotion candidate ID from the current proof pointer by default; `configs\live-test-profiles.json` no longer points at the stale PID `47560` promotion reference summary |
| Proof-pose pointer guard | `scripts\capture-riftscan-proof-pose.ps1` can now resolve `CandidateFile` from the current proof pointer only after exact requested PID/process/HWND metadata matches; pointer mismatches fail closed before readback |
| Docs | `agents.md`, `docs\recovery\README.md`, and `docs\riftscan-riftreader-coordinate-candidate-workflow.md` now document the RiftScan read-only boundary, the coordination checkpoint, the feedback packet, the milestone review gate, the aggregate validation runner, and warn that `invoke-riftscan-coordinate-readback.ps1` without `-CandidateFile` can create RiftScan sessions/reports |
| Validation | `python .\scripts\test_live_test_orchestrator.py`; `python .\scripts\test_riftscan_coordination.py`; `python .\scripts\test_riftscan_feedback.py`; `python .\scripts\test_riftscan_milestone_review.py`; `python .\scripts\test_riftscan_validation.py`; `python .\scripts\validate_riftscan_coordination.py --pid 33912 --hwnd 0xE0DB2 --process-name rift_x64 --write-summary --write-markdown --update-latest-pointer`; `powershell -File .\scripts\test-capture-riftscan-proof-pose-success.ps1`; `powershell -File .\scripts\test-capture-riftscan-proof-pose-reference-blocker.ps1`; `powershell -File .\scripts\test-capture-riftscan-proof-pose-pointer.ps1`; `powershell -File .\scripts\test-import-riftscan-coordinate-candidates.ps1`; `powershell -File .\scripts\test-promote-riftscan-reference-match-to-proof-anchor.ps1`; `pwsh -File .\scripts\test-invoke-riftscan-coordinate-readback-decode.ps1` |
| Remaining blocker | Auto-turn remains blocked; this pass improves coordinate-candidate coordination and proof promotion safety only |

## May 8 continuation: on-demand coord anchor proof refreshed

| Fact | Value |
|---|---|
| Reason | User asked whether the coord anchor required a client restart; refreshed proof immediately to remove stale-age ambiguity |
| Target | `rift_x64` PID `33912`, HWND `0xE0DB2` |
| Proof run | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260508-102345\run-summary.json` |
| Readback | `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-33912-readback-summary-20260508-062445.json` |
| Status | `passed-proof-only` |
| Coordinate | `7436.64013671875,885.2191772460938,3055.749267578125` at `2026-05-08T10:24:54.3463325Z` |
| Movement | `movementSent=false`; `movementAttempted=false` |
| Safety | no CE; no SavedVariables live truth; exact PID/HWND |
| Restart needed | No restart needed for coord truth while PID `33912` / HWND `0xE0DB2` remains alive; only fresh proof/preflight is needed before movement |

## May 8 continuation: auto-turn now requires promoted backend evidence

| Fact | Value |
|---|---|
| Scope | Offline safety hardening; no live input sent |
| Guard | `run-a-to-b-prototype.ps1` added `-AutoTurnBackendEvidenceFile` and checks for a promoted candidate matching the selected key plus input mode before `Invoke-TurnKeyPulse` |
| Default evidence | `C:\RIFT MODDING\RiftReader\docs\recovery\turn-key-profile-evidence.json` |
| Current behavior | Because all current-PID profile summaries have `promotedCandidateCount=0`, any misaligned `-AutoTurnBeforeMove` route now fails closed before turn input |
| Future promotion path | After a real promoted profile exists, pass evidence containing `promotedCandidates` for the desired key/input mode before using auto-turn in the A/B navigation prototype |
| Report support | `C:\RIFT MODDING\RiftReader\scripts\summarize_turn_key_profiles.py` now preserves `promotedCandidates` in its JSON rows so compact evidence can support the guard once a candidate exists |
| Regression test | `C:\RIFT MODDING\RiftReader\scripts\navigation\test-run-a-to-b-proof-anchor-gate.ps1` now asserts the promoted-backend guard exists and runs before auto-turn key pulses |
| Promotion checklist | `C:\RIFT MODDING\RiftReader\docs\navigation-turn-backend-promotion.md`; requires exact PID/HWND, fresh proof, no CE, no SavedVariables live truth, known input delivery, same-sign yaw repeats, zero proof-coordinate movement, post-profile `ProofOnly`, and persisted `promotedCandidates` evidence |

## May 8 continuation: proof pointer restored; post-message arrows still no-turn

| Fact | Value |
|---|---|
| Target | `rift_x64` PID `33912`, HWND `0xE0DB2` |
| Proof-pointer root cause | A local docs update temporarily replaced `C:\RIFT MODDING\RiftReader\docs\recovery\current-proof-anchor-readback.json` with a raw proof readback summary, removing required `riftscanCandidateSource.matchFile`; `capture-riftscan-proof-pose.ps1` failed closed with `CandidateFile was not supplied ... does not contain riftscanCandidateSource.matchFile` |
| Safety impact | The first post-message arrow profile attempt `C:\RIFT MODDING\RiftReader\scripts\captures\turn-key-profile-currentpid-33912-20260508-085519\turn-key-profile-summary.json` sent **no input**; all attempts blocked on proof refresh before key delivery |
| Fix | Restored `current-proof-anchor-readback.json` as the current-proof pointer schema and added `C:\RIFT MODDING\RiftReader\scripts\test_current_proof_pointer.py` to guard the required `riftscanCandidateSource.matchFile` field |
| Proof after fix | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260508-090048\run-summary.json`; status `passed-proof-only`; `movementSent=false` |
| Baseline screenshot | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260508-050201-775.png` |
| Rerun command | `python .\scripts\profile_turn_keys.py --pid 33912 --hwnd 0xE0DB2 --process-name rift_x64 --keys Left Right --input-modes post-message --repeat 2 --hold-ms 250 --post-input-wait-ms 250 --live --refresh-proof-before-each-attempt --proof-refresh-retries 1` |
| Rerun summary | `C:\RIFT MODDING\RiftReader\scripts\captures\turn-key-profile-currentpid-33912-20260508-090211\turn-key-profile-summary.json`; status `completed-no-promoted-turn-candidate`; script exit `1` because no backend was promoted |
| Proof refresh behavior | All four per-attempt `ProofOnly` refreshes succeeded on try `1`; retry capacity was configured (`maxAttemptCount=2`) but no retry was needed |
| Input delivery | `Left` and `Right` both delivered twice with `effectiveMode=post-message`; no AutoHotkey fallback |
| Turn result | All four attempts had yaw delta `0.0` and proof-coordinate planar delta `0.0`; classifications `no-turn`, so exact-HWND post-message arrows remain not promoted |
| Visual verification | `wait_for_frame_change` after profile reported `changed=true`, `7.4368%`; comparison screenshot `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260508-050555-492.png`; final capture `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260508-050600-359.png` |
| Post-profile proof | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260508-090608\run-summary.json`; current coordinate `7436.64013671875,885.2191772460938,3055.749267578125`; `movementSent=false`; readback `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-33912-readback-summary-20260508-050631.json` |
| Safety | no CE; exact PID/HWND; proof refresh before each attempt; no SavedVariables live truth; no proof-coordinate movement |
| Next boundary | Auto-turn remains blocked. Do not run turn-then-forward navigation until a backend produces at least two same-sign yaw deltas with zero proof-coordinate movement. |

## May 8 continuation: retry-enabled Right turn profile still no-turn

| Fact | Value |
|---|---|
| Target | `rift_x64` PID `33912`, HWND `0xE0DB2` |
| Exact bind/focus | `find_game_window(processId=33912, windowHandle="0xE0DB2")` and `focus_game_window()` returned foreground target |
| Baseline screenshot | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260508-044910-768.png` |
| Profile command | `python .\scripts\profile_turn_keys.py --pid 33912 --hwnd 0xE0DB2 --process-name rift_x64 --keys Right --input-modes foreground-sendinput --repeat 2 --hold-ms 250 --post-input-wait-ms 250 --live --refresh-proof-before-each-attempt --proof-refresh-retries 1` |
| Profile summary | `C:\RIFT MODDING\RiftReader\scripts\captures\turn-key-profile-currentpid-33912-20260508-084929\turn-key-profile-summary.json`; status `completed-no-promoted-turn-candidate`; script exit `1` because no backend was promoted |
| Proof refresh behavior | Both attempts ran `ProofOnly` first and succeeded on try `1`; retry capacity was configured (`maxAttemptCount=2`) but no retry was needed |
| Input delivery | Both `Right` attempts delivered via true `foreground-sendinput`; `sendInputFailed=false`, `autoHotkeyFallbackUsed=false` |
| Turn result | Both attempts had yaw delta `0.0` and proof-coordinate planar delta `0.0`; classifications `no-turn`, so `Right` foreground SendInput remains not promoted |
| Visual verification | `wait_for_frame_change` after profile reported `changed=true`, `3.5674%`; comparison screenshot `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260508-045131-890.png`; final capture `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260508-045136-336.png` |
| Post-profile proof | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260508-085153\run-summary.json`; current coordinate `7436.64013671875,885.2191772460938,3055.749267578125`; `movementSent=false`; readback `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-33912-readback-summary-20260508-045227.json` |
| Safety | no CE; exact PID/HWND; proof refresh before each attempt; no SavedVariables live truth; no proof-coordinate movement |
| Next boundary | Auto-turn remains blocked. Do not run turn-then-forward navigation until a backend produces at least two same-sign yaw deltas with zero proof-coordinate movement. |

## May 8 continuation: turn-key profiler proof-refresh retry hardening

| Fact | Value |
|---|---|
| Scope | Offline code hardening only; no live RIFT input, no CE, and no SavedVariables live truth |
| Root cause addressed | A live arrow profile had one attempt blocked before input because the per-attempt `ProofOnly` refresh failed once; the profiler had no bounded retry option, so a transient proof-refresh miss could discard an otherwise safe attempt |
| New option | `python .\scripts\profile_turn_keys.py ... --refresh-proof-before-each-attempt --proof-refresh-retries 1` attempts one additional proof refresh after a failed refresh before blocking the key attempt |
| Also applies to | `--refresh-proof-first`; the same bounded retry wrapper is used before the profile and before individual attempts |
| Safety behavior | Input remains fail-closed: if all proof refresh attempts fail, the attempt is still marked `blocked-proof-refresh` / `proof-refresh-failed` and no key input is sent |
| Evidence emitted | The final `proofRefresh` payload now records `attemptCount`, `maxAttemptCount`, and concise `attemptResults` with each proof-refresh try label/status/run directory |
| Validation | `python -m py_compile scripts\rift_live_test\turn_keys.py scripts\profile_turn_keys.py scripts\test_turn_key_profile.py`; `python scripts\test_turn_key_profile.py` (9 tests); `python scripts\profile_turn_keys.py --help` shows `--proof-refresh-retries` |
| Current live truth impact | None; current live truth remains the latest post-q/e-profile `ProofOnly` at 08:37 UTC, and auto-turn remains blocked until a turn backend is promoted |

## May 8 continuation: Python turn-key profiler added; turn backend remains unpromoted

| Fact | Value |
|---|---|
| Target | `rift_x64` PID `33912`, HWND `0xE0DB2` |
| New runner | `C:\RIFT MODDING\RiftReader\scripts\profile_turn_keys.py`; Python owns the turn-key profiling workflow, while existing PowerShell scripts remain leaf adapters for orientation/readback/key delivery |
| Plan-only validation | `C:\RIFT MODDING\RiftReader\scripts\captures\turn-key-profile-currentpid-33912-20260508-072834\turn-key-profile-summary.json`; verified exact PID/HWND and sent no input |
| Multi-key live profile | `C:\RIFT MODDING\RiftReader\scripts\captures\turn-key-profile-currentpid-33912-20260508-072955\turn-key-profile-summary.json`; post-message `a` exited successfully but yaw delta was `0.0`; later planned key attempts failed closed before input when the 60-second proof gate expired |
| Single `d` candidate | `C:\RIFT MODDING\RiftReader\scripts\captures\turn-key-profile-currentpid-33912-20260508-073539\turn-key-profile-summary.json`; post-message `d` produced yaw delta `-8.38371711655384` with proof-coordinate delta `0.0`, but only one candidate is not promotable |
| Repeat `d` run | `C:\RIFT MODDING\RiftReader\scripts\captures\turn-key-profile-currentpid-33912-20260508-073726\turn-key-profile-summary.json`; two proof-refreshed post-message `d` repeats both had yaw delta `0.0` and proof-coordinate delta `0.0`, so no backend was promoted |
| Foreground `d` probe | `C:\RIFT MODDING\RiftReader\scripts\captures\turn-key-profile-currentpid-33912-20260508-074456\turn-key-profile-summary.json`; exact foreground target, `foreground-sendinput` mode fell back to AutoHotkey with input exit `0`, yaw delta `0.0`, proof-coordinate delta `0.0`, so foreground fallback `d` is also not promoted |
| Foreground arrow probe | `C:\RIFT MODDING\RiftReader\scripts\captures\turn-key-profile-currentpid-33912-20260508-075123\turn-key-profile-summary.json`; exact foreground target, `foreground-sendinput` mode fell back to AutoHotkey for `Left` and `Right` with input exit `0`, yaw delta `0.0` for both, proof-coordinate delta `0.0`, so arrows are also not promoted |
| Longer 500ms `d` probe | `C:\RIFT MODDING\RiftReader\scripts\captures\turn-key-profile-currentpid-33912-20260508-075910\turn-key-profile-summary.json`; foreground-sendinput mode fell back to AutoHotkey and no-turned twice, while post-message `d` produced `+10.232531344273667` then `-10.99219056890891` degree yaw deltas with proof-coordinate delta `0.0`; opposite signs mean no repeatable same-direction backend was promoted |
| SendInput struct fix | `scripts\post-rift-key.ps1` now declares the full INPUT union; validation showed `Marshal.SizeOf(INPUT)=40` instead of the previous 32-byte invalid parameter path that produced `LastWin32Error=87` |
| True SendInput `d` probes | `C:\RIFT MODDING\RiftReader\scripts\captures\turn-key-profile-currentpid-33912-20260508-081354\turn-key-profile-summary.json` and `C:\RIFT MODDING\RiftReader\scripts\captures\turn-key-profile-currentpid-33912-20260508-081531\turn-key-profile-summary.json`; `sendInputFailed=false`, `autoHotkeyFallbackUsed=false`, but yaw delta stayed `0.0` for 125ms and two 500ms `d` attempts with proof-coordinate delta `0.0` |
| True SendInput arrow probes | `C:\RIFT MODDING\RiftReader\scripts\captures\turn-key-profile-currentpid-33912-20260508-082051\turn-key-profile-summary.json`; Left no-turned twice, Right r1 blocked before input on proof-refresh reference capture, then Right r2 delivered without fallback and no-turned; completed attempts had proof-coordinate delta `0.0` |
| Keybind surface | No plaintext movement binding hits in AppData/Documents configs outside AddOns; binary `C:\Program Files (x86)\Glyph\Games\RIFT\Live\codex_keys.dat` begins with W/S/A/D entries paired with arrow alternates, followed by Q/E |
| True SendInput `q/e` probes | `C:\RIFT MODDING\RiftReader\scripts\captures\turn-key-profile-currentpid-33912-20260508-083210\turn-key-profile-summary.json`; `q` and `e` delivered without fallback for two 125ms attempts each, but all yaw deltas stayed `0.0` and proof-coordinate deltas stayed `0.0` |
| Latest proof | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260508-083654\run-summary.json`; current coordinate `7436.64013671875,885.2191772460938,3055.749267578125`; `movementSent=false` |
| Visual verification | `wait_for_frame_change` returned changed after post-fix SendInput profiles, including `3.6376%` after the true SendInput q/e profile; latest screenshots include `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260508-043637-695.png` and final capture `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260508-043643-390.png` |
| Safety | no CE; exact PID/HWND; no SavedVariables live truth; profiler detected no proof-coordinate movement during key attempts including arrows, longer `d`, post-fix true SendInput `d`, post-fix true SendInput arrows, and true SendInput `q/e`; no forward navigation was sent |
| Next boundary | Auto-turn remains blocked. Post-message and foreground SendInput `d`/`a`, foreground SendInput `Left`/`Right` arrows, longer 500ms `d` trials, post-fix true SendInput `d` trials, post-fix true SendInput arrow trials, and true SendInput `q/e` trials are not promoted; do not re-run auto-turn-to-forward until a backend is promoted by at least two same-sign yaw deltas with zero proof-coordinate movement. |

## May 8 continuation: offset-route auto-turn blocked on turn-input convergence

| Fact | Value |
|---|---|
| Target | `rift_x64` PID `33912`, HWND `0xE0DB2` |
| Offset route | `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-autoturn-currentpid-33912-20260508-0633-offset20\smoke-test-waypoints-autoturn-offset20.json`; destination was intentionally offset by `20` degrees from the current forward-key bearing |
| Proof-age blocker | `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-autoturn-currentpid-33912-20260508-0633-offset20\a-to-b-prototype-autoturn-offset20-retry.ndjson`; auto-turn improved once but then failed closed on `proof_anchor_age_out_of_range_seconds:65.587`; `Navigation calls=0` |
| No-convergence blocker | `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-autoturn-currentpid-33912-20260508-0633-offset20\a-to-b-prototype-autoturn-offset20-winps-shiftD75-postmessage.ndjson`; key helper reported success, but yaw stayed `-73.08494464580617` and delta stayed `13.651793251539019` degrees across 3 pulses; `Navigation calls=0` |
| Key/backend probes | Lowercase `d` post-message 250ms produced no yaw delta; uppercase/modified `D` and arrow-key probes produced inconsistent or stale/delayed yaw evidence, so no key/backend is promoted as reliable turn input yet |
| Code hardening from blocker | `scripts\navigation\run-a-to-b-prototype.ps1` now exposes `-AutoTurnUsePostMessage` for explicit exact-HWND post-message trials and adds a no-progress auto-turn guard (`AutoTurnMinImprovementDegrees`, `AutoTurnMaxNoImprovementPulses`) so non-converging turn pulses fail closed earlier |
| Post-attempt proof | `python .\scripts\live_test.py --profile ProofOnly --pid 33912 --hwnd 0xE0DB2 --no-gui`; summary `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260508-071016\run-summary.json`; readback `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-33912-readback-summary-20260508-031040.json`; `movementSent=false` |
| Safety | no CE; exact PID/HWND; no SavedVariables live truth; all auto-turn attempts failed before forward navigation |
| Next boundary | Treat auto-turn as blocked until the effective live turn key/backend is profiled and proven to change actor-facing reliably. Do not allow auto-turn to enter forward movement unless alignment is already within threshold after a fresh proof/preflight. |

## May 8 continuation: 2m fixed-bearing A/B waypoint smoke passed live

| Fact | Value |
|---|---|
| Target | `rift_x64` PID `33912`, HWND `0xE0DB2` |
| Pre-route proof | `python .\scripts\live_test.py --profile ProofOnly --pid 33912 --hwnd 0xE0DB2 --no-gui`; summary `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260508-062201\run-summary.json`; `movementSent=false` |
| Route generation | `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-smoke-currentpid-33912-20260508-0622-2m\smoke-test-waypoints-2m-fixed-bearing.json`; intentional `/reloadui` post-save refresh succeeded; route bearing `-79.60378349460011` degrees; distance `2.0m`; arrival radius `0.7m` |
| Pre-move proof | `python .\scripts\live_test.py --profile ProofOnly --pid 33912 --hwnd 0xE0DB2 --no-gui`; summary `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260508-062550\run-summary.json`; `movementSent=false` |
| Facing guard | Preflight distance `2.000m`; destination bearing `-79.604` degrees; forward-key movement bearing/yaw `-79.604` degrees; heading delta `0.000` degrees; source `0x202E570DB20 @ 0xD4` |
| Passing 2m A/B smoke | `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-smoke-currentpid-33912-20260508-0622-2m\a-to-b-prototype-2m-fixed-bearing.ndjson`; `Status=success`; `StopReason=arrived`; 4 pulses; distance `2.000000000000236m -> 0.6994920167255987m`; elapsed `10250ms` |
| Visual verification | `wait_for_frame_change` after the 2m smoke returned `changed=true`, `39.8806%`, screenshot `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260508-022731-069.png` |
| Post-navigation proof | `python .\scripts\live_test.py --profile ProofOnly --pid 33912 --hwnd 0xE0DB2 --no-gui`; summary `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260508-062740\run-summary.json`; current coordinate `7436.4345703125,885.2191772460938,3056.560546875`; `movementSent=false` |
| Route summary Markdown | `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-smoke-currentpid-33912-20260508-0622-2m\a-to-b-prototype-2m-fixed-bearing-summary.md` |
| Wrapper note | The navigation session log is authoritative and reports `success/arrived`. An outer ad hoc PowerShell pipeline wrapper threw after `Tee-Object` because `$LASTEXITCODE` was blank; this did not indicate navigation failure. |
| Safety | no CE; exact PID/HWND; fresh proof before movement; post-navigation ProofOnly passed; SavedVariables were refreshed only via intentional `/reloadui` as a post-save snapshot, not live IPC |
| Next boundary | Continue with fresh proof before each movement slice. Next live step should be deliberate auto-turn validation with an offset route, not blind longer forward pulses. |

## May 8 continuation: actor-facing promoted, movement bearing fixed, A/B waypoint smoke passed live

| Fact | Value |
|---|---|
| Target | `rift_x64` PID `33912`, HWND `0xE0DB2` |
| Actor-facing promotion | `scripts\actor-facing-behavior-backed-lead.json` promoted current PID source `0X202E570DB20` with basis forward offset `0XD4` |
| Promotion evidence | `C:\RIFT MODDING\RiftReader\scripts\captures\actor-facing-currentpid-33912-da-20260508-052500\session.json`; `LiveTruthStatus=confirmed`; `PromotionStatus=promoted`; D/A reversible yaw deltas `71.9515/71.4643` degrees; coord drift `0.0` |
| Default orientation readback | `C:\RIFT MODDING\RiftReader\scripts\captures\actor-facing-currentpid-33912-da-20260508-052500\capture-default-after-promotion.json` resolved through the tracked behavior-backed lead |
| Initial waypoint attempt | `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-smoke-currentpid-33912-20260508-051600\a-to-b-prototype-after-facing-promotion-correct-ids.ndjson`; failed safely after 2 pulses with `StopReason=no-progress`; distance increased `1.0000m -> 1.6381m` |
| Root cause | Live W movement proved the prior actor-facing-to-route bearing was 180 degrees opposite of actual forward-key movement. The route destination was generated in the opposite direction, so distance increased. |
| Code fix | `reader\RiftReader.Reader\Navigation\NavigationMath.cs` and `scripts\navigation\new-forward-smoke-route.ps1` now map the actor-facing basis projection to the opposite forward-key movement bearing; navigation tests were updated in `reader\RiftReader.Reader.Tests\Navigation\WaypointNavigationTests.cs` |
| Fixed route | `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-smoke-currentpid-33912-20260508-051600\smoke-test-waypoints-fixed-movement-bearing.json`; start `7435.94921875,885.2191772460938,3059.5537109375`; destination `7435.122945326888,885.2191772460938,3058.990441703244`; bearing `-145.71781003282072` degrees |
| Passing A/B smoke | `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-smoke-currentpid-33912-20260508-051600\a-to-b-prototype-fixed-movement-bearing.ndjson`; `Status=success`; `StopReason=arrived`; 1 pulse; final distance `0.6652750379001031m` within `0.7m` arrival radius |
| Post-navigation proof | `python scripts\live_test.py --profile ProofOnly --pid 33912 --hwnd 0xE0DB2 --no-gui`; summary `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260508-053953\run-summary.json`; current coordinate `7435.66650390625,885.2191772460938,3059.3740234375` |
| Visual verification | `wait_for_frame_change` after the fixed A/B smoke returned `changed=true`, `17.9565%`, screenshot `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260508-013920-428.png` |
| Safety | no CE; exact PID/HWND; fresh proof before movement; post-navigation ProofOnly passed; SavedVariables were only refreshed by `/reloadui` before route generation as a post-save snapshot |
| Next boundary | Continue with fresh proof before each movement slice. Next live step should be a slightly longer route or auto-turn validation, not blind repeated forward pulses. |
| Offline hardening after live proof | `WaypointNavigator` now fails closed when a pulse materially increases destination distance before the wider wrong-way tolerance is reached; route generation labels future bearings as `forward-key-movement-bearing`; the waypoint loader validates that bearing kind when present; route provenance extension metadata is preserved on future waypoint rewrites and TomTom imports; `summarize-a-to-b-log.ps1 -MarkdownFile` now emits compact route summaries; `docs\navigation-waypoint-v1.md` documents raw actor yaw vs forward-key movement bearing. |
| Latest route summary Markdown | `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-smoke-currentpid-33912-20260508-051600\a-to-b-prototype-fixed-movement-bearing-summary.md` |

## May 8 continuation: current PID ProofOnly and ForwardSeries3x250 passed live

| Fact | Value |
|---|---|
| Target | `rift_x64` PID `33912`, HWND `0xE0DB2` |
| Exact bind before proof | `find_game_window(processId=33912, windowHandle="0xE0DB2")` returned bound/foreground target |
| ProofOnly | `python scripts\live_test.py --profile ProofOnly --pid 33912 --hwnd 0xE0DB2 --no-gui`; status `passed-proof-only`; `movementSent=false` |
| Forward250 | `python scripts\live_test.py --profile Forward250 --pid 33912 --hwnd 0xE0DB2 --live --no-gui`; status `passed`; `movementSent=true`; planar delta `0.326128836893223m` |
| ForwardSeries3x250 | `python scripts\live_test.py --profile ForwardSeries3x250 --pid 33912 --hwnd 0xE0DB2 --live --no-gui`; status `passed`; completed `3/3` pulses; auto-refresh attempts used `1` |
| Series delta | `dX=0.20068359375`, `dY=0.0`, `dZ=-0.96044921875`, planar `0.9811914219956779m` |
| Final coordinate | `X=7436.48828125`, `Y=885.2191772460938`, `Z=3059.8955078125` at `2026-05-08T05:05:55.2929453Z` |
| Run summary | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ForwardSeries3x250-20260508-050351\run-summary.json` |
| Run progress | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ForwardSeries3x250-20260508-050351\run-progress.json` |
| Safety | no CE; no SavedVariables live truth; exact PID/HWND; `--live` required for input profiles |
| Next boundary | Further movement is allowed only after exact re-bind and fresh proof/preflight because the current proof remains age-gated |

## Earlier May 8: current PID candidate reacquired before movement proof passed

At this earlier checkpoint, the game window was back on `rift_x64` PID `33912`, HWND `0xE0DB2`. Forward
movement approval was recorded, but the live movement gate was still proof-gated.
No Codex-sent movement/input was sent in that reacquisition pass.

| Fact | Value |
|---|---|
| Current target | `rift_x64` PID `33912`, HWND `0xE0DB2` |
| RiftScan inventory | `C:\RIFT MODDING\Riftscan\reports\generated\currentpid-33912-inventory-20260508-042443.json` |
| RiftScan session | `C:\RIFT MODDING\Riftscan\sessions\currentpid-33912-reacquire-exact16m-20260508-042613` |
| RiftScan match file | `C:\RIFT MODDING\Riftscan\reports\generated\currentpid-33912-reacquire-exact16m-20260508-042613-addon-coordinate-matches.json` |
| Candidate | `rift-addon-coordinate-candidate-000001`, `0x202FE9F0000 + 0x4E180 = 0x202FEA3E180` |
| Candidate readback | `ReferenceMatchCount=1`, `StableDecodedCandidateCount=1`, `ReadbackTotalRegionReadFailures=0` |
| Baseline capture | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-RefreshBaseline-20260508-045224\run-summary.json`, status `passed-baseline-captured`; displaced about `3.023m` from prior blocked proof coordinate |
| Earlier ProofOnly run | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260508-044728\run-summary.json`, status `blocked-promotion-reference-mismatch`; superseded by later passing `ProofOnly` at `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260508-050153\run-summary.json` |
| Prior blocker | Resolved later by displaced baseline plus passing `ProofOnly`; movement-grade proof now comes from `Forward250` and `ForwardSeries3x250` on PID `33912` |
| Config hardening | `configs\live-test-profiles.json` now uses `scanContextBytes=16384`; `4096` missed the usable `RRAPICOORD1` context in this session |
| Next required action | Superseded; before further movement, re-bind exact target and run fresh proof/preflight, then use a small waypoint/navigation smoke rather than blind longer forward movement |
| Safety boundary | no CE; no SavedVariables live truth; input only after current proof promotion and exact-target preflight are green |

## May 7 continuation: interruption-safe progress checkpoint validated

The orchestrator now writes `run-progress.json` incrementally during a run and
updates `scripts\captures\latest-live-test-run.json` with both progress and
summary paths. This directly addresses interrupted live tests: if the final
summary is missing, the progress file still shows the latest state and any
series pulses already completed.

| Fact | Value |
|---|---|
| Validation command | `python scripts\live_test.py --profile ProofOnly --pid 47560 --hwnd 0x2122E` |
| Run summary | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260507-161726\run-summary.json` |
| Run progress | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260507-161726\run-progress.json` |
| Latest pointer | `C:\RIFT MODDING\RiftReader\scripts\captures\latest-live-test-run.json` |
| Status | `passed-proof-only` |
| Movement sent | `false` |
| Final summary written | `true` |



## May 7 continuation: dynamic promotion baseline pool validated

The orchestrator now records every fresh proof-pose summary into a Python-managed
promotion baseline pool and selects compatible same-target summaries with enough
reference displacement before proof promotion. This reduces dependence on a
single brittle PID/HWND-specific config baseline.

| Fact | Value |
|---|---|
| Baseline capture command | `python scripts\live_test.py --profile RefreshBaseline --pid 47560 --hwnd 0x2122E` |
| Baseline capture summary | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-RefreshBaseline-20260507-160159\run-summary.json` |
| Proof command | `python scripts\live_test.py --profile ProofOnly --pid 47560 --hwnd 0x2122E` |
| Proof summary | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260507-160239\run-summary.json` |
| Selection diagnostics | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260507-160239\promotion-baseline-selection-attempt-1.json` |
| Selection result | `selected`, compatible displaced count `2` |
| Pool file | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-promotion-baselines.json` |
| Safety boundary | no input, no CE, no SavedVariables live truth |



## May 7 continuation: Python-owned `ForwardSeries3x250` passed live

The `ForwardSeries3x250` profile now runs as a Python-owned per-pulse loop.
Each pulse uses a single-pulse wrapper dry-run and a single-pulse live wrapper
call. The run completed all three pulses and auto-refreshed proof once when the
third dry-run saw low proof-age budget.

| Fact | Value |
|---|---|
| Command | `python scripts\live_test.py --profile ForwardSeries3x250 --pid 47560 --hwnd 0x2122E --live` |
| Run summary | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ForwardSeries3x250-20260507-145404\run-summary.json` |
| Status | `passed` |
| Completed pulses | `3` / `3` |
| Auto-refresh | `1` proof refresh before pulse 3 retry |
| Final live wrapper summary | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ForwardSeries3x250-20260507-145404\gated-forward-smoke-currentpid-47560-summary-20260507-145544.json` |
| Final post-readback | `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-47560-readback-summary-20260507-105552.json`, `Status=valid`, `MovementAllowed=true` |
| Final coordinate | `X=7436.6025390625`, `Y=885.2205810546875`, `Z=3056.416259765625` at `2026-05-07T14:55:56.3626433Z` |
| Series delta | `dX=0.22412109375`, `dY=0.0`, `dZ=-0.9267578125`, planar `0.9534727619043354` |
| Safety boundary | no CE; no SavedVariables live truth; exact PID/HWND; `--live` required |



## May 7 continuation: Python live-testing orchestrator MVP passed live `Forward250`

The live-test workflow was moved from Codex step-by-step decisions into a
Python profile runner. The runner verified exact target, refreshed no-CE proof,
validated the promotion baseline, ran the wrapper dry-run, then sent one bounded
live input pulse and captured post-readback.

| Fact | Value |
|---|---|
| Command | `python scripts\live_test.py --profile Forward250 --pid 47560 --hwnd 0x2122E --live` |
| Run summary | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-Forward250-20260507-144303\run-summary.json` |
| Dry-run summary | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-Forward250-20260507-144303\gated-forward-smoke-currentpid-47560-summary-20260507-144320.json` |
| Live wrapper summary | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-Forward250-20260507-144303\gated-forward-smoke-currentpid-47560-summary-20260507-144325.json` |
| Input | exact-target `W`, `250 ms`, `PulseCount=1` |
| Post-readback | `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-47560-readback-summary-20260507-104333.json`, `Status=valid`, `MovementAllowed=true` |
| Post coordinate | `X=7436.35498046875`, `Y=885.2205810546875`, `Z=3057.44140625` at `2026-05-07T14:43:38.4287423Z` |
| Delta | `dX=0.04443359375`, `dY=0.0`, `dZ=-0.30126953125`, planar `0.30452861066430975` |
| Safety boundary | no CE; no SavedVariables live truth; `--live` now unconditional for input profiles |



## May 7 continuation: resumed handoff wrapper pulse passed

Resume started from `C:\RIFT MODDING\RiftReader\docs\handoffs\2026-05-07-072508-gated-wrapper-forward-smoke-handoff.md`. The target was still exact (`rift_x64` PID `47560`, HWND `0x2122E`). The first no-input wrapper dry-run correctly blocked on stale proof age, a later live wrapper attempt correctly blocked before input because only `14.560s` of proof-age budget remained for a `15s` guard, then a chained no-CE refresh -> wrapper `-DryRun` -> wrapper live pulse passed.

| Fact | Value |
|---|---|
| Successful refresh root | `C:\RIFT MODDING\RiftReader\scripts\captures\resume-proof-refresh-live-chain-20260507-134858` |
| Resume reference | `C:\RIFT MODDING\RiftReader\scripts\captures\resume-proof-refresh-live-chain-20260507-134858\resume-api-reference-wide-context.json` |
| Resume pose summary | `C:\RIFT MODDING\RiftReader\scripts\captures\resume-proof-refresh-live-chain-20260507-134858\riftscan-proof-resume-current-live-chain-20260507-134910\riftscan-riftreader-currentpid-47560-readback-wrapper-summary-20260507-094911.json` |
| Proof anchor generated | `2026-05-07T13:49:16.6085148+00:00` |
| Dry-run summary | `C:\RIFT MODDING\RiftReader\scripts\captures\gated-forward-smoke-currentpid-47560-summary-20260507-134917.json`, `Status=dry-run-valid` |
| Live wrapper summary | `C:\RIFT MODDING\RiftReader\scripts\captures\gated-forward-smoke-currentpid-47560-summary-20260507-134922.json`, `Status=passed` |
| Input | exact-target `W`, `250 ms`, wrapper-only, `MovementSent=true` |
| Post-readback | `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-47560-readback-summary-20260507-094931.json`, `Status=valid`, `MovementAllowed=true` |
| Post coordinate | `X=7437.97802734375`, `Y=885.2205810546875`, `Z=3049.539794921875` at `2026-05-07T13:49:35.6276265Z` |
| Delta | `dX=0.06201171875`, `dY=0.0`, `dZ=-0.3193359375`, planar `0.3253012361509452` |
| Fail-closed evidence | `C:\RIFT MODDING\RiftReader\scripts\captures\gated-forward-smoke-currentpid-47560-summary-20260507-134531.json` blocked before input with `proof_anchor_remaining_age_budget_too_low`; `MovementSent=false` |
| CE / SavedVariables | no CE path; no SavedVariables live truth |

Operational interpretation:

- The hardened age-budget guard is working: it blocked a too-late pulse before input.
- A fresh chained proof refresh left enough budget, and the wrapper pulse passed with post-readback still green.
- The proof is still session-bound and age-gated; refresh proof and run wrapper `-DryRun` before any future input.


## May 7 continuation: first gated-wrapper forward smoke passed after post-recovery

The wrapper path was tested live after a fresh no-CE proof refresh:

| Fact | Value |
|---|---|
| Pre-wrapper proof refresh reference | `C:\RIFT MODDING\RiftReader\scripts\captures\gated-wrapper-refresh-before-live-20260507-111447\current-api-reference-wide-context.json` |
| Pre-wrapper pose summary | `C:\RIFT MODDING\RiftReader\scripts\captures\gated-wrapper-refresh-before-live-20260507-111447\riftscan-proof-current-before-gated-wrapper-20260507-111520\riftscan-riftreader-currentpid-47560-readback-wrapper-summary-20260507-071521.json` |
| Pre-wrapper proof anchor generated | `2026-05-07T11:15:39.9032533+00:00` |
| Wrapper dry-run | `C:\RIFT MODDING\RiftReader\scripts\captures\gated-forward-smoke-currentpid-47560-summary-20260507-111556.json`, `Status=dry-run-valid` |
| Baseline screenshot | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260507-071621-832.png` |
| Wrapper live summary | `C:\RIFT MODDING\RiftReader\scripts\captures\gated-forward-smoke-currentpid-47560-summary-20260507-111630.json` |
| Input sent | exact-target `W`, `250 ms`, `post-rift-key.ps1 -RequireTargetForeground`; `SendInput` failed and AutoHotkey fallback reported success |
| Frame change | `true`, change percent `13.7569`; screenshot `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260507-071648-391.png` |
| Final screenshot | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260507-071653-129.png` |
| Wrapper postcheck status | `blocked-post-readback` only because the proof-anchor age was `61.302s`, just past the 60-second gate |
| Post-pulse recovery reference | `C:\RIFT MODDING\RiftReader\scripts\captures\gated-wrapper-post-pulse-recovery-20260507-111705\post-wrapper-api-reference-wide-context.json` |
| Post-pulse recovery pose | `C:\RIFT MODDING\RiftReader\scripts\captures\gated-wrapper-post-pulse-recovery-20260507-111705\riftscan-proof-post-gated-wrapper-pulse-20260507-111713\riftscan-riftreader-currentpid-47560-readback-wrapper-summary-20260507-071714.json` |
| Post-pulse proof anchor generated | `2026-05-07T11:17:32.0507730+00:00` |
| Post-pulse hard readback | `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-47560-readback-summary-20260507-071736.json`, `Status=valid`, `MovementAllowed=true` |
| Coordinate delta | `dX=0.06640625`, `dY=0.0`, `dZ=-0.3388671875`, planar `0.3453125552354311` |
| Wrapper hardening | `MinimumPostReadbackAgeBudgetSeconds` added so future runs block before input if not enough proof-age budget remains |

Operational interpretation:

- The first wrapper-mediated `W` pulse did move the proof coordinate and visual frame.
- The wrapper's original postcheck failed for timing, not coordinate/proof quality; the post-pulse no-input recovery proved the current coordinate again.
- The code is now safer than the run just performed: it refuses to send if the proof anchor is too close to age expiry for the postcheck.
- No Cheat Engine path and no SavedVariables live truth were used.

## Historical May 7 continuation: third repeat forward smoke passed

This continuation again failed closed first because the prior proof anchor had aged past the 60-second gate. A default 512-byte `RRAPICOORD1` scan had live API context but not the companion unit-detail `x/y/z` payload. A read-only unit-payload scan confirmed the live `Atank` payload was present, then a wider 4096-byte `RRAPICOORD1` context scan captured the companion payload through the helper fallback. The proof anchor was re-promoted, the hard gate passed, and only then was the third `W` pulse sent.

Refresh and pre-smoke artifacts:

- expired preflight summary: `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-47560-readback-summary-20260507-065223.json`
- failed default context scan: `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-proof-pose-current-refresh-before-third-smoke-20260507-105238\rift-api-reference-scan-currentpid-47560-20260507-105259-attempt3.json`
- unit-payload inspection scan: `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-proof-pose-current-refresh-before-third-smoke-20260507-105238\rift-api-unit-payload-scan-currentpid-47560-name-atank.json`
- fresh wide-context reference: `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-proof-pose-current-refresh-before-third-smoke-20260507-105238\pose-current-refresh-before-third-smoke-api-reference-wide-context.json`
- fresh wide-context scan: `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-proof-pose-current-refresh-before-third-smoke-20260507-105238\rift-api-reference-scan-currentpid-47560-20260507-105404.json`
- fresh recovered-reference pose summary: `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-proof-pose-current-third-smoke-reference-recovered-20260507-105424\riftscan-riftreader-currentpid-47560-readback-wrapper-summary-20260507-065425.json`
- refreshed proof anchor: `C:\RIFT MODDING\RiftReader\scripts\captures\telemetry-proof-coord-anchor.json`
- pre-smoke hard gate summary: `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-47560-readback-summary-20260507-065446.json`
- pre-smoke proof-anchor preflight file: `C:\RIFT MODDING\RiftReader\scripts\captures\assert-current-proof-coord-anchor-currentpid-47560-readback-preflight-20260507-065446.json`

Third forward smoke artifacts:

- baseline screenshot: `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260507-065509-596.png`
- frame-change screenshot: `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260507-065517-786.png`
- final screenshot: `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260507-065522-118.png`
- post-smoke hard gate summary: `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-47560-readback-summary-20260507-065532.json`
- post-smoke proof-anchor preflight file: `C:\RIFT MODDING\RiftReader\scripts\captures\assert-current-proof-coord-anchor-currentpid-47560-readback-preflight-20260507-065532.json`
- post-smoke watchset file: `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-47560-watchset-20260507-065532.json`
- post-smoke readback session: `C:\RIFT MODDING\RiftReader\scripts\sessions\proof-anchor-currentpid-47560-readback-20260507-065532`

Promotion facts:

| Fact | Value |
|---|---|
| Candidate | `rift-addon-coordinate-candidate-000001` |
| Candidate address | `0x2400EA32120` |
| Region address / offset | `0x2400EA320E0` / `64` |
| Pose count | `2` |
| Reference planar displacement | `3.8614090795978067` |
| Max candidate/reference delta error | `0.0028953125001862645` |
| Proof method | `no-ce-riftscan-reference-multisample` |
| Reference kind | `rift-api-unit-payload-companion` |
| No CE | `true` |
| Movement sent during promotion/preflight | `false` |

Third forward smoke proof facts:

| Fact | Value |
|---|---|
| Input | exact-target `W`, `250 ms`, `window-message` backend |
| Pre-smoke coordinate | `X=7437.787109375`, `Y=885.2205810546875`, `Z=3050.5166015625` at `2026-05-07T10:54:50.5192134Z` |
| Post-smoke coordinate | `X=7437.849609375`, `Y=885.2205810546875`, `Z=3050.197998046875` at `2026-05-07T10:55:36.6703454Z` |
| Delta | `dX=0.0625`, `dY=0.0`, `dZ=-0.318603515625` |
| Planar movement | `0.3246759155967834` |
| Three-pulse planar series movement | `0.9529119785083983` |
| Post-smoke status | `valid` |
| Post-smoke MovementAllowed | `true` |
| Post-smoke read failures | `0` |
| Stable across post-smoke samples | `true` |
| Frame change | `true`, change percent `8.7708` |

Operational interpretation:

- This is a **current-session, exact PID/HWND, no-CE** coordinate proof and three-pulse active forward-smoke proof.
- Three tiny active `W` pulses have now produced measurable proof-coordinate deltas and the proof anchor remained valid afterward.
- The companion-payload reference fallback is bounded to scans that also contain live Rift API probe context; it is not a SavedVariables path.
- The proof anchor is age-gated; before any further live input, rerun:

  ```powershell
  .\scripts\invoke-gated-forward-smoke.ps1 `
    -ProcessId 47560 `
    -TargetWindowHandle 0x2122E `
    -HoldMilliseconds 250 `
    -PulseCount 1 `
    -Json
  ```

- The gated wrapper performs the hard current-readback preflight before input
  and the hard current-readback postcheck after each pulse. Use `-DryRun` to run
  its no-input gate path only.

## May 7 continuation: gated wrapper added after live proof

After the third live smoke, the ad hoc exact-target key-posting flow was
captured as a narrow fail-closed wrapper:

| Item | Value |
|---|---|
| Wrapper | `C:\RIFT MODDING\RiftReader\scripts\invoke-gated-forward-smoke.ps1` |
| Regression | `C:\RIFT MODDING\RiftReader\scripts\test-invoke-gated-forward-smoke.ps1` |
| Default input | exactly one `W` pulse, `250 ms` |
| Safety caps | `HoldMilliseconds <= 1000`; `PulseCount <= 3` |
| Required target | exact `ProcessId` and `TargetWindowHandle` |
| Pre-input gate | `assert-current-proof-coord-anchor-readback.ps1` must return `Status=valid` and `MovementAllowed=true` |
| Post-input gate | same current-readback gate must remain green after each pulse |
| Age-budget gate | `MinimumPostReadbackAgeBudgetSeconds=15` by default; the wrapper blocks before input if the proof anchor is too close to expiry for a post-readback check |
| Default input backend | `post-rift-key.ps1 -RequireTargetForeground` |
| No-input mode | `-DryRun` |
| Live no-input dry run | `C:\RIFT MODDING\RiftReader\scripts\captures\gated-forward-smoke-currentpid-47560-summary-20260507-111124.json` |
| Dry-run result | `blocked-preflight`; `MovementAttempted=false`; `MovementSent=false`; issue `proof_anchor_age_out_of_range_seconds:1006.028` |
| Live input through wrapper | first run sent one `W` 250 ms pulse: `C:\RIFT MODDING\RiftReader\scripts\captures\gated-forward-smoke-currentpid-47560-summary-20260507-111630.json`; postcheck timed out on age, then post-recovery validation passed |
| CE / SavedVariables | no CE path; SavedVariables are not used as live truth |

## Historical May 6/7 RiftScan-first no-CE forward movement proof

The resumed lane now follows the user-corrected workflow: use RiftScan for candidate acquisition, then let RiftReader import/read back/promote only fresh candidates. The older `api-probe-triplet-000007` wording is superseded by the RiftScan candidate below.

1. Re-bound exact live target: PID `47560`, HWND `0x2122E`.
2. Seeded RiftScan with a same-session no-CE RiftReader readback coordinate, then captured the containing memory region read-only:
   - RiftScan session: `C:\RIFT MODDING\Riftscan\sessions\codex-current-coord-region-passive-20260506-230940`
   - RiftScan match file: `C:\RIFT MODDING\Riftscan\reports\generated\codex-current-coord-region-passive-20260506-230940-addon-coordinate-matches.json`
   - candidate: `rift-addon-coordinate-candidate-000001`
   - absolute address: `0x2400EA32120`
   - source base/offset: `0x2400E970000 + 0xC2120`
   - support: `3` snapshots; `best_max_abs_distance=0`
3. Imported the fresh RiftScan match into RiftReader and validated readback at pose A:
   - summary: `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-pivot-candidate-readback-20260506-231205\riftscan-riftreader-currentpid-47560-readback-wrapper-summary-ui-reference.json`
   - reference/readback max delta: `0.0365722656251819`
4. Captured pose B after a bounded `1000 ms W` pulse used for candidate proof displacement:
   - summary: `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-pivot-pose-b-readback-20260506-231548\riftscan-riftreader-currentpid-47560-readback-wrapper-summary-ui-reference.json`
   - reference/readback max delta: `0.021484375`
5. Promoted the fresh no-CE proof anchor from poses A/B and validated the default current-readback gate:
   - first promotion time: `2026-05-07T03:20:26.3697670Z`
   - validation summary: `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-47560-readback-summary-20260506-232031.json`
   - status: `valid`; movement gate: `satisfied_by_current_process_proof_anchor_current_readback`
6. Ran a proof-gated forward smoke (`1000 ms W`) after the valid preflight:
   - baseline screenshot: `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260506-232057-700.png`
   - changed screenshot: `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260506-232107-504.png`
   - final screenshot: `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260506-232110-751.png`
   - pre-readback: `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-47560-readback-summary-20260506-232031.json`
   - post-readback: `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-47560-readback-summary-20260506-232117.json`
   - coordinate delta: `dX=0.23681640625`, `dY=0`, `dZ=-1.21630859375`, planar `1.2391483387792066`
7. Captured pose C after the proof-gated pulse and re-promoted the anchor from poses B/C:
   - pose C reference: `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-pivot-pose-c-readback-20260506-232117\pose-c-ui-marker-reference.json`
   - pose C summary: `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-pivot-pose-c-readback-20260506-232117\riftscan-riftreader-currentpid-47560-readback-wrapper-summary-20260506-232223.json`
   - final proof anchor generated: `2026-05-07T03:22:38.8570044Z`
   - max reference planar displacement: `1.2165525060594347`
   - max candidate/reference delta error: `0.0368164062501819`
8. Verified the current proof-anchor readback gate again:
   - summary: `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-47560-readback-summary-20260506-232245.json`
   - status: `valid`; `MovementAllowed=true`; `ProofAnchorMaxAgeSeconds=60`
   - current coordinate: `X=7437.0498046875`, `Y=885.2205810546875`, `Z=3054.30517578125`

Operational interpretation:

- The latest recorded proof was movement-grade for the exact live PID/HWND during its proof-anchor age window.
- Do not reuse it after process restart, HWND change, or proof-anchor age expiry; rerun target discovery and preflight.
- The current proof source is a no-CE RiftScan/RiftReader validated candidate, not a CE coord-trace source.
- SavedVariables were not used as live truth.
- CE remains out of bounds unless explicitly reauthorized.

## Historical April 30 status snapshot

| Area | Status |
|---|---|
| Client executable | changed by the April 28, 2026 update; current `rift_x64.exe` SHA256 is `33B35F2DC17BD9AF1CC2186DF2B62ED5232D77630BDB3C00895FD84C464BF3EC`, size `59918272`, LastWrite `2026-04-28 14:05:32 -04:00` |
| Low-level reader | working against current live PID `32468` |
| ReaderBridge snapshot/export | available; export matched Atank at Sanctum Watch during April 30 recovery |
| Player current read | working for read-only context; current `SelectionSource=cached-anchor` / heuristic lineage remains exploration-only, not movement proof |
| Proof coord anchor cache | stale after Rift restart; post-restart proof-anchor rebuild failed and must be rerun/fixed before movement |
| Proof coord source | not proof-grade after restart; `read-player-current` matches ReaderBridge but is heuristic/cached-anchor only, latest read address `0x2C9ABD62850` |
| Proof polling watchset | stale after restart; no post-restart required `coord-trace-coords` watchset has been promoted |
| Source-chain/accessor-family coord recovery | historical for the pre-restart session; not re-promoted after PID `32468` restart |
| CE Lua server/bootstrap | available during this pass; `cheatengine-exec.ps1 -Code 'return 123'` returned `123` |
| Telemetry preflight | mixed after restart: memory-facing is valid from `0x2C9A013A490 @ +0xD4`, but memory coords are not proof-grade; effective position falls back to addon |
| Actor yaw / pitch truth | re-found after restart via source `0x2C9A013A490`; forward basis `+0xD4/+0xD8/+0xDC`; duplicate row not yet proven in this session |
| `--read-player-orientation` reader mode | live mode works when called with explicit `--pid 32468`; artifact-only/no-PID mode remains historical-only |
| Actor-facing provenance | April 30 post-restart exact PID/HWND D/A validation confirmed behavior-backed yaw on `0x2C9A013A490 @ +0xD4`; durable owner/source recovery remains unresolved |
| Navigation preflight (`--read-navigation-current`) | blocked for movement-grade proof after restart until coord anchor/watchset is rebuilt; facing source alone is available |
| Auto-turn preflight | historical for pre-restart session; not rerun after restart because coord proof is blocked |
| Active movement (`--navigate-waypoints`) | historical for pre-restart session; active movement is currently blocked until post-restart coord proof/watchset is green |
| Navigation v3 active route gate | implementation exists, but April 23 active movement proofs are historical after this update; live route-chain promotion remains pending |
| ReaderBridge orientation probe | still not treated as a usable direct yaw/pitch source |
| Camera yaw / pitch / distance on `main` | stale / unverified after the update |
| Authoritative camera controller | not yet isolated |

## April 30 post-restart yaw recheck

After the Rift client restart, the previous current actor-truth packet became
stale because PID `41220` no longer exists. The new live target is PID `32468`,
HWND `0x15908B2`, process start `2026-04-30T16:03:29.7977969Z`.

Current post-restart yaw/facing truth:

- source object: `0x2C9A013A490`
- forward basis: `+0xD4/+0xD8/+0xDC`
- yaw formula: `atan2(forwardZ, forwardX)`
- proof artifact:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\actor-yaw-recheck-after-restart-20260430-121848\manual-yaw-basis-confirmation-after-restart.json`
- compact restart packet:
  - `C:\RIFT MODDING\RiftReader\docs\recovery\current-actor-yaw-restart-check.json`

Behavior proof:

- exact target: PID `32468`, HWND `0x15908B2`
- `D` yaw delta: about `-128.309°`
- `A` yaw delta: about `+127.864°`
- coordinate drift during both turn checks: `0.0`

Operational interpretation:

- yaw/facing is current for this restarted session
- the previous `0x216F2F26020 @ +0x60/+0x94` lead is historical/stale after
  restart
- the coord-source-minus-`0x48` plus `+0x60/+0x94` pattern did not survive this
  restart as the yaw source
- movement-grade coord proof is still blocked: proof coord anchor reacquisition
  armed debug-register access watchpoints but received no verified hits against
  explicit current coord candidates
- bounded neighborhood recovery captured the current yaw object and coord-like
  candidates, but exact ReaderBridge-coordinate triplets remained in
  heuristic/current-candidate lineage only; see
  `C:\RIFT MODDING\RiftReader\docs\recovery\current-coord-proof-blocker.json`
- active movement must stay blocked until a post-restart `coord-trace-coords`
  watchset is rebuilt and validated
## April 30 actor-yaw recovery truth

April 30, 2026 live recovery supersedes conflicting April 28 session-bound
addresses below. The older April 28 sections are retained as historical proof
context.

Compact machine-readable truth packet:

- `C:\RIFT MODDING\RiftReader\docs\recovery\current-actor-truth.json`
- validation guard:
  - `C:\RIFT MODDING\RiftReader\scripts\validate-current-actor-truth.ps1`

Current live target:

- process: `rift_x64`
- PID: `41220`
- HWND: `0xBD0D94`
- character/location: `Atank` / `Sanctum Watch`

Current proof-grade coord source:

- source object: `0x216F2F26020`
- canonical coord triplet: `0x216F2F26068`
- source coord offset: `+0x48`
- proof-anchor refresh artifact:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\actor-facing-recovery-20260430-110229\proof-coord-anchor-refresh.json`
- post-active proof-anchor refresh artifact:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\actor-facing-recovery-20260430-110229\proof-coord-anchor-after-active-forward-smoke.json`
- proof polling watchset artifact:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\actor-facing-recovery-20260430-110229\proof-polling-watchset-after-yaw-promotion.json`
- post-active proof polling watchset artifact:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\actor-facing-recovery-20260430-110229\proof-polling-watchset-after-active-forward-smoke.json`
- current default watchset:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\proof-polling-watchset.json`
- required watchset region:
  - `coord-trace-coords` at `0x216F2F26068`, length `12`
- match: `CoordMatchesWithinTolerance=true`
- deltas vs ReaderBridge at refresh:
  - `DeltaX = -0.0043945312`
  - `DeltaY = -0.0009765625`
  - `DeltaZ = 0.0014648438`

Current behavior-backed actor-facing/yaw source:

- source object: `0x216F2F26020`
- primary forward basis: `+0x60/+0x64/+0x68`
- duplicate forward basis: `+0x94/+0x98/+0x9C`
- primary/duplicate agreement after promotion:
  - duplicate delta magnitude: `0.000003339988166361308`
  - duplicate agreement: `true`
- canonical formulas:
  - yaw = `atan2(forwardZ, forwardX)`
  - pitch = `atan2(forwardY, sqrt(forwardX^2 + forwardZ^2))`

Live exact-window D/A validation:

- validation artifact:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\actor-facing-recovery-20260430-110229\actor-yaw-candidate-test-da-ahk-700ms.json`
- candidate screen:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\actor-facing-recovery-20260430-110229\actor-yaw-validation-candidate-screen.json`
- input: exact target AutoHotkey `d` then `a`, `700 ms` holds
- foreground guard: target remained `0xBD0D94` / PID `41220`
- primary basis response:
  - forward yaw delta: about `-129.553°`
  - reverse yaw delta: about `+129.603°`
  - player coord drift: `0.0`
- duplicate basis response:
  - forward yaw delta: about `-129.554°`
  - reverse yaw delta: about `+129.604°`
  - player coord drift: `0.0`
- top pointer-hop candidates were nonresponsive except weak rank 9
  `0x216A250A590 @ +0xD4`, which moved only about `+3.650°/-2.916°`;
  it is not preferred over the owner/source coord object.

Promotion and validation after updating
`C:\RIFT MODDING\RiftReader\scripts\actor-facing-behavior-backed-lead.json`:

- `--read-player-orientation --pid 41220` resolved
  `0x216F2F26020 @ +0x60/+0x94`
- telemetry preflight is green:
  - memory coords valid: `true`
  - facing valid: `true`
  - effective position source: `memory`
  - effective facing source: `memory-facing`
- `--read-navigation-current` is green:
  - current address: `0x216F2F26068`
  - facing status: `available`
  - facing source: `behavior-backed-memory-facing`
  - facing source address: `0x216F2F26020`
  - facing forward basis offset: `0x60`
- turn-only auto-turn preflight is green:
  - script:
    - `C:\RIFT MODDING\RiftReader\scripts\navigation\run-a-to-b-prototype.ps1`
  - mode:
    - `-PreflightOnly -AutoTurnBeforeMove`
  - custom current-session waypoint file:
    - `C:\RIFT MODDING\RiftReader\scripts\captures\actor-facing-recovery-20260430-110229\autoturn-current-session-waypoints.json`
  - log:
    - `C:\RIFT MODDING\RiftReader\scripts\captures\actor-facing-recovery-20260430-110229\autoturn-preflight-only.ndjson`
  - start yaw/delta:
    - `1.450°` yaw, `42.135°` absolute delta, turn `right`
  - final yaw/delta:
    - `48.287°` yaw, `4.702°` absolute delta, turn hint `left`
  - pulses:
    - three exact-target `d` pulses at `75 ms`
  - movement:
    - no forward movement was sent; this was preflight-only
- smallest active forward smoke is green:
  - route file:
    - `C:\RIFT MODDING\RiftReader\scripts\captures\actor-facing-recovery-20260430-110229\active-forward-smoke-waypoints.json`
  - log:
    - `C:\RIFT MODDING\RiftReader\scripts\captures\actor-facing-recovery-20260430-110229\active-forward-smoke.ndjson`
  - stdout:
    - `C:\RIFT MODDING\RiftReader\scripts\captures\actor-facing-recovery-20260430-110229\active-forward-smoke.stdout.txt`
  - compact summary:
    - `C:\RIFT MODDING\RiftReader\scripts\navigation\summarize-a-to-b-log.ps1 -LogFile <active-forward-smoke.ndjson>`
    - emits `lastNavigationSummary` with status, stop reason, pulse count,
      distances, positions, and computed planar movement
  - command mode:
    - `--navigate-waypoints`
  - status:
    - `success`
  - stop reason:
    - `arrived`
  - anchor source:
    - `coord-trace-anchor`
  - preflight:
    - yaw `48.287°`, bearing `48.287°`, heading delta `0.000°`
  - movement input:
    - two `w` pulses
  - initial/final planar distance:
    - `2.600 -> 1.890`
  - initial position:
    - `X = 7260.58544921875`
    - `Y = 875.6790161132812`
    - `Z = 3052.92138671875`
  - final position:
    - `X = 7261.05712890625`
    - `Y = 875.696533203125`
    - `Z = 3053.451904296875`
  - planar movement:
    - about `0.710`
  - post-active telemetry after proof refresh:
    - memory coords valid: `true`
    - facing valid: `true`
    - effective position source: `memory`
    - effective facing source: `memory-facing`
  - post-active navigation read:
    - current address: `0x216F2F26068`
    - within arrival radius: `true`
    - facing source: `0x216F2F26020 @ +0x60`
    - yaw/bearing delta: about `0.027°`

Operational interpretation:

- `0x216F2F26020 @ +0x60/+0x94` is the current live behavior-backed
  actor-facing/yaw truth for this PID/HWND.
- The old behavior-backed lead `0x216FE3C6280 @ +0xD4` is stale/unreadable in
  this live session and must not be used unless separately re-proven.
- These addresses are still session-bound; after restart/client update,
  refresh proof coord readiness and rerun short exact-target yaw validation
  before treating them as current.
- Durable owner/source recovery is still unresolved.

## Historical April 28 proof coord anchor truth

_Historical: this section is retained as proof context only. April 30, 2026
re-promoted current coord truth to `0x216F2F26068` on source object
`0x216F2F26020`; use the April 30 section above for current live-session
addresses._

April 28 live validation established the then-current proof-grade movement
coord source:

- live process: `rift_x64` PID `41220`
- target window: `0xBD0D94`
- canonical live coord region: `0x216F87CDE18`
- canonical live coord-trace object base: `0x216F87CDE18`
- current trace-linked source object: `0x216F87CDDD0`
- source-object coord offset: `+0x48`
- verification method: `coord-triplet-access`
- match source: `readerbridge-live`
- sample memory coords after final active-proof ReaderBridge refresh:
  - `X = 7449.1753`
  - `Y = 863.58527`
  - `Z = 2973.069`
- ReaderBridge deltas at validation:
  - `DeltaX = -0.0043945312`
  - `DeltaY = -0.004699707`
  - `DeltaZ = -0.00073242193`
- current proof cache file:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\telemetry-proof-coord-anchor.json`

Operational interpretation:

- this validated coord-trace anchor remains the **only** proof-grade movement
  source
- `read-player-current.ps1`, heuristic current-player anchors, and cached
  current-player snapshots remain read-only/exploration aids only
- if a proof watchset does not include this validated coord-trace coord region,
  treat it as a blocker instead of silently accepting a stale/candidate source
- current proof watchset file:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\proof-polling-watchset.json`
- the current proof watchset contains required region `coord-trace-coords` at
  `0x216F87CDE18`, length `12`
- active route movement was **not** rerun in this April 28 pass; use the fresh
  proof anchor again immediately before any movement-polling proof

## Historical April 28 source-chain / accessor-family coord evidence

_Historical: retained for recovery pattern/provenance context. Do not treat the
April 28 object addresses below as current unless separately re-proven._

The April 28 current-session source-chain capture rebuilt the coord
source-chain on PID `41220`:

- selected/source object: `0x216F87CDDD0`
- cluster trace instruction: `0x7FF7879B117E`
- cluster pattern offset: `rift_x64.exe+0x931169`
- source container load: `0x7FF7879B1133` / `mov rcx,[rax+78]`
- source object load: `0x7FF7879B1137` / `mov rdi,[rcx+rdx*8]`
- source resolve target: `0x7FF787705C30`
- accessor return offset: `72` (`+0x48`)
- suggested source-chain scan: `rift_x64.exe+0x931133`
- suggested accessor scan: `rift_x64.exe+0x685C30`

Script fix validated in this pass:

- `C:\RIFT MODDING\RiftReader\scripts\resolve-proof-coord-anchor.ps1` now uses
  named hashtable splatting when invoking `trace-player-coord-write.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\capture-player-trace-cluster.ps1` now
  uses named hashtable splatting, a 12-byte access watch window, and
  `MaxCandidates=4`
- `C:\RIFT MODDING\RiftReader\scripts\refresh-discovery-chain.ps1` now accepts
  and propagates exact `-ProcessId` / `-TargetWindowHandle` through the
  provenance chain instead of relying on process-name-only defaults
- `C:\RIFT MODDING\RiftReader\scripts\capture-player-source-accessor-family.ps1`
  and `C:\RIFT MODDING\RiftReader\scripts\capture-player-stat-hub-graph.ps1`
  now support exact target args for reader calls and record the target in their
  output artifacts
- `C:\RIFT MODDING\RiftReader\scripts\refresh-actor-facing-discovery.ps1` now
  passes the exact live target into `refresh-discovery-chain.ps1` during
  `-RunProvenance`
- both patched paths were exercised live and then covered by the source-chain
  regression tests listed below

## Historical April 28 actor yaw / pitch truth

_Historical: April 30 re-promoted actor yaw/facing to
`0x216F2F26020 @ +0x60/+0x94`; the April 28 `+0xD4` lead below is stale in the
current April 30 proof packet unless separately re-proven._

April 28 live agentic discovery promoted a then-current session-bound lead:

- canonical live source address: `0x216FE3C6280`
- canonical forward basis row:
  - `X = +0xD4`
  - `Y = +0xD8`
  - `Z = +0xDC`
- canonical formulas:
  - yaw = `atan2(forwardZ, forwardX)`
  - pitch = `atan2(forwardY, sqrt(forwardX^2 + forwardZ^2))`

April 28 live checks on the promoted lead:

- `refresh-actor-facing-discovery.ps1 -RestartSession -StimulusMode AutoHotkey`
  promoted `0x216FE3C6280 @ +0xD4`
- reversible validation observed yaw peaks of about `59.055°` and `74.600°`
  with `0.0` coord drift across one D/A cycle
- `dotnet ... -- --pid 41220 --read-player-orientation --json` resolved the
  same behavior-backed lead
- telemetry preflight used memory-facing from `0x216FE3C6280 @ +0xD4`
- `refresh-actor-facing-discovery.ps1 -RunProvenance -ProcessId 41220
  -TargetWindowHandle 0xBD0D94` completed successfully after exact-target
  plumbing was added
- provenance summary: `SuccessfulSteps=1`, `FailedSteps=0`,
  `ProvenanceStatus=confirmed`

Operational interpretation:

- the April 28 live actor-facing truth was the validated `0xD4` forward row on
  `0x216FE3C6280`
- this is facing-only truth; it is not the movement coord source
- the April 23 actor-facing address `0x12CC0FA0F70 @ +0xD4` and earlier April
  source-chain/accessor-family addresses are historical after the April 28
  client update unless separately re-proven
- the exact-target post-update provenance chain was green for that live
  PID/HWND, but it remains session-bound evidence; rerun it after a client
  restart/update before treating addresses as current again

## Historical April 28 telemetry and navigation validation

_Historical: retained as the earlier post-update movement proof. The April 30
section above is the current actor-yaw/coord truth after the later live
recovery._

April 28 telemetry preflight after final active-proof ReaderBridge refresh on
**April 28, 2026**:

- memory coords available: `true`
- memory coords valid: `true`
- memory facing available: `true`
- facing valid: `true`
- effective position source: `memory`
- effective facing source: `memory-facing`
- position source address: `0x216F87CDE18`
- facing source address: `0x216FE3C6280`
- facing forward basis offset: `0xD4`

Read-only navigation preflight was also validated with the active-proof
current-session smoke waypoint file:

- waypoint file:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\post-update-inworld-20260428-141625\current-session-smoke-waypoints-active-proof.json`
- command mode: `--read-navigation-current`
- anchor source: `coord-trace-anchor`
- current address: `0x216F87CDE18`
- planar distance to smoke destination after active proof: about `1.784`
- arrival radius: `2.1`
- within arrival radius: `true`
- facing source: `0x216FE3C6280 @ +0xD4`
- signed bearing delta before the active proof: about `0.065°`
- suggested turn direction: `right`

Smallest active `--navigate-waypoints` smoke proof also passed:

- runner:
  - `C:\RIFT MODDING\RiftReader\scripts\navigation\run-a-to-b-prototype.ps1`
- log:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\post-update-inworld-20260428-141625\a-to-b-prototype-active-proof.ndjson`
- route file:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\post-update-inworld-20260428-141625\current-session-smoke-waypoints-active-proof.json`
- status: `success`
- stop reason: `arrived`
- anchor source: `coord-trace-anchor`
- pulse count: `1`
- input: one `w` pulse for `250 ms`
- initial planar distance: `2.5991395661`
- final planar distance: `1.7840590320`
- elapsed: `2406 ms`
- initial position:
  - `X = 7448.36083984375`
  - `Y = 863.5816650390625`
  - `Z = 2973.037109375`
- final position:
  - `X = 7449.17529296875`
  - `Y = 863.5852661132812`
  - `Z = 2973.069091796875`

No active multi-segment route-chain proof was run during this post-update
validation slice.

## Validation commands from this pass

These checks passed after the April 28 update and the small script fixes:

- PowerShell parser checks for:
  - `C:\RIFT MODDING\RiftReader\scripts\resolve-proof-coord-anchor.ps1`
  - `C:\RIFT MODDING\RiftReader\scripts\capture-player-trace-cluster.ps1`
- whitespace check:
  - `git diff --check -- scripts/resolve-proof-coord-anchor.ps1 scripts/capture-player-trace-cluster.ps1`
- source-chain recovery regression:
  - `C:\RIFT MODDING\RiftReader\scripts\test-player-source-chain-recovery.ps1`
- source-chain fresh rebuild regression:
  - `C:\RIFT MODDING\RiftReader\scripts\test-player-source-chain-fresh-rebuild.ps1`
- actor-facing proof suite:
- `C:\RIFT MODDING\RiftReader\scripts\test-actor-facing-proof-suite.ps1`
- navigation proof suite, non-live/default mode:
  - `C:\RIFT MODDING\RiftReader\scripts\navigation\test-navigation-proof-suite.ps1`
- live exact-target provenance chain:
  - `C:\RIFT MODDING\RiftReader\scripts\refresh-actor-facing-discovery.ps1 -RunProvenance -ProcessId 41220 -TargetWindowHandle 0xBD0D94`
- final post-provenance ReaderBridge refresh, proof anchor, telemetry preflight,
  and read-only navigation-current sanity checks
- exact-target proof polling watchset export:
  - `C:\RIFT MODDING\RiftReader\scripts\export-proof-polling-watchset.ps1 -ProcessId 41220 -TargetWindowHandle 0xBD0D94 -Json`
- proof watchset reader smoke:
  - `dotnet ... -- --pid 41220 --record-session --session-watchset-file scripts\captures\proof-polling-watchset.json --session-sample-count 2 --session-interval-ms 100 --json`
- active movement smoke proof:
  - `C:\RIFT MODDING\RiftReader\scripts\navigation\run-a-to-b-prototype.ps1 -ProcessId 41220 -TargetWindowHandle 0xBD0D94 -WaypointFile <active-proof-route> -UseExistingWaypoints -AutoConfirm -SkipRefresh -ArrivalRadius 2.1 -MaxTravelSeconds 5`
- final post-active ReaderBridge refresh, proof anchor, telemetry preflight, and
  read-only navigation-current sanity checks

## Broken, stale, or pending right now

- April 23 live addresses are historical after the April 28 client update:
  - old coord anchor: `0x12C9B02B888`
  - old actor-facing lead: `0x12CC0FA0F70 @ +0xD4`
- active single-segment smoke movement has been re-promoted after the update;
  multi-segment route-chain movement is still pending
- actor-facing selector/source-chain provenance is green only for the current
  live PID/HWND; it is not durable across restarts or future client updates
- proof polling watchset is current for PID `41220` / HWND `0xBD0D94`, but it
  must be rebuilt after client restart/update before movement proof
- camera yaw/pitch/distance on `main` remains stale/unverified after the update
- `--read-player-orientation` without explicit `--pid` / `--process-name`
  remains the historical artifact-only path until the owner/source artifact path
  is rebuilt

## Canonical scripts on `main`

- `C:\RIFT MODDING\RiftReader\scripts\resolve-proof-coord-anchor.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\capture-player-trace-cluster.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\capture-player-source-chain.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\capture-actor-orientation.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\refresh-actor-facing-discovery.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\test-actor-orientation-stimulus.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\profile-actor-orientation-keys.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\post-rift-key.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\invoke-gated-forward-smoke.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\refresh-readerbridge-export.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\navigation\test-navigation-proof-suite.ps1`

## Evidence folder

Post-update recovery evidence for this pass is under:

- `C:\RIFT MODDING\RiftReader\scripts\captures\post-update-inworld-20260428-141625`

Key files:

- `process-info.json`
- `smart-capture-player-family.stdout.txt`
- `capture-player-source-chain-refreshcluster-size12-max4.stdout.txt`
- `resolve-proof-coord-anchor-after-sourcechain.stdout.txt`
- `resolve-proof-coord-anchor-final-refresh.stdout.txt`
- `read-player-orientation-after-facing-promotion.stdout.txt`
- `telemetry-preflight-after-facing-promotion.stdout.txt`
- `current-session-smoke-waypoints.json`
- `read-navigation-current-current-smoke.stdout.txt`
- `refresh-actor-facing-discovery-runprovenance-exact-target.stdout.txt`
- `refresh-readerbridge-export-post-provenance.stdout.txt`
- `resolve-proof-coord-anchor-post-provenance-after-readerbridge-refresh.stdout.txt`
- `telemetry-preflight-post-provenance-after-readerbridge-refresh.stdout.txt`
- `current-session-smoke-waypoints-post-provenance.json`
- `read-navigation-current-post-provenance-after-readerbridge-refresh.stdout.txt`
- `export-proof-polling-watchset-exact-target.stdout.txt`
- `record-session-proof-watchset-smoke.stdout.txt`
- `watchset-record-session-smoke`
- `current-session-smoke-waypoints-active-proof.json`
- `run-a-to-b-prototype-active-proof.stdout.txt`
- `a-to-b-prototype-active-proof.ndjson`
- `resolve-proof-coord-anchor-after-active-proof.stdout.txt`
- `telemetry-preflight-after-active-proof.stdout.txt`
- `read-navigation-current-after-active-proof.stdout.txt`

## Camera script location note

The currently documented live camera helpers are **not present** on the `main`
worktree during this pass.

The active camera workflow currently lives on:

- branch: `feature/camera-orientation-discovery`
- worktree: `C:\RIFT MODDING\RiftReader_camera_feature`

Relevant scripts there:

- `C:\RIFT MODDING\RiftReader_camera_feature\scripts\read-live-camera-yaw-pitch.ps1`
- `C:\RIFT MODDING\RiftReader_camera_feature\scripts\find-live-camera-angle-candidates.ps1`
- `C:\RIFT MODDING\RiftReader_camera_feature\scripts\test-camera-stimulus.ps1`

Do not treat camera outputs as current truth on `main` until the camera path is
revalidated on the updated client.

<!-- RIFTREADER_CSHARP_SENDINPUT_SCANCODE_PROOF_20260511_START -->
## May 11, 2026 — C# SendInput ScanCode movement proof

C# `RiftReader.SendInput` is now proof-backed for bounded forward movement calibration.

Measured run:

- target: `rift_x64` PID `35728`, HWND `0x60E42`
- wrapper: `scripts/send-rift-key-csharp.ps1`
- project: `tools/RiftReader.SendInput/RiftReader.SendInput.csproj`
- commit: `06d82cd29bc173d4145829513b8eb521c0d9c6f5`
- method: `--input-mode ScanCode --key w --hold-ms 750`
- result: `passed-csharp-sendinput-scancode-displacement`
- before API coordinate: `X=7405.9297 Y=871.78 Z=3028.05`
- after API coordinate: `X=7405.0498 Y=871.78 Z=3027.7`
- planar displacement: `0.9469551256527897`
- spatial displacement: `0.9469551256527897`
- exact HWND foreground: `true`
- target process foreground: `true`
- automatic `Esc`: `false`
- CE: `false`
- SavedVariables live truth: `false`

Current backend truth:

1. `tools/RiftReader.SendInput` / `scripts/send-rift-key-csharp.ps1 --input-mode ScanCode` is proof-backed for bounded forward movement.
2. Legacy `scripts/send-rift-key.ps1` is superseded for serious SendInput testing because earlier PowerShell VirtualKey/ScanCode runs delivered but did not move.
3. `scripts/post-rift-key.ps1 -SkipBackgroundFocus -UseWindowMessage` remains a working exact-HWND window-message backend.
4. Do not auto-send `Esc`; gameplay input mode is operator-managed until a reliable chat/text-entry detector exists.
5. Proof anchor remains required for navigation/proof promotion, but not for bounded backend calibration.
<!-- RIFTREADER_CSHARP_SENDINPUT_SCANCODE_PROOF_20260511_END -->
