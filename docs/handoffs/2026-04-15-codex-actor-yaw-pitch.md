---
state: active
as_of: 2026-04-19
---

# Actor-Facing Discovery Handoff (2026-04-19)

## Scope

This handoff freezes the current state of the **actor-facing discovery** branch
in:

- `C:\RIFT MODDING\RiftReader_facing`

The branch goal is now explicit:

- discover the **true live actor-facing carrier**
- prove it with **turn-left / turn-right / move-forward** evidence
- use **debug scanning + Cheat Engine + focused session capture** as the main
  discovery tools

This branch is **not** currently about generic post-update rebuild work, broad
offset maintenance, or expanding navigation behavior before facing is proven.

## Snapshot metadata

| Field | Value |
|---|---|
| State | `active` |
| As of | `2026-04-19` |
| Report date | `2026-04-19` |
| Branch | `facing` |
| Worktree | `C:\RIFT MODDING\RiftReader_facing` |
| Input mode | repo edits + live read-only process inspection + workflow planning |
| Validation status | partial |

## Current verdict

| Area | Result | Notes |
|---|---|---|
| Actor-facing truth | **not confirmed yet** | No source has been promoted to truth |
| Player coordinate reads | working | Current live player read and coord-anchor remain usable |
| Artifact selected-source address | stale | Historical selected-source address no longer reads live |
| Facing math / integrity logic | working offline | Shared analyzer/tests are already in place |
| Debug scanning posture | strong | This is now the preferred recovery/discovery path |
| Branch scope | corrected | Discovery-first; consumer/navigation work is secondary |

## Commands run this pass

```powershell
git -C C:\RIFT MODDING\RiftReader_facing branch --show-current
git -C C:\RIFT MODDING\RiftReader_facing status --short
dotnet test C:\RIFT MODDING\RiftReader_facing\reader\RiftReader.Reader.Tests\RiftReader.Reader.Tests.csproj
C:\RIFT MODDING\RiftReader_facing\reader\RiftReader.Reader\bin\Debug\net10.0-windows\RiftReader.Reader.exe --read-player-orientation --owner-components-file "C:\RIFT MODDING\RiftReader\scripts\captures\player-owner-components.json" --json
C:\RIFT MODDING\RiftReader_facing\reader\RiftReader.Reader\bin\Debug\net10.0-windows\RiftReader.Reader.exe --process-name rift_x64 --address 0x1FDA0D13170 --length 192 --json
```

## Validated findings from this pass

| Finding | Evidence | Why it matters |
|---|---|---|
| Tests passed after the parser/navigation changes | `dotnet test ...RiftReader.Reader.Tests.csproj` passed `25/25` | Current code changes are locally green |
| `--owner-components-file` was being dropped for general navigation modes | Fixed in `C:\RIFT MODDING\RiftReader_facing\reader\RiftReader.Reader\Cli\ReaderOptionsParser.cs` with parser tests added | This was blocking proper navigation-side use of owner-components artifacts |
| The artifact-side selected source is stale live | `SelectedSourceAddress = 0x1FDA0D13170` from `player-owner-components.json`, but direct live read failed with `ReadProcessMemory ... Win32 299` | The current blocker is **live source reacquisition**, not yaw math |
| Coordinates are not the blocker | Player-current and coord-anchor paths still work; known coord layouts remain usable | Actor-facing discovery should pivot from live coords outward |
| Debug scanning changes the workflow | We no longer need an offset-ledger mindset | Discovery should be invariant-driven and behavior-validated |

## Surviving anchors

| Area | Result | Notes |
|---|---|---|
| `--readerbridge-snapshot` baseline | working | Still the addon-backed coord freshness source |
| `--read-player-current` | working | Current coord read path survives |
| `--read-player-coord-anchor` | working | Still a useful bootstrap for family reacquire |
| Coord layouts | working / known | `+0x0/+0x4/+0x8`, historical anchor `+0x158/+0x15C/+0x160`, historical source-style `+0x48/+0x4C/+0x50` and `+0x88/+0x8C/+0x90` |
| Basis integrity logic | working | Existing actor-facing analyzer code/tests already cover the contract math |
| CE / debug scan workbench | working | Best live discriminator for candidate families |

## Broken or drifted anchors

| Area | Result | Notes |
|---|---|---|
| Source-chain / owner-components refresh | broken post-update | This is already reflected in `C:\RIFT MODDING\RiftReader_facing\docs\recovery\current-truth.md` |
| Artifact selected-source lineage | stale | Historical selected-source addresses cannot be trusted as live truth |
| Navigation-facing live summary | incomplete | It can only populate once a fresh facing source is reacquired |
| Actor-facing authority | candidate-only | The selected-source basis remains an incumbent candidate, not confirmed truth |

## Files touched in the current worktree

These are the actor-facing-adjacent reader changes currently present in the
worktree and should be treated as **existing context**, not as proof that
actor-facing is solved:

| File | Reason |
|---|---|
| `C:\RIFT MODDING\RiftReader_facing\reader\RiftReader.Reader\Navigation\NavigationFacingSource.cs` | Added live navigation-facing reader using selected-source-style basis logic |
| `C:\RIFT MODDING\RiftReader_facing\reader\RiftReader.Reader\Program.cs` | Wires facing into navigation reads/runs |
| `C:\RIFT MODDING\RiftReader_facing\reader\RiftReader.Reader\Cli\ReaderOptionsParser.cs` | Fixed `--owner-components-file` passthrough for navigation modes |
| `C:\RIFT MODDING\RiftReader_facing\reader\RiftReader.Reader\Navigation\WaypointNavigator.cs` | Added optional facing-aware turn alignment support |
| `C:\RIFT MODDING\RiftReader_facing\reader\RiftReader.Reader.Tests\Cli\ReaderOptionsParserTests.cs` | Added regression coverage for owner-components passthrough |
| `C:\RIFT MODDING\RiftReader_facing\reader\RiftReader.Reader.Tests\Navigation\WaypointNavigationTests.cs` | Added facing/turn-related navigation tests |

There are also unrelated or pre-existing local doc/script changes already in the
worktree:

- `C:\RIFT MODDING\RiftReader_facing\README.md`
- `C:\RIFT MODDING\RiftReader_facing\docs\actor-facing-discovery.md`
- `C:\RIFT MODDING\RiftReader_facing\docs\addon-validation-spec.md`
- `C:\RIFT MODDING\RiftReader_facing\docs\analysis\2026-04-16-actor-facing-passive-baseline.md`
- `C:\RIFT MODDING\RiftReader_facing\scripts\analyze-actor-facing-passive.cmd`
- `C:\RIFT MODDING\RiftReader_facing\scripts\analyze-actor-facing-passive.ps1`

Do not assume all modified files belong to one clean patch.

## Workflow authority for the next conversation

Use these documents first:

- `C:\RIFT MODDING\RiftReader_facing\docs\actor-facing-discovery.md`
- `C:\RIFT MODDING\RiftReader_facing\docs\cheat-engine-workflow.md`
- `C:\RIFT MODDING\RiftReader_facing\docs\agentic-workflow.md`
- `C:\RIFT MODDING\RiftReader_facing\docs\recovery\current-truth.md`

Use these tools first:

- `C:\RIFT MODDING\RiftReader_facing\scripts\capture-player-trace-cluster.ps1`
- `C:\RIFT MODDING\RiftReader_facing\scripts\capture-owner-state-neighborhood.ps1`
- `C:\RIFT MODDING\RiftReader_facing\scripts\capture-ce-family-neighborhood.ps1`
- `C:\RIFT MODDING\RiftReader_facing\scripts\generate-cheatengine-probe.cmd`
- `C:\RIFT MODDING\RiftReader_facing\scripts\test-actor-facing-validation.ps1`
- `C:\RIFT MODDING\RiftReader_facing\scripts\build-navigation-facing-contract.ps1`

## What the next agent should do

| Step | Action | Why |
|---|---|---|
| 1 | Reacquire the live source/transform family from the surviving coord anchor | This is the real blocker |
| 2 | Keep the candidate set narrow: coord match, source-style duplicate coords, basis-like blocks, owner/source adjacency | Faster and less noisy than broad scans |
| 3 | Validate `idle`, `turn-left`, and `turn-right` before `move-forward` | Turn response is the cleanest discriminator |
| 4 | Run repeated forward-heading validation only on the top surviving candidate | Avoid wasting live validation on junk candidates |
| 5 | Promote a source only if `C:\RIFT MODDING\RiftReader_facing\scripts\build-navigation-facing-contract.ps1` emits `confirmed` | Prevents stale folklore from becoming truth |

## Anti-drift rules

| Do | Do not |
|---|---|
| Treat offsets as temporary outputs | Rebuild a giant offset ledger |
| Use debug scanning and CE as focused discovery tools | Start with broad unbounded memory search |
| Classify failure shapes before widening | Retry the same stale source path repeatedly |
| Keep branch scope on actor-facing proof | Expand navigation/consumer work first |
| Require live evidence before promotion | Trust old owner/source artifacts as current truth |

## Recommended first action in the next conversation

- Reacquire the live selected-source / transform family from the working coord anchor with `C:\RIFT MODDING\RiftReader_facing\scripts\capture-player-trace-cluster.ps1` plus `C:\RIFT MODDING\RiftReader_facing\scripts\capture-owner-state-neighborhood.ps1`, then run turn-response validation on the top basis-like candidate before doing any more navigation work.
- If the incumbent selected-source basis cannot be reacquired quickly, switch immediately to `C:\RIFT MODDING\RiftReader_facing\scripts\capture-ce-family-neighborhood.ps1` plus the Cheat Engine probe to watch live candidate families during manual turn stimuli.
- Keep the first successful proof package small: baseline, idle, turn-left, turn-right, repeated forward.

## Practical next improvements after handoff

1. Align `C:\RIFT MODDING\RiftReader_facing\docs\actor-facing-discovery.md` with the new live-reacquire-first workflow.
2. Add a tiny actor-facing-specific workboard file if dashboard readiness matters for this branch.
3. Persist the top reacquired candidate family as a fresh per-build artifact only after live validation succeeds.
