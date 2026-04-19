## Context

`C:\RIFT MODDING\RiftReader\docs\recovery\current-truth.md` currently marks source-chain refresh, selector-owner trace, and player orientation as broken or stale after the April 14, 2026 client update. At the same time, this branch already introduces a repo-native actor-yaw workflow in `C:\RIFT MODDING\RiftReader\scripts\run-actor-yaw-debug-scan.ps1` that chains together player-current truth, coord-anchor confirmation, candidate search, truth-like candidate proof, and optional bounded debug tracing.

The missing piece is not another broad search tool. The missing piece is a stable contract that answers three questions for every run:

1. Which source candidate won and why?
2. Was the evidence fresh and live, or degraded by cached fallback / blocked debug confirmation?
3. Is this run strong enough to promote the source back to repo truth?

## Goals / Non-Goals

**Goals:**
- Standardize a single actor-yaw proof run that emits one summary artifact with the selected candidate, evidence references, and promotion status.
- Treat cached fallback, stale artifacts, skipped proof, and debug-blocked runs as explicit degraded states instead of silent success.
- Publish repo truth only from a promotion-ready run with supporting artifact references and freshness metadata.

**Non-Goals:**
- Rebuild or expand the camera-orientation workflow.
- Replace the existing repo-native workflow with a broad Cheat Engine pointer-table process.
- Refactor unrelated typed-reader or addon features.

## Decisions

### 1. Use the repo-native actor-yaw debug workflow as the canonical proof path

The existing `run-actor-yaw-debug-scan.ps1` workflow already matches the current repo strategy: coord truth first, source-family candidate search second, turn-stimulus proof third, and bounded debug confirmation last. Extending that single path is lower risk than reviving multiple ad hoc orientation scripts or pushing truth decisions into scattered artifacts.

**Alternatives considered:**
- Keep candidate search, candidate proof, and debug confirmation as loosely related scripts with no single summary contract. Rejected because it makes truth promotion subjective and slows post-update recovery.
- Reintroduce a pointer-chain-first workflow. Rejected because the branch analysis explicitly treats pointer proof as a later confirmation step, not the primary discovery path.

### 2. Separate candidate selection from truth promotion

A run can still produce a “best candidate” even when the evidence is not strong enough to update repo truth. The summary artifact should therefore carry both:

- selection outcome: which candidate won
- promotion outcome: whether the run is safe to promote to repo truth

This keeps deterministic candidate ranking useful for debugging without allowing degraded runs to overwrite the repo’s current-truth documents.

**Alternatives considered:**
- Use one status field for both selection and truth promotion. Rejected because statuses like `success`, `trace-failed`, or `debug-blocked` do not fully capture whether the evidence is promotion-ready.

### 3. Make degraded-state provenance explicit and blocking

Cached selector-owner fallback, stale source-chain inputs, skipped turn stimulus, and skipped debug confirmation must be visible in the summary artifact and must block truth promotion when they invalidate the proof gate. This keeps the repo aligned with the existing post-update policy that older or degraded artifacts cannot silently become “current truth.”

**Alternatives considered:**
- Allow cached or partially confirmed runs to count as truth when they match historical expectations. Rejected because the current repo policy explicitly warns against promoting pre-update or fallback evidence as current truth.

### 4. Keep truth publication doc-driven and narrow

When a run is promotion-ready, the repo should update the narrow truth surfaces that people already use (`current-truth.md`, README references, and closely related recovery notes) with the authoritative source description, freshness date, and proof-artifact references. This is enough to make the truth usable without inventing a larger state-management system.

**Alternatives considered:**
- Create a new database or separate truth registry. Rejected as unnecessary for the current repo size and workflow.

## Risks / Trade-offs

- **[Game update drift]** → Keep promotion gated on fresh live proof and artifact references from the current client session.
- **[False positive candidate ranking]** → Require turn-stimulus responsiveness, coord-drift limits, and explicit proof artifacts before a run becomes promotion-ready.
- **[Debugger already attached]** → Record the run as debug-blocked or partially confirmed instead of treating skipped debug confirmation as a full success.
- **[Documentation drift from implementation reality]** → Update repo truth only from the same summary artifact used to determine promotion readiness.

## Migration Plan

1. Extend the existing actor-yaw workflow summary so it can express selection result, degraded-state reasons, and promotion readiness.
2. Normalize the supporting search/proof helpers so they feed the same proof contract.
3. Run the workflow against a live Rift client and review the resulting artifacts.
4. Update repo truth docs only when the run is promotion-ready; otherwise preserve the stale/provisional truth state.

## Open Questions

- Should repo-truth publication be fully automated from the workflow summary, or should it remain a reviewed documentation step that uses the summary as the gate?
- Is a debug-blocked but otherwise truth-like run enough for a provisional truth state, or should it remain strictly non-promotable?
