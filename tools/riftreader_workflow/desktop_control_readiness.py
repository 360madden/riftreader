#!/usr/bin/env python3
"""Read-only Browser/Computer Use readiness for the ChatGPT MCP workflow.

This helper does not automate browsers, click desktop UI, start MCP servers,
start tunnels, send RIFT input, attach debuggers, or mutate Git. It only reports
whether repo-owned dashboard/MCP prerequisites are in place and whether an
operator has recorded external Browser/Computer Use smoke proof.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .common import find_repo_root, repo_rel, safety_flags, utc_iso, utc_stamp
except ImportError:  # pragma: no cover - supports direct script execution.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.common import find_repo_root, repo_rel, safety_flags, utc_iso, utc_stamp

SCHEMA_VERSION = 1
OBSERVATION_ROOT = Path(".riftreader-local") / "riftreader-chatgpt-mcp" / "desktop-control-readiness"
OBSERVATION_MAX_AGE_SECONDS = 24 * 60 * 60
DASHBOARD_URL = "http://127.0.0.1:8788/"
DASHBOARD_STATUS_URL = "http://127.0.0.1:8788/status.json"
COMPUTER_USE_BLOCKER = "computer-use-native-pipe-not-confirmed"
COMPUTER_USE_LIST_APPS_BLOCKER = "computer-use-list-apps-not-confirmed"
BROWSER_USE_BLOCKER = "browser-use-dashboard-smoke-not-confirmed"
OBSERVATION_STALE_BLOCKER = "desktop-control-observation-stale"


def latest_observation_path(repo_root: Path) -> Path | None:
    root = repo_root / OBSERVATION_ROOT
    if not root.is_dir():
        return None
    candidates = [path for path in root.rglob("*.json") if path.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: (path.stat().st_mtime_ns, str(path)))


def load_json_object(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - readiness must fail closed on malformed local notes.
        return None
    return value if isinstance(value, dict) else None


def bool_from_path(payload: dict[str, Any] | None, *path: str) -> bool | None:
    value: Any = payload
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value if isinstance(value, bool) else None


def script_exists(repo_root: Path, relative_path: str) -> bool:
    return (repo_root / relative_path).is_file()


def parse_utc_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def observation_generated_at(path: Path | None, payload: dict[str, Any] | None) -> datetime | None:
    generated_at = parse_utc_iso(payload.get("generatedAtUtc") if payload else None)
    if generated_at is not None:
        return generated_at
    if path is None or not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


def observation_age(path: Path | None, payload: dict[str, Any] | None) -> dict[str, Any]:
    generated_at = observation_generated_at(path, payload)
    if generated_at is None:
        return {
            "generatedAtUtc": None,
            "ageSeconds": None,
            "maxAgeSeconds": OBSERVATION_MAX_AGE_SECONDS,
            "stale": None,
        }
    age_seconds = max(0, int((datetime.now(timezone.utc) - generated_at).total_seconds()))
    return {
        "generatedAtUtc": generated_at.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "ageSeconds": age_seconds,
        "maxAgeSeconds": OBSERVATION_MAX_AGE_SECONDS,
        "stale": age_seconds > OBSERVATION_MAX_AGE_SECONDS,
    }


def recommended_next_actions(*, browser_ok: bool, computer_ok: bool) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    if not computer_ok:
        actions.append(
            {
                "key": "repair-computer-use-native-pipe",
                "reason": "Computer Use bootstrap/list_apps must succeed before desktop automation can be trusted.",
            }
        )
    if not browser_ok:
        actions.append(
            {
                "key": "run-no-write-browser-dashboard-smoke",
                "reason": "Browser Use should prove it can read the localhost MCP dashboard without transmitting data.",
            }
        )
    if not browser_ok or not computer_ok:
        actions.append(
            {
                "key": "record-observation-artifact",
                "reason": (
                    "After any external smoke changes readiness, store a local ignored observation JSON under the "
                    "desktop-control-readiness root."
                ),
            }
        )
    if browser_ok and computer_ok:
        actions.append(
            {
                "key": "maintenance-loop",
                "reason": "Both external desktop-control smokes are confirmed; keep observations fresh before live workflow use.",
            }
        )
    return actions


def observation_payload_from_args(args: argparse.Namespace) -> dict[str, Any]:
    browser_ok = bool(args.browser_dashboard_smoke_ok)
    computer_native_pipe_ok = bool(args.computer_use_native_pipe_ok)
    computer_list_apps_ok = bool(args.computer_use_list_apps_ok)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-desktop-control-observation",
        "generatedAtUtc": utc_iso(),
        "source": {
            "tool": "riftreader-desktop-control-readiness",
            "mode": "record-observation",
        },
        "browserUse": {
            "dashboardSmokeOk": browser_ok,
            "checkedUrl": args.browser_checked_url or DASHBOARD_URL,
            "statusUrl": args.browser_status_url or DASHBOARD_STATUS_URL,
            "notes": args.browser_notes or "",
        },
        "computerUse": {
            "nativePipeOk": computer_native_pipe_ok,
            "listAppsOk": computer_list_apps_ok,
            "stage": args.computer_use_stage or ("passed" if computer_native_pipe_ok else "setup"),
            "error": args.computer_use_error or "",
            "notes": args.computer_notes or "",
        },
        "safety": {
            "noClicks": True,
            "noTyping": True,
            "noWindowActions": True,
            "noRiftInput": True,
            "noGitMutation": True,
            "browserReadOnly": True,
            "computerUseInputSent": False,
        },
    }


def write_observation(repo_root: Path, args: argparse.Namespace) -> dict[str, Any]:
    payload = observation_payload_from_args(args)
    observation_dir = repo_root / OBSERVATION_ROOT / utc_stamp()
    observation_dir.mkdir(parents=True, exist_ok=True)
    observation_path = observation_dir / "observation.json"
    observation_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    readiness = readiness_payload(repo_root)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-desktop-control-observation-write",
        "generatedAtUtc": utc_iso(),
        "status": "stored",
        "ok": True,
        "observationPath": repo_rel(repo_root, observation_path),
        "readinessStatus": readiness.get("status"),
        "readinessOk": readiness.get("ok"),
        "readinessBlockers": readiness.get("blockers"),
        "latestObservation": readiness.get("latestObservation"),
        "safety": {
            **safety_flags(),
            "localObservationOnly": True,
            "browserAutomated": False,
            "computerUseAutomated": False,
            "desktopClicksSent": False,
            "desktopTypingSent": False,
            "serverStarted": False,
            "publicTunnelStarted": False,
        },
    }


def readiness_payload(repo_root: Path) -> dict[str, Any]:
    observation_path = latest_observation_path(repo_root)
    observation = load_json_object(observation_path)
    age = observation_age(observation_path, observation)
    browser_ok = bool_from_path(observation, "browserUse", "dashboardSmokeOk") is True
    computer_native_pipe_ok = bool_from_path(observation, "computerUse", "nativePipeOk") is True
    computer_list_apps_ok = bool_from_path(observation, "computerUse", "listAppsOk") is True
    computer_ok = computer_native_pipe_ok and computer_list_apps_ok
    blockers: list[str] = []
    warnings: list[str] = []
    if not browser_ok:
        blockers.append(BROWSER_USE_BLOCKER)
    if not computer_native_pipe_ok:
        blockers.append(COMPUTER_USE_BLOCKER)
    elif not computer_list_apps_ok:
        blockers.append(COMPUTER_USE_LIST_APPS_BLOCKER)
    if observation_path is None:
        warnings.append("no-desktop-control-observation-artifact")
    elif observation is None:
        blockers.append("desktop-control-observation-malformed")
    elif age.get("stale") is True:
        blockers.append(OBSERVATION_STALE_BLOCKER)
    status = "passed" if not blockers else "blocked"
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-desktop-control-readiness",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "ok": not blockers,
        "blockers": blockers,
        "warnings": warnings,
        "surfaces": {
            "browserUse": {
                "status": "passed" if browser_ok else "blocked",
                "ok": browser_ok,
                "requiredSmoke": {
                    "dashboardUrl": DASHBOARD_URL,
                    "statusUrl": DASHBOARD_STATUS_URL,
                    "expectedFinalReadiness": "status.json finalReadiness.ok=true",
                    "noWriteActions": True,
                },
                "blockers": [] if browser_ok else [BROWSER_USE_BLOCKER],
            },
            "computerUse": {
                "status": "passed" if computer_ok else "blocked",
                "ok": computer_ok,
                "requiredSmoke": {
                    "action": "supported Computer Use bootstrap plus list_apps only",
                    "noClicks": True,
                    "noTyping": True,
                    "noWindowActions": True,
                    "noRiftInput": True,
                },
                "blockers": [] if computer_ok else ([COMPUTER_USE_BLOCKER] if not computer_native_pipe_ok else [COMPUTER_USE_LIST_APPS_BLOCKER]),
            },
            "localDashboard": {
                "status": "ready" if script_exists(repo_root, "scripts/riftreader-mcp-dashboard.cmd") else "blocked",
                "script": "scripts\\riftreader-mcp-dashboard.cmd",
                "localhostOnly": True,
                "statusOnly": True,
            },
            "operatorLite": {
                "status": "ready" if script_exists(repo_root, "scripts/riftreader-operator-lite.cmd") else "blocked",
                "script": "scripts\\riftreader-operator-lite.cmd",
            },
        },
        "latestObservation": {
            "path": repo_rel(repo_root, observation_path),
            "present": observation is not None,
            "browserUseDashboardSmokeOk": browser_ok,
            "computerUseNativePipeOk": computer_native_pipe_ok,
            "computerUseListAppsOk": computer_list_apps_ok,
            "generatedAtUtc": age.get("generatedAtUtc"),
            "ageSeconds": age.get("ageSeconds"),
            "maxAgeSeconds": age.get("maxAgeSeconds"),
            "stale": age.get("stale"),
        },
        "observationTemplate": {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "riftreader-desktop-control-observation",
            "browserUse": {
                "dashboardSmokeOk": False,
                "checkedUrl": DASHBOARD_URL,
                "notes": "Set true only after a no-write browser smoke reads the dashboard/status JSON.",
            },
            "computerUse": {
                "nativePipeOk": False,
                "listAppsOk": False,
                "notes": "Set nativePipeOk true only after the supported Computer Use bootstrap/list_apps smoke succeeds.",
            },
            "safety": {
                "noClicks": True,
                "noTyping": True,
                "noWindowActions": True,
                "noRiftInput": True,
                "noGitMutation": True,
                "browserReadOnly": True,
                "computerUseInputSent": False,
            },
        },
        "recommendedNextActions": recommended_next_actions(browser_ok=browser_ok, computer_ok=computer_ok),
        "safety": {
            **safety_flags(),
            "statusOnly": True,
            "browserAutomated": False,
            "computerUseAutomated": False,
            "desktopClicksSent": False,
            "desktopTypingSent": False,
            "serverStarted": False,
            "publicTunnelStarted": False,
        },
    }


def self_test(repo_root: Path) -> dict[str, Any]:
    payload = readiness_payload(repo_root)
    text = json.dumps(payload, sort_keys=True)
    blockers: list[str] = []
    root_text = str(repo_root.resolve())
    if root_text in text or root_text.replace("\\", "\\\\") in text or root_text.replace("\\", "/") in text:
        blockers.append("absolute-repo-root-exposed")
    if payload.get("safety", {}).get("browserAutomated") is not False:
        blockers.append("browser-automation-flag-not-false")
    if payload.get("safety", {}).get("computerUseAutomated") is not False:
        blockers.append("computer-use-automation-flag-not-false")
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-desktop-control-readiness-self-test",
        "generatedAtUtc": utc_iso(),
        "status": "passed" if not blockers else "failed",
        "ok": not blockers,
        "blockers": blockers,
        "statusPreview": payload,
        "safety": {**safety_flags(), "statusOnly": True},
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only Browser/Computer Use readiness for RiftReader MCP.")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--record-observation", action="store_true", help="Write an ignored local observation artifact.")
    parser.add_argument("--browser-dashboard-smoke-ok", action="store_true")
    parser.add_argument("--browser-checked-url", default=DASHBOARD_URL)
    parser.add_argument("--browser-status-url", default=DASHBOARD_STATUS_URL)
    parser.add_argument("--browser-notes", default="")
    parser.add_argument("--computer-use-native-pipe-ok", action="store_true")
    parser.add_argument("--computer-use-list-apps-ok", action="store_true")
    parser.add_argument("--computer-use-stage", default="")
    parser.add_argument("--computer-use-error", default="")
    parser.add_argument("--computer-notes", default="")
    parser.add_argument("--json", action="store_true", help="Emit JSON. This helper is JSON-first; kept for wrapper symmetry.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    if args.record_observation:
        payload = write_observation(repo_root, args)
    elif args.self_test:
        payload = self_test(repo_root)
    else:
        payload = readiness_payload(repo_root)
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.record_observation:
        return 0
    if args.self_test:
        return 0 if payload.get("ok") else 1
    return 0 if payload.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
