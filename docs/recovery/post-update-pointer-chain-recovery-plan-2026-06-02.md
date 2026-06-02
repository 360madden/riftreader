# Post-update pointer-chain recovery plan - 2026-06-02

Generated UTC: `2026-06-02T17:47:35Z`
Repo: `C:\RIFT MODDING\RiftReader`

## Verdict

The 2026-06-02 RIFT update changed the current process epoch enough that the
previous promoted static owner root must not be used as current navigation truth.
The old module RVA is still readable, but its qword is currently null:

`[rift_x64+0x32EBC80] == 0x0` for PID `77152` / HWND `0x17A0DB2`.

The current direct coordinate candidate remains useful as a recovery seed:

`api-family-hit-000001 @ 0x1D4BA11BE00`

It matches a fresh RRAPICOORD/API coordinate within about `0.005`, but it is
candidate-only and not movement proof.

## Current target epoch

| Field | Value |
|---|---|
| PID | `77152` |
| HWND | `0x17A0DB2` |
| Process start UTC | `2026-06-02T15:45:29.2617327Z` |
| Module base | `0x7FF7211C0000` |
| RIFT manifest version | `STABLE-1-1152-a-1256395` |
| RIFT manifest path | `C:\Program Files (x86)\Glyph\Games\RIFT\Live\manifest64.txt` |
| Manifest `rift_x64.exe` SHA1 | `a8ba8748ea752e4e5581cea34188dc702469c923` |
| Binary LastWriteTimeUtc | `2026-06-02T09:04:57.6557069Z` |
| Binary SHA256 | `339F5FF5D52EDE1CDC3F239E3DA927A8872B595EE1AABCB799725E93F0085977` |
| Client size | `640x360` |

## Evidence gathered

| Evidence | Result | Artifact |
|---|---|---|
| Exact target/window | One RIFT window, target matches PID/HWND | live MCP + PowerShell checks |
| Old static root read | `0x7FF7244ABC80 -> 0x0` | console root qword probe |
| Old promoted coordinate/facing chains | Blocked with explicit `root-pointer-null` verdict | `scripts/captures/static-owner-coordinate-chain-readback-20260602-175043-068641/summary.json` |
| RIFT manifest version | Current install is `STABLE-1-1152-a-1256395`; PE version fields are generic `1.0.0.0`, so manifest version is the authoritative semantic update identifier | `C:\Program Files (x86)\Glyph\Games\RIFT\Live\manifest64.txt` |
| Current-PID fast reacquire | Found direct vec3 candidate | `scripts/captures/recover-currentpid-coord-anchor-fast-execute-77152-20260602-162111-548228/summary.json` |
| Candidate readback | Fresh API-vs-memory max delta about `0.005` | `scripts/captures/candidate-readback-currentpid-77152-20260602-170631-488108/candidate-readback-summary.json` |
| Quick static field matrix | Owner-layout offsets still have static access evidence; old root refs not found in bounded pass | `scripts/captures/static-field-access-matrix-20260602-173358-216541/summary.json` |
| Fresh Ghidra static evidence | Updated binary scanned `8,058,671` instructions; old root refs captured: `0` | `scripts/captures/ghidra-static-analysis-20260602-173637/summary.json` |
| Static readback helper hardening | Added explicit `root-pointer-null` classification for readable static roots that contain null | `scripts/static_owner_coordinate_chain_readback.py` |
| Candidate-minus-0x320 owner hypothesis | Rejected: no owner/vtable module pointers, nonsense facing/support fields | `scripts/captures/postupdate-owner-hypothesis-currentpid-77152-20260602-175553-458224/summary.json` |
| Pointer refs to direct coordinate candidate | Weak: one non-module same-family ref, no module/static root hit | `scripts/captures/pointer-family-scan-20260602-175458-061032/summary.json` |
| Owner-batch module hints | Candidate-only ref-storage island at `0x1D4BA11F480`; module-RVA hints `0x26E5E80`, `0x26E5278`, `0x26E3200` | `scripts/captures/pointer-owner-batch-currentpid-77152-20260602-181241-737979/summary.json` |
| Post-update root-signature seed | Reproducible candidate-only seed built from owner-batch evidence; not a promoted root | `scripts/postupdate_root_signature_seed.py`; `scripts/captures/postupdate-root-signature-seed-currentpid-77152-20260602-184943-874781/root-signature-seed.json` |
| Root-signature batch sweep | Negative: three module-RVA sweeps reconfirmed heap/ref-storage evidence but found no high-signal parent/root candidate | `scripts/captures/root-signature-batch-sweep-currentpid-77152-20260602-183920-580940/summary.json` |
| Root-family classifiers | Negative/weak: priority parent leads are low-score heap-like or string/asset-heavy; no promotion candidates | `scripts/captures/root-signature-family-classifier-20260602-185009-448441/summary.json`, `scripts/captures/root-signature-family-classifier-20260602-185009-419098/summary.json`, `scripts/captures/root-signature-family-classifier-20260602-185009-432017/summary.json` |
| Priority lead pointer-family follow-ups | Negative: bounded scans over exported classifier leads found `0` module/RIFT-module hits; largest scan hit the 32-target cap | `scripts/captures/pointer-family-scan-20260602-185045-917536/summary.json`, `scripts/captures/pointer-family-scan-20260602-185045-954296/summary.json`, `scripts/captures/pointer-family-scan-20260602-185045-985913/summary.json` |
| Static access-chain packet | Positive for updated constructor/global evidence, negative for position root: constructor `0x3F8B0` writes the same owner-layout field cluster and stores `rdi` to `rift_x64+0x335F508`; current readback points to `0x1D4BA2A6230`, but `+0x320` is unit/matrix-like and no world-coordinate triple matches the API coordinate | `scripts/postupdate_static_access_chain.py`; `scripts/captures/postupdate-static-access-chain-20260602-194135-824662/summary.json` |

## Recovery methods examined

| Method | Signal | Risk/gate | Use now? | Reason |
|---|---|---|---|---|
| `recover_current_pid_coord_anchor_fast.py` | High for current-PID direct coordinate candidates | Safe until movement/proof stages; movement requires explicit flag | **Primary live reacquire lane** | Uses target preflight, visual gate, live reference, memory inventory, prioritized stop-on-hit scan. Already found current candidate quickly. |
| `current_pid_candidate_readback.py` | High for same-time API-vs-memory candidate verification | Safe readback; no input | **Primary verification loop** | Confirms candidate survives without promoting it. Useful after any root/candidate hypothesis. |
| `static_owner_coordinate_chain_readback.py` | High for already-known static root survival | Safe readback; no input | **Diagnostic only until root fixed** | It proves the old root is null in this epoch; do not retry blindly without a new root. |
| `riftreader-static-field-access-matrix.cmd` | Medium/high offline offset semantics | Offline only | **Use for static prioritization** | Shows owner layout offsets still exist and clusters remain useful; cannot identify current owner/root by itself. |
| `riftreader-ghidra-static-evidence.cmd` | High offline code/xref evidence | Offline only; slow | **Run after update** | Last RIFT Ghidra artifact predates the update. Fresh Ghidra should be used to inspect root writers/accessors and replacement statics. |
| `riftreader_postupdate_proof_reacquire_stage1.py` | Medium legacy post-update control plane | Safe unless `--allow-movement-stimulus` | **Fallback/reference only** | Older path uses less optimal family scan; useful if fast helper regresses. |
| `pointer_family_scan.py` / owner neighborhood scans | High for rediscovering owner-root edges once an owner candidate is known | Live memory read, no input | **Use after owner candidate identified** | Previous promotion relied on exactly one module hit to owner. Need this again for a new root. |
| Structural/root-signature helpers | Medium if module-hint sweep/type artifacts exist | Read-only artifacts/live memory depending helper | **Fallback after static clusters** | `root_signature_family_classifier.py`, `owner_type_instance_inspector.py`, and parent-graph helpers can classify candidates, but they need upstream type/module-hint artifacts. |
| `current_pid_family_snapshot_sequence.py` | Medium/high for comparing same-process families over time | Live memory reads; stimulus may be gated depending sequence | **Use no-stimulus first** | Good for copying/duplicate detection; movement variant requires approval. |
| `riftreader-current-truth-refresh-plan/apply` | High for publishing truth | Apply writes tracked truth and is gated | **Plan only until proof gates pass** | Current truth still references PID `12664`; never apply candidate-only evidence. |
| Navigation consumer/live-run tools | Downstream validation | Live-run/input gated | **Blocked** | Navigation must wait for current proof/current truth. |
| ChromaLink provider | High if fresh | Provider state external; writes gated | **Repair optional** | Currently refused connection; RRAPICOORD fallback works but slower. |
| x64dbg/CE/procdump/vmmap | Potentially high but high blast radius | Explicit debugger/process-inspection gates | **Do not use now** | Safe no-debug methods already produced a candidate and static evidence. |

## Optimal recovery workflow

### Phase 0 - Freeze stale truth and exact target

1. Keep movement/navigation blocked while tracked truth points at PID `12664`.
2. Bind exact PID/HWND/process-start/module-base for PID `77152`.
3. Record binary hash/timestamp so evidence is tied to this update.
4. Do not use old heap owner/coordinate/proof addresses as current truth.

### Phase 1 - Establish current live coordinate seed without movement

1. Use `recover_current_pid_coord_anchor_fast.py --execute` with exact PID/HWND and **without** movement/truth/proof flags.
2. Prefer ChromaLink only if fresh/healthy; otherwise use RRAPICOORD fallback.
3. Use ranked memory inventory + stop-on-hit scan, not broad scanning first.
4. Verify candidate with `current_pid_candidate_readback.py` against a fresh API reference.
5. Preserve candidate-only status.

Current result: `api-family-hit-000001 @ 0x1D4BA11BE00` passed same-time API-vs-memory readback.

### Phase 2 - Rediscover owner/root edge safely

Goal: replace the broken old root `[rift_x64+0x32EBC80]` with a current static or high-stability owner acquisition path.

Preferred sequence:

1. Run fresh offline Ghidra evidence against the updated binary. Completed for this update: `scripts/captures/ghidra-static-analysis-20260602-173637/summary.json`, old root references captured: `0`.
2. Use quick/full static field matrix around clustered functions such as `0x3F8B0`, `0x18BC50`, `0x198470`, `0x19A520`, `0x1A3BC0`, `0xB0EC0`, and `0xB14C4`.
3. From the direct coordinate candidate, inspect nearby memory for owner-shaped windows with coordinate at a stable owner-relative offset. Completed first hypothesis: `candidateAddress-0x320` is not owner-shaped, so do not assume the direct candidate is embedded in the old owner layout.
4. Run pointer-family scans looking for module/static references to any inferred owner, mirroring the successful 2026-05-27 workflow. Pointer refs to the direct coordinate candidate alone produced no module/static root hit.
5. Reject roots that only point to stale heap addresses, copied coordinate buffers, or single-pose aliases.

Current post-update result: the candidate-only owner-batch/root-signature path is now exhausted for the three available module-RVA hints. The sweeps and classifier follow-ups stayed heap-only/no-module-root. Do not repeat the same `0x26E5E80`, `0x26E5278`, or `0x26E3200` sweeps unless a fresh owner batch produces new evidence.

Static/access-chain tracing has now produced one durable new anchor:

| Anchor | Current readback | Classification | Use |
|---|---|---|---|
| `[rift_x64+0x335F508]` | `0x1D4BA2A6230` | `orientation-matrix-root-not-position-root` | Candidate orientation/facing/static layout anchor only; **not** a world-position resolver |

The direct call breadcrumbs from that constructor are:

`0x3F8B0 <- 0x39CD0 <- 0x13D2D80 <- 0x13CA1F0 <- 0x13B7DE0 <- 0x13A37D0 <- {0x13AFAD0, 0x13B5E00} <- 0x1392E10 <- 0x6A7890 <- {0xC38390, 0xF75D90}`

The packet now also records breadcrumb-function RIP-relative globals and field accesses. The `0xC38390` function touches `rift_x64+0x32DD7E8`, making it a follow-up static/container scan target. This is not a promoted root and is not yet position proof.

The next safe lane is no longer another repeat root-signature sweep. Continue offline caller-chain/static container tracing above `0x1392E10`, `0x6A7890`, `0xC38390`, and `0xF75D90`, plus a fresh non-repeating current-PID family/container scan to find the higher-level object that owns the current world-coordinate copy.

Success criteria:

- Root chain resolves from module/static or another restart-survivable source.
- Owner-relative offsets recover coordinate `+0x320/+0x324/+0x328` and facing/yaw `+0x30C/+0x310/+0x314` or updated equivalents.
- Same candidate/root survives at least a relog/restart check before promotion.

### Phase 3 - Controlled displacement proof, only with explicit approval

Do not run until movement approval is explicit.

1. Run three-pose displacement validation against the current candidate/root hypothesis.
2. Require at least two displaced API-coordinate poses and same-candidate tracking.
3. Reject visual-only movement, zero API displacement, or copied/static coordinate mirrors.
4. If proof passes, run the promotion helper and same-target ProofOnly.
5. Only after ProofOnly passes, refresh tracked `current-truth.json` and navigation pointer discovery.

### Phase 4 - Navigation consumer recovery

1. Regenerate navigation pointer discovery and compact workflow status.
2. Regenerate navigation consumer state/package/readiness artifacts.
3. Run schema validation and downstream package demo.
4. Only then plan live route automation.

## Method ranking for this update

| Rank | Method | Why |
|---:|---|---|
| 1 | Fast current-PID reacquire + candidate readback | Already produced current coordinate truth seed with low risk. |
| 2 | Fresh offline Ghidra/static matrix/access-chain packet | Needed because binary changed and old static root is null; already found `rift_x64+0x335F508` as an orientation/static-layout anchor, not position. |
| 3 | Higher-level owner/container tracing above `0x1392E10` / `0x6A7890` and fresh non-repeating current-PID scans | Direct candidate is useful as a coordinate seed, but initial owner-layout hypothesis failed and `0x335F508` is not a position root. |
| 4 | Controlled displacement proof | Required for promotion but gated by movement approval. |
| 5 | Truth refresh/navigation consumer rebuild | Only after proof, otherwise it spreads stale/candidate truth. |
| 6 | ChromaLink repair | Useful for speed/freshness, but not required because RRAPICOORD fallback works. |
| 7 | Post-update legacy stage1 helper | Keep as fallback; not optimal primary path. |
| 8 | x64dbg/CE/process dump | Last resort only; currently unnecessary and gated. |

## Do not do

- Do not retry `[rift_x64+0x32EBC80]` as if it were current; root is null and fresh Ghidra captured zero old-root refs.
- Do not write `current-truth.json` from the direct candidate alone.
- Do not treat current API-vs-memory proximity as movement proof.
- Do not use SavedVariables as live truth.
- Do not run route automation while proof/current truth still points at PID `12664`.
- Do not use debugger/CE/procdump/vmmap without explicit approval.

## Next command sequence

Safe/no-input sequence already completed for this update:

```text
scripts\riftreader-ghidra-static-evidence.cmd --run --binary-path "C:\Program Files (x86)\Glyph\Games\RIFT\Live\rift_x64.exe" --json
scripts\riftreader-static-field-access-matrix.cmd --binary-path "C:\Program Files (x86)\Glyph\Games\RIFT\Live\rift_x64.exe" --root-rva 0x32EBC80 --offset 0x300,0x304,0x30C,0x310,0x314,0x320,0x324,0x328,0x438,0x43C,0x440 --json
python scripts\current_pid_candidate_readback.py --pid 77152 --hwnd 0x17A0DB2 --candidate-jsonl "C:\RIFT MODDING\RiftReader\scripts\captures\family-scan-currentpid-77152-20260602-162409-918002\api-family-vec3-candidates.jsonl" --reference-timeout-seconds 180 --json
python scripts\postupdate_static_access_chain.py --json
```

Next safe no-input implementation work is higher-level static container tracing above `0x1392E10` / `0x6A7890` / `0xC38390` / `0xF75D90`, plus any fresh non-repeating current-PID family/container scan. The candidate-neighborhood module-RVA sweep lane has current negative evidence and should not be repeated blindly. Keep `rift_x64+0x335F508` available as an orientation/facing anchor candidate, but do not treat it as position or current truth.

Gated sequence after explicit approval:

```text
python scripts\recover_current_pid_coord_anchor_fast.py --pid 77152 --hwnd 0x17A0DB2 --execute --movement-approved --allow-current-truth-update --run-proofonly --json
```

Only run the gated command after confirming the candidate/root hypothesis and movement approval.
