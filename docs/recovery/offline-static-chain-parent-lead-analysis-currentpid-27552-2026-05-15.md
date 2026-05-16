# Offline parent/reference lead analysis — current PID coordinate static-chain work

Generated UTC: `2026-05-15T08:08:41+00:00`
Scope: **offline artifact analysis only**. No live memory reads, no x64dbg attach/watchpoints, no Cheat Engine, and no movement/input.

## Verdict

The stable qword `0x27B1EC75C50` remains the best **offline parent/container lead**, but it is **not** a stable static pointer chain. It was observed as a stable qword inside the proven coordinate neighborhood, and all available evidence still stops at current-PID heap/object relationships.

| Address | Meaning | Current offset relationship |
|---|---|---|
| `0x27B1EC70000` | current top memory family/allocation base | rank-1 readable private region |
| `0x27B1EC75C50` | best offline parent/container lead | family base `+0x5C50` |
| `0x27B1ED85080` | proof read region | family base `+0x115080`; parent lead `+0x10F430` |
| `0x27B1ED850C0` | proven XYZ coord leaf | region `+0x40`; family base `+0x1150C0`; parent lead `+0x10F470` |

## Candidate-family recurrence pattern

Across parsed current-PID candidate JSON files, the same coordinate address/base/offset recurs. This strengthens current-PID confidence, but it does not create a restart-stable static root.

| Candidate address | Count |
|---|---:|
| `0x27B1ED850C0` | 10 |

| Family base | Count |
|---|---:|
| `0x27B1EC70000` | 10 |

| Coord offset | Count |
|---|---:|
| `0x1150C0` | 10 |

### Latest candidate runs sampled

| Generated UTC | Candidate count | Addresses | File |
|---|---:|---|---|
| `2026-05-15T02:20:24.207850+00:00` | `0` | `` | `scripts/captures/family-scan-currentpid-27552-20260515-022020-431060/api-family-vec3-candidates.json` |
| `2026-05-15T02:20:28.688346+00:00` | `0` | `` | `scripts/captures/family-scan-currentpid-27552-20260515-022024-593618/api-family-vec3-candidates.json` |
| `2026-05-15T02:20:33.524419+00:00` | `1` | `0x27B1ED850C0` | `scripts/captures/family-scan-currentpid-27552-20260515-022029-063377/api-family-vec3-candidates.json` |
| `2026-05-15T05:51:19.431420+00:00` | `1` | `0x27B1ED850C0` | `scripts/captures/family-scan-currentpid-27552-20260515-055116-450192/api-family-vec3-candidates.json` |
| `2026-05-15T05:54:43.020496+00:00` | `1` | `0x27B1ED850C0` | `scripts/captures/family-scan-currentpid-27552-20260515-055439-934855/api-family-vec3-candidates.json` |
| `2026-05-15T06:24:00.904157+00:00` | `1` | `0x27B1ED850C0` | `scripts/captures/family-scan-currentpid-27552-20260515-062357-946704/api-family-vec3-candidates.json` |
| `2026-05-15T06:30:02.981812+00:00` | `1` | `0x27B1ED850C0` | `scripts/captures/family-scan-currentpid-27552-20260515-063000-134028/api-family-vec3-candidates.json` |
| `2026-05-15T06:33:57.571763+00:00` | `1` | `0x27B1ED850C0` | `scripts/captures/family-scan-currentpid-27552-20260515-063354-727364/api-family-vec3-candidates.json` |
| `2026-05-15T06:37:53.193962+00:00` | `1` | `0x27B1ED850C0` | `scripts/captures/family-scan-currentpid-27552-20260515-063750-354520/api-family-vec3-candidates.json` |
| `2026-05-15T06:41:25.074678+00:00` | `1` | `0x27B1ED850C0` | `scripts/captures/family-scan-currentpid-27552-20260515-064122-206907/api-family-vec3-candidates.json` |
| `2026-05-15T06:58:08.061785+00:00` | `1` | `0x27B1ED850C0` | `scripts/captures/family-scan-currentpid-27552-20260515-065805-164528/api-family-vec3-candidates.json` |
| `2026-05-15T07:02:36.011093+00:00` | `1` | `0x27B1ED850C0` | `scripts/captures/family-scan-currentpid-27552-20260515-070233-117821/api-family-vec3-candidates.json` |

## Memory-region context

| Item | Value |
|---|---|
| Inventory artifact | `scripts/captures/recover-currentpid-coord-anchor-fast-execute-27552-20260515-055223-314971/03-memory-inventory/memory-region-inventory-currentpid-27552-20260515-055438-908621/regions.json` |
| Scan-plan artifact | `scripts/captures/recover-currentpid-coord-anchor-fast-execute-27552-20260515-055223-314971/03-memory-inventory/memory-region-inventory-currentpid-27552-20260515-055438-908621/scan-plan.json` |
| Region containing parent/coord | `0x27B1EC70000`..`0x27B1FC80000`, `16.0625` MiB, `readwrite`, `private`, rank `1` |

Interpretation: both the parent lead and coordinate leaf sit inside the same rank-1 private readwrite heap region. That is excellent for current-PID recovery but weak for static-chain proof.

## Byte-reference search inside existing samples

Search scope was limited to `scripts/sessions/**/samples.ndjson` byte blobs. These are narrow watchset/readback samples, **not full process dumps**.

| Target | Address | Little-endian qword needle | Occurrences in sampled blobs | First offset seen |
|---|---|---|---:|---|
| `parentLead` | `0x27B1EC75C50` | `505CC71E7B020000` | 123 | `0x68` |
| `coordLeaf` | `0x27B1ED850C0` | `C050D81E7B020000` | 0 | `` |
| `readRegion` | `0x27B1ED85080` | `8050D81E7B020000` | 0 | `` |
| `familyBase` | `0x27B1EC70000` | `0000C71E7B020000` | 0 | `` |

Interpretation:

- `parentLead` occurrences are expected because the qword sits at `region+0x68` in the sampled coord neighborhood.
- No broad reference map is available offline, so absence of other references does **not** mean no references exist in process memory.
- A real parent/reference scan would need current-PID memory reads or debugger evidence, which remains outside the current offline-only boundary.

## Latest region field sketch

| Offset | Absolute address | u32 | f32 interpretation | qword | qword class | qword delta from family base | u32 unique count | qword unique count |
|---|---|---|---:|---|---|---:|---:|---:|
| `0x0` | `0x27B1ED85080` | `0xFFFFFFFF` | `nan` | `` | `` | `` | `1` | `1` |
| `0x18` | `0x27B1ED85098` | `0x20007D0` | `9.40619688412122e-38` | `` | `` | `` | `1` | `1` |
| `0x20` | `0x27B1ED850A0` | `0xFFFF` | `9.183409485952689e-41` | `` | `` | `` | `1` | `1` |
| `0x28` | `0x27B1ED850A8` | `0x0` | `0.0` | `` | `` | `` | `1` | `1` |
| `0x40` | `0x27B1ED850C0` | `0x45E4983F` | `7315.03076171875` | `` | `` | `` | `11` | `13` |
| `0x44` | `0x27B1ED850C4` | `0x445AC772` | `875.1163330078125` | `` | `` | `` | `13` | `13` |
| `0x48` | `0x27B1ED850C8` | `0x453EA3EA` | `3050.24462890625` | `0x27B453EA3EA` | `pointer-like` | `+0x2677a3ea` | `11` | `11` |
| `0x4C` | `0x27B1ED850CC` | `0x27B` | `8.898245248462588e-43` | `` | `` | `` | `1` | `1` |
| `0x50` | `0x27B1ED850D0` | `0x20` | `4.484155085839415e-44` | `` | `` | `` | `1` | `1` |
| `0x58` | `0x27B1ED850D8` | `0x83` | `1.8357009882655104e-43` | `` | `` | `` | `1` | `1` |
| `0x60` | `0x27B1ED850E0` | `0xDAECC947` | `-3.3324700641787904e+16` | `` | `` | `` | `1` | `1` |
| `0x68` | `0x27B1ED850E8` | `0x1EC75C50` | `2.1108124118098872e-20` | `0x27B1EC75C50` | `pointer-like` | `+0x5c50` | `1` | `1` |
| `0x70` | `0x27B1ED850F0` | `0x1` | `1.401298464324817e-45` | `` | `` | `` | `1` | `1` |
| `0x78` | `0x27B1ED850F8` | `0x3` | `4.203895392974451e-45` | `` | `` | `` | `1` | `1` |
| `0x80` | `0x27B1ED85100` | `0x1` | `1.401298464324817e-45` | `` | `` | `` | `1` | `1` |

Key layout conclusion:

- Region `+0x40/+0x44/+0x48` is the only meaningful changing float lane and is the proven XYZ triplet.
- Region `+0x68` is a stable pointer-like qword to `0x27B1EC75C50`.
- The apparent qword at `+0x48` is a false pointer lead: it overlaps the proven Z float bytes and the following `0x27B` value, changes with pose, and should not be ranked as owner/static evidence.
- The surrounding constants (`+0x58 = 0x20`, `+0x60 = 0x83`, `+0x70 = 1`, `+0x78 = 3`, `+0x80 = 1`) look structural but do not identify a static root by themselves.

## What this improves over the first offline report

| Question | Refined offline answer |
|---|---|
| Is there a repeatable parent/container lead? | Yes: `region+0x68 -> 0x27B1EC75C50`, stable across current-region samples. |
| Does this lead point to a static chain? | No. It is inside the same current-PID private heap family. |
| Do candidate scans repeatedly find the same coord leaf? | Yes, the same address/base/offset recurs across current-PID candidate files. |
| Can offline artifacts locate the module/RVA root? | No. Existing samples are too narrow and no current-PID access event exists. |
| What should be scanned next if staying safe? | Prepare a parent/reference scan plan around `0x27B1EC75C50`, but do not execute live memory reads without approval. |

## Blockers

- `parent lead was observed only as a qword inside the coord neighborhood samples`
- `no references to parent lead were found outside sampled region blobs because the available offline samples are narrow watchsets, not a full memory image`
- `no current instruction provenance links the parent lead to rift_x64.exe code`
- `no module/RVA root or static-owner chain is derivable offline from current artifacts`

## Recommended next offline-only work

1. Convert this lead into a **planned** parent/reference scan packet, not a live scan.
2. Define exactly what a future scan would seek: references to `0x27B1EC75C50`, references to `0x27B1ED85080`, and any module/static pointer path into the rank-1 heap region.
3. Predefine rejection rules: heap-only references, VCRUNTIME/memcpy copy helpers without caller path, and one-pose-only evidence stay candidate-only.
4. Keep current x64dbg boundary unchanged: offline/read-only until explicit current-turn approval.
5. If live reads are later approved, start with bounded parent/reference scan around the current rank-1 region before broad process scans.

## Generated artifacts

| Artifact | Path |
|---|---|
| Machine summary | `scripts/captures/offline-static-chain-parent-lead-analysis-currentpid-27552-20260515-080841/summary.json` |
| Human report | `docs/recovery/offline-static-chain-parent-lead-analysis-currentpid-27552-2026-05-15.md` |
