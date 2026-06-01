#!/usr/bin/env python3
"""Classify visual camera change versus static-owner yaw/facing memory change.

This helper is candidate-only discovery evidence.  It captures a visual frame,
static-owner snapshots/nav-state, sends one approved exact-target mouse-look
stimulus, captures the same evidence again, then summarizes whether the visual
frame, static yaw candidate, and owner-window fields changed together.

It does not promote facing/turn-rate/proof, attach debuggers, use Cheat Engine,
write provider repos, write target memory, or mutate Git.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
import tempfile
from ctypes import wintypes
from pathlib import Path
from typing import Any, Mapping

from workflow_common import (
    base_safety,
    full_summary_from_compact,
    load_json_object,
    repo_root,
    run_child,
    safe_mapping,
    utc_iso,
    utc_stamp,
    write_json,
)
from static_owner_mouse_turn_probe import (
    SW_RESTORE,
    foreground_info,
    get_user32,
    hwnd_to_hex,
    parse_hwnd,
    perform_mouse_turn,
    process_id_for_hwnd,
    target_from_summary,
)


SCHEMA_VERSION = 1
DEFAULT_CURRENT_TRUTH_JSON = "docs/recovery/current-truth.json"
FOCUS_OFFSETS = (0x300, 0x304, 0x308, 0x30C, 0x310, 0x314, 0x318, 0x31C, 0x320, 0x324, 0x328, 0x408)


def json_text(value: Mapping[str, Any]) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def safe_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def rel(root: Path, path: str | Path | None) -> str | None:
    if path is None:
        return None
    candidate = Path(str(path))
    try:
        return str(candidate.resolve().relative_to(root.resolve()))
    except Exception:  # noqa: BLE001 - artifact rendering should never fail the helper.
        return str(candidate)


def signed_angle_delta(before: float | None, after: float | None) -> float | None:
    if before is None or after is None:
        return None
    return ((float(after) - float(before) + 180.0) % 360.0) - 180.0


def float_by_offset(snapshot: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    result: dict[int, Mapping[str, Any]] = {}
    samples = snapshot.get("floatSamples", [])
    if not isinstance(samples, list):
        return result
    for item in samples:
        if not isinstance(item, Mapping):
            continue
        try:
            offset = int(str(item.get("offset")), 0)
        except Exception:  # noqa: BLE001
            continue
        result[offset] = item
    return result


def focus_offset_deltas(before: Mapping[str, Any], after: Mapping[str, Any]) -> list[dict[str, Any]]:
    before_map = float_by_offset(before)
    after_map = float_by_offset(after)
    rows: list[dict[str, Any]] = []
    for offset in FOCUS_OFFSETS:
        before_item = before_map.get(offset)
        after_item = after_map.get(offset)
        before_value = before_item.get("value") if before_item else None
        after_value = after_item.get("value") if after_item else None
        delta = None
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            delta = float(after_value) - float(before_value)
        rows.append(
            {
                "offset": f"0x{offset:X}",
                "before": before_value,
                "after": after_value,
                "delta": delta,
                "absDelta": abs(delta) if delta is not None else None,
                "addressBefore": before_item.get("address") if before_item else None,
                "addressAfter": after_item.get("address") if after_item else None,
            }
        )
    return rows


def nav_latest_state(full_state_summary: Mapping[str, Any]) -> dict[str, Any]:
    latest = safe_mapping(full_state_summary.get("latestState"))
    if latest:
        return latest
    # Compact state output can already be the latest state.
    return dict(full_state_summary)


def compact_capture_artifact(capture_summary: Mapping[str, Any]) -> dict[str, Any]:
    tool = safe_mapping(capture_summary.get("toolReport"))
    quality = safe_mapping(tool.get("quality"))
    return {
        "output": tool.get("output"),
        "rawOutput": quality.get("rawOutput"),
        "rawMetadata": quality.get("rawMetadata"),
        "manifest": tool.get("manifest"),
        "controllerSummary": safe_mapping(capture_summary.get("artifacts")).get("summaryJson"),
        "usable": tool.get("usable"),
        "method": tool.get("captureMethod"),
        "width": tool.get("width"),
        "height": tool.get("height"),
    }


def visual_foreground_capture_gate(
    *,
    target: Mapping[str, Any],
    capture_summary: Mapping[str, Any],
    focus_delay_milliseconds: int,
) -> dict[str, Any]:
    """Fail closed unless the visual capture and foreground target match the exact Rift HWND.

    This is intentionally a pre-input guard for live helpers.  The capture tool
    proves the captured visual artifact is tied to the expected window identity;
    the foreground check catches screen/top-layer mismatches where a different
    application would receive raw input.
    """

    blockers: list[str] = []
    warnings: list[str] = []
    details: dict[str, Any] = {}
    expected_pid = int(target.get("processId") or 0)
    expected_hwnd = hwnd_to_hex(target.get("targetWindowHandle"))
    tool = safe_mapping(capture_summary.get("toolReport"))
    details["capture"] = {
        "usable": tool.get("usable"),
        "windowPid": tool.get("windowPid"),
        "hwnd": tool.get("hwnd"),
        "windowTitle": tool.get("windowTitle"),
        "captureMethod": tool.get("captureMethod"),
        "output": tool.get("output"),
    }
    if tool.get("usable") is not True:
        blockers.append("visual-capture-not-usable")
    if str(tool.get("windowPid")) != str(expected_pid):
        blockers.append(f"visual-capture-pid-mismatch:{tool.get('windowPid')}!={expected_pid}")
    if str(tool.get("windowProcessName") or "").lower() != "rift_x64":
        blockers.append(f"visual-capture-process-mismatch:{tool.get('windowProcessName')}")
    captured_hwnd = tool.get("hwnd")
    if not captured_hwnd:
        blockers.append("visual-capture-hwnd-missing")
    elif hwnd_to_hex(captured_hwnd) != expected_hwnd:
        blockers.append(f"visual-capture-hwnd-mismatch:{captured_hwnd}!={expected_hwnd}")
    if str(tool.get("windowTitle") or "") != "RIFT":
        warnings.append(f"visual-capture-title-not-exact-rift:{tool.get('windowTitle')}")

    try:
        user32 = get_user32()
        hwnd = parse_hwnd(expected_hwnd)
        details["foregroundBeforeGate"] = foreground_info(user32)
        if not user32.IsWindow(wintypes.HWND(hwnd)):
            blockers.append("visual-gate-target-window-not-found")
        else:
            actual_pid = process_id_for_hwnd(user32, hwnd)
            details["targetWindowProcessId"] = actual_pid
            if actual_pid != expected_pid:
                blockers.append(f"visual-gate-target-pid-mismatch:{actual_pid}!={expected_pid}")
            user32.ShowWindow(wintypes.HWND(hwnd), SW_RESTORE)
            user32.BringWindowToTop(wintypes.HWND(hwnd))
            user32.SetForegroundWindow(wintypes.HWND(hwnd))
            if focus_delay_milliseconds:
                time.sleep(focus_delay_milliseconds / 1000.0)
            details["foregroundAfterGate"] = foreground_info(user32)
            foreground = safe_mapping(details["foregroundAfterGate"])
            if foreground.get("processId") != expected_pid:
                blockers.append(f"visual-gate-target-not-foreground:{foreground.get('processId')}!={expected_pid}")
            elif parse_hwnd(foreground.get("hwnd")) != hwnd:
                blockers.append(f"visual-gate-target-not-exact-foreground-window:{foreground.get('hwnd')}!={expected_hwnd}")
    except Exception as exc:  # noqa: BLE001 - gate must report and fail closed.
        blockers.append(f"visual-foreground-gate-error:{type(exc).__name__}:{exc}")

    return {
        "status": "passed" if not blockers else "blocked",
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "details": details,
    }


def raw_visual_diff(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    before_raw = before.get("rawOutput")
    after_raw = after.get("rawOutput")
    if not before_raw or not after_raw:
        return {"status": "unavailable", "reason": "raw-output-missing"}
    before_path = Path(str(before_raw))
    after_path = Path(str(after_raw))
    if not before_path.is_file() or not after_path.is_file():
        return {"status": "unavailable", "reason": "raw-output-not-found"}
    before_bytes = before_path.read_bytes()
    after_bytes = after_path.read_bytes()
    if len(before_bytes) != len(after_bytes):
        return {
            "status": "changed",
            "reason": "raw-size-mismatch",
            "beforeBytes": len(before_bytes),
            "afterBytes": len(after_bytes),
        }
    if len(before_bytes) % 4 != 0:
        changed_bytes = sum(1 for left, right in zip(before_bytes, after_bytes, strict=True) if left != right)
        return {
            "status": "changed" if changed_bytes else "unchanged",
            "changedByteCount": changed_bytes,
            "totalBytes": len(before_bytes),
            "changedByteRatio": changed_bytes / max(1, len(before_bytes)),
        }
    changed_pixels = 0
    for index in range(0, len(before_bytes), 4):
        if before_bytes[index : index + 4] != after_bytes[index : index + 4]:
            changed_pixels += 1
    total_pixels = len(before_bytes) // 4
    ratio = changed_pixels / max(1, total_pixels)
    return {
        "status": "changed" if changed_pixels else "unchanged",
        "changedPixelCount": changed_pixels,
        "totalPixelCount": total_pixels,
        "changedPixelRatio": ratio,
        "changedPercent": ratio * 100.0,
    }


def build_capture_command(
    *,
    root: Path,
    output_root: Path,
    target: Mapping[str, Any],
    timeout_seconds: int,
) -> list[str]:
    command = [
        sys.executable,
        str(root / "scripts" / "capture_rift_window.py"),
        "capture",
        "--no-build",
        "--timeout-seconds",
        str(timeout_seconds),
        "--output-root",
        str(output_root),
        "--pid",
        str(target.get("processId")),
        "--hwnd",
        str(target.get("targetWindowHandle")),
        "--emit-png",
        "--emit-raw-bgra",
        "--require-usable",
        "--json",
    ]
    process_start = target.get("processStartUtc")
    if process_start:
        command.extend(["--expected-process-start-utc", str(process_start)])
    return command


def build_snapshot_command(*, root: Path, output_root: Path, label: str, owner_window_bytes: int) -> list[str]:
    return [
        sys.executable,
        str(root / "scripts" / "static_owner_facing_discovery.py"),
        "snapshot",
        "--output-root",
        str(output_root),
        "--label",
        label,
        "--owner-window-bytes",
        hex(owner_window_bytes),
        "--json",
    ]


def build_state_command(*, root: Path, output_root: Path, samples: int, interval_seconds: float) -> list[str]:
    return [
        sys.executable,
        str(root / "scripts" / "static_owner_facing_discovery.py"),
        "state",
        "--output-root",
        str(output_root),
        "--samples",
        str(samples),
        "--interval-seconds",
        str(interval_seconds),
        "--expect-stationary",
        "--json",
    ]


def build_compare_command(*, root: Path, output_root: Path, before_json: str, after_json: str) -> list[str]:
    return [
        sys.executable,
        str(root / "scripts" / "static_owner_facing_discovery.py"),
        "compare",
        "--output-root",
        str(output_root),
        "--snapshot-json",
        before_json,
        after_json,
        "--min-yaw-delta-degrees",
        "0.01",
        "--json",
    ]


def build_pointer_command(*, root: Path, output_root: Path, snapshot: Mapping[str, Any], target: Mapping[str, Any]) -> list[str]:
    owner = safe_mapping(snapshot.get("owner"))
    owner_address = owner.get("ownerAddress")
    target_address = None
    try:
        target_address = f"0x{int(str(owner_address), 0) + 0x30C:X}" if owner_address else None
    except Exception:  # noqa: BLE001
        target_address = None
    command = [
        sys.executable,
        str(root / "scripts" / "pointer_owner_neighborhood_inspector.py"),
        "--output-root",
        str(output_root),
        "--owner-window-bytes",
        "0x700",
        "--near-target-bytes",
        "0x80",
        "--json",
    ]
    if target.get("processId"):
        command.extend(["--pid", str(target.get("processId"))])
    if target.get("targetWindowHandle"):
        command.extend(["--hwnd", str(target.get("targetWindowHandle"))])
    if owner_address:
        command.extend(["--owner-address", str(owner_address)])
    if target_address:
        command.extend(["--target-address", target_address])
    return command


def self_test_summary() -> dict[str, Any]:
    before = {
        "floatSamples": [
            {"offset": "0x304", "value": 0.1},
            {"offset": "0x30C", "value": 10.0},
            {"offset": "0x314", "value": 20.0},
        ]
    }
    after = {
        "floatSamples": [
            {"offset": "0x304", "value": -0.2},
            {"offset": "0x30C", "value": 11.5},
            {"offset": "0x314", "value": 19.25},
        ]
    }
    deltas = focus_offset_deltas(before, after)
    checks = [
        {"name": "signed-angle-wrap", "passed": math.isclose(signed_angle_delta(350.0, 10.0) or 0.0, 20.0)},
        {"name": "focus-offsets-built", "passed": len(deltas) == len(FOCUS_OFFSETS)},
        {
            "name": "candidate-facing-offset-delta-detected",
            "passed": any(row["offset"] == "0x30C" and row["delta"] == 1.5 for row in deltas),
        },
    ]
    passed = all(bool(item["passed"]) for item in checks)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "static-owner-camera-yaw-classification-self-test",
        "generatedAtUtc": utc_iso(),
        "status": "passed" if passed else "failed",
        "verdict": "self-test-passed" if passed else "self-test-failed",
        "checks": checks,
        "blockers": [],
        "warnings": [],
        "errors": [] if passed else ["self-test-check-failed"],
        "safety": {**base_safety(), "targetMemoryBytesRead": False, "targetMemoryBytesWritten": False},
        "artifacts": {},
    }


def aggregate_camera_yaw_summaries(args: argparse.Namespace, root: Path, run_dir: Path) -> tuple[dict[str, Any], int]:
    """Build a report-only multi-pose summary from existing classification runs."""

    source_paths = [Path(str(item)) for item in args.aggregate_summary_json or []]
    resolved_paths = [path if path.is_absolute() else root / path for path in source_paths]
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "static-owner-camera-yaw-multipose-report",
        "generatedAtUtc": utc_iso(),
        "status": "failed",
        "verdict": "multipose-report-not-built",
        "repoRoot": str(root),
        "runDirectory": str(run_dir),
        "sourceCount": len(resolved_paths),
        "poses": [],
        "offsetAggregate": {},
        "analysis": {},
        "blockers": [],
        "warnings": ["report-only-no-input-sent"],
        "errors": [],
        "safety": {
            **base_safety(),
            "reportOnly": True,
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
        },
        "sourceSafety": {
            "inputSent": False,
            "movementSent": False,
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
        },
        "artifacts": {
            "summaryJson": str(run_dir / "summary.json"),
            "summaryMarkdown": str(run_dir / "summary.md"),
        },
        "next": {
            "recommendedAction": (
                "Add left/right/return classification summaries, then compare owner+0x300/+0x304 "
                "directionality before any turn-dependent route."
            )
        },
    }

    if not resolved_paths:
        summary["status"] = "blocked"
        summary["verdict"] = "classification-summary-paths-required"
        summary["blockers"].append("aggregate-summary-json-required")
        return summary, 2

    offset_rows: dict[str, list[dict[str, Any]]] = {}
    route_actionable_count = 0
    visual_changed_static_unchanged_count = 0
    classifications: dict[str, int] = {}

    try:
        for path in resolved_paths:
            if not path.is_file():
                summary["blockers"].append(f"classification-summary-not-found:{path}")
                continue
            data = load_json_object(path)
            if data.get("kind") != "static-owner-camera-yaw-classification":
                summary["warnings"].append(f"unexpected-summary-kind:{path}:{data.get('kind')}")
            analysis = safe_mapping(data.get("analysis"))
            stimulus = safe_mapping(data.get("stimulus"))
            visual = safe_mapping(data.get("visualEvidence"))
            raw_diff = safe_mapping(visual.get("rawDiff"))
            source_safety = safe_mapping(data.get("safety"))
            summary["sourceSafety"]["inputSent"] = bool(summary["sourceSafety"]["inputSent"]) or bool(source_safety.get("inputSent"))
            summary["sourceSafety"]["movementSent"] = bool(summary["sourceSafety"]["movementSent"]) or bool(source_safety.get("movementSent"))
            summary["sourceSafety"]["targetMemoryBytesRead"] = bool(summary["sourceSafety"]["targetMemoryBytesRead"]) or bool(
                source_safety.get("targetMemoryBytesRead")
            )
            summary["sourceSafety"]["targetMemoryBytesWritten"] = bool(summary["sourceSafety"]["targetMemoryBytesWritten"]) or bool(
                source_safety.get("targetMemoryBytesWritten")
            )

            classification = str(analysis.get("classification") or data.get("verdict") or "unknown")
            classifications[classification] = classifications.get(classification, 0) + 1
            actionable = analysis.get("actionableForRouteControl") is True
            if actionable:
                route_actionable_count += 1
            if classification == "visual-changed-static-yaw-unchanged":
                visual_changed_static_unchanged_count += 1

            changed_offsets = []
            for item in safe_list(analysis.get("changedFocusOffsets")):
                row = safe_mapping(item)
                offset = str(row.get("offset") or "")
                if offset:
                    offset_rows.setdefault(offset, []).append(
                        {
                            "summaryJson": str(path),
                            "direction": stimulus.get("direction"),
                            "pixels": stimulus.get("pixels"),
                            "delta": row.get("delta"),
                            "absDelta": row.get("absDelta"),
                            "before": row.get("before"),
                            "after": row.get("after"),
                        }
                    )
                changed_offsets.append(
                    {
                        "offset": row.get("offset"),
                        "delta": row.get("delta"),
                        "absDelta": row.get("absDelta"),
                    }
                )

            summary["poses"].append(
                {
                    "summaryJson": str(path),
                    "generatedAtUtc": data.get("generatedAtUtc"),
                    "status": data.get("status"),
                    "verdict": data.get("verdict"),
                    "stimulus": {
                        "type": stimulus.get("type"),
                        "direction": stimulus.get("direction"),
                        "pixels": stimulus.get("pixels"),
                        "approved": bool(stimulus.get("approved")),
                    },
                    "classification": classification,
                    "visualChanged": analysis.get("visualChanged"),
                    "staticYawChanged": analysis.get("staticYawChanged"),
                    "actionableForRouteControl": actionable,
                    "signedYawDeltaDegrees": analysis.get("signedYawDeltaDegrees"),
                    "absoluteYawDeltaDegrees": analysis.get("absoluteYawDeltaDegrees"),
                    "visualRawDiff": {
                        "status": raw_diff.get("status"),
                        "changedPercent": raw_diff.get("changedPercent"),
                    },
                    "changedFocusOffsets": changed_offsets,
                }
            )

        if summary["blockers"]:
            summary["status"] = "blocked"
            summary["verdict"] = "multipose-report-blocked"
            return summary, 2

        offset_aggregate: dict[str, Any] = {}
        for offset, rows in sorted(offset_rows.items()):
            numeric_deltas = [float(row["delta"]) for row in rows if isinstance(row.get("delta"), (int, float))]
            directions = sorted({str(row.get("direction")) for row in rows if row.get("direction")})
            offset_aggregate[offset] = {
                "sampleCount": len(rows),
                "directions": directions,
                "minDelta": min(numeric_deltas) if numeric_deltas else None,
                "maxDelta": max(numeric_deltas) if numeric_deltas else None,
                "maxAbsDelta": max((abs(delta) for delta in numeric_deltas), default=None),
                "samples": rows[:10],
            }

        summary["offsetAggregate"] = offset_aggregate
        summary["analysis"] = {
            "classificationCounts": classifications,
            "routeActionablePoseCount": route_actionable_count,
            "visualChangedStaticYawUnchangedCount": visual_changed_static_unchanged_count,
            "changedOffsetCount": len(offset_aggregate),
            "candidateOnly": True,
            "promotionAllowed": False,
            "actionableForRouteControl": route_actionable_count > 0,
        }
        summary["warnings"].append("candidate-only-multipose-report-no-promotion")
        if route_actionable_count:
            summary["verdict"] = "route-actionable-candidate-present-needs-proof"
            if route_actionable_count >= 2:
                summary["next"]["recommendedAction"] = (
                    "Package the route-forward passes into a formal three-pose gate and preserve this aggregate "
                    "as candidate-only camera/yaw evidence before any promotion review."
                )
            else:
                summary["next"]["recommendedAction"] = (
                    "Rerun a bounded proof pack for the route-actionable candidate before any turn-dependent route movement."
                )
        elif visual_changed_static_unchanged_count:
            summary["verdict"] = "visual-changed-static-yaw-unchanged-across-poses"
        else:
            summary["verdict"] = "multipose-report-built"
        summary["status"] = "passed"
        return summary, 0
    except Exception as exc:  # noqa: BLE001
        summary["status"] = "failed"
        summary["verdict"] = "multipose-report-error"
        summary["errors"].append(f"{type(exc).__name__}:{exc}")
        return summary, 1


def dry_run_summary(args: argparse.Namespace, root: Path, run_dir: Path) -> dict[str, Any]:
    truth = load_json_object(root / args.current_truth_json)
    target = safe_mapping(truth.get("target"))
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "static-owner-camera-yaw-classification",
        "generatedAtUtc": utc_iso(),
        "status": "passed",
        "verdict": "dry-run-plan-built",
        "repoRoot": str(root),
        "runDirectory": str(run_dir),
        "target": target,
        "stimulus": {
            "type": "mouse-look",
            "direction": args.direction,
            "pixels": args.pixels,
            "steps": args.steps,
            "holdMilliseconds": args.hold_milliseconds,
            "approved": False,
        },
        "commandPlan": {
            "baselineCapture": build_capture_command(root=root, output_root=run_dir / "visual-baseline", target=target, timeout_seconds=args.timeout_seconds),
            "baselineSnapshot": build_snapshot_command(root=root, output_root=run_dir, label="camera-yaw-baseline", owner_window_bytes=args.owner_window_bytes),
            "postCapture": build_capture_command(root=root, output_root=run_dir / "visual-post", target=target, timeout_seconds=args.timeout_seconds),
        },
        "blockers": [],
        "warnings": ["dry-run-only-no-input-sent"],
        "errors": [],
        "safety": {**base_safety(), "dryRunOnly": True, "targetMemoryBytesRead": False, "targetMemoryBytesWritten": False},
        "artifacts": {},
        "next": {"recommendedAction": "Review the command plan, then rerun with --stimulus-approved for live classification."},
    }


def run_classification(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    if args.self_test:
        return self_test_summary(), 0

    output_root = Path(args.output_root) if args.output_root else root / "scripts" / "captures"
    if not output_root.is_absolute():
        output_root = root / output_root
    run_prefix = "static-owner-camera-yaw-multipose-report" if args.aggregate_summary_json else "static-owner-camera-yaw-classification"
    run_dir = output_root / f"{run_prefix}-{utc_stamp()}"
    child_dir = run_dir / "child-outputs"
    run_dir.mkdir(parents=True, exist_ok=False)

    if args.aggregate_summary_json:
        return aggregate_camera_yaw_summaries(args, root, run_dir)

    if args.dry_run:
        summary = dry_run_summary(args, root, run_dir)
        return summary, 0

    safety = {**base_safety(), "targetMemoryBytesRead": True, "targetMemoryBytesWritten": False, "routeMovementSent": False}
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "static-owner-camera-yaw-classification",
        "generatedAtUtc": utc_iso(),
        "status": "failed",
        "verdict": "classification-not-finished",
        "repoRoot": str(root),
        "runDirectory": str(run_dir),
        "target": {},
        "stimulus": {
            "type": "mouse-look",
            "direction": args.direction,
            "pixels": args.pixels,
            "steps": args.steps,
            "holdMilliseconds": args.hold_milliseconds,
            "approved": bool(args.stimulus_approved),
        },
        "commands": [],
        "visualEvidence": {},
        "visualPreflightGate": {},
        "snapshotEvidence": {},
        "analysis": {},
        "blockers": [],
        "warnings": [],
        "errors": [],
        "safety": safety,
        "artifacts": {
            "summaryJson": str(run_dir / "summary.json"),
            "summaryMarkdown": str(run_dir / "summary.md"),
        },
        "next": {"recommendedAction": "Inspect analysis.focusOffsetDeltas and comparison artifacts before any turn-dependent route."},
    }

    if not args.stimulus_approved:
        summary["status"] = "blocked"
        summary["verdict"] = "stimulus-approval-required"
        summary["blockers"].append("stimulus-approved-flag-required")
        return summary, 2

    try:
        truth = load_json_object(root / args.current_truth_json)
        truth_target = safe_mapping(truth.get("target"))
        summary["target"] = truth_target

        baseline_capture = run_child(
            label="visual-baseline-capture",
            command=build_capture_command(root=root, output_root=run_dir / "visual-baseline", target=truth_target, timeout_seconds=args.timeout_seconds),
            cwd=root,
            child_dir=child_dir,
            timeout_seconds=args.timeout_seconds + 15,
        )
        summary["commands"].append(baseline_capture)
        if not baseline_capture["ok"]:
            raise RuntimeError("visual-baseline-capture-failed")
        baseline_capture_json = safe_mapping(baseline_capture.get("json"))
        baseline_visual = compact_capture_artifact(baseline_capture_json)
        visual_gate = visual_foreground_capture_gate(
            target=truth_target,
            capture_summary=baseline_capture_json,
            focus_delay_milliseconds=args.focus_delay_milliseconds,
        )
        summary["visualPreflightGate"] = visual_gate
        summary["warnings"].extend(str(item) for item in visual_gate.get("warnings", []))
        if visual_gate.get("status") != "passed":
            summary["blockers"].extend(str(item) for item in visual_gate.get("blockers", []))
            raise RuntimeError("visual-foreground-capture-gate-failed")

        baseline_snapshot_cmd = run_child(
            label="snapshot-baseline",
            command=build_snapshot_command(root=root, output_root=run_dir, label="camera-yaw-baseline", owner_window_bytes=args.owner_window_bytes),
            cwd=root,
            child_dir=child_dir,
            timeout_seconds=args.timeout_seconds,
        )
        summary["commands"].append(baseline_snapshot_cmd)
        if not baseline_snapshot_cmd["ok"] or not isinstance(baseline_snapshot_cmd.get("json"), Mapping):
            raise RuntimeError("baseline-snapshot-failed")
        baseline_snapshot = full_summary_from_compact(safe_mapping(baseline_snapshot_cmd.get("json")))

        baseline_state_cmd = run_child(
            label="state-baseline",
            command=build_state_command(root=root, output_root=run_dir, samples=args.samples, interval_seconds=args.interval_seconds),
            cwd=root,
            child_dir=child_dir,
            timeout_seconds=args.timeout_seconds,
        )
        summary["commands"].append(baseline_state_cmd)
        if not baseline_state_cmd["ok"] or not isinstance(baseline_state_cmd.get("json"), Mapping):
            raise RuntimeError("baseline-state-failed")
        baseline_state = full_summary_from_compact(safe_mapping(baseline_state_cmd.get("json")))

        target = target_from_summary(baseline_snapshot)
        mouse = perform_mouse_turn(
            label="mouse-look-stimulus",
            child_dir=child_dir,
            target=target,
            direction=args.direction,
            pixels=args.pixels,
            steps=args.steps,
            hold_milliseconds=args.hold_milliseconds,
            focus_delay_milliseconds=args.focus_delay_milliseconds,
            require_foreground=True,
        )
        summary["commands"].append(mouse)
        safety["inputSent"] = True
        safety["movementSent"] = True
        if not mouse.get("ok"):
            summary["blockers"].extend(str(item) for item in mouse.get("blockers", []))
            summary["errors"].extend(str(item) for item in mouse.get("errors", []))
            raise RuntimeError("mouse-look-stimulus-failed")

        if args.post_input_wait_milliseconds:
            time.sleep(args.post_input_wait_milliseconds / 1000.0)

        post_capture = run_child(
            label="visual-post-capture",
            command=build_capture_command(root=root, output_root=run_dir / "visual-post", target=truth_target, timeout_seconds=args.timeout_seconds),
            cwd=root,
            child_dir=child_dir,
            timeout_seconds=args.timeout_seconds + 15,
        )
        summary["commands"].append(post_capture)
        if not post_capture["ok"]:
            raise RuntimeError("visual-post-capture-failed")
        post_capture_json = safe_mapping(post_capture.get("json"))
        post_visual = compact_capture_artifact(post_capture_json)

        post_snapshot_cmd = run_child(
            label="snapshot-post",
            command=build_snapshot_command(root=root, output_root=run_dir, label="camera-yaw-post", owner_window_bytes=args.owner_window_bytes),
            cwd=root,
            child_dir=child_dir,
            timeout_seconds=args.timeout_seconds,
        )
        summary["commands"].append(post_snapshot_cmd)
        if not post_snapshot_cmd["ok"] or not isinstance(post_snapshot_cmd.get("json"), Mapping):
            raise RuntimeError("post-snapshot-failed")
        post_snapshot = full_summary_from_compact(safe_mapping(post_snapshot_cmd.get("json")))

        post_state_cmd = run_child(
            label="state-post",
            command=build_state_command(root=root, output_root=run_dir, samples=args.samples, interval_seconds=args.interval_seconds),
            cwd=root,
            child_dir=child_dir,
            timeout_seconds=args.timeout_seconds,
        )
        summary["commands"].append(post_state_cmd)
        if not post_state_cmd["ok"] or not isinstance(post_state_cmd.get("json"), Mapping):
            raise RuntimeError("post-state-failed")
        post_state = full_summary_from_compact(safe_mapping(post_state_cmd.get("json")))

        before_json = str(safe_mapping(baseline_snapshot_cmd.get("json")).get("summaryJson"))
        after_json = str(safe_mapping(post_snapshot_cmd.get("json")).get("summaryJson"))
        compare_cmd = run_child(
            label="snapshot-compare",
            command=build_compare_command(root=root, output_root=run_dir, before_json=before_json, after_json=after_json),
            cwd=root,
            child_dir=child_dir,
            timeout_seconds=args.timeout_seconds,
        )
        summary["commands"].append(compare_cmd)
        compare_full: dict[str, Any] = {}
        if compare_cmd["ok"] and isinstance(compare_cmd.get("json"), Mapping):
            compare_full = full_summary_from_compact(safe_mapping(compare_cmd.get("json")))
        else:
            summary["warnings"].append("snapshot-compare-not-available")

        pointer_cmd = run_child(
            label="pointer-owner-neighborhood-post",
            command=build_pointer_command(
                root=root,
                output_root=run_dir / "pointer-owner-neighborhood-post",
                snapshot=post_snapshot,
                target=truth_target,
            ),
            cwd=root,
            child_dir=child_dir,
            timeout_seconds=args.timeout_seconds,
        )
        summary["commands"].append(pointer_cmd)
        if not pointer_cmd["ok"]:
            summary["warnings"].append("pointer-owner-neighborhood-post-not-available")

        baseline_nav = nav_latest_state(baseline_state)
        post_nav = nav_latest_state(post_state)
        yaw_delta = signed_angle_delta(
            baseline_nav.get("yawDegrees") if isinstance(baseline_nav.get("yawDegrees"), (int, float)) else None,
            post_nav.get("yawDegrees") if isinstance(post_nav.get("yawDegrees"), (int, float)) else None,
        )
        focus_deltas = focus_offset_deltas(baseline_snapshot, post_snapshot)
        changed_focus = [
            row
            for row in focus_deltas
            if isinstance(row.get("absDelta"), (int, float)) and float(row["absDelta"]) >= float(args.min_scalar_delta)
        ]
        visual_diff = raw_visual_diff(baseline_visual, post_visual)
        comparison = safe_mapping(compare_full.get("comparison"))
        relative_targets = comparison.get("relativeTargetCandidates", [])
        top_relative = relative_targets[0] if isinstance(relative_targets, list) and relative_targets else None

        static_yaw_changed = yaw_delta is not None and abs(yaw_delta) >= float(args.min_yaw_delta_degrees)
        visual_changed = visual_diff.get("status") == "changed"
        summary["visualEvidence"] = {
            "baseline": baseline_visual,
            "post": post_visual,
            "rawDiff": visual_diff,
        }
        summary["snapshotEvidence"] = {
            "baselineSnapshotJson": before_json,
            "postSnapshotJson": after_json,
            "baselineStateJson": safe_mapping(baseline_state_cmd.get("json")).get("summaryJson"),
            "postStateJson": safe_mapping(post_state_cmd.get("json")).get("summaryJson"),
            "comparisonJson": safe_mapping(compare_cmd.get("json")).get("summaryJson") if isinstance(compare_cmd.get("json"), Mapping) else None,
            "pointerNeighborhoodJson": safe_mapping(pointer_cmd.get("json")).get("summaryJson") if isinstance(pointer_cmd.get("json"), Mapping) else None,
        }
        summary["analysis"] = {
            "baselineYawDegrees": baseline_nav.get("yawDegrees"),
            "postYawDegrees": post_nav.get("yawDegrees"),
            "signedYawDeltaDegrees": yaw_delta,
            "absoluteYawDeltaDegrees": abs(yaw_delta) if yaw_delta is not None else None,
            "staticYawChanged": static_yaw_changed,
            "visualChanged": visual_changed,
            "focusOffsetDeltas": focus_deltas,
            "changedFocusOffsets": changed_focus,
            "topRelativeTargetCandidate": top_relative,
            "coordinateBefore": baseline_snapshot.get("coordinate"),
            "coordinateAfter": post_snapshot.get("coordinate"),
            "classification": (
                "visual-and-static-yaw-changed"
                if visual_changed and static_yaw_changed
                else "visual-changed-static-yaw-unchanged"
                if visual_changed and not static_yaw_changed
                else "static-yaw-changed-without-visual-diff"
                if static_yaw_changed and not visual_changed
                else "no-visual-or-static-yaw-change-detected"
            ),
            "candidateOnly": True,
            "promotionAllowed": False,
            "actionableForRouteControl": bool(static_yaw_changed),
        }

        summary["warnings"].append("candidate-only-no-facing-or-turn-rate-promotion")
        if not static_yaw_changed:
            summary["warnings"].append("static-owner-yaw-did-not-change-after-visual-stimulus")
            summary["next"]["recommendedAction"] = (
                "Use the changed focus offsets and visual evidence for camera-vs-avatar classification; "
                "do not run turn-dependent routes until a yaw/control field is freshly proven."
            )
        else:
            summary["next"]["recommendedAction"] = (
                "Rerun a small proof pack against the changed yaw field before any turn-dependent route movement."
            )
        summary["status"] = "passed"
        summary["verdict"] = str(summary["analysis"]["classification"])
        return summary, 0
    except Exception as exc:  # noqa: BLE001
        summary["status"] = "failed" if not summary["blockers"] else "blocked"
        summary["verdict"] = "camera-yaw-classification-error" if not summary["blockers"] else "camera-yaw-classification-blocked"
        summary["errors"].append(f"{type(exc).__name__}:{exc}")
        return summary, 2 if summary["status"] == "blocked" else 1
    finally:
        summary["blockers"] = sorted(set(str(item) for item in summary.get("blockers", [])))
        summary["warnings"] = sorted(set(str(item) for item in summary.get("warnings", [])))
        summary["errors"] = sorted(set(str(item) for item in summary.get("errors", [])))


def build_markdown(summary: Mapping[str, Any]) -> str:
    if summary.get("kind") == "static-owner-camera-yaw-multipose-report":
        return build_multipose_markdown(summary)

    analysis = safe_mapping(summary.get("analysis"))
    artifacts = safe_mapping(summary.get("artifacts"))
    visual = safe_mapping(summary.get("visualEvidence"))
    lines = [
        "# Static owner camera/yaw classification",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Verdict: `{summary.get('verdict')}`",
        f"- Generated UTC: `{summary.get('generatedAtUtc')}`",
        f"- Run directory: `{summary.get('runDirectory')}`",
        "",
        "## Analysis",
        "",
        f"- Classification: `{analysis.get('classification')}`",
        f"- Baseline yaw: `{analysis.get('baselineYawDegrees')}`",
        f"- Post yaw: `{analysis.get('postYawDegrees')}`",
        f"- Signed yaw delta: `{analysis.get('signedYawDeltaDegrees')}`",
        f"- Visual changed: `{analysis.get('visualChanged')}`",
        f"- Static yaw changed: `{analysis.get('staticYawChanged')}`",
        f"- Actionable for route control: `{analysis.get('actionableForRouteControl')}`",
        "",
        "## Visual evidence",
        "",
        f"- Baseline PNG: `{safe_mapping(visual.get('baseline')).get('output')}`",
        f"- Post PNG: `{safe_mapping(visual.get('post')).get('output')}`",
        f"- Raw diff: `{safe_mapping(visual.get('rawDiff')).get('status')}`",
        "",
        "## Changed focus offsets",
        "",
        "| Offset | Before | After | Delta |",
        "|---|---:|---:|---:|",
    ]
    changed = analysis.get("changedFocusOffsets", [])
    if isinstance(changed, list) and changed:
        for row in changed[:20]:
            item = safe_mapping(row)
            lines.append(f"| `{item.get('offset')}` | `{item.get('before')}` | `{item.get('after')}` | `{item.get('delta')}` |")
    else:
        lines.append("| none |  |  |  |")
    lines.extend(["", "## Artifacts", ""])
    for key, value in artifacts.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Blockers", ""])
    for item in summary.get("blockers", []) or ["none"]:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Warnings", ""])
    for item in summary.get("warnings", []) or ["none"]:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Errors", ""])
    for item in summary.get("errors", []) or ["none"]:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Safety", "", "| Flag | Value |", "|---|---:|"])
    for key, value in safe_mapping(summary.get("safety")).items():
        lines.append(f"| `{key}` | `{value}` |")
    lines.extend(["", "## Next", "", str(safe_mapping(summary.get("next")).get("recommendedAction") or "none")])
    return "\n".join(lines) + "\n"


def build_multipose_markdown(summary: Mapping[str, Any]) -> str:
    analysis = safe_mapping(summary.get("analysis"))
    offset_aggregate = safe_mapping(summary.get("offsetAggregate"))
    lines = [
        "# Static owner camera/yaw multi-pose report",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Verdict: `{summary.get('verdict')}`",
        f"- Generated UTC: `{summary.get('generatedAtUtc')}`",
        f"- Run directory: `{summary.get('runDirectory')}`",
        f"- Source count: `{summary.get('sourceCount')}`",
        "",
        "## Analysis",
        "",
        f"- Classification counts: `{analysis.get('classificationCounts')}`",
        f"- Route-actionable pose count: `{analysis.get('routeActionablePoseCount')}`",
        f"- Visual-changed/static-yaw-unchanged count: `{analysis.get('visualChangedStaticYawUnchangedCount')}`",
        f"- Changed offset count: `{analysis.get('changedOffsetCount')}`",
        f"- Candidate only: `{analysis.get('candidateOnly')}`",
        f"- Promotion allowed: `{analysis.get('promotionAllowed')}`",
        "",
        "## Poses",
        "",
        "| # | Direction | Pixels | Classification | Static yaw changed | Signed yaw delta | Route-actionable |",
        "|---:|---|---:|---|---:|---:|---:|",
    ]
    poses = safe_list(summary.get("poses"))
    if poses:
        for index, pose in enumerate(poses, start=1):
            item = safe_mapping(pose)
            stimulus = safe_mapping(item.get("stimulus"))
            lines.append(
                "| {index} | `{direction}` | `{pixels}` | `{classification}` | `{static}` | `{delta}` | `{actionable}` |".format(
                    index=index,
                    direction=stimulus.get("direction"),
                    pixels=stimulus.get("pixels"),
                    classification=item.get("classification"),
                    static=item.get("staticYawChanged"),
                    delta=item.get("signedYawDeltaDegrees"),
                    actionable=item.get("actionableForRouteControl"),
                )
            )
    else:
        lines.append("| none |  |  |  |  |  |  |")

    lines.extend(["", "## Offset aggregate", "", "| Offset | Samples | Directions | Min delta | Max delta | Max abs delta |", "|---|---:|---|---:|---:|---:|"])
    if offset_aggregate:
        for offset, item_value in offset_aggregate.items():
            item = safe_mapping(item_value)
            lines.append(
                f"| `{offset}` | `{item.get('sampleCount')}` | `{item.get('directions')}` | `{item.get('minDelta')}` | `{item.get('maxDelta')}` | `{item.get('maxAbsDelta')}` |"
            )
    else:
        lines.append("| none |  |  |  |  |  |")

    artifacts = safe_mapping(summary.get("artifacts"))
    lines.extend(["", "## Artifacts", ""])
    for key, value in artifacts.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Blockers", ""])
    for item in summary.get("blockers", []) or ["none"]:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Warnings", ""])
    for item in summary.get("warnings", []) or ["none"]:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Errors", ""])
    for item in summary.get("errors", []) or ["none"]:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Safety", "", "| Flag | Value |", "|---|---:|"])
    for key, value in safe_mapping(summary.get("safety")).items():
        lines.append(f"| `{key}` | `{value}` |")
    lines.extend(["", "## Source safety", "", "| Flag | Value |", "|---|---:|"])
    for key, value in safe_mapping(summary.get("sourceSafety")).items():
        lines.append(f"| `{key}` | `{value}` |")
    lines.extend(["", "## Next", "", str(safe_mapping(summary.get("next")).get("recommendedAction") or "none")])
    return "\n".join(lines) + "\n"


def persist(summary: dict[str, Any]) -> None:
    artifacts = safe_mapping(summary.get("artifacts"))
    summary_json = artifacts.get("summaryJson")
    summary_markdown = artifacts.get("summaryMarkdown")
    if not summary_json or not summary_markdown:
        run_dir = Path(str(summary.get("runDirectory") or tempfile.mkdtemp(prefix="riftreader-camera-yaw-classification-")))
        summary["artifacts"] = {
            "summaryJson": str(run_dir / "summary.json"),
            "summaryMarkdown": str(run_dir / "summary.md"),
        }
        summary_json = summary["artifacts"]["summaryJson"]
        summary_markdown = summary["artifacts"]["summaryMarkdown"]
    write_json(Path(str(summary_json)), summary)
    Path(str(summary_markdown)).parent.mkdir(parents=True, exist_ok=True)
    Path(str(summary_markdown)).write_text(build_markdown(summary), encoding="utf-8", newline="\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Classify visual camera changes against static-owner yaw/facing fields.")
    parser.add_argument("--repo-root")
    parser.add_argument("--output-root")
    parser.add_argument("--current-truth-json", default=DEFAULT_CURRENT_TRUTH_JSON)
    parser.add_argument("--direction", choices=["left", "right"], default="right")
    parser.add_argument("--pixels", type=int, default=80)
    parser.add_argument("--steps", type=int, default=8)
    parser.add_argument("--hold-milliseconds", type=int, default=250)
    parser.add_argument("--focus-delay-milliseconds", type=int, default=250)
    parser.add_argument("--post-input-wait-milliseconds", type=int, default=700)
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--interval-seconds", type=float, default=0.1)
    parser.add_argument("--owner-window-bytes", type=lambda value: int(value, 0), default=0x700)
    parser.add_argument("--min-yaw-delta-degrees", type=float, default=2.0)
    parser.add_argument("--min-scalar-delta", type=float, default=0.001)
    parser.add_argument("--timeout-seconds", type=int, default=60)
    parser.add_argument("--stimulus-approved", action="store_true")
    parser.add_argument(
        "--aggregate-summary-json",
        nargs="+",
        help="Report-only mode: aggregate existing camera/yaw classification summary JSON files without live input.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def compact(summary: Mapping[str, Any]) -> dict[str, Any]:
    if summary.get("kind") == "static-owner-camera-yaw-multipose-report":
        artifacts = safe_mapping(summary.get("artifacts"))
        analysis = safe_mapping(summary.get("analysis"))
        return {
            "status": summary.get("status"),
            "verdict": summary.get("verdict"),
            "sourceCount": summary.get("sourceCount"),
            "classificationCounts": analysis.get("classificationCounts"),
            "routeActionablePoseCount": analysis.get("routeActionablePoseCount"),
            "visualChangedStaticYawUnchangedCount": analysis.get("visualChangedStaticYawUnchangedCount"),
            "changedOffsetCount": analysis.get("changedOffsetCount"),
            "summaryJson": artifacts.get("summaryJson"),
            "summaryMarkdown": artifacts.get("summaryMarkdown"),
            "blockers": summary.get("blockers", []),
            "warnings": summary.get("warnings", []),
            "errors": summary.get("errors", []),
            "safety": summary.get("safety", {}),
            "sourceSafety": summary.get("sourceSafety", {}),
        }

    artifacts = safe_mapping(summary.get("artifacts"))
    analysis = safe_mapping(summary.get("analysis"))
    visual = safe_mapping(summary.get("visualEvidence"))
    return {
        "status": summary.get("status"),
        "verdict": summary.get("verdict"),
        "classification": analysis.get("classification"),
        "visualChanged": analysis.get("visualChanged"),
        "staticYawChanged": analysis.get("staticYawChanged"),
        "signedYawDeltaDegrees": analysis.get("signedYawDeltaDegrees"),
        "changedFocusOffsetCount": len(analysis.get("changedFocusOffsets", []))
        if isinstance(analysis.get("changedFocusOffsets"), list)
        else None,
        "baselinePng": safe_mapping(visual.get("baseline")).get("output"),
        "postPng": safe_mapping(visual.get("post")).get("output"),
        "summaryJson": artifacts.get("summaryJson"),
        "summaryMarkdown": artifacts.get("summaryMarkdown"),
        "blockers": summary.get("blockers", []),
        "warnings": summary.get("warnings", []),
        "errors": summary.get("errors", []),
        "safety": summary.get("safety", {}),
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary, exit_code = run_classification(args)
    persist(summary)
    if args.json:
        print(json.dumps(compact(summary), ensure_ascii=False))
    else:
        print(json.dumps(compact(summary), indent=2, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
