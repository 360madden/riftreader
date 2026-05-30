from __future__ import annotations

import argparse
import json
import os
import sys
import time
from ctypes import wintypes
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Ensure scripts/ and the project root are on sys.path so both rift_live_test.*
# and scripts.* imports resolve regardless of invocation directory.
_script_dir = Path(__file__).resolve().parent  # scripts/rift_live_test/
_parent_scripts = str(_script_dir.parent)  # scripts/
_project_root = str(_script_dir.parent.parent)  # RiftReader/
if _parent_scripts not in sys.path:
    sys.path.insert(0, _parent_scripts)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

try:
    from rift_live_test.reports import write_json, write_text_atomic
    from rift_live_test.target_control import (
        WNDENUMPROC,
        WindowSnapshot,
        _load_user32,
        get_window_snapshot,
        parse_hwnd,
    )
except ImportError:  # pragma: no cover - alternate invocation paths
    from rift_live_test.reports import write_json, write_text_atomic  # type: ignore[no-redef]
    from rift_live_test.target_control import (  # type: ignore[no-redef]
        WNDENUMPROC, WindowSnapshot, _load_user32, get_window_snapshot, parse_hwnd,
    )

try:
    from scripts.nav_state_readback import read_nav_state
except ImportError:  # pragma: no cover - invoked from within scripts/ directory.
    from scripts.nav_state_readback import read_nav_state  # type: ignore[no-redef]


TARGET_FOUND_PASSIVE = "target-found-passive"
TARGET_MISSING = "blocked-target-missing"
TARGET_MINIMIZED = "blocked-target-minimized"
UNSUPPORTED_NON_WINDOWS = "unsupported-non-windows"


@dataclass(frozen=True)
class NavigationTargetWatchOptions:
    repo_root: Path
    process_id: int | None = None
    window_handle: str | None = None
    process_name: str = "rift_x64"
    title_contains: str = "RIFT"
    attempts: int = 1
    interval_seconds: float = 5.0
    output_dir: Path | None = None


def watch_navigation_target(
    options: NavigationTargetWatchOptions,
    *,
    run_nav_state: bool = False,
) -> dict[str, Any]:
    repo_root = options.repo_root.resolve()
    output_dir = (options.output_dir or _default_output_dir(repo_root)).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    started_at = _utc_now()
    attempts: list[dict[str, Any]] = []

    if os.name != "nt":
        summary = _summary(
            options=options,
            repo_root=repo_root,
            output_dir=output_dir,
            started_at=started_at,
            attempts=[],
            final_status=UNSUPPORTED_NON_WINDOWS,
            blockers=[UNSUPPORTED_NON_WINDOWS],
            nav_state_check=None,
        )
        _write_summary(summary, output_dir)
        return summary

    user32 = _load_user32()
    final_status = TARGET_MISSING
    blockers = ["target-window-missing"]
    selected_window: dict[str, Any] | None = None

    for attempt_number in range(1, max(1, options.attempts) + 1):
        windows = _find_matching_windows(options, user32)
        attempt = _attempt_summary(attempt_number, windows)
        attempts.append(attempt)

        final_status = str(attempt["status"])
        blockers = list(attempt["blockers"])
        if attempt.get("selectedWindow"):
            selected_window = attempt["selectedWindow"]
        if attempt["readyForTargetControl"]:
            break
        if attempt_number < max(1, options.attempts):
            time.sleep(max(0.0, options.interval_seconds))

    # Optional pointer-chain nav-state health check.
    # Uses --use-current-truth because the live window enumeration does not
    # capture the module base address; the current-truth JSON is validated
    # separately and contains the correct module base.
    nav_state_check: dict[str, Any] | None = None
    if run_nav_state and selected_window:
        nav_state_check = read_nav_state(
            root=repo_root,
            use_current_truth=True,
            current_truth_json="docs/recovery/current-truth.json",
        )

    summary = _summary(
        options=options,
        repo_root=repo_root,
        output_dir=output_dir,
        started_at=started_at,
        attempts=attempts,
        final_status=final_status,
        blockers=blockers,
        nav_state_check=nav_state_check,
    )
    _write_summary(summary, output_dir)
    return summary


def _find_matching_windows(options: NavigationTargetWatchOptions, user32: Any) -> list[WindowSnapshot]:
    requested_hwnd = parse_hwnd(options.window_handle)
    if requested_hwnd is not None:
        snapshot = get_window_snapshot(user32, requested_hwnd)
        windows = [snapshot] if snapshot is not None else []
    else:
        windows = _enumerate_top_level_windows(user32)
    return _filter_matching_windows(
        windows,
        process_id=options.process_id,
        process_name=options.process_name,
        title_contains=options.title_contains,
    )


def _enumerate_top_level_windows(user32: Any) -> list[WindowSnapshot]:
    windows: list[WindowSnapshot] = []

    @WNDENUMPROC  # type: ignore[misc]
    def enum_proc(hwnd: wintypes.HWND, _lparam: wintypes.LPARAM) -> bool:
        snapshot = get_window_snapshot(user32, int(hwnd))
        if snapshot is not None:
            windows.append(snapshot)
        return True

    user32.EnumWindows(enum_proc, 0)
    return windows


def _filter_matching_windows(
    windows: list[WindowSnapshot],
    *,
    process_id: int | None,
    process_name: str,
    title_contains: str,
) -> list[WindowSnapshot]:
    matches: list[WindowSnapshot] = []
    for window in windows:
        if process_id is not None and window.process_id != process_id:
            continue
        if process_name and not _process_name_matches(window.process_name, process_name):
            continue
        if title_contains and title_contains.lower() not in (window.title or "").lower():
            continue
        matches.append(window)
    return matches


def _attempt_summary(attempt_number: int, windows: list[WindowSnapshot]) -> dict[str, Any]:
    visible = [window for window in windows if window.is_visible and not window.is_minimized]
    minimized = [window for window in windows if window.is_minimized]

    if visible:
        status = TARGET_FOUND_PASSIVE
        blockers: list[str] = []
        ready = True
    elif minimized:
        status = TARGET_MINIMIZED
        blockers = ["target-window-minimized"]
        ready = False
    else:
        status = TARGET_MISSING
        blockers = ["target-window-missing"]
        ready = False

    selected = visible[0] if visible else (windows[0] if windows else None)
    return {
        "attempt": attempt_number,
        "attemptedAtUtc": _utc_now(),
        "status": status,
        "ok": ready,
        "readyForTargetControl": ready,
        "readyForVisualGate": False,
        "readyForProofOnly": False,
        "blockers": blockers,
        "selectedWindow": _window_to_dict(selected) if selected else None,
        "matchingWindowCount": len(windows),
        "matchingWindows": [_window_to_dict(window) for window in windows[:10]],
    }


def _summary(
    *,
    options: NavigationTargetWatchOptions,
    repo_root: Path,
    output_dir: Path,
    started_at: str,
    attempts: list[dict[str, Any]],
    final_status: str,
    blockers: list[str],
    nav_state_check: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ready = final_status == TARGET_FOUND_PASSIVE
    selected = None
    for attempt in reversed(attempts):
        selected = attempt.get("selectedWindow")
        if selected is not None:
            break

    summary_json = output_dir / "summary.json"
    summary_md = output_dir / "summary.md"
    return {
        "schemaVersion": 1,
        "mode": "navigation-target-watch",
        "status": final_status,
        "ok": ready,
        "startedAtUtc": started_at,
        "completedAtUtc": _utc_now(),
        "repoRoot": str(repo_root),
        "outputDir": str(output_dir),
        "target": {
            "processName": options.process_name,
            "processId": options.process_id,
            "windowHandle": options.window_handle,
            "titleContains": options.title_contains,
        },
        "attemptCount": len(attempts),
        "attemptsRequested": max(1, options.attempts),
        "intervalSeconds": options.interval_seconds,
        "readyForTargetControl": ready,
        "readyForVisualGate": False,
        "readyForProofOnly": False,
        "readyForLiveInput": False,
        "selectedWindow": selected,
        "blockers": blockers,
        "warnings": ["passive-watch-only-rerun-target-control-before-visual-or-proof"] if ready else [],
        "attempts": attempts,
        "navStateCheck": nav_state_check,
        "safety": {
            "passiveEnumerationOnly": True,
            "foregroundChanged": False,
            "movementSent": False,
            "inputSent": False,
            "reloaduiSent": False,
            "screenshotKeySent": False,
            "noCheatEngine": True,
            "providerWrites": False,
        },
        "artifacts": {
            "summaryJson": str(summary_json),
            "summaryMarkdown": str(summary_md),
        },
        "next": _next_actions(final_status),
    }





def _next_actions(status: str) -> list[dict[str, str]]:
    if status == TARGET_FOUND_PASSIVE:
        return [
            {
                "action": "Run target-control for the selected exact PID/HWND",
                "why": "Passive enumeration found a window, but did not prove foreground/focus readiness.",
            },
            {
                "action": "Run visual gate only after target-control passes",
                "why": "Visual capture must match the exact active RIFT target.",
            },
            {
                "action": "Run same-target ProofOnly before route work",
                "why": "Navigation needs a fresh proof anchor for the current process epoch.",
            },
        ]
    return [
        {
            "action": "Relaunch or log into RIFT, then rerun this watcher",
            "why": "No visible matching RIFT target was found.",
        },
        {
            "action": "Keep visual gate, ProofOnly, and movement blocked",
            "why": "There is no exact target to validate.",
        },
    ]


def _write_summary(summary: dict[str, Any], output_dir: Path) -> None:
    write_json(output_dir / "summary.json", summary)
    write_text_atomic(output_dir / "summary.md", _render_markdown(summary))


def _render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Navigation target watch",
        "",
        f"Generated: `{summary.get('completedAtUtc')}`",
        f"Status: `{summary.get('status')}`",
        "",
        "## Safety",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Passive enumeration only | `{str(summary['safety']['passiveEnumerationOnly']).lower()}` |",
        f"| Foreground changed | `{str(summary['safety']['foregroundChanged']).lower()}` |",
        f"| Movement sent | `{str(summary['safety']['movementSent']).lower()}` |",
        f"| Input sent | `{str(summary['safety']['inputSent']).lower()}` |",
        f"| Cheat Engine | `not-used` |",
        "",
        "## Target",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Process name | `{summary['target'].get('processName')}` |",
        f"| Process ID | `{summary['target'].get('processId')}` |",
        f"| HWND | `{summary['target'].get('windowHandle')}` |",
        f"| Title contains | `{summary['target'].get('titleContains')}` |",
        "",
        "## Blockers",
        "",
    ]
    if summary.get("blockers"):
        lines.extend(f"- `{blocker}`" for blocker in summary["blockers"])
    else:
        lines.append("- None from passive target watch.")

    selected = summary.get("selectedWindow")
    if selected:
        lines.extend(
            [
                "",
                "## Selected window",
                "",
                "| Field | Value |",
                "|---|---|",
                f"| PID | `{selected.get('processId')}` |",
                f"| HWND | `{selected.get('windowHandleHex')}` |",
                f"| Process | `{selected.get('processName')}` |",
                f"| Title | `{selected.get('title')}` |",
                f"| Visible | `{selected.get('isVisible')}` |",
                f"| Minimized | `{selected.get('isMinimized')}` |",
            ]
        )

    lines.extend(
        [
            "",
            "## Attempts",
            "",
            "| # | Status | Matches | Selected |",
            "|---:|---|---:|---|",
        ]
    )
    for attempt in summary.get("attempts", []):
        selected_window = attempt.get("selectedWindow") or {}
        selected_text = ""
        if selected_window:
            selected_text = f"pid={selected_window.get('processId')}; hwnd={selected_window.get('windowHandleHex')}"
        lines.append(
            f"| {attempt.get('attempt')} | `{attempt.get('status')}` | "
            f"`{attempt.get('matchingWindowCount')}` | `{selected_text}` |"
        )

    lines.extend(
        [
            "",
            "## Recommended next actions",
            "",
            "| # | Action | Why |",
            "|---:|---|---|",
        ]
    )
    for index, item in enumerate(summary.get("next") or [], start=1):
        lines.append(f"| {index} | {item.get('action')} | {item.get('why')} |")

    # Pointer-chain nav-state health check
    nav_check = summary.get("navStateCheck")
    if nav_check:
        lines.extend([
            "",
            "## Pointer-chain nav-state health check (candidate-only)",
            "",
            f"- Status: `{nav_check.get('status')}`",
            f"- Verdict: `{nav_check.get('verdict')}`",
            f"- Yaw: `{nav_check.get('yawDegrees')}`",
            f"- Turn rate (0x304): `{nav_check.get('turnRate0x304')}`",
            f"- Turn classification: `{nav_check.get('turnRateClassification')}`",
            "",
            "> **Note:** Pointer-chain readback is candidate-only and not used for navigation decisions.",
        ])
        if not nav_check.get("ok"):
            lines.extend([
                "",
                "> **Warning:** Pointer-chain resolver is not healthy for this target. Navigation should not proceed until the resolver is validated.",
            ])
    return "\n".join(lines).rstrip() + "\n"


def _process_name_matches(actual: str | None, expected: str) -> bool:
    if not actual:
        return False
    return _normalize_process_name(actual) == _normalize_process_name(expected)


def _normalize_process_name(value: str) -> str:
    text = Path(value).stem if "\\" in value or "/" in value else value
    return text.removesuffix(".exe").lower()


def _window_to_dict(window: WindowSnapshot | None) -> dict[str, Any] | None:
    if window is None:
        return None
    return {
        "windowHandle": window.hwnd,
        "windowHandleHex": window.hwnd_hex,
        "processId": window.process_id,
        "processName": window.process_name,
        "title": window.title,
        "isWindow": window.is_window,
        "isVisible": window.is_visible,
        "isMinimized": window.is_minimized,
    }


def _default_output_dir(repo_root: Path) -> Path:
    return repo_root / "scripts" / "captures" / f"navigation-target-watch-{_stamp()}"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Passively watch for the RIFT navigation target.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--pid", type=int)
    parser.add_argument("--hwnd")
    parser.add_argument("--process-name", default="rift_x64")
    parser.add_argument("--title-contains", default="RIFT")
    parser.add_argument("--attempts", type=int, default=1)
    parser.add_argument("--interval-seconds", type=float, default=5.0)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict-exit",
        action="store_true",
        help="Return 2 when no visible target is found. Default returns 0 after writing artifacts.",
    )
    parser.add_argument("--nav-state", action="store_true",
        help="Run pointer-chain nav-state readback to validate resolver health after finding the target window.",
    )
    args = parser.parse_args(argv)

    summary = watch_navigation_target(
        NavigationTargetWatchOptions(
            repo_root=args.root,
            process_id=args.pid,
            window_handle=args.hwnd,
            process_name=args.process_name,
            title_contains=args.title_contains,
            attempts=args.attempts,
            interval_seconds=args.interval_seconds,
            output_dir=args.output_dir,
        ),
        run_nav_state=bool(args.nav_state),
    )
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"Navigation target watch: {summary['status']}")
        print(f"Summary JSON: {summary['artifacts']['summaryJson']}")
        print(f"Summary Markdown: {summary['artifacts']['summaryMarkdown']}")

    if args.strict_exit and not summary.get("ok"):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
