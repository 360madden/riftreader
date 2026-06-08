#!/usr/bin/env python3
"""Plan-only Browser/Computer command queue contract for the ChatGPT MCP lane.

This helper does not execute queued actions. It does not automate Browser Use,
Computer Use, desktop UI, RIFT input, tunnels, package apply, Git, CE, or x64dbg.
It only prints the inert contract future queue producers/consumers must satisfy.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

try:
    from .common import find_repo_root, safety_flags, utc_iso
    from .desktop_control_readiness import (
        COMPUTER_USE_BLOCKER,
        readiness_payload,
        repair_guide_payload,
    )
except ImportError:  # pragma: no cover - supports direct script execution.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.common import find_repo_root, safety_flags, utc_iso
    from riftreader_workflow.desktop_control_readiness import (
        COMPUTER_USE_BLOCKER,
        readiness_payload,
        repair_guide_payload,
    )


SCHEMA_VERSION = 1
QUEUE_DRAFT_ROOT = Path(".riftreader-local") / "riftreader-chatgpt-mcp" / "desktop-control-queue-drafts"


def queue_item_schema() -> dict[str, Any]:
    return {
        "required": [
            "schemaVersion",
            "kind",
            "queueId",
            "actionKey",
            "surface",
            "intent",
            "requiresHumanApproval",
            "dryRunOnly",
        ],
        "kind": "riftreader-desktop-control-queue-item",
        "surfaceValues": ["browser-use", "computer-use"],
        "dryRunOnlyMustBeTrue": True,
        "requiresHumanApprovalMustBeTrue": True,
        "allowedUntilReadinessPasses": [
            "browser-dashboard-status-read",
            "computer-use-bootstrap-list-apps-smoke",
            "chatgpt-window-discovery-no-input",
        ],
        "forbiddenActionFamilies": [
            "desktop-click",
            "desktop-typing",
            "window-activation",
            "browser-form-submit",
            "browser-sensitive-data-entry",
            "rift-input",
            "rift-movement",
            "reloadui",
            "package-apply",
            "git-mutation",
            "provider-write",
            "ce-x64dbg",
        ],
    }


def repo_rel(repo_root: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return str(path)


def load_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    except Exception:  # noqa: BLE001 - draft viewer must stay read-only and fail closed.
        return None


def validate_queue_item(payload: dict[str, Any]) -> list[str]:
    schema = queue_item_schema()
    blockers: list[str] = []
    for field in schema["required"]:
        if field not in payload:
            blockers.append(f"missing:{field}")
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        blockers.append("schemaVersion-invalid")
    if payload.get("kind") != schema["kind"]:
        blockers.append("kind-invalid")
    if payload.get("surface") not in schema["surfaceValues"]:
        blockers.append("surface-invalid")
    if payload.get("actionKey") not in schema["allowedUntilReadinessPasses"]:
        blockers.append("actionKey-not-allowed-before-readiness")
    if payload.get("dryRunOnly") is not True:
        blockers.append("dryRunOnly-not-true")
    if payload.get("requiresHumanApproval") is not True:
        blockers.append("requiresHumanApproval-not-true")
    forbidden_text = json.dumps(payload, sort_keys=True).lower()
    for family in schema["forbiddenActionFamilies"]:
        if family in forbidden_text:
            blockers.append(f"forbidden-action-family:{family}")
    return blockers


def queue_draft_viewer_payload(repo_root: Path) -> dict[str, Any]:
    draft_root = repo_root / QUEUE_DRAFT_ROOT
    draft_paths = sorted(
        [path for path in draft_root.glob("*.json") if path.is_file()] if draft_root.is_dir() else [],
        key=lambda path: (path.stat().st_mtime_ns, str(path)),
        reverse=True,
    )
    latest_path = draft_paths[0] if draft_paths else None
    latest_payload = load_json(latest_path) if latest_path else None
    latest_blockers = validate_queue_item(latest_payload) if isinstance(latest_payload, dict) else []
    latest_draft = None
    if latest_path is not None:
        latest_draft = {
            "path": repo_rel(repo_root, latest_path),
            "mtimeUtc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(latest_path.stat().st_mtime)),
            "parseOk": isinstance(latest_payload, dict),
            "valid": isinstance(latest_payload, dict) and not latest_blockers,
            "blockers": latest_blockers if isinstance(latest_payload, dict) else ["json-invalid"],
            "queueId": latest_payload.get("queueId") if isinstance(latest_payload, dict) else None,
            "actionKey": latest_payload.get("actionKey") if isinstance(latest_payload, dict) else None,
            "surface": latest_payload.get("surface") if isinstance(latest_payload, dict) else None,
            "dryRunOnly": latest_payload.get("dryRunOnly") if isinstance(latest_payload, dict) else None,
            "requiresHumanApproval": latest_payload.get("requiresHumanApproval") if isinstance(latest_payload, dict) else None,
        }
    return {
        "status": "ready",
        "ok": True,
        "root": str(QUEUE_DRAFT_ROOT),
        "exists": draft_root.is_dir(),
        "count": len(draft_paths),
        "latestDraft": latest_draft,
        "schema": queue_item_schema(),
        "safety": {
            **safety_flags(),
            "viewerOnly": True,
            "draftWriteEndpoint": False,
            "executionEndpoint": False,
            "queueWriteEndpoint": False,
            "browserAutomated": False,
            "computerUseAutomated": False,
            "desktopClicksSent": False,
            "desktopTypingSent": False,
            "windowActivationSent": False,
            "mcpToolExposed": False,
            "gitMutation": False,
            "providerWrites": False,
        },
    }


def contract_payload(repo_root: Path) -> dict[str, Any]:
    readiness = readiness_payload(repo_root)
    readiness_ok = bool(readiness.get("ok"))
    blockers = list(readiness.get("blockers") or [])
    repair_guide = repair_guide_payload()
    draft_viewer = queue_draft_viewer_payload(repo_root)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-desktop-control-command-queue-contract",
        "generatedAtUtc": utc_iso(),
        "status": "passed",
        "ok": True,
        "summary": "Plan-only contract for future Browser Use / Computer Use command queues. No execution is implemented here.",
        "execution": {
            "enabled": False,
            "status": "disabled",
            "reason": "Queue contract is inert until a separate reviewed executor is explicitly designed, approved, implemented, and validated.",
            "readinessRequiredBeforeExecutor": True,
            "currentDesktopReadinessOk": readiness_ok,
            "currentReadinessBlockers": blockers,
            "computerUseBlocked": COMPUTER_USE_BLOCKER in blockers,
            "executorImplemented": False,
            "mcpToolExposed": False,
            "operatorLiteExecutesQueue": False,
        },
        "readiness": {
            "status": readiness.get("status"),
            "ok": readiness_ok,
            "blockers": blockers,
            "latestObservation": readiness.get("latestObservation"),
            "repairGuideCommand": repair_guide.get("recordBlockedCommand"),
        },
        "queueItemSchema": queue_item_schema(),
        "queueDraftViewer": draft_viewer,
        "chatGptWindowDiscovery": {
            "status": "blocked" if not readiness_ok else "ready",
            "ok": readiness_ok,
            "actionKey": "chatgpt-window-discovery-no-input",
            "scope": "future-no-input-contract",
            "requiredBeforeUse": [
                "desktopControlReadiness.ok=true",
                "computerUse.nativePipeOk=true",
                "computerUse.listAppsOk=true",
                "no clicks",
                "no typing",
                "no window activation unless separately approved",
                "no ChatGPT prompt submission",
                "no RIFT input or movement",
            ],
            "allowedEvidenceOnly": [
                "enumerated app/window metadata from Computer Use list_apps",
                "operator-readable window-title candidates",
                "no-input target identity draft",
            ],
            "blockedBy": blockers,
        },
        "stateMachine": [
            {
                "state": "contract-only",
                "allowed": True,
                "description": "Emit this contract and readiness status only.",
            },
            {
                "state": "readiness-smoke",
                "allowed": True,
                "description": "Record external Browser Use dashboard smoke and Computer Use bootstrap/list_apps proof only.",
            },
            {
                "state": "queue-draft",
                "allowed": False,
                "description": "Future inert queue draft storage requires separate schema/tests and must remain dry-run-only.",
            },
            {
                "state": "executor",
                "allowed": False,
                "description": "No executor exists. Any executor requires explicit review, readiness proof, and safety gates.",
            },
            {
                "state": "live-rift-control",
                "allowed": False,
                "description": "Live RIFT input, movement, or stimulus requires explicit operator approval and fresh proof gates.",
            },
        ],
        "requiredGatesBeforeAnyFutureExecutor": [
            "desktopControlReadiness.ok=true",
            "latestObservation.stale=false",
            "computerUse.nativePipeOk=true",
            "computerUse.listAppsOk=true",
            "Browser Use dashboard smoke current",
            "exact target window identity captured before any desktop action",
            "human approval for any action with external side effects",
            "explicit live-RIFT approval before any game input or movement",
        ],
        "recommendedNextActions": [
            {
                "key": "repair-computer-use-native-pipe",
                "command": [
                    "scripts\\riftreader-operator-lite.cmd",
                    "--desktop-control-repair-guide",
                    "--json",
                ],
                "reason": "Computer Use native pipe/list_apps proof is required before desktop automation can be trusted.",
            },
            {
                "key": "record-computer-use-success-observation",
                "command": [
                    "scripts\\riftreader-desktop-control-readiness.cmd",
                    "--record-observation",
                    "--browser-dashboard-smoke-ok",
                    "--computer-use-native-pipe-ok",
                    "--computer-use-list-apps-ok",
                    "--computer-use-stage",
                    "passed",
                    "--json",
                ],
                "reason": "After Computer Use bootstrap/list_apps succeeds, store durable ignored readiness evidence.",
            },
        ],
        "safety": {
            **safety_flags(),
            "contractOnly": True,
            "dryRunOnly": True,
            "executionEndpoint": False,
            "queueWriteEndpoint": False,
            "browserAutomated": False,
            "computerUseAutomated": False,
            "desktopClicksSent": False,
            "desktopTypingSent": False,
            "windowActivationSent": False,
            "serverStarted": False,
            "publicTunnelStarted": False,
            "chatGptRegistrationPerformed": False,
            "packageApply": False,
            "gitMutation": False,
            "providerWrites": False,
            "mcpToolExposed": False,
        },
    }


def self_test(repo_root: Path) -> dict[str, Any]:
    payload = contract_payload(repo_root)
    text = json.dumps(payload, sort_keys=True)
    blockers: list[str] = []
    root_text = str(repo_root.resolve())
    if root_text in text or root_text.replace("\\", "\\\\") in text or root_text.replace("\\", "/") in text:
        blockers.append("absolute-repo-root-exposed")
    safety = payload.get("safety", {})
    execution = payload.get("execution", {})
    if safety.get("contractOnly") is not True:
        blockers.append("contract-only-flag-missing")
    if safety.get("executionEndpoint") is not False:
        blockers.append("execution-endpoint-not-false")
    if safety.get("desktopClicksSent") is not False:
        blockers.append("desktop-clicks-sent-not-false")
    if execution.get("enabled") is not False:
        blockers.append("execution-enabled-not-false")
    if execution.get("executorImplemented") is not False:
        blockers.append("executor-implemented-not-false")
    draft_viewer = payload.get("queueDraftViewer", {})
    if draft_viewer.get("safety", {}).get("viewerOnly") is not True:
        blockers.append("queue-draft-viewer-only-flag-missing")
    if draft_viewer.get("safety", {}).get("draftWriteEndpoint") is not False:
        blockers.append("queue-draft-write-endpoint-not-false")
    if draft_viewer.get("safety", {}).get("executionEndpoint") is not False:
        blockers.append("queue-draft-execution-endpoint-not-false")
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-desktop-control-command-queue-contract-self-test",
        "generatedAtUtc": utc_iso(),
        "status": "passed" if not blockers else "failed",
        "ok": not blockers,
        "blockers": blockers,
        "statusPreview": payload,
        "safety": {
            **safety_flags(),
            "contractOnly": True,
            "executionEndpoint": False,
            "gitMutation": False,
            "providerWrites": False,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plan-only Browser/Computer command queue contract.")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true", help="Emit JSON. This helper is JSON-first; kept for wrapper symmetry.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    payload = self_test(repo_root) if args.self_test else contract_payload(repo_root)
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.self_test:
        return 0 if payload.get("ok") else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
