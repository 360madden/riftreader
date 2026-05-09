# Version: riftreader-visual-gate-target-control-v0.2.0
# Total-Character-Count: 10691
# Purpose: Combine the no-input RiftReader target-control preflight with the existing visual gate. Runs target-control first, then runs visual gate with its weaker focus step skipped only after exact-HWND foreground is proven.

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .target_control import (
    EXACT_HWND_FOREGROUND,
    TARGET_CONTROL_PASSED,
    TargetControlOptions,
    run_target_control,
)

VISUAL_GATE_TC_PASSED = "passed-visual-gate-target-control"
VISUAL_GATE_TC_BLOCKED_TARGET_CONTROL = "blocked-target-control-preflight"
VISUAL_GATE_TC_BLOCKED_VISUAL_GATE = "blocked-visual-gate-after-target-control"

DEFAULT_PROCESS_NAME = "rift_x64"
DEFAULT_TITLE_CONTAINS = "RIFT"


@dataclass(frozen=True)
class VisualGateTargetControlOptions:
    repo_root: Path
    process_id: int | None = None
    window_handle: str | None = None
    process_name: str = DEFAULT_PROCESS_NAME
    title_contains: str = DEFAULT_TITLE_CONTAINS
    output_dir: Path | None = None
    full: bool = False
    timeout_seconds: int = 45
    retries: int = 5
    settle_ms: int = 400
    strong_assist: bool = True


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def target_control_allows_visual_gate(summary: dict[str, Any] | None) -> bool:
    if not isinstance(summary, dict):
        return False
    return (
        summary.get("status") == TARGET_CONTROL_PASSED
        and summary.get("classification") == EXACT_HWND_FOREGROUND
        and summary.get("readyForVisualGate") is True
        and not summary.get("blockers")
    )


def default_output_dir(repo_root: Path, process_id: int | None) -> Path:
    pid_text = f"currentpid-{process_id}" if process_id is not None else "currenttarget"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return repo_root / "scripts" / "captures" / f"visual-gate-target-control-{pid_text}-{stamp}"


def build_combined_summary(
    *,
    repo_root: Path,
    output_dir: Path,
    status: str,
    target_control_summary: dict[str, Any],
    visual_gate_summary: dict[str, Any] | None,
    attempted_at_utc: str,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    target_blockers = target_control_summary.get("blockers") if isinstance(target_control_summary, dict) else None
    target_warnings = target_control_summary.get("warnings") if isinstance(target_control_summary, dict) else None
    visual_blockers = visual_gate_summary.get("blockers") if isinstance(visual_gate_summary, dict) else None
    visual_warnings = visual_gate_summary.get("cautions") if isinstance(visual_gate_summary, dict) else None

    if isinstance(target_blockers, list):
        blockers.extend(f"target-control:{item}" for item in target_blockers)
    if isinstance(visual_blockers, list):
        blockers.extend(f"visual-gate:{item}" for item in visual_blockers)
    if isinstance(target_warnings, list):
        warnings.extend(f"target-control:{item}" for item in target_warnings)
    if isinstance(visual_warnings, list):
        warnings.extend(f"visual-gate:{item}" for item in visual_warnings)

    ready_for_visual_gate = target_control_allows_visual_gate(target_control_summary)
    visual_ready = bool(isinstance(visual_gate_summary, dict) and visual_gate_summary.get("readyForLiveInput") is True)
    final_ready = ready_for_visual_gate and visual_ready

    summary: dict[str, Any] = {
        "schemaVersion": 1,
        "status": status,
        "ok": final_ready,
        "readyForVisualGate": ready_for_visual_gate,
        "readyForLiveInput": final_ready,
        "movementSent": False,
        "inputSent": False,
        "screenshotKeySent": False,
        "reloaduiSent": False,
        "noCheatEngine": True,
        "attemptedAtUtc": attempted_at_utc,
        "completedAtUtc": utc_now(),
        "repoRoot": str(repo_root),
        "outputDir": str(output_dir),
        "targetControl": target_control_summary,
        "visualGate": visual_gate_summary,
        "blockers": blockers,
        "warnings": warnings,
        "policyNotes": [
            "This wrapper sends no movement, yaw stimulus, turn stimulus, slash command, screenshot-key input, or /reloadui.",
            "The existing visual gate is run with focus_first disabled only after target-control proves exact-HWND foreground.",
            "This wrapper is a preflight only; it does not authorize movement by itself.",
        ],
    }
    summary["summaryPath"] = str(output_dir / "visual-gate-target-control-status.json")
    return summary


def run_visual_gate_with_target_control(options: VisualGateTargetControlOptions) -> dict[str, Any]:
    repo_root = options.repo_root.resolve()
    output_dir = (options.output_dir or default_output_dir(repo_root, options.process_id)).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    attempted_at = utc_now()

    target_control_summary = run_target_control(
        TargetControlOptions(
            repo_root=repo_root,
            process_id=options.process_id,
            window_handle=options.window_handle,
            process_name=options.process_name,
            title_contains=options.title_contains,
            output_dir=output_dir / "target-control",
            retries=options.retries,
            settle_ms=options.settle_ms,
            strong_assist=options.strong_assist,
        )
    )

    if not target_control_allows_visual_gate(target_control_summary):
        summary = build_combined_summary(
            repo_root=repo_root,
            output_dir=output_dir,
            status=VISUAL_GATE_TC_BLOCKED_TARGET_CONTROL,
            target_control_summary=target_control_summary,
            visual_gate_summary=None,
            attempted_at_utc=attempted_at,
        )
        write_artifacts(summary, output_dir)
        return summary

    from .visual_gate_status import VisualGateOptions, run_visual_gate

    visual_gate_summary = run_visual_gate(
        VisualGateOptions(
            repo_root=repo_root,
            process_id=options.process_id,
            window_handle=options.window_handle,
            process_name=options.process_name,
            title_contains=options.title_contains,
            output_dir=output_dir / "visual-gate",
            focus_first=False,
            full=options.full,
            timeout_seconds=options.timeout_seconds,
        )
    )

    status = (
        VISUAL_GATE_TC_PASSED
        if visual_gate_summary.get("readyForLiveInput") is True
        else VISUAL_GATE_TC_BLOCKED_VISUAL_GATE
    )
    summary = build_combined_summary(
        repo_root=repo_root,
        output_dir=output_dir,
        status=status,
        target_control_summary=target_control_summary,
        visual_gate_summary=visual_gate_summary,
        attempted_at_utc=attempted_at,
    )
    write_artifacts(summary, output_dir)
    return summary


def write_artifacts(summary: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "visual-gate-target-control-status.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    write_markdown_summary(summary, output_dir / "visual-gate-target-control-status.md")


def write_markdown_summary(summary: dict[str, Any], path: Path) -> None:
    blockers = ", ".join(summary.get("blockers") or []) or "none"
    warnings = ", ".join(summary.get("warnings") or []) or "none"
    target = summary.get("targetControl") or {}
    visual = summary.get("visualGate") or {}
    body = f"""# Visual Gate with Target-Control Status

| Field | Value |
|---|---|
| Status | `{summary.get('status')}` |
| Ready for visual gate | `{summary.get('readyForVisualGate')}` |
| Ready for live input preflight | `{summary.get('readyForLiveInput')}` |
| Target-control classification | `{target.get('classification')}` |
| Visual-gate status | `{visual.get('status')}` |
| Blockers | `{blockers}` |
| Warnings | `{warnings}` |
| Summary JSON | `{summary.get('summaryPath')}` |

## Safety

No movement, yaw stimulus, turn stimulus, slash command, screenshot-key input, or `/reloadui` was sent by this wrapper.
"""
    path.write_text(body, encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run target-control first, then the no-input RiftReader visual gate.")
    parser.add_argument("--pid", type=int, dest="process_id", help="Exact target Rift process id.")
    parser.add_argument("--hwnd", dest="window_handle", help="Exact target window handle, e.g. 0x5121A.")
    parser.add_argument("--process-name", default=DEFAULT_PROCESS_NAME)
    parser.add_argument("--title-contains", default=DEFAULT_TITLE_CONTAINS)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=45)
    parser.add_argument("--retries", type=int, default=5)
    parser.add_argument("--settle-ms", type=int, default=400)
    parser.add_argument("--no-strong-assist", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path(__file__).resolve().parents[2]
    summary = run_visual_gate_with_target_control(
        VisualGateTargetControlOptions(
            repo_root=repo_root,
            process_id=args.process_id,
            window_handle=args.window_handle,
            process_name=args.process_name,
            title_contains=args.title_contains,
            output_dir=args.output_dir,
            full=args.full,
            timeout_seconds=args.timeout_seconds,
            retries=args.retries,
            settle_ms=args.settle_ms,
            strong_assist=not args.no_strong_assist,
        )
    )

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(
            f"{summary['status']}: readyForVisualGate={summary['readyForVisualGate']} "
            f"readyForLiveInput={summary['readyForLiveInput']} "
            f"targetControl={summary.get('targetControl', {}).get('classification')} "
            f"blockers={','.join(summary['blockers']) or 'none'}"
        )
        print(f"summaryPath={summary['summaryPath']}")

    return 0 if summary["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())

# END_OF_SCRIPT_MARKER
