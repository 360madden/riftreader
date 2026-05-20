from __future__ import annotations

import argparse
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .character_login_resilience_plan import identities_match, target_identity
from .character_select_automation_plan import repo_relative_or_absolute
from .reports import write_json, write_text_atomic


SCHEMA_VERSION = 1
WATCH_KIND = "riftreader-character-login-crash-watch"
DEFAULT_PROCESS_NAME = "rift_x64"
DEFAULT_TITLE_CONTAINS = "RIFT"


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_repo_path(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def load_json_object(path: Path | None, errors: list[dict[str, str]], *, label: str) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            raise ValueError("JSON root is not an object")
        return data
    except Exception as exc:  # noqa: BLE001 - watcher should report malformed local evidence.
        errors.append({"type": type(exc).__name__, "message": str(exc), "path": str(path), "label": label})
        return {}


def parse_hwnd_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, int):
        return f"0x{value:X}"
    text = str(value).strip()
    if not text:
        return None
    try:
        number = int(text, 0)
    except ValueError:
        return text
    return f"0x{number:X}"


def process_name_matches(actual: Any, expected: str) -> bool:
    actual_text = str(actual or "").strip().casefold()
    expected_text = expected.strip().casefold()
    if actual_text.endswith(".exe"):
        actual_text = actual_text[:-4]
    if expected_text.endswith(".exe"):
        expected_text = expected_text[:-4]
    return bool(actual_text) and actual_text == expected_text


def title_matches(actual: Any, expected_contains: str) -> bool:
    if not expected_contains:
        return True
    return expected_contains.casefold() in str(actual or "").casefold()


def compact_window(raw: dict[str, Any]) -> dict[str, Any]:
    hwnd = parse_hwnd_text(raw.get("windowHandle") or raw.get("windowHandleHex") or raw.get("hwnd"))
    return {
        "processId": raw.get("processId") or raw.get("pid"),
        "windowHandle": hwnd,
        "processName": raw.get("processName"),
        "title": raw.get("title") or raw.get("windowTitle"),
        "isVisible": bool(raw.get("isVisible", raw.get("visible", True))),
        "isMinimized": bool(raw.get("isMinimized", raw.get("minimized", False))),
        "clientSize": raw.get("clientSize"),
        "windowRect": raw.get("windowRect"),
        "clientRect": raw.get("clientRect"),
    }


def live_window_geometry(user32: Any, hwnd: int) -> dict[str, Any]:
    import ctypes
    from ctypes import wintypes

    class POINT(ctypes.Structure):
        _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetWindowRect.restype = wintypes.BOOL
    user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetClientRect.restype = wintypes.BOOL
    user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(POINT)]
    user32.ClientToScreen.restype = wintypes.BOOL

    result: dict[str, Any] = {}
    window_rect = wintypes.RECT()
    if user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(window_rect)):
        result["windowRect"] = {
            "left": int(window_rect.left),
            "top": int(window_rect.top),
            "right": int(window_rect.right),
            "bottom": int(window_rect.bottom),
            "width": int(window_rect.right - window_rect.left),
            "height": int(window_rect.bottom - window_rect.top),
        }
    client_rect = wintypes.RECT()
    origin = POINT(0, 0)
    if user32.GetClientRect(wintypes.HWND(hwnd), ctypes.byref(client_rect)):
        client = {
            "left": int(client_rect.left),
            "top": int(client_rect.top),
            "right": int(client_rect.right),
            "bottom": int(client_rect.bottom),
            "width": int(client_rect.right - client_rect.left),
            "height": int(client_rect.bottom - client_rect.top),
        }
        result["clientSize"] = {"width": client["width"], "height": client["height"]}
        if user32.ClientToScreen(wintypes.HWND(hwnd), ctypes.byref(origin)):
            result["clientRect"] = {
                "left": int(origin.x),
                "top": int(origin.y),
                "right": int(origin.x + client["width"]),
                "bottom": int(origin.y + client["height"]),
                "width": client["width"],
                "height": client["height"],
            }
    return result


def discover_live_windows(*, process_name: str, title_contains: str) -> dict[str, Any]:
    if os.name != "nt":
        return {
            "status": "unsupported-platform",
            "observedAtUtc": utc_iso(),
            "windows": [],
            "errors": [{"type": "UnsupportedPlatform", "message": "Windows HWND discovery is required."}],
        }

    from . import target_control

    user32 = target_control._load_user32()  # noqa: SLF001 - reuse repo-owned no-input Win32 setup.
    windows: list[dict[str, Any]] = []
    for snapshot in target_control.enumerate_top_level_windows(user32):
        if not snapshot.is_visible:
            continue
        if not title_matches(snapshot.title, title_contains):
            continue
        if snapshot.process_name and not process_name_matches(snapshot.process_name, process_name):
            continue
        record = {
            "processId": snapshot.process_id,
            "windowHandle": snapshot.hwnd_hex,
            "processName": snapshot.process_name,
            "title": snapshot.title,
            "isVisible": snapshot.is_visible,
            "isMinimized": snapshot.is_minimized,
        }
        record.update(live_window_geometry(user32, snapshot.hwnd))
        windows.append(record)

    return {
        "status": "observed",
        "observedAtUtc": utc_iso(),
        "windows": windows,
        "errors": [],
    }


def load_observations(path: Path, errors: list[dict[str, str]]) -> list[dict[str, Any]]:
    data = load_json_object(path, errors, label="observations")
    if not data:
        return []
    if isinstance(data.get("observations"), list):
        return [item for item in data["observations"] if isinstance(item, dict)]
    if isinstance(data.get("windows"), list):
        return [
            {
                "status": data.get("status", "observed"),
                "observedAtUtc": data.get("observedAtUtc", utc_iso()),
                "windows": data["windows"],
                "errors": data.get("errors", []),
            }
        ]
    errors.append({"type": "ValueError", "message": "observations JSON must contain observations[] or windows[]", "path": str(path)})
    return []


def collect_observations(
    *,
    samples: int,
    interval_seconds: float,
    process_name: str,
    title_contains: str,
) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for index in range(max(1, samples)):
        observation = discover_live_windows(process_name=process_name, title_contains=title_contains)
        observation["sampleIndex"] = index + 1
        observations.append(observation)
        if index + 1 < max(1, samples):
            time.sleep(max(0.0, interval_seconds))
    return observations


def window_identity(window: dict[str, Any]) -> dict[str, Any]:
    return {
        "processName": window.get("processName"),
        "processId": window.get("processId"),
        "windowHandle": parse_hwnd_text(window.get("windowHandle")),
        "windowTitle": window.get("title"),
    }


def enrich_observations(
    observations: list[dict[str, Any]],
    *,
    expected_target: dict[str, Any],
    process_name: str,
    title_contains: str,
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for observation in observations:
        windows = []
        for raw_window in observation.get("windows") or []:
            if not isinstance(raw_window, dict):
                continue
            window = compact_window(raw_window)
            if not title_matches(window.get("title"), title_contains):
                continue
            if window.get("processName") and not process_name_matches(window.get("processName"), process_name):
                continue
            identity = window_identity(window)
            window["matchesExpectedTarget"] = identities_match(identity, expected_target) if expected_target else False
            window["matchesExpectedPid"] = (
                expected_target.get("processId") is not None
                and identity.get("processId") == expected_target.get("processId")
            )
            window["matchesExpectedHwnd"] = (
                bool(expected_target.get("windowHandle"))
                and str(identity.get("windowHandle")).casefold() == str(expected_target.get("windowHandle")).casefold()
            )
            windows.append(window)
        enriched.append(
            {
                "sampleIndex": observation.get("sampleIndex"),
                "status": observation.get("status", "observed"),
                "observedAtUtc": observation.get("observedAtUtc"),
                "windowCount": len(windows),
                "windows": windows,
                "errors": observation.get("errors", []),
            }
        )
    return enriched


def latest_observation(observations: list[dict[str, Any]]) -> dict[str, Any]:
    return observations[-1] if observations else {"status": "missing-observation", "windows": [], "errors": []}


def classify_watch(
    *,
    observations: list[dict[str, Any]],
    expected_target: dict[str, Any],
    readiness: dict[str, Any],
) -> tuple[str, list[str], list[str], str]:
    blockers: list[str] = []
    warnings: list[str] = []
    latest = latest_observation(observations)
    latest_errors = latest.get("errors") if isinstance(latest.get("errors"), list) else []
    if latest.get("status") == "unsupported-platform":
        blockers.append("unsupported-platform")
        return "blocked-unsupported-platform", blockers, warnings, "Cannot observe RIFT HWNDs on this platform."
    if latest_errors:
        warnings.extend(f"observation-error:{item.get('type', 'unknown')}" for item in latest_errors if isinstance(item, dict))

    windows = latest.get("windows") if isinstance(latest.get("windows"), list) else []
    if not windows:
        blockers.append("rift-client-not-running-or-window-not-visible")
        return "blocked-no-client", blockers, warnings, "Relaunch RIFT, reach character selection, then rerun the watcher."

    exact = [window for window in windows if window.get("matchesExpectedTarget") is True]
    if exact:
        target = exact[0]
        if target.get("isMinimized"):
            blockers.append("expected-target-minimized")
            return "blocked-target-minimized", blockers, warnings, "Restore the RIFT window, then rerun readiness capture."
        if target.get("isVisible") is not True:
            blockers.append("expected-target-not-visible")
            return "blocked-target-not-visible", blockers, warnings, "Make the RIFT window visible, then rerun readiness capture."
        if readiness.get("status") not in {None, "packet-ready"}:
            warnings.append(f"readiness-packet-status:{readiness.get('status')}")
        return (
            "target-present-same-epoch",
            blockers,
            warnings,
            "Same PID/HWND is still present. Refresh readiness immediately before any approved Play click.",
        )

    same_pid = [window for window in windows if window.get("matchesExpectedPid") is True]
    if same_pid:
        blockers.append("expected-pid-present-but-hwnd-changed")
        return "blocked-hwnd-drift", blockers, warnings, "Rebind exact HWND and recapture character-select environment."

    if len(windows) > 1:
        blockers.append("multiple-rift-windows-without-expected-target")
        return "blocked-multiple-rift-windows", blockers, warnings, "Select the intended RIFT PID/HWND before planning login."

    blockers.append("expected-target-not-found-new-client-epoch")
    return (
        "blocked-target-drift-new-epoch",
        blockers,
        warnings,
        "Treat the old PID/HWND as stale; recapture environment and rebuild readiness for the new client epoch.",
    )


def build_state_log(summary: dict[str, Any]) -> list[dict[str, Any]]:
    watch_status = summary.get("watchStatus")
    same_epoch = watch_status == "target-present-same-epoch"
    live_present = watch_status not in {"blocked-no-client", "blocked-unsupported-platform"}
    return [
        {
            "state": "detect-client",
            "status": "passed" if live_present else "blocked",
            "liveInputAllowed": False,
        },
        {
            "state": "target-epoch-check",
            "status": "same-epoch" if same_epoch else "blocked",
            "liveInputAllowed": False,
        },
        {
            "state": "refresh-character-select-readiness",
            "status": "recommended" if same_epoch else "pending-after-recapture",
            "liveInputAllowed": False,
        },
        {
            "state": "future-click-play",
            "status": "approval-required" if same_epoch else "blocked",
            "liveInputAllowed": "approval-required",
        },
        {
            "state": "post-world-proof",
            "status": "pending-after-world-load",
            "liveInputAllowed": False,
        },
    ]


def build_packet(
    *,
    repo_root: Path,
    output_root: Path,
    observations: list[dict[str, Any]],
    current_truth_path: Path,
    current_proof_path: Path,
    readiness_packet_path: Path | None,
    process_name: str,
    title_contains: str,
) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    truth = load_json_object(current_truth_path, errors, label="current-truth")
    proof = load_json_object(current_proof_path, errors, label="current-proof")
    readiness = load_json_object(readiness_packet_path, errors, label="readiness-packet")

    truth_target = target_identity(truth) if truth else {}
    proof_target = target_identity(proof) if proof else {}
    readiness_target = target_identity(readiness) if readiness else {}
    expected_target = truth_target or readiness_target or proof_target

    data_warnings: list[str] = []
    data_blockers: list[str] = []
    if not truth:
        data_blockers.append("missing-current-truth")
    if not proof:
        data_blockers.append("missing-current-proof")
    if not readiness:
        data_warnings.append("missing-character-login-readiness-packet")
    if truth_target and proof_target and not identities_match(truth_target, proof_target):
        data_blockers.append("current-truth-current-proof-target-mismatch")
    if readiness_target and truth_target and not identities_match(readiness_target, truth_target):
        data_warnings.append("readiness-packet-target-mismatch")

    enriched = enrich_observations(
        observations,
        expected_target=expected_target,
        process_name=process_name,
        title_contains=title_contains,
    )
    watch_status, watch_blockers, watch_warnings, recommended = classify_watch(
        observations=enriched,
        expected_target=expected_target,
        readiness=readiness,
    )
    status = "failed" if errors else "blocked" if data_blockers or watch_blockers else "watch-ready"

    summary_json = output_root / "character-login-crash-watch-summary.json"
    summary_markdown = output_root / "character-login-crash-watch.md"
    observations_jsonl = output_root / "character-login-crash-watch-observations.jsonl"
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": WATCH_KIND,
        "status": status,
        "watchStatus": watch_status,
        "generatedAtUtc": utc_iso(),
        "dataBlockers": data_blockers,
        "watchBlockers": watch_blockers,
        "warnings": data_warnings + watch_warnings,
        "errors": errors,
        "expectedTarget": expected_target,
        "targetComparisons": {
            "currentTruth": truth_target,
            "currentProof": proof_target,
            "readinessPacket": readiness_target,
        },
        "latestObservation": latest_observation(enriched),
        "observations": enriched,
        "resumeDecision": {
            "recommendedAction": recommended,
            "resumeAtState": "detect-client" if watch_status != "target-present-same-epoch" else "refresh-character-select-readiness",
            "oldEpochReusePolicy": "do-not-reuse-old-PID-HWND-absolute-addresses-screenshots-or-approval-tokens-after-drift",
            "movementAllowed": False,
            "worldEntryAllowedNow": False,
            "requiresExplicitWorldEntryApproval": True,
            "requiresPostWorldProofOnly": True,
        },
        "stateLog": [],
        "commands": {
            "refreshWatch": "scripts\\riftreader-character-login-crash-watch.cmd --samples 3 --interval-seconds 1 --json",
            "refreshReadinessPacket": "scripts\\riftreader-character-login-readiness-packet.cmd --target-character ATANK --json",
            "refreshEnvironment": "scripts\\riftreader-character-select-env-capture.cmd --pid <PID> --hwnd <HWND> --process-start-utc <UTC> --module-base <BASE> --json",
            "workflowStatus": "scripts\\riftreader-workflow-status.cmd --compact-json",
        },
        "safety": {
            "planOnly": True,
            "willExecuteLiveActions": False,
            "movementSent": False,
            "keyInputSent": False,
            "mouseClickSent": False,
            "worldEntryClicked": False,
            "clientLaunchAttempted": False,
            "cheatEngineUsed": False,
            "x64dbgAttachStarted": False,
            "savedVariablesUsedAsLiveTruth": False,
            "providerWrites": False,
            "gitMutation": False,
        },
        "artifacts": {
            "currentTruth": repo_relative_or_absolute(current_truth_path, repo_root),
            "currentProof": repo_relative_or_absolute(current_proof_path, repo_root),
            "readinessPacket": repo_relative_or_absolute(readiness_packet_path, repo_root)
            if readiness_packet_path
            else None,
            "summaryJson": str(summary_json.resolve()),
            "summaryMarkdown": str(summary_markdown.resolve()),
            "observationsJsonl": str(observations_jsonl.resolve()),
        },
    }
    summary["stateLog"] = build_state_log(summary)
    return summary


def write_observations_jsonl(path: Path, observations: list[dict[str, Any]]) -> None:
    write_text_atomic(path, "".join(json.dumps(item, sort_keys=True) + "\n" for item in observations))


def render_markdown(summary: dict[str, Any]) -> str:
    target = summary.get("expectedTarget") if isinstance(summary.get("expectedTarget"), dict) else {}
    latest = summary.get("latestObservation") if isinstance(summary.get("latestObservation"), dict) else {}
    windows = latest.get("windows") if isinstance(latest.get("windows"), list) else []
    resume = summary.get("resumeDecision") if isinstance(summary.get("resumeDecision"), dict) else {}
    lines = [
        "# Character login crash/relogin watch",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Watch status: `{summary.get('watchStatus')}`",
        f"- Generated: `{summary.get('generatedAtUtc')}`",
        f"- Expected target: PID `{target.get('processId')}`, HWND `{target.get('windowHandle')}`",
        f"- Observed matching windows: `{len(windows)}`",
        f"- Resume at: `{resume.get('resumeAtState')}`",
        f"- Movement allowed: `{str(resume.get('movementAllowed')).lower()}`",
        f"- World entry allowed now: `{str(resume.get('worldEntryAllowedNow')).lower()}`",
        "",
        "## Observed windows",
        "",
        "| PID | HWND | Title | Visible | Minimized | Matches expected | Client |",
        "|---:|---|---|---|---|---|---|",
    ]
    for window in windows:
        client = window.get("clientSize") if isinstance(window.get("clientSize"), dict) else {}
        lines.append(
            f"| `{window.get('processId')}` | `{window.get('windowHandle')}` | `{window.get('title')}` | "
            f"`{str(window.get('isVisible')).lower()}` | `{str(window.get('isMinimized')).lower()}` | "
            f"`{str(window.get('matchesExpectedTarget')).lower()}` | `{client.get('width')}x{client.get('height')}` |"
        )
    lines.extend(["", "## Blockers", ""])
    blockers = list(summary.get("dataBlockers") or []) + list(summary.get("watchBlockers") or [])
    lines.extend([f"- `{item}`" for item in blockers] or ["- none"])
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- `{item}`" for item in (summary.get("warnings") or [])] or ["- none"])
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            str(resume.get("recommendedAction") or ""),
            "",
            "This watcher never launches the client, clicks, sends keys, enters world, moves, reads live game memory, attaches a debugger, or writes provider/Git state.",
            "",
        ]
    )
    return "\n".join(lines)


def latest_readiness_packet(repo_root: Path) -> Path | None:
    root = repo_root / ".riftreader-local" / "character-login-readiness-packet"
    latest = root / "latest-run.txt"
    if latest.exists():
        candidate = Path(latest.read_text(encoding="utf-8").strip()) / "character-login-readiness-packet-summary.json"
        if candidate.exists():
            return candidate.resolve()
    matches = list(root.glob("run-*/character-login-readiness-packet-summary.json"))
    if not matches:
        return None
    return max(matches, key=lambda path: path.stat().st_mtime).resolve()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Observe RIFT client crash/relogin state without live input.")
    parser.add_argument("--repo-root", type=Path, default=repo_root_from_module())
    parser.add_argument("--current-truth", type=Path, default=Path("docs/recovery/current-truth.json"))
    parser.add_argument("--current-proof", type=Path, default=Path("docs/recovery/current-proof-anchor-readback.json"))
    parser.add_argument("--readiness-packet", type=Path)
    parser.add_argument("--observations-json", type=Path, help="Offline fixture with observations[] or windows[].")
    parser.add_argument("--process-name", default=DEFAULT_PROCESS_NAME)
    parser.add_argument("--title-contains", default=DEFAULT_TITLE_CONTAINS)
    parser.add_argument("--samples", type=int, default=1)
    parser.add_argument("--interval-seconds", type=float, default=1.0)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    output_root = (
        args.output_root.resolve()
        if args.output_root
        else (repo_root / ".riftreader-local" / "character-login-crash-watch" / f"run-{utc_stamp()}").resolve()
    )
    output_root.mkdir(parents=True, exist_ok=True)
    current_truth = resolve_repo_path(repo_root, args.current_truth)
    current_proof = resolve_repo_path(repo_root, args.current_proof)
    readiness_packet = (
        resolve_repo_path(repo_root, args.readiness_packet)
        if args.readiness_packet
        else latest_readiness_packet(repo_root)
    )
    observation_errors: list[dict[str, str]] = []
    observations = (
        load_observations(resolve_repo_path(repo_root, args.observations_json), observation_errors)
        if args.observations_json
        else collect_observations(
            samples=args.samples,
            interval_seconds=args.interval_seconds,
            process_name=args.process_name,
            title_contains=args.title_contains,
        )
    )
    summary = build_packet(
        repo_root=repo_root,
        output_root=output_root,
        observations=observations,
        current_truth_path=current_truth,
        current_proof_path=current_proof,
        readiness_packet_path=readiness_packet,
        process_name=args.process_name,
        title_contains=args.title_contains,
    )
    summary["errors"].extend(observation_errors)
    if observation_errors and summary["status"] != "blocked":
        summary["status"] = "failed"

    summary_json = output_root / "character-login-crash-watch-summary.json"
    summary_markdown = output_root / "character-login-crash-watch.md"
    observations_jsonl = output_root / "character-login-crash-watch-observations.jsonl"
    summary["artifacts"]["summaryJson"] = str(summary_json.resolve())
    summary["artifacts"]["summaryMarkdown"] = str(summary_markdown.resolve())
    summary["artifacts"]["observationsJsonl"] = str(observations_jsonl.resolve())
    write_observations_jsonl(observations_jsonl, summary.get("observations") or [])
    write_json(summary_json, summary)
    write_text_atomic(summary_markdown, render_markdown(summary))
    latest = repo_root / ".riftreader-local" / "character-login-crash-watch" / "latest-run.txt"
    write_text_atomic(latest, str(output_root.resolve()))

    if args.json:
        print(json.dumps(summary, indent=2))

    if summary.get("status") == "watch-ready":
        return 0
    if summary.get("status") == "blocked":
        return 2
    return 1
