<!--
Version: riftreader-status-static-root-null-overlay-docs-v0.1.0
Purpose: Document the status packet overlay that prevents proof-anchor-current/static-root-null states from looping back into proof-anchor recovery.
-->

# Status Static Root Null Overlay v0.1

## Purpose

This patch teaches `tools/riftreader_workflow/status_packet.py` to classify this state correctly:

```text
current proof anchor: current-target-proofonly-passed for live PID/HWND
current-truth/status artifact: stale historical PID/HWND
promoted static owner root: root-pointer-null
```

The correct workflow classification is:

```text
static-chain-repair-needed
```

not another proof-anchor recovery loop.

## Why this exists

On 2026-06-03 / 2026-06-04, proof-anchor recovery for live RIFT PID `77152` / HWND `0x17A0DB2` succeeded and was committed, but the old promoted static owner root:

```text
[rift_x64+0x32EBC80]
```

read as null in the current process epoch. Current-truth/navigation dashboard artifacts still referenced historical PID `12664`, causing the compact status packet to report a misleading stale-proof style next action.

## Safety

This patch changes classification and status text only.

It does not:

```text
send movement
send input
attach Cheat Engine
attach x64dbg
write target memory
promote proof
apply current truth
stage, commit, or push by itself
```

## Expected behavior

When all of these are true:

```text
current proof target matches a live RIFT PID
coordinate/status artifact points at an old PID
static owner coordinate chain verdict is root-pointer-null
```

the status packet should include:

```json
{
  "workflowClassification": {
    "classification": "static-chain-repair-needed",
    "blocker": "static-chain-repair-needed:root-pointer-null"
  }
}
```

and the next recommended action should tell the operator to repair the static pointer chain/root instead of rerunning proof-anchor recovery.

## Validation

Run:

```powershell
python -m py_compile tools\riftreader_workflow\status_packet.py scripts\test_status_packet_static_root_null_overlay.py
python -m unittest scripts.test_status_packet_static_root_null_overlay
.\scripts\riftreader-workflow-status.cmd --compact-json --write
git --no-pager diff --check
```

## END_OF_SCRIPT_MARKER
