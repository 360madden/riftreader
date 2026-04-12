# Agentic Workflow

## Goal

Move discovery forward with narrow worker scopes, low context drift, and minimal
idle time between tasks.

## Recommended architecture

- **Top-level integrator**
  - owns final decisions, merges findings, applies patches, runs validation
  - is the only role allowed to change more than one worker lane in the same step
- **Coordinator sidecar**
  - does not edit code
  - maintains the rolling queue and next-assignment list
  - watches for anchor drift, quota pressure, and commit thresholds
- **Narrow workers**
  - each worker owns one lane only
  - each worker always has:
    - one active task
    - one pre-approved next task

Do **not** use a recursive “manager of managers” tree. Keep one thin
coordinator and several narrow workers.

## Worker lanes

### Lane A — Live discovery / memory graph

Owns:

- `C:\RIFT MODDING\RiftReader\scripts\smart-capture-player-family.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\trace-player-*.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\capture-player-*.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\capture-ce-family-neighborhood.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\capture-owner-state-neighborhood.ps1`

Does not own:

- watchset export
- package orchestration
- offline diff tooling

### Lane B — Session packaging / consistency

Owns:

- `C:\RIFT MODDING\RiftReader\scripts\export-discovery-watchset.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\record-discovery-session.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\inspect-capture-consistency.ps1`
- package/manifest/session docs

Does not own:

- live trace logic
- CE family narrowing logic

### Lane C — Offline decode / diff analysis

Owns:

- offline analyzers
- session comparison helpers
- docs that explain decoded structures

Does not own:

- live acquisition scripts
- package orchestration

### Lane D — Archival research (optional, on demand)

Owns:

- forum/history research notes
- old offset/path/tooling comparisons

Only use this lane when live engineering is blocked or when a newly found string,
class name, or subsystem label needs historical context.

## Rolling queue format

Every worker assignment should be written in this shape:

- **Active**
- **Next**
- **Validation**
- **Stop if**
- **Commit when**

That keeps the handoff small and prevents drift.

## Current recommended queue

### Lane A — Live discovery / memory graph

- **Active:** add a second-level pointer walker for the owner-state neighborhood,
  starting from `0x15769DDFC80`, `0x1577ACAFE90`, and `0x1577ACAFEA8`
- **Next:** build an immediate chained probe for transient CE families so a new
  family is inspected before the sample addresses drift
- **Validation:** fresh
  `C:\RIFT MODDING\RiftReader\scripts\capture-owner-state-neighborhood.ps1 -Json`
  and one short packaged session
- **Stop if:** selected source changes away from `0x1577AC2FB60`
- **Commit when:** pointer-chain artifact is stable across 2 runs

### Lane B — Session packaging / consistency

- **Active:** package the owner-state neighborhood subgraph as a first-class
  artifact in every projector-refresh session
- **Next:** add stimulus/event marker support for combat states like pull, cast,
  buff, and target swap
- **Validation:** fresh
  `C:\RIFT MODDING\RiftReader\scripts\record-discovery-session.ps1 -RefreshProjectorTrace -Json`
  with `Warnings = []`
- **Stop if:** Lane A changes artifact schema without updating the manifest flow
- **Commit when:** one full session package completes cleanly and consistency
  remains stable

### Lane C — Offline decode / diff analysis

- **Active:** build a diff helper for
  `C:\RIFT MODDING\RiftReader\scripts\captures\owner-state-neighborhood.json`
  across packaged sessions
- **Next:** compare
  `C:\RIFT MODDING\RiftReader\scripts\sessions\20260410-080938-combat-projector-clean`
  vs.
  `C:\RIFT MODDING\RiftReader\scripts\sessions\20260410-083213-state-neighborhood-breakthrough`
- **Validation:** diff output highlights changed offsets/strings/pointer targets
- **Stop if:** live schema changes invalidate stored field names
- **Commit when:** diff output is useful without manual cleanup

### Lane D — Archival research

- **Active:** idle
- **Next:** only activate if a discovered string like `OBJECTIVE6ITEMTAGSIGNAL`
  needs subsystem context
- **Validation:** findings link directly to a current live hypothesis
- **Stop if:** results are only historical trivia
- **Commit when:** a research brief changes active engineering priorities

## Forward-planning rules

- The coordinator always keeps **2 queued tasks per live lane**.
- Workers never choose their own follow-up from scratch.
- If a task finishes early, the worker immediately takes its queued **Next** task.
- If a new anchor or class label appears, the coordinator rewrites all queued
  tasks before assigning more work.

## Quota-aware checkpoint rules

- **Soft checkpoint:** commit after each validated lane-level improvement.
- **Hard checkpoint:** commit before:
  - a risky cross-lane edit
  - a likely context reset
  - a long browsing/research branch
  - token/quota pressure
- Prefer **small themed commits**:
  - `lane-a: owner-state pointer walker`
  - `lane-b: package owner-state artifact`
  - `lane-c: add neighborhood diff helper`

Do not wait for a “major milestone” if the current step is already green.

## When a worker must stop and hand back

- it needs to edit a file owned by another lane
- it finds a new canonical anchor or selected source
- validation fails twice without a clear local fix
- the task expands into schema design or repo-wide decisions
- it is about to cross the current commit boundary

## Integration rule

Only the top-level integrator:

- changes multiple lanes in one step
- resolves conflicting findings
- chooses commit boundaries
- rebases the rolling queue after breakthroughs

