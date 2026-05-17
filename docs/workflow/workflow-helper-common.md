# RiftReader workflow helper common module

## Purpose

`tools/riftreader_workflow/common.py` is the shared offline-safe utility layer
for RiftReader local workflow helpers. It keeps repeated helper behavior
consistent without merging the workflow into one large operator app.

## Current shared primitives

| Primitive | Purpose |
|---|---|
| `utc_iso()` | UTC timestamp for JSON summaries. |
| `utc_stamp()` | Filesystem-safe UTC timestamp for artifact folders. |
| `find_repo_root()` | Locate the RiftReader repo root from a child path. |
| `repo_rel()` | Render repo-relative Windows-style paths for summaries. |
| `unique()` | Preserve first-seen order while removing duplicates. |
| `preview_text()` | Bound command stdout/stderr previews. |
| `safety_flags()` | Standard fail-closed no-movement/no-input/no-Git/no-debugger flags. |
| `timestamped_output_dir()` | Create collision-safe ignored artifact directories. |

## Safety contract

The common module must remain deterministic and offline-safe:

- no live input;
- no movement;
- no CE/x64dbg attach;
- no provider writes;
- no Git staging, committing, pushing, resetting, or cleaning;
- no secrets/config dumps;
- no background service or watcher behavior.

## Current consumers

| File | Shared behavior consumed |
|---|---|
| `tools/riftreader_workflow/status_packet.py` | Repo root, timestamps, output dirs, path rendering, previews, safety flags. |
| `tools/riftreader_workflow/apply_package.py` | Timestamps, output dirs, path rendering, safety flags. |
| `tools/riftreader_workflow/live_test_triage.py` | Timestamps, output dirs, path rendering, safety flags. |
| `tools/riftreader_workflow/operator_lite.py` | Repo root, timestamps, safety flags. |

## Extension rule

Add only small, reusable primitives here. If a function starts making workflow
decisions, running commands, or owning a state machine, keep it in a dedicated
module such as `status_packet.py`, `apply_package.py`, or a future
`validation.py`.
