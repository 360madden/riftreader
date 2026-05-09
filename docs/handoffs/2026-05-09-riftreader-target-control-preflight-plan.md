# RiftReader Target-Control Preflight Plan

Created: 2026-05-09
Repo: C:\RIFT MODDING\RiftReader
Branch: main
Scope: RiftReader workflow only
Status: planning / implementation-ready

## Purpose

RiftReader needs a reusable target-control preflight layer for the full live-testing workflow. This is broader than the current visual gate blocker. The immediate symptom is focus-window-not-foreground, but the real workflow gap is that ProofOnly, visual capture, screenshot validation, movement smoke tests, waypoint navigation, actor-yaw stimulus, and future auto-turn promotion all need a shared target-resolution and foreground-readiness contract.

RiftScan is only the reference model. This milestone must not modify RiftScan.

## Design principle

Acquire aggressively. Classify precisely. Allow or block based on workflow risk.

The system must not simply treat same-process foreground as a universal pass. Exact-HWND foreground, same-PID different-HWND foreground, and wrong-process foreground must remain distinct states.

## Phase 1 deliverable

Add a standalone RiftReader target-control preflight, not wired into movement yet.

Planned files:

- scripts/rift_live_test/target_control.py
- scripts/check_rift_target_control.py
- scripts/test_target_control.py

Phase 1 must send no game input. It must not move, turn, send yaw stimulus, send screenshot-key input, run slash commands, or run /reloadui.

## Target-control responsibilities

The target-control layer should resolve the requested RIFT target by PID, HWND, process name, and title constraint. It should verify that the process exists, verify that the requested HWND is still valid, verify visibility and minimized state, restore the window when appropriate, attempt foreground acquisition with Win32 APIs, retry with controlled timing, classify the final foreground state, and write durable JSON and Markdown artifacts.

The standard output directory should be under scripts/captures using a target-control-currentpid timestamped folder. The primary files should be target-control-status.json and target-control-status.md.

## Foreground acquisition strategy

Tier 1 should use safe Win32 restore and foreground request behavior: restore the window, request foreground, wait briefly, then verify the actual foreground window and foreground process.

Tier 2 should add stronger no-input Win32 foreground assistance when Tier 1 fails. The intended tools are BringWindowToTop and AttachThreadInput around the foreground request. This remains a no-input method. It must not click, type, move, turn, or trigger screenshots.

Tier 3 should be diagnostic only for the first implementation. Do not add topmost toggling, synthetic clicking, or keyboard tricks in the first milestone.

## Required foreground classifications

The new layer should classify focus into these states:

- exact-hwnd-foreground: requested target HWND is foreground. This is the strongest pass.
- same-pid-different-hwnd-foreground: a window from the same RIFT process is foreground, but it is not the requested HWND. This is a partial pass and warning state.
- target-visible-not-foreground: target exists and is visible, but foreground acquisition did not succeed.
- different-process-foreground: another process is foreground. This blocks live input.
- target-process-missing: PID no longer exists. This blocks all current-session testing.
- target-window-missing: requested HWND is invalid or stale. This blocks all current-session testing.
- target-window-minimized: target is minimized and could not be restored. This blocks live testing.
- foreground-not-acquired: all foreground attempts failed. This blocks live input.

## Capability policy

Target-control must expose workflow-specific readiness flags rather than a single generic pass.

Recommended capabilities:

- readOnlyProof: requires valid target process and window epoch.
- visualCapture: requires valid target, visible window, and target-control permission for capture.
- exactHwndInput: requires a valid target HWND. Exact foreground is preferred; same-PID different-HWND may be allowed only if downstream code explicitly accepts it.
- foregroundSendInput: requires exact-HWND foreground.
- yawStimulus: requires exact-HWND foreground, fresh ProofOnly, and passed visual gate.
- autoTurn: requires exact-HWND foreground, fresh ProofOnly, passed visual gate, and current-session promoted actor-facing truth.

## Integration phases

Phase 1: Add standalone target-control module, CLI wrapper, and tests. No movement, yaw, route execution, or auto-turn changes.

Phase 2: Integrate target-control into the visual gate. The visual gate should consume target-control first and proceed only when target-control says visual-gate work is permitted.

Phase 3: Integrate target-control into live_test.py and related profile runners. Profiles that may send input must record target-control status in their run summaries.

Phase 4: Integrate target-control into navigation and actor-yaw entrypoints. No route, movement, yaw, or turn stimulus should execute without a recorded target-control result.

## Test requirements

Unit tests should cover exact-HWND foreground, same-PID different-HWND foreground, different-process foreground, missing process, missing HWND, minimized target, Tier 1 success, Tier 2 success after Tier 1 failure, false success prevention when foreground is not actually acquired, foreground SendInput policy, and exact-HWND PostMessage policy.

## Validation sequence

Initial validation should be no-input only:

1. Run target-control unit tests.
2. Run visual-gate unit tests.
3. Run the target-control CLI against the current RIFT PID and HWND.
4. Run the visual gate only after target-control has a usable result.
5. Run fresh ProofOnly only after target-control and visual gate pass.

No movement, yaw, turn, screenshot-key input, or auto-turn should run during the first implementation milestone.

## Commit discipline

Use explicit staging only. Do not use git add dot.

Likely implementation paths:

- scripts/rift_live_test/target_control.py
- scripts/check_rift_target_control.py
- scripts/test_target_control.py
- scripts/rift_live_test/visual_gate_status.py
- scripts/test_visual_gate_status.py
- docs/recovery/current-truth.md
- docs/handoffs/new-target-control-handoff.md

## Milestone definition

Milestone name: RiftReader Target-Control Preflight.

Success condition: RiftReader can aggressively request foreground, classify exact-HWND versus same-PID foreground state, write target-control artifacts, and expose workflow-specific readiness flags without sending game input.

This milestone is foundational and should be completed before expanding live movement, yaw, actor-facing promotion, or auto-turn testing.
