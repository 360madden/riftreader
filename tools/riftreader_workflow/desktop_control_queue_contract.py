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


def contract_payload(repo_root: Path) -> dict[str, Any]:
    readiness = readiness_payload(repo_root)
    readiness_ok = bool(readiness.get("ok"))
    blockers = list(readiness.get("blockers") or [])
    repair_guide = repair_guide_payload()
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
        "queueItemSchema": {
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
